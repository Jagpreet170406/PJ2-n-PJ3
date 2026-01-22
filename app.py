from flask import Flask, render_template, request, session, redirect, url_for
import sqlite3

app = Flask(__name__)
app.secret_key = "super-secret-key"
DB = 'database.db'  # your already created DB

# --------------------
# Helper Functions
# --------------------
def modify_cart_in_db(product_id, quantity, action, role):
    conn = sqlite3.connect(DB)
    c = conn.cursor()
    product_id = int(product_id)
    quantity = int(quantity)
    
    if action == "add":
        c.execute("SELECT quantity FROM cart WHERE user_role=? AND product_id=?", (role, product_id))
        row = c.fetchone()
        if row:
            c.execute("UPDATE cart SET quantity=quantity+? WHERE user_role=? AND product_id=?", (quantity, role, product_id))
        else:
            c.execute("INSERT INTO cart(user_role, product_id, quantity) VALUES(?,?,?)", (role, product_id, quantity))
    elif action == "remove":
        c.execute("DELETE FROM cart WHERE user_role=? AND product_id=?", (role, product_id))
    conn.commit()
    conn.close()

def modify_customer_cart(product_id, quantity, action):
    if "customer_cart" not in session:
        session["customer_cart"] = {}
    cart = session["customer_cart"]
    if action == "add":
        cart[product_id] = cart.get(product_id, 0) + quantity
    elif action == "remove":
        if product_id in cart:
            del cart[product_id]
    session["customer_cart"] = cart

def get_cart_items(role):
    items = []
    if role in ["employee","admin","superowner"]:
        conn = sqlite3.connect(DB)
        c = conn.cursor()
        c.execute('''
            SELECT p.product_id, p.name, p.price, c.quantity
            FROM cart c
            JOIN products p ON p.product_id=c.product_id
            WHERE c.user_role=?
        ''', (role,))
        items = c.fetchall()
        conn.close()
    else:  # customer
        cart = session.get("customer_cart", {})
        conn = sqlite3.connect(DB)
        c = conn.cursor()
        for pid, qty in cart.items():
            c.execute("SELECT product_id, name, price FROM products WHERE product_id=?", (pid,))
            row = c.fetchone()
            if row:
                items.append((row[0], row[1], row[2], qty))
        conn.close()
    return items

# --------------------
# CUSTOMER CART PAGE
# --------------------
@app.route('/cart', methods=['GET','POST'])
def cart():
    role = session.get("role") or "customer"
    session["role"] = role

    if request.method == "POST":
        product_id = request.form.get("product_id")
        action = request.form.get("action")
        quantity = int(request.form.get("quantity",1))

        if role in ["employee","admin","superowner"]:
            modify_cart_in_db(product_id, quantity, action, role)
        else:
            modify_customer_cart(product_id, quantity, action)

    cart_items = get_cart_items(role)
    can_edit = True if role in ["employee","admin","superowner"] else False
    return render_template('cart.html', cart_items=cart_items, role=role, can_edit=can_edit)

@app.route('/')
def root():
    return redirect(url_for("cart"))

# --------------------
# EMPLOYEE / ADMIN / SUPEROWNER LOGIN
# --------------------
@app.route('/employee-login')
def employee_login():
    role = session.get("role")
    if role == "customer":
        return redirect(url_for("cart"))
    if role in ["employee","admin","superowner"]:
        return redirect(url_for("home"))
    return render_template('employee_login.html')

@app.route('/login', methods=['POST'])
def login():
    role = request.form.get("role")  # employee, admin, superowner
    session["role"] = role
    return redirect(url_for('home'))

# --------------------
# INTERNAL PAGES
# --------------------
@app.route('/home')
def home():
    if session.get("role") not in ["employee","admin","superowner"]:
        return redirect(url_for('employee_login'))
    return render_template('home.html')

@app.route('/dashboard')
def dashboard():
    if session.get("role") not in ["employee","admin","superowner"]:
        return redirect(url_for('employee_login'))
    return render_template('dashboard.html')

@app.route('/analysis')
def analysis():
    if session.get("role") not in ["employee","admin","superowner"]:
        return redirect(url_for('employee_login'))
    return render_template('analysis.html')

# --------------------
# ADMIN / SUPEROWNER ONLY
# --------------------
@app.route('/inventory')
def inventory():
    if session.get("role") not in ["admin","superowner"]:
        return redirect(url_for('employee_login'))
    return render_template('inventory.html')

# --------------------
# SUPEROWNER DB PANEL
# --------------------
@app.route('/superowner', methods=['GET','POST'])
def superowner_panel():
    if session.get("role") != "superowner":
        return redirect(url_for('employee_login'))

    conn = sqlite3.connect(DB)
    c = conn.cursor()
    message = ""

    if request.method == "POST":
        query = request.form.get("query")  # raw SQL input
        try:
            c.execute(query)
            conn.commit()
            message = "Query executed successfully."
        except Exception as e:
            message = f"Error: {e}"

    # Fetch table names and preview data
    c.execute("SELECT name FROM sqlite_master WHERE type='table';")
    tables = c.fetchall()
    data = {}
    for t in tables:
        table_name = t[0]
        c.execute(f"SELECT * FROM {table_name} LIMIT 50")
        data[table_name] = c.fetchall()
    conn.close()

    return render_template('superowner.html', tables=data, message=message)

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





