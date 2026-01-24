import sqlite3
import os

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB = os.path.join(BASE_DIR, "database.db")

conn = sqlite3.connect(DB)

# Check tables exist
tables = conn.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()
print("Tables:", [t[0] for t in tables])

# Check columns in each table
for table in ["sales_invoice_header", "sales_invoice_line", "sales_product", "sales_customer"]:
    try:
        cursor = conn.execute(f"PRAGMA table_info({table})")
        print(f"\n{table} columns:", [col[1] for col in cursor.fetchall()])
        
        count = conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
        print(f"{table} row count:", count)
        
        # Sample data
        sample = conn.execute(f"SELECT * FROM {table} LIMIT 1").fetchone()
        print(f"{table} sample:", sample)
    except Exception as e:
        print(f"Error with {table}: {e}")

conn.close()