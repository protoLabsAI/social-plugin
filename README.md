# Social Studio — a protoAgent plugin

Organic social marketing for [protoAgent](https://github.com/protoLabsAI/protoAgent): plan a
calendar, draft posts that sound like *your* brand and read as native to each platform, catch
the mistakes before a human sees them, and hand back a copy-ready pack.

**It never posts anywhere.** No platform credentials, no API keys, no outbound calls. The agent
produces the content; a person publishes it. That's a deliberate boundary — see
[Why draft-only](#why-draft-only).

## What it gives the agent

| Piece | What it does |
|---|---|
| **Brand kit** | One YAML file — audiences, content pillars, voice, banned words, proof points, CTAs. Read before every draft, so posts sound like the brand instead of like marketing. |
| **Platform limits** | What nine surfaces *enforce*: character caps, field caps, image dimensions, whether captions make links clickable. Compiled in, because the platform rejects the post otherwise. |
| **Platform norms** | What currently *works* there — length band, hashtag counts, the "…more" fold, link demotion. Researched by the agent, stored with its sources and the date, editable by you. Never compiled in. |
| **Content queue** | A board — idea → drafted → needs edit → approved → scheduled → posted — with pillar and campaign tagging, so the calendar stays balanced and nothing gets lost. |
| **Linter** | Grades a draft 0–100 against the platform and the brand: over-length, hashtag spam, demoted links, missing alt text, banned phrases, and the cadence that makes copy read as machine-written. |
| **Export** | A markdown pack with every approved post in its own copy block, in send order — or CSV for a scheduling tool. |
| **Crew** | `social_writer` and `social_editor` subagents, so a batch of posts isn't nine variations of one sentence. |
| **Skills** | `brand-kit-setup`, `platform-norms`, `content-calendar`, `draft-post`, `repurpose`, `engagement-prep`. |
| **View** | A "Social Studio" rail panel: the queue as a board, with a copy button on every card. |

Platforms carried: X, LinkedIn, Instagram, Threads, Bluesky, TikTok, YouTube, Facebook, Reddit.

## Quick start

```bash
# In protoAgent — install, then enable (install is not consent)
protoagent plugin install https://github.com/protoLabsAI/social-plugin
```

Enable `social` in **System → Plugins**, then in chat:

```
Set up our brand kit.
```

That runs the `brand-kit-setup` interview. Twenty minutes of real answers, and every draft
afterwards is downstream of them. Then:

```
Research the norms for LinkedIn.  → dated, sourced norms on file for the linter to use
Plan two weeks of content.        → a balanced calendar, seeded with concrete ideas
Draft the Tuesday LinkedIn post.  → written native to the surface, linted, queued
Export what I've approved.        → a copy-ready pack
```

## Settings

| Key | Default | What it's for |
|---|---|---|
| `data_dir` | `~/.protoagent/social` (per instance) | Brand kit, queue database, exports. Point it at a synced or version-controlled folder if you want the kit in git. |
| `brand_kit_path` | `<data_dir>/brand-kit.yaml` | Override the kit's path alone — useful when the kit lives in a repo but the queue stays local. |
| `active_platforms` | `x, linkedin, instagram, bluesky` | The surfaces this brand actually posts to. Specs for the rest stay available on request. |

## The brand kit

Plain YAML, meant to be edited by hand as well as by the agent:

```yaml
brand: Testco
positioning: Deployment tooling for teams too small to have a platform team.

audiences:
  - name: Solo founders
    cares_about: shipping without hiring a devops engineer
    avoid: enterprise procurement language

pillars:
  - { name: Build in public, description: what shipped and what broke, mix: 60 }
  - { name: Teardowns,       description: how other people's infra works, mix: 40 }

voice:
  traits: [direct, specific, dry]
  person: first-person singular — a founder, not a company
  emoji: sparing
  do:   ["name the number"]
  dont: ["open with a rhetorical question"]
  banned: [synergy, leverage]     # hard failure in the linter
  avoid:  [best-in-class]         # warning

proof:
  - 4,000 developers deploy with it weekly

ctas: ["Try it free"]
platforms:
  linkedin: { hashtag_norm: [2, 3] }   # house rules beat researched norms
```

Two things in here do real work beyond flavour:

- **`proof`** is the only source of numbers the agent is permitted to cite. Everything else it
  has to research and attribute, or ask you about. A social agent that invents a statistic
  costs more than one that posts nothing.
- **`banned`** is enforced mechanically, not suggested. A draft containing one is `blocked`.

## Platform norms

Hard limits are compiled in — X caps at 280 characters, YouTube titles at 100 — because the
platform enforces them and correcting one is a version bump, not a guess.

**Everything soft is not.** How long a post should be, how many hashtags read as native,
whether an external link costs you reach, where the "…more" fold falls: all of that drifts as
the platforms retune their ranking. A constant compiled into a plugin would still be asserting
2026's folklore in 2029, with the same confidence and none of the truth.

So the agent researches it and writes down what it found, with sources and a date, next to your
brand kit:

```yaml
# platform-norms.yaml — written by the agent, owned by you
linkedin:
  checked: 2026-07-24
  sources: ["https://...", "https://..."]
  sweet_spot: [900, 1800]
  hashtag_norm: [3, 5]
  fold: 210
  link_penalty: true
  link_workaround: drop the link in the first comment and say so in the post
  alt_text: recommended
  notes: the first-comment link trick still measurably beats an in-body link
```

`sources` is required — the write is refused without it, because a norm nobody can check is a
guess wearing a number. Norms older than 180 days get flagged for re-checking.

**With no norms on file, the linter says so and skips those checks.** It never fills the gap
with a plausible threshold:

```
linkedin · 640 chars · score 100/100 · SHIP
Clean — nothing to fix.

· [no_norms] No norms on file for linkedin — checked hard limits and brand rules only.
    → Research the current norms and record them with social_record_norms.
```

Say *"research the norms for LinkedIn"* to fill it in, or write the file yourself. Your brand
kit's `platforms:` house rules beat researched norms either way — what you decided outranks
what the agent read.

## The linter

```
linkedin · 1,240 chars · score 74/100 · REVISE

! [link_in_body] 1 link(s) in the body — LinkedIn demotes posts that send people away.
    → Drop the link in the first comment and say so in the post.
! [ai_tell] "let's dive in" is a cadence readers now clock as machine-written.
    → Say it the way you'd say it out loud.
· [fold] Only the first ~210 characters show before '…more': "We've been thinking a lot about…"
    → Everything that earns the click has to be above that line.
```

Errors block, warnings cost 8 points, notes cost 2. `blocked` never reaches the operator.

## Why draft-only

Publishing was left out on purpose, not for lack of time:

- **Platform APIs are the expensive, brittle part.** Each is its own OAuth app, review process,
  and rate limit; X's write tier alone is a monthly bill. That's a lot of plumbing to build
  before knowing whether the *content* is any good.
- **A human between the agent and the public feed is worth keeping.** The failure mode of an
  autonomous poster isn't a typo — it's a confident, wrong, permanent, screenshot-able post.
- **Nothing here is wasted if that changes.** The brand kit, the linter, the queue, and the
  export are the same whether a person or an API sends the post. Publishing would be one
  additional tool reading the same `approved` rows.

If you want automation today, export CSV and import it into whatever scheduler you already pay
for.

## Development

```bash
python3.12 -m venv .venv && .venv/bin/pip install -r requirements-dev.txt ruff
.venv/bin/python -m pytest -q      # 163 tests, no protoAgent host required
.venv/bin/ruff check . && .venv/bin/ruff format --check .
```

The suite is host-free by design: every `graph.*` import lives inside a function, so the whole
plugin imports and tests with nothing but `fastapi`, `langchain-core`, and `pyyaml`. `SOCIAL_DIR`
is redirected to a temp dir for every test, so a bug in a path helper can't touch a real queue.

## Licence

MIT.
