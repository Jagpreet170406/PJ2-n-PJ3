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
# ROUTES
# --------------------
@app.route("/")
def root():
    role = session.get("role")
    if role in ["employee", "admin", "superowner"]:
        return redirect(url_for("home"))
    return redirect(url_for("cart"))

@app.route("/cart")
def cart():
    # Crucial: passing role='customer' if not logged in so navbar shows up
    return render_template("cart.html", role=session.get("role", "customer"))

@app.route("/process-payment", methods=["POST"])
def process_payment():
    pay_method = request.form.get("payment_method")
    card_num = request.form.get("card_number", "")
    total_val = request.form.get("total_amount")
    
    # Security Masking for Teacher
    masked = f"**** **** **** {card_num[-4:]}" if len(card_num) >= 4 else "WALLET_PAY"
    
    with get_db() as conn:
        conn.execute("INSERT INTO transactions (username, payment_type, masked_card, amount) VALUES (?,?,?,?)",
                     (session.get("username", "Guest"), pay_method, masked, total_val))
        conn.commit()
    
    flash(f"Payment successful via {pay_method}!", "success")
    return redirect(url_for('cart'))

@app.route("/home")
def home():
    if "role" not in session: return redirect(url_for("staff_login"))
    return render_template("home.html", role=session.get("role"))

# Placeholder routes to prevent navbar BuildErrors
@app.route("/inventory")
def inventory(): return render_template("inventory.html", role=session.get("role", "customer"))

@app.route("/dashboard")
def dashboard(): return "Dashboard"

@app.route("/market-analysis")
def market_analysis(): return "Analysis"

@app.route("/real-time-analytics")
def real_time_analytics(): return "Real-time"

@app.route("/contact")
def contact(): return "Contact Us"

@app.route("/employee-login")
def employee_login(): return redirect(url_for('staff_login'))

@app.route("/staff-login", methods=["GET", "POST"])
def staff_login():
    if request.method == "POST":
        u, p = request.form.get("username"), request.form.get("password")
        with get_db() as conn:
            user = conn.execute("SELECT * FROM users WHERE username=?", (u,)).fetchone()
        if user and check_password_hash(user['password_hash'], p):
            session.update({"username": u, "role": user['role']})
            return redirect(url_for("home"))
    return render_template("staff_login.html")

@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("cart"))

if __name__ == "__main__":
    init_db()
    app.run(debug=True)