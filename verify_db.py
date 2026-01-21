import sqlite3

def check_db():
    try:
        conn = sqlite3.connect("database.db")
        cursor = conn.cursor()
        
        # Get list of tables
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
        tables = cursor.fetchall()
        
        print("Tables found in database.db:")
        for table in tables:
            print(f"- {table[0]}")
            
            # Get schema for each table
            cursor.execute(f"PRAGMA table_info({table[0]})")
            columns = cursor.fetchall()
            print("  Columns:")
            for col in columns:
                print(f"    {col[1]} ({col[2]})")
            print("")
            
        if not tables:
            print("No tables found.")
            
        conn.close()
    except Exception as e:
        print(f"Error checking database: {e}")

if __name__ == "__main__":
    check_db()
