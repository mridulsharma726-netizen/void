import sys
import os
sys.path.insert(0, os.path.abspath('server'))
import sqlite3
from backend.memory_sqlite import DB_FILE, get_all_preferences, get_all_facts

print("DB_FILE:", DB_FILE)
try:
    print("Preferences:", get_all_preferences())
except Exception as e:
    print("Error getting preferences:", e)

try:
    print("Facts:", get_all_facts())
except Exception as e:
    print("Error getting facts:", e)

try:
    conn = sqlite3.connect(str(DB_FILE))
    cursor = conn.cursor()
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
    print("Tables:", cursor.fetchall())
    cursor.execute("SELECT * FROM preferences;")
    print("Preferences rows:", cursor.fetchall())
    cursor.execute("SELECT * FROM facts;")
    print("Facts rows:", cursor.fetchall())
    conn.close()
except Exception as e:
    print("Direct sqlite connection error:", e)
