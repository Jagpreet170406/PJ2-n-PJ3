import sqlite3

conn = sqlite3.connect('database.db')
cursor = conn.cursor()

# Check columns
cursor.execute("PRAGMA table_info(inventory)")
columns = cursor.fetchall()
print("Columns:")
for col in columns:
    print(f"  - {col[1]}")

# Check first 5 products
print("\nFirst 5 products:")
cursor.execute("SELECT inventory_id, hem_name, image_url FROM inventory LIMIT 5")
for p in cursor.fetchall():
    print(f"ID: {p[0]}, Name: {p[1][:30]}, Image: {p[2]}")

conn.close()