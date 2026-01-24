"""
SIMPLE IMAGE SOLUTION - Uses placehold.co (more reliable than via.placeholder)
"""

import sqlite3

DB_PATH = "database.db"

def create_product_specific_placeholders():
    """
    Creates unique placeholders with actual product names
    Uses placehold.co - more reliable than via.placeholder
    """
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    
    print("="*70)
    print("🏷️  CREATING PRODUCT-SPECIFIC PLACEHOLDERS")
    print("="*70)
    
    # Get products needing images
    products = cursor.execute("""
        SELECT inventory_id, hem_name, category 
        FROM inventory
    """).fetchall()
    
    total = len(products)
    print(f"\n📊 Processing {total} products...")
    
    updated = 0
    
    for product in products:
        # Create short name for placeholder
        short_name = product['hem_name'][:25].replace(' ', '+')
        
        # Use placehold.co instead (more reliable)
        placeholder_url = f"https://placehold.co/300x200/2563eb/white?text={short_name}"
        
        cursor.execute(
            "UPDATE inventory SET image_url = ? WHERE inventory_id = ?",
            (placeholder_url, product['inventory_id'])
        )
        
        updated += 1
        
        if updated % 1000 == 0:
            print(f"  Progress: {updated}/{total}...")
            conn.commit()
    
    conn.commit()
    conn.close()
    
    print(f"\n✅ DONE! Updated {updated} products")
    print("🎨 Using placehold.co service (more reliable)")

if __name__ == "__main__":
    create_product_specific_placeholders()
    print("\n🌐 Refresh your website to see images!")
"""
SIMPLE IMAGE SOLUTION - NO API NEEDED
Just uses pre-made placeholder images based on categories
"""

import sqlite3

DB_PATH = "database.db"

def create_smart_placeholders():
    """
    Creates unique, color-coded placeholder URLs for each category
    100% FREE, works instantly, looks professional
    """
    
    # Color schemes for each automotive category
    CATEGORY_COLORS = {
        'Engine Parts': '1e3a8a/ffffff',  # Dark blue
        'Brake System': 'dc2626/ffffff',  # Red
        'Suspension': 'ea580c/ffffff',    # Orange
        'Electrical': 'eab308/000000',    # Yellow
        'Filters': '16a34a/ffffff',       # Green
        'Lubricants': '0891b2/ffffff',    # Cyan
        'Body Parts': '7c3aed/ffffff',    # Purple
        'Transmission': 'db2777/ffffff',  # Pink
        'Cooling System': '06b6d4/000000', # Light blue
        'Exhaust': '78716c/ffffff',       # Gray
        'Fuel System': 'f59e0b/000000',   # Amber
        'Steering': '8b5cf6/ffffff',      # Violet
        'Wheels & Tires': '0f172a/ffffff', # Slate
        'Lighting': 'fbbf24/000000',      # Light yellow
        'Interior': '92400e/ffffff',      # Brown
        'Accessories': 'ec4899/ffffff',   # Hot pink
    }
    
    DEFAULT_COLOR = '6b7280/ffffff'  # Gray for unknown categories
    
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    
    # Get all unique categories first
    categories = cursor.execute("SELECT DISTINCT category FROM inventory WHERE category IS NOT NULL").fetchall()
    
    print("Found categories:")
    for cat in categories:
        print(f"  - {cat['category']}")
    
    print("\n" + "="*70)
    print("🎨 CREATING SMART PLACEHOLDERS FOR ALL PRODUCTS")
    print("="*70)
    
    total_updated = 0
    
    # Update each category
    for category_row in categories:
        category = category_row['category']
        
        # Get color for this category
        color = CATEGORY_COLORS.get(category, DEFAULT_COLOR)
        
        # Create placeholder URL with category name
        placeholder_url = f"https://via.placeholder.com/300x200/{color}?text={category.replace(' ', '+')}"
        
        # Update all products in this category
        cursor.execute("""
            UPDATE inventory 
            SET image_url = ? 
            WHERE category = ? AND (image_url IS NULL OR image_url LIKE '/static/defaults/%')
        """, (placeholder_url, category))
        
        updated = cursor.rowcount
        total_updated += updated
        
        print(f"✅ {category}: {updated} products updated")
    
    conn.commit()
    conn.close()
    
    print("\n" + "="*70)
    print(f"✅ DONE! Updated {total_updated} products")
    print("="*70)
    print("\n💡 Each category now has its own color-coded placeholder!")
    print("🌐 Refresh your website to see the changes!")

def create_product_specific_placeholders():
    """
    Creates unique placeholders with actual product names
    Makes each product visually distinct
    """
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    
    print("="*70)
    print("🏷️  CREATING PRODUCT-SPECIFIC PLACEHOLDERS")
    print("="*70)
    
    # Get products needing images
    products = cursor.execute("""
        SELECT inventory_id, hem_name, category 
        FROM inventory 
        WHERE image_url IS NULL OR image_url LIKE '/static/defaults/%'
    """).fetchall()
    
    total = len(products)
    print(f"\n📊 Processing {total} products...")
    
    updated = 0
    
    for product in products:
        # Create short name for placeholder
        short_name = product['hem_name'][:20].replace(' ', '+')
        
        # Choose color based on first letter of product name
        color_map = {
            'A': 'ef4444', 'B': 'f97316', 'C': 'f59e0b', 'D': 'eab308',
            'E': '84cc16', 'F': '22c55e', 'G': '10b981', 'H': '14b8a6',
            'I': '06b6d4', 'J': '0ea5e9', 'K': '3b82f6', 'L': '6366f1',
            'M': '8b5cf6', 'N': 'a855f7', 'O': 'c026d3', 'P': 'd946ef',
            'Q': 'ec4899', 'R': 'f43f5e', 'S': 'dc2626', 'T': 'ea580c',
            'U': 'f97316', 'V': 'fb923c', 'W': 'fbbf24', 'X': 'facc15',
            'Y': 'a3e635', 'Z': '4ade80'
        }
        
        first_letter = product['hem_name'][0].upper()
        color = color_map.get(first_letter, '6b7280')
        
        placeholder_url = f"https://via.placeholder.com/300x200/{color}/ffffff?text={short_name}"
        
        cursor.execute(
            "UPDATE inventory SET image_url = ? WHERE inventory_id = ?",
            (placeholder_url, product['inventory_id'])
        )
        
        updated += 1
        
        if updated % 1000 == 0:
            print(f"  Progress: {updated}/{total}...")
            conn.commit()
    
    conn.commit()
    conn.close()
    
    print(f"\n✅ DONE! Updated {updated} products")
    print("🎨 Each product now has a unique colored placeholder!")

def use_category_default_images():
    """
    Simple approach: Use one generic image per category
    Upload 10-15 category images and you're done!
    """
    print("="*70)
    print("📁 CATEGORY DEFAULT IMAGE SETUP")
    print("="*70)
    print("\n📝 Instructions:")
    print("1. Create folder: static/defaults/")
    print("2. Download/save these images:")
    print("   - engine.jpg")
    print("   - brakes.jpg")
    print("   - suspension.jpg")
    print("   - filters.jpg")
    print("   - lubricants.jpg")
    print("   etc.")
    print("\n3. Run this script again and choose this option")
    
    choice = input("\nHave you added the images? (y/n): ").strip().lower()
    
    if choice != 'y':
        print("\n👉 Add images first, then run again!")
        return
    
    CATEGORY_IMAGES = {
        'Engine Parts': '/static/defaults/engine.jpg',
        'Brake System': '/static/defaults/brakes.jpg',
        'Suspension': '/static/defaults/suspension.jpg',
        'Filters': '/static/defaults/filters.jpg',
        'Lubricants': '/static/defaults/lubricants.jpg',
        'Electrical': '/static/defaults/electrical.jpg',
        'Body Parts': '/static/defaults/body.jpg',
        'Transmission': '/static/defaults/transmission.jpg',
    }
    
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    total_updated = 0
    
    for category, image_path in CATEGORY_IMAGES.items():
        cursor.execute("""
            UPDATE inventory 
            SET image_url = ? 
            WHERE category = ? AND (image_url IS NULL OR image_url LIKE '/static/defaults/%')
        """, (image_path, category))
        
        updated = cursor.rowcount
        total_updated += updated
        print(f"✅ {category}: {updated} products")
    
    conn.commit()
    conn.close()
    
    print(f"\n✅ Total updated: {total_updated}")

if __name__ == "__main__":
    print("\n🎯 CHOOSE YOUR SOLUTION (NO API NEEDED!):\n")
    print("1. 🎨 Smart Category Placeholders (RECOMMENDED)")
    print("   - Different color for each category")
    print("   - Works instantly")
    print("   - Looks professional")
    print("   - 100% FREE")
    print()
    print("2. 🏷️  Product-Specific Placeholders")
    print("   - Unique color + name for each product")
    print("   - Takes 1-2 minutes to process all")
    print("   - Most visually distinct")
    print()
    print("3. 📁 Category Default Images")
    print("   - Use real images (you provide 10-15 images)")
    print("   - Best quality")
    print("   - Requires manual image download")
    print()
    
    choice = input("Enter choice (1, 2, or 3): ").strip()
    
    if choice == "1":
        create_smart_placeholders()
    elif choice == "2":
        create_product_specific_placeholders()
    elif choice == "3":
        use_category_default_images()
    else:
        print("❌ Invalid choice")
    
    print("\n🌐 Refresh your website to see images!")