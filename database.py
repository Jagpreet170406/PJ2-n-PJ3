import sqlite3
import os
from werkzeug.security import generate_password_hash

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(BASE_DIR, "database.db")

def setup_database():
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    # 1. USERS
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS users (
        user_id INTEGER PRIMARY KEY AUTOINCREMENT,
        username TEXT UNIQUE NOT NULL,
        password_hash TEXT NOT NULL,
        role TEXT NOT NULL CHECK (role IN ('employee','admin','superowner')),
        active INTEGER DEFAULT 1
    );
    """)

    # Default SUPEROWNER
    cursor.execute("SELECT 1 FROM users WHERE role='superowner' LIMIT 1")
    if not cursor.fetchone():
        cursor.execute("""
            INSERT INTO users (username, password_hash, role, active)
            VALUES (?, ?, 'superowner', 1)
        """, ("superowner", generate_password_hash("changeme123")))

    # 2. BUSINESS TABLES (Legends, Products, etc.)
    cursor.execute("CREATE TABLE IF NOT EXISTS legends (legend_id TEXT PRIMARY KEY, legend_name TEXT NOT NULL);")
    cursor.execute("CREATE TABLE IF NOT EXISTS products (product_id INTEGER PRIMARY KEY AUTOINCREMENT, sku_no TEXT UNIQUE NOT NULL, hem_name TEXT NOT NULL);")
    cursor.execute("CREATE TABLE IF NOT EXISTS customers (customer_id INTEGER PRIMARY KEY, customer_code TEXT NOT NULL);")
    cursor.execute("CREATE TABLE IF NOT EXISTS suppliers (supplier_id INTEGER PRIMARY KEY, supp_name TEXT NOT NULL);")
    
    # 3. SALES & PURCHASE
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS sales_invoice_header (
        invoice_no TEXT PRIMARY KEY, invoice_date TEXT NOT NULL, customer_id INTEGER NOT NULL, legend_id TEXT,
        FOREIGN KEY (customer_id) REFERENCES customers(customer_id)
    );""")
    
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS inventory (
        inventory_id INTEGER PRIMARY KEY AUTOINCREMENT,
        sup_part_no TEXT NOT NULL, hem_name TEXT NOT NULL, org TEXT,
        loc_on_shelf TEXT, qty INTEGER NOT NULL, sell_price REAL NOT NULL
    );""")

    conn.commit()
    conn.close()
    print("✅ database.db created successfully!")

if __name__ == "__main__":
    setup_database()