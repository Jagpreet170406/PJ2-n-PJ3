import sqlite3

DB_NAME = "sales.db"

def get_connection():
    return sqlite3.connect(DB_NAME)

def init_db():
    conn = get_connection()
    c = conn.cursor()
    c.execute("""
        CREATE TABLE IF NOT EXISTS parts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            item_code TEXT NOT NULL,
            description TEXT,
            qty_sold INTEGER,
            total_sales REAL,
            period TEXT,
            competitor_price REAL,
            stock_qty INTEGER,
            demand_level INTEGER,
            recommended_price REAL
        )
    """)
    conn.commit()
    conn.close()

def get_all_parts():
    conn = get_connection()
    c = conn.cursor()
    c.execute("SELECT * FROM parts ORDER BY period DESC, total_sales DESC")
    rows = c.fetchall()
    conn.close()
    return rows

def add_part(item_code, description, qty_sold, total_sales,
             period, competitor_price, stock_qty,
             demand_level, recommended_price):
    conn = get_connection()
    c = conn.cursor()
    c.execute("""
        INSERT INTO parts
        (item_code, description, qty_sold, total_sales,
         period, competitor_price, stock_qty,
         demand_level, recommended_price)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (item_code, description, qty_sold, total_sales,
          period, competitor_price, stock_qty,
          demand_level, recommended_price))
    conn.commit()
    conn.close()

def update_part(id, item_code, description, qty_sold, total_sales,
                period, competitor_price, stock_qty,
                demand_level, recommended_price):
    conn = get_connection()
    c = conn.cursor()
    c.execute("""
        UPDATE parts SET
        item_code=?, description=?, qty_sold=?, total_sales=?,
        period=?, competitor_price=?, stock_qty=?,
        demand_level=?, recommended_price=?
        WHERE id=?
    """, (item_code, description, qty_sold, total_sales,
          period, competitor_price, stock_qty,
          demand_level, recommended_price, id))
    conn.commit()
    conn.close()

def delete_part(id):
    conn = get_connection()
    c = conn.cursor()
    c.execute("DELETE FROM parts WHERE id=?", (id,))
    conn.commit()
    conn.close()

def compute_recommended_price(total_sales, qty_sold,
                              competitor_price, stock_qty,
                              demand_level):
    # base price from historical sales
    avg_price = (total_sales / qty_sold) if qty_sold else 0

    if competitor_price and avg_price:
        base = (avg_price + competitor_price) / 2
    elif competitor_price:
        base = competitor_price
    else:
        base = avg_price or 10  # fallback if no data

    # adjust by stock and demand
    if stock_qty and stock_qty > 100:
        base *= 0.95      # high stock, slightly cheaper
    if demand_level and demand_level >= 4:
        base *= 1.05      # high demand, slightly higher price

    return round(base, 2)

if __name__ == "__main__":
    init_db()
    print("Database initialised.")
