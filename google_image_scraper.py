"""
Google Image Scraper for Auto Parts
Automatically finds and assigns images to products based on their names
"""

import sqlite3
import requests
import time
from urllib.parse import quote_plus

# ============================================
# OPTION 1: Using Google Custom Search API
# ============================================
def google_custom_search(api_key, search_engine_id):
    """
    Uses official Google Custom Search API
    GET YOUR FREE API KEY: https://developers.google.com/custom-search/v1/overview
    - Go to Google Cloud Console
    - Create project -> Enable Custom Search API
    - Get API key
    - Create Custom Search Engine at: https://cse.google.com/cse/
    
    FREE TIER: 100 searches/day
    """
    conn = sqlite3.connect('database.db')
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    
    # Get products without images
    products = cursor.execute("""
        SELECT inventory_id, hem_name, category, sup_part_no 
        FROM inventory 
        WHERE image_url IS NULL OR image_url LIKE '/static/defaults/%'
        LIMIT 100
    """).fetchall()
    
    updated = 0
    
    for product in products:
        # Build search query
        search_query = f"{product['hem_name']} {product['category']} automotive part"
        
        try:
            # Google Custom Search API call
            url = "https://www.googleapis.com/customsearch/v1"
            params = {
                'key': api_key,
                'cx': search_engine_id,
                'q': search_query,
                'searchType': 'image',
                'num': 1,
                'imgSize': 'medium',
                'safe': 'active'
            }
            
            response = requests.get(url, params=params, timeout=10)
            
            if response.ok:
                data = response.json()
                if 'items' in data and len(data['items']) > 0:
                    image_url = data['items'][0]['link']
                    
                    # Update database
                    cursor.execute(
                        "UPDATE inventory SET image_url = ? WHERE inventory_id = ?",
                        (image_url, product['inventory_id'])
                    )
                    conn.commit()
                    
                    updated += 1
                    print(f"✓ [{updated}] {product['hem_name'][:40]} -> Image found")
                else:
                    print(f"✗ No image found for: {product['hem_name']}")
            else:
                print(f"❌ API Error: {response.status_code}")
                
        except Exception as e:
            print(f"❌ Error for {product['hem_name']}: {e}")
        
        # Rate limiting - don't overwhelm the API
        time.sleep(1)
    
    conn.close()
    print(f"\n✅ Successfully updated {updated} products!")


# ============================================
# OPTION 2: Web Scraping (No API key needed)
# ============================================
def scrape_google_images():
    """
    Scrapes Google Images directly (No API key needed)
    NOTE: Google may block you if you make too many requests
    Use responsibly and add delays between requests
    """
    import re
    
    conn = sqlite3.connect('database.db')
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    
    # Get products
    products = cursor.execute("""
        SELECT inventory_id, hem_name, category, sup_part_no 
        FROM inventory 
        WHERE image_url IS NULL OR image_url LIKE '/static/defaults/%'
        LIMIT 50
    """).fetchall()
    
    updated = 0
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
    }
    
    for product in products:
        search_query = f"{product['hem_name']} {product['category']} automotive"
        encoded_query = quote_plus(search_query)
        
        try:
            # Google Images search URL
            url = f"https://www.google.com/search?q={encoded_query}&tbm=isch"
            
            response = requests.get(url, headers=headers, timeout=10)
            
            if response.ok:
                # Extract first image URL using regex
                # This finds URLs in the HTML response
                image_urls = re.findall(r'"(https?://[^"]+\.(?:jpg|jpeg|png|webp))"', response.text)
                
                if image_urls:
                    # Filter out Google's own icons and get first real image
                    real_images = [url for url in image_urls if 'google.com' not in url]
                    
                    if real_images:
                        image_url = real_images[0]
                        
                        cursor.execute(
                            "UPDATE inventory SET image_url = ? WHERE inventory_id = ?",
                            (image_url, product['inventory_id'])
                        )
                        conn.commit()
                        
                        updated += 1
                        print(f"✓ [{updated}] {product['hem_name'][:40]}")
                    else:
                        print(f"✗ No suitable image for: {product['hem_name']}")
                else:
                    print(f"✗ No images found for: {product['hem_name']}")
            
        except Exception as e:
            print(f"❌ Error: {e}")
        
        # Important: Add delay to avoid being blocked
        time.sleep(3)
    
    conn.close()
    print(f"\n✅ Successfully updated {updated} products!")


# ============================================
# OPTION 3: Bing Image Search API (Alternative)
# ============================================
def bing_image_search(subscription_key):
    """
    Uses Bing Image Search API
    GET FREE KEY: https://azure.microsoft.com/en-us/services/cognitive-services/bing-image-search-api/
    FREE TIER: 1000 transactions/month
    """
    conn = sqlite3.connect('database.db')
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    
    products = cursor.execute("""
        SELECT inventory_id, hem_name, category 
        FROM inventory 
        WHERE image_url IS NULL OR image_url LIKE '/static/defaults/%'
        LIMIT 100
    """).fetchall()
    
    updated = 0
    endpoint = "https://api.bing.microsoft.com/v7.0/images/search"
    
    for product in products:
        search_query = f"{product['hem_name']} automotive part"
        
        try:
            headers = {"Ocp-Apim-Subscription-Key": subscription_key}
            params = {
                "q": search_query,
                "count": 1,
                "imageType": "Photo",
                "size": "Medium"
            }
            
            response = requests.get(endpoint, headers=headers, params=params, timeout=10)
            
            if response.ok:
                data = response.json()
                if 'value' in data and len(data['value']) > 0:
                    image_url = data['value'][0]['contentUrl']
                    
                    cursor.execute(
                        "UPDATE inventory SET image_url = ? WHERE inventory_id = ?",
                        (image_url, product['inventory_id'])
                    )
                    conn.commit()
                    
                    updated += 1
                    print(f"✓ [{updated}] {product['hem_name'][:40]}")
            
        except Exception as e:
            print(f"❌ Error: {e}")
        
        time.sleep(0.5)
    
    conn.close()
    print(f"\n✅ Successfully updated {updated} products!")


# ============================================
# OPTION 4: Use SerpAPI (Easiest, Paid but Reliable)
# ============================================
def serpapi_search(api_key):
    """
    Uses SerpAPI - a paid service that handles Google scraping
    GET API KEY: https://serpapi.com/
    FREE TIER: 100 searches/month
    """
    conn = sqlite3.connect('database.db')
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    
    products = cursor.execute("""
        SELECT inventory_id, hem_name, category 
        FROM inventory 
        WHERE image_url IS NULL OR image_url LIKE '/static/defaults/%'
        LIMIT 100
    """).fetchall()
    
    updated = 0
    
    for product in products:
        search_query = f"{product['hem_name']} {product['category']} automotive"
        
        try:
            url = "https://serpapi.com/search"
            params = {
                'api_key': api_key,
                'q': search_query,
                'tbm': 'isch',  # Image search
                'num': 1
            }
            
            response = requests.get(url, params=params, timeout=10)
            
            if response.ok:
                data = response.json()
                if 'images_results' in data and len(data['images_results']) > 0:
                    image_url = data['images_results'][0]['original']
                    
                    cursor.execute(
                        "UPDATE inventory SET image_url = ? WHERE inventory_id = ?",
                        (image_url, product['inventory_id'])
                    )
                    conn.commit()
                    
                    updated += 1
                    print(f"✓ [{updated}] {product['hem_name'][:40]}")
            
        except Exception as e:
            print(f"❌ Error: {e}")
        
        time.sleep(1)
    
    conn.close()
    print(f"\n✅ Successfully updated {updated} products!")


# ============================================
# MAIN EXECUTION
# ============================================
if __name__ == "__main__":
    print("="*60)
    print("GOOGLE IMAGE SCRAPER FOR AUTO PARTS")
    print("="*60)
    print("\nChoose a method:")
    print("1. Google Custom Search API (Recommended, 100 free/day)")
    print("2. Web Scraping (Free but may get blocked)")
    print("3. Bing Image Search API (1000 free/month)")
    print("4. SerpAPI (Easiest, 100 free/month)")
    
    choice = input("\nEnter choice (1-4): ").strip()
    
    if choice == "1":
        api_key = input("Enter Google API Key: ").strip()
        search_engine_id = input("Enter Search Engine ID: ").strip()
        google_custom_search(api_key, search_engine_id)
        
    elif choice == "2":
        print("\n⚠️  Warning: This may get blocked by Google if overused")
        print("Starting scraping with 3-second delays...")
        time.sleep(2)
        scrape_google_images()
        
    elif choice == "3":
        api_key = input("Enter Bing API Key: ").strip()
        bing_image_search(api_key)
        
    elif choice == "4":
        api_key = input("Enter SerpAPI Key: ").strip()
        serpapi_search(api_key)
        
    else:
        print("❌ Invalid choice")
    
    print("\n" + "="*60)
    print("DONE! Refresh your cart page to see images!")
    print("="*60)