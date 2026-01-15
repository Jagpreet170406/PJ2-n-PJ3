from flask import Flask, render_template

app = Flask(__name__)

@app.route('/')
def home():
    return render_template('home.html')

@app.route('/inventory')
def inventory():
    return render_template('inventory.html')

@app.route("/cart")
def cart():
    return render_template("cart.html")

if __name__ == '__main__':
    app.run(debug=True)
