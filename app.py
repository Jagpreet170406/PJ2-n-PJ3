import sqlite3
import os
import json
from functools import wraps
from flask import Flask, render_template, request, redirect, url_for, session, flash, jsonify
from flask_wtf.csrf import CSRFProtect
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
    """Shopping cart checkout page"""
    return render_template("checkout.html", role=session.get("role", "customer"))

@app.route("/process-payment", methods=["POST"])
def process_payment():
    """Process cart checkout payment via JSON request"""
    data = request.get_json()

    if not data:
        return jsonify({"success": False, "message": "No data received"})

    cart_items = data.get('cart', [])
    payment_method = data.get('payment_method', 'Credit Card')
    total_amount = data.get('total_amount', 0)
    fulfillment = data.get('fulfillment', 'pickup')
    fulfillment_date = data.get('fulfillment_date', 'Not Specified')

    if not cart_items:
        return jsonify({"success": False, "message": "Cart is empty"})

    try:
        with get_db() as conn:
            conn.execute(
                "INSERT INTO transactions (username, payment_type, amount) VALUES (?, ?, ?)",
                (session.get("username", "Guest"), f"{payment_method} ({fulfillment})", total_amount)
            )
            conn.commit()

        return jsonify({"success": True, "message": "Payment successful"})

    except Exception as e:
        print(f"Payment error: {e}")
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
    with get_db() as conn:
        products = conn.execute("SELECT * FROM inventory LIMIT 100").fetchall()
    return render_template("inventory.html", products=products, role=session.get("role"))

@app.route("/dashboard")
@require_staff
def dashboard():
    return render_template("dashboard.html", role=session.get("role"))

# --------------------
# MARKET ANALYSIS (REAL DATA)
# --------------------
@app.route("/market-analysis")
@require_staff
def market_analysis():
    # Filters (GET params)
    start = request.args.get("start", "").strip()
    end = request.args.get("end", "").strip()
    legend = request.args.get("legend", "").strip()

    with get_db() as conn:
        # Check if tables exist
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

        # Get legends
        try:
            legends = [r["legend_code"] for r in conn.execute(
                "SELECT DISTINCT legend_code FROM sales_invoice_header WHERE legend_code IS NOT NULL AND legend_code != '' ORDER BY legend_code"
            ).fetchall()]
        except Exception as e:
            print(f"Error fetching legends: {e}")
            legends = []

        # Get date range
        try:
            max_date_row = conn.execute("SELECT MAX(invoice_date) AS m FROM sales_invoice_header WHERE invoice_date IS NOT NULL").fetchone()
            min_date_row = conn.execute("SELECT MIN(invoice_date) AS m FROM sales_invoice_header WHERE invoice_date IS NOT NULL").fetchone()
            
            max_date = max_date_row["m"] if max_date_row else None
            min_date = min_date_row["m"] if min_date_row else None
            
            # Set defaults
            if not end and max_date:
                end = max_date
            if not start and end:
                start_row = conn.execute("SELECT date(?, '-365 day') AS d", (end,)).fetchone()
                start = start_row["d"] if start_row else min_date or ""
            elif not start and min_date:
                start = min_date
                
        except Exception as e:
            print(f"Error with date logic: {e}")
            # Fallback to today
            from datetime import datetime, timedelta
            if not end:
                end = datetime.now().strftime("%Y-%m-%d")
            if not start:
                start = (datetime.now() - timedelta(days=365)).strftime("%Y-%m-%d")

        # Build WHERE clause
        where = "WHERE h.invoice_date >= ? AND h.invoice_date <= ?"
        params = [start, end]

        if legend:
            where += " AND h.legend_code = ?"
            params.append(legend)

        try:
            # KPIs
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

            # Trend by month
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

            # Top products
            top_products_rows = conn.execute(f"""
                SELECT
                    l.sku_no,
                    COALESCE(p.hem_name, l.sku_no) AS hem_name,
                    COALESCE(SUM(l.total_amt), 0) AS revenue,
                    COALESCE(SUM(l.qty), 0) AS units
                FROM sales_invoice_header h
                JOIN sales_invoice_line l ON l.invoice_no = h.invoice_no
                LEFT JOIN sales_product p ON p.sku_no = l.sku_no
                {where}
                GROUP BY l.sku_no, hem_name
                ORDER BY revenue DESC
                LIMIT 10
            """, params).fetchall()

            top_products = [{
                "sku_no": r["sku_no"],
                "hem_name": r["hem_name"],
                "revenue": round(float(r["revenue"] or 0), 2),
                "units": round(float(r["units"] or 0), 2)
            } for r in top_products_rows]

            # Top customers
            top_customers_rows = conn.execute(f"""
                SELECT
                    h.customer_id,
                    COALESCE(c.customer_code, CAST(h.customer_id AS TEXT)) AS customer_code,
                    COALESCE(SUM(l.total_amt), 0) AS revenue,
                    COUNT(DISTINCT h.invoice_no) AS orders
                FROM sales_invoice_header h
                JOIN sales_invoice_line l ON l.invoice_no = h.invoice_no
                LEFT JOIN sales_customer c ON c.customer_id = h.customer_id
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
