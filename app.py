from flask import Flask, render_template, request, session, redirect, url_for
import sqlite3

app = Flask(__name__)
app.secret_key = "super-secret-key-change-this-in-production"
DB = 'database.db'

# --------------------
# Database Initialization
# --------------------
def init_db():
    """Initialize database with users table for RBAC"""
    conn = sqlite3.connect(DB)
    c = conn.cursor()
    
    # Create users table if not exists
    c.execute('''
        CREATE TABLE IF NOT EXISTS users (
            username TEXT PRIMARY KEY,
            password TEXT NOT NULL,
            role TEXT NOT NULL,
            active INTEGER DEFAULT 1
        )
    ''')
    
    # Create superowner account if not exists
    c.execute("SELECT * FROM users WHERE role='superowner'")
    if not c.fetchone():
        # Default superowner credentials - CHANGE THESE!
        c.execute("INSERT INTO users VALUES (?, ?, ?, 1)", 
                  ('superowner', 'changeme123', 'superowner'))
    
    conn.commit()
    conn.close()

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
            c.execute("UPDATE cart SET quantity=quantity+? WHERE user_role=? AND product_id=?", 
                      (quantity, role, product_id))
        else:
            c.execute("INSERT INTO cart(user_role, product_id, quantity) VALUES(?,?,?)", 
                      (role, product_id, quantity))
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

def check_user_credentials(username, password):
    """Verify user credentials and return role if valid"""
    conn = sqlite3.connect(DB)
    c = conn.cursor()
    c.execute("SELECT role, active FROM users WHERE username=? AND password=?", 
              (username, password))
    result = c.fetchone()
    conn.close()
    
    if result and result[1] == 1:  # active user
        return result[0]
    return None

# --------------------
# PUBLIC ROUTES
# --------------------
@app.route('/')
def root():
    """Default landing page - cart for customers"""
    if "role" not in session:
        session["role"] = "customer"
    return redirect(url_for("cart"))

@app.route('/cart', methods=['GET','POST'])
def cart():
    """Customer cart page (public access)"""
    role = session.get("role", "customer")
    
    # If employee/admin/superowner, redirect to their home
    if role in ["employee", "admin", "superowner"]:
        return redirect(url_for("home"))

    if request.method == "POST":
        product_id = request.form.get("product_id")
        action = request.form.get("action")
        quantity = int(request.form.get("quantity", 1))
        modify_customer_cart(product_id, quantity, action)

    cart_items = get_cart_items("customer")
    return render_template('cart.html', cart_items=cart_items, role="customer", can_edit=False)

# --------------------
# AUTHENTICATION
# --------------------
@app.route('/staff-login', methods=['GET', 'POST'])
def staff_login():
    """Login page for employees, admins, and superowner"""
    if request.method == 'POST':
        username = request.form.get("username")
        password = request.form.get("password")
        
        role = check_user_credentials(username, password)
        
        if role:
            session["role"] = role
            session["username"] = username
            return redirect(url_for('home'))
        else:
            return render_template('staff_login.html', error="Invalid credentials or account disabled")
    
    # If already logged in as staff, redirect to home
    if session.get("role") in ["employee", "admin", "superowner"]:
        return redirect(url_for("home"))
    
    return render_template('staff_login.html', error=None)

@app.route('/logout')
def logout():
    """Logout and return to customer cart"""
    session.clear()
    session["role"] = "customer"
    return redirect(url_for('cart'))

# --------------------
# INTERNAL PAGES (Employee/Admin/Superowner)
# --------------------
@app.route('/home')
def home():
    """Home page for authenticated staff"""
    if session.get("role") not in ["employee","admin","superowner"]:
        return redirect(url_for('staff_login'))
    return render_template('home.html', role=session.get("role"), username=session.get("username"))

@app.route('/dashboard')
def dashboard():
    """Dashboard for authenticated staff"""
    if session.get("role") not in ["employee","admin","superowner"]:
        return redirect(url_for('staff_login'))
    return render_template('dashboard.html', role=session.get("role"))

@app.route('/analysis')
def analysis():
    """Analysis page for authenticated staff"""
    if session.get("role") not in ["employee","admin","superowner"]:
        return redirect(url_for('staff_login'))
    return render_template('analysis.html', role=session.get("role"))

# --------------------
# ADMIN / SUPEROWNER ONLY
# --------------------
@app.route('/inventory')
def inventory():
    """Inventory management for admin and superowner"""
    if session.get("role") not in ["admin","superowner"]:
        return redirect(url_for('staff_login'))
    return render_template('inventory.html', role=session.get("role"))

# --------------------
# SUPEROWNER ONLY - USER MANAGEMENT
# --------------------
@app.route('/manage-users', methods=['GET', 'POST'])
def manage_users():
    """Superowner panel to add/remove/disable users"""
    if session.get("role") != "superowner":
        return redirect(url_for('staff_login'))

    conn = sqlite3.connect(DB)
    c = conn.cursor()
    message = ""

    if request.method == "POST":
        action = request.form.get("action")
        
        if action == "add":
            username = request.form.get("username")
            password = request.form.get("password")
            role = request.form.get("role")
            
            try:
                c.execute("INSERT INTO users VALUES (?, ?, ?, 1)", 
                          (username, password, role))
                conn.commit()
                message = f"User '{username}' added successfully as {role}."
            except sqlite3.IntegrityError:
                message = f"Error: Username '{username}' already exists."
            except Exception as e:
                message = f"Error: {e}"
        
        elif action == "toggle":
            username = request.form.get("username")
            c.execute("SELECT active FROM users WHERE username=?", (username,))
            result = c.fetchone()
            if result:
                new_status = 0 if result[0] == 1 else 1
                c.execute("UPDATE users SET active=? WHERE username=?", (new_status, username))
                conn.commit()
                status_text = "enabled" if new_status == 1 else "disabled"
                message = f"User '{username}' {status_text}."
            else:
                message = f"User '{username}' not found."
        
        elif action == "delete":
            username = request.form.get("username")
            if username == session.get("username"):
                message = "Error: Cannot delete your own account."
            else:
                c.execute("DELETE FROM users WHERE username=?", (username,))
                conn.commit()
                message = f"User '{username}' deleted."
        
        elif action == "change_role":
            username = request.form.get("username")
            new_role = request.form.get("new_role")
            c.execute("UPDATE users SET role=? WHERE username=?", (new_role, username))
            conn.commit()
            message = f"User '{username}' role changed to {new_role}."

    # Get all users
    c.execute("SELECT username, role, active FROM users ORDER BY role, username")
    users = c.fetchall()
    conn.close()

    return render_template('manage_users.html', users=users, message=message)

# --------------------
# SUPEROWNER DB PANEL (Optional)
# --------------------
@app.route('/db-panel', methods=['GET','POST'])
def db_panel():
    """Direct database access for superowner (use with caution)"""
    if session.get("role") != "superowner":
        return redirect(url_for('staff_login'))

    conn = sqlite3.connect(DB)
    c = conn.cursor()
    message = ""

    if request.method == "POST":
        query = request.form.get("query")
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

    return render_template('db_panel.html', tables=data, message=message)

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
    init_db()  # Initialize database on startup
    app.run(debug=True)





