# check_images.py - Create and run this
import sqlite3

conn = sqlite3.connect('database.db')
cursor = conn.cursor()

# Check if image_url column exists
cursor.execute("PRAGMA table_info(inventory)")
columns = cursor.fetchall()
print("Columns in inventory table:")
for col in columns:
    print(f"  - {col[1]}")

print("\n" + "="*50)

# Check first 5 products
cursor.execute("SELECT inventory_id, hem_name, image_url FROM inventory LIMIT 5")
products = cursor.fetchall()

print("\nFirst 5 products:")
for p in products:
    print(f"ID: {p[0]}")
    print(f"Name: {p[1]}")
    print(f"Image URL: {p[2]}")
    print("-" * 30)

conn.close()