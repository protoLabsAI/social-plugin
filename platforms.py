"""Platform capabilities — only the facts the platform itself enforces.

What lives here is deliberately narrow: character caps, field caps, the aspect
ratios a surface renders, whether captions make links clickable, whether chains are
native. These are **hard limits**. When one changes, it changes discretely and
publicly, and correcting it is a version bump rather than a guess.

What does NOT live here is every soft norm — the length band that performs, hashtag
counts that read as native, whether the ranking demotes an external link, where the
"…more" fold falls, what flops. Those drift as the platforms retune, and a constant
compiled into a plugin states last year's folklore as fact forever. They live in
``norms.py``: researched by the agent, stamped with a date and its sources, owned and
editable by the operator, refreshable without a release.

So: if the platform would reject the post, it belongs here. If it would merely
perform badly, it belongs in norms.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class PlatformSpec:
    """One surface's hard, platform-enforced capabilities."""

    id: str
    label: str
    max_chars: int  # over this the platform rejects the post
    media: str  # the aspect ratios / dimensions the surface renders
    links_clickable: bool  # whether a link in the body is a link at all
    threading: bool  # multi-post chains are a native affordance
    link_note: str = ""  # where a link has to go when the body can't hold one

    def summary(self) -> str:
        """The hard facts, as a writer needs them stated."""
        lines = [
            f"## {self.label} ({self.id})",
            f"- Hard limit: {self.max_chars:,} characters.",
            f"- Media: {self.media}.",
        ]
        caps = FIELD_LIMITS.get(self.id, {})
        for field_name, cap in caps.items():
            lines.append(f"- {field_name.replace('_', ' ').capitalize()} caps at {cap} characters.")
        if not self.links_clickable:
            lines.append(f"- Links in the body are NOT clickable here — {self.link_note}")
        if self.threading:
            lines.append("- Threads/chains are native — a long idea can run across linked posts.")
        return "\n".join(lines)


SPECS: dict[str, PlatformSpec] = {
    "x": PlatformSpec(
        id="x",
        label="X",
        max_chars=280,  # the free-tier limit; Premium raises it, but 280 is what to write to
        media="16:9 or 1:1, up to 4 images; video under ~2:20",
        links_clickable=True,
        threading=True,
    ),
    "linkedin": PlatformSpec(
        id="linkedin",
        label="LinkedIn",
        max_chars=3000,
        media="1:1 or 4:5 images; native video; PDF carousels (documents)",
        links_clickable=True,
        threading=False,
    ),
    "instagram": PlatformSpec(
        id="instagram",
        label="Instagram",
        max_chars=2200,
        media="feed 4:5 (1080×1350) or 1:1; Reels 9:16 (1080×1920)",
        links_clickable=False,
        link_note="use the bio link or a story sticker.",
        threading=False,
    ),
    "threads": PlatformSpec(
        id="threads",
        label="Threads",
        max_chars=500,
        media="1:1 or 4:5 images (up to 20), or one video",
        links_clickable=True,
        threading=True,
    ),
    "bluesky": PlatformSpec(
        id="bluesky",
        label="Bluesky",
        max_chars=300,
        media="16:9 or 1:1, up to 4 images",
        links_clickable=True,
        threading=True,
    ),
    "tiktok": PlatformSpec(
        id="tiktok",
        label="TikTok",
        max_chars=2200,
        media="9:16 (1080×1920) vertical video",
        links_clickable=False,
        link_note="use the bio link.",
        threading=False,
    ),
    "youtube": PlatformSpec(
        id="youtube",
        label="YouTube",
        max_chars=5000,  # description; the title is capped separately
        media="16:9 (1920×1080) long-form; Shorts 9:16",
        links_clickable=True,
        threading=False,
    ),
    "facebook": PlatformSpec(
        id="facebook",
        label="Facebook",
        max_chars=63206,
        media="1:1 or 4:5 images; native video 4:5 or 9:16",
        links_clickable=True,
        threading=False,
    ),
    "reddit": PlatformSpec(
        id="reddit",
        label="Reddit",
        max_chars=40000,  # body; the title is capped separately
        media="varies by subreddit; many are text-only",
        links_clickable=True,
        threading=False,
    ),
}

# Hard caps on fields that aren't the post body.
FIELD_LIMITS: dict[str, dict[str, int]] = {
    "youtube": {"title": 100},
    "reddit": {"title": 300},
    "x": {"alt_text": 1000},
    "instagram": {"alt_text": 100},
    "bluesky": {"alt_text": 2000},
}

DEFAULT_PLATFORMS = ["x", "linkedin", "instagram", "bluesky"]

# The surfaces this operator actually posts to, set by register() from config. The
# specs for every platform stay available — this only marks which ones are in scope,
# so the agent doesn't plan a calendar for accounts that don't exist.
_ACTIVE: list[str] = []


def configure_active(ids: list[str] | None) -> None:
    """Set the operator's active platforms (unknown ids are dropped)."""
    global _ACTIVE
    _ACTIVE = [p for p in (normalize(i) for i in (ids or [])) if p in SPECS]


def active() -> list[str]:
    """The in-scope platforms, falling back to the shipped default set."""
    return list(_ACTIVE) or list(DEFAULT_PLATFORMS)


# Common spellings operators and models reach for, mapped to canonical ids.
_ALIASES = {
    "twitter": "x",
    "x.com": "x",
    "tweet": "x",
    "li": "linkedin",
    "ig": "instagram",
    "insta": "instagram",
    "reel": "instagram",
    "reels": "instagram",
    "bsky": "bluesky",
    "yt": "youtube",
    "shorts": "youtube",
    "youtube_shorts": "youtube",
    "fb": "facebook",
    "meta": "facebook",
    "sub": "reddit",
    "subreddit": "reddit",
}


def normalize(platform: str) -> str:
    """Canonical platform id for a user- or model-supplied name ('Twitter' -> 'x').

    Returns the input lowercased/stripped when it matches nothing, so callers can
    report an unknown platform rather than silently drafting for the wrong one.
    """
    key = (platform or "").strip().lower().replace(" ", "_").replace("-", "_")
    if key in SPECS:
        return key
    if key in _ALIASES:
        return _ALIASES[key]
    # "linked-in" and "linked in" both arrive here as "linked_in" — try it joined up
    # before giving in, so a separator the operator chose isn't an unknown platform.
    joined = key.replace("_", "")
    if joined in SPECS:
        return joined
    return _ALIASES.get(joined, key)


def get(platform: str) -> PlatformSpec | None:
    """The spec for a platform, or None if it isn't one we carry."""
    return SPECS.get(normalize(platform))


def known() -> list[str]:
    """Every canonical platform id, in a stable order."""
    return list(SPECS.keys())


def brief(platform: str = "") -> str:
    """Hard limits plus whatever norms are on file, or a table of every platform.

    Imports ``norms`` lazily: platforms.py is the layer with no opinions, and keeping
    the dependency one-way means the hard limits stay readable on their own.
    """
    from . import norms

    if platform:
        spec = get(platform)
        if spec is None:
            return (
                f"Unknown platform {platform!r}. Known: {', '.join(known())}.\n"
                "Add house rules for anything else under `platforms:` in the brand kit."
            )
        return f"{spec.summary()}\n\n{norms.brief(spec.id)}"

    in_scope = active()
    rows = ["| Platform | Limit | Links clickable | Threads | Norms on file |", "|---|---|---|---|---|"]
    for spec in SPECS.values():
        mark = " ●" if spec.id in in_scope else ""
        rows.append(
            f"| {spec.label}{mark} | {spec.max_chars:,} | {'yes' if spec.links_clickable else 'no'} | "
            f"{'yes' if spec.threading else 'no'} | {norms.freshness(spec.id)} |"
        )
    rows += [
        "",
        f"● = in scope for this brand ({', '.join(in_scope)}). The others are available if asked for.",
        "",
        "Only hard, platform-enforced limits are built in. Everything soft — the length band that",
        "performs, hashtag counts, link demotion, where the fold falls — is researched and dated,",
        "not compiled in. Ask for one platform to see its norms, or run social_record_norms to",
        "refresh a platform whose norms are missing or stale.",
    ]
    return "\n".join(rows)
