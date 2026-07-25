---
name: content-calendar
description: >-
  Use to plan what goes out and when — a two-week or monthly calendar balanced across the brand's
  content pillars and platforms, seeded with concrete post ideas. Triggers: "plan our content",
  "what should we post", "build a calendar", "we need a month of posts", "fill the queue", or a
  review of what's already scheduled.
tools: [social_brand_kit, social_platform_spec, social_calendar, social_queue_add, social_queue_list]
---

# Planning the calendar

A calendar's job is to stop two failure modes: posting nothing for eleven days then five times
on a Tuesday, and posting about the product every single time. Both are solved by planning the
*shape* first and writing the copy later.

## 1. Read the ground truth

- `social_brand_kit()` — pillars and their target mix, audiences, offers, cadence.
- `social_calendar(days=...)` — what's already scheduled. Never plan into an occupied slot.
- `social_queue_list(status="open")` — ideas and drafts already waiting. Schedule those before
  inventing new ones; an unused idea in the queue is wasted work.

If there's no brand kit, stop and run `brand-kit-setup` first. Planning a calendar without
pillars produces a list of topics nobody agreed to.

## 2. Ask for what only the operator knows

Two or three questions, no more:
- What's actually happening in this window? Launches, events, announcements, deadlines, travel.
- Anything not to touch right now?
- Is there a piece of source material to mine — a release, a talk, a post, a customer call?
  (If yes, `repurpose` will get more out of it than inventing from scratch.)

## 3. Lay out the shape

Work out the slots before the ideas:

- **Cadence per platform** from the brand kit. Respect it — proposing daily LinkedIn to someone
  who manages twice a week just generates work that won't happen.
- **Pillar mix.** Allocate slots to pillars in the target proportions across the whole window,
  not within each day. Check the mix as you go; `social_calendar` reports actual-vs-target.
- **Format variety** inside each pillar. Five text posts in a row reads as a feed on autopilot,
  even when the ideas are good. Rotate: a story, a specific number, a strong opinion, a
  behind-the-scenes, a question, a resource, a customer moment.
- **Timing.** Weekday business hours in the audience's timezone for professional surfaces;
  spread posts out rather than clustering. Don't overthink exact minutes — consistency beats
  a perfect hour.

Present the shape as a table and get a yes before you fill it. Cheap to change now, expensive
after nine drafts exist.

## 4. Seed the ideas

For each slot, queue an idea — not a finished post:

```
social_queue_add(platform=..., status="idea", pillar=..., scheduled_for="2026-08-04T09:30",
                 body="<the angle in one line — the specific claim or story>",
                 notes="<the source, the proof point to use, the format>")
```

Make each idea specific enough that a writer could draft it without asking a question. "Post
about onboarding" is not an idea. "The three-question onboarding survey that cut our churn —
what we asked and what we changed" is.

Where an idea needs a fact the brand kit doesn't have, put the question in `notes` so it gets
resolved before drafting rather than invented during it.

## 5. Hand back

Show the calendar with `social_calendar()` and report:
- the pillar mix against target, and any pillar with nothing scheduled;
- the slots whose idea still needs a fact from the operator;
- what you'd draft first.

Then offer to draft — `draft-post` for one, or fan out `social_writer` across a batch. Drafting
everything unasked burns the operator's review attention on posts they might have cut at the
idea stage.
