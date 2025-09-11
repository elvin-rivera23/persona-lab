# app/ab_track.py
# Persist A/B interactions to SQLite alongside engagement, and satisfy
# feedback.interaction_id -> interactions(id) FK without altering legacy schema.

from __future__ import annotations

import os
import sqlite3
from contextlib import contextmanager
from datetime import UTC, datetime
from typing import Any

# Reuse your existing engagement DB
DB_PATH = os.getenv("ENGAGEMENT_DB_PATH", "./data/engagement.db")

DDL = """
-- Legacy parent table (exists already in your DB, usually with only id column).
-- We include IF NOT EXISTS for fresh setups; on existing DB, it will be ignored.
CREATE TABLE IF NOT EXISTS interactions (
    id TEXT PRIMARY KEY
);

-- Auxiliary AB table to hold rich attribution details.
CREATE TABLE IF NOT EXISTS ab_interactions (
    interaction_id TEXT PRIMARY KEY,
    created_at INTEGER NOT NULL,
    session_id TEXT,
    ab_group TEXT NOT NULL,
    persona   TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_ab_interactions_group_persona
  ON ab_interactions(ab_group, persona, created_at);
"""


@contextmanager
def _conn():
    conn = sqlite3.connect(DB_PATH)
    try:
        yield conn
    finally:
        conn.close()


def init():
    with _conn() as c:
        cur = c.cursor()
        cur.executescript(DDL)
        c.commit()


def record_interaction(
    interaction_id: str, ab_group: str, persona: str, session_id: str | None = None
) -> None:
    """
    Insert into interactions(id) ONLY (to satisfy FK) and into ab_interactions with details.
    This avoids altering legacy schema while preserving rich data for leaderboard.
    """
    ts = int(datetime.now(UTC).timestamp())
    with _conn() as c:
        cur = c.cursor()
        # Satisfy FK: ensure a row exists in interactions with the given id
        cur.execute(
            "INSERT OR IGNORE INTO interactions (id) VALUES (?)",
            (interaction_id,),
        )
        # Keep detailed record in our auxiliary table
        cur.execute(
            "INSERT OR REPLACE INTO ab_interactions (interaction_id, created_at, session_id, ab_group, persona) VALUES (?,?,?,?,?)",
            (interaction_id, ts, session_id, ab_group, persona),
        )
        c.commit()


def aggregate_with_feedback(limit_days: int = 30) -> list[dict[str, Any]]:
    """
    Join ab_interactions with feedback (which references interactions(id)) to compute aggregates.
    feedback schema (from engagement.py):
      feedback(id PK, created_at INTEGER epoch, session_id TEXT, interaction_id TEXT, score INTEGER, notes TEXT)
    """
    cutoff = int(datetime.now(UTC).timestamp()) - limit_days * 86400
    sql = """
    SELECT ai.ab_group, ai.persona,
           COUNT(f.id)                                AS n_feedback,
           AVG(CAST(f.score AS REAL))                 AS avg_score,
           SUM(CASE WHEN f.score >= 4 THEN 1 ELSE 0 END) AS pos,
           SUM(CASE WHEN f.score <= 2 THEN 1 ELSE 0 END) AS neg
      FROM ab_interactions ai
 LEFT JOIN feedback f
        ON f.interaction_id = ai.interaction_id
     WHERE ai.created_at >= ?
  GROUP BY ai.ab_group, ai.persona
  ORDER BY n_feedback DESC, avg_score DESC;
    """
    out: list[dict[str, Any]] = []
    with _conn() as c:
        cur = c.cursor()
        cur.execute(sql, (cutoff,))
        for row in cur.fetchall():
            ab_group, persona, n_feedback, avg_score, pos, neg = row
            n = int(n_feedback or 0)
            p = (pos or 0) / n if n > 0 else 0.0
            wilson = _wilson_lower_bound(p, n)
            out.append(
                {
                    "group": ab_group,
                    "persona": persona,
                    "n_feedback": n,
                    "avg_score": float(avg_score) if avg_score is not None else None,
                    "pos": int(pos or 0),
                    "neg": int(neg or 0),
                    "wilson_lb": wilson,
                }
            )
    return out


def _wilson_lower_bound(p_hat: float, n: int, z: float = 1.96) -> float:
    # 95% Wilson lower bound for a binomial proportion (robust at low N)
    if n == 0:
        return 0.0
    denom = 1 + z * z / n
    center = p_hat + z * z / (2 * n)
    margin = z * ((p_hat * (1 - p_hat) / n + z * z / (4 * n * n)) ** 0.5)
    return max(0.0, (center - margin) / denom)
