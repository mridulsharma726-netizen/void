import sqlite3
import os

db_path = 'memory/data/memory.db'
if os.path.exists(db_path):
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    tables = cursor.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()
    print("Tables:", tables)
    for table in tables:
        t_name = table[0]
        try:
            rows = cursor.execute(f"SELECT * FROM {t_name} LIMIT 5").fetchall()
            print(f"\nTable {t_name} rows:")
            for r in rows:
                print(r)
        except Exception as e:
            print(f"Error reading {t_name}: {e}")
else:
    print("DB file not found")
