from flask import Flask, render_template, request, redirect, url_for, session, abort
import sqlite3
from werkzeug.security import generate_password_hash, check_password_hash

app = Flask(__name__)
app.secret_key = "change-this-in-production"
DB = "database.db"


STAFF_ROLES = {"employee", "admin", "superowner"}
ADMIN_ROLES = {"admin", "superowner"}


# --------------------
# Database Initialization
# --------------------
def init_db():
    """Initialize database with users table for RBAC."""
    conn = sqlite3.connect(DB)
    c = conn.cursor()

    c.execute(
        """
        CREATE TABLE IF NOT EXISTS users (
            username TEXT PRIMARY KEY,
            password TEXT NOT NULL,
            role TEXT NOT NULL,
            active INTEGER DEFAULT 1
        )
        """
    )

    # Create superowner account if not exists
    c.execute("SELECT 1 FROM users WHERE role='superowner' LIMIT 1")
    if not c.fetchone():
        c.execute(
            "INSERT INTO users(username, password, role, active) VALUES (?, ?, ?, 1)",
            ("superowner", "changeme123", "superowner"),
        )

    conn.commit()
    conn.close()


# --------------------
# Helpers
# --------------------
def check_user_credentials(username, password):
    """Verify user credentials and return role if valid."""
    conn = sqlite3.connect(DB)
    c = conn.cursor()
    c.execute(
        "SELECT role, active FROM users WHERE username=? AND password=?",
        (username, password),
    )
    result = c.fetchone()
    conn.close()

    if result and result[1] == 1:
        return result[0]
    return None


def require_roles(*allowed_roles):
    """Route decorator: restrict access by role."""
    allowed = set(allowed_roles)

    def decorator(fn):
        @wraps(fn)
        def wrapper(*args, **kwargs):
            role = session.get("role", "customer")
            if role not in allowed:
                return redirect(url_for("staff_login"))
            return fn(*args, **kwargs)

        return wrapper

    return decorator


# --------------------
# CUSTOMER PAGES
# --------------------
@app.route("/")
def home():
    """Landing page. Restrict customers to cart."""
    session.setdefault("role", "customer")
    role = session.get("role")
    
    if role == "customer":
        return redirect(url_for("cart"))
        
    return render_template("home.html", role=role)


@app.route("/cart", methods=["GET", "POST"])
def cart():
    """Customer cart page (public access)."""
    session.setdefault("role", "customer")
    role = session.get("role", "customer")

    # If staff tries to access customer cart, send them to dashboard
    # EXCEPTION: Superowner is allowed to view everything
    if role in STAFF_ROLES and role != "superowner":
        return redirect(url_for("dashboard"))

    # NOTE: Your existing cart/session DB functions were removed here
    # because your snippet references tables like 'cart' and 'products'
    # that may or may not exist in DB init. Add them back when ready.

    return render_template("cart.html", role="customer")


@app.route("/contact")
def contact():
    session.setdefault("role", "customer")
    return render_template("contact.html", role=session.get("role"))

#KPI
@app.context_processor
def inject_defaults():
    return {
        "kpis": []
    }

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
            session["role"] = role
            session["username"] = username
            return redirect(url_for("dashboard"))

        return render_template("staff_login.html", error="Invalid credentials or account disabled")

    # If already staff, go dashboard
    if session.get("role") in STAFF_ROLES:
        return redirect(url_for("dashboard"))

    return render_template("staff_login.html", error=None)


@app.route("/logout")
def logout():
    """Logout and go back to customer home."""
    session.clear()
    session["role"] = "customer"
    return redirect(url_for("home"))


# --------------------
# STAFF PAGES
# --------------------
@app.route("/dashboard")
@require_roles("employee", "staff", "admin", "superowner")
def dashboard():
    return render_template("dashboard.html", role=session.get("role"), username=session.get("username"))


@app.route("/analysis")
@require_roles("employee","staff", "admin", "superowner")
def analysis():
    return render_template("analysis.html", role=session.get("role"))


@app.route("/market-analysis")
@require_roles("employee","staff", "admin", "superowner")
def market_analysis():
    return render_template("market_analysis.html", role=session.get("role"))


@app.route("/real-time-analytics")
@require_roles("employee","staff", "admin", "superowner")
def real_time_analytics():
    return render_template("real_time_analytics.html", role=session.get("role"))


# --------------------
# ADMIN / SUPEROWNER /employee 
# --------------------
@app.route("/inventory")
@require_roles("employee","admin", "superowner")
def inventory():
    return render_template("inventory.html", role=session.get("role"))


# --------------------
# SUPEROWNER ONLY - USER MANAGEMENT
# --------------------
@app.route("/manage-users", methods=["GET", "POST"])
@require_roles("superowner")
def manage_users():
    conn = sqlite3.connect(DB)
    c = conn.cursor()
    message = ""

    if request.method == "POST":
        action = request.form.get("action")

        if action == "add":
            username = request.form.get("username", "").strip()
            password = request.form.get("password", "").strip()
            role = request.form.get("role", "").strip()

            try:
                c.execute(
                    "INSERT INTO users(username, password, role, active) VALUES (?, ?, ?, 1)",
                    (username, password, role),
                )
                conn.commit()
                message = f"User '{username}' added as {role}."
            except sqlite3.IntegrityError:
                message = f"Error: Username '{username}' already exists."
            except Exception as e:
                message = f"Error: {e}"

        elif action == "toggle":
            username = request.form.get("username", "").strip()
            c.execute("SELECT active FROM users WHERE username=?", (username,))
            result = c.fetchone()
            if result:
                new_status = 0 if result[0] == 1 else 1
                c.execute("UPDATE users SET active=? WHERE username=?", (new_status, username))
                conn.commit()
                message = f"User '{username}' {'enabled' if new_status == 1 else 'disabled'}."
            else:
                message = f"User '{username}' not found."

        elif action == "delete":
            username = request.form.get("username", "").strip()
            if username == session.get("username"):
                message = "Error: Cannot delete your own account."
            else:
                c.execute("DELETE FROM users WHERE username=?", (username,))
                conn.commit()
                message = f"User '{username}' deleted."

        elif action == "change_role":
            username = request.form.get("username", "").strip()
            new_role = request.form.get("new_role", "").strip()
            c.execute("UPDATE users SET role=? WHERE username=?", (new_role, username))
            conn.commit()
            message = f"User '{username}' role changed to {new_role}."

    c.execute("SELECT username, role, active FROM users ORDER BY role, username")
    users = c.fetchall()
    conn.close()

    return render_template("manage_users.html", users=users, message=message)


# --------------------
# SUPEROWNER CODE VIEWER
# --------------------
@app.route("/code")
@require_roles("superowner")
def code_viewer():
    """List files and view content."""
    import os
    
    file_path = request.args.get("file")
    base_dir = os.path.dirname(os.path.abspath(__file__))
    
    # If a file is requested, read it
    content = None
    if file_path:
        # Security: Prevent directory traversal (basic check)
        full_path = os.path.join(base_dir, file_path)
        if os.path.commonprefix([os.path.abspath(full_path), base_dir]) == base_dir:
            try:
                if os.path.isfile(full_path):
                    with open(full_path, "r", encoding="utf-8") as f:
                        content = f.read()
                else:
                    content = "Error: File not found or is a directory."
            except Exception as e:
                content = f"Error reading file: {e}"
        else:
            content = "Error: Access denied."
            
    # List files in current directory (recursive or simple? start simple)
    files = []
    for root, _, filenames in os.walk(base_dir):
        # Exclude venv and __pycache__ for clarity
        if "venv" in root or "__pycache__" in root or ".git" in root:
            continue
            
        for name in filenames:
            rel_path = os.path.relpath(os.path.join(root, name), base_dir)
            files.append(rel_path)
            
    files.sort()
    
    return render_template("code_viewer.html", files=files, content=content, current_file=file_path)


# --------------------
# SUPEROWNER DB PANEL (Optional)
# --------------------
@app.route("/db-panel", methods=["GET", "POST"])
@require_roles("superowner")
def db_panel():
    conn = sqlite3.connect(DB)
    c = conn.cursor()
    message = ""

    if request.method == "POST":
        query = request.form.get("query", "")
        try:
            c.execute(query)
            conn.commit()
            message = "Query executed successfully."
        except Exception as e:
            message = f"Error: {e}"

    c.execute("SELECT name FROM sqlite_master WHERE type='table';")
    tables = [t[0] for t in c.fetchall()]

    data = {}
    for table_name in tables:
        try:
            c.execute(f"SELECT * FROM {table_name} LIMIT 50")
            data[table_name] = c.fetchall()
        except Exception:
            data[table_name] = []

    conn.close()
    return render_template("db_panel.html", tables=data, message=message)


# --------------------
# IGNORE FAVICON
# --------------------
@app.route("/favicon.ico")
def favicon():
    return "", 204


# --------------------
# RUN SERVER
# --------------------
if __name__ == "__main__":
    init_db()
    app.run(debug=True)
