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

CREATE TABLE IF NOT EXISTS meta (
    key   TEXT PRIMARY KEY,
    value TEXT NOT NULL DEFAULT ''
);
"""

# Columns added after the first release. Applied to existing databases on connect —
# an operator who has been queueing posts for weeks must not lose them to an upgrade.
_ADDED_COLUMNS = {
    # The material connection that triggers an FTC disclosure requirement, if any.
    "material_connection": "TEXT NOT NULL DEFAULT ''",
    # Results pasted back after publishing, as JSON. The only way a draft-only agent
    # ever learns whether any of this worked.
    "results": "TEXT NOT NULL DEFAULT '{}'",
    "posted_at": "TEXT NOT NULL DEFAULT ''",
}

# Relationships that require a disclosure in the post itself (FTC Endorsement Guides).
# "none" is explicit rather than blank so an operator can record that they considered
# it and there is no connection.
MATERIAL_CONNECTIONS = ("", "none", "sponsored", "gifted", "affiliate", "employee", "partner", "own_product")


def db_path() -> Path:
    return data_dir() / DB_NAME


def _now() -> str:
    return datetime.now(UTC).isoformat(timespec="seconds")


def connect() -> sqlite3.Connection:
    """A connection with the schema applied and rows returned as mappings."""
    conn = sqlite3.connect(db_path())
    conn.row_factory = sqlite3.Row
    conn.executescript(_SCHEMA)
    _migrate(conn)
    return conn


def _migrate(conn: sqlite3.Connection) -> None:
    """Add columns introduced after a database was created.

    SQLite has no ``ADD COLUMN IF NOT EXISTS``, so compare against the live table.
    Cheap enough to run per connect, and it means an upgrade never asks the operator
    to choose between the new features and the queue they've already built.
    """
    have = {r["name"] for r in conn.execute("PRAGMA table_info(posts)")}
    for name, decl in _ADDED_COLUMNS.items():
        if name not in have:
            conn.execute(f"ALTER TABLE posts ADD COLUMN {name} {decl}")


def _row(r: sqlite3.Row) -> dict[str, Any]:
    d = dict(r)
    for key, default in (("assets", []), ("results", {})):
        try:
            d[key] = json.loads(d.get(key) or json.dumps(default))
        except json.JSONDecodeError:
            d[key] = default
    return d


# ── the queue hold (crisis stop) ─────────────────────────────────────────────
def hold(reason: str) -> dict[str, str]:
    """Stop the queue. Nothing scheduled should leave while this is set.

    The first move in a social crisis is to pause pre-scheduled content, because the
    damage isn't the crisis — it's the cheerful product post that goes out during it.
    This plugin doesn't publish, so the hold works on the thing it does own: the
    export pack refuses to build, and the calendar leads with the hold.
    """
    if not (reason or "").strip():
        raise ValueError("a hold needs a reason — whoever reads this later will need to know why")
    at = _now()
    with connect() as conn:
        conn.executemany(
            "INSERT INTO meta (key, value) VALUES (?, ?) ON CONFLICT(key) DO UPDATE SET value = excluded.value",
            [("hold_reason", reason.strip()), ("hold_since", at)],
        )
    return {"reason": reason.strip(), "since": at}


def release() -> bool:
    """Lift the hold. Returns False if there wasn't one."""
    held = hold_state() is not None
    with connect() as conn:
        conn.execute("DELETE FROM meta WHERE key IN ('hold_reason', 'hold_since')")
    return held


def hold_state() -> dict[str, str] | None:
    """The active hold, or None."""
    with connect() as conn:
        rows = {r["key"]: r["value"] for r in conn.execute("SELECT key, value FROM meta")}
    if not rows.get("hold_reason"):
        return None
    return {"reason": rows["hold_reason"], "since": rows.get("hold_since", "")}


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
    material_connection: str = "",
) -> dict[str, Any]:
    """Insert one post. Returns the stored row."""
    status = _valid_status(status)
    material_connection = _valid_connection(material_connection)
    now = _now()
    with connect() as conn:
        cur = conn.execute(
            "INSERT INTO posts (created, updated, platform, status, pillar, campaign, scheduled_for,"
            " title, body, hashtags, alt_text, assets, source, notes, score, material_connection)"
            " VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
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
                material_connection,
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
        "material_connection",
        "results",
        "posted_at",
    }
    sets, vals = [], []
    for key, val in fields.items():
        if key not in allowed or val is None:
            continue
        if key == "status":
            val = _valid_status(str(val))
        if key == "material_connection":
            val = _valid_connection(str(val))
        if key == "assets":
            val = json.dumps(val if isinstance(val, list) else [val])
        if key == "results":
            val = json.dumps(val if isinstance(val, dict) else {})
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


def _normalise(text: str) -> str:
    return " ".join((text or "").lower().split())


def find_similar(platform: str, body: str, *, threshold: float = 0.85) -> dict[str, Any] | None:
    """An existing open post on the same platform that says nearly the same thing.

    Guards the lint-and-fix loop. A writer whose draft comes back ``blocked`` has two
    options — edit the row, or write a new one — and the second is a strong instinct.
    Left unguarded, one post that fails the linter three times becomes four rows in
    the queue and the operator reviews the same copy four times.
    """
    text = _normalise(body)
    if len(text) < 40:  # too short to judge; ideas legitimately repeat
        return None
    from difflib import SequenceMatcher

    for row in list_posts(status="open", platform=platform, limit=200):
        other = _normalise(row.get("body", ""))
        if not other:
            continue
        # Cheap length gate before the O(n²) comparison.
        if not (0.7 <= len(other) / len(text) <= 1.4):
            continue
        if SequenceMatcher(None, text, other).ratio() >= threshold:
            return row
    return None


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


def record_results(post_id: int, results: dict[str, Any], *, posted_at: str = "") -> dict[str, Any] | None:
    """Attach real-world numbers to a published post, and mark it posted.

    Merges into whatever is already recorded, so adding week-two numbers doesn't
    discard week-one's. Non-numeric values are kept as-is — "what the operator
    noticed" is data too, and often better data than impressions.
    """
    row = get(post_id)
    if not row:
        return None
    merged = {**(row.get("results") or {}), **{k: v for k, v in (results or {}).items() if v not in (None, "")}}
    fields: dict[str, Any] = {"results": merged}
    if row["status"] != "posted":
        fields["status"] = "posted"
    if posted_at or not row.get("posted_at"):
        fields["posted_at"] = posted_at or _now()
    return update(post_id, **fields)


def with_results(*, platform: str = "", pillar: str = "", limit: int = 500) -> list[dict[str, Any]]:
    """Posted rows that actually carry numbers — the only ones worth analysing."""
    rows = [r for r in list_posts(status="posted", platform=platform, pillar=pillar, limit=limit) if r.get("results")]
    return rows


def _valid_status(status: str) -> str:
    s = (status or "").strip().lower()
    if s not in STATUSES:
        raise ValueError(f"unknown status {status!r} — use one of: {', '.join(STATUSES)}")
    return s


def _valid_connection(value: str) -> str:
    v = (value or "").strip().lower()
    if v not in MATERIAL_CONNECTIONS:
        raise ValueError(
            f"unknown material connection {value!r} — use one of: {', '.join(c for c in MATERIAL_CONNECTIONS if c)}"
        )
    return v
