# --------------------
# DB INIT (Updated to match database.py)
# --------------------
def init_db():
    with get_db() as conn:
        c = conn.cursor()
        c.execute("""
        CREATE TABLE IF NOT EXISTS users (
            user_id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            password_hash TEXT NOT NULL,
            role TEXT NOT NULL,
            active INTEGER DEFAULT 1
        )
        """)
        # Bootstrap superowner
        c.execute("SELECT 1 FROM users WHERE role='superowner'")
        if not c.fetchone():
            hashed_pw = generate_password_hash("changeme123")
            c.execute(
                "INSERT INTO users (username, password_hash, role, active) VALUES (?, ?, ?, 1)",
                ("superowner", hashed_pw, "superowner")
            )
        conn.commit()

# --------------------
# SUPEROWNER: USER MGMT (Fixed INSERT)
# --------------------
@app.route("/manage-users", methods=["GET", "POST"])
@require_roles("superowner")
def manage_users():
    message = ""
    if request.method == "POST":
        action = request.form.get("action")
        username = request.form.get("username", "").strip()

        with get_db() as conn:
            c = conn.cursor()
            if action == "add":
                password = request.form.get("password", "").strip()
                role = request.form.get("role", "employee")
                try:
                    # ✅ FIXED: Explicitly naming columns allows SQLite to handle 'user_id' automatically
                    c.execute("""
                        INSERT INTO users (username, password_hash, role, active) 
                        VALUES (?, ?, ?, 1)
                    """, (username, generate_password_hash(password), role))
                    message = f"User '{username}' added."
                except sqlite3.IntegrityError:
                    message = "Error: Username already exists."
            
            elif action == "toggle":
                c.execute("UPDATE users SET active = 1 - active WHERE username=?", (username,))
                message = "User status updated."
                
            elif action == "delete":
                if username == session.get("username"):
                    message = "Error: Cannot delete yourself."
                else:
                    c.execute("DELETE FROM users WHERE username=?", (username,))
                    message = "User deleted."
                    
            elif action == "change_role":
                new_role = request.form.get("new_role")
                c.execute("UPDATE users SET role=? WHERE username=?", (new_role, username))
                message = "Role updated."
            conn.commit()

    with get_db() as conn:
        # Note: selecting specific columns to match the template expectations
        users = conn.execute("SELECT username, role, active FROM users ORDER BY role, username").fetchall()
    
    return render_template("manage_users.html", users=users, message=message)