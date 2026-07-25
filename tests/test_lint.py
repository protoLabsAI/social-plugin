"""The linter — the gate between a draft and the operator's attention."""

from __future__ import annotations

import pytest
from social import brandkit, lint


def codes(result):
    return {f["code"] for f in result["findings"]}


def levels(result, code):
    return [f["level"] for f in result["findings"] if f["code"] == code]


def test_unknown_platform_is_blocked_not_silently_accepted():
    result = lint.check("hello", "myspace")
    assert result["verdict"] == "blocked"
    assert codes(result) == {"unknown_platform"}


def test_over_the_hard_limit_is_an_error():
    result = lint.check("a" * 300, "x")
    assert result["verdict"] == "blocked"
    assert "too_long" in codes(result)
    assert levels(result, "too_long") == ["error"]


def test_a_thread_capable_platform_suggests_splitting():
    fix = next(f["fix"] for f in lint.check("a" * 300, "x")["findings"] if f["code"] == "too_long")
    assert "thread" in fix.lower()


def test_empty_draft_is_an_error():
    assert "empty" in codes(lint.check("", "x"))


def test_length_band_is_advisory_not_blocking(seeded_norms):
    result = lint.check("Short.", "linkedin")
    assert "under_sweet_spot" in codes(result)
    assert levels(result, "under_sweet_spot") == ["info"]
    assert result["verdict"] != "blocked"


def test_the_fold_is_reported_with_the_text_above_it(seeded_norms):
    body = "The first line is the whole pitch. " + ("filler words here. " * 30)
    result = lint.check(body, "linkedin")
    fold = next(f for f in result["findings"] if f["code"] == "fold")
    assert "The first line is the whole pitch." in fold["message"]
    assert result["hook"].startswith("The first line is the whole pitch.")


def test_too_many_hashtags_warns_with_the_native_range(seeded_norms):
    result = lint.check("Post " + " ".join(f"#tag{i}" for i in range(8)), "linkedin")
    assert "too_many_hashtags" in codes(result)
    assert levels(result, "too_many_hashtags") == ["warn"]


def test_brand_kit_house_rules_beat_researched_norms(seeded_norms):
    kit = {"platforms": {"linkedin": {"hashtag_norm": [0, 1]}}}
    result = lint.check("Post #one #two #three", "linkedin", kit=kit)
    assert "too_many_hashtags" in codes(result)
    # The same draft is fine under the researched 3-5 norm.
    assert "too_many_hashtags" not in codes(lint.check("Post #one #two #three", "linkedin"))


def test_link_in_body_warns_where_the_platform_demotes_it(seeded_norms):
    result = lint.check("Read this https://example.com/post", "linkedin")
    assert "link_in_body" in codes(result)
    fix = next(f["fix"] for f in result["findings"] if f["code"] == "link_in_body")
    assert "comment" in fix.lower()


def test_bare_domains_count_as_links(seeded_norms):
    # Found by dogfooding: nobody types "https://" into a tweet, but a bare domain
    # is still a link and still gets the post demoted. Scoring these clean was the
    # linter passing exactly the posts it exists to catch.
    result = lint.check("Star it if it's useful: github.com/protoLabsAI/protoAgent", "x")
    assert result["links"] == 1
    assert "link_in_body" in codes(result)
    assert "link_in_body" in codes(lint.check("Visit www.example.com today", "linkedin"))


@pytest.mark.parametrize(
    "text",
    [
        "We shipped v0.114.0 today. It works.",  # a version, not a domain
        "The report.pdf is attached. Done.",  # a filename
        "Deploys dropped to 40s. Nothing else changed.",  # a number then a sentence
        "Ends here.Next sentence starts",  # a missing space after a full stop
    ],
)
def test_link_detection_does_not_fire_on_things_that_merely_contain_a_dot(text):
    assert lint.check(text, "linkedin")["links"] == 0


def test_no_link_warning_where_links_are_fine(seeded_norms):
    assert "link_in_body" not in codes(lint.check("Read this https://example.com", "bluesky"))


def test_instagram_flags_that_captions_have_no_clickable_links():
    assert "link_not_clickable" in codes(lint.check("Link https://example.com in bio", "instagram"))


def test_banned_phrase_blocks_and_avoid_phrase_warns(kit):
    data = brandkit.load()
    blocked = lint.check("We unlock synergy across the stack.", "x", kit=data)
    assert blocked["verdict"] == "blocked"
    assert levels(blocked, "banned_phrase") == ["error"]

    warned = lint.check("A best-in-class deployment story, with numbers.", "x", kit=data)
    assert levels(warned, "avoid_phrase") == ["warn"]
    assert warned["verdict"] != "blocked"


def test_banned_phrase_matching_is_case_insensitive(kit):
    result = lint.check("SYNERGY, obviously.", "x", kit=brandkit.load())
    assert "banned_phrase" in codes(result)


def test_ai_cadence_is_flagged_and_can_be_switched_off():
    text = "In today's fast-paced world, let's dive in."
    assert "ai_tell" in codes(lint.check(text, "x"))
    off = lint.check(text, "x", kit={"voice": {"check_ai_tells": False}})
    assert "ai_tell" not in codes(off)


def test_emoji_policy_is_enforced_per_brand():
    text = "Shipping today 🚀🎉🔥"
    assert "emoji" in codes(lint.check(text, "x", kit={"voice": {"emoji": "none"}}))
    assert "emoji" in codes(lint.check(text, "x", kit={"voice": {"emoji": "sparing"}}))
    assert "emoji" not in codes(lint.check(text, "x", kit={"voice": {"emoji": "liberal"}}))
    assert "emoji" not in codes(lint.check("Shipping today 🚀", "x", kit={"voice": {"emoji": "sparing"}}))


def test_missing_alt_text_is_an_error_where_the_culture_expects_it(seeded_norms):
    on_bluesky = lint.check("A chart of our uptime.", "bluesky", has_media=True)
    assert levels(on_bluesky, "missing_alt_text") == ["error"]

    on_x = lint.check("A chart of our uptime.", "x", has_media=True)
    assert levels(on_x, "missing_alt_text") == ["warn"]

    supplied = lint.check("A chart.", "bluesky", has_media=True, alt_text="Uptime chart, 99.99%.")
    assert "missing_alt_text" not in codes(supplied)


def test_alt_text_over_the_platform_cap_is_an_error():
    result = lint.check("Caption.", "instagram", has_media=True, alt_text="x" * 150)
    assert levels(result, "alt_too_long") == ["error"]


def test_youtube_title_cap_is_enforced_separately_from_the_body():
    result = lint.check("A fine description.", "youtube", title="t" * 120)
    assert levels(result, "title_too_long") == ["error"]


def test_cta_detection_accepts_a_kit_cta_a_question_or_an_imperative(kit):
    data = brandkit.load()
    assert "no_cta" not in codes(lint.check("It ships today. Try it free", "x", kit=data))
    assert "no_cta" not in codes(lint.check("It ships today. What would you build?", "x", kit=data))
    assert "no_cta" not in codes(lint.check("It ships today.\nRead the changelog", "x", kit=data))
    assert "no_cta" in codes(lint.check("It ships today.", "x", kit=data))


def test_score_and_verdict_track_severity():
    clean = lint.check("Deploys went from 9 minutes to 40 seconds. Try it free", "x")
    assert clean["verdict"] in ("ship", "revise")
    assert clean["score"] >= 85 or clean["verdict"] == "revise"

    broken = lint.check("a" * 400, "x")
    assert broken["score"] <= 75
    assert broken["verdict"] == "blocked"


def test_counts_are_reported_for_the_board():
    result = lint.check("Hi @someone, see https://a.example #one", "bluesky")
    assert result["hashtags"] == 1
    assert result["links"] == 1
    assert result["mentions"] == 1


def test_render_is_readable_and_groups_by_severity(kit):
    result = lint.check("Pure synergy, in today's fast-paced world!! " + "#a " * 6, "linkedin", kit=brandkit.load())
    text = lint.render(result)
    assert "BLOCKED" in text
    assert text.index("✗") < text.index("!"), "errors must be listed before warnings"
    assert "→" in text, "every finding should carry a fix"


def test_render_says_so_when_a_draft_is_clean():
    draft = (
        "Deploys dropped from nine minutes to forty seconds after we rewrote the scheduler. What's your slowest step?"
    )
    assert "Clean" in lint.render(lint.check(draft, "bluesky"))
