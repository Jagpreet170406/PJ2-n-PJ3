#!/usr/bin/env python3
"""
EMERGENCY DATABASE DIAGNOSTIC
Run this to see what's ACTUALLY in your database
"""
import sqlite3
import os

DB_PATH = "database.db"

print("=" * 70)
print("🔍 EMERGENCY DATABASE DIAGNOSTIC")
print("=" * 70)

if not os.path.exists(DB_PATH):
    print(f"\n❌ CRITICAL: Database file '{DB_PATH}' NOT FOUND!")
    print(f"   Looking in: {os.getcwd()}")
    print(f"   Files here: {os.listdir('.')}")
    exit(1)

print(f"\n✅ Database found: {DB_PATH}")
print(f"   Size: {os.path.getsize(DB_PATH)} bytes")
print(f"   Path: {os.path.abspath(DB_PATH)}")

conn = sqlite3.connect(DB_PATH)
cursor = conn.cursor()

# Check all tables
print("\n" + "=" * 70)
print("📋 ALL TABLES IN DATABASE")
print("=" * 70)
cursor.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name")
tables = cursor.fetchall()
for table in tables:
    cursor.execute(f"SELECT COUNT(*) FROM {table[0]}")
    count = cursor.fetchone()[0]
    print(f"  {table[0]:<30} {count:>6} rows")

# Check sales_invoice_header
print("\n" + "=" * 70)
print("📊 SALES_INVOICE_HEADER TABLE (ALL INVOICES)")
print("=" * 70)
cursor.execute("SELECT COUNT(*) FROM sales_invoice_header")
total = cursor.fetchone()[0]
print(f"Total invoices: {total}")

if total == 0:
    print("\n🚨 NO INVOICES IN DATABASE AT ALL!")
    print("   This means invoices are NOT being saved!")
else:
    print(f"\nShowing ALL {total} invoices:")
    print("-" * 70)
    cursor.execute("SELECT invoice_no, invoice_date, customer_id, legend_id FROM sales_invoice_header ORDER BY invoice_date DESC")
    rows = cursor.fetchall()
    print(f"{'Invoice No':<20} {'Date':<12} {'Customer':<12} {'Legend':<10}")
    print("-" * 70)
    for row in rows:
        print(f"{row[0]:<20} {row[1]:<12} {row[2]:<12} {row[3] or 'N/A':<10}")

# Check sales_invoice_line
print("\n" + "=" * 70)
print("📦 SALES_INVOICE_LINE TABLE (ALL LINE ITEMS)")
print("=" * 70)
cursor.execute("SELECT COUNT(*) FROM sales_invoice_line")
line_total = cursor.fetchone()[0]
print(f"Total line items: {line_total}")

if line_total > 0:
    print(f"\nShowing ALL {line_total} line items:")
    print("-" * 70)
    cursor.execute("SELECT invoice_no, line_no, product_id, qty FROM sales_invoice_line ORDER BY invoice_no, line_no")
    lines = cursor.fetchall()
    print(f"{'Invoice No':<20} {'Line':<6} {'Product':<10} {'Qty':<6}")
    print("-" * 70)
    for line in lines:
        print(f"{line[0]:<20} {line[1]:<6} {line[2]:<10} {line[3]:<6}")

# Search for specific invoice
print("\n" + "=" * 70)
print("🔎 SEARCH FOR SPECIFIC INVOICE")
print("=" * 70)
search = input("Enter invoice number to search (or press Enter to skip): ").strip()

if search:
    cursor.execute("SELECT * FROM sales_invoice_header WHERE invoice_no = ?", (search,))
    result = cursor.fetchone()
    
    if result:
        print(f"\n✅ FOUND in sales_invoice_header:")
        print(f"   Invoice No: {result[0]}")
        print(f"   Date: {result[1]}")
        print(f"   Customer ID: {result[2]}")
        print(f"   Legend: {result[3]}")
        
        cursor.execute("SELECT * FROM sales_invoice_line WHERE invoice_no = ?", (search,))
        lines = cursor.fetchall()
        print(f"\n   Line items: {len(lines)}")
        for line in lines:
            print(f"      Line {line[1]}: Product {line[2]}, Qty {line[3]}")
    else:
        print(f"\n❌ NOT FOUND: Invoice '{search}' does not exist in database")
        print("\n   This could mean:")
        print("   1. Invoice was created BEFORE the fix was applied")
        print("   2. Invoice creation is still broken")
        print("   3. You're looking at the wrong database file")

conn.close()

print("\n" + "=" * 70)
print("💡 DIAGNOSIS TIPS")
print("=" * 70)
print("1. If you see 0 invoices but you created some:")
print("   → Your Flask app is using a DIFFERENT database.db file")
print("   → Check app.py for the DB_PATH variable")
print("")
print("2. If old invoices exist but new ones don't appear:")
print("   → The fix wasn't applied correctly")
print("   → Make sure you replaced app.py and restarted Flask")
print("")
print("3. If the invoice shows in UI but not in this script:")
print("   → It's a 'ghost invoice' from before the fix")
print("   → Just ignore it, it will disappear on page reload")
print("=" * 70)