import json
import os
import sqlite3

json_path = r"c:\Users\HP\OneDrive\Desktop\void\VOID\memory\data\memory.json"
db_path = r"c:\Users\HP\OneDrive\Desktop\void\VOID\memory\data\memory.db"

if os.path.exists(json_path):
    print("Searching json...")
    with open(json_path, "r", encoding="utf-8", errors="ignore") as f:
        data = f.read()
    if "science, technology, culture" in data or "assist with that" in data:
        print("Found in json!")
        try:
            parsed = json.loads(data)
            # print some context
            for k, v in parsed.items():
                if isinstance(v, str) and ("assist with that" in v or "science, technology" in v):
                    print(f"Key: {k}, Value: {v}")
                elif isinstance(v, list):
                    for item in v:
                        if isinstance(item, str) and ("assist with that" in item or "science, technology" in item):
                            print(f"List item: {item}")
                        elif isinstance(item, dict):
                            for ik, iv in item.items():
                                if isinstance(iv, str) and ("assist with that" in iv or "science, technology" in iv):
                                    print(f"Dict item {ik}: {iv}")
        except Exception as e:
            print("Failed to parse json:", e)

if os.path.exists(db_path):
    print("Searching db...")
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
    tables = cursor.fetchall()
    for table_name in tables:
        t_name = table_name[0]
        cursor.execute(f"PRAGMA table_info({t_name})")
        columns = [col[1] for col in cursor.fetchall()]
        cursor.execute(f"SELECT * FROM {t_name}")
        rows = cursor.fetchall()
        for row in rows:
            for i, val in enumerate(row):
                if isinstance(val, str) and ("assist with that" in val or "science, technology" in val):
                    print(f"Found in Table: {t_name}, Col: {columns[i]}")
                    print("Val:", val)
    conn.close()
