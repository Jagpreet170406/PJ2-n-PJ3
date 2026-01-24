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
    return render_template('cart.html')

@app.route("/zhenghong")
def zhenghong():
    return render_template("zhenghong.html")

@app.route("/nabil2.html")
def nabil2():
    return render_template("nabil2.html")

@app.route('/test-image')
def test_image():
    return '<img src="/static/images/logo.png" alt="test">'

if __name__ == '__main__':
    app.run(debug=True)
