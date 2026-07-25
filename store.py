"""The content queue — every idea, draft, and approved post, in one SQLite file.

This is the spine of the draft-only workflow. The agent plans into it, drafts into
it, and lints into it; the operator reads the board, approves what's good, and
exports the approved set to publish by hand. Nothing here talks to a social network.

Statuses move in one direction most of the time:

    idea → drafted → needs_edit ⇄ drafted → approved → scheduled → posted
                                                     ↘ archived

``needs_edit`` exists so the editor subagent has somewhere to put a rejection with a
reason, instead of silently overwriting the writer's draft.

Host-free: only stdlib. Point ``SOCIAL_DIR`` at a temp dir to test.
"""

from __future__ import annotations

import json
import sqlite3
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

from .paths import data_dir

DB_NAME = "social.db"

# Board order — the console view renders columns in this order.
STATUSES = ("idea", "drafted", "needs_edit", "approved", "scheduled", "posted", "archived")

# Statuses that still need work from someone.
OPEN_STATUSES = ("idea", "drafted", "needs_edit")

_SCHEMA = """
CREATE TABLE IF NOT EXISTS posts (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    created       TEXT NOT NULL,
    updated       TEXT NOT NULL,
    platform      TEXT NOT NULL,
    status        TEXT NOT NULL,
    pillar        TEXT NOT NULL DEFAULT '',
    campaign      TEXT NOT NULL DEFAULT '',
    scheduled_for TEXT NOT NULL DEFAULT '',
    title         TEXT NOT NULL DEFAULT '',
    body          TEXT NOT NULL DEFAULT '',
    hashtags      TEXT NOT NULL DEFAULT '',
    alt_text      TEXT NOT NULL DEFAULT '',
    assets        TEXT NOT NULL DEFAULT '[]',
    source        TEXT NOT NULL DEFAULT '',
    notes         TEXT NOT NULL DEFAULT '',
    score         INTEGER NOT NULL DEFAULT 0
);
CREATE INDEX IF NOT EXISTS idx_posts_status ON posts(status);
CREATE INDEX IF NOT EXISTS idx_posts_sched  ON posts(scheduled_for);
"""


def db_path() -> Path:
    return data_dir() / DB_NAME


def _now() -> str:
    return datetime.now(UTC).isoformat(timespec="seconds")


def connect() -> sqlite3.Connection:
    """A connection with the schema applied and rows returned as mappings."""
    conn = sqlite3.connect(db_path())
    conn.row_factory = sqlite3.Row
    conn.executescript(_SCHEMA)
    return conn


def _row(r: sqlite3.Row) -> dict[str, Any]:
    d = dict(r)
    try:
        d["assets"] = json.loads(d.get("assets") or "[]")
    except json.JSONDecodeError:
        d["assets"] = []
    return d


def add(
    *,
    platform: str,
    body: str = "",
    status: str = "idea",
    pillar: str = "",
    campaign: str = "",
    scheduled_for: str = "",
    title: str = "",
    hashtags: str = "",
    alt_text: str = "",
    assets: list[str] | None = None,
    source: str = "",
    notes: str = "",
    score: int = 0,
) -> dict[str, Any]:
    """Insert one post. Returns the stored row."""
    status = _valid_status(status)
    now = _now()
    with connect() as conn:
        cur = conn.execute(
            "INSERT INTO posts (created, updated, platform, status, pillar, campaign, scheduled_for,"
            " title, body, hashtags, alt_text, assets, source, notes, score)"
            " VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
            (
                now,
                now,
                platform,
                status,
                pillar,
                campaign,
                scheduled_for,
                title,
                body,
                hashtags,
                alt_text,
                json.dumps(assets or []),
                source,
                notes,
                int(score),
            ),
        )
        new_id = cur.lastrowid
    return get(new_id)  # type: ignore[return-value]


def get(post_id: int) -> dict[str, Any] | None:
    with connect() as conn:
        row = conn.execute("SELECT * FROM posts WHERE id = ?", (post_id,)).fetchone()
    return _row(row) if row else None


def update(post_id: int, **fields: Any) -> dict[str, Any] | None:
    """Patch a post. Unknown keys are ignored so a model can't corrupt the schema."""
    allowed = {
        "platform",
        "status",
        "pillar",
        "campaign",
        "scheduled_for",
        "title",
        "body",
        "hashtags",
        "alt_text",
        "assets",
        "source",
        "notes",
        "score",
    }
    sets, vals = [], []
    for key, val in fields.items():
        if key not in allowed or val is None:
            continue
        if key == "status":
            val = _valid_status(str(val))
        if key == "assets":
            val = json.dumps(val if isinstance(val, list) else [val])
        if key == "score":
            val = int(val)
        sets.append(f"{key} = ?")
        vals.append(val)
    if not sets:
        return get(post_id)
    sets.append("updated = ?")
    vals.append(_now())
    vals.append(post_id)
    with connect() as conn:
        conn.execute(f"UPDATE posts SET {', '.join(sets)} WHERE id = ?", vals)
    return get(post_id)


def delete(post_id: int) -> bool:
    with connect() as conn:
        cur = conn.execute("DELETE FROM posts WHERE id = ?", (post_id,))
    return cur.rowcount > 0


def list_posts(
    *,
    status: str = "",
    platform: str = "",
    campaign: str = "",
    pillar: str = "",
    limit: int = 100,
) -> list[dict[str, Any]]:
    """Filtered list. Scheduled items sort by their slot, everything else newest-first."""
    where, vals = [], []
    if status:
        if status == "open":
            where.append(f"status IN ({','.join('?' * len(OPEN_STATUSES))})")
            vals.extend(OPEN_STATUSES)
        else:
            where.append("status = ?")
            vals.append(_valid_status(status))
    if platform:
        where.append("platform = ?")
        vals.append(platform)
    if campaign:
        where.append("campaign = ?")
        vals.append(campaign)
    if pillar:
        where.append("pillar = ?")
        vals.append(pillar)
    sql = "SELECT * FROM posts"
    if where:
        sql += " WHERE " + " AND ".join(where)
    # Empty scheduled_for sorts last, then by slot, then newest created.
    sql += " ORDER BY (scheduled_for = '') ASC, scheduled_for ASC, id DESC LIMIT ?"
    vals.append(max(1, int(limit)))
    with connect() as conn:
        rows = conn.execute(sql, vals).fetchall()
    return [_row(r) for r in rows]


def counts() -> dict[str, int]:
    """How many posts sit in each status — the board header."""
    with connect() as conn:
        rows = conn.execute("SELECT status, COUNT(*) AS n FROM posts GROUP BY status").fetchall()
    got = {r["status"]: r["n"] for r in rows}
    return {s: got.get(s, 0) for s in STATUSES}


def calendar(days: int = 14, start: str = "") -> list[dict[str, Any]]:
    """Scheduled posts inside a window, oldest first.

    ``start`` is an ISO date (defaults to today, UTC). Only rows with a
    ``scheduled_for`` inside the window come back — the point is to see the shape of
    the next fortnight, including the days with nothing in them.
    """
    days = max(1, int(days))
    begin = datetime.fromisoformat(start).date() if start else datetime.now(UTC).date()
    end = begin + timedelta(days=days)
    with connect() as conn:
        rows = conn.execute(
            "SELECT * FROM posts WHERE scheduled_for != '' AND scheduled_for >= ? AND scheduled_for < ?"
            " AND status NOT IN ('archived') ORDER BY scheduled_for ASC",
            (begin.isoformat(), end.isoformat()),
        ).fetchall()
    return [_row(r) for r in rows]


def pillar_balance(*, status: str = "", days: int = 0) -> dict[str, int]:
    """Post count per pillar — compare against the brand kit's target mix.

    ``days`` restricts to the scheduled window; 0 counts everything.
    """
    where, vals = ["status != 'archived'"], []
    if status:
        where = ["status = ?"]
        vals = [_valid_status(status)]
    if days:
        begin = datetime.now(UTC).date()
        end = begin + timedelta(days=max(1, int(days)))
        where.append("scheduled_for != '' AND scheduled_for >= ? AND scheduled_for < ?")
        vals.extend([begin.isoformat(), end.isoformat()])
    with connect() as conn:
        rows = conn.execute(
            f"SELECT COALESCE(NULLIF(pillar, ''), '(unassigned)') AS pillar, COUNT(*) AS n"
            f" FROM posts WHERE {' AND '.join(where)} GROUP BY 1 ORDER BY n DESC",
            vals,
        ).fetchall()
    return {r["pillar"]: r["n"] for r in rows}


def _valid_status(status: str) -> str:
    s = (status or "").strip().lower()
    if s not in STATUSES:
        raise ValueError(f"unknown status {status!r} — use one of: {', '.join(STATUSES)}")
    return s
