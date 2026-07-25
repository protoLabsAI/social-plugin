"""Platform norms — dated, sourced, and owned by the operator rather than compiled in.

A norm is anything that makes a post perform well or badly without the platform ever
rejecting it: the length band that lands, how many hashtags read as native, whether
the ranking demotes an external link, where the "…more" fold falls, what reliably
flops. All of it drifts as the platforms retune, which is exactly why none of it is a
constant in the source — a compiled-in norm states last year's folklore as fact and
needs a plugin release to correct.

Instead the agent researches a platform, records what it found **with its sources and
the date**, and the file lives beside the brand kit where the operator can read, edit,
or delete it. Three consequences worth stating plainly:

* A norm on file is always attributable — you can check where it came from.
* A norm on file is always dated, so staleness is visible instead of assumed.
* No norms on file means the linter says so and checks hard limits only. It never
  invents a number to fill the gap.

Precedence when a draft is linted: the brand kit's ``platforms:`` house rules beat
researched norms, which beat nothing. What the operator decided outranks what the
agent read.

Host-free: stdlib + yaml.
"""

from __future__ import annotations

from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any

import yaml

from .paths import data_dir

FILENAME = "platform-norms.yaml"

# Past this, a norm is old enough that the agent should re-check before trusting it.
STALE_AFTER_DAYS = 180

ALT_TEXT_LEVELS = ("expected", "recommended", "n/a")

# The keys the linter and the drafting brief understand. Anything else an operator
# adds is preserved untouched — this is their file, not ours.
KNOWN_KEYS = (
    "checked",
    "sources",
    "sweet_spot",
    "hashtag_norm",
    "fold",
    "link_penalty",
    "link_workaround",
    "alt_text",
    "hook",
    "native_shape",
    "flops",
    "notes",
)


def today() -> date:
    """The clock this module stamps and measures against.

    UTC, matching the queue's timestamps. Exposed rather than inlined so callers and
    tests measure age against the same day boundary the stamp was written on —
    comparing a UTC stamp to a local ``date.today()`` silently shifts every age by a
    day near midnight.
    """
    return datetime.now(timezone.utc).date()


def path() -> Path:
    return data_dir() / FILENAME


def exists() -> bool:
    return path().is_file()


def load() -> dict[str, Any]:
    """Every platform's norms. An unreadable file raises rather than silently
    reverting the agent to guesswork."""
    p = path()
    if not p.is_file():
        return {}
    raw = yaml.safe_load(p.read_text(encoding="utf-8"))
    if raw is None:
        return {}
    if not isinstance(raw, dict):
        raise ValueError(f"{p} must be a YAML mapping of platform -> norms, got {type(raw).__name__}")
    return raw


def save(data: dict[str, Any]) -> Path:
    p = path()
    p.parent.mkdir(parents=True, exist_ok=True)
    tmp = p.with_suffix(p.suffix + ".tmp")
    tmp.write_text(yaml.safe_dump(data, sort_keys=True, allow_unicode=True, width=100), encoding="utf-8")
    tmp.replace(p)
    return p


def get(platform: str) -> dict[str, Any] | None:
    """One platform's norms, or None when it's never been researched."""
    from . import platforms

    try:
        row = load().get(platforms.normalize(platform))
    except ValueError:
        return None
    return row if isinstance(row, dict) else None


def validate(row: dict[str, Any]) -> list[str]:
    """Check one platform's norms. 'error:' entries block the write."""
    out: list[str] = []
    if not isinstance(row, dict):
        return ["error: norms must be a mapping of key: value"]

    sources = row.get("sources")
    if not sources or not isinstance(sources, list) or not [s for s in sources if str(s).strip()]:
        out.append("error: `sources` is required and must be a non-empty list — an unattributable norm is a guess")

    for key in ("sweet_spot", "hashtag_norm"):
        val = row.get(key)
        if val is None:
            continue
        if not isinstance(val, (list, tuple)) or len(val) != 2:
            out.append(f"error: `{key}` must be a two-item list [min, max]")
            continue
        try:
            lo, hi = int(val[0]), int(val[1])
        except (TypeError, ValueError):
            out.append(f"error: `{key}` values must be whole numbers")
            continue
        if lo < 0 or hi < lo:
            out.append(f"error: `{key}` must be [min, max] with 0 <= min <= max, got {val}")

    fold = row.get("fold")
    if fold is not None:
        try:
            if int(fold) < 0:
                out.append("error: `fold` must be a positive character position (or omitted)")
        except (TypeError, ValueError):
            out.append("error: `fold` must be a whole number of characters")

    if row.get("link_penalty") is not None and not isinstance(row.get("link_penalty"), bool):
        out.append("error: `link_penalty` must be true or false")

    alt = row.get("alt_text")
    if alt is not None and str(alt).strip().lower() not in ALT_TEXT_LEVELS:
        out.append(f"error: `alt_text` must be one of {', '.join(ALT_TEXT_LEVELS)}")

    if row.get("link_penalty") and not str(row.get("link_workaround", "")).strip():
        out.append("warn: `link_penalty` is set but there's no `link_workaround` — the linter can't suggest a fix")

    return out


def record(platform: str, row: dict[str, Any], *, checked: str = "") -> dict[str, Any]:
    """Store one platform's researched norms, stamped with today's date.

    Merges into whatever is already on file for that platform, so a run that only
    re-checked the hashtag norm doesn't wipe the rest. Raises on a fatal problem —
    most importantly a missing ``sources``.
    """
    from . import platforms

    pid = platforms.normalize(platform)
    if platforms.get(pid) is None:
        raise ValueError(f"unknown platform {platform!r} — use one of: {', '.join(platforms.known())}")

    incoming = {k: v for k, v in (row or {}).items() if v is not None and v != ""}
    existing = get(pid) or {}
    merged = {**existing, **incoming}
    merged["checked"] = checked or today().isoformat()

    fatal = [p for p in validate(merged) if p.startswith("error:")]
    if fatal:
        raise ValueError("; ".join(fatal))

    all_norms = load()
    all_norms[pid] = merged
    save(all_norms)
    return merged


def record_yaml(platform: str, text: str, *, checked: str = "") -> dict[str, Any]:
    """Record norms supplied as a small YAML document."""
    parsed = yaml.safe_load(text or "")
    if parsed is None:
        raise ValueError("no norms supplied")
    if not isinstance(parsed, dict):
        raise ValueError("norms must be a YAML mapping (key: value pairs)")
    return record(platform, parsed, checked=checked)


def age_days(platform: str, *, as_of: date | None = None) -> int | None:
    """How long since this platform's norms were checked, or None if never."""
    row = get(platform)
    if not row or not row.get("checked"):
        return None
    try:
        checked = date.fromisoformat(str(row["checked"]))
    except ValueError:
        return None
    return ((as_of or today()) - checked).days


def is_stale(platform: str, *, as_of: date | None = None) -> bool:
    """True when norms exist but are old enough to re-check."""
    age = age_days(platform, as_of=as_of)
    return age is not None and age > STALE_AFTER_DAYS


def freshness(platform: str, *, as_of: date | None = None) -> str:
    """One-cell summary for the platform table."""
    row = get(platform)
    if not row:
        return "never checked"
    age = age_days(platform, as_of=as_of)
    if age is None:
        return "undated"
    if age <= 0:
        return f"{row['checked']} (today)"
    return f"{row['checked']} ({age}d{' — stale' if age > STALE_AFTER_DAYS else ''})"


def brief(platform: str, *, as_of: date | None = None) -> str:
    """The norms a writer needs, or an honest statement that there aren't any."""
    from . import platforms

    pid = platforms.normalize(platform)
    row = get(pid)
    if not row:
        return (
            f"No norms on file for {pid} — checking hard limits only.\n"
            "Nothing here guesses at the length band, hashtag count, or link behaviour. "
            "Research the current norms and record them with social_record_norms."
        )

    lines = [f"### Norms — {pid} (checked {freshness(pid, as_of=as_of)})"]
    if row.get("sweet_spot"):
        lo, hi = row["sweet_spot"]
        lines.append(f"- Sweet spot: {lo}–{hi} characters.")
    if row.get("hashtag_norm"):
        hmin, hmax = row["hashtag_norm"]
        lines.append(f"- Hashtags: {hmin}–{hmax}." if hmax else "- Hashtags: none — they read as spam here.")
    if row.get("fold"):
        lines.append(f"- Fold: only the first ~{row['fold']} characters show before '…more'.")
    if row.get("link_penalty") is not None:
        if row["link_penalty"]:
            lines.append(f"- Links: demoted in the body — {row.get('link_workaround', 'move it out of the post')}")
        else:
            lines.append("- Links: fine in the body.")
    if row.get("alt_text"):
        lines.append(f"- Alt text: {row['alt_text']}.")
    for key, label in (("hook", "Hook"), ("native_shape", "Native shape"), ("flops", "Flops here")):
        if row.get(key):
            lines.append(f"- {label}: {row[key]}")
    if row.get("notes"):
        lines.append(f"- Notes: {row['notes']}")
    if row.get("sources"):
        lines.append("- Sources: " + ", ".join(str(s) for s in row["sources"]))

    if is_stale(pid, as_of=as_of):
        lines.append(
            f"\n⚠ These norms are over {STALE_AFTER_DAYS} days old. Re-check before trusting them — "
            "platform ranking changes faster than that."
        )
    return "\n".join(lines)


def status(*, as_of: date | None = None) -> str:
    """Freshness across every platform — what's researched, what's stale, what's missing."""
    from . import platforms

    rows = ["| Platform | Norms |", "|---|---|"]
    rows += [f"| {platforms.SPECS[p].label} | {freshness(p, as_of=as_of)} |" for p in platforms.known()]
    missing = [p for p in platforms.active() if not get(p)]
    if missing:
        rows += ["", f"In scope but never researched: {', '.join(missing)}."]
    return "\n".join(rows)
