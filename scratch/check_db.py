import sqlite3
conn = sqlite3.connect('memory/data/memory.db')
cursor = conn.cursor()
cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
tables = [r[0] for r in cursor.fetchall()]
print("Tables:", tables)

# Check action_items columns
cursor.execute("PRAGMA table_info(action_items)")
cols = [r[1] for r in cursor.fetchall()]
print("action_items columns:", cols)
conn.close()
