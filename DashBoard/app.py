from flask import Flask, render_template, request, redirect, url_for
from db import db, DashboardGoal

app = Flask(__name__)
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///dashboard.db'
db.init_app(app)

with app.app_context():
    db.create_all()

@app.route('/')
def index():
    # 1. RETRIEVE: Showing all goals on the dashboard 
    goals = DashboardGoal.query.all()
    return render_template('dashboard.html', goals=goals)

@app.route('/add_goal', methods=['POST'])
def add_goal():
    # 2. CREATE: Adding a new target 
    name = request.form.get('goal_name')
    amount = request.form.get('target_amount')
    
    # FIELD VALIDATION: Ensures data consistency (Required for 'A') [cite: 77, 128]
    if not name or not amount or float(amount) <= 0:
        return "Error: Invalid Input", 400
        
    new_goal = DashboardGoal(goal_name=name, target_amount=float(amount))
    db.session.add(new_goal)
    db.session.commit()
    return redirect(url_for('index'))

@app.route('/update_goal/<int:id>', methods=['POST'])
def update_goal(id):
    # 3. UPDATE: Changing existing dashboard data 
    goal = DashboardGoal.query.get(id)
    goal.status = "Completed"
    db.session.commit()
    return redirect(url_for('index'))

@app.route('/delete_goal/<int:id>')
def delete_goal(id):
    # 4. DELETE: Removing old data 
    goal = DashboardGoal.query.get(id)
    db.session.delete(goal)
    db.session.commit()
    return redirect(url_for('index'))

if __name__ == '__main__':
    app.run(debug=True)