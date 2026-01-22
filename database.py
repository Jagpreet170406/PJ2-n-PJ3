import sqlite3

# Connect (or create) the database
conn = sqlite3.connect("database.db")
cursor = conn.cursor()

# -------------------------------
# 1️⃣ SPI_LEGEND
# -------------------------------
cursor.execute("""
CREATE TABLE IF NOT EXISTS legends (
    legend_id INTEGER PRIMARY KEY,
    legend_name TEXT NOT NULL
)
""")

# -------------------------------
# 2️⃣ PRODUCTS (shared by sales & purchase)
# -------------------------------
cursor.execute("""
CREATE TABLE IF NOT EXISTS products (
    product_id INTEGER PRIMARY KEY,
    sku_no TEXT NOT NULL,
    hem_name TEXT NOT NULL
)
""")

# -------------------------------
# 3️⃣ CUSTOMERS
# -------------------------------
cursor.execute("""
CREATE TABLE IF NOT EXISTS customers (
    customer_id INTEGER PRIMARY KEY,
    customer_code TEXT NOT NULL
)
""")

# -------------------------------
# 4️⃣ SALES
# -------------------------------
cursor.execute("""
CREATE TABLE IF NOT EXISTS sales_invoice_header (
    invoice_no TEXT PRIMARY KEY,
    invoice_date TEXT,
    customer_id INTEGER,
    legend_id INTEGER,
    FOREIGN KEY(customer_id) REFERENCES customers(customer_id),
    FOREIGN KEY(legend_id) REFERENCES legends(legend_id)
)
""")

cursor.execute("""
CREATE TABLE IF NOT EXISTS sales_invoice_line (
    invoice_no TEXT,
    line_no INTEGER,
    product_id INTEGER,
    qty INTEGER,
    total_amt REAL,
    gst_amt REAL,
    PRIMARY KEY(invoice_no, line_no),
    FOREIGN KEY(invoice_no) REFERENCES sales_invoice_header(invoice_no),
    FOREIGN KEY(product_id) REFERENCES products(product_id)
)
""")

# -------------------------------
# 5️⃣ SUPPLIERS
# -------------------------------
cursor.execute("""
CREATE TABLE IF NOT EXISTS suppliers (
    supp_id INTEGER PRIMARY KEY,
    supp_name TEXT NOT NULL,
    legend_id INTEGER,
    FOREIGN KEY(legend_id) REFERENCES legends(legend_id)
)
""")

# -------------------------------
# 6️⃣ PURCHASE
# -------------------------------
cursor.execute("""
CREATE TABLE IF NOT EXISTS purchase_header (
    purchase_ref_no TEXT PRIMARY KEY,
    purchase_date TEXT,
    total_purchase REAL,
    gst_amt REAL,
    supp_id INTEGER,
    legend_id INTEGER,
    FOREIGN KEY(supp_id) REFERENCES suppliers(supp_id),
    FOREIGN KEY(legend_id) REFERENCES legends(legend_id)
)
""")

cursor.execute("""
CREATE TABLE IF NOT EXISTS purchase_line (
    purchase_ref_no TEXT,
    product_id INTEGER,
    qty INTEGER,
    PRIMARY KEY(purchase_ref_no, product_id),
    FOREIGN KEY(purchase_ref_no) REFERENCES purchase_header(purchase_ref_no),
    FOREIGN KEY(product_id) REFERENCES products(product_id)
)
""")

# -------------------------------
# 7️⃣ INVENTORY
# -------------------------------
cursor.execute("""
CREATE TABLE IF NOT EXISTS inventory (
    sup_part_no TEXT PRIMARY KEY,
    product_id INTEGER,
    org TEXT,
    loc_on_shelf TEXT,
    qty INTEGER,
    sell_price REAL,
    FOREIGN KEY(product_id) REFERENCES products(product_id)
)
""")

# Commit changes and close
conn.commit()
conn.close()

print("Database created successfully with all tables!")




