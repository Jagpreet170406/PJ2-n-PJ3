"""
AI IMAGE GENERATOR - FREE Auto Part Images
Uses multiple FREE AI services
"""

import sqlite3
import requests
import time
import os
import base64

DB_PATH = "database.db"
IMAGE_FOLDER = "static/product_images"

if not os.path.exists(IMAGE_FOLDER):
    os.makedirs(IMAGE_FOLDER)

# ============================================
# OPTION 1: Pollinations.AI (UNLIMITED FREE!)
# ============================================
def generate_with_pollinations():
    """
    Pollinations.AI - UNLIMITED FREE AI images!
    No API key needed
    Best option!
    """
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    
    # Get products needing images
    products = cursor.execute("""
        SELECT inventory_id, hem_name, category 
        FROM inventory 
        WHERE image_url LIKE 'data:image%' OR image_url LIKE 'https://placehold%'
        LIMIT 100
    """).fetchall()
    
    total = len(products)
    
    print("="*70)
    print("🎨 GENERATING AI IMAGES WITH POLLINATIONS.AI")
    print(f"📊 Processing {total} products")
    print("⚡ UNLIMITED & FREE - No API key needed!")
    print("="*70)
    
    successful = 0
    
    for i, product in enumerate(products, 1):
        print(f"\n[{i}/{total}] {product['hem_name'][:50]}")
        
        # Create AI prompt
        prompt = f"professional product photo of {product['hem_name']} automotive {product['category']}, white background, high quality, detailed"
        
        # Pollinations.AI URL - auto-generates image
        image_url = f"https://image.pollinations.ai/prompt/{requests.utils.quote(prompt)}?width=400&height=300&nologo=true&enhance=true"
        
        try:
            # Download the generated image
            response = requests.get(image_url, timeout=15)
            
            if response.ok:
                # Save locally
                filename = f"{product['inventory_id']}.jpg"
                filepath = os.path.join(IMAGE_FOLDER, filename)
                
                with open(filepath, 'wb') as f:
                    f.write(response.content)
                
                local_path = f"/static/product_images/{filename}"
                cursor.execute(
                    "UPDATE inventory SET image_url = ? WHERE inventory_id = ?",
                    (local_path, product['inventory_id'])
                )
                conn.commit()
                
                successful += 1
                print(f"  ✅ Generated AI image: {filename}")
            else:
                print(f"  ❌ Generation failed")
                
        except Exception as e:
            print(f"  ❌ Error: {e}")
        
        # Save progress every 10
        if i % 10 == 0:
            conn.commit()
            print(f"\n💾 Progress saved: {successful}/{i}")
        
        # Delay to be nice to the API
        time.sleep(2)
    
    conn.commit()
    conn.close()
    
    print("\n" + "="*70)
    print(f"✅ Generated {successful}/{total} AI images!")
    print("="*70)


# ============================================
# OPTION 2: Hugging Face (FREE with API key)
# ============================================
def generate_with_huggingface():
    """
    Hugging Face Stable Diffusion
    FREE API key: https://huggingface.co/settings/tokens
    """
    API_KEY = input("\nEnter Hugging Face API token (or press Enter to skip): ").strip()
    
    if not API_KEY:
        print("Skipping Hugging Face...")
        return
    
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    
    products = cursor.execute("""
        SELECT inventory_id, hem_name, category 
        FROM inventory 
        WHERE image_url LIKE 'data:image%' OR image_url LIKE 'https://placehold%'
        LIMIT 50
    """).fetchall()
    
    print(f"\n🎨 Generating {len(products)} AI images with Stable Diffusion...")
    
    successful = 0
    
    for i, product in enumerate(products, 1):
        prompt = f"professional product photograph of {product['hem_name']} car part, automotive component, white background, studio lighting, high detail"
        
        print(f"[{i}/{len(products)}] Generating: {product['hem_name'][:40]}")
        
        try:
            headers = {"Authorization": f"Bearer {API_KEY}"}
            
            response = requests.post(
                "https://api-inference.huggingface.co/models/stabilityai/stable-diffusion-2-1",
                headers=headers,
                json={"inputs": prompt},
                timeout=30
            )
            
            if response.ok:
                filename = f"{product['inventory_id']}.jpg"
                filepath = os.path.join(IMAGE_FOLDER, filename)
                
                with open(filepath, 'wb') as f:
                    f.write(response.content)
                
                local_path = f"/static/product_images/{filename}"
                cursor.execute(
                    "UPDATE inventory SET image_url = ? WHERE inventory_id = ?",
                    (local_path, product['inventory_id'])
                )
                
                successful += 1
                print(f"  ✅ Generated")
            else:
                print(f"  ❌ Failed: {response.status_code}")
            
            time.sleep(3)
            
        except Exception as e:
            print(f"  ❌ Error: {e}")
    
    conn.commit()
    conn.close()
    
    print(f"\n✅ Generated {successful} images")


# ============================================
# OPTION 3: Just use DALL-E style URLs
# ============================================
def use_dalle_style_urls():
    """
    Uses a service that mimics DALL-E style images
    Completely free, no API needed
    """
    from urllib.parse import quote
    
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    products = cursor.execute("""
        SELECT inventory_id, hem_name, category 
        FROM inventory
    """).fetchall()
    
    total = len(products)
    print(f"🎨 Creating AI-style image URLs for {total} products...")
    
    updated = 0
    for product in products:
        inventory_id, hem_name, category = product
        
        # Create AI image prompt
        prompt = f"professional product photo {hem_name} automotive {category} part white background"
        
        # Pollinations.AI URL - generates AI image on-the-fly
        image_url = f"https://image.pollinations.ai/prompt/{quote(prompt)}?width=400&height=300&nologo=true&enhance=true"
        
        cursor.execute(
            "UPDATE inventory SET image_url = ? WHERE inventory_id = ?",
            (image_url, inventory_id)
        )
        
        updated += 1
        
        if updated % 5000 == 0:
            print(f"  Progress: {updated}/{total}...")
            conn.commit()
    
    conn.commit()
    conn.close()
    
    print(f"✅ Updated all {total} products with AI-generated image URLs!")
    print("🌐 Images will generate dynamically when you view your cart!")


# ============================================
# MAIN MENU
# ============================================
if __name__ == "__main__":
    print("\n" + "="*70)
    print("🎨 AI IMAGE GENERATOR FOR AUTO PARTS")
    print("="*70)
    print("\nChoose AI service:\n")
    
    print("1. 🚀 Pollinations.AI (RECOMMENDED)")
    print("   - UNLIMITED & FREE")
    print("   - No API key needed")
    print("   - Downloads actual images")
    print("   - High quality")
    print()
    
    print("2. 🤗 Hugging Face Stable Diffusion")
    print("   - FREE (need account)")
    print("   - Very high quality")
    print("   - Slower")
    print()
    
    print("3. ⚡ AI-Style URLs (Instant)")
    print("   - Updates all 25,119 products instantly")
    print("   - Uses AI image service URLs")
    print("   - No downloading")
    print()
    
    choice = input("Enter choice (1, 2, or 3): ").strip()
    
    if choice == "1":
        print("\n💡 This will process 100 products at a time")
        print("   Run multiple times to complete all products")
        print("   Takes ~5 minutes per 100 products\n")
        
        confirm = input("Start generating? (y/n): ").lower()
        if confirm == 'y':
            generate_with_pollinations()
    
    elif choice == "2":
        print("\n💡 Get FREE API token: https://huggingface.co/settings/tokens")
        generate_with_huggingface()
    
    elif choice == "3":
        print("\n⚡ This updates ALL products instantly with AI image URLs")
        confirm = input("Continue? (y/n): ").lower()
        if confirm == 'y':
            use_dalle_style_urls()
    
    else:
        print("❌ Invalid choice")
    
    print("\n🌐 Refresh your website to see AI-generated images!")