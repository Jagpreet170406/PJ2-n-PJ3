import os
import pandas as pd
import sqlite3

# -------------------------------
# CONFIG: folder paths
# -------------------------------
BASE_DIR = os.path.dirname(os.path.abspath(__file__))

FOLDERS = {
    "legends": os.path.join(BASE_DIR, "LEGEND"),
    "sales": os.path.join(BASE_DIR, "SALES"),
    "purchase": os.path.join(BASE_DIR, "PURCHASE"),
    "inventory": os.path.join(BASE_DIR, "INVENTORY")
}

DB_PATH = os.path.join(BASE_DIR, "database.db")

# -------------------------------
# HELPER FUNCTION
# -------------------------------
def import_excel_to_db(sheet_path, table_name, conn, engine=None):
    if not os.path.exists(sheet_path):
        print(f"❌ File not found: {sheet_path}")
        return
    df = pd.read_excel(sheet_path, engine=engine)
    df.to_sql(table_name.lower(), conn, if_exists='append', index=False)
    print(f"✅ {table_name.lower()} imported successfully from {os.path.basename(sheet_path)}")

# -------------------------------
# CONNECT TO DB
# -------------------------------
conn = sqlite3.connect(DB_PATH)

# -------------------------------
# 1️⃣ LEGENDS
# -------------------------------
legend_files = [f for f in os.listdir(FOLDERS["legends"]) if f.lower().endswith((".xls", ".xlsx"))]
for f in legend_files:
    file_path = os.path.join(FOLDERS["legends"], f)
    import_excel_to_db(file_path, "legends", conn, engine='xlrd' if f.lower().endswith(".xls") else None)

# -------------------------------
# 2️⃣ SALES: products & customers
# -------------------------------
sales_files = ["SALES_PRODUCT.xlsx", "SALES_CUSTOMER.xlsx", "SALES_INVOICE_HEADER.xlsx", "SALES_INVOICE_LINE.xlsx"]
for f in sales_files:
    file_path = os.path.join(FOLDERS["sales"], f)
    table_name = f.split(".")[0].lower()  # use filename as table name
    import_excel_to_db(file_path, table_name, conn)

# -------------------------------
# 3️⃣ PURCHASE: suppliers & headers & lines
# -------------------------------
purchase_files = ["SUPPLIERS.xlsx", "PURCHASE_HEADER.xlsx", "PURCHASE_LINES.xlsx"]
for f in purchase_files:
    file_path = os.path.join(FOLDERS["purchase"], f)
    table_name = f.split(".")[0].lower()
    import_excel_to_db(file_path, table_name, conn)

# -------------------------------
# 4️⃣ INVENTORY folder (all XLS)
# -------------------------------
inventory_folder = FOLDERS["inventory"]

for filename in os.listdir(inventory_folder):
    if filename.lower().endswith(".xls"):
        file_path = os.path.join(inventory_folder, filename)
        df = pd.read_excel(file_path, engine='xlrd')
        df = df[['SUP_PART_NO', 'HEM_NAME', 'ORG', 'LOC_ON_SHELF', 'QTY', 'SELL_PRICE']]
        df.to_sql("inventory", conn, if_exists='append', index=False)
        print(f"✅ Imported {filename} into inventory table")

# -------------------------------
# CLOSE CONNECTION
# -------------------------------
conn.close()
print("\n🎉 All Excel sheets imported successfully into the database!")


