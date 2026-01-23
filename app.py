import sqlite3
import os
from functools import wraps
from flask import Flask, render_template, request, redirect, url_for, session, flash
from werkzeug.security import generate_password_hash, check_password_hash

# --------------------
# APP CONFIG
# --------------------
app = Flask(__name__)
app.secret_key = "very-secret-key-lah"

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB = os.path.join(BASE_DIR, "database.db")

STAFF_ROLES = {"employee", "admin", "superowner"}

# --------------------
# DB INIT (Payment Table Added)
# --------------------
def init_db():
    with sqlite3.connect(DB) as conn:
        # Users Table
        conn.execute("""
        CREATE TABLE IF NOT EXISTS users (
            user_id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            password_hash TEXT NOT NULL,
            role TEXT NOT NULL,
            active INTEGER DEFAULT 1
        )
        """)
        # Transactions Table (Teacher Requirement)
        conn.execute("""
        CREATE TABLE IF NOT EXISTS transactions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT,
            payment_type TEXT,
            masked_card TEXT, 
            amount REAL,
            timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
        )
        """)
        conn.commit()

# --------------------
# HELPERS
# --------------------
def get_db():
    conn = sqlite3.connect(DB)
    conn.row_factory = sqlite3.Row  
    return conn

def check_user_credentials(username, password):
    with get_db() as conn:
        row = conn.execute(
            "SELECT password_hash, role, active FROM users WHERE username=?",
            (username,)
        ).fetchone()
        
    if row and row['active'] == 1 and check_password_hash(row['password_hash'], password):
        return row['role']
    return None

def require_roles(*roles):
    allowed = set(roles)
    def decorator(fn):
        @wraps(fn)
        def wrapper(*args, **kwargs):
            if session.get("role") not in allowed:
                return redirect(url_for("staff_login"))
            return fn(*args, **kwargs)
        return wrapper
    return decorator

# --------------------
# PUBLIC & CHECKOUT ROUTES
# --------------------
@app.route("/")
def root():
    if session.get("role") in STAFF_ROLES:
        return redirect(url_for("home"))
    return redirect(url_for("cart"))

@app.route("/cart")
def cart():
    return render_template("cart.html", role=session.get("role", "customer"))

@app.route("/process-payment", methods=["POST"])
def process_payment():
    pay_method = request.form.get("payment_method")
    card_num = request.form.get("card_number", "")
    
    # SECURE STORAGE: Masking the card (Show this to your teacher!)
    # We never store the full card. We store the provider and the last 4 digits.
    masked_info = f"**** **** **** {card_num[-4:]}" if len(card_num) >= 4 else "WALLET_PAY"
    
    username = session.get("username", "Guest")
    
    try:
        with get_db() as conn:
            conn.execute("""
                INSERT INTO transactions (username, payment_type, masked_card, amount) 
                VALUES (?, ?, ?, ?)
            """, (username, pay_method, masked_info, 420.69)) # Placeholder amount
            conn.commit()
        flash(f"Payment successful via {pay_method}! Your parts are on the way.", "success")
    except Exception as e:
        flash(f"Payment Error: {e}", "danger")
        
    return redirect(url_for('cart'))

@app.route("/contact")
def contact():
    return "<h1>Contact Page</h1><a href='/'>Back Home</a>"

@app.route("/about")
def about():
    return "<h1>About Page</h1><a href='/'>Back Home</a>"

# --------------------
# STAFF AUTH
# --------------------
@app.route("/employee-login")
def employee_login():
    return redirect(url_for('staff_login'))

@app.route("/staff-login", methods=["GET", "POST"])
def staff_login():
    if session.get("role") in STAFF_ROLES:
        return redirect(url_for("home"))

    if request.method == "POST":
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "").strip()
        role = check_user_credentials(username, password)

        if role:
            session.clear()
            session["username"] = username
            session["role"] = role
            return redirect(url_for("manage_users" if role == "superowner" else "home"))
        
        flash("Invalid credentials.", "danger")
    return render_template("staff_login.html")

@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("staff_login"))

# --------------------
# STAFF PAGES
# --------------------
@app.route("/home")
@require_roles("employee", "admin", "superowner")
def home():
    return render_template("home.html", role=session.get("role"), username=session.get("username"))

@app.route("/inventory")
@require_roles("employee", "admin", "superowner")
def inventory():
    return render_template("inventory.html")

@app.route("/dashboard")
@require_roles("employee", "admin", "superowner")
def dashboard():
    return "<h1>Dashboard Page</h1><a href='/home'>Back</a>"

@app.route("/market-analysis")
@require_roles("admin", "superowner")
def market_analysis():
    return "<h1>Market Analysis</h1><a href='/home'>Back</a>"

@app.route("/real-time-analytics")
@require_roles("admin", "superowner")
def real_time_analytics():
    return "<h1>Real Time Analytics</h1><a href='/home'>Back</a>"

# --------------------
# SUPEROWNER: USER MGMT
# --------------------
@app.route("/manage-users", methods=["GET", "POST"])
@require_roles("superowner")
def manage_users():
    message = ""
    if request.method == "POST":
        action = request.form.get("action")
        username = request.form.get("username", "").strip()
        with get_db() as conn:
            if action == "add":
                pw, role = request.form.get("password"), request.form.get("role")
                try:
                    conn.execute("INSERT INTO users (username, password_hash, role, active) VALUES (?, ?, ?, 1)",
                                 (username, generate_password_hash(pw), role))
                    conn.commit()
                except Exception as e: message = str(e)
            elif action == "delete":
                conn.execute("DELETE FROM users WHERE username=?", (username,))
                conn.commit()
    
    with get_db() as conn:
        users = conn.execute("SELECT username, role, active FROM users").fetchall()
    return render_template("manage_users.html", users=users, message=message)

if __name__ == "__main__":
    init_db()
    app.run(debug=True, port=5000)