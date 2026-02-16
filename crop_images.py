#!/usr/bin/env python3
"""
Auto-crop white borders from all product images
Run this ONCE to fix all 197 images permanently
"""

from PIL import Image, ImageChops
import os
import shutil

def trim_white_borders(image_path, output_path=None, threshold=240):
    """Remove white borders from an image"""
    img = Image.open(image_path)
    
    if img.mode != 'RGB':
        img = img.convert('RGB')
    
    # Create white background
    bg = Image.new('RGB', img.size, (255, 255, 255))
    
    # Get difference
    diff = ImageChops.difference(img, bg)
    diff = ImageChops.add(diff, diff, 2.0, -threshold)
    
    # Get bounding box of non-white area
    bbox = diff.getbbox()
    
    if bbox:
        # Crop to non-white area
        cropped = img.crop(bbox)
        
        if output_path is None:
            output_path = image_path
        
        cropped.save(output_path, quality=95, optimize=True)
        
        return {
            'success': True,
            'original': img.size,
            'cropped': cropped.size,
            'removed': (img.size[0] - cropped.size[0], img.size[1] - cropped.size[1])
        }
    else:
        return {'success': False, 'reason': 'no borders found'}


def process_folder(input_folder):
    """Process all images in folder"""
    
    # Create backup
    backup_folder = input_folder + '_BACKUP'
    if not os.path.exists(backup_folder):
        print(f"📦 Creating backup: {backup_folder}")
        shutil.copytree(input_folder, backup_folder)
        print(f"✅ Backup created!\n")
    else:
        print(f"⚠️  Backup already exists: {backup_folder}\n")
    
    # Get all images
    image_files = [f for f in os.listdir(input_folder) 
                   if f.lower().endswith(('.jpg', '.jpeg', '.png'))]
    
    print(f"🖼️  Found {len(image_files)} images\n")
    
    success = 0
    failed = 0
    
    for i, filename in enumerate(image_files, 1):
        filepath = os.path.join(input_folder, filename)
        
        try:
            result = trim_white_borders(filepath, filepath, threshold=240)
            
            if result['success']:
                success += 1
                removed = result['removed']
                print(f"✅ [{i}/{len(image_files)}] {filename}")
                print(f"   {result['original']} → {result['cropped']} (removed {removed[0]}x{removed[1]}px)")
            else:
                failed += 1
                print(f"⚠️  [{i}/{len(image_files)}] {filename}: {result['reason']}")
                
        except Exception as e:
            failed += 1
            print(f"❌ [{i}/{len(image_files)}] {filename}: {e}")
    
    # Summary
    print(f"\n{'='*60}")
    print(f"✅ SUCCESS: {success} images cropped")
    print(f"❌ FAILED: {failed} images")
    print(f"📦 BACKUP: {backup_folder}")
    print(f"{'='*60}\n")
    print("🎉 DONE! Your images are now cropped!")
    print("   Restart Flask and refresh browser to see clean images!\n")


if __name__ == "__main__":
    import sys
    
    if len(sys.argv) > 1:
        folder = sys.argv[1]
    else:
        folder = 'static/product_images_v2'
    
    if not os.path.exists(folder):
        print(f"❌ Folder not found: {folder}")
        print(f"\nUsage: python crop_images.py [folder_path]")
        print(f"Example: python crop_images.py static/product_images_v2")
        sys.exit(1)
    
    print(f"\n{'='*60}")
    print(f"🔪 AUTO-CROP WHITE BORDERS")
    print(f"{'='*60}\n")
    print(f"📁 Processing folder: {folder}\n")
    
    response = input("This will MODIFY all images (backup will be created). Continue? (yes/no): ")
    
    if response.lower() in ['yes', 'y']:
        process_folder(folder)
    else:
        print("\n❌ Cancelled!")