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
def import_excel_to_db(sheet_path, table_name, conn, rename_columns=None, dtype_casts=None, 
                       engine=None, subset_pk=None, clear_first=False, required_fields=None):
    """
    Import Excel data into SQLite database
    
    Args:
        sheet_path: Path to Excel file
        table_name: Target table name
        conn: SQLite connection
        rename_columns: Dict to rename columns
        dtype_casts: Dict to cast column types
        engine: Excel engine ('openpyxl' for .xlsx, 'xlrd' for .xls)
        subset_pk: List of columns that form primary key (for duplicate removal)
        clear_first: If True, delete existing data before importing
        required_fields: List of columns that cannot be NULL
    """
    df = pd.read_excel(sheet_path, engine=engine)

    # Rename columns if mapping provided
    if rename_columns:
        df = df.rename(columns=rename_columns)

    # Clear existing data if requested
    if clear_first:
        cursor = conn.cursor()
        cursor.execute(f"DELETE FROM {table_name.lower()}")
        conn.commit()
        print(f"🗑️  Cleared existing data from {table_name.lower()}")

    # Remove rows with NULL values in required fields
    if required_fields:
        initial_count = len(df)
        df = df.dropna(subset=required_fields)
        null_rows = initial_count - len(df)
        if null_rows > 0:
            print(f"⚠️  Removed {null_rows} rows with missing required fields from {os.path.basename(sheet_path)}")

    # Drop duplicates for primary key if specified
    if subset_pk:
        initial_count = len(df)
        df = df.drop_duplicates(subset=subset_pk)
        duplicates = initial_count - len(df)
        if duplicates > 0:
            print(f"⚠️  Removed {duplicates} duplicate rows from {os.path.basename(sheet_path)}")

    # Cast numeric columns
    if dtype_casts:
        for col, dtype in dtype_casts.items():
            if col in df.columns:
                df[col] = df[col].astype(dtype)

    # Insert into DB
    if len(df) > 0:
        df.to_sql(table_name.lower(), conn, if_exists='append', index=False)
        print(f"✅ {len(df)} records imported into {table_name.lower()} from {os.path.basename(sheet_path)}")
    else:
        print(f"⚠️  No valid records to import into {table_name.lower()}")


# -------------------------------
# CONNECT TO DB
# -------------------------------
conn = sqlite3.connect(DB_PATH)

try:
    # -------------------------------
    # 1️⃣ LEGENDS
    # -------------------------------
    import_excel_to_db(
        os.path.join(FOLDERS["legends"], "spi_legend.xlsx"),
        "legends",
        conn,
        rename_columns={"legend_id": "legend_id", "legend_name": "legend_name"},
        dtype_casts={"legend_id": str, "legend_name": str},
        subset_pk=["legend_id"],
        clear_first=True  # ✅ Clear before import
    )

    # -------------------------------
    # 2️⃣ SALES TABLES
    # -------------------------------
    sales_files = {
        "products": ("sales_product.xlsx", {"sku_no": "sku_no", "hem_name": "hem_name"}, 
                    ["sku_no"], ["sku_no", "hem_name"]),
        "customers": ("sales_customer.xlsx", {"id": "customer_id", "customer_code": "customer_code"}, 
                     ["customer_id"], ["customer_id", "customer_code"]),
        "sales_invoice_header": ("sales_invoice_header.xlsx",
                                 {"invoice_no": "invoice_no", "invoice_date": "invoice_date",
                                  "customer_id": "customer_id", "legend_code": "legend_id"}, 
                                 ["invoice_no"], ["invoice_no", "invoice_date", "customer_id"]),
        "sales_invoice_line": ("sales_invoice_line.xlsx",
                               {"invoice_no": "invoice_no", "line_no": "line_no", "sku_no": "sku_no",
                                "qty": "qty", "total_amt": "total_amt", "gst_amt": "gst_amt"}, 
                               ["invoice_no", "line_no"], 
                               ["invoice_no", "line_no", "qty", "total_amt", "gst_amt"])
    }

    sales_casts = {
        "customers": {"customer_id": int},
        "sales_invoice_line": {"line_no": int, "qty": int, "total_amt": float, "gst_amt": float}
    }

    for table, (filename, col_map, pk_cols, required_cols) in sales_files.items():
        file_path = os.path.join(FOLDERS["sales"], filename)
        import_excel_to_db(
            file_path,
            table,
            conn,
            rename_columns=col_map,
            dtype_casts=sales_casts.get(table, None),
            subset_pk=pk_cols,
            required_fields=required_cols,
            clear_first=True  # ✅ Clear before import
        )

    # -------------------------------
    # 3️⃣ PURCHASE TABLES
    # -------------------------------
    purchase_files = {
        "suppliers": ("suppliers.xlsx", {"supp_id": "supplier_id", "supp_name": "supp_name"}, 
                     ["supplier_id"], ["supplier_id", "supp_name"]),
        "products": ("product.xlsx", {"product_id": "product_id", "sku_no": "sku_no", 
                                     "hem_name": "hem_name"}, 
                    ["product_id"], ["sku_no", "hem_name"]),
        "purchase_header": ("purchase_header.xlsx",
                            {"purchase_ref_no": "purchase_ref_no", "purchase_date": "purchase_date",
                             "total_purchase": "total_purchase", "gst_amt": "gst_amt", 
                             "supplier_id": "supplier_id", "legend_id": "legend_id"}, 
                            ["purchase_ref_no"], 
                            ["purchase_ref_no", "purchase_date", "total_purchase", "gst_amt", "supplier_id"]),
        "purchase_line": ("purchase_lines.xlsx", 
                         {"purchase_ref_no": "purchase_ref_no", "line_no": "line_no",
                          "qty": "qty", "product_id": "product_id"}, 
                         ["purchase_ref_no", "line_no"],
                         ["purchase_ref_no", "product_id", "qty"])
    }

    purchase_casts = {
        "suppliers": {"supplier_id": int},
        "products": {"product_id": int},
        "purchase_header": {"total_purchase": float, "gst_amt": float},
        "purchase_line": {"line_no": int, "qty": int}
    }

    for table, (filename, col_map, pk_cols, required_cols) in purchase_files.items():
        file_path = os.path.join(FOLDERS["purchase"], filename)
        import_excel_to_db(
            file_path,
            table,
            conn,
            rename_columns=col_map,
            dtype_casts=purchase_casts.get(table, None),
            subset_pk=pk_cols,
            required_fields=required_cols,
            clear_first=True  # ✅ Clear before import
        )

    # -------------------------------
    # 4️⃣ INVENTORY TABLES (.xls)
    # -------------------------------
    print("\n📦 Importing inventory files...")
    
    # Clear inventory table first
    cursor = conn.cursor()
    cursor.execute("DELETE FROM inventory")
    conn.commit()
    print("🗑️  Cleared existing data from inventory")
    
    inventory_folder = FOLDERS["inventory"]
    inventory_columns = ['SUP_PART_NO', 'HEM_NAME', 'ORG', 'LOC_ON_SHELF', 'QTY', 'SELL_PRICE']
    
    total_inventory_records = 0
    for filename in os.listdir(inventory_folder):
        if filename.lower().endswith(".xls"):
            file_path = os.path.join(inventory_folder, filename)
            df = pd.read_excel(file_path, engine='xlrd')

            # Select only required columns
            df = df[inventory_columns]

            # Cast data types
            df['QTY'] = df['QTY'].astype(int)
            df['SELL_PRICE'] = df['SELL_PRICE'].astype(float)

            # Rename columns to lowercase for consistency
            df.columns = df.columns.str.lower()

            df.to_sql("inventory", conn, if_exists='append', index=False)
            total_inventory_records += len(df)
            print(f"✅ {len(df)} records imported from {filename}")
    
    print(f"📊 Total inventory records: {total_inventory_records}")

    # -------------------------------
    # COMMIT & CLOSE CONNECTION
    # -------------------------------
    conn.commit()
    print("\n🎉 All Excel sheets imported successfully into the database!")

except Exception as e:
    print(f"\n❌ Error during import: {e}")
    conn.rollback()
    raise

finally:
    conn.close()
    print("🔒 Database connection closed")





