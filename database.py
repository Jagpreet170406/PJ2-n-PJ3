import sqlite3
import os
from werkzeug.security import generate_password_hash

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(BASE_DIR, "database.db")

conn = sqlite3.connect(DB_PATH)
cursor = conn.cursor()

# =========================
# USERS (RBAC / AUTH)
# =========================
cursor.execute("""
CREATE TABLE IF NOT EXISTS users (
    user_id INTEGER PRIMARY KEY AUTOINCREMENT,
    username TEXT UNIQUE NOT NULL,
    password_hash TEXT NOT NULL,
    role TEXT NOT NULL CHECK (role IN ('employee','admin','superowner')),
    active INTEGER DEFAULT 1
);
""")

# Create default SUPEROWNER if not exists
cursor.execute("SELECT 1 FROM users WHERE role='superowner' LIMIT 1")
if not cursor.fetchone():
    cursor.execute(
        """
        INSERT INTO users (username, password_hash, role, active)
        VALUES (?, ?, 'superowner', 1)
        """,
        ("superowner", generate_password_hash("changeme123")),
    )

# =========================
# LEGENDS
# =========================
cursor.execute("""
CREATE TABLE IF NOT EXISTS legends (
    legend_id TEXT PRIMARY KEY,
    legend_name TEXT NOT NULL
);
""")

# =========================
# PRODUCTS (Shared)
# =========================
cursor.execute("""
CREATE TABLE IF NOT EXISTS products (
    product_id INTEGER PRIMARY KEY AUTOINCREMENT,
    sku_no TEXT UNIQUE NOT NULL,
    hem_name TEXT NOT NULL
);
""")

# =========================
# CUSTOMERS
# =========================
cursor.execute("""
CREATE TABLE IF NOT EXISTS customers (
    customer_id INTEGER PRIMARY KEY,
    customer_code TEXT NOT NULL
);
""")

# =========================
# SUPPLIERS
# =========================
cursor.execute("""
CREATE TABLE IF NOT EXISTS suppliers (
    supplier_id INTEGER PRIMARY KEY,
    supp_name TEXT NOT NULL
);
""")

# =========================
# SALES
# =========================
cursor.execute("""
CREATE TABLE IF NOT EXISTS sales_invoice_header (
    invoice_no TEXT PRIMARY KEY,
    invoice_date TEXT NOT NULL,
    customer_id INTEGER NOT NULL,
    legend_id TEXT,
    FOREIGN KEY (customer_id) REFERENCES customers(customer_id),
    FOREIGN KEY (legend_id) REFERENCES legends(legend_id)
);
""")

cursor.execute("""
CREATE TABLE IF NOT EXISTS sales_invoice_line (
    invoice_no TEXT NOT NULL,
    line_no INTEGER NOT NULL,
    product_id INTEGER NOT NULL,
    qty INTEGER NOT NULL,
    total_amt REAL NOT NULL,
    gst_amt REAL NOT NULL,
    PRIMARY KEY (invoice_no, line_no),
    FOREIGN KEY (invoice_no) REFERENCES sales_invoice_header(invoice_no),
    FOREIGN KEY (product_id) REFERENCES products(product_id)
);
""")

# =========================
# PURCHASE
# =========================
cursor.execute("""
CREATE TABLE IF NOT EXISTS purchase_header (
    purchase_ref_no TEXT PRIMARY KEY,
    purchase_date TEXT NOT NULL,
    total_purchase REAL NOT NULL,
    gst_amt REAL NOT NULL,
    supplier_id INTEGER NOT NULL,
    legend_id TEXT,
    FOREIGN KEY (supplier_id) REFERENCES suppliers(supplier_id),
    FOREIGN KEY (legend_id) REFERENCES legends(legend_id)
);
""")

cursor.execute("""
CREATE TABLE IF NOT EXISTS purchase_line (
    purchase_ref_no TEXT NOT NULL,
    line_no INTEGER NOT NULL,
    product_id INTEGER NOT NULL,
    qty INTEGER NOT NULL,
    PRIMARY KEY (purchase_ref_no, line_no),
    FOREIGN KEY (purchase_ref_no) REFERENCES purchase_header(purchase_ref_no),
    FOREIGN KEY (product_id) REFERENCES products(product_id)
);
""")

# =========================
# INVENTORY
# =========================
cursor.execute("""
CREATE TABLE IF NOT EXISTS inventory (
    inventory_id INTEGER PRIMARY KEY AUTOINCREMENT,
    sup_part_no TEXT NOT NULL,
    hem_name TEXT NOT NULL,
    org TEXT,
    loc_on_shelf TEXT,
    qty INTEGER NOT NULL,
    sell_price REAL NOT NULL
);
""")

conn.commit()
conn.close()

print("✅ database.db created successfully with USERS + BUSINESS schema")









