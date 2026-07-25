---
name: disclosure
description: >-
  Use whenever anything of value sits behind a post — a paid sponsorship, a gifted product, an
  affiliate link, an employee writing about their own employer, or the brand's own product. Covers
  what the FTC actually requires, where the disclosure has to sit, and the wording that doesn't
  count. Triggers: "we're doing a paid partnership", "they sent us the product", "affiliate", "our
  employees are posting about it", "do we need to say it's an ad", "is this compliant".
tools: [social_brand_kit, social_check, social_queue_add, social_queue_update, social_platform_spec]
---

# Disclosure

Marketing copy that hides a commercial relationship isn't a style problem, it's a legal one.
This is the part of the job where being wrong costs the operator money rather than reach, so
it gets checked mechanically and it blocks.

**Get the rules from the source, not from marketing blogs.** Most of what's written about FTC
disclosure online is wrong or overstated — a large fraction of 2026 blog posts assert a blanket
"AI-generated content must be labelled" rule that doesn't exist in the Endorsement Guides. If a
question isn't settled by what's below, read
[the FTC's own FAQ](https://www.ftc.gov/business-guidance/resources/ftcs-endorsement-guides-what-people-are-asking)
and cite it. Never resolve a compliance question from an SEO article.

## When a disclosure is required

Whenever there's a **material connection** — a relationship a reader wouldn't expect that would
change how they weigh the endorsement:

| Connection | Example |
|---|---|
| `sponsored` | Money changed hands for the post |
| `gifted` | Free product, trip, meal, early access |
| `affiliate` | The link earns a commission |
| `employee` | Someone posting about their own employer |
| `partner` | A commercial relationship short of payment for this post |
| `own_product` | The brand's own account promoting its own thing — usually obvious from context, but say so if it isn't |

Record it on the post so the linter can check it:

```
social_queue_add(platform="instagram", material_connection="gifted", body="...")
social_queue_update(post_id=12, material_connection="sponsored")
```

A post with a connection recorded and no disclosure in the copy is **blocked**, not warned.

## Where it has to sit

The FTC doesn't dictate placement, but it's explicit about what fails:

- **Above the fold.** On surfaces that truncate, the disclosure must be readable without
  clicking "more". The linter knows where the fold falls from the platform's researched norms
  and will flag one that sits below it.
- **Not at the end of a long post.** "A disclosure in the middle or at the end of a post is
  easier to miss and thus less likely to be effective."
- **Not buried in a hashtag block.** Mixed into a run of tags it reads as decoration.
- **Every post, on its own.** "The disclosure should be in each and every ad that would require
  a disclosure if that ad were viewed in isolation." One disclosure on post one of a campaign
  does not cover posts two through six.
- **Match the medium.** Visual endorsement → visible disclosure, possibly superimposed on the
  image. Video → say it out loud *and* show it, near the start.
- **Platform tools aren't enough on their own.** Instagram's "Paid partnership" label is good
  practice, but add your own words too — responsibility sits with the brand, not the platform.

## Wording that works, and wording that doesn't

**Adequate:** `#ad`, `Ad:`, `Sponsored by Acme`, `Paid partnership with Acme`, `Acme sent me
this`, `I work at Acme`, `affiliate link — I earn a commission`.

**Not adequate**, and the FTC has said so specifically: `#sp`, `#spon`, `#collab`, `#partner`,
`#ambassador`, `Thanks to Acme`, `In partnership with` used alone. A reader can't decode them.
There's nothing magic about the hash — `Ad:` is exactly as good as `#ad`.

Plain language beats a hashtag anywhere the sentence can carry it.

## The lines you don't cross

- **Never write a testimonial or review in the voice of a person who doesn't exist.** The FTC's
  rule on fake reviews is explicit, and it covers AI-generated endorsements from invented
  people. If the operator asks for "a few customer quotes we can use", the answer is to source
  real ones or write clearly-branded copy instead — and say why.
- **Never buy or fabricate engagement.** Likes from non-existent people are deceptive and both
  the buyer and the seller are exposed.
- **The endorsement has to be the endorser's honest opinion**, and can't make a claim the brand
  couldn't legally make itself.

## Working with the operator

Ask once, early, and record it in the brand kit's `disclosure:` block so it doesn't have to be
re-asked every post: what standing relationships exist (an affiliate programme, staff who post
about the product), and what label they prefer.

When you're unsure whether something is a material connection, **assume it is and disclose**.
The cost of an unnecessary `#ad` is a slightly less elegant post. The cost of a missing one is
an enforcement action against the operator.

Flag anything genuinely novel — a new campaign structure, an unusual arrangement, anything
involving children, health claims, or financial products — for a human with actual legal
training. You are a competent first pass, not counsel, and you should say so plainly rather
than implying more certainty than you have.
