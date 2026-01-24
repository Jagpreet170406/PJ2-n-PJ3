import os
import sqlite3
import pandas as pd

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(BASE_DIR, "database.db")

FILES = {
    "sales_invoice_header": os.path.join(BASE_DIR, "SALES", "sales_invoice_header.xlsx"),
    "sales_invoice_line": os.path.join(BASE_DIR, "SALES", "sales_invoice_line.xlsx"),
    "sales_product": os.path.join(BASE_DIR, "SALES", "sales_product.xlsx"),
    "sales_customer": os.path.join(BASE_DIR, "SALES", "sales_customer.xlsx"),
}
    
def main():
    conn = sqlite3.connect(DB_PATH)

    for table_name, path in FILES.items():
        if not os.path.exists(path):
            raise FileNotFoundError(f"Missing file: {path}")

        df = pd.read_excel(path)

        # Normalize column names (optional but helpful)
        df.columns = [c.strip() for c in df.columns]

        # Convert invoice_date nicely if present
        if "invoice_date" in df.columns:
            df["invoice_date"] = pd.to_datetime(df["invoice_date"], errors="coerce").dt.strftime("%Y-%m-%d")

        # Replace table with the Excel schema
        df.to_sql(table_name, conn, if_exists="replace", index=False)
        print(f"Imported {table_name}: {len(df)} rows, cols={list(df.columns)}")

    conn.commit()
    conn.close()
    print("\n✅ Done importing SALES excel into database.db")

if __name__ == "__main__":
    main()
