import sqlite3

conn = sqlite3.connect("database.db")
cursor = conn.cursor()

# SALES TABLE
cursor.execute("""
CREATE TABLE IF NOT EXISTS sales (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    invoice_no TEXT,
    sale_date TEXT,
    product_code TEXT,
    brand TEXT,
    quantity INTEGER,
    unit_price REAL,
    total_amount REAL
)
""")

# INVENTORY TABLE
cursor.execute("""
CREATE TABLE IF NOT EXISTS inventory (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    company TEXT,
    product_code TEXT,
    product_name TEXT,
    stock_qty INTEGER,
    snapshot_date TEXT
)
""")

# PURCHASE TABLE
cursor.execute("""
CREATE TABLE IF NOT EXISTS purchase (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    supplier TEXT,
    purchase_date TEXT,
    product_code TEXT,
    brand TEXT,
    quantity INTEGER,
    unit_price REAL,
    total_amount REAL
)
""")

conn.commit()
conn.close()
print("Tables created successfully")


