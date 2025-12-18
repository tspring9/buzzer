import sqlite3
from pathlib import Path
from datetime import datetime, timezone

import streamlit as st

st.set_page_config(page_title="Jeopardy Buzzer", layout="centered")

DB_PATH = Path(__file__).parent / "buzzer.db"


# -----------------------
# DB helpers
# -----------------------
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

    cur.execute("""
        CREATE TABLE IF NOT EXISTS buzz_log (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            round_id INTEGER NOT NULL,
            player_name TEXT NOT NULL,
            buzz_time_utc TEXT NOT NULL,
            was_winner INTEGER NOT NULL DEFAULT 0,
            FOREIGN KEY (round_id) REFERENCES rounds(id)
        )
    """)

    cur.execute("SELECT id FROM rounds WHERE is_active = 1 ORDER BY id DESC LIMIT 1")
    if cur.fetchone() is None:
        cur.execute("INSERT INTO rounds (is_active) VALUES (1)")

    conn.commit()
    conn.close()


def get_active_round(conn):
    cur = conn.cursor()
    cur.execute("SELECT * FROM rounds WHERE is_active = 1 ORDER BY id DESC LIMIT 1")
    return cur.fetchone()


def utc_now_iso():
    return datetime.now(timezone.utc).isoformat(timespec="milliseconds")


# -----------------------
# Buzzer logic (atomic)
# -----------------------
def attempt_buzz(player_name: str) -> tuple[bool, str]:
    player_name = (player_name or "").strip()
    if not player_name:
        return False, "Enter your name first."

    conn = get_conn()
    cur = conn.cursor()

    try:
        cur.execute("BEGIN IMMEDIATE")  # lock for write

        rnd = get_active_round(conn)
        if rnd is None:
            cur.execute("INSERT INTO rounds (is_active) VALUES (1)")
            round_id = cur.lastrowid
            winner_name = None
        else:
            round_id = rnd["id"]
            winner_name = rnd["winner_name"]

        buzz_time = utc_now_iso()

        # Log attempt, capture row id
        cur.execute(
            "INSERT INTO buzz_log (round_id, player_name, buzz_time_utc, was_winner) VALUES (?, ?, ?, 0)",
            (round_id, player_name, buzz_time),
        )
        log_id = cur.lastrowid

        if winner_name:
            conn.commit()
            return False, f"Too late - {winner_name} already buzzed first."

        # Claim winner
        cur.execute(
            "UPDATE rounds SET winner_name = ?, winner_time_utc = ? WHERE id = ? AND winner_name IS NULL",
            (player_name, buzz_time, round_id),
        )

        # Mark THIS log row as winner
        cur.execute("UPDATE buzz_log SET was_winner = 1 WHERE id = ?", (log_id,))

        conn.commit()
        return True, "You buzzed in FIRST!"

    except sqlite3.Error as e:
        try:
            conn.rollback()
        except Exception:
            pass
        return False, f"Database error: {e}"
    finally:
        conn.close()
