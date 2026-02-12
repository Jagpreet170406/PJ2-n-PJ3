#!/usr/bin/env python3
"""Quick check if invoice exists in database"""
import sqlite3
import sys

DB_PATH = "database.db"

if len(sys.argv) < 2:
    print("Usage: python3 quick_check.py INVOICE-NUMBER")
    sys.exit(1)

invoice_no = sys.argv[1]

conn = sqlite3.connect(DB_PATH)
cursor = conn.cursor()

# Check header
header = cursor.execute("SELECT * FROM sales_invoice_header WHERE invoice_no = ?", (invoice_no,)).fetchone()

# Check lines
lines = cursor.execute("SELECT * FROM sales_invoice_line WHERE invoice_no = ?", (invoice_no,)).fetchall()

conn.close()

print("=" * 60)
print(f"CHECKING INVOICE: {invoice_no}")
print("=" * 60)

if header:
    print("✅ FOUND in sales_invoice_header")
    print(f"   Date: {header[1]}")
    print(f"   Customer ID: {header[2]}")
    print(f"   Legend: {header[3]}")
    print(f"\n   Line items: {len(lines)}")
    for line in lines:
        print(f"      Line {line[1]}: Product {line[2]}, Qty {line[3]}")
else:
    print("❌ NOT FOUND in sales_invoice_header")
    print("\nThis invoice does NOT exist in the database!")
    print("It's a 'ghost invoice' - only exists in the UI, not in DB.")