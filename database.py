import sqlite3

conn = sqlite3.connect("database.db")
cursor = conn.cursor()

# -------------------------------
# LEGENDS
# -------------------------------
cursor.execute("""
CREATE TABLE IF NOT EXISTS legends (
    legend_id TEXT PRIMARY KEY,
    legend_name TEXT NOT NULL
)
""")

# -------------------------------
# SALES TABLES
# -------------------------------
cursor.execute("""
CREATE TABLE IF NOT EXISTS products (
    sku_no TEXT PRIMARY KEY,
    hem_name TEXT
)
""")

cursor.execute("""
CREATE TABLE IF NOT EXISTS customers (
    id INTEGER PRIMARY KEY,
    customer_code TEXT
)
""")

cursor.execute("""
CREATE TABLE IF NOT EXISTS sales_invoice_header (
    invoice_no TEXT PRIMARY KEY,
    invoice_date TEXT,
    customer_id INTEGER,
    legend_id TEXT,
    FOREIGN KEY(customer_id) REFERENCES customers(id),
    FOREIGN KEY(legend_id) REFERENCES legends(legend_id)
)
""")

cursor.execute("""
CREATE TABLE IF NOT EXISTS sales_invoice_line (
    invoice_no TEXT,
    line_no INTEGER,
    sku_no TEXT,
    qty INTEGER,
    total_amt REAL,
    gst_amt REAL,
    FOREIGN KEY(invoice_no) REFERENCES sales_invoice_header(invoice_no),
    FOREIGN KEY(sku_no) REFERENCES products(sku_no)
)
""")

# -------------------------------
# PURCHASE TABLES
# -------------------------------
cursor.execute("""
CREATE TABLE IF NOT EXISTS suppliers (
    supp_id TEXT PRIMARY KEY,
    supp_name TEXT
)
""")

cursor.execute("""
CREATE TABLE IF NOT EXISTS purchase_header (
    purchase_ref_no TEXT PRIMARY KEY,
    purchase_date TEXT,
    total_purchase REAL,
    gst_amt REAL,
    supplier_id TEXT,
    legend_id TEXT,
    FOREIGN KEY(supplier_id) REFERENCES suppliers(supp_id),
    FOREIGN KEY(legend_id) REFERENCES legends(legend_id)
)
""")

cursor.execute("""
CREATE TABLE IF NOT EXISTS purchase_line (
    purchase_ref_no TEXT,
    qty INTEGER,
    product_id TEXT,
    FOREIGN KEY(purchase_ref_no) REFERENCES purchase_header(purchase_ref_no)
)
""")

# -------------------------------
# INVENTORY TABLE
# -------------------------------
cursor.execute("""
CREATE TABLE IF NOT EXISTS inventory (
    sup_part_no TEXT,
    hem_name TEXT,
    org TEXT,
    loc_on_shelf TEXT,
    qty INTEGER,
    sell_price REAL
)
""")

conn.commit()
conn.close()
print("✅ Database and tables created successfully")





