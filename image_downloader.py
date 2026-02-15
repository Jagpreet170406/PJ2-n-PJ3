#!/usr/bin/env python3
"""
ACCURATE OEM PARTS IMAGE DOWNLOADER v2
======================================
Sources images accurately using OEM SKU numbers from multiple trusted sources.

Strategy (in priority order):
  1. DuckDuckGo Image Search (SKU-specific, finds real product pages)
  2. eBay Motors (real product listing photos)
  3. AutoParts-specific CDNs by OEM brand (Hyundai/Kia, Honda, Ford, Mazda)
  4. Google Images scrape (fallback)

INSTALL:
    pip install requests pillow beautifulsoup4

USAGE:
    Place this script in the same folder as your CSV file, then run:
    python image_downloader_v2.py
"""

import csv
import os
import re
import time
import glob
from pathlib import Path
from io import BytesIO
from concurrent.futures import ThreadPoolExecutor, as_completed
from threading import Lock

import requests
from PIL import Image
from bs4 import BeautifulSoup

# CONFIG
OUTPUT_DIR  = "product_images_v2"
MIN_SIZE    = 200
MAX_SIZE    = 3000
DELAY       = 0.4
MAX_TRIES   = 3
NUM_WORKERS = 5

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    ),
    "Accept-Language": "en-US,en;q=0.9",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
}

IMG_HEADERS = {
    "User-Agent": HEADERS["User-Agent"],
    "Accept": "image/webp,image/apng,image/*,*/*;q=0.8",
    "Referer": "https://www.google.com/",
}

print_lock = Lock()
stats_lock = Lock()
stats = {"ddg": 0, "ebay": 0, "oem": 0, "google": 0, "failed": 0, "skipped": 0}


def detect_brand(sku):
    sku = sku.upper()
    if re.match(r'^(58|59|95|97)\d{3}-', sku):         return "hyundai_kia"
    if re.match(r'^0K\d', sku):                         return "hyundai_kia"
    if re.match(r'^H\d{5}-', sku):                      return "honda"
    if re.match(r'^(33|45|46|44)\d{3}-\d', sku):       return "honda"
    if re.match(r'^[0-9A-Z]{4}[0-9]{7}[A-Z]{2}$', sku): return "ford"
    if re.match(r'^[A-Z0-9]{4}-\d{2}-', sku):          return "mazda"
    if re.match(r'^N\d{3}-', sku):                      return "mazda"
    if re.match(r'^BHP', sku):                          return "mazda"
    return "generic"


def download_image(url, referer=None):
    hdrs = dict(IMG_HEADERS)
    if referer:
        hdrs["Referer"] = referer
    try:
        r = requests.get(url, headers=hdrs, timeout=12, stream=True)
        if r.status_code != 200:
            return None
        ctype = r.headers.get("Content-Type", "")
        if "image" not in ctype and not url.lower().endswith((".jpg", ".jpeg", ".png", ".webp")):
            return None
        img = Image.open(BytesIO(r.content))
        w, h = img.size
        if w < MIN_SIZE or h < MIN_SIZE or w > MAX_SIZE or h > MAX_SIZE:
            return None
        if img.mode != "RGB":
            bg = Image.new("RGB", img.size, (255, 255, 255))
            try:
                bg.paste(img, mask=img.split()[-1])
            except Exception:
                bg.paste(img)
            img = bg
        return img
    except Exception:
        return None


def get_ddg_vqd(query):
    url = f"https://duckduckgo.com/?q={requests.utils.quote(query)}&iax=images&ia=images"
    try:
        r = requests.get(url, headers=HEADERS, timeout=10)
        m = re.search(r"vqd=['\"]([\d-]+)['\"]", r.text)
        if m:
            return m.group(1)
    except Exception:
        pass
    return None


def try_duckduckgo(sku, product_name):
    clean_name = re.sub(r'\b(ASSY|UNIT|SET|KIT|LH|RH|FRT|RR|REAR|FRONT)\b', '', product_name, flags=re.I).strip()
    query = f"{sku} {clean_name} auto part OEM"
    vqd = get_ddg_vqd(query)
    if not vqd:
        return None, None
    api_url = (
        f"https://duckduckgo.com/i.js"
        f"?q={requests.utils.quote(query)}&vqd={vqd}"
        f"&o=json&l=us-en&p=1&s=0&u=bing&f=&dc=&type=photos"
    )
    try:
        time.sleep(DELAY)
        r = requests.get(api_url, headers=HEADERS, timeout=12)
        results = r.json().get("results", [])
        priority = ["ebay","amazon","rockauto","autozone","oreillyauto","carparts",
                    "partsfan","autodoc","buyautoparts","carid","partsgeek","genuineparts","oem"]

        def score(res):
            u = res.get("image", "").lower()
            s = sum(2 for d in priority if d in u)
            w, h = res.get("width", 0) or 0, res.get("height", 0) or 0
            if w >= 400 and h >= 400:
                s += 1
            return s

        results.sort(key=score, reverse=True)
        for result in results[:MAX_TRIES]:
            img_url = result.get("image")
            if not img_url:
                continue
            img = download_image(img_url, referer=result.get("url", ""))
            if img:
                return img, "DDG"
            time.sleep(0.15)
    except Exception:
        pass
    return None, None


def try_ebay(sku):
    url = (f"https://www.ebay.com/sch/i.html"
           f"?_nkw={requests.utils.quote(sku)}&_sacat=6030&LH_ItemCondition=1000&_ipg=8")
    try:
        time.sleep(DELAY)
        r = requests.get(url, headers=HEADERS, timeout=12)
        soup = BeautifulSoup(r.text, "html.parser")
        img_tags = soup.select(".s-item__image-img, .srp-results img[src*='i.ebayimg.com']")
        urls = []
        for tag in img_tags:
            src = tag.get("src") or tag.get("data-src") or ""
            if "i.ebayimg.com" in src:
                src = re.sub(r's-l\d+', 's-l640', src)
                urls.append(src)
        for img_url in urls[:MAX_TRIES]:
            img = download_image(img_url, referer=url)
            if img:
                return img, "eBay"
            time.sleep(0.15)
    except Exception:
        pass
    return None, None


def try_oem_cdn(sku, brand):
    sku_clean = re.sub(r'[\s/\\()]', '', sku)
    urls = []
    if brand == "hyundai_kia":
        urls = [f"https://www.hyundaipartsdeal.com/images/parts/{sku_clean}.jpg",
                f"https://www.kiapartsnow.com/images/parts/{sku_clean}.jpg"]
    elif brand == "honda":
        urls = [f"https://www.hondaautomotiveparts.com/assets/item/large/{sku_clean}.jpg",
                f"https://www.acuraoemparts.com/assets/item/large/{sku_clean}.jpg"]
    elif brand == "ford":
        urls = [f"https://www.fordparts.com/images/{sku_clean}.jpg"]
    elif brand == "mazda":
        urls = [f"https://www.mazdaoemparts.com/assets/item/large/{sku_clean}.jpg"]
    for url in urls:
        try:
            img = download_image(url)
            if img:
                return img, "OEM-CDN"
            time.sleep(0.1)
        except Exception:
            pass
    return None, None


def try_google_scrape(sku, product_name):
    query = f"{sku} {product_name} OEM part"
    url = f"https://www.google.com/search?q={requests.utils.quote(query)}&tbm=isch&num=10"
    try:
        time.sleep(DELAY)
        r = requests.get(url, headers=HEADERS, timeout=12)
        all_urls = re.findall(r'"(https?://[^"]+\.(?:jpg|jpeg|png|webp)(?:\?[^"]*)?)"', r.text)
        good = [u for u in all_urls if "gstatic" not in u and "google" not in u
                and "logo" not in u.lower() and len(u) < 600]

        def img_score(u):
            ul = u.lower()
            return sum(1 for kw in ["part","oem","product","item","auto","motor",sku.lower()[:6]] if kw in ul)

        good.sort(key=img_score, reverse=True)
        for img_url in good[:MAX_TRIES]:
            img = download_image(img_url, referer=url)
            if img:
                return img, "Google"
            time.sleep(0.15)
    except Exception:
        pass
    return None, None


def process_product(args):
    idx, total, row = args
    name     = row["Product Name"].strip()
    sku      = row["Sample SKU"].strip()
    filename = row["Image Filename"].strip()
    output   = os.path.join(OUTPUT_DIR, filename)

    if os.path.exists(output):
        with stats_lock:
            stats["skipped"] += 1
        return idx, "SKIP", name, sku

    brand = detect_brand(sku)
    img, method = try_duckduckgo(sku, name)
    if not img:
        img, method = try_ebay(sku)
    if not img:
        img, method = try_oem_cdn(sku, brand)
    if not img:
        img, method = try_google_scrape(sku, name)

    if img:
        img.save(output, "JPEG", quality=92, optimize=True)
        with stats_lock:
            key = method.lower().split("-")[0]
            if key in stats:
                stats[key] += 1
        return idx, method, name, sku
    else:
        with stats_lock:
            stats["failed"] += 1
        return idx, "FAILED", name, sku


def find_csv():
    for pattern in ["products_with_search_links*.csv", "*.csv"]:
        files = glob.glob(pattern)
        if files:
            return files[0]
    return None


def main():
    print("=" * 70)
    print("  ACCURATE OEM PARTS IMAGE DOWNLOADER v2")
    print(f"  Workers: {NUM_WORKERS}  |  Delay: {DELAY}s  |  Est. time: ~30-45 min")
    print("=" * 70)
    print()
    print("Sources (priority order):")
    print("  1. DuckDuckGo  — SKU-targeted, real product photos")
    print("  2. eBay Motors  — Actual listing images")
    print("  3. OEM CDNs     — Brand-specific (Hyundai/Kia, Honda, Ford, Mazda)")
    print("  4. Google       — Fallback scrape")
    print()

    csv_file = find_csv()
    if not csv_file:
        print("ERROR: No CSV file found in current directory!")
        input("Press Enter to exit...")
        return

    print(f"CSV      : {csv_file}")
    Path(OUTPUT_DIR).mkdir(exist_ok=True)
    print(f"Output   : {OUTPUT_DIR}/")
    print()

    with open(csv_file, "r", encoding="utf-8") as f:
        products = list(csv.DictReader(f))

    total = len(products)
    print(f"Products : {total:,}")
    print()
    input("Press Enter to start downloading...")
    print()

    start_time = time.time()
    completed  = 0
    work_items = [(idx + 1, total, row) for idx, row in enumerate(products)]

    with ThreadPoolExecutor(max_workers=NUM_WORKERS) as executor:
        futures = {executor.submit(process_product, item): item for item in work_items}

        for future in as_completed(futures):
            try:
                idx, method, name, sku = future.result()
                completed += 1
                symbol = "✓" if method not in ("FAILED","SKIP") else ("·" if method == "SKIP" else "✗")
                short  = method[:8] if method not in ("FAILED","SKIP") else method

                with print_lock:
                    print(f"[{idx:>5}/{total}] {symbol} {short:<8}  {name[:30]:<30}  {sku}")

                if completed % 100 == 0:
                    elapsed   = time.time() - start_time
                    rate      = completed / elapsed if elapsed > 0 else 0
                    remaining = (total - completed) / rate / 60 if rate > 0 else 0
                    done      = stats["ddg"] + stats["ebay"] + stats["oem"] + stats["google"]
                    tried     = done + stats["failed"]
                    pct       = done / tried * 100 if tried else 0
                    with print_lock:
                        print(f"\n  ── {completed}/{total} | "
                              f"DDG:{stats['ddg']} eBay:{stats['ebay']} OEM:{stats['oem']} "
                              f"Google:{stats['google']} Failed:{stats['failed']} | "
                              f"Hit:{pct:.0f}% | ~{remaining:.0f}min left\n")

            except KeyboardInterrupt:
                print("\nStopping...")
                executor.shutdown(wait=False)
                break
            except Exception as e:
                with print_lock:
                    print(f"  ERROR: {e}")

    elapsed = time.time() - start_time
    done    = stats["ddg"] + stats["ebay"] + stats["oem"] + stats["google"]
    print()
    print("=" * 70)
    print("  COMPLETE")
    print("=" * 70)
    print(f"  Time taken : {elapsed/60:.1f} minutes")
    print(f"  DuckDuckGo : {stats['ddg']:>6}")
    print(f"  eBay Motors: {stats['ebay']:>6}")
    print(f"  OEM CDN    : {stats['oem']:>6}")
    print(f"  Google     : {stats['google']:>6}")
    print(f"  ────────────────────")
    print(f"  Total OK   : {done:>6}")
    print(f"  Failed     : {stats['failed']:>6}")
    print(f"  Skipped    : {stats['skipped']:>6}")
    print()
    print(f"  Images saved to: {os.path.abspath(OUTPUT_DIR)}/")
    print("=" * 70)
    input("\nPress Enter to exit...")


if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        print(f"\nFATAL ERROR: {e}")
        input("Press Enter to exit...")