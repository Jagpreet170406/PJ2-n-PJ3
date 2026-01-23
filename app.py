from flask import Flask, render_template, request, redirect, url_for, session, abort
import sqlite3
import os
from functools import wraps
from werkzeug.security import generate_password_hash, check_password_hash

# --------------------
# APP CONFIG
# --------------------
app = Flask(__name__)
app.secret_key = "change-this-in-production"

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB = os.path.join(BASE_DIR, "database.db")

STAFF_ROLES = {"employee", "admin", "superowner"}
ADMIN_ROLES = {"admin", "superowner"}

# --------------------
# DB INIT (AUTH ONLY)
# --------------------
def init_db():
    conn = sqlite3.connect(DB)
    c = conn.cursor()

    c.execute("""
    CREATE TABLE IF NOT EXISTS users (
        username TEXT PRIMARY KEY,
        password_hash TEXT NOT NULL,
        role TEXT NOT NULL,
        active INTEGER DEFAULT 1
    )
    """)

    # Bootstrap superowner
    c.execute("SELECT 1 FROM users WHERE role='superowner'")
    if not c.fetchone():
        c.execute(
            "INSERT INTO users VALUES (?, ?, ?, 1)",
            ("superowner", generate_password_hash("changeme123"), "superowner")
        )

    conn.commit()
    conn.close()

# --------------------
# HELPERS
# --------------------
def get_db():
    return sqlite3.connect(DB)

def check_user_credentials(username, password):
    conn = get_db()
    c = conn.cursor()

    c.execute(
        "SELECT password_hash, role, active FROM users WHERE username=?",
        (username,)
    )
    row = c.fetchone()
    conn.close()

    if row and row[2] == 1 and check_password_hash(row[0], password):
        return row[1]
    return None

def require_roles(*roles):
    allowed = set(roles)

    def decorator(fn):
        @wraps(fn)
        def wrapper(*args, **kwargs):
            role = session.get("role")
            if role not in allowed:
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

@app.route("/cart", methods=["GET", "POST"])
def cart():
    role = session.get("role", "customer")
    session["role"] = role

    can_edit = role in STAFF_ROLES  # employees/admin/superowner

    return render_template(
        "cart.html",
        role=role,
        can_edit=can_edit
    )

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

            if role == "superowner":
                return redirect("/manage-users")
            elif role == "admin":
                return redirect("/inventory")
            else:
                return redirect("/dashboard")

        return render_template("staff_login.html", error="Invalid credentials")

    if session.get("role") in STAFF_ROLES:
        return redirect("/dashboard")

    return render_template("staff_login.html")

@app.route("/logout")
def logout():
    session.clear()
    session["role"] = "customer"
    return redirect("/cart")

# --------------------
# STAFF PAGES
# --------------------
@app.route("/dashboard")
@require_roles("employee", "admin", "superowner")
def dashboard():
    return render_template(
        "dashboard.html",
        role=session.get("role"),
        username=session.get("username")
    )

@app.route("/analysis")
@require_roles("employee", "admin", "superowner")
def analysis():
    return render_template("analysis.html", role=session.get("role"))

@app.route("/market-analysis")
@require_roles("employee", "admin", "superowner")
def market_analysis():
    return render_template("market_analysis.html", role=session.get("role"))

@app.route("/real-time-analytics")
@require_roles("employee", "admin", "superowner")
def real_time_analytics():
    return render_template("real_time_analytics.html", role=session.get("role"))

# --------------------
# INVENTORY
# --------------------
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
    conn = get_db()
    c = conn.cursor()
    message = ""

    if request.method == "POST":
        action = request.form.get("action")

        if action == "add":
            username = request.form.get("username")
            password = request.form.get("password")
            role = request.form.get("role")

            try:
                c.execute(
                    "INSERT INTO users VALUES (?, ?, ?, 1)",
                    (username, generate_password_hash(password), role)
                )
                conn.commit()
                message = "User created."
            except sqlite3.IntegrityError:
                message = "Username already exists."

        elif action == "toggle":
            username = request.form.get("username")
            c.execute("UPDATE users SET active = 1 - active WHERE username=?", (username,))
            conn.commit()
            message = "User status updated."

        elif action == "delete":
            username = request.form.get("username")
            if username == session.get("username"):
                message = "Cannot delete yourself."
            else:
                c.execute("DELETE FROM users WHERE username=?", (username,))
                conn.commit()
                message = "User deleted."

        elif action == "change_role":
            username = request.form.get("username")
            new_role = request.form.get("new_role")
            c.execute("UPDATE users SET role=? WHERE username=?", (new_role, username))
            conn.commit()
            message = "Role updated."

    c.execute("SELECT username, role, active FROM users ORDER BY role, username")
    users = c.fetchall()
    conn.close()

    return render_template("manage_users.html", users=users, message=message)

# --------------------
# SUPEROWNER: CODE VIEWER
# --------------------
@app.route("/code")
@require_roles("superowner")
def code_viewer():
    base_dir = BASE_DIR
    file_path = request.args.get("file")
    content = None

    if file_path:
        full_path = os.path.abspath(os.path.join(base_dir, file_path))
        if full_path.startswith(base_dir) and os.path.isfile(full_path):
            with open(full_path, "r", encoding="utf-8") as f:
                content = f.read()
        else:
            content = "Access denied."

    files = []
    for root, _, filenames in os.walk(base_dir):
        if any(x in root for x in ["venv", "__pycache__", ".git"]):
            continue
        for name in filenames:
            files.append(os.path.relpath(os.path.join(root, name), base_dir))

    return render_template(
        "code_viewer.html",
        files=sorted(files),
        content=content,
        current_file=file_path
    )

# --------------------
# SUPEROWNER: DB PANEL
# --------------------
@app.route("/db-panel", methods=["GET", "POST"])
@require_roles("superowner")
def db_panel():
    conn = get_db()
    c = conn.cursor()
    message = ""

    if request.method == "POST":
        query = request.form.get("query")
        try:
            c.execute(query)
            conn.commit()
            message = "Query executed."
        except Exception as e:
            message = str(e)

    c.execute("SELECT name FROM sqlite_master WHERE type='table'")
    tables = [t[0] for t in c.fetchall()]

    data = {}
    for table in tables:
        try:
            c.execute(f"SELECT * FROM {table} LIMIT 50")
            data[table] = c.fetchall()
        except Exception:
            data[table] = []

    conn.close()
    return render_template("db_panel.html", tables=data, message=message)

# --------------------
# FAVICON
# --------------------
@app.route("/favicon.ico")
def favicon():
    return "", 204

# --------------------
# RUN
# --------------------
if __name__ == "__main__":
    init_db()
    app.run(debug=True)
