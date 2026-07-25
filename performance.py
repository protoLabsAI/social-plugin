"""What actually performed — read back from results the operator recorded.

A draft-only agent has no analytics API, so the numbers arrive by hand. That makes
the sample small, and small samples are where marketing analysis usually goes wrong:
four posts is enough to produce a confident-sounding ranking and not nearly enough
to mean anything. A brand that reorganises its calendar around a six-post
"finding" has chased an accident.

So this module is built to under-claim. It always reports its sample size, refuses
to compare groups below a floor, and puts the qualitative outcomes — the reply from
a customer, the demo booked — above the impression counts, because for most brands
at this scale those are the only signal that isn't noise.

Host-free: stdlib only.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any

from . import store

# Below this many posts overall, no comparisons are offered at all.
MIN_TOTAL = 8
# Below this many posts in a group, the group is listed but never ranked against others.
MIN_GROUP = 4

# Length bands, in characters — coarse on purpose. Anything finer over-fits.
_BANDS = ((0, 150, "short (<150)"), (150, 600, "medium (150–600)"), (600, 10**9, "long (600+)"))


def _rate(row: dict[str, Any]) -> float | None:
    """Engagement rate — the one metric comparable across posts of different reach."""
    results = row.get("results") or {}
    try:
        impressions = float(results.get("impressions") or 0)
        engagements = float(results.get("engagements") or 0)
    except (TypeError, ValueError):
        return None
    if impressions <= 0:
        return None
    return 100.0 * engagements / impressions


def _band(row: dict[str, Any]) -> str:
    n = len(row.get("body") or "")
    for lo, hi, label in _BANDS:
        if lo <= n < hi:
            return label
    return _BANDS[-1][2]


def _within(row: dict[str, Any], days: int) -> bool:
    stamp = row.get("posted_at") or row.get("updated") or ""
    if not days or not stamp:
        return True
    try:
        when = datetime.fromisoformat(stamp)
    except ValueError:
        return True
    if when.tzinfo is None:
        when = when.replace(tzinfo=timezone.utc)
    return when >= datetime.now(timezone.utc) - timedelta(days=days)


def _group(rows: list[dict[str, Any]], key) -> dict[str, list[float]]:
    out: dict[str, list[float]] = {}
    for row in rows:
        rate = _rate(row)
        if rate is None:
            continue
        out.setdefault(key(row) or "(unassigned)", []).append(rate)
    return out


def _summarise(title: str, groups: dict[str, list[float]]) -> list[str]:
    """Rank a grouping, but only across groups big enough to be worth ranking."""
    rankable = {k: v for k, v in groups.items() if len(v) >= MIN_GROUP}
    lines = [f"**{title}**"]
    if not groups:
        lines.append("  no posts with both impressions and engagements recorded")
        return lines
    for name, rates in sorted(groups.items(), key=lambda kv: -sum(kv[1]) / len(kv[1])):
        avg = sum(rates) / len(rates)
        flag = "" if len(rates) >= MIN_GROUP else f"  ← only {len(rates)}, not comparable"
        lines.append(f"  {name}: {avg:.2f}% over {len(rates)} post(s){flag}")
    if len(rankable) < 2:
        lines.append(f"  (nothing ranked — needs {MIN_GROUP}+ posts in at least two groups)")
    return lines


def report(*, days: int = 90, platform: str = "") -> str:
    """The performance read-back, honest about how little it may know."""
    rows = [r for r in store.with_results(platform=platform) if _within(r, days)]
    total = len(rows)
    window = f"last {days} days" if days else "all time"
    scope = f" on {platform}" if platform else ""

    if not total:
        return (
            f"No results recorded{scope} in the {window}.\n\n"
            "Nothing here can tell you what worked until someone reads the numbers off the "
            "platform and records them with social_record_results. Even a handful of posts a "
            "month is enough to stop the calendar being pure guesswork."
        )

    rated = [r for r in rows if _rate(r) is not None]
    lines = [f"Performance — {window}{scope}", ""]
    lines.append(f"{total} post(s) with results recorded; {len(rated)} with enough to compute an engagement rate.")

    if total < MIN_TOTAL:
        lines += [
            "",
            f"⚠ That's below the {MIN_TOTAL}-post floor for comparing anything. Individual posts "
            "are listed below, but any difference between them at this sample size is noise. "
            "Don't reshape the calendar around it.",
        ]

    # Qualitative outcomes first — at this scale they beat the metrics, and they're the
    # thing a dashboard would drop on the floor.
    outcomes = [(r, (r.get("results") or {}).get("outcome")) for r in rows]
    outcomes = [(r, o) for r, o in outcomes if o]
    if outcomes:
        lines += ["", "**What actually came of it**"]
        for row, outcome in outcomes[:10]:
            lines.append(f"  #{row['id']} ({row['platform']}): {outcome}")
        lines.append("  These are worth more than the percentages below. Post more of what caused them.")

    if total >= MIN_TOTAL and rated:
        lines += [""]
        lines += _summarise("By platform", _group(rated, lambda r: r.get("platform")))
        lines += [""]
        lines += _summarise("By pillar", _group(rated, lambda r: r.get("pillar")))
        lines += [""]
        lines += _summarise("By length", _group(rated, _band))

    if rated:
        best = sorted(rated, key=lambda r: -(_rate(r) or 0))
        lines += ["", "**Highest engagement rate**"]
        for row in best[:3]:
            preview = " ".join((row.get("body") or "").split())[:80]
            lines.append(f"  {_rate(row):.2f}%  #{row['id']} {row['platform']}: {preview}")
        if len(best) >= 6:
            lines += ["", "**Lowest**"]
            for row in best[-3:]:
                preview = " ".join((row.get("body") or "").split())[:80]
                lines.append(f"  {_rate(row):.2f}%  #{row['id']} {row['platform']}: {preview}")

    missing = total - len(rated)
    if missing:
        lines += [
            "",
            f"{missing} post(s) have results but no impressions/engagements, so they're excluded "
            "from the rates. Record both if you want them counted.",
        ]

    lines += [
        "",
        "Read this as a prompt for a hypothesis, not a verdict. The honest use is to pick one "
        "thing to try differently next fortnight and see whether it holds up.",
    ]
    return "\n".join(lines)
