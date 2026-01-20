import sqlite3

conn = sqlite3.connect("database.db")
cursor = conn.cursor()

print("Database created successfully")

conn.close()

