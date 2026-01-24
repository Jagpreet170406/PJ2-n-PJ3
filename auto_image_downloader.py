"""
FULLY AUTOMATED IMAGE DOWNLOADER
Set it and forget it - handles ALL products automatically
"""

import sqlite3
import requests
import time
import os
from urllib.parse import quote_plus
import random

# Configuration
DB_PATH = "database.db"
SAVE_IMAGES_LOCALLY = True  # Set False to just store URLs
IMAGE_FOLDER = "static/product_images"
BATCH_SIZE = 100  # Process 100 products at a time
DELAY_BETWEEN_REQUESTS = 2  # seconds (to avoid being blocked)

# Create image folder if saving locally
if SAVE_IMAGES_LOCALLY and not os.path.exists(IMAGE_FOLDER):
    os.makedirs(IMAGE_FOLDER)

def download_image(url, save_path):
    """Download image from URL and save locally"""
    try:
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        }
        response = requests.get(url, headers=headers, timeout=10, stream=True)
        if response.ok:
            with open(save_path, 'wb') as f:
                for chunk in response.iter_content(1024):
                    f.write(chunk)
            return True
    except:
        return False
    return False

def find_image_for_product(product_name, category):
    """
    Scrape Google Images for a product
    Returns image URL or None
    """
    search_query = f"{product_name} {category} automotive part"
    encoded_query = quote_plus(search_query)
    
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
        'Accept-Language': 'en-US,en;q=0.5',
        'Referer': 'https://www.google.com/'
    }
    
    try:
        # Use DuckDuckGo instead (no rate limiting!)
        url = f"https://duckduckgo.com/?q={encoded_query}&iax=images&ia=images"
        response = requests.get(url, headers=headers, timeout=10)
        
        if response.ok:
            # Extract image URLs from response
            import re
            # Look for image URLs in the response
            image_pattern = r'https?://[^\s<>"]+?\.(?:jpg|jpeg|png|webp)'
            matches = re.findall(image_pattern, response.text)
            
            if matches:
                # Filter out low quality images
                good_images = [m for m in matches if len(m) < 500 and 'icon' not in m.lower()]
                if good_images:
                    return good_images[0]
    except Exception as e:
        print(f"Error searching: {e}")
    
    return None

def automated_image_update():
    """
    Main function - fully automated, processes ALL products
    """
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    
    # Count total products needing images
    total = cursor.execute("""
        SELECT COUNT(*) FROM inventory 
        WHERE image_url IS NULL OR image_url LIKE '/static/defaults/%'
    """).fetchone()[0]
    
    print("="*70)
    print(f"🚀 STARTING AUTOMATED IMAGE DOWNLOAD")
    print(f"📊 Total products to process: {total}")
    print(f"⏱️  Estimated time: {(total * DELAY_BETWEEN_REQUESTS) / 60:.1f} minutes")
    print("="*70)
    print("\n💡 TIP: You can close this and come back - progress is saved to DB")
    print("Press Ctrl+C anytime to stop\n")
    
    input("Press ENTER to start...")
    
    processed = 0
    successful = 0
    failed = 0
    
    # Process in batches
    offset = 0
    
    try:
        while True:
            # Get next batch
            products = cursor.execute(f"""
                SELECT inventory_id, hem_name, category, sup_part_no 
                FROM inventory 
                WHERE image_url IS NULL OR image_url LIKE '/static/defaults/%'
                LIMIT {BATCH_SIZE} OFFSET {offset}
            """).fetchall()
            
            if not products:
                break  # Done!
            
            for product in products:
                processed += 1
                
                print(f"\n[{processed}/{total}] Processing: {product['hem_name'][:50]}")
                
                # Find image
                image_url = find_image_for_product(product['hem_name'], product['category'])
                
                if image_url:
                    if SAVE_IMAGES_LOCALLY:
                        # Download and save locally
                        filename = f"{product['inventory_id']}.jpg"
                        save_path = os.path.join(IMAGE_FOLDER, filename)
                        
                        if download_image(image_url, save_path):
                            web_path = f"/static/product_images/{filename}"
                            cursor.execute(
                                "UPDATE inventory SET image_url = ? WHERE inventory_id = ?",
                                (web_path, product['inventory_id'])
                            )
                            successful += 1
                            print(f"  ✅ Downloaded and saved: {filename}")
                        else:
                            # Save URL instead
                            cursor.execute(
                                "UPDATE inventory SET image_url = ? WHERE inventory_id = ?",
                                (image_url, product['inventory_id'])
                            )
                            successful += 1
                            print(f"  ✅ Saved URL: {image_url[:50]}...")
                    else:
                        # Just save URL
                        cursor.execute(
                            "UPDATE inventory SET image_url = ? WHERE inventory_id = ?",
                            (image_url, product['inventory_id'])
                        )
                        successful += 1
                        print(f"  ✅ Found: {image_url[:60]}...")
                else:
                    failed += 1
                    print(f"  ❌ No image found")
                
                # Commit every 10 products
                if processed % 10 == 0:
                    conn.commit()
                    print(f"\n💾 Progress saved: {successful} successful, {failed} failed")
                
                # Rate limiting with random delay
                delay = DELAY_BETWEEN_REQUESTS + random.uniform(0, 1)
                time.sleep(delay)
            
            offset += BATCH_SIZE
            
    except KeyboardInterrupt:
        print("\n\n⏸️  PAUSED by user")
        conn.commit()
    
    conn.commit()
    conn.close()
    
    print("\n" + "="*70)
    print("✅ COMPLETED!")
    print(f"📊 Results:")
    print(f"   • Total processed: {processed}")
    print(f"   • Successful: {successful}")
    print(f"   • Failed: {failed}")
    print(f"   • Success rate: {(successful/processed*100):.1f}%")
    print("="*70)

# Alternative: Use Unsplash API (High Quality Stock Images)
def use_unsplash_api():
    """
    Uses Unsplash API for high-quality stock images
    Sign up FREE: https://unsplash.com/developers
    50 requests/hour FREE
    """
    API_KEY = input("Enter your Unsplash API Key (or press Enter to skip): ").strip()
    
    if not API_KEY:
        print("Skipping Unsplash...")
        return
    
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    
    products = cursor.execute("""
        SELECT inventory_id, hem_name, category 
        FROM inventory 
        WHERE image_url IS NULL OR image_url LIKE '/static/defaults/%'
        LIMIT 50
    """).fetchall()
    
    updated = 0
    
    for product in products:
        search = f"{product['category']} automotive"
        
        try:
            response = requests.get(
                "https://api.unsplash.com/search/photos",
                params={'query': search, 'per_page': 1},
                headers={'Authorization': f'Client-ID {API_KEY}'}
            )
            
            if response.ok:
                data = response.json()
                if data['results']:
                    image_url = data['results'][0]['urls']['regular']
                    cursor.execute(
                        "UPDATE inventory SET image_url = ? WHERE inventory_id = ?",
                        (image_url, product['inventory_id'])
                    )
                    updated += 1
                    print(f"✅ [{updated}] {product['hem_name'][:40]}")
            
            time.sleep(1)
            
        except Exception as e:
            print(f"Error: {e}")
    
    conn.commit()
    conn.close()
    print(f"\n✅ Updated {updated} products with Unsplash images")

if __name__ == "__main__":
    print("\n🎯 CHOOSE YOUR METHOD:\n")
    print("1. 🤖 FULLY AUTOMATED (Recommended)")
    print("   - Runs completely hands-free")
    print("   - Processes ALL products")
    print("   - Can pause/resume anytime")
    print("   - FREE (uses web scraping)")
    print()
    print("2. 📸 UNSPLASH API (High Quality)")
    print("   - Professional stock photos")
    print("   - 50/hour limit")
    print("   - Requires free API key")
    print()
    
    choice = input("Enter choice (1 or 2): ").strip()
    
    if choice == "1":
        automated_image_update()
    elif choice == "2":
        use_unsplash_api()
    else:
        print("Invalid choice")