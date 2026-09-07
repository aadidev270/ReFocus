import sqlite3
from contextlib import contextmanager
from .config import DB_PATH

SCHEMA = """
CREATE TABLE IF NOT EXISTS settings (key TEXT PRIMARY KEY, value TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS captures (
 id INTEGER PRIMARY KEY AUTOINCREMENT, created_at TEXT NOT NULL, app_name TEXT NOT NULL,
 window_title TEXT NOT NULL, category TEXT NOT NULL, image_path TEXT, ocr_text TEXT NOT NULL DEFAULT '',
 ai_status TEXT NOT NULL DEFAULT 'pending', task_summary TEXT, next_action TEXT
);
CREATE TABLE IF NOT EXISTS interruptions (
 id INTEGER PRIMARY KEY AUTOINCREMENT, started_at TEXT NOT NULL, ended_at TEXT,
 category TEXT NOT NULL, duration_seconds INTEGER NOT NULL DEFAULT 0, resumed INTEGER NOT NULL DEFAULT 0
);
CREATE TABLE IF NOT EXISTS goals (
 id INTEGER PRIMARY KEY AUTOINCREMENT, title TEXT NOT NULL, goal_date TEXT NOT NULL,
 completed INTEGER NOT NULL DEFAULT 0, carry_forward INTEGER NOT NULL DEFAULT 0
);
"""
DEFAULTS = {"privacy_enabled": "false", "capture_interval": "20", "ollama_model": "llama3.2", "tesseract_path": ""}

@contextmanager
def connection():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()

def initialize():
    with connection() as conn:
        conn.executescript(SCHEMA)
        for key, value in DEFAULTS.items():
            conn.execute("INSERT OR IGNORE INTO settings(key,value) VALUES (?,?)", (key, value))
