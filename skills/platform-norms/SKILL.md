---
name: platform-norms
description: >-
  Use to research and record how a platform currently behaves — the length band that performs,
  hashtag counts, where the fold falls, whether links get demoted, what flops. Run it when
  social_check reports "no norms on file", when norms are flagged stale, or when the operator
  says results have changed. Triggers: "research the norms", "what works on LinkedIn now",
  "our reach dropped", "refresh the platform rules", "no norms on file".
tools: [social_platform_spec, social_record_norms]
---

# Researching platform norms

Nothing soft is built into this plugin. Character caps are compiled in because the platform
enforces them; everything else — how long a post should be, how many hashtags read as native,
whether an external link costs you reach — is researched, dated, and stored where the operator
can see and edit it.

That's deliberate. A hashtag rule hard-coded in 2026 is still being asserted in 2029, with the
same confidence and none of the truth. **A norm with no date and no source is a guess wearing a
number.**

## When to run this

- `social_check` said *no norms on file* for a platform you're about to write for.
- Norms are flagged stale (older than ~180 days).
- The operator says reach or engagement changed and nobody knows why.
- A platform announced a ranking or format change.

## 1. Look at what's on file

`social_platform_spec(platform)` — hard limits, whatever norms exist, and when they were last
checked. `social_platform_spec()` with no argument shows freshness across every platform, so
you can see what's missing at a glance.

## 2. Research it properly

Use `web_search` and `fetch_url`. What you're after, in rough order of value:

1. **The platform's own engineering or creator posts.** Primary sources beat commentary.
2. **Recent, dated analyses with a sample size** — someone who measured a few thousand posts
   this year beats a listicle with no date.
3. **Practitioner reports** where they agree with each other.

Weigh sources honestly:

- **Prefer recent.** A 2024 study of a 2026 ranking model is archaeology.
- **Distrust anything selling a scheduling tool.** Their "best time to post" data is marketing
  with a chart attached.
- **Watch for folklore.** Some norms get repeated for years after they stopped being true —
  the "external links are punished" claim in particular is asserted far more often than it's
  measured. If the evidence is thin, record `link_penalty` as false, or leave it out and put
  what you actually found in `notes`. Leaving a field out is a real answer.
- **Two independent sources or it's a note, not a norm.**

## 3. Record what you found

```
social_record_norms(platform="linkedin", norms_yaml="""
sources: ["https://...", "https://..."]
sweet_spot: [900, 1800]
hashtag_norm: [3, 5]
fold: 210
link_penalty: true
link_workaround: drop the link in the first comment and say so in the post
alt_text: recommended
hook: the first two lines are all that show before 'see more'
native_shape: short paragraphs with white space; a story or a number, then the lesson
flops: corporate announcement voice, buzzword stacks, obvious AI cadence
notes: the first-comment link trick still measurably beats an in-body link
""")
```

`sources` is required and the write is refused without it. Every other key is optional, and
the record merges into what's already there — re-checking one field won't wipe the rest.

**Only record what you actually found.** If the research didn't settle the hashtag question,
omit `hashtag_norm`. The linter skips checks it has no norm for and says so; that is a much
better outcome than a threshold you made up, because the operator can see the gap.

## 4. Report

Tell the operator what you recorded, what you couldn't establish, and anything that contradicts
what they believed. A norm that changed since they last looked is the most useful thing you can
hand back — it usually explains a number they've been staring at.

Then offer to re-lint anything already in the queue for that platform: drafts approved under
the old norms may read differently under the new ones.
