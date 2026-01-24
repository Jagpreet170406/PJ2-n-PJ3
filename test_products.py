# test_products.py
import sqlite3

conn = sqlite3.connect('database.db')
conn.row_factory = sqlite3.Row
cursor = conn.cursor()

# Check what your /cart route is actually fetching
products = cursor.execute("SELECT * FROM inventory WHERE qty > 0 LIMIT 3").fetchall()

print(f"Found {len(products)} products")
for p in products:
    print(f"\nProduct: {p['hem_name']}")
    print(f"Image URL: {p['image_url']}")
    print(f"Price: {p['sell_price']}")

conn.close()
