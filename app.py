from flask import Flask, render_template, session, redirect, url_for, request

app = Flask(__name__)
app.secret_key = "super-secret-key"  # required for sessions

# -------------------------
# Helper: role checker
# -------------------------
def role_required(allowed_roles):
    def decorator(func):
        def wrapper(*args, **kwargs):
            role = session.get("role")
            if role not in allowed_roles:
                return redirect(url_for("employee_login"))
            return func(*args, **kwargs)
        wrapper.__name__ = func.__name__
        return wrapper
    return decorator

# -------------------------
# Public routes
# -------------------------
@app.route('/')
def home():
    return render_template('home.html')

@app.route("/cart")
def cart():
    session["role"] = "customer"   # simulate customer role
    return render_template("cart.html")

@app.route("/employee-login")
def employee_login():
    return render_template("employee_login.html")

# -------------------------
# Login simulation
# -------------------------
@app.route("/login", methods=["POST"])
def login():
    role = request.form.get("role")

    if role in ["employee", "admin"]:
        session["role"] = role
        return redirect(url_for("dashboard"))

    return redirect(url_for("employee_login"))

# -------------------------
# Protected routes
# -------------------------
@app.route("/dashboard")
@role_required(["employee", "admin"])
def dashboard():
    return render_template("dashboard.html")

@app.route("/analysis")
@role_required(["employee", "admin"])
def analysis():
    return render_template("analysis.html")

@app.route("/inventory")
@role_required(["admin"])
def inventory():
    return render_template("inventory.html")

# -------------------------
# Logout
# -------------------------
@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("home"))

if __name__ == '__main__':
    app.run(debug=True)

