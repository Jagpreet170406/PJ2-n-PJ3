import sqlite3
import os
from functools import wraps
from flask import Flask, render_template, request, redirect, url_for, session, flash, abort
from werkzeug.security import generate_password_hash, check_password_hash

# --------------------
# APP CONFIG
# --------------------
app = Flask(__name__)
app.secret_key = "change-this-in-production-use-a-long-random-string"

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB = os.path.join(BASE_DIR, "database.db")

STAFF_ROLES = {"employee", "admin", "superowner"}
ADMIN_ROLES = {"admin", "superowner"}

# --------------------
# DB INIT
# --------------------
def init_db():
    conn = sqlite3.connect(DB)
    c = conn.cursor()
    # Updated Schema to match your database.py (added user_id)
    c.execute("""
    CREATE TABLE IF NOT EXISTS users (
        user_id INTEGER PRIMARY KEY AUTOINCREMENT,
        username TEXT UNIQUE NOT NULL,
        password_hash TEXT NOT NULL,
        role TEXT NOT NULL,
        active INTEGER DEFAULT 1
    )
    """)
    # Bootstrap superowner if none exists
    c.execute("SELECT 1 FROM users WHERE role='superowner'")
    if not c.fetchone():
        hashed_pw = generate_password_hash("changeme123")
        c.execute(
            "INSERT INTO users (username, password_hash, role, active) VALUES (?, ?, ?, 1)",
            ("superowner", hashed_pw, "superowner")
        )
    conn.commit()
    conn.close()

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
# PUBLIC / CUSTOMER
# --------------------
@app.route("/")
def root():
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
    if request.method == "POST":
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "").strip()
        role = check_user_credentials(username, password)
        
        if role:
            session["username"] = username
            session["role"] = role
            # Superowner goes to User Management, others to Home
            return redirect(url_for("manage_users" if role == "superowner" else "home"))
        
        flash("Invalid credentials or account disabled.", "danger")
        return render_template("staff_login.html", error="Invalid credentials")

    if session.get("role") in STAFF_ROLES:
        return redirect(url_for("home"))
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
            c = conn.cursor()
            if action == "add":
                password = request.form.get("password", "").strip()
                role = request.form.get("role", "employee")
                try:
                    # FIX: Explicitly naming columns so user_id auto-increments correctly
                    c.execute("""
                        INSERT INTO users (username, password_hash, role, active) 
                        VALUES (?, ?, ?, 1)
                    """, (username, generate_password_hash(password), role))
                    message = f"User '{username}' added."
                except sqlite3.IntegrityError:
                    message = "Error: Username already exists."
            
            elif action == "toggle":
                c.execute("UPDATE users SET active = 1 - active WHERE username=?", (username,))
                message = "User status updated."
                
            elif action == "delete":
                if username == session.get("username"):
                    message = "Error: Cannot delete yourself."
                else:
                    c.execute("DELETE FROM users WHERE username=?", (username,))
                    message = "User deleted."
                    
            elif action == "change_role":
                new_role = request.form.get("new_role")
                c.execute("UPDATE users SET role=? WHERE username=?", (new_role, username))
                message = "Role updated."
            conn.commit()

    with get_db() as conn:
        users = conn.execute("SELECT username, role, active FROM users ORDER BY role, username").fetchall()
    
    return render_template("manage_users.html", users=users, message=message)

# --------------------
# SUPEROWNER: CODE VIEWER
# --------------------
@app.route("/code")
@require_roles("superowner")
def code_viewer():
    file_path = request.args.get("file")
    content = None
    if file_path:
        full_path = os.path.abspath(os.path.join(BASE_DIR, file_path))
        if full_path.startswith(BASE_DIR) and os.path.isfile(full_path):
            try:
                with open(full_path, "r", encoding="utf-8") as f:
                    content = f.read()
            except Exception as e:
                content = f"Error reading file: {e}"
        else:
            content = "Access denied or file not found."

    files = []
    for root, dirs, filenames in os.walk(BASE_DIR):
        dirs[:] = [d for d in dirs if d not in ["venv", "__pycache__", ".git", "static"]]
        for name in filenames:
            files.append(os.path.relpath(os.path.join(root, name), BASE_DIR))

    return render_template("code_viewer.html", files=sorted(files), content=content, current_file=file_path)

# --------------------
# SUPEROWNER: DB PANEL
# --------------------
@app.route("/db-panel", methods=["GET", "POST"])
@require_roles("superowner")
def db_panel():
    message = ""
    query_results = None
    
    if request.method == "POST":
        query = request.form.get("query")
        try:
            with get_db() as conn:
                c = conn.cursor()
                c.execute(query)
                if query.strip().lower().startswith("select"):
                    query_results = c.fetchall()
                conn.commit()
                message = "Query executed successfully."
        except Exception as e:
            message = f"SQL Error: {e}"

    with get_db() as conn:
        tables_list = conn.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()
        data = {}
        for row in tables_list:
            table_name = row['name']
            data[table_name] = conn.execute(f"SELECT * FROM {table_name} LIMIT 10").fetchall()

    return render_template("db_panel.html", tables=data, message=message, query_results=query_results)

# --------------------
# RUN
# --------------------
if __name__ == "__main__":
    init_db()
    app.run(debug=True, port=5000)

