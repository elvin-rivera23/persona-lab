from __future__ import annotations

import os
import sqlite3
import time
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path

# Resolve DB path; default to ./data/engagement.db relative to app root
DB_PATH = Path(os.getenv("ENGAGEMENT_DB_PATH", "./data/engagement.db"))
DATA_DIR = DB_PATH.parent


@contextmanager
def _conn() -> Iterator[sqlite3.Connection]:
    # Ensure directory exists (fixes "unable to open database file" in CI/container)
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(DB_PATH), timeout=5)
    try:
        conn.execute("PRAGMA foreign_keys = ON;")
        yield conn
        conn.commit()
    finally:
        conn.close()


def init() -> None:
    """Create required tables (idempotent)."""
    with _conn() as c:
        c.executescript(
            """
            CREATE TABLE IF NOT EXISTS interactions (
                id TEXT PRIMARY KEY
            );

            CREATE TABLE IF NOT EXISTS ab_interactions (
                interaction_id TEXT PRIMARY KEY,
                created_at INTEGER NOT NULL,
                session_id TEXT,
                ab_group TEXT NOT NULL,
                persona TEXT NOT NULL
            );

            CREATE INDEX IF NOT EXISTS idx_ab_interactions_created
            ON ab_interactions(created_at);
            """
        )


def record_interaction(
    interaction_id: str,
    ab_group: str,
    persona: str,
    session_id: str | None = None,
) -> None:
    """Insert parent id (for FK) + rich A/B attributes."""
    now = int(time.time())
    with _conn() as c:
        c.execute("INSERT OR IGNORE INTO interactions(id) VALUES (?);", (interaction_id,))
        c.execute(
            """
            INSERT OR REPLACE INTO ab_interactions(interaction_id, created_at, session_id, ab_group, persona)
            VALUES (?, ?, ?, ?, ?);
            """,
            (interaction_id, now, session_id, ab_group, persona),
        )


def _wilson_lower_bound(pos: int, n: int, z: float = 1.96) -> float:
    if n == 0:
        return 0.0
    p_hat = pos / n
    denom = 1 + (z**2) / n
    centre = p_hat + (z**2) / (2 * n)
    margin = z * ((p_hat * (1 - p_hat) + (z**2) / (4 * n)) / n) ** 0.5
    return max(0.0, (centre - margin) / denom)


def aggregate_with_feedback(limit_days: int = 30) -> list[dict]:
    """Join ab_interactions with feedback and compute aggregates per (group, persona)."""
    cutoff = int(time.time()) - limit_days * 86400
    with _conn() as c:
        rows = c.execute(
            """
            SELECT
              a.ab_group,
              a.persona,
              COUNT(f.id) AS n_fb,
              COALESCE(AVG(f.score), 0) AS avg_score,
              SUM(CASE WHEN f.score >= 4 THEN 1 ELSE 0 END) AS pos,
              SUM(CASE WHEN f.score <= 2 THEN 1 ELSE 0 END) AS neg
            FROM ab_interactions a
            LEFT JOIN feedback f ON f.interaction_id = a.interaction_id
            WHERE a.created_at >= ?
            GROUP BY a.ab_group, a.persona
            ORDER BY a.ab_group, a.persona;
            """,
            (cutoff,),
        ).fetchall()

    out: list[dict] = []
    for grp, persona, n_fb, avg_score, pos, neg in rows:
        n = int(n_fb or 0)
        pos = int(pos or 0)
        neg = int(neg or 0)
        lb = _wilson_lower_bound(pos, n)
        out.append(
            {
                "group": grp,
                "persona": persona,
                "n_feedback": n,
                "avg_score": float(avg_score or 0.0),
                "pos": pos,
                "neg": neg,
                "wilson_lb": lb,
            }
        )
    return out
