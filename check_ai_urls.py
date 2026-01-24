# check_ai_urls.py
import sqlite3

conn = sqlite3.connect('database.db')
cursor = conn.cursor()

cursor.execute("SELECT inventory_id, hem_name, image_url FROM inventory LIMIT 5")
products = cursor.fetchall()

print("First 5 products:")
for p in products:
    print(f"ID: {p[0]}")
    print(f"Name: {p[1]}")
    print(f"Image URL: {p[2][:100]}...")
    print("-" * 50)

conn.close()