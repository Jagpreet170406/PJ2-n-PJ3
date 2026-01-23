import sqlite3
import os
from functools import wraps
from flask import Flask, render_template, request, redirect, url_for, session, flash, abort
from werkzeug.security import generate_password_hash, check_password_hash

# --------------------
# APP CONFIG
# --------------------
app = Flask(__name__)
app.secret_key = "very-secret-key-lah" # Change this for production

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB = os.path.join(BASE_DIR, "database.db")

STAFF_ROLES = {"employee", "admin", "superowner"}

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
                print(f"DEBUG: Access Denied to {fn.__name__}. Role: {session.get('role')}")
                return redirect(url_for("staff_login"))
            return fn(*args, **kwargs)
        return wrapper
    return decorator

# --------------------
# PUBLIC / CUSTOMER
# --------------------
@app.route("/")
def root():
    # If a staff is already logged in, go straight to home
    if session.get("role") in STAFF_ROLES:
        return redirect(url_for("home"))
    
    session.setdefault("role", "customer")
    return redirect(url_for("cart"))

@app.route("/cart")
def cart():
    role = session.get("role", "customer")
    can_edit = role in STAFF_ROLES
    return render_template("cart.html", role=role, can_edit=can_edit)

# --------------------
# STAFF AUTH
# --------------------
@app.route("/staff-login", methods=["GET", "POST"])
def staff_login():
    # If already logged in, skip the login page
    if session.get("role") in STAFF_ROLES:
        return redirect(url_for("home"))

    if request.method == "POST":
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "").strip()
        
        role = check_user_credentials(username, password)
        print(f"DEBUG: Login Attempt - User: {username}, Role Found: {role}")

        if role:
            session.clear() # Reset session to ensure clean login
            session["username"] = username
            session["role"] = role
            
            # Redirect logic
            if role == "superowner":
                return redirect(url_for("manage_users"))
            return redirect(url_for("home"))
        
        flash("Invalid credentials or account disabled.", "danger")
        
    return render_template("staff_login.html")

@app.route("/logout")
def logout():
    session.clear()
    session["role"] = "customer"
    return redirect(url_for("cart"))

# --------------------
# STAFF PAGES
# --------------------
@app.route("/home")
@require_roles("employee", "admin", "superowner")
def home():
    return render_template("home.html", role=session.get("role"), username=session.get("username"))

@app.route("/dashboard")
@require_roles("employee", "admin", "superowner")
def dashboard():
    return render_template("dashboard.html", role=session.get("role"))

@app.route("/inventory")
@require_roles("employee", "admin", "superowner")
def inventory():
    return render_template("inventory.html", role=session.get("role"))

# --------------------
# SUPEROWNER ONLY
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
                    message = f"User '{username}' added."
                except Exception as e:
                    message = f"Error: {e}"
            
            elif action == "delete":
                if username != session.get("username"):
                    conn.execute("DELETE FROM users WHERE username=?", (username,))
                    conn.commit()
                    message = "User deleted."
            
            elif action == "toggle":
                conn.execute("UPDATE users SET active = 1 - active WHERE username=?", (username,))
                conn.commit()
                message = "Status updated."

    with get_db() as conn:
        users = conn.execute("SELECT username, role, active FROM users").fetchall()
    return render_template("manage_users.html", users=users, message=message)

if __name__ == "__main__":
    app.run(debug=True, port=5000)