import sqlite3
import os
from werkzeug.security import generate_password_hash

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(BASE_DIR, "database.db")

conn = sqlite3.connect(DB_PATH)
cursor = conn.cursor()

# =========================
# 1. USERS (RBAC / AUTH)
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

# Default SUPEROWNER
cursor.execute("SELECT 1 FROM users WHERE role='superowner' LIMIT 1")
if not cursor.fetchone():
    cursor.execute("""
        INSERT INTO users (username, password_hash, role, active)
        VALUES (?, ?, 'superowner', 1)
    """, ("superowner", generate_password_hash("changeme123")))

# =========================
# 2. LEGENDS, CUSTOMERS, SUPPLIERS
# =========================
cursor.execute("CREATE TABLE IF NOT EXISTS legends (legend_id TEXT PRIMARY KEY, legend_name TEXT NOT NULL);")
cursor.execute("CREATE TABLE IF NOT EXISTS customers (customer_id INTEGER PRIMARY KEY, customer_code TEXT NOT NULL);")
cursor.execute("CREATE TABLE IF NOT EXISTS suppliers (supplier_id INTEGER PRIMARY KEY, supp_name TEXT NOT NULL);")

# =========================
# 3. PRODUCTS (Master List)
# =========================
cursor.execute("""
CREATE TABLE IF NOT EXISTS products (
    product_id INTEGER PRIMARY KEY AUTOINCREMENT,
    sku_no TEXT UNIQUE NOT NULL,
    hem_name TEXT NOT NULL
);
""")

# =========================
# 4. INVENTORY (This is what pulls into your Cart)
# =========================
cursor.execute("""
CREATE TABLE IF NOT EXISTS inventory (
    inventory_id INTEGER PRIMARY KEY AUTOINCREMENT,
    sup_part_no TEXT DEFAULT '',
    hem_name TEXT NOT NULL,
    category TEXT DEFAULT 'Lubricants', 
    org TEXT,
    loc_on_shelf TEXT,
    qty INTEGER NOT NULL DEFAULT 0,
    sell_price REAL NOT NULL DEFAULT 0,
    image_url TEXT DEFAULT ''
);
""")

# =========================
# 5. TRANSACTIONS (Order Headers)
# =========================
cursor.execute("""
CREATE TABLE IF NOT EXISTS transactions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    username TEXT,
    payment_type TEXT,
    amount REAL,
    status TEXT DEFAULT 'Incoming',
    fulfillment_method TEXT DEFAULT 'pickup',
    fulfillment_details TEXT,
    timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
);
""")

# Add new columns to existing transactions table if they don't exist
try:
    cursor.execute("ALTER TABLE transactions ADD COLUMN fulfillment_method TEXT DEFAULT 'pickup'")
except sqlite3.OperationalError:
    pass  # Column already exists

try:
    cursor.execute("ALTER TABLE transactions ADD COLUMN fulfillment_details TEXT")
except sqlite3.OperationalError:
    pass  # Column already exists

# =========================
# 6. ORDER ITEMS (Products in each order)
# =========================
cursor.execute("""
CREATE TABLE IF NOT EXISTS order_items (
    item_id INTEGER PRIMARY KEY AUTOINCREMENT,
    order_id INTEGER NOT NULL,
    inventory_id INTEGER NOT NULL,
    product_name TEXT NOT NULL,
    product_sku TEXT,
    quantity INTEGER NOT NULL,
    unit_price REAL NOT NULL,
    image_url TEXT,
    FOREIGN KEY (order_id) REFERENCES transactions(id) ON DELETE CASCADE,
    FOREIGN KEY (inventory_id) REFERENCES inventory(inventory_id)
);
""")

# =========================
# 7. SALES & PURCHASE (The Enterprise Tables)
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
    FOREIGN KEY (invoice_no) REFERENCES sales_invoice_header(invoice_no)
);
""")

cursor.execute("""
CREATE TABLE IF NOT EXISTS purchase_header (
    purchase_ref_no TEXT PRIMARY KEY,
    purchase_date TEXT NOT NULL,
    total_purchase REAL NOT NULL,
    gst_amt REAL NOT NULL,
    supplier_id INTEGER NOT NULL,
    legend_id TEXT,
    FOREIGN KEY (supplier_id) REFERENCES suppliers(supplier_id)
);
""")

cursor.execute("""
CREATE TABLE IF NOT EXISTS purchase_line (
    purchase_ref_no TEXT NOT NULL,
    line_no INTEGER NOT NULL,
    product_id INTEGER NOT NULL,
    qty INTEGER NOT NULL,
    PRIMARY KEY (purchase_ref_no, line_no),
    FOREIGN KEY (purchase_ref_no) REFERENCES purchase_header(purchase_ref_no)
);
""")

# Create indexes for performance
cursor.execute("CREATE INDEX IF NOT EXISTS idx_order_items_order ON order_items(order_id)")
cursor.execute("CREATE INDEX IF NOT EXISTS idx_transactions_status ON transactions(status)")
cursor.execute("CREATE INDEX IF NOT EXISTS idx_sih_date ON sales_invoice_header(invoice_date)")
cursor.execute("CREATE INDEX IF NOT EXISTS idx_sih_cust ON sales_invoice_header(customer_id)")
cursor.execute("CREATE INDEX IF NOT EXISTS idx_sil_inv ON sales_invoice_line(invoice_no)")
cursor.execute("CREATE INDEX IF NOT EXISTS idx_sil_prod ON sales_invoice_line(product_id)")
cursor.execute("CREATE INDEX IF NOT EXISTS idx_prod_name ON products(hem_name)")
cursor.execute("CREATE INDEX IF NOT EXISTS idx_cust_code ON customers(customer_code)")

conn.commit()
conn.close()

print("✅ database.db updated with ORDER_ITEMS table + fulfillment fields!")
print("   - Added order_items table to store products")
print("   - Added fulfillment_method and fulfillment_details to transactions")
print("   - Added indexes for better performance")