import os
import sqlite3
import time
import uuid
from typing import Any

# What it does:
# - Minimal SQLite layer for feedback writes, table init, and summary reads.
# Why needed:
# - Capture engagement with zero external deps; expose simple reward metrics.
# Pitfalls:
# - SQLite is single-writer. Fine for our scale; migrate to Postgres later if needed.

DEFAULT_DB_PATH = "./data/engagement.db"


def _get_db_path() -> str:
    return os.getenv("DB_PATH", DEFAULT_DB_PATH)


def _connect() -> sqlite3.Connection:
    # isolation_level=None gives autocommit-like behavior
    conn = sqlite3.connect(_get_db_path(), timeout=5, isolation_level=None)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL;")
    conn.execute("PRAGMA foreign_keys=ON;")
    return conn


def init_db() -> None:
    conn = _connect()
    try:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS interactions (
              id TEXT PRIMARY KEY,
              session_id TEXT,
              route TEXT,
              prompt TEXT,
              response_preview TEXT,
              ts INTEGER
            );
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS feedback (
              id TEXT PRIMARY KEY,
              interaction_id TEXT,
              session_id TEXT,
              score INTEGER,            -- 1..5
              notes TEXT,
              ts INTEGER,
              FOREIGN KEY (interaction_id) REFERENCES interactions(id)
            );
            """
        )
        # Lightweight indices for reads
        conn.execute("CREATE INDEX IF NOT EXISTS idx_feedback_ts ON feedback(ts);")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_feedback_session ON feedback(session_id);")
    finally:
        conn.close()


def insert_feedback(
    interaction_id: str | None,
    session_id: str | None,
    score: int,
    notes: str | None,
) -> str:
    fid = str(uuid.uuid4())
    ts = int(time.time())
    conn = _connect()
    try:
        conn.execute(
            """
            INSERT INTO feedback (id, interaction_id, session_id, score, notes, ts)
            VALUES (?, ?, ?, ?, ?, ?);
            """,
            (fid, interaction_id, session_id, score, notes, ts),
        )
    finally:
        conn.close()
    return fid


def get_feedback_summary(window_seconds: int | None = None) -> dict[str, Any]:
    """
    Returns counts and average score; if window_seconds is provided,
    only consider rows with ts >= now - window_seconds.
    """
    now = int(time.time())
    cutoff = None
    params: tuple[Any, ...]
    if window_seconds is not None and window_seconds > 0:
        cutoff = now - window_seconds
        where = "WHERE ts >= ?"
        params = (cutoff,)
    else:
        where = ""
        params = ()

    conn = _connect()
    try:
        # Count + average
        row = conn.execute(
            f"SELECT COUNT(*) AS n, AVG(score) AS avg_score FROM feedback {where};",
            params,
        ).fetchone()
        n = row["n"] or 0
        avg_score = float(row["avg_score"]) if row["avg_score"] is not None else None

        # Histogram 1..5
        hist = {str(k): 0 for k in range(1, 6)}
        for r in conn.execute(
            f"SELECT score, COUNT(*) AS c FROM feedback {where} GROUP BY score;",
            params,
        ).fetchall():
            hist[str(r["score"])] = r["c"]

        out: dict[str, Any] = {
            "count": n,
            "avg_score": avg_score,
            "histogram": hist,
            "window_seconds": window_seconds,
            "as_of": now,
        }
        if cutoff:
            out["cutoff_ts"] = cutoff
        return out
    finally:
        conn.close()


def get_recent_feedback(limit: int = 10) -> list[dict[str, Any]]:
    """
    Returns the most recent feedback entries (id, session_id, score, notes, ts).
    """
    limit = max(1, min(limit, 200))
    conn = _connect()
    try:
        rows = conn.execute(
            "SELECT id, interaction_id, session_id, score, notes, ts "
            "FROM feedback ORDER BY ts DESC LIMIT ?;",
            (limit,),
        ).fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()
