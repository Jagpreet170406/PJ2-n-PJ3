# === IMPORTS ===
import sqlite3
import os
import json
from functools import wraps
from collections import defaultdict
from datetime import datetime, timedelta, date
from flask import Flask, render_template, request, redirect, url_for, session, flash, jsonify
from flask_wtf.csrf import CSRFProtect, generate_csrf
from werkzeug.security import generate_password_hash, check_password_hash
from groq import Groq

# === FLASK APP INITIALIZATION ===
app = Flask(__name__)
app.secret_key = "chinhon_secret_key"  # Secret key for session management
csrf = CSRFProtect(app)  # Enable CSRF protection for forms

# === GROQ API SETUP ===
# Get API key from environment variable (set in your system or .env file)
GROQ_API_KEY = os.getenv("GROQ_API_KEY", "")
groq_client = Groq(api_key=GROQ_API_KEY) if GROQ_API_KEY else None

# === DATABASE SETUP ===
BASE_DIR = os.path.dirname(os.path.abspath(__file__))  # Get current directory
DB = os.path.join(BASE_DIR, "database.db")  # Path to SQLite database

def get_db():
    """Create and return a database connection with dict-like row access."""
    conn = sqlite3.connect(DB)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    """Initialize database tables if they don't exist."""
    with get_db() as conn:
        # Table for storing user credit card information
        conn.execute("""
            CREATE TABLE IF NOT EXISTS user_cards (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT NOT NULL,
                brand TEXT,
                last4 TEXT,
                exp TEXT,
                name TEXT
            )
        """)
        # Table for storing sales analytics data
        conn.execute("""
            CREATE TABLE IF NOT EXISTS sales_data (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                item_code TEXT NOT NULL,
                description TEXT,
                qty_sold INTEGER NOT NULL,
                total_sales REAL NOT NULL,
                period TEXT NOT NULL,
                competitor_price REAL,
                stock_qty INTEGER DEFAULT 0,
                demand_level INTEGER DEFAULT 3,
                recommended_price REAL
            )
        """)
        # Performance indexes for dashboard filtering/sorting
        conn.execute("CREATE INDEX IF NOT EXISTS idx_sih_date    ON sales_invoice_header(invoice_date)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_sih_cust    ON sales_invoice_header(customer_id)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_sil_inv     ON sales_invoice_line(invoice_no)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_sil_prod    ON sales_invoice_line(product_id)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_prod_name   ON products(hem_name)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_cust_code   ON customers(customer_code)")
        conn.commit()

init_db()  # Initialize database on app startup

# === CONTEXT PROCESSORS ===
@app.context_processor
def inject_csrf_token():
    """Make CSRF token and today's date available to all templates."""
    return dict(
        csrf_token=generate_csrf,
        today=date.today().isoformat()
    )

# === AUTHENTICATION DECORATORS ===
def require_staff(f):
    """Decorator to protect routes that require staff access."""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if session.get("role") not in ["employee", "admin", "superowner"]:
            return redirect(url_for('cart'))
        return f(*args, **kwargs)
    return decorated_function

# === ROUTING ===

@app.route("/")
def root():
    """Root route - redirects based on user role."""
    role = session.get("role")
    if role in ["employee", "admin", "superowner"]:
        return redirect(url_for("home"))
    return redirect(url_for("cart"))

@app.route("/cart")
def cart():
    """Customer-facing product catalog with pagination, search, and filtering."""
    # Get pagination and filter parameters from URL
    page = request.args.get('page', 1, type=int)
    search_query = request.args.get('search', '')
    category_filter = request.args.get('category', '')
    per_page = 24
    offset = (page - 1) * per_page

    with get_db() as conn:
        # Get all unique categories for filter dropdown
        categories = conn.execute("SELECT DISTINCT category FROM inventory WHERE category IS NOT NULL").fetchall()
        
        # Build dynamic query based on filters
        base_query = " FROM inventory WHERE qty > 0"  # Only show in-stock items
        params = []

        # Add search filter if provided
        if search_query:
            base_query += " AND (hem_name LIKE ? OR sup_part_no LIKE ?)"
            params.extend([f'%{search_query}%', f'%{search_query}%'])

        # Add category filter if provided
        if category_filter:
            base_query += " AND category = ?"
            params.append(category_filter)

        # Calculate total pages for pagination
        total_count = conn.execute("SELECT COUNT(*)" + base_query, params).fetchone()[0]
        total_pages = (total_count // per_page) + (1 if total_count % per_page > 0 else 0)

        # Get products for current page
        final_query = "SELECT *" + base_query + " ORDER BY hem_name ASC LIMIT ? OFFSET ?"
        params.extend([per_page, offset])
        products = conn.execute(final_query, params).fetchall()

    return render_template("cart.html", products=products, categories=categories,
                           current_page=page, total_pages=total_pages,
                           search_query=search_query, category_filter=category_filter,
                           role=session.get("role", "customer"))

@app.route("/checkout")
def checkout():
    """Checkout page where customers finalize their orders."""
    return render_template("checkout.html", role=session.get("role", "customer"), user_cards=[])

@app.route("/process-payment", methods=["POST"])
@csrf.exempt  # Exempt from CSRF for API-style endpoint
def process_payment():
    """Process payment submission and save transaction to database."""
    data = request.get_json()
    if not data:
        return jsonify({"success": False, "message": "No data received"})

    # Extract payment details from request
    cart_items = data.get('cart', [])
    payment_method = data.get('payment_method', 'Credit Card')
    total_amount = data.get('total_amount', 0)
    fulfillment = data.get('fulfillment', 'pickup')
    username = session.get("username", "Guest")

    # Validate cart is not empty
    if not cart_items:
        return jsonify({"success": False, "message": "Cart is empty"})

    try:
        # Save transaction to database
        with get_db() as conn:
            payment_label = f"{payment_method} ({fulfillment})"
            conn.execute("INSERT INTO transactions (username, payment_type, amount) VALUES (?, ?, ?)",
                        (username, payment_label, total_amount))
            conn.commit()
            print(f"✅ Payment processed: {payment_label} - S${total_amount} for {username}")
        return jsonify({"success": True, "message": "Payment successful"})
    except Exception as e:
        print(f"❌ Payment error: {e}")
        return jsonify({"success": False, "message": str(e)})

@app.route("/order-success")
def order_success():
    """Order confirmation page after successful payment."""
    method = request.args.get('method', 'pickup')  # delivery or pickup
    date = request.args.get('date', '')  # delivery address or pickup date
    return render_template("order_success.html", method=method, date=date, role="customer")

@app.route("/contact")
def contact():
    """Contact information page for customers."""
    return render_template("contact.html", role="customer")

@app.route("/staff-login", methods=["GET", "POST"])
def staff_login():
    """Staff login page - validates credentials and creates session."""
    # Redirect if already logged in as staff
    if session.get("role") in ["employee", "admin", "superowner"]:
        return redirect(url_for("home"))

    if request.method == "POST":
        u, p = request.form.get("username"), request.form.get("password")
        with get_db() as conn:
            user = conn.execute("SELECT * FROM users WHERE username=?", (u,)).fetchone()

        # Verify password and create session
        if user and check_password_hash(user['password_hash'], p):
            session.update({"username": u, "role": user['role']})
            return redirect(url_for("home"))
        flash("Invalid credentials", "danger")

    return render_template("staff_login.html", role="customer")

@app.route("/home")
@require_staff  # Only accessible to staff
def home():
    """Staff home/dashboard page."""
    return render_template("home.html", role=session.get("role"))

@app.route('/about')
def about():
    """About us page - company information."""
    return render_template('about_us.html')

# === INVENTORY MANAGEMENT ROUTES ===

@app.route("/inventory")
@require_staff
def inventory():
    """Inventory management page with CRUD operations."""
    return render_template("inventory.html", role=session.get("role"))

@app.route("/api/inventory", methods=["GET"])
@csrf.exempt
@require_staff
def api_get_inventory():
    """API: Retrieve all inventory items as JSON."""
    try:
        with get_db() as conn:
            items = conn.execute("SELECT * FROM inventory ORDER BY hem_name ASC").fetchall()
            print(f"✅ Loaded {len(items)} inventory items")
            return jsonify([dict(item) for item in items])
    except Exception as e:
        print(f"❌ Error getting inventory: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({"error": str(e)}), 500

@app.route("/api/inventory", methods=["POST"])
@csrf.exempt
@require_staff
def api_create_inventory():
    """API: Create a new inventory item with validation."""
    data = request.get_json()
    
    # Extract and sanitize input data
    sup_part_no = (data.get('sup_part_no') or '').strip()
    hem_name = (data.get('hem_name') or '').strip()
    category = data.get('category', 'Lubricants')
    qty = int(data.get('qty', 0))
    sell_price = float(data.get('sell_price', 0))
    image_url = (data.get('image_url') or '').strip()
    
    if not hem_name:
        return jsonify({"success": False, "message": "Product name is required"}), 400
    
    try:
        with get_db() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO inventory (sup_part_no, hem_name, category, qty, sell_price, image_url)
                VALUES (?, ?, ?, ?, ?, ?)
            """, (sup_part_no, hem_name, category, qty, sell_price, image_url))
            conn.commit()
            print(f"✅ Product created: {hem_name} (ID: {cursor.lastrowid})")
            return jsonify({"success": True, "inventory_id": cursor.lastrowid, "message": "Product added successfully"})
    except Exception as e:
        print(f"❌ Error creating product: {e}")
        return jsonify({"success": False, "message": str(e)}), 500

@app.route("/api/inventory/<int:inventory_id>", methods=["PUT"])
@csrf.exempt
@require_staff
def api_update_inventory(inventory_id):
    """API: Update an existing inventory item."""
    data = request.get_json()
    
    # Extract and sanitize input
    sup_part_no = (data.get('sup_part_no') or '').strip()
    hem_name = (data.get('hem_name') or '').strip()
    category = data.get('category', 'Lubricants')
    qty = int(data.get('qty', 0))
    sell_price = float(data.get('sell_price', 0))
    image_url = (data.get('image_url') or '').strip()
    
    if not hem_name:
        return jsonify({"success": False, "message": "Product name is required"}), 400
    
    try:
        with get_db() as conn:
            conn.execute("""
                UPDATE inventory
                SET sup_part_no=?, hem_name=?, category=?, qty=?, sell_price=?, image_url=?
                WHERE inventory_id=?
            """, (sup_part_no, hem_name, category, qty, sell_price, image_url, inventory_id))
            conn.commit()
            print(f"✅ Product updated: {hem_name} (ID: {inventory_id})")
            return jsonify({"success": True, "message": "Product updated successfully"})
    except Exception as e:
        print(f"❌ Error updating product: {e}")
        return jsonify({"success": False, "message": str(e)}), 500

@app.route("/api/inventory/<int:inventory_id>", methods=["DELETE"])
@csrf.exempt
@require_staff
def api_delete_inventory(inventory_id):
    """API: Delete an inventory item permanently."""
    try:
        with get_db() as conn:
            conn.execute("DELETE FROM inventory WHERE inventory_id=?", (inventory_id,))
            conn.commit()
            print(f"✅ Product deleted (ID: {inventory_id})")
            return jsonify({"success": True, "message": "Product deleted successfully"})
    except Exception as e:
        print(f"❌ Error deleting product: {e}")
        return jsonify({"success": False, "message": str(e)}), 500


# === SALES DASHBOARD ROUTES ===

@app.route("/dashboard")
@require_staff
def dashboard():
    """Sales dashboard — optimized: SQL-level pagination, minimal joins, indexed queries."""
    page       = request.args.get('page', 1, type=int)
    per_page   = 20
    offset     = (page - 1) * per_page
    search     = request.args.get('search', '').strip()
    start_date = request.args.get('start_date', '').strip()
    end_date   = request.args.get('end_date', '').strip()

    with get_db() as conn:

        # === BUILD FILTER: only join what each query actually needs ===
        # For search we need products/customers; date filter only touches header.
        # We pre-compute a set of matching invoice_nos once, then reuse it.

        if search or start_date or end_date:
            # Build a minimal subquery that returns matching invoice_nos
            inner_clauses = []
            inner_params  = []

            if search:
                inner_clauses.append("""(
                    h.invoice_no LIKE ?
                    OR EXISTS (
                        SELECT 1 FROM sales_invoice_line l2
                        JOIN products p2 ON p2.product_id = l2.product_id
                        WHERE l2.invoice_no = h.invoice_no AND p2.hem_name LIKE ?
                    )
                    OR EXISTS (
                        SELECT 1 FROM customers c2
                        WHERE c2.customer_id = h.customer_id AND c2.customer_code LIKE ?
                    )
                )""")
                like = f'%{search}%'
                inner_params.extend([like, like, like])

            if start_date:
                inner_clauses.append("h.invoice_date >= ?")
                inner_params.append(start_date)

            if end_date:
                inner_clauses.append("h.invoice_date <= ?")
                inner_params.append(end_date)

            filter_where = "WHERE " + " AND ".join(inner_clauses)
        else:
            filter_where  = ""
            inner_params  = []

        # === 1. COUNT + KPIs in a single pass (no Python-side aggregation) ===
        kpi_row = conn.execute(f"""
            SELECT
                COUNT(DISTINCT h.invoice_no)            AS total_invoices,
                COUNT(DISTINCT h.customer_id)           AS total_customers,
                COALESCE(SUM(l.total_amt), 0)           AS total_revenue,
                COALESCE(SUM(l.gst_amt),  0)            AS total_gst,
                COALESCE(SUM(l.qty),      0)            AS total_units
            FROM sales_invoice_header h
            LEFT JOIN sales_invoice_line l ON l.invoice_no = h.invoice_no
            {filter_where}
        """, inner_params).fetchone()

        total_count = int(kpi_row['total_invoices'] or 0)
        total_pages = (total_count + per_page - 1) // per_page
        stats = {
            'total_invoices':  total_count,
            'total_customers': int(kpi_row['total_customers'] or 0),
            'total_revenue':   round(float(kpi_row['total_revenue'] or 0), 2),
            'total_gst':       round(float(kpi_row['total_gst']     or 0), 2),
            'total_units':     int(kpi_row['total_units']    or 0),
        }

        # === 2. PAGINATED invoice numbers — SQL LIMIT/OFFSET, never load all rows ===
        page_params = inner_params + [per_page, offset]
        paginated_invoice_nos = [
            row['invoice_no'] for row in conn.execute(f"""
                SELECT DISTINCT h.invoice_no
                FROM sales_invoice_header h
                {filter_where}
                ORDER BY h.invoice_date DESC, h.invoice_no DESC
                LIMIT ? OFFSET ?
            """, page_params).fetchall()
        ]

        # === 3. FETCH headers + lines only for this page's invoices ===
        invoices = {}
        if paginated_invoice_nos:
            placeholders = ','.join(['?'] * len(paginated_invoice_nos))

            for hdr in conn.execute(f"""
                SELECT h.invoice_no, h.invoice_date, h.customer_id,
                       c.customer_code, h.legend_id
                FROM sales_invoice_header h
                LEFT JOIN customers c ON c.customer_id = h.customer_id
                WHERE h.invoice_no IN ({placeholders})
            """, paginated_invoice_nos).fetchall():
                invoices[hdr['invoice_no']] = {
                    'header': dict(hdr),
                    'lines':  [],
                    'totals': {'total_amt': 0, 'gst_amt': 0, 'qty': 0}
                }

            for line in conn.execute(f"""
                SELECT l.invoice_no, l.line_no, l.product_id,
                       p.sku_no, p.hem_name, l.qty, l.total_amt, l.gst_amt
                FROM sales_invoice_line l
                LEFT JOIN products p ON p.product_id = l.product_id
                WHERE l.invoice_no IN ({placeholders})
                ORDER BY l.invoice_no, l.line_no
            """, paginated_invoice_nos).fetchall():
                inv = line['invoice_no']
                if inv in invoices:
                    invoices[inv]['lines'].append(dict(line))
                    invoices[inv]['totals']['total_amt'] += line['total_amt'] or 0
                    invoices[inv]['totals']['gst_amt']   += line['gst_amt']   or 0
                    invoices[inv]['totals']['qty']        += line['qty']       or 0

            # Restore sort order from paginated list
            invoices = {k: invoices[k] for k in paginated_invoice_nos if k in invoices}

        # === 4. TREND — only needs header + line, no products/customers join ===
        trend_rows = conn.execute(f"""
            SELECT substr(h.invoice_date, 1, 7)  AS month,
                   COALESCE(SUM(l.total_amt), 0) AS revenue
            FROM sales_invoice_header h
            LEFT JOIN sales_invoice_line l ON l.invoice_no = h.invoice_no
            {filter_where}
            GROUP BY month
            ORDER BY month
        """, inner_params).fetchall()
        trend_labels = [r['month'] or 'Unknown' for r in trend_rows]
        trend_data   = [round(float(r['revenue'] or 0), 2) for r in trend_rows]

        # === 5. Reference data for form dropdowns ===
        customers = conn.execute(
            "SELECT customer_id, customer_code FROM customers ORDER BY customer_code"
        ).fetchall()
        products = conn.execute(
            "SELECT DISTINCT product_id, sku_no, hem_name FROM products ORDER BY hem_name"
        ).fetchall()

    return render_template("dashboard.html",
        invoices=invoices,
        total_revenue=stats['total_revenue'],
        total_gst=stats['total_gst'],
        invoice_count=stats['total_invoices'],
        total_qty=stats['total_units'],
        inventory=products,
        customers=customers,
        current_page=page,
        total_pages=total_pages,
        search=search,
        start_date=start_date,
        end_date=end_date,
        trend_labels=trend_labels,
        trend_data=trend_data,
        role=session.get("role"))

@app.route("/create-invoice", methods=["POST"])
@require_staff
def create_invoice():
    """
    Create a new sales invoice with header and line items.
    Performs extensive server-side validation on all fields.
    """
    # Get form data from POST request
    invoice_no = request.form.get("invoice_no", "").strip()
    invoice_date = request.form.get("invoice_date", "").strip()
    customer_id = request.form.get("customer_id", "").strip()
    legend_id = request.form.get("legend_id", "SGP").strip()
    product_id = request.form.get("product_id", "").strip()
    
    # === EXTENSIVE SERVER-SIDE VALIDATION ===
    # Even though client-side validation exists, always validate on server
    
    # Validate invoice number (required, min 3 characters)
    if not invoice_no or len(invoice_no) < 3:
        flash("Invoice number is required and must be at least 3 characters!", "danger")
        return redirect(url_for("dashboard"))
    
    # Validate invoice date (required, no future dates)
    if not invoice_date:
        flash("Invoice date is required!", "danger")
        return redirect(url_for("dashboard"))
    try:
        parsed_date = datetime.strptime(invoice_date, "%Y-%m-%d").date()
        if parsed_date > date.today():
            flash("Invoice date cannot be in the future!", "danger")
            return redirect(url_for("dashboard"))
    except ValueError:
        flash("Invalid date format!", "danger")
        return redirect(url_for("dashboard"))
    
    # Validate customer selection (required)
    if not customer_id:
        flash("Customer selection is required!", "danger")
        return redirect(url_for("dashboard"))
    
    # Validate product selection (required)
    if not product_id:
        flash("Product selection is required!", "danger")
        return redirect(url_for("dashboard"))
    
    # Validate quantity (must be positive integer)
    try:
        qty = int(request.form.get("qty", 0))
        if qty <= 0:
            flash("Quantity must be greater than 0!", "danger")
            return redirect(url_for("dashboard"))
    except ValueError:
        flash("Invalid quantity value!", "danger")
        return redirect(url_for("dashboard"))
    
    # Validate total amount (must be non-negative number)
    try:
        total_amt = float(request.form.get("total_amt", 0))
        if total_amt < 0:
            flash("Total amount cannot be negative!", "danger")
            return redirect(url_for("dashboard"))
    except ValueError:
        flash("Invalid total amount value!", "danger")
        return redirect(url_for("dashboard"))
    
    # Validate GST amount (must be non-negative number)
    try:
        gst_amt = float(request.form.get("gst_amt", 0))
        if gst_amt < 0:
            flash("GST amount cannot be negative!", "danger")
            return redirect(url_for("dashboard"))
    except ValueError:
        flash("Invalid GST amount value!", "danger")
        return redirect(url_for("dashboard"))
    
            # === INSERT INVOICE INTO DATABASE ===
    try:
        # Use context manager (with statement) to ensure proper commit
        with get_db() as conn:
            # Check if invoice number already exists (prevent duplicates)
            existing = conn.execute("SELECT 1 FROM sales_invoice_header WHERE invoice_no = ?", (invoice_no,)).fetchone()
            if existing:
                flash(f"Invoice {invoice_no} already exists!", "danger")
                print(f"❌ Invoice {invoice_no} already exists!")
                return redirect(url_for("dashboard"))

            # Resolve customer_code → customer_id integer
            # The form submits customer_code text; we need the integer FK
            cust_row = conn.execute(
                "SELECT customer_id FROM customers WHERE customer_code = ? COLLATE NOCASE",
                (customer_id,)
            ).fetchone()
            if cust_row:
                resolved_customer_id = cust_row['customer_id']
            else:
                # Customer doesn't exist yet — create it on the fly
                cur = conn.execute(
                    "INSERT INTO customers (customer_code) VALUES (?)", (customer_id.upper(),)
                )
                resolved_customer_id = cur.lastrowid
                print(f"✅ New customer created: {customer_id} → id {resolved_customer_id}")

            print(f"📝 Inserting invoice {invoice_no}...")
            print(f"   Date: {invoice_date}")
            print(f"   Customer: {customer_id} (id={resolved_customer_id})")
            print(f"   Legend: {legend_id}")
            print(f"   Product ID: {product_id}")
            print(f"   Qty: {qty}")
            print(f"   Total: {total_amt}")
            print(f"   GST: {gst_amt}")

            # Insert invoice header with resolved integer customer_id
            conn.execute(
                "INSERT INTO sales_invoice_header (invoice_no, invoice_date, customer_id, legend_id) VALUES (?, ?, ?, ?)",
                (invoice_no, invoice_date, resolved_customer_id, legend_id)
            )
            print(f"✅ Header inserted")
            
            # Insert first line item (line_no = 1)
            conn.execute("INSERT INTO sales_invoice_line (invoice_no, line_no, product_id, qty, total_amt, gst_amt) VALUES (?, 1, ?, ?, ?, ?)",
                        (invoice_no, product_id, qty, total_amt, gst_amt))
            print(f"✅ Line item inserted")
            
            # Commit is automatic when exiting the 'with' block successfully
            conn.commit()
            print(f"✅ COMMITTED to database")
        
        # Verify it was saved (using fresh connection)
        with get_db() as verify_conn:
            verify = verify_conn.execute("SELECT * FROM sales_invoice_header WHERE invoice_no = ?", (invoice_no,)).fetchone()
            
            if verify:
                print(f"✅✅✅ VERIFIED: Invoice {invoice_no} is in database!")
                flash(f"Invoice {invoice_no} created successfully!", "success")
            else:
                print(f"❌❌❌ VERIFICATION FAILED: Invoice {invoice_no} NOT in database after commit!")
                flash(f"Invoice {invoice_no} creation failed - not saved!", "danger")
            
    except Exception as e:
        print(f"❌ Create invoice error: {e}")
        print(f"   Error type: {type(e).__name__}")
        import traceback
        traceback.print_exc()
        flash(f"Error creating invoice: {str(e)}", "danger")
    
    return redirect(url_for("dashboard"))

@app.route("/delete-invoice/<invoice_no>", methods=["POST"])
@csrf.exempt
@require_staff
def delete_invoice(invoice_no):
    """
    Delete an invoice and all its line items.
    Cascades deletion: line items first, then header.
    Returns JSON response for AJAX handling.
    """
    print("=" * 70)
    print(f"🔥 DELETE REQUEST for invoice: '{invoice_no}'")
    print(f"   Type: {type(invoice_no)}")
    print(f"   Length: {len(invoice_no)}")
    print(f"   Repr: {repr(invoice_no)}")
    print("=" * 70)
    
    try:
        with get_db() as conn:
            # Check if invoice exists first
            print(f"🔍 Searching for invoice '{invoice_no}' in database...")
            existing = conn.execute("SELECT * FROM sales_invoice_header WHERE invoice_no = ?", (invoice_no,)).fetchone()
            
            if not existing:
                print(f"❌ Invoice '{invoice_no}' NOT FOUND in database")
                
                # Show all invoices for debugging
                all_inv = conn.execute("SELECT invoice_no FROM sales_invoice_header LIMIT 10").fetchall()
                print(f"📋 First 10 invoices in DB:")
                for inv in all_inv:
                    print(f"   - '{inv[0]}'")
                
                return jsonify({
                    'success': False,
                    'message': f'Invoice {invoice_no} not found in database'
                }), 404
            
            print(f"✅ Invoice found! Proceeding with deletion...")
            
            # Delete line items first (to satisfy foreign key constraints)
            deleted_lines = conn.execute("DELETE FROM sales_invoice_line WHERE invoice_no=?", (invoice_no,))
            print(f"   Deleted {deleted_lines.rowcount} line items")
            
            # Then delete the header
            deleted_header = conn.execute("DELETE FROM sales_invoice_header WHERE invoice_no=?", (invoice_no,))
            print(f"   Deleted {deleted_header.rowcount} header rows")
            
            conn.commit()
            print(f"✅ Successfully deleted invoice '{invoice_no}'")
        
        return jsonify({
            'success': True,
            'message': f'Invoice {invoice_no} deleted successfully'
        })
        
    except Exception as e:
        print(f"❌ Delete error: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({
            'success': False,
            'message': f'Error deleting invoice: {str(e)}'
        }), 500

@app.route("/update-invoice/<invoice_no>", methods=["POST"])
@csrf.exempt
@require_staff
def update_invoice(invoice_no):
    """
    Update an existing invoice and its line items.
    Accepts JSON payload with invoice header and line items.
    
    Expected JSON structure:
    {
        "invoice_date": "2024-01-15",
        "customer_id": 1,
        "legend_id": "SGP",
        "lines": [
            {
                "line_no": 1,
                "product_id": 5,
                "qty": 10,
                "total_amt": 150.00,
                "gst_amt": 12.00
            },
            ...
        ]
    }
    """
    try:
        # Get JSON data from request
        data = request.get_json()
        
        if not data:
            return jsonify({
                'success': False, 
                'message': 'No data provided'
            }), 400
        
        # === VALIDATE REQUIRED FIELDS ===
        if not data.get('invoice_date'):
            return jsonify({'success': False, 'message': 'Invoice date is required'}), 400

        try:
            parsed_date = datetime.strptime(data['invoice_date'], "%Y-%m-%d").date()
            if parsed_date > date.today():
                return jsonify({'success': False, 'message': 'Invoice date cannot be in the future'}), 400
        except ValueError:
            return jsonify({'success': False, 'message': 'Invalid date format'}), 400

        if not data.get('customer_id'):
            return jsonify({'success': False, 'message': 'Customer is required'}), 400
        
        if not data.get('lines') or len(data['lines']) == 0:
            return jsonify({'success': False, 'message': 'At least one line item is required'}), 400
        
        # === VALIDATE LINE ITEMS ===
        for i, line in enumerate(data['lines']):
            # Validate product_id
            if not line.get('product_id'):
                return jsonify({'success': False, 'message': f'Line {i+1}: Product is required'}), 400
            
            # Validate quantity
            try:
                qty = int(line.get('qty', 0))
                if qty < 1:
                    return jsonify({'success': False, 'message': f'Line {i+1}: Quantity must be at least 1'}), 400
            except (ValueError, TypeError):
                return jsonify({'success': False, 'message': f'Line {i+1}: Invalid quantity'}), 400
            
            # Validate total amount
            try:
                total_amt = float(line.get('total_amt', 0))
                if total_amt < 0:
                    return jsonify({'success': False, 'message': f'Line {i+1}: Total amount cannot be negative'}), 400
            except (ValueError, TypeError):
                return jsonify({'success': False, 'message': f'Line {i+1}: Invalid total amount'}), 400
            
            # Validate GST amount
            try:
                gst_amt = float(line.get('gst_amt', 0))
                if gst_amt < 0:
                    return jsonify({'success': False, 'message': f'Line {i+1}: GST amount cannot be negative'}), 400
            except (ValueError, TypeError):
                return jsonify({'success': False, 'message': f'Line {i+1}: Invalid GST amount'}), 400
        
        # === UPDATE DATABASE ===
        with get_db() as conn:
            # Check if invoice exists
            existing = conn.execute("SELECT 1 FROM sales_invoice_header WHERE invoice_no = ?", (invoice_no,)).fetchone()
            if not existing:
                return jsonify({
                    'success': False,
                    'message': f'Invoice {invoice_no} not found'
                }), 404
            
            # Update invoice header
            conn.execute("""
                UPDATE sales_invoice_header 
                SET invoice_date = ?, 
                    customer_id = ?, 
                    legend_id = ?
                WHERE invoice_no = ?
            """, (
                data['invoice_date'],
                data['customer_id'],
                data.get('legend_id', ''),
                invoice_no
            ))
            
            # Delete all existing line items for this invoice
            conn.execute("DELETE FROM sales_invoice_line WHERE invoice_no = ?", (invoice_no,))
            
            # Insert new line items
            for line in data['lines']:
                conn.execute("""
                    INSERT INTO sales_invoice_line (
                        invoice_no, 
                        line_no, 
                        product_id, 
                        qty, 
                        total_amt, 
                        gst_amt
                    )
                    VALUES (?, ?, ?, ?, ?, ?)
                """, (
                    invoice_no,
                    line['line_no'],
                    line['product_id'],
                    line['qty'],
                    line['total_amt'],
                    line['gst_amt']
                ))
            
            conn.commit()
        
        print(f"✅ Updated invoice {invoice_no}")
        return jsonify({
            'success': True,
            'message': 'Invoice updated successfully'
        })
        
    except Exception as e:
        print(f"❌ Update invoice error: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({
            'success': False,
            'message': f'Server error: {str(e)}'
        }), 500

# === MARKET ANALYSIS ROUTES ===

def generate_ai_insights(kpis, top_products, top_customers, trend_data):
    """
    Generate AI-powered insights and recommendations using Groq API.
    Falls back to None if API is unavailable or fails.
    """
    if not groq_client:
        return None
    
    try:
        # Prepare data summary for AI (with safe checks for empty data)
        top_product_share = (top_products[0]['revenue'] / kpis['revenue'] * 100) if top_products and kpis['revenue'] > 0 else 0
        top_customer_share = (top_customers[0]['revenue'] / kpis['revenue'] * 100) if top_customers and kpis['revenue'] > 0 else 0
        
        # Build product and customer details safely
        if top_products:
            product_detail = f"{top_products[0]['hem_name']} (SGD {top_products[0]['revenue']:.2f}, {top_product_share:.1f}% of revenue)"
        else:
            product_detail = "N/A (no product data available)"
        
        if top_customers:
            customer_detail = f"{top_customers[0]['customer_code']} (SGD {top_customers[0]['revenue']:.2f}, {top_customer_share:.1f}% of revenue, {top_customers[0]['orders']} orders)"
        else:
            customer_detail = "N/A (no customer data available)"
        
        data_summary = f"""
Sales Performance Data:
- Total Revenue: SGD {kpis['revenue']:.2f}
- Total Orders: {kpis['orders']}
- Units Sold: {kpis['units']:.2f}
- Average Order Value: SGD {kpis['aov']:.2f}
- GST Collected: SGD {kpis['gst']:.2f}

Top Product: {product_detail}
Top Customer: {customer_detail}

Revenue Trend: {len(trend_data['labels'])} months of data
"""

        # Call Groq API
        response = groq_client.chat.completions.create(
            model="llama-3.3-70b-versatile",  # Updated model (llama-3.1 was decommissioned)
            messages=[
                {
                    "role": "system",
                    "content": "You are a business analyst. Provide CONCISE, actionable insights. Each insight should be 1-2 SHORT sentences max. Be direct and specific with numbers."
                },
                {
                    "role": "user",
                    "content": f"""Analyze this sales data and provide:
1. SIX key strategic insights (1-2 SHORT sentences each, max 25 words)
2. Five specific, actionable recommendations (2-3 sentences each, max 40 words)

{data_summary}

Format your response as JSON:
{{
  "insights": [
    {{"title": "Short Title (2-4 words)", "description": "One concise sentence with a key metric or finding."}},
    ... (6 total)
  ],
  "recommendations": [
    {{"title": "Action Title (3-5 words)", "description": "Specific action with numbers/targets."}},
    ... (5 total)
  ]
}}

Be BRIEF and SPECIFIC. Focus on numbers and actionable insights."""
                }
            ],
            temperature=0.3,  # Lower temperature for more consistent output
            max_tokens=2000
        )
        
        # Parse AI response
        ai_text = response.choices[0].message.content
        
        # Try to extract JSON from response
        import re
        json_match = re.search(r'\{.*\}', ai_text, re.DOTALL)
        if json_match:
            ai_insights = json.loads(json_match.group())
            return ai_insights
        else:
            return None
            
    except Exception as e:
        print(f"⚠️ Groq API error: {e}")
        return None

@app.route("/market-analysis")
@require_staff
def market_analysis():
    """
    Market analysis page with comprehensive business intelligence.
    Features:
    - KPIs (revenue, orders, units sold, average order value, GST)
    - Monthly revenue trend visualization
    - Top 10 products by revenue
    - Top 10 customers by revenue
    - Filtering by date range and legend (region/entity)
    """
    # Get filter parameters from URL
    start = request.args.get("start", "").strip()
    end = request.args.get("end", "").strip()
    legend = request.args.get("legend", "").strip()

    with get_db() as conn:
        # === VERIFY SALES TABLES EXIST ===
        # Check if required tables have data before proceeding
        try:
            conn.execute("SELECT 1 FROM sales_invoice_header LIMIT 1;").fetchone()
            conn.execute("SELECT 1 FROM sales_invoice_line LIMIT 1;").fetchone()
        except Exception as e:
            # Return error page if tables don't exist or are empty
            return render_template("market_analysis.html", role=session.get("role"),
                error_message=f"Sales tables not found or empty. Error: {str(e)}",
                legends=[], selected={"start": start, "end": end, "legend": legend},
                kpis={"revenue": 0, "orders": 0, "units": 0, "aov": 0, "gst": 0},
                trend_labels=[], trend_revenue=[], top_products=[], top_customers=[])

        # === GET AVAILABLE LEGENDS FOR FILTER ===
        # Legends represent different regions or business entities
        try:
            legends = [r["legend_id"] for r in conn.execute(
                "SELECT DISTINCT legend_id FROM sales_invoice_header WHERE legend_id IS NOT NULL AND legend_id != '' ORDER BY legend_id"
            ).fetchall()]
        except Exception as e:
            legends = []

        # === SET DEFAULT DATE RANGE IF NOT PROVIDED ===
        # Default to last 365 days of data
        try:
            # Get the min and max dates from the database
            max_date_row = conn.execute("SELECT MAX(invoice_date) AS m FROM sales_invoice_header WHERE invoice_date IS NOT NULL").fetchone()
            min_date_row = conn.execute("SELECT MIN(invoice_date) AS m FROM sales_invoice_header WHERE invoice_date IS NOT NULL").fetchone()
            max_date = max_date_row["m"] if max_date_row else None
            min_date = min_date_row["m"] if min_date_row else None
            
            # Set end date to most recent invoice if not provided
            if not end and max_date:
                end = max_date
            
            # Set start date to 365 days before end date
            if not start and end:
                start_row = conn.execute("SELECT date(?, '-365 day') AS d", (end,)).fetchone()
                start = start_row["d"] if start_row else min_date or ""
            elif not start and min_date:
                start = min_date
        except Exception as e:
            # Fallback to current date if database query fails
            if not end:
                end = datetime.now().strftime("%Y-%m-%d")
            if not start:
                start = (datetime.now() - timedelta(days=365)).strftime("%Y-%m-%d")

        # === BUILD WHERE CLAUSE FOR FILTERING ===
        where = "WHERE h.invoice_date >= ? AND h.invoice_date <= ?"
        params = [start, end]

        # Add legend filter if specified
        if legend:
            where += " AND h.legend_id = ?"
            params.append(legend)

        try:
            # === CALCULATE KEY PERFORMANCE INDICATORS ===
            # Deduplicate lines first via subquery (DISTINCT on invoice_no + line_no)
            # to prevent double-counting if any line rows were inserted more than once.
            kpi_row = conn.execute(f"""
                SELECT COALESCE(SUM(lines.total_amt), 0) AS revenue,
                       COALESCE(SUM(lines.gst_amt),   0) AS gst,
                       COUNT(DISTINCT lines.invoice_no) AS orders,
                       COALESCE(SUM(lines.qty),        0) AS units
                FROM (
                    SELECT DISTINCT l.invoice_no, l.line_no,
                           l.total_amt, l.gst_amt, l.qty
                    FROM sales_invoice_header h
                    JOIN sales_invoice_line l ON l.invoice_no = h.invoice_no
                    {where}
                ) AS lines
            """, params).fetchone()

            revenue = float(kpi_row["revenue"] or 0)
            gst     = float(kpi_row["gst"]     or 0)
            orders  = int(kpi_row["orders"]    or 0)
            units   = float(kpi_row["units"]   or 0)
            aov     = (revenue / orders) if orders else 0

            kpis = {
                "revenue": round(revenue, 2),
                "gst":     round(gst,     2),
                "orders":  orders,
                "units":   round(units,   2),
                "aov":     round(aov,     2)
            }

            # === GET MONTHLY REVENUE TREND ===
            # Deduplicate lines before grouping by month.
            trend_rows = conn.execute(f"""
                SELECT lines.ym,
                       COALESCE(SUM(lines.total_amt), 0) AS revenue
                FROM (
                    SELECT DISTINCT l.invoice_no, l.line_no,
                           substr(h.invoice_date, 1, 7) AS ym,
                           l.total_amt
                    FROM sales_invoice_header h
                    JOIN sales_invoice_line l ON l.invoice_no = h.invoice_no
                    {where}
                ) AS lines
                GROUP BY lines.ym
                ORDER BY lines.ym
            """, params).fetchall()

            trend_labels  = [r["ym"] for r in trend_rows if r["ym"]]
            trend_revenue = [float(r["revenue"] or 0) for r in trend_rows if r["ym"]]

            # === GET TOP 10 PRODUCTS BY REVENUE ===
            # Deduplicate at (invoice_no, line_no) level before aggregating per product.
            top_products_rows = conn.execute(f"""
                SELECT lines.product_id,
                       p.sku_no,
                       COALESCE(p.hem_name, 'Unknown') AS hem_name,
                       COALESCE(SUM(lines.total_amt), 0) AS revenue,
                       COALESCE(SUM(lines.qty),       0) AS units
                FROM (
                    SELECT DISTINCT l.invoice_no, l.line_no,
                           l.product_id, l.total_amt, l.qty
                    FROM sales_invoice_header h
                    JOIN sales_invoice_line l ON l.invoice_no = h.invoice_no
                    {where}
                ) AS lines
                LEFT JOIN products p ON p.product_id = lines.product_id
                GROUP BY lines.product_id, p.sku_no, hem_name
                ORDER BY revenue DESC
                LIMIT 10
            """, params).fetchall()

            top_products = [{
                "product_id": r["product_id"],
                "sku_no":     r["sku_no"],
                "hem_name":   r["hem_name"],
                "revenue":    round(float(r["revenue"] or 0), 2),
                "units":      round(float(r["units"]   or 0), 2)
            } for r in top_products_rows]

            # === GET TOP 10 CUSTOMERS BY REVENUE ===
            # Deduplicate at (invoice_no, line_no) level before aggregating per customer.
            top_customers_rows = conn.execute(f"""
                SELECT lines.customer_id,
                       COALESCE(c.customer_code, CAST(lines.customer_id AS TEXT)) AS customer_code,
                       COALESCE(SUM(lines.total_amt),      0) AS revenue,
                       COUNT(DISTINCT lines.invoice_no)      AS orders
                FROM (
                    SELECT DISTINCT l.invoice_no, l.line_no,
                           h.customer_id, l.total_amt
                    FROM sales_invoice_header h
                    JOIN sales_invoice_line l ON l.invoice_no = h.invoice_no
                    {where}
                ) AS lines
                LEFT JOIN customers c ON c.customer_id = lines.customer_id
                GROUP BY lines.customer_id, customer_code
                ORDER BY revenue DESC
                LIMIT 10
            """, params).fetchall()

            top_customers = [{
                "customer_id":   r["customer_id"],
                "customer_code": r["customer_code"],
                "revenue":       round(float(r["revenue"] or 0), 2),
                "orders":        int(r["orders"] or 0)
            } for r in top_customers_rows]

        except Exception as e:
            # If any query fails, log the error and return empty data
            print(f"Database query error: {e}")
            import traceback
            traceback.print_exc()
            return render_template("market_analysis.html", role=session.get("role"),
                error_message=f"Query error: {str(e)}", legends=legends,
                selected={"start": start, "end": end, "legend": legend},
                kpis={"revenue": 0, "orders": 0, "units": 0, "aov": 0, "gst": 0},
                trend_labels=[], trend_revenue=[], top_products=[], top_customers=[], ai_insights=None)

    # Generate AI insights (optional, falls back gracefully if unavailable)
    ai_insights = generate_ai_insights(
        kpis=kpis,
        top_products=top_products,
        top_customers=top_customers,
        trend_data={"labels": trend_labels, "revenue": trend_revenue}
    )

    # Render market analysis page with all calculated data
    return render_template("market_analysis.html", role=session.get("role"), error_message="",
        legends=legends, selected={"start": start, "end": end, "legend": legend},
        kpis=kpis, trend_labels=trend_labels, trend_revenue=trend_revenue,
        top_products=top_products, top_customers=top_customers, ai_insights=ai_insights)

@app.route("/real-time-analytics")
@require_staff
def real_time_analytics():
    """Real-time analytics dashboard for monitoring current business metrics."""
    return render_template("real_time_analytics.html", role=session.get("role"))

@app.route("/logout")
def logout():
    """Clear user session and redirect to customer cart page."""
    session.clear()
    return redirect(url_for("cart"))

# === APPLICATION ENTRY POINT ===
if __name__ == "__main__":
    app.run(debug=True)  # Run Flask development server with debug mode enabled