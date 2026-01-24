"""
Bulk Image Updater for Product Database
Run this script to add images to all products in your database
"""

import sqlite3
import os

# Configuration
DB_PATH = "database.db"
IMAGE_FOLDER = "static/product_images"  # Create this folder

# Category-to-default-image mapping
CATEGORY_DEFAULTS = {
    'Engine Parts': '/static/defaults/engine.jpg',
    'Brake System': '/static/defaults/brakes.jpg',
    'Suspension': '/static/defaults/suspension.jpg',
    'Electrical': '/static/defaults/electrical.jpg',
    'Filters': '/static/defaults/filters.jpg',
    'Lubricants': '/static/defaults/lubricants.jpg',
    'Body Parts': '/static/defaults/body.jpg',
    'Transmission': '/static/defaults/transmission.jpg',
}

def update_images_from_folder():
    """
    Update products with images from a folder
    Assumes images are named: {inventory_id}.jpg or {sup_part_no}.jpg
    """
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    
    products = cursor.execute("SELECT inventory_id, sup_part_no FROM inventory").fetchall()
    
    updated = 0
    for product in products:
        # Try to find image by ID or part number
        possible_names = [
            f"{product['inventory_id']}.jpg",
            f"{product['inventory_id']}.png",
            f"{product['sup_part_no']}.jpg",
            f"{product['sup_part_no']}.png",
        ]
        
        for img_name in possible_names:
            img_path = os.path.join(IMAGE_FOLDER, img_name)
            if os.path.exists(img_path):
                web_path = f"/static/product_images/{img_name}"
                cursor.execute(
                    "UPDATE inventory SET image_url = ? WHERE inventory_id = ?",
                    (web_path, product['inventory_id'])
                )
                updated += 1
                print(f"✓ Updated product {product['inventory_id']}: {img_name}")
                break
    
    conn.commit()
    conn.close()
    print(f"\n✅ Updated {updated} products with images")


def set_category_defaults():
    """
    Set default images based on product category
    """
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    for category, default_img in CATEGORY_DEFAULTS.items():
        result = cursor.execute(
            """UPDATE inventory 
               SET image_url = ? 
               WHERE category = ? AND (image_url IS NULL OR image_url = '')""",
            (default_img, category)
        )
        print(f"✓ Set default for {category}: {result.rowcount} products")
    
    conn.commit()
    conn.close()
    print("\n✅ Category defaults applied")


def use_external_api():
    """
    Fetch images from an external API (like Unsplash, Pexels)
    This is an example - you'd need API keys
    """
    import requests
    
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    
    products = cursor.execute(
        "SELECT inventory_id, hem_name, category FROM inventory WHERE image_url IS NULL LIMIT 100"
    ).fetchall()
    
    for product in products:
        # Example with Unsplash (requires API key)
        # search_term = f"{product['category']} automotive"
        # response = requests.get(
        #     "https://api.unsplash.com/search/photos",
        #     params={"query": search_term, "per_page": 1},
        #     headers={"Authorization": "Client-ID YOUR_API_KEY"}
        # )
        # if response.ok:
        #     data = response.json()
        #     if data['results']:
        #         image_url = data['results'][0]['urls']['regular']
        #         cursor.execute(
        #             "UPDATE inventory SET image_url = ? WHERE inventory_id = ?",
        #             (image_url, product['inventory_id'])
        #         )
        pass
    
    conn.commit()
    conn.close()


def generate_placeholder_urls():
    """
    Generate nice placeholder URLs for all products
    Uses a free service like UI Avatars or Placeholder.com
    """
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    
    products = cursor.execute(
        "SELECT inventory_id, hem_name, category FROM inventory WHERE image_url IS NULL OR image_url = ''"
    ).fetchall()
    
    updated = 0
    for product in products:
        # Create a nice placeholder with product name
        product_name_short = product['hem_name'][:30].replace(' ', '+')
        placeholder_url = f"https://via.placeholder.com/300x200/1e40af/ffffff?text={product_name_short}"
        
        cursor.execute(
            "UPDATE inventory SET image_url = ? WHERE inventory_id = ?",
            (placeholder_url, product['inventory_id'])
        )
        updated += 1
        
        if updated % 100 == 0:
            print(f"Progress: {updated} products updated...")
    
    conn.commit()
    conn.close()
    print(f"\n✅ Generated placeholders for {updated} products")


# ====================
# MAIN EXECUTION
# ====================
if __name__ == "__main__":
    print("=" * 60)
    print("BULK IMAGE UPDATE TOOL")
    print("=" * 60)
    print("\nChoose an option:")
    print("1. Update from local image folder")
    print("2. Set category-based default images")
    print("3. Generate placeholder URLs for all products")
    print("4. All of the above (recommended)")
    
    choice = input("\nEnter choice (1-4): ").strip()
    
    if choice == "1":
        update_images_from_folder()
    elif choice == "2":
        set_category_defaults()
    elif choice == "3":
        generate_placeholder_urls()
    elif choice == "4":
        print("\n[1/3] Updating from local folder...")
        update_images_from_folder()
        print("\n[2/3] Setting category defaults...")
        set_category_defaults()
        print("\n[3/3] Generating placeholders for remaining products...")
        generate_placeholder_urls()
    else:
        print("❌ Invalid choice")
    
    print("\n" + "=" * 60)
    print("DONE!")
    print("=" * 60)