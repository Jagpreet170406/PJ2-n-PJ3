import sqlite3
import pandas as pd
import os

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
def import_excel_to_db(sheet_path, table_name, conn):
    df = pd.read_excel(sheet_path)
    df.to_sql(table_name, conn, if_exists='append', index=False)
    print(f"{table_name} imported successfully from {sheet_path}")

# -------------------------------
# CONNECT TO DB
# -------------------------------
conn = sqlite3.connect(DB_PATH)

# -------------------------------
# 1️⃣ Dimension tables first
# -------------------------------
import_excel_to_db(os.path.join(FOLDERS["legends"], "SPI_LEGEND.xlsx"), "legends", conn)
import_excel_to_db(os.path.join(FOLDERS["sales"], "SALES_PRODUCT.xlsx"), "products", conn)
import_excel_to_db(os.path.join(FOLDERS["sales"], "SALES_CUSTOMER.xlsx"), "customers", conn)
import_excel_to_db(os.path.join(FOLDERS["purchase"], "SUPPLIERS.xlsx"), "suppliers", conn)

# -------------------------------
# 2️⃣ Sales tables
# -------------------------------
import_excel_to_db(os.path.join(FOLDERS["sales"], "SALES_INVOICE_HEADER.xlsx"), "sales_invoice_header", conn)
import_excel_to_db(os.path.join(FOLDERS["sales"], "SALES_INVOICE_LINE.xlsx"), "sales_invoice_line", conn)

# -------------------------------
# 3️⃣ Purchase tables
# -------------------------------
import_excel_to_db(os.path.join(FOLDERS["purchase"], "PURCHASE_HEADER.xlsx"), "purchase_header", conn)
import_excel_to_db(os.path.join(FOLDERS["purchase"], "PURCHASE_LINES.xlsx"), "purchase_line", conn)

# -------------------------------
# 4️⃣ Inventory
# -------------------------------
import_excel_to_db(os.path.join(FOLDERS["inventory"], "INVENTORY.xlsx"), "inventory", conn)

# -------------------------------
# CLOSE CONNECTION
# -------------------------------
conn.close()
print("\nAll Excel sheets imported successfully!")
