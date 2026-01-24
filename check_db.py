import sqlite3
import pandas as pd
import os

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(BASE_DIR, "database.db")

# Connect to database
conn = sqlite3.connect(DB_PATH)
cursor = conn.cursor()

print("=" * 60)
print("DATABASE CONTENT SUMMARY")
print("=" * 60)

# Get all table names
cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
tables = cursor.fetchall()

total_records = 0

for table in tables:
    table_name = table[0]
    
    # Count records in each table
    cursor.execute(f"SELECT COUNT(*) FROM {table_name}")
    count = cursor.fetchone()[0]
    total_records += count
    
    print(f"\n📊 {table_name.upper()}")
    print(f"   Records: {count:,}")
    
    # Show sample data (first 3 rows)
    if count > 0:
        df = pd.read_sql(f"SELECT * FROM {table_name} LIMIT 3", conn)
        print(f"   Columns: {', '.join(df.columns.tolist())}")
        print("\n   Sample Data:")
        print(df.to_string(index=False))

print("\n" + "=" * 60)
print(f"TOTAL RECORDS ACROSS ALL TABLES: {total_records:,}")
print("=" * 60)

conn.close()