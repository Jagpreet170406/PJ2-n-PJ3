from flask import Flask, render_template, request, redirect, url_for, flash
from models import (
    init_db, get_all_parts, add_part, update_part,
    delete_part, compute_recommended_price
)

app = Flask(__name__)
app.secret_key = "secret123"  # change to anything

# ensure table exists
init_db()

@app.route("/")
def home():
    return redirect(url_for("dashboard"))

@app.route("/dashboard")
def dashboard():
    parts = get_all_parts()

    # simple stats for summary row
    total_items = len(parts)
    total_sales_sum = sum(p[4] or 0 for p in parts)
    avg_recommended = round(
        sum((p[9] or 0) for p in parts) / total_items, 2
    ) if total_items else 0

    stats = {
        "total_items": total_items,
        "total_sales": total_sales_sum,
        "avg_recommended": avg_recommended
    }

    return render_template("dashboard.html", parts=parts, stats=stats)

@app.route("/create", methods=["POST"])
def create():
    try:
        item_code = request.form["item_code"].strip()
        description = request.form.get("description", "").strip()
        qty_sold = int(request.form["qty_sold"] or 0)
        total_sales = float(request.form["total_sales"] or 0)
        period = request.form["period"].strip()

        competitor_price = float(request.form["competitor_price"] or 0)
        stock_qty = int(request.form["stock_qty"] or 0)
        demand_level = int(request.form["demand_level"] or 1)
    except ValueError:
        flash("Please enter valid numeric values.", "danger")
        return redirect(url_for("dashboard"))

    # basic validation
    if not item_code or not period:
        flash("Item Code and Period are required.", "danger")
        return redirect(url_for("dashboard"))

    if qty_sold <= 0 or total_sales <= 0:
        flash("Qty and Sales Value must be greater than 0.", "danger")
        return redirect(url_for("dashboard"))

    if demand_level < 1 or demand_level > 5:
        flash("Demand must be between 1 and 5.", "danger")
        return redirect(url_for("dashboard"))

    rec_price = compute_recommended_price(
        total_sales, qty_sold, competitor_price, stock_qty, demand_level
    )

    add_part(item_code, description, qty_sold, total_sales,
             period, competitor_price, stock_qty,
             demand_level, rec_price)

    flash("Item added successfully.", "success")
    return redirect(url_for("dashboard"))

@app.route("/update/<int:id>", methods=["POST"])
def update(id):
    try:
        item_code = request.form["item_code"].strip()
        description = request.form.get("description", "").strip()
        qty_sold = int(request.form["qty_sold"] or 0)
        total_sales = float(request.form["total_sales"] or 0)
        period = request.form["period"].strip()

        competitor_price = float(request.form["competitor_price"] or 0)
        stock_qty = int(request.form["stock_qty"] or 0)
        demand_level = int(request.form["demand_level"] or 1)
    except ValueError:
        flash("Please enter valid numeric values.", "danger")
        return redirect(url_for("dashboard"))

    if not item_code or not period:
        flash("Item Code and Period are required.", "danger")
        return redirect(url_for("dashboard"))

    if qty_sold <= 0 or total_sales <= 0:
        flash("Qty and Sales Value must be greater than 0.", "danger")
        return redirect(url_for("dashboard"))

    if demand_level < 1 or demand_level > 5:
        flash("Demand must be between 1 and 5.", "danger")
        return redirect(url_for("dashboard"))

    rec_price = compute_recommended_price(
        total_sales, qty_sold, competitor_price, stock_qty, demand_level
    )

    update_part(id, item_code, description, qty_sold, total_sales,
                period, competitor_price, stock_qty,
                demand_level, rec_price)

    flash("Item updated.", "success")
    return redirect(url_for("dashboard"))

@app.route("/delete/<int:id>", methods=["POST"])
def delete(id):
    delete_part(id)
    flash("Item deleted.", "success")
    return redirect(url_for("dashboard"))

if __name__ == "__main__":
    app.run(debug=True)
