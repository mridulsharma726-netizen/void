import sqlite3

db_path = 'memory/data/memory.db'
conn = sqlite3.connect(db_path)
cursor = conn.cursor()
rows = cursor.execute("SELECT id, role, content, timestamp FROM history ORDER BY id DESC LIMIT 15").fetchall()
print("Chat History:")
for r in reversed(rows):
    role = r[1].upper()
    content = r[2].encode('ascii', errors='replace').decode('ascii')
    print(f"[{r[3]}] {role}: {content}")
