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
def import_excel_to_db(sheet_path, table_name, conn, dtype_casts=None, engine=None, subset_pk=None):
    df = pd.read_excel(sheet_path, engine=engine)

    # Drop duplicates for primary key if specified
    if subset_pk:
        df = df.drop_duplicates(subset=subset_pk)

    # Apply type casting if provided
    if dtype_casts:
        for col, dtype in dtype_casts.items():
            if col in df.columns:
                df[col] = df[col].astype(dtype)

    # Insert into DB
    df.to_sql(table_name.lower(), conn, if_exists='append', index=False)
    print(f"✅ {table_name.lower()} imported successfully from {os.path.basename(sheet_path)}")

# -------------------------------
# CONNECT TO DB
# -------------------------------
conn = sqlite3.connect(DB_PATH)

# -------------------------------
# 1️⃣ LEGENDS
# -------------------------------
legend_file = os.path.join(FOLDERS["legends"], "spi_legend.xlsx")
import_excel_to_db(
    legend_file,
    "legends",
    conn,
    dtype_casts={"legend_id": str, "legend_name": str},
    subset_pk=["legend_id"]
)

# -------------------------------
# 2️⃣ SALES TABLES
# -------------------------------
sales_files = {
    "products": "sales_product.xlsx",
    "customers": "sales_customer.xlsx",
    "sales_invoice_header": "sales_invoice_header.xlsx",
    "sales_invoice_line": "sales_invoice_line.xlsx"
}

sales_casts = {
    "customers": {"id": int},
    "sales_invoice_line": {"line_no": int, "qty": int, "total_amt": float, "gst_amt": float}
}

for table, filename in sales_files.items():
    file_path = os.path.join(FOLDERS["sales"], filename)
    import_excel_to_db(
        file_path,
        table,
        conn,
        dtype_casts=sales_casts.get(table, None)
    )

# -------------------------------
# 3️⃣ PURCHASE TABLES
# -------------------------------
purchase_files = {
    "suppliers": "suppliers.xlsx",
    "purchase_header": "purchase_header.xlsx",
    "purchase_line": "purchase_lines.xlsx",
    "products": "product.xlsx"
}

purchase_casts = {
    "purchase_header": {"total_purchase": float, "gst_amt": float},
    "purchase_line": {"qty": int}
}

for table, filename in purchase_files.items():
    file_path = os.path.join(FOLDERS["purchase"], filename)
    import_excel_to_db(
        file_path,
        table,
        conn,
        dtype_casts=purchase_casts.get(table, None)
    )

# -------------------------------
# 4️⃣ INVENTORY TABLES (multiple .xls files)
# -------------------------------
inventory_folder = FOLDERS["inventory"]
inventory_columns = ['SUP_PART_NO', 'HEM_NAME', 'ORG', 'LOC_ON_SHELF', 'QTY', 'SELL_PRICE']

for filename in os.listdir(inventory_folder):
    if filename.lower().endswith(".xls"):
        file_path = os.path.join(inventory_folder, filename)
        df = pd.read_excel(file_path, engine='xlrd')

        # Keep only relevant DB columns
        df = df[inventory_columns]

        # Cast numeric columns
        df['QTY'] = df['QTY'].astype(int)
        df['SELL_PRICE'] = df['SELL_PRICE'].astype(float)

        # Insert into DB
        df.to_sql("inventory", conn, if_exists='append', index=False)
        print(f"✅ Imported {filename} into inventory table")

# -------------------------------
# CLOSE CONNECTION
# -------------------------------
conn.close()
print("\n🎉 All Excel sheets imported successfully into the database!")




