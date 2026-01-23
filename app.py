import sqlite3
import os
from functools import wraps
from flask import Flask, render_template, request, redirect, url_for, session, flash
from werkzeug.security import generate_password_hash, check_password_hash

app = Flask(__name__)
app.secret_key = "chinhon_secret_key"

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB = os.path.join(BASE_DIR, "database.db")

# --------------------
# DATABASE HELPER
# --------------------
def get_db():
    conn = sqlite3.connect(DB)
    conn.row_factory = sqlite3.Row  # Crucial for 25k records to access by column name
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
    # 1. Get Parameters for Big Data Handling
    page = request.args.get('page', 1, type=int)
    search_query = request.args.get('search', '')
    category_filter = request.args.get('category', '')
    
    per_page = 24  # Don't load 25k at once!
    offset = (page - 1) * per_page

    with get_db() as conn:
        # 2. Get categories for the sidebar (Distinct list)
        categories = conn.execute("SELECT DISTINCT category FROM inventory WHERE category IS NOT NULL").fetchall()
        
        # 3. Build Dynamic Query
        base_query = " FROM inventory WHERE qty > 0"
        params = []

        if search_query:
            base_query += " AND (hem_name LIKE ? OR sup_part_no LIKE ?)"
            params.extend([f'%{search_query}%', f'%{search_query}%'])
        
        if category_filter:
            base_query += " AND category = ?"
            params.append(category_filter)

        # 4. Count total for Pagination Logic
        total_count = conn.execute("SELECT COUNT(*)" + base_query, params).fetchone()[0]
        total_pages = (total_count // per_page) + (1 if total_count % per_page > 0 else 0)

        # 5. Fetch only the 24 records for this specific page
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

@app.route("/contact")
def contact():
    return render_template("contact.html", role="customer")

@app.route("/process-payment", methods=["POST"])
def process_payment():
    pay_method = request.form.get("payment_method", "Credit Card")
    total_val = request.form.get("total_amount")
    
    with get_db() as conn:
        # Logs into your 'transactions' table
        conn.execute("INSERT INTO transactions (username, payment_type, amount) VALUES (?,?,?)",
                     (session.get("username", "Guest"), pay_method, total_val))
        conn.commit()
    
    flash(f"Payment successful! SGD {total_val} received.", "success")
    return redirect(url_for('cart'))

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
    # Admin view can also use pagination later if needed, 
    # but for now, we'll keep it simple or use same logic as cart
    with get_db() as conn:
        products = conn.execute("SELECT * FROM inventory LIMIT 100").fetchall() # Limit for safety
    return render_template("inventory.html", products=products, role=session.get("role"))

@app.route("/dashboard")
@require_staff
def dashboard():
    return render_template("dashboard.html", role=session.get("role"))

@app.route("/market-analysis")
@require_staff
def market_analysis():
    return render_template("market_analysis.html", role=session.get("role"))

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