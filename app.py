from flask import Flask, render_template

app = Flask(__name__)

# ---------- CUSTOMER PAGES ----------

@app.route("/")
def home():
    return render_template("home.html")

@app.route("/cart")
def cart():
    return render_template("cart.html")

@app.route("/inventory")
def inventory():
    return render_template("inventory.html")


# ---------- EMPLOYEE / ADMIN PAGES ----------

@app.route("/employee-login")
def employee_login():
    return render_template("employee_login.html")

@app.route("/dashboard")
def dashboard():
    return render_template("dashboard.html")

@app.route("/analysis")
def analysis():
    return render_template("analysis.html")

@app.route("/market-analysis")
def market_analysis():
    return render_template("market_analysis.html")

@app.route("/real-time-analytics")
def real_time_analytics():
    return render_template("real_time_analytics.html")

@app.route("/contact")
def contact():
    return render_template("contact.html")


# ---------- RUN APP ----------

if __name__ == "__main__":
    app.run(debug=True)
