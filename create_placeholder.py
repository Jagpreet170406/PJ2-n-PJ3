#!/usr/bin/env python3
"""
Generate a simple placeholder image for products without photos
Run this once to create static/placeholder.png
"""

try:
    from PIL import Image, ImageDraw, ImageFont
    
    # Create 400x400 placeholder with gray background
    img = Image.new('RGB', (400, 400), color='#e5e7eb')
    draw = ImageDraw.Draw(img)
    
    # Draw border
    draw.rectangle([10, 10, 390, 390], outline='#9ca3af', width=3)
    
    # Draw X
    draw.line([100, 100, 300, 300], fill='#d1d5db', width=5)
    draw.line([300, 100, 100, 300], fill='#d1d5db', width=5)
    
    # Add text
    try:
        # Try to use a nice font
        font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 32)
    except:
        # Fall back to default
        font = ImageFont.load_default()
    
    text = "No Image"
    bbox = draw.textbbox((0, 0), text, font=font)
    text_width = bbox[2] - bbox[0]
    draw.text(((400 - text_width) // 2, 340), text, fill='#6b7280', font=font)
    
    # Save
    img.save('static/product_images_v2/placeholder.png')
    print("✅ Created static/product_images_v2/placeholder.png")
    print("   Dimensions: 400x400px")
    print("   Ready to use!")
    
except ImportError:
    print("❌ PIL/Pillow not installed")
    print("Install it: pip install Pillow")
    print("\nAlternatively, use the placeholder.png file provided in outputs/")