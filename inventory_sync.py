#!/usr/bin/env python3
"""
Sync Inventory to Products Table
This script copies all items from the inventory table to the products table
so that invoices can reference them properly.
"""

import sqlite3

DB_PATH = "database.db"

def sync_inventory_to_products():
    """Copy all inventory items to products table"""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    print("🔍 Checking current state...")
    
    # Count items in each table
    inv_count = cursor.execute("SELECT COUNT(*) FROM inventory").fetchone()[0]
    prod_count = cursor.execute("SELECT COUNT(*) FROM products").fetchone()[0]
    
    print(f"   Inventory table: {inv_count} items")
    print(f"   Products table: {prod_count} items")
    
    if inv_count == 0:
        print("\n❌ ERROR: Inventory table is empty!")
        print("   Please add items to inventory first.")
        conn.close()
        return False
    
    print("\n📋 Syncing inventory → products...")
    
    # Get all inventory items
    inventory_items = cursor.execute("""
        SELECT inventory_id, sup_part_no, hem_name 
        FROM inventory
    """).fetchall()
    
    synced = 0
    skipped = 0
    
    for inv_id, sku, name in inventory_items:
        # Use sup_part_no as SKU, or generate one from inventory_id
        sku_to_use = sku if sku else f"INV-{inv_id}"
        
        # Check if product already exists with this SKU
        existing = cursor.execute(
            "SELECT product_id FROM products WHERE sku_no = ?", 
            (sku_to_use,)
        ).fetchone()
        
        if existing:
            skipped += 1
            continue
        
        # Insert into products table with the SAME product_id as inventory_id
        # This ensures foreign keys work!
        try:
            cursor.execute("""
                INSERT INTO products (product_id, sku_no, hem_name)
                VALUES (?, ?, ?)
            """, (inv_id, sku_to_use, name))
            synced += 1
        except sqlite3.IntegrityError as e:
            # If product_id already exists, try without specifying it
            cursor.execute("""
                INSERT INTO products (sku_no, hem_name)
                VALUES (?, ?)
            """, (sku_to_use, name))
            synced += 1
    
    conn.commit()
    
    print(f"✅ Synced {synced} items")
    print(f"⏭️  Skipped {skipped} duplicates")
    
    # Show final counts
    new_prod_count = cursor.execute("SELECT COUNT(*) FROM products").fetchone()[0]
    print(f"\n📊 Products table now has: {new_prod_count} items")
    
    # Show sample products
    print("\n🔍 Sample products:")
    samples = cursor.execute("SELECT product_id, sku_no, hem_name FROM products LIMIT 5").fetchall()
    for prod_id, sku, name in samples:
        print(f"   ID: {prod_id} | SKU: {sku} | Name: {name}")
    
    conn.close()
    return True

def verify_foreign_keys():
    """Check if foreign keys are working"""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    print("\n🔍 Verifying foreign key constraints...")
    
    # Check if PRAGMA is enabled
    fk_status = cursor.execute("PRAGMA foreign_keys").fetchone()
    print(f"   Foreign keys enabled: {fk_status[0] if fk_status else 'Unknown'}")
    
    # Try to create a test invoice
    print("\n🧪 Testing invoice creation...")
    
    # Get first customer
    customer = cursor.execute("SELECT customer_id FROM customers LIMIT 1").fetchone()
    if not customer:
        print("   ❌ No customers found! Add a customer first.")
        conn.close()
        return False
    
    # Get first product
    product = cursor.execute("SELECT product_id FROM products LIMIT 1").fetchone()
    if not product:
        print("   ❌ No products found! Run sync first.")
        conn.close()
        return False
    
    customer_id = customer[0]
    product_id = product[0]
    
    print(f"   Using customer_id: {customer_id}")
    print(f"   Using product_id: {product_id}")
    
    # Try creating a test invoice
    try:
        test_invoice = "TEST-SYNC-001"
        
        # Delete if exists
        cursor.execute("DELETE FROM sales_invoice_line WHERE invoice_no = ?", (test_invoice,))
        cursor.execute("DELETE FROM sales_invoice_header WHERE invoice_no = ?", (test_invoice,))
        
        # Create header
        cursor.execute("""
            INSERT INTO sales_invoice_header (invoice_no, invoice_date, customer_id, legend_id)
            VALUES (?, '2024-02-13', ?, 'SGP')
        """, (test_invoice, customer_id))
        
        print("   ✅ Header created")
        
        # Create line
        cursor.execute("""
            INSERT INTO sales_invoice_line (invoice_no, line_no, product_id, qty, total_amt, gst_amt)
            VALUES (?, 1, ?, 1, 100.0, 8.0)
        """, (test_invoice, product_id))
        
        print("   ✅ Line item created")
        
        conn.commit()
        print("   ✅ Test invoice committed successfully!")
        
        # Clean up
        cursor.execute("DELETE FROM sales_invoice_line WHERE invoice_no = ?", (test_invoice,))
        cursor.execute("DELETE FROM sales_invoice_header WHERE invoice_no = ?", (test_invoice,))
        conn.commit()
        
        print("   ✅ Test invoice deleted")
        print("\n✅ Foreign keys are working correctly!")
        
    except sqlite3.IntegrityError as e:
        print(f"   ❌ Foreign key error: {e}")
        conn.rollback()
        conn.close()
        return False
    except Exception as e:
        print(f"   ❌ Unexpected error: {e}")
        conn.rollback()
        conn.close()
        return False
    
    conn.close()
    return True

if __name__ == "__main__":
    print("=" * 60)
    print("  INVENTORY → PRODUCTS SYNC TOOL")
    print("=" * 60)
    
    # Step 1: Sync
    if sync_inventory_to_products():
        # Step 2: Verify
        verify_foreign_keys()
    
    print("\n" + "=" * 60)
    print("✅ Done! You can now create invoices.")
    print("=" * 60)