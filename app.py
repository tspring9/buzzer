import sqlite3
import time
from datetime import datetime, timezone

import streamlit as st

DB_PATH = "buzzer.db"


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

    # One row represents the "active question/round"
    cur.execute("""
        CREATE TABLE IF NOT EXISTS rounds (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            is_active INTEGER NOT NULL DEFAULT 1,
            winner_name TEXT,
            winner_time_utc TEXT
        )
    """)

    # Optional: record all buzz attempts for auditing/fun
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

    # Ensure there is exactly one active round
    cur.execute("SELECT id FROM rounds WHERE is_active = 1 ORDER BY id DESC LIMIT 1")
    row = cur.fetchone()
    if row is None:
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
    """
    Returns (won, message).
    Uses a transaction to guarantee only one winner.
    """
    player_name = (player_name or "").strip()
    if not player_name:
        return False, "Enter your name first."

    conn = get_conn()
    cur = conn.cursor()

    try:
        # Lock DB for write so two buzzers don't both win.
        cur.execute("BEGIN IMMEDIATE")

        rnd = get_active_round(conn)
        if rnd is None:
            # Extremely unlikely, but recover gracefully
            cur.execute("INSERT INTO rounds (is_active) VALUES (1)")
            round_id = cur.lastrowid
            winner_name = None
        else:
            round_id = rnd["id"]
            winner_name = rnd["winner_name"]

        buzz_time = utc_now_iso()

        # Always log the attempt
        cur.execute(
            "INSERT INTO buzz_log (round_id, player_name, buzz_time_utc, was_winner) VALUES (?, ?, ?, 0)",
            (round_id, player_name, buzz_time),
        )

        if winner_name:
            conn.commit()
            return False, f"Too late — {winner_name} already buzzed first."

        # Claim winner
        cur.execute(
            "UPDATE rounds SET winner_name = ?, winner_time_utc = ? WHERE id = ? AND winner_name IS NULL",
            (player_name, buzz_time, round_id),
        )

        # Mark most recent log row for this player as winner (nice-to-have)
        cur.execute(
            "UPDATE buzz_log SET was_winner = 1 WHERE id = (SELECT id FROM buzz_log ORDER BY id DESC LIMIT 1)"
        )

        conn.commit()
        return True, "✅ You buzzed in FIRST!"

    except sqlite3.Error as e:
        try:
            conn.rollback()
        except Exception:
            pass
        return False, f"Database error: {e}"
    finally:
        conn.close()


def reset_round() -> None:
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("BEGIN IMMEDIATE")
    # Deactivate current round
    cur.execute("UPDATE rounds SET is_active = 0 WHERE is_active = 1")
    # Create new active round
    cur.execute("INSERT INTO rounds (is_active) VALUES (1)")
    conn.commit()
    conn.close()


# -----------------------
# UI Pages
# -----------------------
def page_player():
    st.title("📣 Jeopardy Buzzer — Player")

    player_name = st.text_input("Your name", value=st.session_state.get("player_name", ""))
    st.session_state["player_name"] = player_name

    st.markdown("###")

    col1, col2 = st.columns([2, 1])
    with col1:
        buzz = st.button("🔴 BUZZ!", use_container_width=True)
    with col2:
        st.caption("Tip: keep this tab open.")

    if buzz:
        won, msg = attempt_buzz(player_name)
        if won:
            st.success(msg)
            st.balloons()
        else:
            st.warning(msg)

    # Show current state (polling)
    st.markdown("---")
    conn = get_conn()
    rnd = get_active_round(conn)
    conn.close()

    if rnd and rnd["winner_name"]:
        st.info(f"Current winner: **{rnd['winner_name']}**")
    else:
        st.info("No one has buzzed yet.")


def page_admin():
    st.title("🧑‍💼 Jeopardy Buzzer — Admin")

    # Lightweight "admin pin" (not enterprise security)
    admin_pin = st.text_input("Admin PIN", type="password")
    expected = st.secrets.get("ADMIN_PIN", "1234")  # set in .streamlit/secrets.toml for real usage

    if admin_pin != expected:
        st.warning("Enter the Admin PIN to continue.")
        st.stop()

    conn = get_conn()
    rnd = get_active_round(conn)

    st.subheader("Current Round")
    if rnd and rnd["winner_name"]:
        st.success(f"Winner: **{rnd['winner_name']}**")
        st.caption(f"Buzz time (UTC): {rnd['winner_time_utc']}")
    else:
        st.info("No buzz yet.")

    colA, colB = st.columns([1, 2])
    with colA:
        if st.button("♻️ Reset for Next Question", use_container_width=True):
            reset_round()
            st.success("Round reset.")
            st.rerun()

    st.markdown("---")
    st.subheader("Buzz Log (latest first)")
    cur = conn.cursor()
    cur.execute("""
        SELECT round_id, player_name, buzz_time_utc, was_winner
        FROM buzz_log
        ORDER BY id DESC
        LIMIT 50
    """)
    rows = cur.fetchall()
    conn.close()

    if rows:
        st.dataframe(
            [
                {
                    "round": r["round_id"],
                    "player": r["player_name"],
                    "time_utc": r["buzz_time_utc"],
                    "winner": "✅" if r["was_winner"] else ""
                }
                for r in rows
            ],
            use_container_width=True,
            hide_index=True
        )
    else:
        st.caption("No buzzes recorded yet.")


# -----------------------
# App entry
# -----------------------
def main():
    init_db()

    # Simple routing
    st.sidebar.title("Navigation")
    mode = st.sidebar.radio("Mode", ["Player", "Admin"])

    # Optional auto-refresh so admin sees buzzes without manual refresh
    refresh_ms = st.sidebar.slider("Auto-refresh (ms)", 0, 3000, 750, step=250)
    if refresh_ms > 0:
        st.markdown(f"<meta http-equiv='refresh' content='{refresh_ms/1000}'>", unsafe_allow_html=True)

    if mode == "Player":
        page_player()
    else:
        page_admin()


if __name__ == "__main__":
    main()