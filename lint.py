"""Draft linter — grade a post against what the platform enforces and the brand decided.

Three tiers of check, and the difference between them matters:

* **Hard limits** (``platforms.py``) — the platform would reject the post. Always
  checked, always an error.
* **Brand rules** (``brandkit.py``) — the operator decided it. Always checked.
* **Norms** (``norms.py``) — researched, dated, refreshable. Checked *only when they
  are on file*. With nothing on file the linter says so and skips them rather than
  inventing a number, because a confident wrong threshold is worse than no threshold.

Precedence for a norm: the brand kit's ``platforms:`` house rules beat researched
norms. What the operator decided outranks what the agent read.

Pure functions over strings and dicts: no network, no I/O beyond reading the two
data files.
"""

from __future__ import annotations

import re
from typing import Any

from . import brandkit, norms, platforms

# Weight per severity, subtracted from 100.
_WEIGHTS = {"error": 25, "warn": 8, "info": 2}

# Findings that report on the linter's own coverage rather than on the draft. They
# belong in the output — a reader has to know what wasn't checked — but they are not
# defects in the copy, so they must not cost the post points.
_UNSCORED_CODES = {"no_norms", "partial_norms", "stale_norms"}

# The checks that need a researched norm, and the norms key each one needs. Used to
# report coverage precisely instead of leaving the reader to work it out.
_NORM_DEPENDENT = (
    ("sweet_spot", "the length band"),
    ("fold", "where the fold falls"),
    ("hashtag_norm", "hashtag count"),
    ("link_penalty", "link demotion"),
    ("alt_text", "how strictly alt text is expected"),
)

# Links, as they're actually written in social copy. Scheme-prefixed URLs are the
# easy case; the one that matters is the BARE domain — nobody types "https://" into a
# tweet, but "github.com/you/repo" is still a link and still gets the post demoted.
# Bare domains are matched against a TLD list rather than `\w+\.\w+` so that version
# numbers ("v0.114.0"), file names ("report.pdf"), and sentences with no space after
# the full stop don't read as links.
_LINK_TLDS = (
    "com|org|net|edu|gov|io|dev|ai|co|app|sh|gg|xyz|me|so|to|tv|fm|us|uk|ca|de|fr|eu|"
    "info|biz|studio|tech|design|blog|news|cloud|page|link|site|online|store|shop"
)
_URL_RE = re.compile(
    r"(?:https?://\S+)"  # explicit scheme
    r"|(?:\bwww\.\S+)"  # www., scheme omitted
    rf"|(?:\b(?!\d+\.)[a-z0-9][a-z0-9-]*(?:\.[a-z0-9-]+)*\.(?:{_LINK_TLDS})\b(?:/\S*)?)",
    re.IGNORECASE,
)
_HASHTAG_RE = re.compile(r"(?<!\w)#(\w+)")
_MENTION_RE = re.compile(r"(?<!\w)@(\w+)")
_CAPS_RUN_RE = re.compile(r"\b[A-Z]{2,}(?:\s+[A-Z]{2,}){2,}\b")

# Emoji-ish codepoint ranges — enough to enforce a policy, not a full grapheme parser.
_EMOJI_RE = re.compile("[\U0001f300-\U0001faff\U00002600-\U000027bf\U0001f1e6-\U0001f1ff\U00002190-\U000021ff]")

# Cadence that reads as generated. Kept tight on purpose: each entry is a phrase
# that is both very common in LLM output and almost never the best available
# phrasing. A brand can switch the whole check off with `voice.check_ai_tells: false`.
AI_TELLS = (
    "in today's fast-paced",
    "in today's digital",
    "let's dive in",
    "let's dive into",
    "dive deep into",
    "it's not just",  # paired with "it's" — the "not just X, it's Y" construction
    "here's the thing",
    "game-changer",
    "game changer",
    "unlock the power",
    "unlock the potential",
    "revolutionize",
    "seamlessly integrate",
    "a testament to",
    "the landscape of",
    "navigate the complexities",
    "delve into",
    "at the end of the day",
    "elevate your",
    "take it to the next level",
    "buckle up",
    "spoiler alert",
)


def _visible_length(text: str) -> int:
    """Characters the platform counts. URLs are counted as written — the t.co-style
    shortening some platforms apply only ever makes a post shorter, so counting the
    raw text is the safe direction to be wrong in."""
    return len(text or "")


def _find_phrases(text: str, phrases: list[str]) -> list[str]:
    """Case-insensitive phrase hits, in the order they appear in `phrases`."""
    low = (text or "").lower()
    return [p for p in phrases if p.strip() and p.strip().lower() in low]


def effective_norms(platform: str, kit: dict[str, Any] | None) -> dict[str, Any]:
    """Researched norms with the brand's house rules layered on top."""
    try:
        researched = norms.get(platform) or {}
    except Exception:  # noqa: BLE001 — a broken norms file must not block linting
        researched = {}
    return {**researched, **brandkit.platform_overrides(kit, platform)}


def _has_cta(text: str, kit_ctas: list[str]) -> bool:
    """A post 'has a CTA' if it uses one from the kit, asks a question, or ends on an
    imperative-looking short line."""
    low = (text or "").lower()
    if any(c.strip().lower() in low for c in kit_ctas if c.strip()):
        return True
    if "?" in text:
        return True
    tail = [ln.strip() for ln in (text or "").splitlines() if ln.strip()]
    if tail:
        last = tail[-1]
        # Short closing line with a verb-ish opener reads as a call to action.
        if len(last) <= 90 and re.match(
            r"^(try|read|get|grab|join|tell|reply|share|check|see|watch|book|start|sign)\b", last, re.I
        ):
            return True
    return False


def _pair(value: Any) -> tuple[int, int] | None:
    """A [min, max] norm, or None when it's absent or malformed."""
    if not isinstance(value, (list, tuple)) or len(value) != 2:
        return None
    try:
        return int(value[0]), int(value[1])
    except (TypeError, ValueError):
        return None


def check(
    text: str,
    platform: str,
    *,
    kit: dict[str, Any] | None = None,
    has_media: bool = False,
    alt_text: str = "",
    title: str = "",
) -> dict[str, Any]:
    """Grade one draft. Returns ``{platform, chars, score, verdict, findings, hook}``.

    ``findings`` is a list of ``{level, code, message, fix}``. ``verdict`` is
    ``blocked`` (a hard violation), ``revise``, or ``ship``.
    """
    text = text or ""
    findings: list[dict[str, str]] = []

    def add(level: str, code: str, message: str, fix: str = "") -> None:
        findings.append({"level": level, "code": code, "message": message, "fix": fix})

    spec = platforms.get(platform)
    if spec is None:
        return {
            "platform": platform,
            "chars": _visible_length(text),
            "score": 0,
            "verdict": "blocked",
            "findings": [
                {
                    "level": "error",
                    "code": "unknown_platform",
                    "message": f"Unknown platform {platform!r}.",
                    "fix": f"Use one of: {', '.join(platforms.known())}.",
                }
            ],
            "hook": "",
        }

    norm = effective_norms(spec.id, kit)
    n = _visible_length(text)

    # ── hard limits — always checked, always errors ───────────────────────────
    if n == 0:
        add("error", "empty", "The draft is empty.", "Write the post.")
    elif n > spec.max_chars:
        add(
            "error",
            "too_long",
            f"{n:,} characters — {spec.label} caps at {spec.max_chars:,} ({n - spec.max_chars:,} over).",
            "Cut, or split it into a thread." if spec.threading else "Cut it down.",
        )

    field_caps = platforms.FIELD_LIMITS.get(spec.id, {})
    if title and "title" in field_caps and len(title) > field_caps["title"]:
        add(
            "error",
            "title_too_long",
            f"Title is {len(title)} characters — {spec.label} caps titles at {field_caps['title']}.",
            "Tighten the title.",
        )
    if alt_text and "alt_text" in field_caps and len(alt_text) > field_caps["alt_text"]:
        add(
            "error",
            "alt_too_long",
            f"Alt text is {len(alt_text)} characters — {spec.label} caps it at {field_caps['alt_text']}.",
            "Shorten the alt text.",
        )

    links = _URL_RE.findall(text)
    if links and not spec.links_clickable:
        add(
            "warn",
            "link_not_clickable",
            f"Links aren't clickable in {spec.label} captions.",
            spec.link_note or "Put the link somewhere it works.",
        )

    # ── coverage: say what isn't being checked, and don't charge for it ───────
    # Name the skipped checks rather than leaving a reader to infer them — an agent
    # asked "what couldn't you check?" will otherwise guess, and guess wrong about
    # which rules were brand rules (always run) and which needed a norm.
    skipped = [label for key, label in _NORM_DEPENDENT if not norm.get(key)]
    if not norm:
        add(
            "info",
            "no_norms",
            f"No norms on file for {spec.id} — checked hard limits and brand rules only. "
            f"Not checked: {', '.join(labels for _, labels in _NORM_DEPENDENT)}.",
            "Research the current norms and record them with social_record_norms.",
        )
    elif skipped:
        add(
            "info",
            "partial_norms",
            f"Norms on file for {spec.id} don't cover: {', '.join(skipped)}.",
            "Record those fields with social_record_norms if the research settles them.",
        )

    # Independent of coverage: norms can be complete and still too old to trust.
    if norm and norms.is_stale(spec.id) and not brandkit.platform_overrides(kit, spec.id):
        add(
            "info",
            "stale_norms",
            f"Norms for {spec.id} were last checked {norms.freshness(spec.id)} — older than "
            f"{norms.STALE_AFTER_DAYS} days.",
            "Re-check them; platform ranking changes faster than that.",
        )

    # ── norm-dependent checks — only where a norm actually exists ────────────
    sweet = _pair(norm.get("sweet_spot"))
    if sweet and n:
        lo, hi = sweet
        if n < lo:
            add(
                "info",
                "under_sweet_spot",
                f"{n} characters — {spec.label} posts tend to land between {lo} and {hi}.",
                "There may be room for a specific, a number, or a second beat.",
            )
        elif n > hi and n <= spec.max_chars:
            add(
                "info",
                "over_sweet_spot",
                f"{n:,} characters — longer than the {lo}–{hi} band that performs on {spec.label}.",
                "Cut the setup; start at the interesting part.",
            )

    hook = ""
    fold = norm.get("fold")
    try:
        fold = int(fold) if fold else 0
    except (TypeError, ValueError):
        fold = 0
    if fold and n > fold:
        hook = text[:fold].rstrip()
        add(
            "info",
            "fold",
            f"Only the first ~{fold} characters show before '…more': {hook!r}",
            "Everything that earns the click has to be above that line.",
        )
    elif n:
        hook = text.splitlines()[0][:200] if text.splitlines() else text[:200]

    tags = _HASHTAG_RE.findall(text)
    hashtag_norm = _pair(norm.get("hashtag_norm"))
    if hashtag_norm and n:
        hmin, hmax = hashtag_norm
        if len(tags) > hmax:
            add(
                "warn",
                "too_many_hashtags",
                f"{len(tags)} hashtags — {spec.label} reads native at {hmin}–{hmax}.",
                f"Keep the {hmax} that a real person would search." if hmax else "Drop them all.",
            )
        elif len(tags) < hmin:
            add(
                "info",
                "too_few_hashtags",
                f"{len(tags)} hashtags — {spec.label} expects around {hmin}–{hmax}.",
                "Add the ones your audience actually follows.",
            )

    if links and norm.get("link_penalty"):
        add(
            "warn",
            "link_in_body",
            f"{len(links)} link(s) in the body — {spec.label} demotes posts that send people away.",
            str(norm.get("link_workaround") or "Move the link out of the post body.").capitalize(),
        )

    # ── brand rules — always checked ─────────────────────────────────────────
    for phrase in _find_phrases(text, brandkit.banned_phrases(kit)):
        add("error", "banned_phrase", f"Uses a banned phrase: {phrase!r}.", "Rewrite the line without it.")
    for phrase in _find_phrases(text, brandkit.avoid_phrases(kit)):
        add("warn", "avoid_phrase", f"Uses a phrase the brand avoids: {phrase!r}.", "Find a plainer way to say it.")

    voice = (kit or {}).get("voice") if isinstance(kit, dict) else None
    check_tells = True
    if isinstance(voice, dict) and voice.get("check_ai_tells") is False:
        check_tells = False
    if check_tells:
        for tell in _find_phrases(text, list(AI_TELLS)):
            add(
                "warn",
                "ai_tell",
                f"{tell!r} is a cadence readers now clock as machine-written.",
                "Say it the way you'd say it out loud.",
            )

    policy = brandkit.emoji_policy(kit)
    emoji = _EMOJI_RE.findall(text)
    if policy == "none" and emoji:
        add("warn", "emoji", f"{len(emoji)} emoji — the brand's policy is none.", "Remove them.")
    elif policy == "sparing" and len(emoji) > 2:
        add("warn", "emoji", f"{len(emoji)} emoji — the brand's policy is sparing.", "Keep at most one or two.")

    # ── accessibility — a value, not a norm, so it holds without norms on file ─
    alt_expectation = str(norm.get("alt_text", "")).strip().lower()
    if has_media and not alt_text.strip() and alt_expectation != "n/a":
        add(
            "error" if alt_expectation == "expected" else "warn",
            "missing_alt_text",
            "Media with no alt text." + (f" On {spec.label} alt text is {alt_expectation}." if alt_expectation else ""),
            "Describe what the image shows and what it means, in one sentence.",
        )

    # ── polish ────────────────────────────────────────────────────────────────
    if not _has_cta(text, brandkit.ctas(kit)) and n:
        add(
            "info",
            "no_cta",
            "No call to action — the post ends without asking for anything.",
            "Rotate in one of the brand's CTAs, or end on a real question.",
        )
    if _CAPS_RUN_RE.search(text):
        add("info", "shouting", "A run of ALL-CAPS words reads as shouting.", "Use emphasis sparingly.")
    if text.count("!") > 1:
        add("info", "exclamations", f"{text.count('!')} exclamation marks.", "One is usually one too many.")

    # ── score ─────────────────────────────────────────────────────────────────
    penalty = sum(_WEIGHTS.get(f["level"], 0) for f in findings if f["code"] not in _UNSCORED_CODES)
    score = max(0, 100 - penalty)
    has_error = any(f["level"] == "error" for f in findings)
    verdict = "blocked" if has_error else ("ship" if score >= 85 else "revise")

    return {
        "platform": spec.id,
        "chars": n,
        "hashtags": len(tags),
        "links": len(links),
        "mentions": len(_MENTION_RE.findall(text)),
        "norms_checked": bool(norm),
        "score": score,
        "verdict": verdict,
        "findings": findings,
        "hook": hook,
    }


def render(result: dict[str, Any]) -> str:
    """Format a check result for the agent (and for a human reading the transcript)."""
    icon = {"error": "✗", "warn": "!", "info": "·"}
    head = (
        f"{result['platform']} · {result['chars']:,} chars · score {result['score']}/100 · {result['verdict'].upper()}"
    )
    scored = [f for f in result["findings"] if f["code"] not in _UNSCORED_CODES]
    if not scored and not result["findings"]:
        return head + "\nClean — nothing to fix."

    lines = [head, ""]
    for level in ("error", "warn", "info"):
        for f in result["findings"]:
            if f["level"] != level:
                continue
            lines.append(f"{icon[level]} [{f['code']}] {f['message']}")
            if f.get("fix"):
                lines.append(f"    → {f['fix']}")
    if not scored:
        lines.insert(1, "Clean — nothing to fix.")
    return "\n".join(lines)
