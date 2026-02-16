# === IMPORTS ===
import sqlite3
import os
import json
from functools import wraps
from collections import defaultdict
from datetime import datetime, timedelta, date
from dotenv import load_dotenv
from flask import Flask, render_template, request, redirect, url_for, session, flash, jsonify, send_from_directory
from flask_wtf.csrf import CSRFProtect, generate_csrf
from werkzeug.security import generate_password_hash, check_password_hash
from groq import Groq
from image_matcher import build_image_cache, get_product_image_url

load_dotenv()

# === FLASK APP INITIALIZATION ===
app = Flask(__name__)
app.secret_key = "chinhon_secret_key"
csrf = CSRFProtect(app)

# === GROQ API SETUP ===
GROQ_API_KEY = os.getenv("GROQ_API_KEY", "")
groq_client = Groq(api_key=GROQ_API_KEY) if GROQ_API_KEY else None

# === DATABASE SETUP ===
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB = os.path.join(BASE_DIR, "database.db")

def get_db():
    """Create and return a database connection with dict-like row access."""
    conn = sqlite3.connect(DB)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    """Initialize database tables if they don't exist."""
    with get_db() as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS user_cards (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT NOT NULL,
                brand TEXT,
                last4 TEXT,
                exp TEXT,
                name TEXT
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS sales_data (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                item_code TEXT NOT NULL,
                description TEXT,
                qty_sold INTEGER NOT NULL,
                total_sales REAL NOT NULL,
                period TEXT NOT NULL,
                competitor_price REAL,
                stock_qty INTEGER DEFAULT 0,
                demand_level INTEGER DEFAULT 3,
                recommended_price REAL
            )
        """)
        # Create orders table
        conn.execute("""
            CREATE TABLE IF NOT EXISTS orders (
                order_id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT NOT NULL,
                payment_type TEXT,
                amount REAL,
                status TEXT DEFAULT 'Incoming',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        conn.execute("CREATE INDEX IF NOT EXISTS idx_sih_date    ON sales_invoice_header(invoice_date)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_sih_cust    ON sales_invoice_header(customer_id)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_sil_inv     ON sales_invoice_line(invoice_no)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_sil_prod    ON sales_invoice_line(product_id)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_prod_name   ON products(hem_name)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_cust_code   ON customers(customer_code)")
        # Migrate: add customer_email if not exists
        try:
            conn.execute("ALTER TABLE transactions ADD COLUMN customer_email TEXT DEFAULT ''")
        except sqlite3.OperationalError:
            pass
        conn.commit()

init_db()

# === CONTEXT PROCESSORS ===
@app.context_processor
def inject_csrf_token():
    """Make CSRF token and today's date available to all templates."""
    return dict(
        csrf_token=generate_csrf,
        today=date.today().isoformat(),
        get_product_image_url=get_product_image_url
    )

# === AUTHENTICATION DECORATORS ===
def require_staff(f):
    """Decorator to protect routes that require staff access."""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if session.get("role") not in ["employee", "admin", "superowner"]:
            return redirect(url_for('cart'))
        return f(*args, **kwargs)
    return decorated_function

# === ROUTING ===
@app.route("/")
def root():
    """Root route - redirects based on user role."""
    role = session.get("role")
    if role in ["employee", "admin", "superowner"]:
        return redirect(url_for("home"))
    return redirect(url_for("cart"))

@app.route("/cart")
def cart():
    """Customer-facing product catalog with pagination, search, and filtering."""
    page = request.args.get('page', 1, type=int)
    search_query = request.args.get('search', '')
    category_filter = request.args.get('category', '')
    min_price = request.args.get('min_price', type=float)
    max_price = request.args.get('max_price', type=float)
    per_page = 24
    offset = (page - 1) * per_page

    with get_db() as conn:
        categories_raw = conn.execute("SELECT DISTINCT category FROM inventory WHERE category IS NOT NULL ORDER BY category").fetchall()
        categories = [row[0] for row in categories_raw]
        
        origins_raw = conn.execute("SELECT DISTINCT org FROM inventory WHERE org IS NOT NULL AND org != '' ORDER BY org").fetchall()
        origins = [row[0] for row in origins_raw]
        
        price_range = conn.execute("SELECT MIN(sell_price), MAX(sell_price) FROM inventory WHERE qty > 0").fetchone()
        
        where_clause = " WHERE qty > 0"
        params = []

        if search_query:
            where_clause += " AND (hem_name LIKE ? OR sup_part_no LIKE ?)"
            params.extend([f'%{search_query}%', f'%{search_query}%'])

        if category_filter:
            where_clause += " AND category = ?"
            params.append(category_filter)

        if min_price is not None:
            where_clause += " AND sell_price >= ?"
            params.append(min_price)

        if max_price is not None:
            where_clause += " AND sell_price <= ?"
            params.append(max_price)

        bucket_core = """
            SELECT
                hem_name,
                GROUP_CONCAT(DISTINCT sup_part_no) as sup_part_no,
                category,
                MIN(sell_price)   as sell_price,
                MAX(sell_price)   as max_price,
                image_url,
                MIN(inventory_id) as inventory_id,
                SUM(qty)          as qty,
                COUNT(*)          as variant_count,
                GROUP_CONCAT(DISTINCT org) as org,
                MIN(sup_part_no)  as first_sku
            FROM inventory
        """

        def make_bucket(vc_condition):
            inner = bucket_core + where_clause + """
                GROUP BY hem_name
                HAVING """ + vc_condition + """
                ORDER BY hem_name ASC
                LIMIT 50
            """
            return "SELECT * FROM (" + inner + ") AS bkt"

        pool_query = """
            SELECT * FROM (
                {b1}
                UNION ALL
                {b2}
                UNION ALL
                {b3}
                UNION ALL
                {b4}
            ) AS pool
            ORDER BY variant_count ASC, hem_name ASC
        """.format(
            b1=make_bucket("COUNT(*) = 1"),
            b2=make_bucket("COUNT(*) = 2"),
            b3=make_bucket("COUNT(*) = 3"),
            b4=make_bucket("COUNT(*) > 3"),
        )

        pool_params = params * 4
        all_pooled = conn.execute(pool_query, pool_params).fetchall()
        total_count = len(all_pooled)
        total_pages = (total_count // per_page) + (1 if total_count % per_page > 0 else 0)
        products_raw = all_pooled[offset: offset + per_page]
        
        products = []
        for row in products_raw:
            product_dict = {
                'id': row['inventory_id'],
                'name': row['hem_name'],
                'category': row['category'] or 'Uncategorized',
                'price': float(row['sell_price']) if row['sell_price'] else 0.0,
                'max_price': float(row['max_price']) if row['max_price'] else 0.0,
                'image_url': row['image_url'] or '/static/placeholder.png',
                'qty': row['qty'] or 0,
                'variant_count': row['variant_count'] or 1,
                'origin': row['org'] or '',
                'sku': row['first_sku'] or ''  # Always include SKU for image matching
            }
            
            products.append(product_dict)

    return render_template("cart.html", products=products, categories=categories,
                           origins=origins,
                           current_page=page, total_pages=total_pages,
                           search_query=search_query, category_filter=category_filter,
                           min_price=min_price, max_price=max_price,
                           price_range=price_range,
                           role=session.get("role", "customer"))

@app.route("/manage_users", methods=["GET", "POST"])
@require_staff
def manage_users():
    """Manage Users page - CRUD operations for user accounts."""
    message = None

    if request.method == "POST":
        action = request.form.get("action")
        username = request.form.get("username", "").strip()

        with get_db() as conn:
            if action == "add":
                password = request.form.get("password", "").strip()
                role = request.form.get("role", "employee").strip()
                
                if not username or not password:
                    message = "Username and password are required."
                else:
                    existing = conn.execute("SELECT 1 FROM users WHERE username = ?", (username,)).fetchone()
                    if existing:
                        message = f"User '{username}' already exists."
                    else:
                        hashed_pw = generate_password_hash(password)
                        conn.execute(
                            "INSERT INTO users (username, password_hash, role, active) VALUES (?, ?, ?, 1)",
                            (username, hashed_pw, role)
                        )
                        conn.commit()
                        message = f"User '{username}' added successfully."

            elif action == "change_role":
                new_role = request.form.get("new_role", "employee").strip()
                conn.execute("UPDATE users SET role = ? WHERE username = ?", (new_role, username))
                conn.commit()
                message = f"Role updated for '{username}'."

            elif action == "toggle":
                conn.execute("UPDATE users SET active = NOT active WHERE username = ?", (username,))
                conn.commit()
                message = f"Status toggled for '{username}'."

            elif action == "delete":
                conn.execute("DELETE FROM users WHERE username = ?", (username,))
                conn.commit()
                message = f"User '{username}' deleted."

    with get_db() as conn:
        users = conn.execute("SELECT username, role, active FROM users ORDER BY username").fetchall()

    return render_template(
        "manage_users.html",
        users=[dict(u) for u in users],
        message=message,
        role=session.get("role")
    )

@app.route("/checkout")
def checkout():
    """Checkout page where customers finalize their orders."""
    return render_template("checkout.html", role=session.get("role", "customer"), user_cards=[])

@app.route("/process-payment", methods=["POST"])
@csrf.exempt
def process_payment():
    """Process payment submission and save transaction + order + items to database."""
    data = request.get_json()
    if not data:
        return jsonify({"success": False, "message": "No data received"})

    cart_items = data.get('cart', [])
    payment_method = data.get('payment_method', 'Credit Card')
    total_amount = data.get('total_amount', 0)
    fulfillment_method = data.get('fulfillment_method', 'pickup')
    fulfillment_details = data.get('fulfillment_details', '')
    customer_email = data.get('customer_email', '')
    username = session.get("username", "Guest")

    if not cart_items:
        return jsonify({"success": False, "message": "Cart is empty"})

    try:
        with get_db() as conn:
            # Insert into transactions table with fulfillment info
            cursor = conn.execute(
                """INSERT INTO transactions 
                   (username, payment_type, amount, status, fulfillment_method, fulfillment_details, customer_email) 
                   VALUES (?, ?, ?, ?, ?, ?, ?)""",
                (username, payment_method, total_amount, 'Incoming', fulfillment_method, fulfillment_details, customer_email)
            )
            order_id = cursor.lastrowid
            
            # Insert each cart item into order_items table
            for item in cart_items:
                inventory_id = item.get('id')
                product_name = item.get('name', 'Unknown Product')
                product_sku = item.get('sku', '')
                quantity = item.get('quantity', 1)
                unit_price = item.get('price', 0)
                image_url = item.get('image', '/static/product_images_v2/placeholder.png')
                
                conn.execute(
                    """INSERT INTO order_items 
                       (order_id, inventory_id, product_name, product_sku, quantity, unit_price, image_url)
                       VALUES (?, ?, ?, ?, ?, ?, ?)""",
                    (order_id, inventory_id, product_name, product_sku, quantity, unit_price, image_url)
                )
            
            conn.commit()
        
        return jsonify({
            "success": True, 
            "message": "Payment successful",
            "order_id": order_id
        })
    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({"success": False, "message": str(e)})

@app.route("/order-success")
def order_success():
    """Order confirmation page after successful payment."""
    method = request.args.get('method', 'pickup')
    date = request.args.get('date', '')
    return render_template("order_success.html", method=method, date=date, role="customer")

@app.route("/contact")
def contact():
    """Contact information page for customers."""
    return render_template("contact.html", role="customer")

@app.route("/orders")
@require_staff
def orders():
    """Staff Orders page with order items display."""
    
    tabs = ["Incoming", "In Progress", "Awaiting Pickup", "Out for Delivery", "Completed", "Issues"]
    active_tab = request.args.get("tab", "Incoming").strip()
    
    if active_tab not in tabs:
        active_tab = "Incoming"
    
    page = request.args.get("page", 1, type=int)
    search_query = request.args.get("search", "").strip()
    per_page = 20
    offset = (page - 1) * per_page
    
    with get_db() as conn:
        where_clauses = ["status = ?"]
        params = [active_tab]
        
        if search_query:
            where_clauses.append("(username LIKE ? OR payment_type LIKE ?)")
            like = f"%{search_query}%"
            params.extend([like, like])
        
        where_sql = " WHERE " + " AND ".join(where_clauses)
        
        total_count = conn.execute(
            f"SELECT COUNT(*) FROM transactions {where_sql}",
            params
        ).fetchone()[0]
        
        total_pages = (total_count + per_page - 1) // per_page
        
        # Fetch orders with their items
        rows = conn.execute(
            f"""
            SELECT id as transaction_id, username, payment_type, amount, status, 
                   fulfillment_method, fulfillment_details, customer_email, timestamp as created_at
            FROM transactions
            {where_sql}
            ORDER BY timestamp DESC
            LIMIT ? OFFSET ?
            """,
            params + [per_page, offset]
        ).fetchall()
        
        # Fetch order items for each order
        orders_with_items = []
        for row in rows:
            order_dict = dict(row)
            order_id = order_dict['transaction_id']
            
            # Get items for this order
            items = conn.execute(
                """SELECT inventory_id, product_name, product_sku, quantity, unit_price, image_url
                   FROM order_items
                   WHERE order_id = ?
                   ORDER BY item_id""",
                (order_id,)
            ).fetchall()
            
            order_dict['order_items'] = [dict(item) for item in items]
            orders_with_items.append(order_dict)
    
    return render_template(
        "orders.html",
        tabs=tabs,
        active_tab=active_tab,
        orders=orders_with_items,
        current_page=page,
        total_pages=total_pages,
        search_query=search_query,
        role=session.get("role"),
    )

@app.route("/api/update-order-status/<int:order_id>", methods=["POST"])
@csrf.exempt
@require_staff
def update_order_status(order_id):
    """API: Update order status (move between workflow stages)."""
    try:
        data = request.get_json()
        new_status = data.get('status', '').strip()
        
        if not new_status:
            return jsonify({"success": False, "message": "Status is required"}), 400
        
        valid_statuses = ["Incoming", "In Progress", "Awaiting Pickup", "Out for Delivery", "Completed", "Issues"]
        if new_status not in valid_statuses:
            return jsonify({"success": False, "message": "Invalid status"}), 400
        
        with get_db() as conn:
            order = conn.execute(
                "SELECT * FROM transactions WHERE id = ?",
                (order_id,)
            ).fetchone()
            
            if not order:
                return jsonify({"success": False, "message": "Order not found"}), 404
            
            conn.execute(
                "UPDATE transactions SET status = ? WHERE id = ?",
                (new_status, order_id)
            )
            conn.commit()
            
            return jsonify({
                "success": True,
                "message": f"Order moved to {new_status}"
            })
            
    except Exception as e:
        return jsonify({"success": False, "message": str(e)}), 500

@app.route("/api/cancel-order/<int:order_id>", methods=["DELETE"])
@csrf.exempt
@require_staff
def cancel_order(order_id):
    """API: Cancel/delete an order from the system."""
    try:
        with get_db() as conn:
            order = conn.execute(
                "SELECT * FROM transactions WHERE id = ?",
                (order_id,)
            ).fetchone()
            
            if not order:
                return jsonify({"success": False, "message": "Order not found"}), 404
            
            # Delete order items first (foreign key constraint)
            conn.execute("DELETE FROM order_items WHERE order_id = ?", (order_id,))
            # Delete the order
            conn.execute("DELETE FROM transactions WHERE id = ?", (order_id,))
            conn.commit()
            
            return jsonify({
                "success": True,
                "message": "Order cancelled successfully"
            })
            
    except Exception as e:
        return jsonify({"success": False, "message": str(e)}), 500

@app.route("/api/notify-pickup/<int:order_id>", methods=["POST"])
@csrf.exempt
@require_staff
def notify_pickup(order_id):
    """API: Email customer via Mailjet when pickup order is ready."""
    import urllib.request
    import urllib.error
    import base64

    MJ_API_KEY    = os.getenv("MAILJET_API_KEY")
    MJ_SECRET_KEY = os.getenv("MAILJET_SECRET_KEY")
    FROM_EMAIL    = os.getenv("MAILJET_FROM_EMAIL")  # must be verified in Mailjet

    if not MJ_API_KEY or not MJ_SECRET_KEY or not FROM_EMAIL:
        return jsonify({"success": False, "message": "Mailjet not configured — set MAILJET_API_KEY, MAILJET_SECRET_KEY, MAILJET_FROM_EMAIL env vars"}), 500

    try:
        with get_db() as conn:
            order = conn.execute(
                "SELECT id, customer_email, amount FROM transactions WHERE id = ?",
                (order_id,)
            ).fetchone()

            if not order:
                return jsonify({"success": False, "message": "Order not found"}), 404

            to_email = order["customer_email"]
            if not to_email:
                return jsonify({"success": False, "message": "No email address on this order"}), 400

            payload = json.dumps({
                "Messages": [{
                    "From": {"Email": FROM_EMAIL, "Name": "Chin Hon Motors"},
                    "To":   [{"Email": to_email}],
                    "Subject": f"Your Order #{order['id']} is Ready for Collection!",
                    "HTMLPart": f"""
                    <div style="font-family:Arial,sans-serif;max-width:600px;margin:auto;padding:32px;background:#f9f9f9;border-radius:12px;">
                        <h2 style="color:#111;">Hi there! Your order is ready. 🎉</h2>
                        <p style="color:#444;font-size:1rem;line-height:1.6;">
                            <strong>Order #{order['id']}</strong> has been packed and is ready for self-collection.
                        </p>
                        <div style="background:#fff;border-radius:8px;padding:20px;margin:24px 0;border-left:4px solid #10b981;">
                            <p style="margin:0 0 8px;font-size:0.95rem;color:#333;">
                                📍 <strong>Pickup Location</strong><br>62 Race Course Rd, Singapore 218568
                            </p>
                            <p style="margin:8px 0 0;font-size:0.95rem;color:#333;">
                                🕐 <strong>Opening Hours</strong><br>Mon–Sat: 9am – 6pm
                            </p>
                        </div>
                        <p style="color:#444;font-size:0.9rem;">Please bring along this email or your order number when you arrive.</p>
                        <p style="color:#888;font-size:0.8rem;margin-top:32px;">— Chin Hon Motors</p>
                    </div>
                    """
                }]
            }).encode("utf-8")

            credentials = base64.b64encode(f"{MJ_API_KEY}:{MJ_SECRET_KEY}".encode()).decode()
            req = urllib.request.Request(
                "https://api.mailjet.com/v3.1/send",
                data=payload,
                headers={
                    "Content-Type":  "application/json",
                    "Authorization": f"Basic {credentials}"
                },
                method="POST"
            )

            with urllib.request.urlopen(req) as resp:
                result = json.loads(resp.read().decode())
                status = result.get("Messages", [{}])[0].get("Status", "")
                if status == "success":
                    return jsonify({"success": True, "message": f"Email sent to {to_email}"})
                else:
                    return jsonify({"success": False, "message": str(result)}), 500

    except urllib.error.HTTPError as e:
        body = e.read().decode()
        print(f"[notify-pickup] HTTPError: {body}")
        return jsonify({"success": False, "message": f"Mailjet error: {body}"}), 500
    except Exception as e:
        import traceback
        traceback.print_exc()
        print(f"[notify-pickup] Exception: {e}")
        return jsonify({"success": False, "message": str(e)}), 500

@app.route("/feedback")
@require_staff
def feedback():
    """Staff feedback management page - view customer feedback and reviews."""
    page = request.args.get('page', 1, type=int)
    search_query = request.args.get('search', '')
    rating_filter = request.args.get('rating', type=int)
    per_page = 20
    offset = (page - 1) * per_page
    
    with get_db() as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS feedback (
                feedback_id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT NOT NULL,
                email TEXT,
                rating INTEGER CHECK(rating >= 1 AND rating <= 5),
                message TEXT NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
        base_query = "FROM feedback f"
        where_clauses = []
        params = []
        
        if search_query:
            where_clauses.append("(f.username LIKE ? OR f.email LIKE ? OR f.message LIKE ?)")
            params.extend([f'%{search_query}%', f'%{search_query}%', f'%{search_query}%'])
        
        if rating_filter:
            where_clauses.append("f.rating = ?")
            params.append(rating_filter)
        
        where_sql = " WHERE " + " AND ".join(where_clauses) if where_clauses else ""
        
        total_count = conn.execute(f"SELECT COUNT(*) {base_query} {where_sql}", params).fetchone()[0]
        total_pages = (total_count // per_page) + (1 if total_count % per_page > 0 else 0)
        
        feedback_list = conn.execute(f"""
            SELECT f.feedback_id, f.username, f.email, f.rating, f.message, f.created_at
            {base_query} {where_sql}
            ORDER BY f.created_at DESC
            LIMIT ? OFFSET ?
        """, params + [per_page, offset]).fetchall()
        
        stats = conn.execute(f"""
            SELECT 
                COUNT(*) as total_feedback,
                COALESCE(AVG(rating), 0) as avg_rating,
                COUNT(CASE WHEN rating = 5 THEN 1 END) as five_star,
                COUNT(CASE WHEN rating = 4 THEN 1 END) as four_star,
                COUNT(CASE WHEN rating = 3 THEN 1 END) as three_star,
                COUNT(CASE WHEN rating <= 2 THEN 1 END) as low_rating
            {base_query} {where_sql}
        """, params).fetchone()
    
    return render_template("feedback.html",
                         feedback=[dict(row) for row in feedback_list],
                         current_page=page,
                         total_pages=total_pages,
                         search_query=search_query,
                         rating_filter=rating_filter,
                         total_feedback=stats['total_feedback'],
                         avg_rating=round(float(stats['avg_rating']), 2),
                         five_star=stats['five_star'],
                         four_star=stats['four_star'],
                         three_star=stats['three_star'],
                         low_rating=stats['low_rating'],
                         role=session.get("role"))

@app.route("/submit-feedback", methods=["POST"])
@csrf.exempt
def submit_feedback():
    """API endpoint for customers to submit feedback."""
    data = request.get_json()
    
    if not data:
        return jsonify({"success": False, "message": "No data received"}), 400
    
    username = session.get("username", "Guest")
    email = data.get('email', '').strip()
    rating = data.get('rating', 0)
    message = data.get('message', '').strip()
    
    if not message:
        return jsonify({"success": False, "message": "Feedback message is required"}), 400
    
    if not rating or rating < 1 or rating > 5:
        return jsonify({"success": False, "message": "Rating must be between 1 and 5"}), 400
    
    try:
        with get_db() as conn:
            conn.execute("""
                INSERT INTO feedback (username, email, rating, message)
                VALUES (?, ?, ?, ?)
            """, (username, email, rating, message))
            conn.commit()
        
        return jsonify({"success": True, "message": "Feedback submitted successfully"})
    except Exception as e:
        return jsonify({"success": False, "message": str(e)}), 500

@app.route("/staff-login", methods=["GET", "POST"])
def staff_login():
    """Staff login page - validates credentials and creates session."""
    if session.get("role") in ["employee", "admin", "superowner"]:
        return redirect(url_for("home"))

    if request.method == "POST":
        u, p = request.form.get("username"), request.form.get("password")
        with get_db() as conn:
            user = conn.execute("SELECT * FROM users WHERE username=?", (u,)).fetchone()

        if user and check_password_hash(user['password_hash'], p):
            session.update({"username": u, "role": user['role']})
            return redirect(url_for("home"))
        flash("Invalid credentials", "danger")

    return render_template("staff_login.html", role="customer")

@app.route("/home")
@require_staff
def home():
    """Staff home/dashboard page."""
    return render_template("home.html", role=session.get("role"))

@app.route('/about')
def about():
    """About us page - company information."""
    return render_template('about_us.html')

# === INVENTORY MANAGEMENT ROUTES ===

@app.route("/inventory")
@require_staff
def inventory():
    """Inventory management page with CRUD operations."""
    return render_template("inventory.html", role=session.get("role"))

@app.route("/api/inventory", methods=["GET"])
@csrf.exempt
@require_staff
def api_get_inventory():
    """API: Retrieve grouped inventory items by product name to reduce duplicates."""
    try:
        with get_db() as conn:
            bucket_select = """
                SELECT
                    hem_name,
                    GROUP_CONCAT(DISTINCT sup_part_no) as sup_part_no,
                    category,
                    org,
                    loc_on_shelf,
                    SUM(qty)          as qty,
                    MIN(sell_price)   as sell_price,
                    MAX(sell_price)   as max_price,
                    image_url,
                    MIN(inventory_id) as inventory_id,
                    COUNT(*)          as variant_count,
                    MIN(sup_part_no)  as first_sku
                FROM inventory
                GROUP BY hem_name
            """
            def inv_bucket(vc_condition):
                inner = bucket_select + " HAVING " + vc_condition + " ORDER BY hem_name ASC LIMIT 50"
                return "SELECT * FROM (" + inner + ") AS bkt"

            pool_query = (
                "SELECT * FROM ("
                + inv_bucket("COUNT(*) = 1")
                + " UNION ALL "
                + inv_bucket("COUNT(*) = 2")
                + " UNION ALL "
                + inv_bucket("COUNT(*) = 3")
                + " UNION ALL "
                + inv_bucket("COUNT(*) > 3")
                + ") AS pool ORDER BY variant_count ASC, hem_name ASC"
            )
            items = conn.execute(pool_query).fetchall()
            return jsonify([dict(item) for item in items])
    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({"error": str(e)}), 500

@app.route("/api/inventory", methods=["POST"])
@csrf.exempt
@require_staff
def api_create_inventory():
    """API: Create a new inventory item with validation."""
    data = request.get_json()
    
    sup_part_no = (data.get('sup_part_no') or '').strip()
    hem_name = (data.get('hem_name') or '').strip()
    category = data.get('category', 'Lubricants')
    qty = int(data.get('qty', 0))
    sell_price = float(data.get('sell_price', 0))
    image_url = (data.get('image_url') or '').strip()
    
    if not hem_name:
        return jsonify({"success": False, "message": "Product name is required"}), 400
    
    try:
        with get_db() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO inventory (sup_part_no, hem_name, category, qty, sell_price, image_url)
                VALUES (?, ?, ?, ?, ?, ?)
            """, (sup_part_no, hem_name, category, qty, sell_price, image_url))
            conn.commit()
            return jsonify({"success": True, "inventory_id": cursor.lastrowid, "message": "Product added successfully"})
    except Exception as e:
        return jsonify({"success": False, "message": str(e)}), 500

@app.route("/api/inventory/<int:inventory_id>", methods=["PUT"])
@csrf.exempt
@require_staff
def api_update_inventory(inventory_id):
    """API: Update an existing inventory item."""
    data = request.get_json()
    
    sup_part_no = (data.get('sup_part_no') or '').strip()
    hem_name = (data.get('hem_name') or '').strip()
    category = data.get('category', 'Lubricants')
    qty = int(data.get('qty', 0))
    sell_price = float(data.get('sell_price', 0))
    image_url = (data.get('image_url') or '').strip()
    
    if not hem_name:
        return jsonify({"success": False, "message": "Product name is required"}), 400
    
    try:
        with get_db() as conn:
            conn.execute("""
                UPDATE inventory
                SET sup_part_no=?, hem_name=?, category=?, qty=?, sell_price=?, image_url=?
                WHERE inventory_id=?
            """, (sup_part_no, hem_name, category, qty, sell_price, image_url, inventory_id))
            conn.commit()
            return jsonify({"success": True, "message": "Product updated successfully"})
    except Exception as e:
        return jsonify({"success": False, "message": str(e)}), 500

@app.route("/api/inventory/<int:inventory_id>", methods=["DELETE"])
@csrf.exempt
@require_staff
def api_delete_inventory(inventory_id):
    """API: Delete an inventory item permanently."""
    try:
        with get_db() as conn:
            conn.execute("DELETE FROM inventory WHERE inventory_id=?", (inventory_id,))
            conn.commit()
            return jsonify({"success": True, "message": "Product deleted successfully"})
    except Exception as e:
        return jsonify({"success": False, "message": str(e)}), 500

@app.route("/api/product-variants", methods=["GET"])
@csrf.exempt
def api_get_product_variants():
    """API: Get all SKU variants for a specific product name."""
    product_name = request.args.get('name', '')
    
    if not product_name:
        return jsonify({"error": "Product name required"}), 400
    
    try:
        with get_db() as conn:
            variants = conn.execute("""
                SELECT inventory_id, sup_part_no, hem_name, category, 
                       org, loc_on_shelf, qty, sell_price, image_url
                FROM inventory
                WHERE hem_name = ? AND qty > 0
                ORDER BY sup_part_no ASC
            """, (product_name,)).fetchall()
            
            return jsonify([dict(v) for v in variants])
    except Exception as e:
        return jsonify({"error": str(e)}), 500

# === SALES DASHBOARD ROUTES ===

@app.route("/dashboard")
@require_staff
def dashboard():
    """Sales dashboard — optimized: SQL-level pagination, minimal joins, indexed queries."""
    page       = request.args.get('page', 1, type=int)
    per_page   = 20
    offset     = (page - 1) * per_page
    search     = request.args.get('search', '').strip()
    start_date = request.args.get('start_date', '').strip()
    end_date   = request.args.get('end_date', '').strip()

    with get_db() as conn:

        if search or start_date or end_date:
            inner_clauses = []
            inner_params  = []

            if search:
                inner_clauses.append("""(
                    h.invoice_no LIKE ?
                    OR EXISTS (
                        SELECT 1 FROM sales_invoice_line l2
                        JOIN products p2 ON p2.product_id = l2.product_id
                        WHERE l2.invoice_no = h.invoice_no AND p2.hem_name LIKE ?
                    )
                    OR EXISTS (
                        SELECT 1 FROM customers c2
                        WHERE c2.customer_id = h.customer_id AND c2.customer_code LIKE ?
                    )
                )""")
                like = f'%{search}%'
                inner_params.extend([like, like, like])

            if start_date:
                inner_clauses.append("h.invoice_date >= ?")
                inner_params.append(start_date)

            if end_date:
                inner_clauses.append("h.invoice_date <= ?")
                inner_params.append(end_date)

            filter_where = "WHERE " + " AND ".join(inner_clauses)
        else:
            filter_where  = ""
            inner_params  = []

        kpi_row = conn.execute(f"""
            SELECT
                COUNT(DISTINCT h.invoice_no)            AS total_invoices,
                COUNT(DISTINCT h.customer_id)           AS total_customers,
                COALESCE(SUM(l.total_amt), 0)           AS total_revenue,
                COALESCE(SUM(l.gst_amt),  0)            AS total_gst,
                COALESCE(SUM(l.qty),      0)            AS total_units
            FROM sales_invoice_header h
            LEFT JOIN sales_invoice_line l ON l.invoice_no = h.invoice_no
            {filter_where}
        """, inner_params).fetchone()

        total_count = int(kpi_row['total_invoices'] or 0)
        total_pages = (total_count + per_page - 1) // per_page
        stats = {
            'total_invoices':  total_count,
            'total_customers': int(kpi_row['total_customers'] or 0),
            'total_revenue':   round(float(kpi_row['total_revenue'] or 0), 2),
            'total_gst':       round(float(kpi_row['total_gst']     or 0), 2),
            'total_units':     int(kpi_row['total_units']    or 0),
        }

        page_params = inner_params + [per_page, offset]
        paginated_invoice_nos = [
            row['invoice_no'] for row in conn.execute(f"""
                SELECT DISTINCT h.invoice_no
                FROM sales_invoice_header h
                {filter_where}
                ORDER BY h.invoice_date DESC, h.invoice_no DESC
                LIMIT ? OFFSET ?
            """, page_params).fetchall()
        ]

        invoices = {}
        if paginated_invoice_nos:
            placeholders = ','.join(['?'] * len(paginated_invoice_nos))

            for hdr in conn.execute(f"""
                SELECT h.invoice_no, h.invoice_date, h.customer_id,
                       c.customer_code, h.legend_id
                FROM sales_invoice_header h
                LEFT JOIN customers c ON c.customer_id = h.customer_id
                WHERE h.invoice_no IN ({placeholders})
            """, paginated_invoice_nos).fetchall():
                invoices[hdr['invoice_no']] = {
                    'header': dict(hdr),
                    'lines':  [],
                    'totals': {'total_amt': 0, 'gst_amt': 0, 'qty': 0}
                }

            for line in conn.execute(f"""
                SELECT l.invoice_no, l.line_no, l.product_id,
                       p.sku_no, p.hem_name, l.qty, l.total_amt, l.gst_amt
                FROM sales_invoice_line l
                LEFT JOIN products p ON p.product_id = l.product_id
                WHERE l.invoice_no IN ({placeholders})
                ORDER BY l.invoice_no, l.line_no
            """, paginated_invoice_nos).fetchall():
                inv = line['invoice_no']
                if inv in invoices:
                    invoices[inv]['lines'].append(dict(line))
                    invoices[inv]['totals']['total_amt'] += line['total_amt'] or 0
                    invoices[inv]['totals']['gst_amt']   += line['gst_amt']   or 0
                    invoices[inv]['totals']['qty']        += line['qty']       or 0

            invoices = {k: invoices[k] for k in paginated_invoice_nos if k in invoices}

        trend_rows = conn.execute(f"""
            SELECT substr(h.invoice_date, 1, 7)  AS month,
                   COALESCE(SUM(l.total_amt), 0) AS revenue
            FROM sales_invoice_header h
            LEFT JOIN sales_invoice_line l ON l.invoice_no = h.invoice_no
            {filter_where}
            GROUP BY month
            ORDER BY month
        """, inner_params).fetchall()
        trend_labels = [r['month'] or 'Unknown' for r in trend_rows]
        trend_data   = [round(float(r['revenue'] or 0), 2) for r in trend_rows]

        customers = conn.execute(
            "SELECT customer_id, customer_code FROM customers ORDER BY customer_code"
        ).fetchall()
        products = conn.execute(
            "SELECT DISTINCT product_id, sku_no, hem_name FROM products ORDER BY hem_name"
        ).fetchall()

    return render_template("dashboard.html",
        invoices=invoices,
        total_revenue=stats['total_revenue'],
        total_gst=stats['total_gst'],
        invoice_count=stats['total_invoices'],
        total_qty=stats['total_units'],
        inventory=products,
        customers=customers,
        current_page=page,
        total_pages=total_pages,
        search=search,
        start_date=start_date,
        end_date=end_date,
        trend_labels=trend_labels,
        trend_data=trend_data,
        role=session.get("role"))

@app.route("/create-invoice", methods=["POST"])
@require_staff
def create_invoice():
    """Create a new sales invoice with header and line items."""
    invoice_no = request.form.get("invoice_no", "").strip()
    invoice_date = request.form.get("invoice_date", "").strip()
    customer_id = request.form.get("customer_id", "").strip()
    legend_id = request.form.get("legend_id", "SGP").strip()
    product_id = request.form.get("product_id", "").strip()
    
    if not invoice_no or len(invoice_no) < 3:
        flash("Invoice number is required and must be at least 3 characters!", "danger")
        return redirect(url_for("dashboard"))
    
    if not invoice_date:
        flash("Invoice date is required!", "danger")
        return redirect(url_for("dashboard"))
    try:
        parsed_date = datetime.strptime(invoice_date, "%Y-%m-%d").date()
        if parsed_date > date.today():
            flash("Invoice date cannot be in the future!", "danger")
            return redirect(url_for("dashboard"))
    except ValueError:
        flash("Invalid date format!", "danger")
        return redirect(url_for("dashboard"))
    
    if not customer_id:
        flash("Customer selection is required!", "danger")
        return redirect(url_for("dashboard"))
    
    if not product_id:
        flash("Product selection is required!", "danger")
        return redirect(url_for("dashboard"))
    
    try:
        qty = int(request.form.get("qty", 0))
        if qty <= 0:
            flash("Quantity must be greater than 0!", "danger")
            return redirect(url_for("dashboard"))
    except ValueError:
        flash("Invalid quantity value!", "danger")
        return redirect(url_for("dashboard"))
    
    try:
        total_amt = float(request.form.get("total_amt", 0))
        if total_amt < 0:
            flash("Total amount cannot be negative!", "danger")
            return redirect(url_for("dashboard"))
    except ValueError:
        flash("Invalid total amount value!", "danger")
        return redirect(url_for("dashboard"))
    
    try:
        gst_amt = float(request.form.get("gst_amt", 0))
        if gst_amt < 0:
            flash("GST amount cannot be negative!", "danger")
            return redirect(url_for("dashboard"))
    except ValueError:
        flash("Invalid GST amount value!", "danger")
        return redirect(url_for("dashboard"))
    
    try:
        with get_db() as conn:
            existing = conn.execute("SELECT 1 FROM sales_invoice_header WHERE invoice_no = ?", (invoice_no,)).fetchone()
            if existing:
                flash(f"Invoice {invoice_no} already exists!", "danger")
                return redirect(url_for("dashboard"))

            cust_row = conn.execute(
                "SELECT customer_id FROM customers WHERE customer_code = ? COLLATE NOCASE",
                (customer_id,)
            ).fetchone()
            if cust_row:
                resolved_customer_id = cust_row['customer_id']
            else:
                cur = conn.execute(
                    "INSERT INTO customers (customer_code) VALUES (?)", (customer_id.upper(),)
                )
                resolved_customer_id = cur.lastrowid


            conn.execute(
                "INSERT INTO sales_invoice_header (invoice_no, invoice_date, customer_id, legend_id) VALUES (?, ?, ?, ?)",
                (invoice_no, invoice_date, resolved_customer_id, legend_id)
            )
            
            conn.execute("INSERT INTO sales_invoice_line (invoice_no, line_no, product_id, qty, total_amt, gst_amt) VALUES (?, 1, ?, ?, ?, ?)",
                        (invoice_no, product_id, qty, total_amt, gst_amt))
            
            conn.commit()
        
        with get_db() as verify_conn:
            verify = verify_conn.execute("SELECT * FROM sales_invoice_header WHERE invoice_no = ?", (invoice_no,)).fetchone()
            
            if verify:
                flash(f"Invoice {invoice_no} created successfully!", "success")
            else:
                flash(f"Invoice {invoice_no} creation failed - not saved!", "danger")
            
    except Exception as e:
        import traceback
        traceback.print_exc()
        flash(f"Error creating invoice: {str(e)}", "danger")
    
    return redirect(url_for("dashboard"))

@app.route("/delete-invoice/<invoice_no>", methods=["POST"])
@csrf.exempt
@require_staff
def delete_invoice(invoice_no):
    """Delete an invoice and all its line items."""
    
    try:
        with get_db() as conn:
            existing = conn.execute("SELECT * FROM sales_invoice_header WHERE invoice_no = ?", (invoice_no,)).fetchone()
            
            if not existing:
                return jsonify({
                    'success': False,
                    'message': f'Invoice {invoice_no} not found in database'
                }), 404
            
            
            deleted_lines = conn.execute("DELETE FROM sales_invoice_line WHERE invoice_no=?", (invoice_no,))
            
            deleted_header = conn.execute("DELETE FROM sales_invoice_header WHERE invoice_no=?", (invoice_no,))
            
            conn.commit()
        
        return jsonify({
            'success': True,
            'message': f'Invoice {invoice_no} deleted successfully'
        })
        
    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({
            'success': False,
            'message': f'Error deleting invoice: {str(e)}'
        }), 500

@app.route("/update-invoice/<invoice_no>", methods=["POST"])
@csrf.exempt
@require_staff
def update_invoice(invoice_no):
    """Update an existing invoice and its line items."""
    try:
        data = request.get_json()
        
        if not data:
            return jsonify({
                'success': False, 
                'message': 'No data provided'
            }), 400
        
        if not data.get('invoice_date'):
            return jsonify({'success': False, 'message': 'Invoice date is required'}), 400

        try:
            parsed_date = datetime.strptime(data['invoice_date'], "%Y-%m-%d").date()
            if parsed_date > date.today():
                return jsonify({'success': False, 'message': 'Invoice date cannot be in the future'}), 400
        except ValueError:
            return jsonify({'success': False, 'message': 'Invalid date format'}), 400

        if not data.get('customer_id'):
            return jsonify({'success': False, 'message': 'Customer is required'}), 400
        
        if not data.get('lines') or len(data['lines']) == 0:
            return jsonify({'success': False, 'message': 'At least one line item is required'}), 400
        
        for i, line in enumerate(data['lines']):
            if not line.get('product_id'):
                return jsonify({'success': False, 'message': f'Line {i+1}: Product is required'}), 400
            
            try:
                qty = int(line.get('qty', 0))
                if qty < 1:
                    return jsonify({'success': False, 'message': f'Line {i+1}: Quantity must be at least 1'}), 400
            except (ValueError, TypeError):
                return jsonify({'success': False, 'message': f'Line {i+1}: Invalid quantity'}), 400
            
            try:
                total_amt = float(line.get('total_amt', 0))
                if total_amt < 0:
                    return jsonify({'success': False, 'message': f'Line {i+1}: Total amount cannot be negative'}), 400
            except (ValueError, TypeError):
                return jsonify({'success': False, 'message': f'Line {i+1}: Invalid total amount'}), 400
            
            try:
                gst_amt = float(line.get('gst_amt', 0))
                if gst_amt < 0:
                    return jsonify({'success': False, 'message': f'Line {i+1}: GST amount cannot be negative'}), 400
            except (ValueError, TypeError):
                return jsonify({'success': False, 'message': f'Line {i+1}: Invalid GST amount'}), 400
        
        with get_db() as conn:
            existing = conn.execute("SELECT 1 FROM sales_invoice_header WHERE invoice_no = ?", (invoice_no,)).fetchone()
            if not existing:
                return jsonify({
                    'success': False,
                    'message': f'Invoice {invoice_no} not found'
                }), 404
            
            conn.execute("""
                UPDATE sales_invoice_header 
                SET invoice_date = ?, 
                    customer_id = ?, 
                    legend_id = ?
                WHERE invoice_no = ?
            """, (
                data['invoice_date'],
                data['customer_id'],
                data.get('legend_id', ''),
                invoice_no
            ))
            
            conn.execute("DELETE FROM sales_invoice_line WHERE invoice_no = ?", (invoice_no,))
            
            for line in data['lines']:
                conn.execute("""
                    INSERT INTO sales_invoice_line (
                        invoice_no, 
                        line_no, 
                        product_id, 
                        qty, 
                        total_amt, 
                        gst_amt
                    )
                    VALUES (?, ?, ?, ?, ?, ?)
                """, (
                    invoice_no,
                    line['line_no'],
                    line['product_id'],
                    line['qty'],
                    line['total_amt'],
                    line['gst_amt']
                ))
            
            conn.commit()
        
        return jsonify({
            'success': True,
            'message': 'Invoice updated successfully'
        })
        
    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({
            'success': False,
            'message': f'Server error: {str(e)}'
        }), 500

# === MARKET ANALYSIS ROUTES ===

def generate_ai_insights(kpis, top_products, top_customers, trend_data):
    """Generate AI-powered insights and recommendations using Groq API."""
    if not groq_client:
        return None
    
    try:
        top_product_share = (top_products[0]['revenue'] / kpis['revenue'] * 100) if top_products and kpis['revenue'] > 0 else 0
        top_customer_share = (top_customers[0]['revenue'] / kpis['revenue'] * 100) if top_customers and kpis['revenue'] > 0 else 0
        
        if top_products:
            product_detail = f"{top_products[0]['hem_name']} (SGD {top_products[0]['revenue']:.2f}, {top_product_share:.1f}% of revenue)"
        else:
            product_detail = "N/A (no product data available)"
        
        if top_customers:
            customer_detail = f"{top_customers[0]['customer_code']} (SGD {top_customers[0]['revenue']:.2f}, {top_customer_share:.1f}% of revenue, {top_customers[0]['orders']} orders)"
        else:
            customer_detail = "N/A (no customer data available)"
        
        data_summary = f"""
Sales Performance Data:
- Total Revenue: SGD {kpis['revenue']:.2f}
- Total Orders: {kpis['orders']}
- Units Sold: {kpis['units']:.2f}
- Average Order Value: SGD {kpis['aov']:.2f}
- GST Collected: SGD {kpis['gst']:.2f}

Top Product: {product_detail}
Top Customer: {customer_detail}

Revenue Trend: {len(trend_data['labels'])} months of data
"""

        response = groq_client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=[
                {
                    "role": "system",
                    "content": "You are a business analyst. Provide CONCISE, actionable insights. Each insight should be 1-2 SHORT sentences max. Be direct and specific with numbers."
                },
                {
                    "role": "user",
                    "content": f"""Analyze this sales data and provide:
1. SIX key strategic insights (1-2 SHORT sentences each, max 25 words)
2. Five specific, actionable recommendations (2-3 sentences each, max 40 words)

{data_summary}

Format your response as JSON:
{{
  "insights": [
    {{"title": "Short Title (2-4 words)", "description": "One concise sentence with a key metric or finding."}},
    ... (6 total)
  ],
  "recommendations": [
    {{"title": "Action Title (3-5 words)", "description": "Specific action with numbers/targets."}},
    ... (5 total)
  ]
}}

Be BRIEF and SPECIFIC. Focus on numbers and actionable insights."""
                }
            ],
            temperature=0.3,
            max_tokens=2000
        )
        
        ai_text = response.choices[0].message.content
        
        import re
        json_match = re.search(r'\{.*\}', ai_text, re.DOTALL)
        if json_match:
            ai_insights = json.loads(json_match.group())
            return ai_insights
        else:
            return None
            
    except Exception as e:
        return None

@app.route("/market-analysis")
@require_staff
def market_analysis():
    """Market analysis page with comprehensive business intelligence."""
    start = request.args.get("start", "").strip()
    end = request.args.get("end", "").strip()
    legend = request.args.get("legend", "").strip()

    with get_db() as conn:
        try:
            conn.execute("SELECT 1 FROM sales_invoice_header LIMIT 1;").fetchone()
            conn.execute("SELECT 1 FROM sales_invoice_line LIMIT 1;").fetchone()
        except Exception as e:
            return render_template("market_analysis.html", role=session.get("role"),
                error_message=f"Sales tables not found or empty. Error: {str(e)}",
                legends=[], selected={"start": start, "end": end, "legend": legend},
                kpis={"revenue": 0, "orders": 0, "units": 0, "aov": 0, "gst": 0},
                trend_labels=[], trend_revenue=[], top_products=[], top_customers=[])

        try:
            legends = [r["legend_id"] for r in conn.execute(
                "SELECT DISTINCT legend_id FROM sales_invoice_header WHERE legend_id IS NOT NULL AND legend_id != '' ORDER BY legend_id"
            ).fetchall()]
        except Exception as e:
            legends = []

        try:
            max_date_row = conn.execute("SELECT MAX(invoice_date) AS m FROM sales_invoice_header WHERE invoice_date IS NOT NULL").fetchone()
            min_date_row = conn.execute("SELECT MIN(invoice_date) AS m FROM sales_invoice_header WHERE invoice_date IS NOT NULL").fetchone()
            max_date = max_date_row["m"] if max_date_row else None
            min_date = min_date_row["m"] if min_date_row else None
            
            if not end and max_date:
                end = max_date
            
            if not start and end:
                start_row = conn.execute("SELECT date(?, '-365 day') AS d", (end,)).fetchone()
                start = start_row["d"] if start_row else min_date or ""
            elif not start and min_date:
                start = min_date
        except Exception as e:
            if not end:
                end = datetime.now().strftime("%Y-%m-%d")
            if not start:
                start = (datetime.now() - timedelta(days=365)).strftime("%Y-%m-%d")

        where = "WHERE h.invoice_date >= ? AND h.invoice_date <= ?"
        params = [start, end]

        if legend:
            where += " AND h.legend_id = ?"
            params.append(legend)

        try:
            kpi_row = conn.execute(f"""
                SELECT COALESCE(SUM(lines.total_amt), 0) AS revenue,
                       COALESCE(SUM(lines.gst_amt),   0) AS gst,
                       COUNT(DISTINCT lines.invoice_no) AS orders,
                       COALESCE(SUM(lines.qty),        0) AS units
                FROM (
                    SELECT DISTINCT l.invoice_no, l.line_no,
                           l.total_amt, l.gst_amt, l.qty
                    FROM sales_invoice_header h
                    JOIN sales_invoice_line l ON l.invoice_no = h.invoice_no
                    {where}
                ) AS lines
            """, params).fetchone()

            revenue = float(kpi_row["revenue"] or 0)
            gst     = float(kpi_row["gst"]     or 0)
            orders  = int(kpi_row["orders"]    or 0)
            units   = float(kpi_row["units"]   or 0)
            aov     = (revenue / orders) if orders else 0

            kpis = {
                "revenue": round(revenue, 2),
                "gst":     round(gst,     2),
                "orders":  orders,
                "units":   round(units,   2),
                "aov":     round(aov,     2)
            }

            trend_rows = conn.execute(f"""
                SELECT lines.ym,
                       COALESCE(SUM(lines.total_amt), 0) AS revenue
                FROM (
                    SELECT DISTINCT l.invoice_no, l.line_no,
                           substr(h.invoice_date, 1, 7) AS ym,
                           l.total_amt
                    FROM sales_invoice_header h
                    JOIN sales_invoice_line l ON l.invoice_no = h.invoice_no
                    {where}
                ) AS lines
                GROUP BY lines.ym
                ORDER BY lines.ym
            """, params).fetchall()

            trend_labels  = [r["ym"] for r in trend_rows if r["ym"]]
            trend_revenue = [float(r["revenue"] or 0) for r in trend_rows if r["ym"]]

            top_products_rows = conn.execute(f"""
                SELECT lines.product_id,
                       p.sku_no,
                       COALESCE(p.hem_name, 'Unknown') AS hem_name,
                       COALESCE(SUM(lines.total_amt), 0) AS revenue,
                       COALESCE(SUM(lines.qty),       0) AS units
                FROM (
                    SELECT DISTINCT l.invoice_no, l.line_no,
                           l.product_id, l.total_amt, l.qty
                    FROM sales_invoice_header h
                    JOIN sales_invoice_line l ON l.invoice_no = h.invoice_no
                    {where}
                ) AS lines
                LEFT JOIN products p ON p.product_id = lines.product_id
                GROUP BY lines.product_id, p.sku_no, hem_name
                ORDER BY revenue DESC
                LIMIT 10
            """, params).fetchall()

            top_products = [{
                "product_id": r["product_id"],
                "sku_no":     r["sku_no"],
                "hem_name":   r["hem_name"],
                "revenue":    round(float(r["revenue"] or 0), 2),
                "units":      round(float(r["units"]   or 0), 2)
            } for r in top_products_rows]

            top_customers_rows = conn.execute(f"""
                SELECT lines.customer_id,
                       COALESCE(c.customer_code, CAST(lines.customer_id AS TEXT)) AS customer_code,
                       COALESCE(SUM(lines.total_amt),      0) AS revenue,
                       COUNT(DISTINCT lines.invoice_no)      AS orders
                FROM (
                    SELECT DISTINCT l.invoice_no, l.line_no,
                           h.customer_id, l.total_amt
                    FROM sales_invoice_header h
                    JOIN sales_invoice_line l ON l.invoice_no = h.invoice_no
                    {where}
                ) AS lines
                LEFT JOIN customers c ON c.customer_id = lines.customer_id
                GROUP BY lines.customer_id, customer_code
                ORDER BY revenue DESC
                LIMIT 10
            """, params).fetchall()

            top_customers = [{
                "customer_id":   r["customer_id"],
                "customer_code": r["customer_code"],
                "revenue":       round(float(r["revenue"] or 0), 2),
                "orders":        int(r["orders"] or 0)
            } for r in top_customers_rows]

        except Exception as e:
            import traceback
            traceback.print_exc()
            return render_template("market_analysis.html", role=session.get("role"),
                error_message=f"Query error: {str(e)}", legends=legends,
                selected={"start": start, "end": end, "legend": legend},
                kpis={"revenue": 0, "orders": 0, "units": 0, "aov": 0, "gst": 0},
                trend_labels=[], trend_revenue=[], top_products=[], top_customers=[], ai_insights=None)

    ai_insights = generate_ai_insights(
        kpis=kpis,
        top_products=top_products,
        top_customers=top_customers,
        trend_data={"labels": trend_labels, "revenue": trend_revenue}
    )

    return render_template("market_analysis.html", role=session.get("role"), error_message="",
        legends=legends, selected={"start": start, "end": end, "legend": legend},
        kpis=kpis, trend_labels=trend_labels, trend_revenue=trend_revenue,
        top_products=top_products, top_customers=top_customers, ai_insights=ai_insights)

@app.route("/real-time-analytics")
@require_staff
def real_time_analytics():
    """Real-time analytics dashboard for monitoring current business metrics."""
    return render_template("real_time_analytics.html", role=session.get("role"))

# === PRODUCT IMAGE ROUTES ===
@app.route('/product-image/<filename>')
def serve_product_image(filename):
    """Serve product images from static/product_images_v2 folder."""
    images_dir = os.path.join(app.root_path, 'static', 'product_images_v2')
    return send_from_directory(images_dir, filename)

@app.route('/api/image-list')
def api_image_list():
    """Return list of all available product image filenames for frontend caching."""
    images_dir = os.path.join(app.root_path, 'static', 'product_images_v2')
    try:
        files = [f for f in os.listdir(images_dir) 
                 if f.lower().endswith(('.jpg', '.jpeg', '.png'))]
        return jsonify(files)
    except Exception as e:
        return jsonify([])

@app.route("/logout")
def logout():
    """Clear user session and redirect to customer cart page."""
    session.clear()
    return redirect(url_for("cart"))

# === APPLICATION ENTRY POINT ===
if __name__ == "__main__":
    with app.app_context():
        build_image_cache('product_images_v2')
    
    app.run(debug=True)