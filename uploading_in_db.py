import pandas as pd
from pathlib import Path
import sqlite3

# ===== CONFIG =====
BASE_DIR = Path("excel_data")  # folder containing SALES, PURCHASE, INVENTORY
DB_FILE = "database.db"        # matches your database.py

FOLDERS = {
    "SALES": "sales",
    "PURCHASE": "purchase",
    "INVENTORY": "inventory"
}
# ==================

def normalize_columns(df):
    """
    Strip whitespace, lowercase, replace spaces with underscores
    """
    df.columns = df.columns.str.strip().str.lower().str.replace(" ", "_")
    return df

def process_folder(folder_name, table_name):
    """
    Process all XLSX files in a folder and insert into the database table
    """
    folder_path = BASE_DIR / folder_name
    all_rows = []

    print(f"Processing folder '{folder_name}' → table '{table_name}'")

    for file in folder_path.glob("*.xlsx"):
        try:
            # Extract brand from filename (for inventory and purchase)
            if table_name in ["inventory", "purchase"]:
                brand = file.stem.split()[0]
            else:
                brand = None

            print(f"  Reading {file.name} | brand={brand if brand else 'N/A'}")

            df = pd.read_excel(file, engine="openpyxl")
            df = normalize_columns(df)

            # Add brand column if applicable
            if brand:
                df["brand"] = brand

            all_rows.append(df)

        except Exception as e:
            print(f"  Failed {file.name}: {e}")

    if not all_rows:
        print(f"No XLSX files found in folder '{folder_name}'")
        return

    master_df = pd.concat(all_rows, ignore_index=True)

    # Insert into SQLite
    conn = sqlite3.connect(DB_FILE)
    master_df.to_sql(table_name, conn, if_exists="append", index=False)
    conn.close()

    print(f"Inserted {len(master_df)} rows into '{table_name}'")

# ===== RUN PIPELINE =====
for folder, table in FOLDERS.items():
    process_folder(folder, table)

print("All XLSX data uploaded successfully")
