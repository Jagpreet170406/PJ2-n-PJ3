
File "C:\Users\jagsi\Documents\NYP\Y1S2 MODS\(IT1925) Web Development Project (WDP-WIU)\PJ2 n PJ3\uploading_in_db.py", line 52, in <module>
    import_excel_to_db(
    ~~~~~~~~~~~~~~~~~~^
        os.path.join(FOLDERS["legends"], "spi_legend.xlsx"),
        ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
    ...<4 lines>...
        subset_pk=["legend_id"]
        ^^^^^^^^^^^^^^^^^^^^^^^
    )
    ^
  File "C:\Users\jagsi\Documents\NYP\Y1S2 MODS\(IT1925) Web Development Project (WDP-WIU)\PJ2 n PJ3\uploading_in_db.py", line 40, in import_excel_to_db
    df.to_sql(table_name.lower(), conn, if_exists='append', index=False)
    ~~~~~~~~~^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
  File "C:\Users\jagsi\Documents\NYP\Y1S2 MODS\(IT1925) Web Development Project (WDP-WIU)\PJ2 n PJ3\venv\Lib\site-packages\pandas\util\_decorators.py", line 333, in wrapper
    return func(*args, **kwargs)
  File "C:\Users\jagsi\Documents\NYP\Y1S2 MODS\(IT1925) Web Development Project (WDP-WIU)\PJ2 n PJ3\venv\Lib\site-packages\pandas\core\generic.py", line 3109, in to_sql
    return sql.to_sql(
           ~~~~~~~~~~^
        self,
        ^^^^^
    ...<8 lines>...
        method=method,
        ^^^^^^^^^^^^^^
    )
    ^
  File "C:\Users\jagsi\Documents\NYP\Y1S2 MODS\(IT1925) Web Development Project (WDP-WIU)\PJ2 n PJ3\venv\Lib\site-packages\pandas\io\sql.py", line 844, in to_sql    
    return pandas_sql.to_sql(
           ~~~~~~~~~~~~~~~~~^
        frame,
        ^^^^^^
    ...<9 lines>...
        **engine_kwargs,
        ^^^^^^^^^^^^^^^^
    )
    ^
  File "C:\Users\jagsi\Documents\NYP\Y1S2 MODS\(IT1925) Web Development Project (WDP-WIU)\PJ2 n PJ3\venv\Lib\site-packages\pandas\io\sql.py", line 2841, in to_sql   
    return table.insert(chunksize, method)
           ~~~~~~~~~~~~^^^^^^^^^^^^^^^^^^^
  File "C:\Users\jagsi\Documents\NYP\Y1S2 MODS\(IT1925) Web Development Project (WDP-WIU)\PJ2 n PJ3\venv\Lib\site-packages\pandas\io\sql.py", line 1121, in insert   
    num_inserted = exec_insert(conn, keys, chunk_iter) 
  File "C:\Users\jagsi\Documents\NYP\Y1S2 MODS\(IT1925) Web Development Project (WDP-WIU)\PJ2 n PJ3\venv\Lib\site-packages\pandas\io\sql.py", line 2537, in _execute_insert
    conn.executemany(self.insert_statement(num_rows=1), data_list)
    ~~~~~~~~~~~~~~~~^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
sqlite3.IntegrityError: UNIQUE constraint failed: legends.legend_id

Show more
12:30 PM
This error occurs because you're trying to insert data with legend_id values that already exist in your legends table. The table has a UNIQUE constraint on legend_id, so duplicate entries are rejected.

Here are several solutions:

Solution 1: Clear the table before importing (if you want fresh data)
Modify your import_excel_to_db function to add a clear_first parameter:

python
def import_excel_to_db(file_path, table_name, conn, subset_pk=None, clear_first=False):
    df = pd.read_excel(file_path)
    
    if clear_first:
        # Delete existing data from the table
        cursor = conn.cursor()
        cursor.execute(f"DELETE FROM {table_name.lower()}")
        conn.commit()
    
    if subset_pk:
        df = df.drop_duplicates(subset=subset_pk)
    
    df.to_sql(table_name.lower(), conn, if_exists='append', index=False)
    print(f"Data imported successfully into {table_name}")
Then call it with:

python
import_excel_to_db(
    os.path.join(FOLDERS["legends"], "spi_legend.xlsx"),
    "legends",
    conn,
    subset_pk=["legend_id"],
    clear_first=True  # Add this
)
Solution 2: Use if_exists='replace' (replaces entire table structure)
python
df.to_sql(table_name.lower(), conn, if_exists='replace', index=False)
Warning: This drops and recreates the table, so you'll lose any indexes or constraints defined in your schema.

Solution 3: Check and skip existing records
python
def import_excel_to_db(file_path, table_name, conn, subset_pk=None):
    df = pd.read_excel(file_path)
    
    if subset_pk:
        df = df.drop_duplicates(subset=subset_pk)
        
        # Get existing IDs from database
        existing_ids = pd.read_sql(
            f"SELECT {', '.join(subset_pk)} FROM {table_name.lower()}", 
            conn
        )
        
        # Filter out rows that already exist
        df = df[~df[subset_pk].apply(tuple, axis=1).isin(
            existing_ids[subset_pk].apply(tuple, axis=1)
        )]
    
    if not df.empty:
        df.to_sql(table_name.lower(), conn, if_exists='append', index=False)
        print(f"{len(df)} new records imported into {table_name}")
    else:
        print(f"No new records to import into {table_name}")
Solution 4: Use UPSERT (update if exists, insert if not)
For SQLite, you can use INSERT OR REPLACE:

python
def import_excel_to_db(file_path, table_name, conn, subset_pk=None):
    df = pd.read_excel(file_path)
    
    if subset_pk:
        df = df.drop_duplicates(subset=subset_pk)
    
    # Use iterrows for more control (slower but handles upsert)
    cursor = conn.cursor()
    for _, row in df.iterrows():
        placeholders = ', '.join(['?' for _ in row])
        columns = ', '.join(row.index)
        sql = f"INSERT OR REPLACE INTO {table_name.lower()} ({columns}) VALUES ({placeholders})"
        cursor.execute(sql, tuple(row))
    
    conn.commit()
    print(f"Data imported successfully into {table_name}")
I recommend Solution 1 if you're just loading fresh data each time, or Solution 3 if you want to add only new records without touching existing ones.

import sqlite3
import os

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(BASE_DIR, "database.db")

conn = sqlite3.connect(DB_PATH)
cursor = conn.cursor()

# =========================
# LEGENDS
# =========================
cursor.execute("""
CREATE TABLE IF NOT EXISTS legends (
    legend_id TEXT PRIMARY KEY,
    legend_name TEXT NOT NULL
);
""")

# =========================
# PRODUCTS (Shared)
# =========================
cursor.execute("""
CREATE TABLE IF NOT EXISTS products (
    product_id INTEGER PRIMARY KEY AUTOINCREMENT,
    sku_no TEXT UNIQUE NOT NULL,
    hem_name TEXT NOT NULL
);
""")

# =========================
# CUSTOMERS
# =========================
cursor.execute("""
CREATE TABLE IF NOT EXISTS customers (
    customer_id INTEGER PRIMARY KEY,
    customer_code TEXT NOT NULL
);
""")

# =========================
# SUPPLIERS
# =========================
cursor.execute("""
CREATE TABLE IF NOT EXISTS suppliers (
    supplier_id INTEGER PRIMARY KEY,
    supp_name TEXT NOT NULL
);
""")

# =========================
# SALES
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
    FOREIGN KEY (invoice_no) REFERENCES sales_invoice_header(invoice_no),
    FOREIGN KEY (product_id) REFERENCES products(product_id)
);
""")

# =========================
# PURCHASE
# =========================
cursor.execute("""
CREATE TABLE IF NOT EXISTS purchase_header (
    purchase_ref_no TEXT PRIMARY KEY,
    purchase_date TEXT NOT NULL,
    total_purchase REAL NOT NULL,
    gst_amt REAL NOT NULL,
    supplier_id INTEGER NOT NULL,
    legend_id TEXT,
    FOREIGN KEY (supplier_id) REFERENCES suppliers(supplier_id),
    FOREIGN KEY (legend_id) REFERENCES legends(legend_id)
);
""")

cursor.execute("""
CREATE TABLE IF NOT EXISTS purchase_line (
    purchase_ref_no TEXT NOT NULL,
    line_no INTEGER NOT NULL,
    product_id INTEGER NOT NULL,
    qty INTEGER NOT NULL,
    PRIMARY KEY (purchase_ref_no, line_no),
    FOREIGN KEY (purchase_ref_no) REFERENCES purchase_header(purchase_ref_no),
    FOREIGN KEY (product_id) REFERENCES products(product_id)
);
""")

# =========================
# INVENTORY
# =========================
cursor.execute("""
CREATE TABLE IF NOT EXISTS inventory (
    inventory_id INTEGER PRIMARY KEY AUTOINCREMENT,
    sup_part_no TEXT NOT NULL,
    hem_name TEXT NOT NULL,
    org TEXT,
    loc_on_shelf TEXT,
    qty INTEGER NOT NULL,
    sell_price REAL NOT NULL
);
""")

conn.commit()
conn.close()

print("✅ database.db created successfully with correct schema")
this is database.py

Show more
12:30 PM
Based on your database schema, I can see that legend_id is defined as the PRIMARY KEY in the legends table, which automatically makes it UNIQUE.

Here's the updated uploading_in_db.py with Solution 1 (clear table before importing), which I think is the best approach for your use case:

uploading_in_db.py (Fixed)
Code 
Key Changes:
Added clear_first=True parameter - This deletes all existing data from the table before importing, preventing the UNIQUE constraint error
Better error messages - Shows what's happening (clearing data, removing duplicates, importing)
Try-except-finally block - Proper error handling and ensures connection is closed
Commented out other imports - Uncomment the ones you need as you add more Excel files
Alternative: If you want to keep existing data and only add new records
If you prefer to keep existing records and only insert new ones, use this version instead:

python
def import_excel_to_db(file_path, table_name, conn, subset_pk=None):
    df = pd.read_excel(file_path)
    
    if subset_pk:
        # Remove duplicates within Excel file
        df = df.drop_duplicates(subset=subset_pk)
        
        # Get existing primary keys from database
        pk_cols = ', '.join(subset_pk)
        existing = pd.read_sql(
            f"SELECT {pk_cols} FROM {table_name.lower()}", 
            conn
        )
        
        # Filter out rows that already exist in database
        if not existing.empty:
            merge_key = subset_pk[0] if len(subset_pk) == 1 else subset_pk
            df = df.merge(existing, on=merge_key, how='left', indicator=True)
            df = df[df['_merge'] == 'left_only'].drop('_merge', axis=1)
    
    if not df.empty:
        df.to_sql(table_name.lower(), conn, if_exists='append', index=False)
        print(f"✅ {len(df)} new records imported into {table_name}")
    else:
        print(f"ℹ️  No new records to import into {table_name}")
Choose the approach that fits your workflow better!






Claude is AI and can make mistakes. Please double-check responses.
import sqlite3
import pandas as pd
import os

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(BASE_DIR, "database.db")

# Define folder structure
FOLDERS = {
    "legends": os.path.join(BASE_DIR, "data", "legends"),
    "sales": os.path.join(BASE_DIR, "data", "sales"),
    "purchase": os.path.join(BASE_DIR, "data", "purchase"),
    "inventory": os.path.join(BASE_DIR, "data", "inventory"),
}

def import_excel_to_db(file_path, table_name, conn, subset_pk=None, clear_first=False):
    """
    Import Excel data into SQLite database
    
    Args:
        file_path: Path to Excel file
        table_name: Target table name
        conn: SQLite connection object
        subset_pk: List of columns to check for duplicates within the Excel file
        clear_first: If True, delete all existing data from table before importing
    """
    # Read Excel file
    df = pd.read_excel(file_path)
    
    # Clear existing data if requested
    if clear_first:
        cursor = conn.cursor()
        cursor.execute(f"DELETE FROM {table_name.lower()}")
        conn.commit()
        print(f"🗑️  Cleared existing data from {table_name}")
    
    # Remove duplicates within the Excel file itself (if subset_pk specified)
    if subset_pk:
        initial_count = len(df)
        df = df.drop_duplicates(subset=subset_pk)
        duplicates_removed = initial_count - len(df)
        if duplicates_removed > 0:
            print(f"⚠️  Removed {duplicates_removed} duplicate rows from Excel file")
    
    # Insert data
    df.to_sql(table_name.lower(), conn, if_exists='append', index=False)
    print(f"✅ {len(df)} records imported into {table_name}")

# Connect to database
conn = sqlite3.connect(DB_PATH)

try:
    # Import legends
    import_excel_to_db(
        os.path.join(FOLDERS["legends"], "spi_legend.xlsx"),
        "legends",
        conn,
        subset_pk=["legend_id"],
        clear_first=True  # Clear existing legends before importing
    )
    
    # Import customers (if you have this file)
    # import_excel_to_db(
    #     os.path.join(FOLDERS["sales"], "customers.xlsx"),
    #     "customers",
    #     conn,
    #     subset_pk=["customer_id"],
    #     clear_first=True
    # )
    
    # Import suppliers (if you have this file)
    # import_excel_to_db(
    #     os.path.join(FOLDERS["purchase"], "suppliers.xlsx"),
    #     "suppliers",
    #     conn,
    #     subset_pk=["supplier_id"],
    #     clear_first=True
    # )
    
    # Import products (if you have this file)
    # import_excel_to_db(
    #     os.path.join(FOLDERS["sales"], "products.xlsx"),
    #     "products",
    #     conn,
    #     subset_pk=["sku_no"],
    #     clear_first=True
    # )
    
    # Import sales invoices
    # import_excel_to_db(
    #     os.path.join(FOLDERS["sales"], "sales_invoice_header.xlsx"),
    #     "sales_invoice_header",
    #     conn,
    #     subset_pk=["invoice_no"],
    #     clear_first=True
    # )
    
    # import_excel_to_db(
    #     os.path.join(FOLDERS["sales"], "sales_invoice_line.xlsx"),
    #     "sales_invoice_line",
    #     conn,
    #     subset_pk=["invoice_no", "line_no"],
    #     clear_first=True
    # )
    
    # Import purchase data
    # import_excel_to_db(
    #     os.path.join(FOLDERS["purchase"], "purchase_header.xlsx"),
    #     "purchase_header",
    #     conn,
    #     subset_pk=["purchase_ref_no"],
    #     clear_first=True
    # )
    
    # import_excel_to_db(
    #     os.path.join(FOLDERS["purchase"], "purchase_line.xlsx"),
    #     "purchase_line",
    #     conn,
    #     subset_pk=["purchase_ref_no", "line_no"],
    #     clear_first=True
    # )
    
    # Import inventory
    # import_excel_to_db(
    #     os.path.join(FOLDERS["inventory"], "inventory.xlsx"),
    #     "inventory",
    #     conn,
    #     clear_first=True
    # )
    
    print("\n🎉 All data imported successfully!")
    
except Exception as e:
    print(f"\n❌ Error during import: {e}")
    conn.rollback()
    
finally:
    conn.close()








