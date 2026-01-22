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
def import_excel_to_db(sheet_path, table_name, conn, dtype_casts=None, engine=None):
    if not os.path.exists(sheet_path):
        print(f"❌ File not found: {sheet_path}")
        return
    df = pd.read_excel(sheet_path, engine=engine)

    # Cast columns if dtype_casts provided
    if dtype_casts:
        for col, dtype in dtype_casts.items():
            if col in df.columns:
                if dtype == int:
                    df[col] = pd.to_numeric(df[col], errors='coerce').fillna(0).astype(int)
                elif dtype == float:
                    df[col] = pd.to_numeric(df[col], errors='coerce').fillna(0.0).astype(float)
                elif dtype == str:
                    df[col] = df[col].astype(str)
    
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
    import_excel_to_db(file_path, "legends", conn, dtype_casts={"legend_id": str, "legend_name": str},
                       engine='xlrd' if f.lower().endswith(".xls") else None)

# -------------------------------
# 2️⃣ SALES
# -------------------------------
sales_files = {
    "products": {"file": "sales_product.xlsx", "dtype": {"sku_no": str, "hem_name": str}},
    "customers": {"file": "sales_customer.xlsx", "dtype": {"id": int, "customer_code": str}},
    "sales_invoice_header": {"file": "sales_invoice_header.xlsx",
                             "dtype": {"invoice_no": str, "invoice_date": str, "customer_id": int, "legend_id": str}},
    "sales_invoice_line": {"file": "sales_invoice_line.xlsx",
                           "dtype": {"invoice_no": str, "line_no": int, "sku_no": str, "qty": int,
                                     "total_amt": float, "gst_amt": float}}
}

for table, info in sales_files.items():
    path = os.path.join(FOLDERS["sales"], info["file"])
    import_excel_to_db(path, table, conn, dtype_casts=info["dtype"])

# -------------------------------
# 3️⃣ PURCHASE
# -------------------------------
purchase_files = {
    "suppliers": {"file": "supplier.xlsx", "dtype": {"supp_id": str, "supp_name": str}},
    "purchase_header": {"file": "purchase_header.xlsx",
                        "dtype": {"purchase_ref_no": str, "purchase_date": str, "total_purchase": float,
                                  "gst_amt": float, "supplier_id": str, "legend_id": str}},
    "purchase_line": {"file": "purchase_lines.xlsx", "dtype": {"purchase_ref_no": str, "qty": int, "product_id": str}}
}

for table, info in purchase_files.items():
    path = os.path.join(FOLDERS["purchase"], info["file"])
    import_excel_to_db(path, table, conn, dtype_casts=info["dtype"])

# -------------------------------
# 4️⃣ INVENTORY folder (all XLS)
# -------------------------------
inventory_folder = FOLDERS["inventory"]
for filename in os.listdir(inventory_folder):
    if filename.lower().endswith(".xls"):
        file_path = os.path.join(inventory_folder, filename)
        df = pd.read_excel(file_path, engine='xlrd')
        df = df[['SUP_PART_NO', 'HEM_NAME', 'ORG', 'LOC_ON_SHELF', 'QTY', 'SELL_PRICE']]

        # Cast numeric columns
        df['QTY'] = pd.to_numeric(df['QTY'], errors='coerce').fillna(0).astype(int)
        df['SELL_PRICE'] = pd.to_numeric(df['SELL_PRICE'], errors='coerce').fillna(0.0).astype(float)

        df.to_sql("inventory", conn, if_exists='append', index=False)
        print(f"✅ Imported {filename} into inventory table")

# -------------------------------
# CLOSE CONNECTION
# -------------------------------
conn.close()
print("\n🎉 All Excel sheets imported successfully into the database!")



