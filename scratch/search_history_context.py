import sqlite3

db_path = r"c:\Users\HP\OneDrive\Desktop\void\VOID\memory\data\memory.db"
conn = sqlite3.connect(db_path)
cursor = conn.cursor()
cursor.execute("SELECT * FROM history WHERE id BETWEEN 560 AND 580")
rows = cursor.fetchall()
for row in rows:
    print("Row:", row)
conn.close()
