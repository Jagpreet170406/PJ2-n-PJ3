from flask import Flask, render_template, session, redirect, url_for, request

app = Flask(__name__)
app.secret_key = "secret123"

# --------------------
# PUBLIC
# --------------------
@app.route('/employee-login')
def employee_login():
    return render_template('employee_login.html')

@app.route('/login', methods=['POST'])
def login():
    role = request.form.get("role")  # employee / admin
    session["role"] = role
    return redirect(url_for('home'))

# --------------------
# CUSTOMER
# --------------------
@app.route('/cart')
def cart():
    session["role"] = "customer"
    return render_template('cart.html')

# --------------------
# EMPLOYEE / ADMIN
# --------------------
@app.route('/')
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

if __name__ == '__main__':
    app.run(debug=True)


# -------------------------
# Logout
# -------------------------
@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("home"))

if __name__ == '__main__':
    app.run(debug=True)

