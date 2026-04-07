import sqlite3
from datetime import datetime
import os
from core.config import DB_PATH

def init_db():
    """Initialize the SQLite database and create the memory table if it doesn't exist."""
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS memory (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp TEXT,
            key TEXT,
            value TEXT
        )
    ''')
    conn.commit()
    conn.close()

def save_memory(key, value):
    """Save a key-value pair to memory with current timestamp."""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    timestamp = datetime.now().isoformat()
    cursor.execute('INSERT INTO memory (timestamp, key, value) VALUES (?, ?, ?)', (timestamp, key, value))
    conn.commit()
    conn.close()

def search_memory(keyword, limit=5):
    """Search memory for entries containing the keyword in key or value, return last limit entries."""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute('''
        SELECT timestamp, key, value FROM memory
        WHERE key LIKE ? OR value LIKE ?
        ORDER BY id DESC
        LIMIT ?
    ''', (f'%{keyword}%', f'%{keyword}%', limit))
    results = cursor.fetchall()
    conn.close()
    return results
