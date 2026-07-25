"""The agent-facing tools.

Thin wrappers over the host-free modules — every docstring here is what the model
reads to decide whether to reach for the tool, so they describe the *job*, not the
implementation. (Docstrings must stay plain string literals: an f-string leaves
``__doc__`` as None and the tool ships with no description at all.)
"""

from __future__ import annotations

import json
import logging

from langchain_core.tools import tool

from . import brandkit, export, lint, platforms, store

log = logging.getLogger("protoagent.plugins.social")


def build_tools(registry):
    """Construct the tool list. ``registry`` is used only for best-effort events."""

    def _emit(topic: str, data: dict) -> None:
        try:
            registry.emit(topic, data)
        except Exception:  # noqa: BLE001 — the event bus is chrome, never load-bearing
            pass

    # ── the brand ─────────────────────────────────────────────────────────────
    @tool
    def social_brand_kit(section: str = "") -> str:
        """Read the brand kit — who we talk to, the content pillars, the voice, the banned
        words, the proof points, and the CTAs. Call this BEFORE drafting anything; without it
        every post sounds like generic marketing. Pass a section (voice, audiences, pillars,
        offers, ctas, platforms, cadence) to read just that part."""
        try:
            return brandkit.brief(section=section)
        except Exception as e:  # noqa: BLE001 — a malformed kit should say so, not crash the turn
            return f"Could not read the brand kit at {brandkit.path()}: {e}"

    @tool
    def social_save_brand_kit(yaml_text: str) -> str:
        """Write the brand kit from a YAML document. Use this at the end of a brand-kit
        interview, or to amend the kit when the operator corrects the voice or adds a pillar.
        Read the current kit first and send the WHOLE document back — this replaces the file.
        Pass the literal string 'template' to write the blank fill-in starter instead."""
        try:
            if yaml_text.strip().lower() == "template":
                if brandkit.exists():
                    return (
                        f"A brand kit already exists at {brandkit.path()} — read it first rather than overwriting it."
                    )
                path = brandkit.save_template()
                return f"Wrote the starter template to {path}. Fill it in with the operator, then save it back."
            path = brandkit.save_yaml(yaml_text)
            warnings = [w for w in brandkit.validate(brandkit.load() or {}) if w.startswith("warn:")]
            msg = f"Saved the brand kit to {path}."
            if warnings:
                msg += "\n\nGaps worth filling:\n" + "\n".join(f"- {w[5:].strip()}" for w in warnings)
            return msg
        except Exception as e:  # noqa: BLE001 — validation errors are the useful output here
            return f"Did not save — {e}"

    # ── the platforms ─────────────────────────────────────────────────────────
    @tool
    def social_platform_spec(platform: str = "") -> str:
        """Look up what a platform enforces and what currently works there: the character
        limit, image dimensions, whether captions make links clickable — plus the researched
        norms on file (length band, hashtag count, the '…more' fold, link demotion) and the
        date they were last checked. Call this before drafting for a surface you haven't
        written for in this session. No argument returns a table of every platform with how
        fresh its norms are. If a platform has no norms, research them and record them with
        social_record_norms rather than guessing."""
        return platforms.brief(platform)

    @tool
    def social_record_norms(platform: str, norms_yaml: str) -> str:
        """Record what you researched about how a platform currently behaves — the length band
        that performs, hashtag counts that read as native, where the '…more' fold falls,
        whether links in the body are demoted and what to do instead, whether alt text is
        expected, and what flops there. Nothing soft is built into this plugin, because
        platform ranking drifts and a compiled-in number would state last year's folklore as
        fact. Search first, then record what you found with the URLs you found it in.

        `sources` is REQUIRED — a norm nobody can check is a guess. Send a small YAML document:

            sources: ["https://...", "https://..."]
            sweet_spot: [900, 1800]
            hashtag_norm: [3, 5]
            fold: 210
            link_penalty: true
            link_workaround: drop the link in the first comment and say so in the post
            alt_text: recommended        # expected | recommended | n/a
            hook: the first two lines are all that show before 'see more'
            native_shape: short paragraphs with white space; a story or a number, then the lesson
            flops: corporate announcement voice, buzzword stacks
            notes: anything else a writer needs

        Every key except `sources` is optional, and this merges into what's already on file,
        so a run that only re-checked hashtags won't wipe the rest."""
        from . import norms

        try:
            row = norms.record_yaml(platform, norms_yaml)
        except Exception as e:  # noqa: BLE001 — validation errors are the useful output here
            return f"Not recorded — {e}"
        _emit("norms_recorded", {"platform": platforms.normalize(platform), "checked": row.get("checked")})
        warnings = [w for w in norms.validate(row) if w.startswith("warn:")]
        out = f"Recorded norms for {platforms.normalize(platform)} (checked {row.get('checked')}).\n\n"
        out += norms.brief(platform)
        if warnings:
            out += "\n\nWorth filling in:\n" + "\n".join(f"- {w[5:].strip()}" for w in warnings)
        return out

    @tool
    def social_check(
        text: str = "",
        platform: str = "",
        post_id: int = 0,
        has_media: bool = False,
        alt_text: str = "",
        title: str = "",
        material_connection: str = "",
    ) -> str:
        """Lint a draft against the platform's limits, the brand's voice, and disclosure law
        before it ships. Catches over-length posts, hashtag counts that read as spam, links
        that get demoted, banned phrases, missing or badly-placed sponsorship disclosures,
        accessibility problems, and cadence that reads as machine-written. Returns a score out
        of 100 and a verdict (ship / revise / blocked) with specific fixes.

        Pass material_connection when anything of value sits behind the post — 'sponsored',
        'gifted', 'affiliate', 'employee', 'partner', or 'own_product' — and the disclosure
        rules are checked too. Pass a post_id instead of text to check a queued post (its
        recorded connection is used) and record its score."""
        if post_id:
            row = store.get(int(post_id))
            if not row:
                return f"No queued post with id {post_id}."
            text = text or row.get("body", "")
            platform = platform or row.get("platform", "")
            alt_text = alt_text or row.get("alt_text", "")
            title = title or row.get("title", "")
            has_media = has_media or bool(row.get("assets"))
            material_connection = material_connection or row.get("material_connection", "")
        if not platform:
            return "Which platform? Pass one of: " + ", ".join(platforms.known())
        try:
            kit = brandkit.load()
        except Exception:  # noqa: BLE001 — lint on platform rules alone rather than refusing
            kit = None
            log.warning("[social] brand kit unreadable; linting on platform rules only")
        result = lint.check(
            text,
            platform,
            kit=kit,
            has_media=has_media,
            alt_text=alt_text,
            title=title,
            material_connection=material_connection,
        )
        out = lint.render(result)
        if post_id:
            store.update(int(post_id), score=result["score"])
            out += f"\n\n(Recorded score {result['score']} on post {post_id}.)"
        if kit is None and brandkit.exists() is False:
            out += "\n\nNote: no brand kit yet, so voice rules weren't checked."
        return out

    # ── the queue ─────────────────────────────────────────────────────────────
    @tool
    def social_queue_add(
        platform: str,
        body: str = "",
        status: str = "idea",
        pillar: str = "",
        campaign: str = "",
        scheduled_for: str = "",
        title: str = "",
        hashtags: str = "",
        alt_text: str = "",
        source: str = "",
        notes: str = "",
        material_connection: str = "",
    ) -> str:
        """Put a post in the queue. Use status 'idea' when planning a calendar and 'drafted'
        once the copy exists. scheduled_for is an ISO date or datetime (2026-08-03 or
        2026-08-03T09:30). pillar ties it to a content pillar so the calendar stays balanced;
        source records where a repurposed piece came from. Set material_connection whenever
        anything of value sits behind the post ('sponsored', 'gifted', 'affiliate', 'employee',
        'partner', 'own_product') so the disclosure rules get checked. Returns the new post's id."""
        try:
            row = store.add(
                platform=platforms.normalize(platform),
                body=body,
                status=status,
                pillar=pillar,
                campaign=campaign,
                scheduled_for=scheduled_for,
                title=title,
                hashtags=hashtags,
                alt_text=alt_text,
                source=source,
                notes=notes,
                material_connection=material_connection,
            )
        except ValueError as e:
            return f"Not queued — {e}"
        _emit("queue_changed", {"action": "add", "id": row["id"], "platform": row["platform"]})
        slot = f" for {row['scheduled_for']}" if row["scheduled_for"] else ""
        return f"Queued #{row['id']} — {row['platform']} ({row['status']}){slot}."

    @tool
    def social_queue_list(status: str = "", platform: str = "", campaign: str = "", limit: int = 25) -> str:
        """List what's in the content queue. Filter by status (idea, drafted, needs_edit,
        approved, scheduled, posted, archived — or 'open' for everything still needing work),
        by platform, or by campaign. Use it to see what's ready, what's stuck, and what to
        work on next."""
        rows = store.list_posts(status=status, platform=platform, campaign=campaign, limit=limit)
        if not rows:
            counts = store.counts()
            total = sum(counts.values())
            if not total:
                return "The queue is empty. Plan a calendar with the `content-calendar` skill, or add posts with social_queue_add."
            return "Nothing matches. Queue holds: " + ", ".join(f"{k} {v}" for k, v in counts.items() if v)
        lines = []
        for r in rows:
            head = f"#{r['id']} [{r['status']}] {r['platform']}"
            if r["scheduled_for"]:
                head += f" · {r['scheduled_for']}"
            if r["pillar"]:
                head += f" · {r['pillar']}"
            if r["score"]:
                head += f" · score {r['score']}"
            preview = " ".join((r["body"] or r["title"] or "(empty)").split())[:110]
            lines.append(f"{head}\n    {preview}")
        counts = store.counts()
        summary = ", ".join(f"{k} {v}" for k, v in counts.items() if v)
        return "\n".join(lines) + f"\n\nQueue: {summary}"

    @tool
    def social_queue_update(
        post_id: int,
        status: str = "",
        body: str = "",
        scheduled_for: str = "",
        pillar: str = "",
        campaign: str = "",
        title: str = "",
        hashtags: str = "",
        alt_text: str = "",
        notes: str = "",
    ) -> str:
        """Update a queued post: move its status, replace the copy, schedule it, or attach
        notes. Only the fields you pass change. Move a post to 'needs_edit' with notes
        explaining what's wrong rather than silently rewriting someone else's draft; move it
        to 'approved' only once the operator has actually said yes."""
        if not store.get(int(post_id)):
            return f"No queued post with id {post_id}."
        try:
            row = store.update(
                int(post_id),
                status=status or None,
                body=body or None,
                scheduled_for=scheduled_for or None,
                pillar=pillar or None,
                campaign=campaign or None,
                title=title or None,
                hashtags=hashtags or None,
                alt_text=alt_text or None,
                notes=notes or None,
            )
        except ValueError as e:
            return f"Not updated — {e}"
        _emit("queue_changed", {"action": "update", "id": post_id, "status": row["status"]})
        return f"Updated #{post_id} — {row['platform']} is now '{row['status']}'."

    @tool
    def social_calendar(days: int = 14) -> str:
        """Show the scheduled content calendar for the next N days — what goes out when, on
        which platform, under which pillar — plus the days with nothing planned and how the
        pillar mix compares to the brand kit's targets. Use it to spot gaps and imbalance
        before drafting more of what's already over-represented."""
        held = store.hold_state()
        rows = store.calendar(days=days)
        kit = None
        try:
            kit = brandkit.load()
        except Exception:  # noqa: BLE001
            pass

        if not rows:
            prefix = f"⛔ QUEUE HELD since {held['since']} — {held['reason']}\n\n" if held else ""
            return (
                prefix + f"Nothing scheduled in the next {days} days. "
                "Plan with the `content-calendar` skill, or schedule queued drafts with social_queue_update."
            )

        by_day: dict[str, list[dict]] = {}
        for r in rows:
            by_day.setdefault((r["scheduled_for"] or "")[:10], []).append(r)

        lines = []
        if held:
            lines += [
                f"⛔ QUEUE HELD since {held['since']} — {held['reason']}",
                "Nothing below should go out until the operator lifts the hold.",
                "",
            ]
        lines += [f"Calendar — next {days} days ({len(rows)} scheduled)", ""]
        for day in sorted(by_day):
            lines.append(day)
            for r in by_day[day]:
                slot = r["scheduled_for"][11:16] if len(r["scheduled_for"]) > 11 else "  —  "
                preview = " ".join((r["body"] or r["title"] or "(no copy yet)").split())[:70]
                lines.append(f"  {slot}  {r['platform']:<10} [{r['status']}] {preview}")

        balance = store.pillar_balance(days=days)
        if balance:
            total = sum(balance.values()) or 1
            lines += ["", "Pillar mix (scheduled window):"]
            targets = brandkit.pillar_mix(kit) if kit else {}
            for name, n in balance.items():
                actual = 100 * n / total
                target = targets.get(name)
                delta = f" (target {target:g}%)" if target is not None else ""
                lines.append(f"  {name}: {n} post(s), {actual:.0f}%{delta}")
            missing = [p for p in brandkit.pillar_names(kit) if p not in balance] if kit else []
            if missing:
                lines.append("  Nothing scheduled for: " + ", ".join(missing))
        return "\n".join(lines)

    @tool
    def social_export(
        status: str = "approved",
        fmt: str = "markdown",
        campaign: str = "",
        limit: int = 100,
        override_hold: bool = False,
    ) -> str:
        """Export the queue as a ready-to-publish pack — the deliverable the operator works
        through by hand. 'markdown' gives each post in its own copy block with hashtags, alt
        text, and assets attached, in the order they go out; 'csv' gives the column shape a
        scheduling tool imports. Defaults to the approved posts. Saves a file and returns its
        path plus a preview. Refuses while the queue is held, unless the operator has explicitly
        decided otherwise (override_hold)."""
        held = store.hold_state()
        if held and not override_hold:
            return (
                f"The queue is HELD (since {held['since']}): {held['reason']}\n\n"
                "Refusing to build a publish pack — that's the whole point of a hold. If the "
                "operator has decided this specific content is safe to send anyway, call again "
                "with override_hold=true and say in your reply that you did."
            )
        rows = store.list_posts(status=status, campaign=campaign, limit=limit)
        if not rows:
            return f"Nothing with status '{status}' to export. Approve some drafts first."
        heading = f"{status.title()} posts" + (f" — {campaign}" if campaign else "")
        try:
            path = export.write(rows, fmt, heading=heading)
        except ValueError as e:
            return f"Not exported — {e}"
        _emit("export_ready", {"path": str(path), "count": len(rows), "format": fmt})
        preview = export.render(rows[:2], fmt, heading=heading)
        more = f"\n\n… plus {len(rows) - 2} more in the file." if len(rows) > 2 else ""
        return f"Exported {len(rows)} post(s) to {path}\n\n{preview}{more}"

    # ── the crisis stop ───────────────────────────────────────────────────────
    @tool
    def social_hold_queue(reason: str) -> str:
        """Stop the queue. Use this the moment something happens that makes scheduled content
        a liability — a crisis at the company, a public tragedy, an outage, a story breaking
        about the brand or its industry. While a hold is on, the export pack refuses to build,
        so nothing queued can be handed over for publishing by accident.

        The damage in a crisis is rarely the crisis itself; it's the cheerful product post that
        goes out in the middle of it. Hold first and ask afterwards — a hold costs a delay, and
        not holding costs a screenshot that outlives the campaign."""
        try:
            state = store.hold(reason)
        except ValueError as e:
            return f"Not held — {e}"
        _emit("queue_held", {"reason": state["reason"]})
        pending = [r for r in store.list_posts(limit=500) if r["status"] in ("approved", "scheduled")]
        out = f"Queue HELD as of {state['since']}.\nReason: {state['reason']}\n\n"
        out += f"{len(pending)} approved/scheduled post(s) are now blocked from export.\n"
        out += "Tell the operator what's held and why. Nothing resumes until they say so."
        return out

    @tool
    def social_release_queue(note: str = "") -> str:
        """Lift a queue hold and let scheduled content flow again. Only do this when the
        operator has explicitly said to resume — releasing is their call, never yours, in the
        same way approving a post is. Record what changed in `note`.

        Before resuming, re-read what's queued: a post written last week may read very
        differently after whatever caused the hold."""
        state = store.hold_state()
        if not state:
            return "There's no hold on the queue."
        store.release()
        _emit("queue_released", {"note": note})
        pending = [r for r in store.list_posts(limit=500) if r["status"] in ("approved", "scheduled")]
        return (
            f"Hold lifted (it was set {state['since']} — {state['reason']}).\n"
            f"{len(pending)} approved/scheduled post(s) can be exported again. "
            "Re-read them before anything goes out; tone that was fine last week may not be now."
        )

    # ── the learning loop ─────────────────────────────────────────────────────
    @tool
    def social_record_results(
        post_id: int,
        impressions: int = 0,
        engagements: int = 0,
        clicks: int = 0,
        saves: int = 0,
        shares: int = 0,
        comments: int = 0,
        followers_gained: int = 0,
        outcome: str = "",
        notes: str = "",
    ) -> str:
        """Record what a published post actually did, from numbers the operator read off the
        platform. Marks the post 'posted'. This is the only way a draft-only agent ever learns
        whether any of its work landed — without it, every calendar is a guess repeated.

        `outcome` is for what the numbers can't hold: a reply from a customer, a demo booked,
        a hire, a link picked up somewhere. That's usually the more valuable signal. Merges
        with anything already recorded, so week-two numbers don't erase week-one's."""
        row = store.get(int(post_id))
        if not row:
            return f"No queued post with id {post_id}."
        metrics = {
            "impressions": impressions,
            "engagements": engagements,
            "clicks": clicks,
            "saves": saves,
            "shares": shares,
            "comments": comments,
            "followers_gained": followers_gained,
            "outcome": outcome,
            "notes": notes,
        }
        updated = store.record_results(int(post_id), {k: v for k, v in metrics.items() if v})
        if not updated:
            return f"No queued post with id {post_id}."
        _emit("results_recorded", {"id": int(post_id)})
        n = len(store.with_results())
        return (
            f"Recorded results for #{post_id} ({updated['platform']}, marked posted).\n"
            f"{n} post(s) now carry results. "
            + (
                "Enough to look for patterns — run social_performance."
                if n >= 8
                else "Too few yet to read anything into."
            )
        )

    @tool
    def social_performance(days: int = 90, platform: str = "") -> str:
        """Report what actually performed, from the results recorded against posted posts —
        broken down by platform, pillar, and length. Use it before planning a calendar, so the
        next fortnight is informed by the last one rather than repeating it.

        It states its own sample size and refuses to draw conclusions from too little data.
        Social numbers are noisy: a difference across six posts is not a finding, and treating
        it as one is how brands end up chasing an accident."""
        from . import performance

        return performance.report(days=days, platform=platform)

    return [
        social_brand_kit,
        social_save_brand_kit,
        social_platform_spec,
        social_record_norms,
        social_check,
        social_hold_queue,
        social_release_queue,
        social_record_results,
        social_performance,
        social_queue_add,
        social_queue_list,
        social_queue_update,
        social_calendar,
        social_export,
    ]


def queue_snapshot() -> str:
    """JSON snapshot of the board — used by the console view's data route."""
    return json.dumps(
        {
            "counts": store.counts(),
            "posts": store.list_posts(limit=200),
            "pillars": store.pillar_balance(),
            "brand": (brandkit.load() or {}).get("brand", "") if brandkit.exists() else "",
        }
    )
