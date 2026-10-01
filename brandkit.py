"""The brand kit — one editable file that makes every draft sound like the brand.

A social agent without this writes competent, anonymous marketing copy. The brand
kit is the smallest artifact that fixes that: who we talk to, what we talk about,
how we sound, what we never say, and what we're actually selling.

It is deliberately a plain YAML file on disk, not a database row — the operator
opens it, edits it, and commits it if they want. ``load()``/``save()`` are host-free
so the whole thing is unit-testable with a temp dir.

Two uses:

* ``brief()`` composes the kit into a drafting brief the model reads before writing.
* ``lint.py`` reads the machine-checkable parts (banned/avoid phrases, emoji policy,
  per-platform overrides) to grade a draft.
"""

from __future__ import annotations

import os
import re
from pathlib import Path
from typing import Any

import yaml

from .paths import data_dir

# Set by register() from plugin config; env wins so tests can point at a temp dir.
_CONFIGURED_PATH: str = ""

FILENAME = "brand-kit.yaml"

EMOJI_POLICIES = ("none", "sparing", "liberal")


def configure(path: str) -> None:
    """Point the module at an operator-configured brand-kit path (blank = default)."""
    global _CONFIGURED_PATH
    _CONFIGURED_PATH = (path or "").strip()


def path() -> Path:
    """Where the brand kit lives: env override, then plugin config, then the data dir."""
    env = os.environ.get("SOCIAL_BRAND_KIT", "").strip()
    if env:
        return Path(env).expanduser()
    if _CONFIGURED_PATH:
        return Path(_CONFIGURED_PATH).expanduser()
    return data_dir() / FILENAME


def exists() -> bool:
    return path().is_file()


def load() -> dict[str, Any] | None:
    """Parse the brand kit, or None when it hasn't been written yet.

    A malformed kit raises — a silent empty dict would let the agent draft in a
    generic voice and never say why.
    """
    p = path()
    if not p.is_file():
        return None
    raw = yaml.safe_load(p.read_text(encoding="utf-8"))
    if raw is None:
        return None
    if not isinstance(raw, dict):
        raise ValueError(f"{p} must be a YAML mapping, got {type(raw).__name__}")
    return raw


def save(data: dict[str, Any]) -> Path:
    """Write the brand kit atomically. Returns the path written."""
    if not isinstance(data, dict):
        raise ValueError("brand kit must be a mapping")
    p = path()
    p.parent.mkdir(parents=True, exist_ok=True)
    tmp = p.with_suffix(p.suffix + ".tmp")
    tmp.write_text(
        yaml.safe_dump(data, sort_keys=False, allow_unicode=True, width=100),
        encoding="utf-8",
    )
    tmp.replace(p)
    return p


def save_template() -> Path:
    """Write the blank fill-in starter.

    Deliberately skips the fatal-error gate ``save_yaml`` applies: the template ships
    with an empty ``brand`` precisely because filling it in is the operator's first
    job, and refusing to write the form because the form is blank would be absurd.
    """
    return save(yaml.safe_load(TEMPLATE))


def save_yaml(text: str) -> Path:
    """Validate a YAML string, then write it. Raises on parse or schema problems."""
    parsed = yaml.safe_load(text)
    if not isinstance(parsed, dict):
        raise ValueError("brand kit must be a YAML mapping (top-level key: value pairs)")
    problems = validate(parsed)
    fatal = [p for p in problems if p.startswith("error:")]
    if fatal:
        raise ValueError("; ".join(fatal))
    return save(parsed)


def validate(data: dict[str, Any]) -> list[str]:
    """Schema check. 'error:' entries block a save; 'warn:' entries are gaps worth filling."""
    out: list[str] = []
    raw_brand = data.get("brand")
    if not brand_name(data):
        out.append("error: `brand` (the name) is required")
    elif isinstance(raw_brand, dict):
        out.append("warn: `brand` is a mapping; a plain string reads better everywhere it's displayed")

    for key in ("audiences", "pillars"):
        val = data.get(key)
        if val is None:
            out.append(f"warn: no `{key}` — drafts will be generic without them")
        elif not isinstance(val, list):
            out.append(f"error: `{key}` must be a list")

    pillars = data.get("pillars")
    if isinstance(pillars, list) and pillars:
        mixes = [p.get("mix") for p in pillars if isinstance(p, dict) and p.get("mix") is not None]
        if mixes:
            try:
                total = sum(float(m) for m in mixes)
            except (TypeError, ValueError):
                out.append("error: pillar `mix` values must be numbers")
            else:
                if len(mixes) == len(pillars) and abs(total - 100) > 1:
                    out.append(f"warn: pillar `mix` totals {total:g}%, not 100% — the calendar will be skewed")

    voice = data.get("voice")
    if voice is None:
        out.append("warn: no `voice` block — nothing to lint drafts against")
    elif not isinstance(voice, dict):
        out.append("error: `voice` must be a mapping")
    else:
        emoji = str(voice.get("emoji", "sparing")).strip().lower()
        if emoji not in EMOJI_POLICIES:
            out.append(f"error: `voice.emoji` must be one of {', '.join(EMOJI_POLICIES)} (got {emoji!r})")
        for key in ("banned", "avoid", "do", "dont", "traits"):
            if key in voice and not isinstance(voice[key], list):
                out.append(f"error: `voice.{key}` must be a list")

    platforms = data.get("platforms")
    if platforms is not None and not isinstance(platforms, dict):
        out.append("error: `platforms` must be a mapping of platform id -> overrides")

    out.extend(validate_visual(data))
    return out


# ── the visual identity (optional) ────────────────────────────────────────────
# A CONTRACT, not just a section: sibling plugins (campaign-plugin) read `visual:`
# straight out of this YAML file to style generated cards. Keep the shape flat and
# stable — every leaf is a scalar string — and only ever ADD optional keys:
#
#   visual:
#     colors:   {primary, accent, background, foreground}   # "#RRGGBB" (or "#RGB"), QUOTED
#     fonts:    {heading, body, heading_url, body_url}       # family names; *_url = stylesheet/font URL
#     logo:     {path, dark, light}                          # relative to the kit file, or absolute
#     wordmark: "Testco"                                     # the name as set in type
#
# `logo.dark` is the variant for DARK backgrounds, `logo.light` for LIGHT ones. Every
# problem in here is a warning, never an error: a kit with an absent or half-filled
# visual section is a normal kit, and a bad colour must never stop a voice edit saving.
VISUAL_COLORS = ("primary", "accent", "background", "foreground")
VISUAL_FONTS = ("heading", "body", "heading_url", "body_url")
VISUAL_LOGOS = ("path", "dark", "light")
VISUAL_KEYS = ("colors", "fonts", "logo", "wordmark")

_HEX = re.compile(r"^#(?:[0-9a-fA-F]{3}|[0-9a-fA-F]{6})$")


def is_hex_color(value: Any) -> bool:
    return isinstance(value, str) and bool(_HEX.match(value.strip()))


def _resolve_asset(value: str, base: Path) -> Path:
    p = Path(value).expanduser()
    return p if p.is_absolute() else base / p


def validate_visual(data: dict[str, Any] | None, base: Path | None = None) -> list[str]:
    """Warnings for the optional `visual:` section. Absent section = no output.

    ``base`` is the directory relative logo paths resolve against — the kit file's
    own directory by default.
    """
    raw = (data or {}).get("visual")
    if raw is None:
        return []
    if not isinstance(raw, dict):
        return ["warn: `visual` must be a mapping (colors / fonts / logo / wordmark) — ignoring it"]
    base = path().parent if base is None else base
    out: list[str] = []

    for key in raw:
        if key not in VISUAL_KEYS:
            out.append(f"warn: `visual.{key}` is not part of the visual contract ({', '.join(VISUAL_KEYS)}) — ignored")

    colors = raw.get("colors")
    if colors is not None and not isinstance(colors, dict):
        out.append("warn: `visual.colors` must be a mapping of role -> hex — ignoring it")
    elif isinstance(colors, dict):
        for key, value in colors.items():
            if key not in VISUAL_COLORS:
                out.append(f"warn: `visual.colors.{key}` is not a contract role ({', '.join(VISUAL_COLORS)}) — ignored")
            elif value is None:
                # `primary: #1F6FEB` parses as null — the # opened a comment.
                out.append(
                    f"warn: `visual.colors.{key}` is empty — quote hex values in YAML "
                    f'(`{key}: "#1F6FEB"`); an unquoted # starts a comment'
                )
            elif str(value).strip() == "":
                continue  # the blank template slot
            elif not is_hex_color(value):
                out.append(f'warn: `visual.colors.{key}` must be a hex colour like "#1F6FEB" (got {value!r}) — ignored')

    fonts = raw.get("fonts")
    if fonts is not None and not isinstance(fonts, dict):
        out.append("warn: `visual.fonts` must be a mapping (heading / body / heading_url / body_url) — ignoring it")
    elif isinstance(fonts, dict):
        for key, value in fonts.items():
            if key not in VISUAL_FONTS:
                out.append(f"warn: `visual.fonts.{key}` is not a contract key ({', '.join(VISUAL_FONTS)}) — ignored")
            elif value is not None and not isinstance(value, str):
                out.append(f"warn: `visual.fonts.{key}` must be a string — ignored")
            elif key.endswith("_url") and value and not value.strip().lower().startswith(("http://", "https://")):
                out.append(f"warn: `visual.fonts.{key}` must be an http(s) URL (got {value!r}) — ignored")

    logo = raw.get("logo")
    if isinstance(logo, str):
        out.append("warn: `visual.logo` is a bare path; write it as `logo: {path: ...}` — readers expect the mapping")
        logo = {"path": logo}
    if logo is not None and not isinstance(logo, dict):
        out.append("warn: `visual.logo` must be a mapping (path / dark / light) — ignoring it")
    elif isinstance(logo, dict):
        for key, value in logo.items():
            if key not in VISUAL_LOGOS:
                out.append(f"warn: `visual.logo.{key}` is not a contract key ({', '.join(VISUAL_LOGOS)}) — ignored")
            elif value is None or str(value).strip() == "":
                continue
            elif not isinstance(value, str):
                out.append(f"warn: `visual.logo.{key}` must be a file path — ignored")
            elif not _resolve_asset(value, base).is_file():
                out.append(f"warn: `visual.logo.{key}` file not found at {_resolve_asset(value, base)}")

    wordmark = raw.get("wordmark")
    if wordmark is not None and not isinstance(wordmark, str):
        out.append("warn: `visual.wordmark` must be a string — ignored")

    return out


def visual(data: dict[str, Any] | None, base: Path | None = None) -> dict[str, Any]:
    """The usable part of `visual:`, normalized: only valid, non-empty values survive.

    Logo paths come back ABSOLUTE (resolved against the kit's directory) with an
    ``exists`` map, so a consumer never has to know where the kit lives. Returns ``{}``
    when the kit has no visual identity.
    """
    raw = (data or {}).get("visual")
    if not isinstance(raw, dict):
        return {}
    base = path().parent if base is None else base
    out: dict[str, Any] = {}

    colors = raw.get("colors")
    if isinstance(colors, dict):
        good = {k: str(colors[k]).strip() for k in VISUAL_COLORS if is_hex_color(colors.get(k))}
        if good:
            out["colors"] = good

    fonts = raw.get("fonts")
    if isinstance(fonts, dict):
        good = {}
        for k in VISUAL_FONTS:
            v = fonts.get(k)
            if not isinstance(v, str) or not v.strip():
                continue
            if k.endswith("_url") and not v.strip().lower().startswith(("http://", "https://")):
                continue
            good[k] = v.strip()
        if good:
            out["fonts"] = good

    logo = raw.get("logo")
    if isinstance(logo, str):
        logo = {"path": logo}
    if isinstance(logo, dict):
        good = {}
        exists_ = {}
        for k in VISUAL_LOGOS:
            v = logo.get(k)
            if isinstance(v, str) and v.strip():
                resolved = _resolve_asset(v.strip(), base)
                good[k] = str(resolved)
                exists_[k] = resolved.is_file()
        if good:
            out["logo"] = {**good, "exists": exists_}

    wordmark = raw.get("wordmark")
    if isinstance(wordmark, str) and wordmark.strip():
        out["wordmark"] = wordmark.strip()

    return out


# ── the machine-checkable slices lint.py needs ────────────────────────────────
def _voice(data: dict[str, Any] | None) -> dict[str, Any]:
    v = (data or {}).get("voice")
    return v if isinstance(v, dict) else {}


def banned_phrases(data: dict[str, Any] | None) -> list[str]:
    """Phrases that are a hard fail in a draft."""
    return [str(x) for x in _voice(data).get("banned", []) if str(x).strip()]


def avoid_phrases(data: dict[str, Any] | None) -> list[str]:
    """Phrases that earn a warning — tired, not forbidden."""
    return [str(x) for x in _voice(data).get("avoid", []) if str(x).strip()]


def emoji_policy(data: dict[str, Any] | None) -> str:
    policy = str(_voice(data).get("emoji", "sparing")).strip().lower()
    return policy if policy in EMOJI_POLICIES else "sparing"


def brand_name(data: dict[str, Any] | None) -> str:
    """The brand's display name, whatever shape the kit put it in.

    ``brand:`` is documented as a scalar, but an agent writing the kit from an
    interview will sometimes nest it (``brand: {name: ..., product: ...}``) — which
    validates fine and then renders as "[object Object]" in the console header. Accept
    both rather than rejecting a kit that is otherwise correct and already in use.
    """
    raw = (data or {}).get("brand")
    if isinstance(raw, dict):
        for key in ("name", "brand", "title", "product"):
            if str(raw.get(key, "")).strip():
                return str(raw[key]).strip()
        return ""
    return str(raw or "").strip()


def disclosure(data: dict[str, Any] | None) -> dict[str, Any]:
    """The brand's standing disclosure policy — the label it uses and the relationships
    that always need declaring (an affiliate programme, staff who post about the product).
    Empty is a real answer for a brand that has no commercial relationships to declare."""
    row = (data or {}).get("disclosure")
    return row if isinstance(row, dict) else {}


def ctas(data: dict[str, Any] | None) -> list[str]:
    return [str(x) for x in (data or {}).get("ctas", []) if str(x).strip()]


def platform_overrides(data: dict[str, Any] | None, platform: str) -> dict[str, Any]:
    """House rules for one platform, e.g. ``{hashtag_norm: [2, 3], notes: "..."}``."""
    plats = (data or {}).get("platforms")
    if not isinstance(plats, dict):
        return {}
    row = plats.get(platform)
    return row if isinstance(row, dict) else {}


def pillar_names(data: dict[str, Any] | None) -> list[str]:
    pillars = (data or {}).get("pillars")
    if not isinstance(pillars, list):
        return []
    return [str(p.get("name", "")).strip() for p in pillars if isinstance(p, dict) and p.get("name")]


def pillar_mix(data: dict[str, Any] | None) -> dict[str, float]:
    """Target share of the calendar per pillar. Missing mixes spread the remainder evenly."""
    pillars = (data or {}).get("pillars")
    if not isinstance(pillars, list) or not pillars:
        return {}
    named = [p for p in pillars if isinstance(p, dict) and str(p.get("name", "")).strip()]
    if not named:
        return {}
    explicit = {
        str(p["name"]).strip(): float(p["mix"]) for p in named if p.get("mix") is not None and _is_number(p.get("mix"))
    }
    missing = [str(p["name"]).strip() for p in named if str(p["name"]).strip() not in explicit]
    if missing:
        remainder = max(0.0, 100.0 - sum(explicit.values()))
        share = remainder / len(missing) if remainder else 0.0
        for name in missing:
            explicit[name] = share
    return explicit


def _is_number(x: Any) -> bool:
    try:
        float(x)
    except (TypeError, ValueError):
        return False
    return True


# ── the drafting brief ────────────────────────────────────────────────────────
def brief(data: dict[str, Any] | None = None, section: str = "") -> str:
    """Compose the kit into the brief a writer reads before drafting.

    ``section`` narrows it to one block (voice / audiences / pillars / offers) when
    the whole kit would be more context than the task needs.
    """
    data = load() if data is None else data
    if not data:
        return (
            "No brand kit yet — every draft will sound like generic marketing until there is one.\n"
            f"Expected at: {path()}\n"
            "Run the `brand-kit-setup` skill to build it, or write one with social_save_brand_kit."
        )

    section = (section or "").strip().lower()
    blocks: dict[str, str] = {}

    head = [f"# Brand kit — {brand_name(data) or 'unnamed'}"]
    if data.get("positioning"):
        head.append(f"\n{data['positioning']}")
    if data.get("website"):
        head.append(f"\nSite: {data['website']}")
    blocks["header"] = "\n".join(head)

    audiences = data.get("audiences")
    if isinstance(audiences, list) and audiences:
        rows = ["## Audiences"]
        for a in audiences:
            if not isinstance(a, dict):
                rows.append(f"- {a}")
                continue
            line = f"- **{a.get('name', 'unnamed')}**"
            if a.get("cares_about"):
                line += f" — cares about: {a['cares_about']}"
            if a.get("avoid"):
                line += f". Avoid: {a['avoid']}"
            rows.append(line)
        blocks["audiences"] = "\n".join(rows)

    pillars = data.get("pillars")
    if isinstance(pillars, list) and pillars:
        mix = pillar_mix(data)
        rows = ["## Content pillars (target mix)"]
        for p in pillars:
            if not isinstance(p, dict):
                rows.append(f"- {p}")
                continue
            name = str(p.get("name", "unnamed")).strip()
            share = mix.get(name)
            head_ = f"- **{name}**" + (f" ({share:g}%)" if share else "")
            if p.get("description"):
                head_ += f" — {p['description']}"
            rows.append(head_)
        blocks["pillars"] = "\n".join(rows)

    voice = _voice(data)
    if voice:
        rows = ["## Voice"]
        if voice.get("traits"):
            rows.append(f"- Traits: {', '.join(str(t) for t in voice['traits'])}")
        if voice.get("person"):
            rows.append(f"- Speaks as: {voice['person']}")
        if voice.get("reading_level"):
            rows.append(f"- Reading level: {voice['reading_level']}")
        rows.append(f"- Emoji: {emoji_policy(data)}")
        for key, label in (("do", "Do"), ("dont", "Don't")):
            items = voice.get(key)
            if isinstance(items, list) and items:
                rows.append(f"- {label}:")
                rows.extend(f"    - {i}" for i in items)
        if banned_phrases(data):
            rows.append(f"- NEVER use: {', '.join(banned_phrases(data))}")
        if avoid_phrases(data):
            rows.append(f"- Avoid: {', '.join(avoid_phrases(data))}")
        blocks["voice"] = "\n".join(rows)

    disc = disclosure(data)
    if disc:
        rows = ["## Disclosure"]
        if disc.get("label"):
            rows.append(f"- Standard label: {disc['label']}")
        rels = disc.get("relationships")
        if isinstance(rels, list) and rels:
            rows.append("- Always declare: " + ", ".join(str(r) for r in rels))
        if disc.get("policy"):
            rows.append(f"- House rule: {disc['policy']}")
        rows.append("- A disclosure goes in the post itself, early enough to read before the fold.")
        blocks["disclosure"] = "\n".join(rows)

    proof = data.get("proof")
    if isinstance(proof, list) and proof:
        blocks["proof"] = "## Proof points (use real numbers, never invent them)\n" + "\n".join(f"- {p}" for p in proof)

    offers = data.get("offers")
    if isinstance(offers, list) and offers:
        rows = ["## Offers"]
        for o in offers:
            if isinstance(o, dict):
                rows.append(f"- {o.get('name', 'unnamed')}" + (f" — {o['url']}" if o.get("url") else ""))
            else:
                rows.append(f"- {o}")
        blocks["offers"] = "\n".join(rows)

    if ctas(data):
        blocks["ctas"] = "## CTAs to rotate\n" + "\n".join(f"- {c}" for c in ctas(data))

    handles = data.get("handles")
    if isinstance(handles, dict) and handles:
        blocks["handles"] = "## Handles\n" + "\n".join(f"- {k}: {v}" for k, v in handles.items())

    plats = data.get("platforms")
    if isinstance(plats, dict) and plats:
        rows = ["## House rules per platform (override the shipped norms)"]
        for pid, over in plats.items():
            if isinstance(over, dict):
                bits = ", ".join(f"{k}={v}" for k, v in over.items())
                rows.append(f"- **{pid}**: {bits}")
        blocks["platforms"] = "\n".join(rows)

    cadence = data.get("cadence")
    if isinstance(cadence, dict) and cadence:
        blocks["cadence"] = "## Cadence\n" + "\n".join(f"- {k}: {v}" for k, v in cadence.items())

    vis = visual(data)
    if vis or data.get("visual") is not None:
        rows = ["## Visual identity"]
        for k, v in vis.get("colors", {}).items():
            rows.append(f"- Colour {k}: {v}")
        fonts = vis.get("fonts", {})
        for k in ("heading", "body"):
            if fonts.get(k):
                rows.append(
                    f"- {k.capitalize()} font: {fonts[k]}"
                    + (f" ({fonts[k + '_url']})" if fonts.get(k + "_url") else "")
                )
        logo = vis.get("logo", {})
        for k, label in (
            ("path", "Logo"),
            ("dark", "Logo on dark backgrounds"),
            ("light", "Logo on light backgrounds"),
        ):
            if logo.get(k):
                rows.append(f"- {label}: {logo[k]}" + ("" if logo["exists"].get(k) else " (FILE MISSING)"))
        if vis.get("wordmark"):
            rows.append(f"- Wordmark: {vis['wordmark']}")
        problems = validate_visual(data)
        if problems:
            rows.append("- Problems:")
            rows.extend(f"    - {p[5:].strip()}" for p in problems)
        if len(rows) == 1:
            rows.append("- (empty)")
        blocks["visual"] = "\n".join(rows)

    if section:
        # Accept a few natural aliases for the block names.
        alias = {
            "audience": "audiences",
            "pillar": "pillars",
            "cta": "ctas",
            "offer": "offers",
            "visuals": "visual",
            "colors": "visual",
            "colours": "visual",
            "fonts": "visual",
            "logo": "visual",
        }
        key = alias.get(section, section)
        if key in blocks:
            return blocks[key]
        return f"No `{section}` section in the brand kit. Sections: {', '.join(k for k in blocks if k != 'header')}."

    return "\n\n".join(blocks.values())


# A fill-in starter the setup skill walks the operator through. Comments explain
# each field so an operator editing it by hand knows what belongs there.
TEMPLATE = """\
# Brand kit — the file that makes every draft sound like you.
# Edit freely; the agent reads this before it writes anything.

brand: ""                 # the name that posts
positioning: ""           # one line: what you do, for whom, and why it's different
website: ""

# Who you're actually talking to. One entry per real segment — not personas
# invented to fill the file.
audiences:
  - name: ""
    cares_about: ""       # the problem they'd stay up late to solve
    avoid: ""             # language or framing that loses them

# The 3–5 themes you post about, and how much of the calendar each should own.
# `mix` values should total 100.
pillars:
  - name: ""
    description: ""
    mix: 40
  - name: ""
    description: ""
    mix: 30
  - name: ""
    description: ""
    mix: 30

voice:
  traits: []              # e.g. [direct, specific, dry]
  person: ""              # e.g. "first-person singular — a founder, not a company"
  reading_level: plain
  emoji: sparing          # none | sparing | liberal
  do:
    - ""
  dont:
    - ""
  banned: []              # hard fail in the linter — words you will never publish
  avoid: []               # warned, not blocked — tired phrasing

# Real, checkable facts. The agent may only cite numbers that appear here.
proof: []

offers:
  - name: ""
    url: ""

# Commercial relationships that have to be declared in the post itself.
disclosure:
  label: ""               # the wording you use, e.g. "#ad" or "Sponsored by Acme"
  relationships: []       # standing ones: affiliate, gifted, employee, own_product
  policy: ""              # any house rule beyond the legal minimum

ctas: []                  # rotate these instead of ending every post the same way

handles: {}               # e.g. {x: "@you", linkedin: "your-company"}

# Optional: override the shipped platform norms with your house rules.
platforms: {}

cadence: {}               # e.g. {x: "5/week", linkedin: "3/week"}

# Optional: the look. Other plugins (e.g. campaign cards) style output from this.
# QUOTE hex colours — an unquoted # starts a YAML comment.
visual:
  colors:
    primary: ""           # e.g. "#1F6FEB"
    accent: ""
    background: ""
    foreground: ""
  fonts:
    heading: ""           # a family name, e.g. Space Grotesk
    body: ""
    heading_url: ""       # optional: a Google Fonts css2 link or font URL
    body_url: ""
  logo:
    path: ""              # relative to this file, or absolute
    dark: ""              # variant for dark backgrounds
    light: ""             # variant for light backgrounds
  wordmark: ""
"""
