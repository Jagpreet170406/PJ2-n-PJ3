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
    # Import products first (needed for foreign key lookups)
    import_excel_to_db(
        os.path.join(FOLDERS["sales"], "sales_product.xlsx"),
        "products",
        conn,
        rename_columns={"sku_no": "sku_no", "hem_name": "hem_name"},
        subset_pk=["sku_no"],
        required_fields=["sku_no", "hem_name"],
        clear_first=True
    )
    
    # Import customers
    import_excel_to_db(
        os.path.join(FOLDERS["sales"], "sales_customer.xlsx"),
        "customers",
        conn,
        rename_columns={"id": "customer_id", "customer_code": "customer_code"},
        dtype_casts={"customer_id": int},
        subset_pk=["customer_id"],
        required_fields=["customer_id", "customer_code"],
        clear_first=True
    )
    
    # Import sales invoice header
    import_excel_to_db(
        os.path.join(FOLDERS["sales"], "sales_invoice_header.xlsx"),
        "sales_invoice_header",
        conn,
        rename_columns={
            "invoice_no": "invoice_no", 
            "invoice_date": "invoice_date",
            "customer_id": "customer_id", 
            "legend_code": "legend_id"
        },
        subset_pk=["invoice_no"],
        required_fields=["invoice_no", "invoice_date", "customer_id"],
        clear_first=True
    )
    
    # Import sales invoice line (with SKU to product_id conversion)
    print("\n📝 Processing sales_invoice_line with SKU lookup...")
    cursor = conn.cursor()
    cursor.execute("DELETE FROM sales_invoice_line")
    conn.commit()
    print("🗑️  Cleared existing data from sales_invoice_line")
    
    df_lines = pd.read_excel(os.path.join(FOLDERS["sales"], "sales_invoice_line.xlsx"))
    df_lines = df_lines.rename(columns={
        "invoice_no": "invoice_no",
        "line_no": "line_no",
        "sku_no": "sku_no",
        "qty": "qty",
        "total_amt": "total_amt",
        "gst_amt": "gst_amt"
    })
    
    # Get product_id mapping from products table
    product_mapping = pd.read_sql("SELECT product_id, sku_no FROM products", conn)
    
    # Merge to get product_id
    df_lines = df_lines.merge(product_mapping, on='sku_no', how='left')
    
    # Check for unmatched SKUs
    unmatched = df_lines[df_lines['product_id'].isna()]
    if len(unmatched) > 0:
        # Filter out rows where sku_no itself is NULL
        unmatched_with_sku = unmatched[unmatched['sku_no'].notna()]
        unmatched_null_sku = unmatched[unmatched['sku_no'].isna()]
        
        if len(unmatched_null_sku) > 0:
            print(f"⚠️  Warning: {len(unmatched_null_sku)} rows have NULL/empty SKU numbers (will be skipped)")
        
        if len(unmatched_with_sku) > 0:
            print(f"⚠️  Warning: {len(unmatched_with_sku)} rows have SKUs not found in products table")
            print(f"    Sample unmatched SKUs: {unmatched_with_sku['sku_no'].head().tolist()}")
    
    # Remove rows without valid product_id and drop sku_no column
    df_lines = df_lines.dropna(subset=['product_id'])
    df_lines = df_lines[['invoice_no', 'line_no', 'product_id', 'qty', 'total_amt', 'gst_amt']]
    
    # Remove duplicates and NULL required fields
    df_lines = df_lines.dropna(subset=['invoice_no', 'line_no', 'qty', 'total_amt', 'gst_amt'])
    df_lines = df_lines.drop_duplicates(subset=['invoice_no', 'line_no'])
    
    # Cast data types
    df_lines['line_no'] = df_lines['line_no'].astype(int)
    df_lines['product_id'] = df_lines['product_id'].astype(int)
    df_lines['qty'] = df_lines['qty'].astype(int)
    df_lines['total_amt'] = df_lines['total_amt'].astype(float)
    df_lines['gst_amt'] = df_lines['gst_amt'].astype(float)
    
    # Insert into database
    if len(df_lines) > 0:
        df_lines.to_sql('sales_invoice_line', conn, if_exists='append', index=False)
        print(f"✅ {len(df_lines)} records imported into sales_invoice_line")

    # -------------------------------
    # 3️⃣ PURCHASE TABLES
    # -------------------------------
    # Import suppliers first
    import_excel_to_db(
        os.path.join(FOLDERS["purchase"], "suppliers.xlsx"),
        "suppliers",
        conn,
        rename_columns={"supp_id": "supplier_id", "supp_name": "supp_name"},
        dtype_casts={"supplier_id": int},
        subset_pk=["supplier_id"],
        required_fields=["supplier_id", "supp_name"],
        clear_first=True
    )
    
    # Import purchase products (if different from sales products)
    # Note: This adds to the products table, doesn't replace it
    print("\n📦 Checking for purchase products...")
    
    purchase_product_path = os.path.join(FOLDERS["purchase"], "product.xlsx")
    if os.path.exists(purchase_product_path):
        cursor = conn.cursor()
        
        df_purchase_prod = pd.read_excel(purchase_product_path)
        df_purchase_prod = df_purchase_prod.rename(columns={
            "product_id": "product_id",
            "sku_no": "sku_no",
            "hem_name": "hem_name"
        })
        
        # Remove rows with missing required fields
        df_purchase_prod = df_purchase_prod.dropna(subset=["sku_no", "hem_name"])
        df_purchase_prod = df_purchase_prod.drop_duplicates(subset=["sku_no"])
        
        # Get existing SKUs to avoid duplicates
        existing_skus = pd.read_sql("SELECT sku_no FROM products", conn)
        df_purchase_prod = df_purchase_prod[~df_purchase_prod['sku_no'].isin(existing_skus['sku_no'])]
        
        if len(df_purchase_prod) > 0:
            # Drop product_id column if it exists (let DB auto-increment)
            if 'product_id' in df_purchase_prod.columns:
                df_purchase_prod = df_purchase_prod.drop('product_id', axis=1)
            
            df_purchase_prod.to_sql('products', conn, if_exists='append', index=False)
            print(f"✅ {len(df_purchase_prod)} new products added from purchase data")
        else:
            print("ℹ️  No new products to add from purchase data")
    else:
        print("ℹ️  No separate purchase product file found (using existing products table)")
    
    # Import purchase header
    import_excel_to_db(
        os.path.join(FOLDERS["purchase"], "purchase_header.xlsx"),
        "purchase_header",
        conn,
        rename_columns={
            "purchase_ref_no": "purchase_ref_no",
            "purchase_date": "purchase_date",
            "total_purchase": "total_purchase",
            "gst_amt": "gst_amt",
            "supplier_id": "supplier_id",
            "legend_id": "legend_id"
        },
        dtype_casts={"total_purchase": float, "gst_amt": float},
        subset_pk=["purchase_ref_no"],
        required_fields=["purchase_ref_no", "purchase_date", "total_purchase", "gst_amt", "supplier_id"],
        clear_first=True
    )
    
    # Import purchase line (with product_id conversion if needed)
    print("\n📝 Processing purchase_line...")
    cursor.execute("DELETE FROM purchase_line")
    conn.commit()
    print("🗑️  Cleared existing data from purchase_line")
    
    df_purch_lines = pd.read_excel(os.path.join(FOLDERS["purchase"], "purchase_lines.xlsx"))
    df_purch_lines = df_purch_lines.rename(columns={
        "purchase_ref_no": "purchase_ref_no",
        "line_no": "line_no",
        "qty": "qty",
        "product_id": "product_id"
    })
    
    # Remove NULL values and duplicates
    df_purch_lines = df_purch_lines.dropna(subset=["purchase_ref_no", "product_id", "qty"])
    df_purch_lines = df_purch_lines.drop_duplicates(subset=["purchase_ref_no", "line_no"])
    
    # Cast data types
    df_purch_lines['product_id'] = df_purch_lines['product_id'].astype(int)
    df_purch_lines['qty'] = df_purch_lines['qty'].astype(int)
    if 'line_no' in df_purch_lines.columns:
        df_purch_lines['line_no'] = df_purch_lines['line_no'].astype(int)
    
    if len(df_purch_lines) > 0:
        df_purch_lines.to_sql('purchase_line', conn, if_exists='append', index=False)
        print(f"✅ {len(df_purch_lines)} records imported into purchase_line")

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
    total_skipped = 0
    
    for filename in os.listdir(inventory_folder):
        if filename.lower().endswith(".xls"):
            file_path = os.path.join(inventory_folder, filename)
            df = pd.read_excel(file_path, engine='xlrd')

            # Select only required columns
            df = df[inventory_columns]
            
            # Remove rows with missing required fields
            initial_count = len(df)
            df = df.dropna(subset=['SUP_PART_NO', 'HEM_NAME', 'QTY', 'SELL_PRICE'])
            skipped = initial_count - len(df)
            total_skipped += skipped
            
            if skipped > 0:
                print(f"⚠️  Removed {skipped} rows with missing data from {filename}")

            # Cast data types (after removing NaN values)
            df['QTY'] = df['QTY'].astype(int)
            df['SELL_PRICE'] = df['SELL_PRICE'].astype(float)

            # Rename columns to lowercase for consistency
            df.columns = df.columns.str.lower()

            if len(df) > 0:
                df.to_sql("inventory", conn, if_exists='append', index=False)
                total_inventory_records += len(df)
                print(f"✅ {len(df)} records imported from {filename}")
    
    print(f"📊 Total inventory records: {total_inventory_records}")
    if total_skipped > 0:
        print(f"⚠️  Total rows skipped across all files: {total_skipped}")

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





