import sqlite3
from pathlib import Path
import streamlit as st

st.set_page_config(page_title="Buzzer Test w/ DB", layout="centered")

DB_PATH = Path(__file__).parent / "buzzer.db"

def get_conn():
    conn = sqlite3.connect(DB_PATH, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("""
        CREATE TABLE IF NOT EXISTS rounds (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            is_active INTEGER NOT NULL DEFAULT 1,
            winner_name TEXT,
            winner_time_utc TEXT
        )
    """)
    cur.execute("SELECT id FROM rounds WHERE is_active = 1 ORDER BY id DESC LIMIT 1")
    if cur.fetchone() is None:
        cur.execute("INSERT INTO rounds (is_active) VALUES (1)")
    conn.commit()
    conn.close()

init_db()

st.title("✅ Streamlit + SQLite is loading")
st.write(f"DB file: {DB_PATH}")

conn = get_conn()
cur = conn.cursor()
cur.execute("SELECT * FROM rounds WHERE is_active = 1 ORDER BY id DESC LIMIT 1")
row = cur.fetchone()
conn.close()

st.write("Active round row:", dict(row) if row else None)

