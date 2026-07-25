"""Draft linter — grade a post against the platform it's going to and the brand kit.

Everything here is mechanical: length, fold position, hashtag count, link placement,
emoji policy, banned phrases, alt text, and the cadence tells that make copy read as
machine-written. It deliberately does NOT judge whether the idea is good — that's
the editor subagent's job. What it does is stop the agent shipping a 340-character
"tweet", a LinkedIn post whose link buries the reach, or a caption containing a word
the brand has banned.

Pure functions over strings and dicts: no host, no network, no I/O.
"""

from __future__ import annotations

import re
from typing import Any

from . import brandkit, platforms

# Weight per severity, subtracted from 100.
_WEIGHTS = {"error": 25, "warn": 8, "info": 2}

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
            r"^(try|read|get|grab|join|tell|reply|share|check|see|watch|book|start|sign)\b", last, re.IGNORECASE
        ):
            return True
    return False


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

    over = brandkit.platform_overrides(kit, spec.id)
    n = _visible_length(text)

    # ── hard limits ───────────────────────────────────────────────────────────
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

    # ── length band ───────────────────────────────────────────────────────────
    lo, hi = spec.sweet_spot
    if n and n < lo:
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

    # ── the fold ──────────────────────────────────────────────────────────────
    hook = ""
    if spec.truncate_at and n > spec.truncate_at:
        hook = text[: spec.truncate_at].rstrip()
        add(
            "info",
            "fold",
            f"Only the first ~{spec.truncate_at} characters show before '…more': {hook!r}",
            "Everything that earns the click has to be above that line.",
        )
    elif n:
        hook = text.splitlines()[0][:200] if text.splitlines() else text[:200]

    # ── hashtags ──────────────────────────────────────────────────────────────
    tags = _HASHTAG_RE.findall(text)
    hmin, hmax = spec.hashtag_norm
    if isinstance(over.get("hashtag_norm"), (list, tuple)) and len(over["hashtag_norm"]) == 2:
        hmin, hmax = int(over["hashtag_norm"][0]), int(over["hashtag_norm"][1])
    if len(tags) > hmax:
        add(
            "warn",
            "too_many_hashtags",
            f"{len(tags)} hashtags — {spec.label} reads native at {hmin}–{hmax}.",
            f"Keep the {hmax} that a real person would search." if hmax else "Drop them all.",
        )
    elif len(tags) < hmin and n:
        add(
            "info",
            "too_few_hashtags",
            f"{len(tags)} hashtags — {spec.label} expects around {hmin}–{hmax}.",
            "Add the ones your audience actually follows.",
        )

    # ── links ─────────────────────────────────────────────────────────────────
    links = _URL_RE.findall(text)
    if links and spec.link_penalty:
        add(
            "warn",
            "link_in_body",
            f"{len(links)} link(s) in the body — {spec.label} demotes posts that send people away.",
            spec.link_workaround.capitalize() + ".",
        )
    if links and spec.id in ("instagram", "tiktok"):
        add(
            "warn",
            "link_not_clickable",
            f"Links aren't clickable in {spec.label} captions.",
            spec.link_workaround.capitalize() + ".",
        )

    # ── brand voice ───────────────────────────────────────────────────────────
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

    # ── accessibility ─────────────────────────────────────────────────────────
    if has_media and spec.alt_text != "n/a" and not alt_text.strip():
        level = "error" if spec.alt_text == "expected" else "warn"
        add(
            level,
            "missing_alt_text",
            f"Media with no alt text. On {spec.label} alt text is {spec.alt_text}.",
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
    penalty = sum(_WEIGHTS.get(f["level"], 0) for f in findings)
    score = max(0, 100 - penalty)
    has_error = any(f["level"] == "error" for f in findings)
    verdict = "blocked" if has_error else ("ship" if score >= 85 else "revise")

    return {
        "platform": spec.id,
        "chars": n,
        "hashtags": len(tags),
        "links": len(links),
        "mentions": len(_MENTION_RE.findall(text)),
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
    if not result["findings"]:
        return head + "\nClean — nothing to fix."
    lines = [head, ""]
    for level in ("error", "warn", "info"):
        for f in result["findings"]:
            if f["level"] != level:
                continue
            lines.append(f"{icon[level]} [{f['code']}] {f['message']}")
            if f.get("fix"):
                lines.append(f"    → {f['fix']}")
    return "\n".join(lines)
