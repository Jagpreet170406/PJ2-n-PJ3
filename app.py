from flask import Flask, render_template, session, redirect, url_for, request

app = Flask(__name__)
app.secret_key = "super-secret-key"

# --------------------
# CUSTOMER PORTAL
# --------------------
@app.route('/cart')
def cart():
    role = session.get("role")

    if role is None:
        # Default to customer
        session["role"] = "customer"
        role = "customer"

    # Role-aware cart
    can_edit = True if role in ["employee", "admin"] else False
    return render_template('cart.html', can_edit=can_edit)

# --------------------
# EMPLOYEE / ADMIN INTERNAL LOGIN
# --------------------
@app.route('/employee-login')
def employee_login():
    if session.get("role") == "customer":
        # customers cannot see internal login
        return redirect(url_for("cart"))
    return render_template('employee_login.html')

@app.route('/login', methods=['POST'])
def login():
    role = request.form.get("role")  # "employee" or "admin"
    session["role"] = role
    return redirect(url_for('home'))

# --------------------
# EMPLOYEE / ADMIN PAGES
# --------------------
@app.route('/home')
def home():
    if session.get("role") not in ["employee", "admin"]:
        return redirect(url_for('employee_login'))
    return render_template('home.html')

@app.route('/dashboard')
def dashboard():
    if session.get("role") not in ["employee", "admin"]:
        return redirect(url_for('employee_login'))
    return render_template('dashboard.html')

@app.route('/analysis')
def analysis():
    if session.get("role") not in ["employee", "admin"]:
        return redirect(url_for('employee_login'))
    return render_template('analysis.html')

# --------------------
# ADMIN ONLY
# --------------------
@app.route('/inventory')
def inventory():
    if session.get("role") != "admin":
        return redirect(url_for('employee_login'))
    return render_template('inventory.html')

# --------------------
# LOGOUT
# --------------------
@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('employee_login'))

# --------------------
# IGNORE FAVICON
# --------------------
@app.route('/favicon.ico')
def favicon():
    return '', 204

# --------------------
# RUN SERVER
# --------------------
if __name__ == '__main__':
    app.run(debug=True)


