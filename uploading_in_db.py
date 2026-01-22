import os
import pandas as pd
import sqlite3

# -------------------------------
# CONFIG: folder paths
# -------------------------------
BASE_DIR = os.path.dirname(os.path.abspath(__file__))

FOLDERS = {
    "legends": os.path.join(BASE_DIR, "legends"),
    "sales": os.path.join(BASE_DIR, "sales"),
    "purchase": os.path.join(BASE_DIR, "purchase"),
    "inventory": os.path.join(BASE_DIR, "inventory")
}

DB_PATH = os.path.join(BASE_DIR, "database.db")

# -------------------------------
# HELPER FUNCTION
# -------------------------------
def import_excel_to_db(sheet_path, table_name, conn, engine=None):
    df = pd.read_excel(sheet_path, engine=engine)
    df.to_sql(table_name.lower(), conn, if_exists='append', index=False)
    print(f"{table_name.lower()} imported successfully from {os.path.basename(sheet_path)}")

# -------------------------------
# CONNECT TO DB
# -------------------------------
conn = sqlite3.connect(DB_PATH)

# -------------------------------
# 1️⃣ LEGENDS
# -------------------------------
import_excel_to_db(
    os.path.join(FOLDERS["legends"], "SPI_LEGEND.xlsx"),
    "legends",
    conn
)

# -------------------------------
# 2️⃣ PRODUCTS & CUSTOMERS (Sales)
# -------------------------------
import_excel_to_db(
    os.path.join(FOLDERS["sales"], "SALES_PRODUCT.xlsx"),
    "products",
    conn
)
import_excel_to_db(
    os.path.join(FOLDERS["sales"], "SALES_CUSTOMER.xlsx"),
    "customers",
    conn
)

# -------------------------------
# 3️⃣ SUPPLIERS (Purchase)
# -------------------------------
import_excel_to_db(
    os.path.join(FOLDERS["purchase"], "SUPPLIERS.xlsx"),
    "suppliers",
    conn
)

# -------------------------------
# 4️⃣ Sales tables
# -------------------------------
import_excel_to_db(
    os.path.join(FOLDERS["sales"], "SALES_INVOICE_HEADER.xlsx"),
    "sales_invoice_header",
    conn
)
import_excel_to_db(
    os.path.join(FOLDERS["sales"], "SALES_INVOICE_LINE.xlsx"),
    "sales_invoice_line",
    conn
)

# -------------------------------
# 5️⃣ Purchase tables
# -------------------------------
import_excel_to_db(
    os.path.join(FOLDERS["purchase"], "PURCHASE_HEADER.xlsx"),
    "purchase_header",
    conn
)
import_excel_to_db(
    os.path.join(FOLDERS["purchase"], "PURCHASE_LINES.xlsx"),
    "purchase_line",
    conn
)

# -------------------------------
# 6️⃣ Inventory folder (multiple XLS files)
# -------------------------------
inventory_folder = FOLDERS["inventory"]

for filename in os.listdir(inventory_folder):
    if filename.lower().endswith(".xls"):
        file_path = os.path.join(inventory_folder, filename)
        df = pd.read_excel(file_path, engine='xlrd')
        
        # Keep only the DB columns (drop MODEL_CAR if not needed)
        df = df[['SUP_PART_NO', 'HEM_NAME', 'ORG', 'LOC_ON_SHELF', 'QTY', 'SELL_PRICE']]
        
        df.to_sql("inventory", conn, if_exists='append', index=False)
        print(f"Imported {filename} into inventory table")

# -------------------------------
# CLOSE CONNECTION
# -------------------------------
conn.close()
print("\nAll Excel sheets imported successfully into the database!")

