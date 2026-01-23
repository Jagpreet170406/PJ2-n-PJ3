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
# DB INIT
# --------------------
def init_db():
    with sqlite3.connect(DB) as conn:
        conn.execute("CREATE TABLE IF NOT EXISTS users (id INTEGER PRIMARY KEY AUTOINCREMENT, username TEXT UNIQUE, password_hash TEXT, role TEXT, active INTEGER DEFAULT 1)")
        conn.execute("CREATE TABLE IF NOT EXISTS transactions (id INTEGER PRIMARY KEY AUTOINCREMENT, username TEXT, payment_type TEXT, masked_card TEXT, amount REAL, timestamp DATETIME DEFAULT CURRENT_TIMESTAMP)")
        conn.commit()

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
    return render_template("cart.html", role=session.get("role", "customer"))

@app.route("/contact")
def contact():
    return render_template("contact.html", role="customer")

@app.route("/process-payment", methods=["POST"])
def process_payment():
    pay_method = request.form.get("payment_method")
    card_num = request.form.get("card_number", "")
    total_val = request.form.get("total_amount")
    
    masked = f"**** **** **** {card_num[-4:]}" if len(card_num) >= 4 else "DIGITAL_PAY"
    
    with get_db() as conn:
        conn.execute("INSERT INTO transactions (username, payment_type, masked_card, amount) VALUES (?,?,?,?)",
                     (session.get("username", "Guest"), pay_method, masked, total_val))
        conn.commit()
    
    flash(f"Payment successful via {pay_method}!", "success")
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
# PROTECTED STAFF ROUTES (FIXED ENDPOINTS)
# --------------------
@app.route("/home")
@require_staff
def home():
    return render_template("home.html", role=session.get("role"))

@app.route("/inventory")
@require_staff
def inventory():
    return render_template("inventory.html", role=session.get("role"))

@app.route("/dashboard")
@require_staff
def dashboard():
    return render_template("dashboard.html", role=session.get("role"))

# FIXED: Endpoint matches url_for('market_analysis')
@app.route("/market-analysis")
@require_staff
def market_analysis():
    return render_template("analysis.html", role=session.get("role"))

# FIXED: Endpoint matches url_for('real_time_analytics')
@app.route("/real-time-analytics")
@require_staff
def real_time_analytics():
    return render_template("real_time.html", role=session.get("role"))

@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("cart"))

if __name__ == "__main__":
    init_db()
    app.run(debug=True)