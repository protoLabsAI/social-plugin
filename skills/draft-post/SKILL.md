---
name: draft-post
description: >-
  Use to write social copy — one post or a batch, for any platform. Covers hooks, native
  structure per surface, the lint-and-fix loop, and getting to an approved queue item. Triggers:
  "write a post about X", "draft something for LinkedIn", "turn this into a tweet", "we need a
  post for the launch", "draft the ideas in the queue".
tools: [social_brand_kit, social_platform_spec, social_check, social_queue_add, social_queue_update, social_queue_list]
---

# Drafting

## Read first, write second

1. `social_brand_kit()` — voice, banned words, proof points, CTAs. This overrides any house
   style you carry from pretraining.
2. `social_platform_spec(platform)` — the hard character limit, plus whatever norms are on
   file (the fold, the hashtag count, whether links are demoted) and **when they were last
   checked**.

Skipping either produces the same post everyone else's AI produces.

If it reports *no norms on file*, or flags them as stale, run the `platform-norms` skill
first — it's ten minutes of research and it's the difference between writing to how the
platform works now and writing to how it worked whenever the model was trained. Nothing soft
is compiled into this plugin, so an unresearched platform genuinely has no length band or
hashtag guidance behind it, and the linter will tell you it skipped those checks rather than
invent a threshold.

## The one rule about facts

**Only cite numbers and claims that appear in the brand kit's proof points.** If the post needs
a fact you don't have, either research it with `web_search`/`fetch_url` and cite the source, or
ask the operator. Never estimate a metric into a post. A fabricated number is the single failure
that costs a brand more than every clumsy sentence combined.

But refusing to invent a number is not a reason to stop working. Draft the post with the proof
points you *can* stand behind, queue it, and put the gap in one line underneath — "I left the
adoption figure out; give me the number and I'll add it." Handing back a question and no draft
turns one missing statistic into a wasted turn.

## Write

**The hook is the post.** The first few words decide the scroll, and on the surfaces that
truncate, everything above the '…more' fold is all most people ever see. Where that line falls
is a researched norm, not a constant — `social_check` reports its position and what's above it
when the platform's norms are on file, and stays quiet about it when they aren't.

Openers that work: a specific number, a concrete moment, a claim someone could disagree with,
the thing that went wrong. Openers that don't: "In today's...", a rhetorical question, "Excited
to announce", any sentence that could open a post about anything.

**Be specific.** Replace every abstraction you can with a fact — a version, a name, a duration,
a failure mode, a number from the proof points. Specificity is what separates a brand's voice
from a template.

**One idea per post.** Two good ideas are two posts.

**Write native, don't translate.** The same idea becomes a different artifact per surface.
What follows is craft — the character of each place — not thresholds. Anything numeric (how
long, how many hashtags, where the fold sits, whether a link costs you reach) comes from the
platform's researched norms, because those move and this doesn't:

- **X** — one sharp claim, or a thread where post 1 stands alone and each post earns the next.
  Line breaks, no preamble.
- **LinkedIn** — a concrete story or a number, then what it means. Short paragraphs with white
  space. Ends on a question or invitation, never a hard sell.
- **Instagram** — the visual carries the idea; the caption adds what the image can't hold.
  Always write alt text.
- **Threads / Bluesky** — conversational and short. These audiences smell scheduled corporate
  copy instantly; write like a person talking.
- **TikTok / YouTube** — the script and the title/thumbnail are the deliverable, not the caption.
- **Reddit** — write as a community member, give the substance away in the post, disclose any
  affiliation plainly. Read the subreddit's rules before proposing anything.

**Close with intent.** Rotate the brand kit's CTAs; don't end every post the same way. A real
question beats a manufactured one.

## Lint and fix

`social_check(text, platform, has_media=..., alt_text=...)`.

- **blocked** — fix every error before showing the operator anything.
- **revise** — fix the warnings you can fix without gutting the point. Where a warning is wrong
  for this post, keep the copy and say why in one line.
- The `ai_tell` findings matter more than their weight suggests. Those phrases are why readers
  can spot generated copy at a glance; rewrite the line the way you'd say it out loud.

Re-check after editing. Then queue it:

```
social_queue_add(platform=..., body=..., status="drafted", pillar=..., hashtags=..., alt_text=...)
```

Drafting against an existing idea? Use `social_queue_update(post_id, body=..., status="drafted")`
so the plan and the copy stay the same row.

## Batches

For more than two or three posts, fan out `social_writer` — one call per post. A single context
drafting nine posts converges on nine variations of the same sentence, because it keeps reading
its own output. Then run `social_editor` over the batch before the operator sees it.

## Handing over

Show the copy in full, with the platform, the character count, and the lint score. Flag any
assumption you made. Then stop — **`approved` is the operator's word, never yours.** Once they
approve, move the status and offer `social_export` to produce the publish pack.
