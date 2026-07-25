"""Platform specs — the hard limits and native norms of each social surface.

Pure data + lookups, no host imports, no network. This is the knowledge that stops
an agent writing one blob of text and pasting it everywhere: a 280-character X post
is a different artifact from a 1,800-character LinkedIn essay, and both are different
from an Instagram caption whose first 125 characters are the only ones most people
read.

Two kinds of fact live here and they are NOT equally durable:

* ``max_chars`` and aspect ratios are **hard limits** enforced by the platform.
* ``hashtag_norm``, ``sweet_spot``, ``link_penalty`` are **norms** — what currently
  works. They drift as the platforms retune their ranking. Each spec carries the
  date it was last checked; ``social_platform_spec`` surfaces that date so nobody
  treats a stale norm as gospel.

Operators can override or extend any of this from the brand kit's ``platforms:``
section (see brandkit.py) — the shipped table is a starting point, not a cage.
"""

from __future__ import annotations

from dataclasses import dataclass, field

# When the norms below were last reviewed against the live platforms. Surfaced in
# tool output so a reader can judge how much to trust the soft guidance.
NORMS_CHECKED = "2026-07"


@dataclass(frozen=True)
class PlatformSpec:
    """One surface's limits, norms, and the shape of a post that works there."""

    id: str
    label: str
    max_chars: int  # hard limit — over this the platform rejects the post
    truncate_at: int  # where the "…more" fold typically falls (0 = no fold)
    sweet_spot: tuple[int, int]  # observed best-performing length band
    hashtag_norm: tuple[int, int]  # (min, max) hashtags that read as native
    link_penalty: bool  # ranking demotes posts with an external link in the body
    link_workaround: str  # where the link should go instead
    media: str  # the aspect ratios / dimensions that fit
    alt_text: str  # "expected" | "recommended" | "n/a"
    hook_note: str  # what has to happen in the first line
    format_note: str  # native structure — what a good post looks like here
    dies_here: str  # the thing that reliably flops on this surface
    threading: bool = False  # multi-post chains are native
    tags: list[str] = field(default_factory=list)

    def summary(self) -> str:
        """Human/agent-readable brief — what a writer needs before drafting."""
        hmin, hmax = self.hashtag_norm
        lo, hi = self.sweet_spot
        lines = [
            f"## {self.label} ({self.id})",
            f"- Hard limit: {self.max_chars:,} characters."
            + (f" Fold (…more) at ~{self.truncate_at}." if self.truncate_at else ""),
            f"- Sweet spot: {lo}–{hi} characters.",
            f"- Hashtags: {hmin}–{hmax}." if hmax else "- Hashtags: none — they read as spam here.",
            f"- Links: {'demoted in-body — ' + self.link_workaround if self.link_penalty else 'fine in the body.'}",
            f"- Media: {self.media}. Alt text: {self.alt_text}.",
            f"- Hook: {self.hook_note}",
            f"- Native shape: {self.format_note}",
            f"- Flops here: {self.dies_here}",
        ]
        if self.threading:
            lines.append("- Threads/chains are native — a long idea can run across linked posts.")
        return "\n".join(lines)


SPECS: dict[str, PlatformSpec] = {
    "x": PlatformSpec(
        id="x",
        label="X",
        max_chars=280,  # the free-tier limit; Premium raises it, but 280 is what to write to
        truncate_at=0,
        sweet_spot=(70, 240),
        hashtag_norm=(0, 1),
        link_penalty=True,
        link_workaround="put the link in a reply to your own post",
        media="16:9 or 1:1, up to 4 images; video under ~2:20",
        alt_text="recommended",
        hook_note="the whole post is the hook — the first 5 words decide the scroll",
        format_note=(
            "one sharp claim, or a thread where post 1 stands alone and each following post "
            "earns the next. Line breaks over paragraphs. No preamble."
        ),
        dies_here="engagement bait, LinkedIn-voice, a link with no reason to click",
        threading=True,
        tags=["short-form", "text-first"],
    ),
    "linkedin": PlatformSpec(
        id="linkedin",
        label="LinkedIn",
        max_chars=3000,
        truncate_at=210,
        sweet_spot=(900, 1800),
        hashtag_norm=(3, 5),
        link_penalty=True,
        link_workaround="drop the link in the first comment and say so in the post",
        media="1:1 or 4:5 images; native video; PDF carousels (documents) travel well",
        alt_text="recommended",
        hook_note="the first 2 lines are all that show before 'see more' — no wind-up, no throat-clearing",
        format_note=(
            "short paragraphs with white space between them. A concrete story or a specific "
            "number, then the lesson. Ends with a question or an invitation, not a hard sell."
        ),
        dies_here="corporate announcement voice, buzzword stacks, obvious AI cadence",
        tags=["long-form", "professional"],
    ),
    "instagram": PlatformSpec(
        id="instagram",
        label="Instagram",
        max_chars=2200,
        truncate_at=125,
        sweet_spot=(140, 800),
        hashtag_norm=(3, 5),
        link_penalty=False,  # links aren't clickable in captions at all
        link_workaround="captions have no clickable links — use the bio link or a story sticker",
        media="feed 4:5 (1080×1350) or 1:1; Reels 9:16 (1080×1920)",
        alt_text="recommended",
        hook_note="first ~125 characters show before the fold — lead with the payoff",
        format_note=(
            "the image or Reel carries the idea; the caption adds context, story, or the "
            "specifics the visual can't hold. Line breaks make it readable."
        ),
        dies_here="a wall of text under a stock photo, 30 hashtags, captions that describe the image",
        tags=["visual-first"],
    ),
    "threads": PlatformSpec(
        id="threads",
        label="Threads",
        max_chars=500,
        truncate_at=0,
        sweet_spot=(80, 400),
        hashtag_norm=(0, 1),
        link_penalty=False,
        link_workaround="links are fine in the body",
        media="1:1 or 4:5 images (up to 20), or one video",
        alt_text="recommended",
        hook_note="conversational opener — it reads like a group chat, not a broadcast",
        format_note="casual, present-tense, a real observation or question. Chains work for longer ideas.",
        dies_here="repurposed LinkedIn posts, formal voice, anything that smells scheduled",
        threading=True,
        tags=["short-form", "casual"],
    ),
    "bluesky": PlatformSpec(
        id="bluesky",
        label="Bluesky",
        max_chars=300,
        truncate_at=0,
        sweet_spot=(80, 260),
        hashtag_norm=(0, 2),
        link_penalty=False,
        link_workaround="links are fine in the body and render a preview card",
        media="16:9 or 1:1, up to 4 images",
        alt_text="expected",  # the culture actively calls out missing alt text
        hook_note="say the thing — the audience is early-adopter and allergic to marketing cadence",
        format_note="plain, specific, human. Reply-chains are how conversations happen.",
        dies_here="brand voice, growth-hack formatting, images without alt text",
        threading=True,
        tags=["short-form", "text-first"],
    ),
    "tiktok": PlatformSpec(
        id="tiktok",
        label="TikTok",
        max_chars=2200,
        truncate_at=100,
        sweet_spot=(40, 200),
        hashtag_norm=(3, 5),
        link_penalty=False,
        link_workaround="captions have no clickable links — use the bio link",
        media="9:16 (1080×1920) vertical video",
        alt_text="n/a",
        hook_note="the first 1–3 SECONDS of video decide it — the caption is secondary",
        format_note=(
            "the script is the deliverable: a visual hook, one idea, a reason to stay to the end. "
            "The caption adds a searchable line and a question."
        ),
        dies_here="repurposed landscape video, slow intros, talking-head with no visual change",
        tags=["video-first"],
    ),
    "youtube": PlatformSpec(
        id="youtube",
        label="YouTube",
        max_chars=5000,  # description limit; title is capped separately at 100
        truncate_at=150,
        sweet_spot=(200, 1500),
        hashtag_norm=(0, 3),
        link_penalty=False,
        link_workaround="links belong in the description",
        media="16:9 (1920×1080) long-form; Shorts 9:16 under ~3 minutes",
        alt_text="n/a",
        hook_note="title (≤100 chars, ~60 visible) + thumbnail do the work; first 150 chars of description show",
        format_note=(
            "description opens with what the viewer gets, then timestamps, then links. "
            "Title promises one specific thing the video delivers."
        ),
        dies_here="clickbait the video doesn't pay off, keyword-stuffed descriptions",
        tags=["video-first", "search"],
    ),
    "facebook": PlatformSpec(
        id="facebook",
        label="Facebook",
        max_chars=63206,
        truncate_at=125,
        sweet_spot=(40, 250),
        hashtag_norm=(0, 2),
        link_penalty=True,
        link_workaround="post natively and put the link in a comment, or accept the reach hit",
        media="1:1 or 4:5 images; native video 4:5 or 9:16",
        alt_text="recommended",
        hook_note="short beats long — under ~80 characters consistently outperforms",
        format_note="conversational, community-facing. Native photo/video outperforms link posts.",
        dies_here="long text posts, anything that reads like an ad in an organic slot",
        tags=["community"],
    ),
    "reddit": PlatformSpec(
        id="reddit",
        label="Reddit",
        max_chars=40000,  # body; title is capped separately at 300
        truncate_at=0,
        sweet_spot=(600, 4000),
        hashtag_norm=(0, 0),
        link_penalty=True,
        link_workaround="most subreddits ban or throttle self-promo links — read the sidebar rules FIRST",
        media="varies by subreddit; many are text-only",
        alt_text="n/a",
        hook_note="the title is the entire pitch and cannot be edited after posting",
        format_note=(
            "write as a member of the community, not a brand. Give the substance away in the "
            "post itself. Disclose affiliation plainly — hiding it is what gets you banned."
        ),
        dies_here="marketing voice, undisclosed promotion, posts that exist to route people elsewhere",
        tags=["community", "long-form"],
    ),
}

# Extra hard caps that aren't the body-character limit.
FIELD_LIMITS: dict[str, dict[str, int]] = {
    "youtube": {"title": 100},
    "reddit": {"title": 300},
    "x": {"alt_text": 1000},
    "instagram": {"alt_text": 100},
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
    """Drafting brief for one platform, or a comparison table for all of them."""
    if platform:
        spec = get(platform)
        if spec is None:
            return (
                f"Unknown platform {platform!r}. Known: {', '.join(known())}.\n"
                "Add house rules for anything else under `platforms:` in the brand kit."
            )
        return f"{spec.summary()}\n\n(Hard limits are current; soft norms last reviewed {NORMS_CHECKED}.)"

    in_scope = active()
    rows = ["| Platform | Limit | Fold | Sweet spot | Hashtags | Link in body |", "|---|---|---|---|---|---|"]
    for spec in SPECS.values():
        lo, hi = spec.sweet_spot
        hmin, hmax = spec.hashtag_norm
        mark = " ●" if spec.id in in_scope else ""
        rows.append(
            f"| {spec.label}{mark} | {spec.max_chars:,} | {spec.truncate_at or '—'} | {lo}–{hi} | "
            f"{hmin}–{hmax} | {'demoted' if spec.link_penalty else 'ok'} |"
        )
    rows += [
        "",
        f"● = in scope for this brand ({', '.join(in_scope)}). The others are available if asked for.",
        f"Soft norms last reviewed {NORMS_CHECKED}. Ask for one platform to get its full brief.",
    ]
    return "\n".join(rows)
