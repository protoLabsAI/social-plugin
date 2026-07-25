---
name: brand-kit-setup
description: >-
  Use to build or overhaul the brand kit — the file that makes every draft sound like this brand
  instead of generic marketing. Run it before the first post, and again when the positioning,
  audience, or voice changes. Triggers: "set up the brand", "who are we talking to", "define our
  voice", "the posts don't sound like us", "onboard me", or any drafting request made when
  social_brand_kit reports no kit exists.
tools: [social_brand_kit, social_save_brand_kit, social_platform_spec]
---

# Building the brand kit

Everything this agent writes is downstream of this file. A vague kit produces vague posts —
so the goal of this session is **specifics**, not a filled-in form.

Interview the operator. Do not generate a kit from your assumptions and ask them to approve
it; that produces a document describing a company that doesn't exist. Ask, listen, and write
down what they actually say — in their words where the words are good.

## Before you start

Call `social_brand_kit()`. If a kit already exists, this is an amendment: read it back,
ask what's changed, and preserve everything that still holds. Never overwrite a kit
wholesale without showing the operator what's being replaced.

## The interview

Work through these in order. Keep it conversational — two or three questions per turn, not
a questionnaire dump. Push back when an answer is generic; "we help businesses grow" is not
positioning and should not survive into the file.

**1. Who posts, and what do they do?**
- Brand name, and whether posts speak as a company ("we") or a person ("I"). This one answer
  changes every draft — a founder's account and a company account are different products.
- Positioning in one line: what you do, for whom, and why it's different from the obvious
  alternative. If they give you a paragraph, hand back your one-line compression and let
  them correct it.

**2. Who are we talking to?**
- One entry per real segment. Ask for a person they know, not a persona.
- For each: what problem would they stay up late to solve? And what language loses them —
  the jargon, the framing, the tone that makes them close the tab?
- Two well-drawn audiences beat five invented ones.

**3. What do we post about?** (the pillars)
- 3–5 themes. Get concrete: "build in public — what we shipped and what broke" is a pillar;
  "thought leadership" is not.
- Assign a target mix that totals 100. This is what keeps the calendar from becoming
  all-product-announcements. If they resist numbers, propose a split and let them adjust.

**4. How do we sound?**
- Three to five voice traits, then immediately test them: "give me a sentence that sounds
  like us, and one that doesn't." The contrast pair teaches you more than the adjectives.
- `do` and `dont` rules — concrete and checkable ("name the number", "never open with a
  rhetorical question").
- **Banned words** — things they will never publish. These become hard failures in the
  linter, so only put real ones here. Ask directly: "what word makes you wince?"
- **Avoid** — tired phrasing that earns a warning rather than a block.
- Emoji policy: none / sparing / liberal.

**5. What's actually true?** (proof points)
- Real, checkable facts and numbers: users, revenue, benchmarks, customers, dates.
- Say plainly why this matters: **the agent may only cite numbers that appear here.** A
  social agent that invents a statistic damages the brand faster than one that posts nothing.

**6. What are we selling, and what do we ask for?**
- Offers with URLs.
- A menu of CTAs to rotate, so every post doesn't end the same way.
- Handles per platform.

**7. Where and how often?**
- Which platforms are actually in scope. Fewer, done natively, beats all of them done badly —
  use `social_platform_spec()` to show them what each surface demands before they commit.
- Realistic cadence per platform. Ask what they can sustain on a bad week, not a good one.
- Any house rules that override the shipped norms (e.g. "we never do the first-comment link
  trick") go in `platforms:`.

## Writing the file

Compose the whole YAML document and save it with `social_save_brand_kit(yaml_text)`. Send the
complete document — the save replaces the file.

Then read back the parts that will surprise them: the banned list, the pillar mix, and the
proof points. Say explicitly: "I'll only use numbers from this list — if I need one that isn't
here, I'll ask."

If the tool reports gaps, tell the operator which ones matter now and which can wait. An
incomplete kit that's honest beats a complete one that's invented.

## Ending well

Offer the obvious next step: plan a first two-week calendar (`content-calendar`), or draft one
post against a pillar so they can see the voice land (`draft-post`). Seeing one real post in
their voice is what makes the kit feel worth the twenty minutes.
