---
name: crisis-response
description: >-
  Use the moment scheduled content becomes a liability — a crisis at the company, an outage, a
  public tragedy, a story breaking about the brand or its industry, a post going wrong. Covers
  holding the queue, drafting a holding statement, and deciding when to resume. Triggers: "hold
  everything", "pause the posts", "we have a situation", "this is blowing up", "should we still
  post today", "something happened".
tools: [social_hold_queue, social_release_queue, social_calendar, social_queue_list, social_queue_update, social_brand_kit]
---

# When not to post

Most brand damage in a crisis isn't caused by the crisis. It's caused by the cheerful product
post that goes out in the middle of it, scheduled a week earlier by someone who couldn't have
known. That post gets screenshotted, and the screenshot outlives the campaign.

You own a queue of scheduled content. Stopping it is the single most useful thing you can do
in the first ten minutes, and it is almost free to be wrong.

## 1. Hold first

```
social_hold_queue(reason="<what happened, in one line, with the date>")
```

Do this **before** analysing, drafting, or asking. While the hold is on, the export pack
refuses to build, so nothing queued can reach a publishing surface by accident.

Then tell the operator immediately: what you held, how many posts, and why. If it turns out to
be nothing, releasing costs one message. The asymmetry is the whole point — a hold costs a
delay, not holding costs a screenshot.

**Hold for:** anything involving death or serious harm, a company crisis or outage, a story
breaking about the brand, a mass-casualty or disaster event in a market you post to, a
significant public moment where routine marketing reads as oblivious.

**Don't hold for:** ordinary bad news, a critical comment, a competitor's problem, or slow
engagement. Holding the queue every time someone is annoyed on the internet makes the hold
meaningless when it matters.

## 2. Work out what you're actually in

Ask the operator, and don't guess:

- What happened, and is it still happening?
- Is the brand a cause, a participant, or a bystander?
- Who is already talking about it, and where?
- Is anyone hurt? Is there a legal or safety dimension?

Then read what's queued (`social_calendar`, `social_queue_list`). Name specifically which posts
would have been the problem — "the Thursday LinkedIn post opens with a joke about downtime" is
useful; "some posts may be insensitive" is not.

## 3. If the brand caused it

Draft for a human to send, quickly. A holding statement within the first hour beats a perfect
statement the next day.

A holding statement says: **we know, we're looking into it, here's when you'll hear more.** It
does not speculate about cause, assign blame, minimise, or promise an outcome nobody has
confirmed.

When you draft the fuller response:

- **Say the thing plainly.** No "we're sorry you feel that way", no "mistakes were made", no
  passive voice hiding who did what.
- **Name what you're doing about it**, only if it's actually been decided.
- **Same message everywhere.** Inconsistency across platforms becomes its own story.
- **Don't over-explain.** Every extra paragraph is more surface area.

Hand it to the operator flagged as needing their judgment before sending. A crisis statement is
never something you post on their behalf, and it should usually see a human with legal or
comms training too. Say that.

## 4. If the brand is a bystander

The usual right answer is: stay held, say nothing, and resume quietly in a day or two.

Brands posting about events they have no connection to reliably reads as opportunism. Unless
the brand has a genuine, material connection to what happened — it serves the affected
community, it has expertise that helps, its people are involved — the respectful move is
silence, not a statement. Say so when the operator asks whether to post something; talking them
out of a well-meant but hollow post is real work.

## 5. Resuming

Releasing is the operator's call, not yours:

```
social_release_queue(note="<what changed, and who decided>")
```

Before you propose resuming, re-read everything queued. Tone that was fine last week can read
very differently now, and posts written before the event may reference it accidentally. Flag
anything that needs rewriting, and suggest starting with the least promotional item in the
queue rather than the campaign launch.

Afterwards, write down what happened and what you did — the trigger, the timing, what was held,
what went out. Most teams learn crisis handling once and then forget it; a short record turns
one bad week into a protocol.
