"""Export the approved queue — the deliverable in a draft-only workflow.

Nothing here publishes. The agent's product is a pack the operator can work
through in ten minutes: each post ready to copy, in the order it should go out,
with its hashtags, alt text, and assets attached, and the platform's constraints
already satisfied.

Two shapes:

* ``markdown`` — a human working document. Each post's body sits in its own fenced
  block so a copy lifts exactly the characters that get pasted, with nothing else.
* ``csv`` — the column shape a scheduling tool or spreadsheet imports cleanly.

Host-free: stdlib only.
"""

from __future__ import annotations

import csv
import io
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from . import platforms
from .paths import data_dir

FORMATS = ("markdown", "csv")

CSV_COLUMNS = ["scheduled_for", "platform", "title", "body", "hashtags", "alt_text", "assets", "pillar", "campaign"]


def export_dir() -> Path:
    d = data_dir() / "exports"
    d.mkdir(parents=True, exist_ok=True)
    return d


def to_markdown(posts: list[dict[str, Any]], *, heading: str = "Approved posts") -> str:
    """A copy-paste pack, grouped by scheduled day then platform."""
    if not posts:
        return f"# {heading}\n\nNothing to export."

    lines = [f"# {heading}", "", f"{len(posts)} post(s). Generated {datetime.now(UTC):%Y-%m-%d %H:%M UTC}.", ""]

    current_day = object()  # sentinel so the first row always opens a section
    for post in posts:
        day = (post.get("scheduled_for") or "")[:10] or "Unscheduled"
        if day != current_day:
            current_day = day
            lines += ["", f"## {day}", ""]

        spec = platforms.get(post.get("platform", ""))
        label = spec.label if spec else post.get("platform", "?")
        slot = post.get("scheduled_for") or ""
        time_part = slot[11:16] if len(slot) > 11 else ""
        header = f"### {label}" + (f" · {time_part}" if time_part else "")
        if post.get("pillar"):
            header += f" · {post['pillar']}"
        lines.append(header)

        if post.get("title"):
            lines += ["", f"**Title:** {post['title']}"]

        body = post.get("body") or ""
        lines += ["", "```text", body, "```"]

        meta = []
        if post.get("hashtags"):
            meta.append(f"**Hashtags:** {post['hashtags']}")
        if post.get("alt_text"):
            meta.append(f"**Alt text:** {post['alt_text']}")
        assets = post.get("assets") or []
        if assets:
            meta.append("**Assets:** " + ", ".join(str(a) for a in assets))
        if post.get("source"):
            meta.append(f"**Source:** {post['source']}")
        if post.get("notes"):
            meta.append(f"**Notes:** {post['notes']}")
        chars = len(body)
        if spec:
            meta.append(f"_{chars:,}/{spec.max_chars:,} characters_")
        if meta:
            lines += [""] + meta

        lines.append("")

    return "\n".join(lines)


def to_csv(posts: list[dict[str, Any]]) -> str:
    """The column shape a spreadsheet or scheduling tool imports."""
    buf = io.StringIO()
    writer = csv.DictWriter(buf, fieldnames=CSV_COLUMNS, extrasaction="ignore", lineterminator="\n")
    writer.writeheader()
    for post in posts:
        row = {k: post.get(k, "") for k in CSV_COLUMNS}
        assets = post.get("assets") or []
        row["assets"] = "; ".join(str(a) for a in assets)
        writer.writerow(row)
    return buf.getvalue()


def render(posts: list[dict[str, Any]], fmt: str = "markdown", *, heading: str = "Approved posts") -> str:
    fmt = (fmt or "markdown").strip().lower()
    if fmt not in FORMATS:
        raise ValueError(f"unknown format {fmt!r} — use one of: {', '.join(FORMATS)}")
    return to_csv(posts) if fmt == "csv" else to_markdown(posts, heading=heading)


def write(posts: list[dict[str, Any]], fmt: str = "markdown", *, heading: str = "Approved posts") -> Path:
    """Render and save under the exports dir. Returns the file path."""
    text = render(posts, fmt, heading=heading)
    stamp = datetime.now(UTC).strftime("%Y%m%d-%H%M%S")
    ext = "csv" if fmt == "csv" else "md"
    out = export_dir() / f"social-{stamp}.{ext}"
    out.write_text(text, encoding="utf-8")
    return out
