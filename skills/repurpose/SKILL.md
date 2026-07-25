---
name: repurpose
description: >-
  Use to turn one piece of source material into a batch of native posts across platforms — a
  blog post, release notes, a talk, a podcast, a customer call, a long document. Triggers:
  "turn this into posts", "repurpose this", "we published X, get social out of it", "make a
  week of content from this", "what can we do with this transcript".
tools: [social_brand_kit, social_platform_spec, social_check, social_queue_add, social_queue_list]
---

# Repurposing

One good source usually contains five to ten posts. Most brands extract one — a link with
"check out our new blog post" — and waste the rest.

The failure mode to avoid is **summarising**. A summary of an article is not a post; it's an
advert for an article, and it performs like one. The job is to find the ideas *inside* the
source that stand on their own, and write each as a native post that's worth reading even by
someone who never clicks through.

## 1. Mine the source

Read it properly (`fetch_url` for a link, or the text the operator supplies). Pull out:

- **Claims** — anything arguable. Disagreement is distribution.
- **Numbers** — every metric, benchmark, duration, cost. Note which are already in the brand
  kit's proof points and which are new (new ones need the operator's confirmation before they
  go in a post).
- **Moments** — the specific story, the thing that broke, the customer sentence, the decision.
- **How-tos** — any step-by-step worth lifting whole.
- **Quotable lines** — sentences that already sound like a post.
- **The counterintuitive bit** — what surprised the author. This is almost always the best post
  in the source, and almost always buried.

List what you found before writing anything, and let the operator strike what's off-limits.

## 2. Map ideas to surfaces

Match each idea to where it actually belongs — not everything to everywhere:

- A contrarian claim → X, LinkedIn
- A story with a lesson → LinkedIn, Threads
- A number with context → X, LinkedIn
- A how-to → a carousel or an X thread; a Reel or Short if it's visual
- A quotable line → a quote card for Instagram, a plain post on Bluesky
- A deep, community-relevant answer → Reddit, written as a member, substance given away

Check the pillar mix and the calendar (`social_calendar`) so a repurpose batch doesn't flood the
schedule with one pillar for two weeks.

## 3. Write each one native

Follow `draft-post`. Two rules matter more here than anywhere:

- **Every post must stand alone.** If it only makes sense to someone who read the source, it
  isn't finished. Give the idea away; the link is a bonus, not the payload.
- **Vary the shape.** Six posts from one source that all open the same way read as a bot. Rotate
  hook types: number, story, claim, question, mistake, before/after.

Spread the batch across days rather than posting it in one block, and stagger the platforms.

For anything over three posts, fan out `social_writer` — one call per post — then run
`social_editor` across the batch to catch the sameness a single writing context won't see in
itself.

## 4. Queue with provenance

Queue each with `source` set to the original URL or a short description, and `notes` recording
which part of the source it came from:

```
social_queue_add(platform="linkedin", status="drafted", pillar="...", source="https://...",
                 notes="from the 'why we rewrote the scheduler' section", body="...")
```

Provenance pays off twice: the operator can check a claim against the source in seconds, and
you can tell later whether a source was fully mined or still has posts left in it.

## 5. Report

Hand back: what you found in the source, what became a post and what you left, the schedule, and
any number you had to leave out because it wasn't in the proof points and you couldn't verify it.
