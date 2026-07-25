---
name: performance-review
description: >-
  Use to close the loop — record what published posts actually did, and work out what that means
  for the next calendar. Run it monthly, or before planning. Triggers: "how did last month do",
  "what's working", "here are the numbers", "review performance", "should we keep doing X",
  "what should we do more of".
tools: [social_record_results, social_performance, social_queue_list, social_brand_kit, social_calendar]
---

# Reading the results

Without this, the agent is write-only: it plans, drafts, and never finds out. Every calendar
becomes the last one repeated with different words.

It's also the place where a marketing agent is most likely to say something confident and
wrong, so most of this skill is about restraint.

## 1. Get the numbers in

There's no analytics API here — the operator reads them off the platform. Make that as cheap
as possible: ask for a batch, in whatever form they have it, and record it.

```
social_record_results(post_id=12, impressions=4200, engagements=310, clicks=48,
                      outcome="two demo requests, one from a customer we'd been chasing")
```

`outcome` matters more than the counts. At the scale most brands operate at, "a customer
replied and booked a call" is real signal and "impressions were up 12%" is weather. Ask
directly: *did anything actually come of any of these?*

If the operator has no numbers, that's worth saying plainly — you can't review what nobody
measured, and the fix is a five-minute habit, not a bigger report.

## 2. Look, honestly

`social_performance(days=90)` groups by platform, pillar, and length, and reports its own
sample size.

**Then be sceptical of it.** The failure mode here isn't missing a pattern, it's inventing one:

- **Under ~8 posts, there is nothing to see.** The tool refuses to compare and so should you.
- **Under ~4 posts in a group, that group isn't comparable to another.** Two posts averaging 6%
  doesn't beat nine averaging 4%.
- **One viral post distorts every average it's in.** Say when a group's mean is carried by a
  single outlier, and report the median alongside it.
- **Timing, luck, and reach confound everything.** A post that landed the day a competitor made
  news isn't a lesson about your copy.
- **Correlation runs both ways.** If long posts perform better, it may be that the topics worth
  writing at length about are simply better topics.

State the sample size in your own summary, every time. "Carousels did better (n=3)" is honest;
"carousels do better" is not.

## 3. Turn it into one change

The output is not a report. It's **one hypothesis to test next fortnight**, phrased so it can
fail:

> "Posts that open with a specific number got roughly twice the engagement rate of ones that
> open with a question, across 11 posts. Next fortnight I'll open six of eight with a number
> and we'll see whether it holds."

One change at a time, or you learn nothing from the result. Write the hypothesis into the
calendar's notes so the next review can check it rather than starting fresh.

## 4. Feed it back

When something is established rather than suspected, put it where it will be used:

- A voice or format rule that keeps proving out → the **brand kit** (`voice.do`, or a house
  rule under `platforms:`).
- Something about how the platform behaves → that's a **norm**; the `platform-norms` skill
  records it with sources.
- A pillar that consistently underperforms → raise it with the operator. It may need retiring,
  or it may be the one that attracts the right ten people rather than the wrong thousand. That
  distinction is theirs to make, not yours — say which pillars look weak on engagement and ask
  whether that matters for what they're for.

## What to tell the operator

Lead with what came of the work — replies, customers, opportunities — then the rates, then the
one thing you'd change. If the honest answer is "three months in, nothing here is
distinguishable from noise", say that. It's more useful than a manufactured insight, and it
protects them from rebuilding a strategy around an accident.
