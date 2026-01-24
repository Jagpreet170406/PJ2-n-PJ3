import sqlite3
import os
import json
from functools import wraps
from flask import Flask, render_template, request, redirect, url_for, session, flash, jsonify
from flask_wtf.csrf import CSRFProtect, generate_csrf
from werkzeug.security import generate_password_hash, check_password_hash

app = Flask(__name__)
app.secret_key = "chinhon_secret_key"

# Enable CSRF Protection
csrf = CSRFProtect(app)

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB = os.path.join(BASE_DIR, "database.db")

# --------------------
# DATABASE HELPER
# --------------------
def get_db():
    conn = sqlite3.connect(DB)
    conn.row_factory = sqlite3.Row
    return conn

# Initialize the database tables
def init_db():
    with get_db() as conn:
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
        
        # Sales & Price Optimization Dashboard Table
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
        conn.commit()

init_db()

# --------------------
# CONTEXT PROCESSOR - Makes csrf_token available to all templates
# --------------------
@app.context_processor
def inject_csrf_token():
    return dict(csrf_token=generate_csrf)

# --------------------
# SECURITY DECORATOR
# --------------------
def require_staff(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if session.get("role") not in ["employee", "admin", "superowner"]:
            return redirect(url_for('cart'))
        return f(*args, **kwargs)
    return decorated_function

# --------------------
# CUSTOMER ROUTES
# --------------------
@app.route("/")
def root():
    role = session.get("role")
    if role in ["employee", "admin", "superowner"]:
        return redirect(url_for("home"))
    return redirect(url_for("cart"))

@app.route("/cart")
def cart():
    page = request.args.get('page', 1, type=int)
    search_query = request.args.get('search', '')
    category_filter = request.args.get('category', '')

    per_page = 24
    offset = (page - 1) * per_page

    with get_db() as conn:
        categories = conn.execute("SELECT DISTINCT category FROM inventory WHERE category IS NOT NULL").fetchall()

        base_query = " FROM inventory WHERE qty > 0"
        params = []

        if search_query:
            base_query += " AND (hem_name LIKE ? OR sup_part_no LIKE ?)"
            params.extend([f'%{search_query}%', f'%{search_query}%'])

        if category_filter:
            base_query += " AND category = ?"
            params.append(category_filter)

        total_count = conn.execute("SELECT COUNT(*)" + base_query, params).fetchone()[0]
        total_pages = (total_count // per_page) + (1 if total_count % per_page > 0 else 0)

        final_query = "SELECT *" + base_query + " ORDER BY hem_name ASC LIMIT ? OFFSET ?"
        params.extend([per_page, offset])
        products = conn.execute(final_query, params).fetchall()

    return render_template("cart.html",
                           products=products,
                           categories=categories,
                           current_page=page,
                           total_pages=total_pages,
                           search_query=search_query,
                           category_filter=category_filter,
                           role=session.get("role", "customer"))

@app.route("/checkout")
def checkout():
    """Shopping cart checkout page - Cards now managed in browser localStorage"""
    return render_template("checkout.html", 
                           role=session.get("role", "customer"), 
                           user_cards=[])

@app.route("/process-payment", methods=["POST"])
@csrf.exempt
def process_payment():
    """Process cart checkout payment - Simplified, no card saving to DB"""
    data = request.get_json()

    if not data:
        return jsonify({"success": False, "message": "No data received"})

    cart_items = data.get('cart', [])
    payment_method = data.get('payment_method', 'Credit Card')
    total_amount = data.get('total_amount', 0)
    fulfillment = data.get('fulfillment', 'pickup')
    pickup_or_delivery_date = data.get('pickup_or_delivery_date', '')
    
    username = session.get("username", "Guest")

    if not cart_items:
        return jsonify({"success": False, "message": "Cart is empty"})

    try:
        with get_db() as conn:
            payment_label = f"{payment_method} ({fulfillment})"
            conn.execute(
                "INSERT INTO transactions (username, payment_type, amount) VALUES (?, ?, ?)",
                (username, payment_label, total_amount)
            )
            conn.commit()
            print(f"✅ Payment processed: {payment_label} - S${total_amount} for {username}")
        
        return jsonify({"success": True, "message": "Payment successful"})

    except Exception as e:
        print(f"❌ Payment error: {e}")
        return jsonify({"success": False, "message": str(e)})

@app.route("/order-success")
def order_success():
    """The 'Big Tick' confirmation page"""
    method = request.args.get('method', 'pickup')
    date = request.args.get('date', '')
    return render_template("order_success.html", method=method, date=date, role="customer")

@app.route("/contact")
def contact():
    return render_template("contact.html", role="customer")

# --------------------
# HIDDEN STAFF LOGIN
# --------------------
@app.route("/staff-login", methods=["GET", "POST"])
def staff_login():
    if session.get("role") in ["employee", "admin", "superowner"]:
        return redirect(url_for("home"))

    if request.method == "POST":
        u, p = request.form.get("username"), request.form.get("password")
        with get_db() as conn:
            user = conn.execute("SELECT * FROM users WHERE username=?", (u,)).fetchone()

        if user and check_password_hash(user['password_hash'], p):
            session.update({"username": u, "role": user['role']})
            return redirect(url_for("home"))
        flash("Invalid credentials", "danger")

    return render_template("staff_login.html", role="customer")

# --------------------
# PROTECTED STAFF ROUTES
# --------------------
@app.route("/home")
@require_staff
def home():
    return render_template("home.html", role=session.get("role"))

@app.route("/inventory")
@require_staff
def inventory():
    return render_template("inventory.html", role=session.get("role"))

# --------------------
# INVENTORY CRUD API ROUTES
# --------------------
@app.route("/api/inventory", methods=["GET"])
@csrf.exempt
@require_staff
def api_get_inventory():
    """Get all inventory items for the inventory management page"""
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
    """Create a new inventory item"""
    data = request.get_json()
    
    print(f"🔍 Received data: {data}")
    
    sup_part_no = (data.get('sup_part_no') or '').strip()
    hem_name = (data.get('hem_name') or '').strip()
    category = data.get('category', 'Lubricants')
    qty = int(data.get('qty', 0))
    sell_price = float(data.get('sell_price', 0))
    image_url = (data.get('image_url') or '').strip()
    
    print(f"📦 Creating product: name='{hem_name}', qty={qty}, price={sell_price}")
    
    if not hem_name:
        print(f"❌ Product name is empty! Received: '{hem_name}'")
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
            
            return jsonify({
                "success": True,
                "inventory_id": cursor.lastrowid,
                "message": "Product added successfully"
            })
    except Exception as e:
        print(f"❌ Error creating product: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({"success": False, "message": str(e)}), 500

@app.route("/api/inventory/<int:inventory_id>", methods=["PUT"])
@csrf.exempt
@require_staff
def api_update_inventory(inventory_id):
    """Update an existing inventory item"""
    data = request.get_json()
    
    print(f"🔍 Update - Received data: {data}")
    
    sup_part_no = (data.get('sup_part_no') or '').strip()
    hem_name = (data.get('hem_name') or '').strip()
    category = data.get('category', 'Lubricants')
    qty = int(data.get('qty', 0))
    sell_price = float(data.get('sell_price', 0))
    image_url = (data.get('image_url') or '').strip()
    
    print(f"📝 Updating product ID {inventory_id}: name='{hem_name}'")
    
    if not hem_name:
        print(f"❌ Product name is empty! Received: '{hem_name}'")
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
        import traceback
        traceback.print_exc()
        return jsonify({"success": False, "message": str(e)}), 500

@app.route("/api/inventory/<int:inventory_id>", methods=["DELETE"])
@csrf.exempt
@require_staff
def api_delete_inventory(inventory_id):
    """Delete an inventory item"""
    print(f"🗑️ Deleting product ID {inventory_id}")
    
    try:
        with get_db() as conn:
            conn.execute("DELETE FROM inventory WHERE inventory_id=?", (inventory_id,))
            conn.commit()
            
            print(f"✅ Product deleted (ID: {inventory_id})")
            
            return jsonify({"success": True, "message": "Product deleted successfully"})
    except Exception as e:
        print(f"❌ Error deleting product: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({"success": False, "message": str(e)}), 500

# --------------------
# ENTERPRISE SALES DASHBOARD (REAL DATA FROM 4 TABLES)
# --------------------
@app.route("/dashboard")
@require_staff
def dashboard():
    """Enterprise Sales Dashboard - Pulls from sales_invoice_header, sales_invoice_line, products, customers"""
    
    # Pagination
    page = request.args.get('page', 1, type=int)
    per_page = 50
    offset = (page - 1) * per_page
    
    # Filters
    search = request.args.get('search', '').strip()
    start_date = request.args.get('start_date', '').strip()
    end_date = request.args.get('end_date', '').strip()
    
    with get_db() as conn:
        # Build WHERE clause for filters
        where_clauses = []
        params = []
        
        if search:
            where_clauses.append("(h.invoice_no LIKE ? OR p.hem_name LIKE ? OR c.customer_code LIKE ?)")
            params.extend([f'%{search}%', f'%{search}%', f'%{search}%'])
        
        if start_date:
            where_clauses.append("h.invoice_date >= ?")
            params.append(start_date)
        
        if end_date:
            where_clauses.append("h.invoice_date <= ?")
            params.append(end_date)
        
        where_sql = " AND ".join(where_clauses) if where_clauses else "1=1"
        
        # KPI Calculations
        kpi_query = f"""
            SELECT 
                COUNT(DISTINCT h.invoice_no) as total_invoices,
                COUNT(DISTINCT h.customer_id) as total_customers,
                COALESCE(SUM(l.total_amt), 0) as total_revenue,
                COALESCE(SUM(l.gst_amt), 0) as total_gst,
                COALESCE(SUM(l.qty), 0) as total_units,
                COALESCE(AVG(l.total_amt), 0) as avg_line_value
            FROM sales_invoice_header h
            LEFT JOIN sales_invoice_line l ON h.invoice_no = l.invoice_no
            WHERE {where_sql}
        """
        
        stats_row = conn.execute(kpi_query, params).fetchone()
        
        stats = {
            'total_invoices': stats_row['total_invoices'] or 0,
            'total_customers': stats_row['total_customers'] or 0,
            'total_revenue': round(stats_row['total_revenue'] or 0, 2),
            'total_gst': round(stats_row['total_gst'] or 0, 2),
            'total_units': stats_row['total_units'] or 0,
            'avg_line_value': round(stats_row['avg_line_value'] or 0, 2)
        }
        
        # Get total count for pagination
        count_query = f"""
            SELECT COUNT(DISTINCT h.invoice_no) as cnt
            FROM sales_invoice_header h
            LEFT JOIN sales_invoice_line l ON h.invoice_no = l.invoice_no
            LEFT JOIN products p ON l.product_id = p.product_id
            LEFT JOIN customers c ON h.customer_id = c.customer_id
            WHERE {where_sql}
        """
        total_count = conn.execute(count_query, params).fetchone()['cnt']
        total_pages = (total_count // per_page) + (1 if total_count % per_page > 0 else 0)
        
        # Main data query with JOIN across all 4 tables
        data_query = f"""
            SELECT 
                h.invoice_no,
                h.invoice_date,
                h.customer_id,
                c.customer_code,
                h.legend_id,
                l.line_no,
                l.product_id,
                p.sku_no,
                p.hem_name,
                l.qty,
                l.total_amt,
                l.gst_amt
            FROM sales_invoice_header h
            LEFT JOIN sales_invoice_line l ON h.invoice_no = l.invoice_no
            LEFT JOIN products p ON l.product_id = p.product_id
            LEFT JOIN customers c ON h.customer_id = c.customer_id
            WHERE {where_sql}
            ORDER BY h.invoice_date DESC, h.invoice_no DESC
            LIMIT ? OFFSET ?
        """
        
        params_with_pagination = params + [per_page, offset]
        sales_data = conn.execute(data_query, params_with_pagination).fetchall()
        
        # Get unique customers and products for dropdowns
        customers = conn.execute("SELECT customer_id, customer_code FROM customers ORDER BY customer_code").fetchall()
        products = conn.execute("SELECT product_id, sku_no, hem_name FROM products ORDER BY hem_name LIMIT 100").fetchall()
        
        # Get sales trend data (monthly breakdown) - use same filters as main query
        trend_query = f"""
            SELECT 
                substr(h.invoice_date, 1, 7) as month,
                COALESCE(SUM(l.total_amt), 0) as revenue
            FROM sales_invoice_header h
            LEFT JOIN sales_invoice_line l ON h.invoice_no = l.invoice_no
            WHERE {where_sql}
            GROUP BY month
            ORDER BY month
        """
        trend_rows = conn.execute(trend_query, params).fetchall()
        trend_labels = [row['month'] if row['month'] else 'Unknown' for row in trend_rows]
        trend_data = [round(float(row['revenue']), 2) if row['revenue'] else 0 for row in trend_rows]
        
        print(f"📊 Trend Query: {trend_query}")
        print(f"📊 Trend Params: {params}")
        print(f"📊 Trend data: {len(trend_rows)} months")
        print(f"📊 Labels: {trend_labels[:10]}")
        print(f"📊 Data: {trend_data[:10]}")
    
    return render_template("dashboard.html", 
                           sales_data=sales_data,
                           stats=stats,
                           customers=customers,
                           products=products,
                           current_page=page,
                           total_pages=total_pages,
                           search=search,
                           start_date=start_date,
                           end_date=end_date,
                           trend_labels=trend_labels,
                           trend_data=trend_data,
                           role=session.get("role"))

# --------------------
# DASHBOARD CRUD OPERATIONS
# --------------------
@app.route("/create-invoice", methods=["POST"])
@require_staff
def create_invoice():
    """Create new invoice with line items"""
    invoice_no = request.form.get("invoice_no")
    invoice_date = request.form.get("invoice_date")
    customer_id = request.form.get("customer_id")
    legend_id = request.form.get("legend_id", "SGP")
    
    product_id = request.form.get("product_id")
    qty = int(request.form.get("qty", 1))
    total_amt = float(request.form.get("total_amt", 0))
    gst_amt = float(request.form.get("gst_amt", 0))
    
    try:
        with get_db() as conn:
            # Insert header
            conn.execute("""
                INSERT INTO sales_invoice_header (invoice_no, invoice_date, customer_id, legend_id)
                VALUES (?, ?, ?, ?)
            """, (invoice_no, invoice_date, customer_id, legend_id))
            
            # Insert line item
            conn.execute("""
                INSERT INTO sales_invoice_line (invoice_no, line_no, product_id, qty, total_amt, gst_amt)
                VALUES (?, 1, ?, ?, ?, ?)
            """, (invoice_no, product_id, qty, total_amt, gst_amt))
            
            conn.commit()
        
        flash("Invoice created successfully!", "success")
    except Exception as e:
        flash(f"Error creating invoice: {str(e)}", "danger")
        print(f"❌ Create invoice error: {e}")
    
    return redirect(url_for("dashboard"))

@app.route("/update-invoice-line", methods=["POST"])
@require_staff
def update_invoice_line():
    """Update invoice line item"""
    invoice_no = request.form.get("invoice_no")
    line_no = int(request.form.get("line_no"))
    qty = int(request.form.get("qty"))
    total_amt = float(request.form.get("total_amt"))
    gst_amt = float(request.form.get("gst_amt"))
    
    try:
        with get_db() as conn:
            conn.execute("""
                UPDATE sales_invoice_line
                SET qty=?, total_amt=?, gst_amt=?
                WHERE invoice_no=? AND line_no=?
            """, (qty, total_amt, gst_amt, invoice_no, line_no))
            conn.commit()
        
        flash("Invoice line updated successfully!", "success")
    except Exception as e:
        flash(f"Error updating invoice line: {str(e)}", "danger")
        print(f"❌ Update error: {e}")
    
    return redirect(url_for("dashboard"))

@app.route("/delete-invoice/<invoice_no>", methods=["POST"])
@require_staff
def delete_invoice(invoice_no):
    """Delete invoice and all its line items"""
    try:
        with get_db() as conn:
            conn.execute("DELETE FROM sales_invoice_line WHERE invoice_no=?", (invoice_no,))
            conn.execute("DELETE FROM sales_invoice_header WHERE invoice_no=?", (invoice_no,))
            conn.commit()
        
        flash("Invoice deleted successfully!", "success")
    except Exception as e:
        flash(f"Error deleting invoice: {str(e)}", "danger")
        print(f"❌ Delete error: {e}")
    
    return redirect(url_for("dashboard"))

# --------------------
# MARKET ANALYSIS (REAL DATA)
# --------------------
@app.route("/market-analysis")
@require_staff
def market_analysis():
    start = request.args.get("start", "").strip()
    end = request.args.get("end", "").strip()
    legend = request.args.get("legend", "").strip()

    with get_db() as conn:
        try:
            conn.execute("SELECT 1 FROM sales_invoice_header LIMIT 1;").fetchone()
            conn.execute("SELECT 1 FROM sales_invoice_line LIMIT 1;").fetchone()
        except Exception as e:
            return render_template(
                "market_analysis.html",
                role=session.get("role"),
                error_message=f"Sales tables not found or empty. Error: {str(e)}",
                legends=[],
                selected={"start": start, "end": end, "legend": legend},
                kpis={"revenue": 0, "orders": 0, "units": 0, "aov": 0, "gst": 0},
                trend_labels=[],
                trend_revenue=[],
                top_products=[],
                top_customers=[]
            )

        try:
            legends = [r["legend_id"] for r in conn.execute(
                "SELECT DISTINCT legend_id FROM sales_invoice_header WHERE legend_id IS NOT NULL AND legend_id != '' ORDER BY legend_id"
            ).fetchall()]
        except Exception as e:
            print(f"Error fetching legends: {e}")
            legends = []

        try:
            max_date_row = conn.execute("SELECT MAX(invoice_date) AS m FROM sales_invoice_header WHERE invoice_date IS NOT NULL").fetchone()
            min_date_row = conn.execute("SELECT MIN(invoice_date) AS m FROM sales_invoice_header WHERE invoice_date IS NOT NULL").fetchone()
            
            max_date = max_date_row["m"] if max_date_row else None
            min_date = min_date_row["m"] if min_date_row else None
            
            if not end and max_date:
                end = max_date
            if not start and end:
                start_row = conn.execute("SELECT date(?, '-365 day') AS d", (end,)).fetchone()
                start = start_row["d"] if start_row else min_date or ""
            elif not start and min_date:
                start = min_date
                
        except Exception as e:
            print(f"Error with date logic: {e}")
            from datetime import datetime, timedelta
            if not end:
                end = datetime.now().strftime("%Y-%m-%d")
            if not start:
                start = (datetime.now() - timedelta(days=365)).strftime("%Y-%m-%d")

        where = "WHERE h.invoice_date >= ? AND h.invoice_date <= ?"
        params = [start, end]

        if legend:
            where += " AND h.legend_id = ?"
            params.append(legend)

        try:
            kpi_row = conn.execute(f"""
                SELECT
                    COALESCE(SUM(l.total_amt), 0) AS revenue,
                    COALESCE(SUM(l.gst_amt), 0) AS gst,
                    COUNT(DISTINCT h.invoice_no) AS orders,
                    COALESCE(SUM(l.qty), 0) AS units
                FROM sales_invoice_header h
                JOIN sales_invoice_line l ON l.invoice_no = h.invoice_no
                {where}
            """, params).fetchone()

            revenue = float(kpi_row["revenue"] or 0)
            gst = float(kpi_row["gst"] or 0)
            orders = int(kpi_row["orders"] or 0)
            units = float(kpi_row["units"] or 0)
            aov = (revenue / orders) if orders else 0

            kpis = {
                "revenue": round(revenue, 2),
                "gst": round(gst, 2),
                "orders": orders,
                "units": round(units, 2),
                "aov": round(aov, 2)
            }

            trend_rows = conn.execute(f"""
                SELECT
                    substr(h.invoice_date, 1, 7) AS ym,
                    COALESCE(SUM(l.total_amt), 0) AS revenue
                FROM sales_invoice_header h
                JOIN sales_invoice_line l ON l.invoice_no = h.invoice_no
                {where}
                GROUP BY ym
                ORDER BY ym
            """, params).fetchall()

            trend_labels = [r["ym"] for r in trend_rows if r["ym"]]
            trend_revenue = [float(r["revenue"] or 0) for r in trend_rows if r["ym"]]

            top_products_rows = conn.execute(f"""
                SELECT
                    l.product_id,
                    p.sku_no,
                    COALESCE(p.hem_name, 'Unknown') AS hem_name,
                    COALESCE(SUM(l.total_amt), 0) AS revenue,
                    COALESCE(SUM(l.qty), 0) AS units
                FROM sales_invoice_header h
                JOIN sales_invoice_line l ON l.invoice_no = h.invoice_no
                LEFT JOIN products p ON p.product_id = l.product_id
                {where}
                GROUP BY l.product_id, p.sku_no, hem_name
                ORDER BY revenue DESC
                LIMIT 10
            """, params).fetchall()

            top_products = [{
                "product_id": r["product_id"],
                "sku_no": r["sku_no"],
                "hem_name": r["hem_name"],
                "revenue": round(float(r["revenue"] or 0), 2),
                "units": round(float(r["units"] or 0), 2)
            } for r in top_products_rows]

            top_customers_rows = conn.execute(f"""
                SELECT
                    h.customer_id,
                    COALESCE(c.customer_code, CAST(h.customer_id AS TEXT)) AS customer_code,
                    COALESCE(SUM(l.total_amt), 0) AS revenue,
                    COUNT(DISTINCT h.invoice_no) AS orders
                FROM sales_invoice_header h
                JOIN sales_invoice_line l ON l.invoice_no = h.invoice_no
                LEFT JOIN customers c ON c.customer_id = h.customer_id
                {where}
                GROUP BY h.customer_id, customer_code
                ORDER BY revenue DESC
                LIMIT 10
            """, params).fetchall()

            top_customers = [{
                "customer_id": r["customer_id"],
                "customer_code": r["customer_code"],
                "revenue": round(float(r["revenue"] or 0), 2),
                "orders": int(r["orders"] or 0)
            } for r in top_customers_rows]

        except Exception as e:
            print(f"Database query error: {e}")
            import traceback
            traceback.print_exc()
            return render_template(
                "market_analysis.html",
                role=session.get("role"),
                error_message=f"Query error: {str(e)}",
                legends=legends,
                selected={"start": start, "end": end, "legend": legend},
                kpis={"revenue": 0, "orders": 0, "units": 0, "aov": 0, "gst": 0},
                trend_labels=[],
                trend_revenue=[],
                top_products=[],
                top_customers=[]
            )

    return render_template(
        "market_analysis.html",
        role=session.get("role"),
        error_message="",
        legends=legends,
        selected={"start": start, "end": end, "legend": legend},
        kpis=kpis,
        trend_labels=trend_labels,
        trend_revenue=trend_revenue,
        top_products=top_products,
        top_customers=top_customers
    )

@app.route("/real-time-analytics")
@require_staff
def real_time_analytics():
    return render_template("real_time_analytics.html", role=session.get("role"))

@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("cart"))

if __name__ == "__main__":
    app.run(debug=True)