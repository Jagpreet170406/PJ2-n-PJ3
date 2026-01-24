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

# Initialize the new table for saved cards if it doesn't exist
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
        conn.commit()

init_db()

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
    # No need to fetch cards from database anymore since they're in localStorage
    return render_template("checkout.html", 
                           role=session.get("role", "customer"), 
                           user_cards=[])  # Empty list - cards loaded from localStorage in frontend

@app.route("/process-payment", methods=["POST"])
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
            # Log transaction
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
    with get_db() as conn:
        products = conn.execute("SELECT * FROM inventory LIMIT 100").fetchall()
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