"""
Image Matcher - Dynamically match products to images without storing in database
Fast lookup using in-memory dictionary built on startup
"""
import os
import re
from flask import send_from_directory, current_app

# Global cache for image mappings (built once on startup)
IMAGE_CACHE = {}

def build_image_cache(images_folder='product_images_v2'):
    """Build in-memory cache of image filenames mapped to search keywords"""
    global IMAGE_CACHE
    IMAGE_CACHE.clear()
    
    base_dir = os.path.join(current_app.root_path, images_folder)
    
    if not os.path.exists(base_dir):
        print(f"⚠️  Warning: Images folder not found: {base_dir}")
        return
    
    for filename in os.listdir(base_dir):
        if not filename.lower().endswith(('.jpg', '.jpeg', '.png')):
            continue
            
        # Extract description from filename (after first underscore)
        match = re.match(r'^[^_]+_(.+)\.(jpg|jpeg|png)$', filename, re.IGNORECASE)
        if match:
            desc = match.group(1).upper()
            # Normalize: remove special chars, extra spaces
            desc_clean = re.sub(r'[^A-Z0-9\s]', ' ', desc)
            desc_clean = ' '.join(desc_clean.split())
            
            # Create multiple search keys
            words = desc_clean.split()
            
            # Store by full description
            IMAGE_CACHE[desc_clean] = filename
            
            # Store by individual words (for partial matching)
            for word in words:
                if len(word) >= 3:  # Only meaningful words
                    if word not in IMAGE_CACHE:
                        IMAGE_CACHE[word] = []
                    if filename not in IMAGE_CACHE[word]:
                        if isinstance(IMAGE_CACHE[word], list):
                            IMAGE_CACHE[word].append(filename)
    
    print(f"✅ Image cache built: {len(IMAGE_CACHE)} entries")


def find_product_image(product_name, sku=None):
    """
    Find matching image for a product
    Returns: filename or None
    """
    if not IMAGE_CACHE:
        return None
    
    # Normalize product name
    search_term = product_name.upper().strip()
    search_term = re.sub(r'[^A-Z0-9\s]', ' ', search_term)
    search_term = ' '.join(search_term.split())
    
    # Try exact match first
    if search_term in IMAGE_CACHE and isinstance(IMAGE_CACHE[search_term], str):
        return IMAGE_CACHE[search_term]
    
    # Try keyword matching - score based on word matches
    words = search_term.split()
    candidates = {}
    
    for word in words:
        if len(word) >= 3 and word in IMAGE_CACHE:
            files = IMAGE_CACHE[word]
            if isinstance(files, list):
                for img_file in files:
                    candidates[img_file] = candidates.get(img_file, 0) + 1
    
    # Return image with most matching keywords
    if candidates:
        best_match = max(candidates, key=candidates.get)
        # Only return if at least 2 keywords match
        if candidates[best_match] >= 2:
            return best_match
    
    return None


def get_product_image_url(product_name, sku=None):
    """
    Get image URL for a product (for use in templates)
    Returns: URL path or placeholder path
    """
    filename = find_product_image(product_name, sku)
    if filename:
        return f'/product-image/{filename}'
    return '/static/placeholder.png'