"""Disclosure checks — the part of the linter where being wrong costs money.

Grounded in the FTC Endorsement Guides FAQ: a material connection must be disclosed
clearly and conspicuously; a disclosure at the end of a long post or mixed into a
hashtag block is "easier to miss and thus less likely to be effective"; on surfaces
that truncate it must be readable without clicking "more".
"""

from __future__ import annotations

import pytest
from social import lint, store


def codes(result):
    return {f["code"] for f in result["findings"]}


def levels(result, code):
    return [f["level"] for f in result["findings"] if f["code"] == code]


def test_no_connection_means_no_disclosure_checks():
    result = lint.check("Just a post about our week.", "x")
    assert not ({"missing_disclosure", "disclosure_below_fold"} & codes(result))


@pytest.mark.parametrize("connection", ["sponsored", "gifted", "affiliate", "employee", "partner"])
def test_a_material_connection_without_a_disclosure_is_blocked(connection):
    result = lint.check("This deployment tool is genuinely great.", "x", material_connection=connection)
    assert levels(result, "missing_disclosure") == ["error"]
    assert result["verdict"] == "blocked"
    assert connection.replace("_", " ") in next(
        f["message"] for f in result["findings"] if f["code"] == "missing_disclosure"
    )


def test_none_is_an_explicit_answer_not_a_missing_one():
    result = lint.check("A post.", "x", material_connection="none")
    assert "missing_disclosure" not in codes(result)


@pytest.mark.parametrize(
    "text",
    [
        "#ad This deployment tool is great.",
        "Ad: this deployment tool is great.",
        "Sponsored by Acme — this tool is great.",
        "Paid partnership with Acme. The tool is great.",
        "Acme sent me this and it's great.",
        "I work at Acme, so take this as you will: the tool is great.",
    ],
)
def test_adequate_disclosures_are_accepted_hash_or_not(text):
    # "There is nothing special about hashtags from a disclosure perspective."
    result = lint.check(text, "x", material_connection="sponsored")
    assert "missing_disclosure" not in codes(result)


@pytest.mark.parametrize("vague", ["#sp", "#collab", "#ambassador", "Thanks to Acme"])
def test_wording_the_ftc_calls_inadequate_does_not_count(vague):
    result = lint.check(f"{vague} this tool is great.", "x", material_connection="sponsored")
    assert "missing_disclosure" in codes(result)
    assert "vague_disclosure" in codes(result)


def test_disclosure_below_the_fold_is_an_error(seeded_norms):
    # LinkedIn norms put the fold at 210 characters.
    body = "A long story about our deployment pipeline. " * 8 + " #ad"
    result = lint.check(body, "linkedin", material_connection="sponsored")
    assert levels(result, "disclosure_below_fold") == ["error"]
    assert "above the fold" in next(f["fix"] for f in result["findings"] if f["code"] == "disclosure_below_fold")


def test_disclosure_above_the_fold_passes(seeded_norms):
    body = "#ad " + "A long story about our deployment pipeline. " * 8
    result = lint.check(body, "linkedin", material_connection="sponsored")
    assert "disclosure_below_fold" not in codes(result)


def test_the_fold_check_is_skipped_when_no_norms_say_where_the_fold_is():
    # No researched norms → no fold position → the check can't run, and mustn't guess.
    body = "A long story about our deployment pipeline. " * 8 + " #ad"
    result = lint.check(body, "linkedin", material_connection="sponsored")
    assert "disclosure_below_fold" not in codes(result)
    assert "missing_disclosure" not in codes(result)
    assert "disclosure_buried" in codes(result), "the length-based check still applies without norms"


def test_a_disclosure_at_the_end_of_a_long_post_warns():
    body = "A story about our pipeline. " * 20 + " Sponsored by Acme"
    result = lint.check(body, "linkedin", material_connection="sponsored")
    assert levels(result, "disclosure_buried") == ["warn"]


def test_a_disclosure_lost_in_a_hashtag_block_warns():
    body = "Our new pipeline is live and it is fast.\n\n#ad #devops #platform #engineering"
    result = lint.check(body, "linkedin", material_connection="sponsored")
    assert "disclosure_in_hashtag_block" in codes(result)


def test_a_disclosure_in_the_sentence_is_not_flagged_as_decoration():
    body = "Sponsored by Acme — our new pipeline is live and it is fast.\n\n#devops #platform #eng"
    result = lint.check(body, "linkedin", material_connection="sponsored")
    assert "disclosure_in_hashtag_block" not in codes(result)


def test_the_connection_rides_on_the_queued_post():
    row = store.add(platform="x", body="This tool is great.", material_connection="gifted")
    assert store.get(row["id"])["material_connection"] == "gifted"


def test_an_unknown_connection_is_refused():
    with pytest.raises(ValueError, match="unknown material connection"):
        store.add(platform="x", material_connection="vibes")


# ── accessibility ─────────────────────────────────────────────────────────────
def test_all_lowercase_multiword_hashtags_are_flagged_for_screen_readers():
    result = lint.check("Shipping today #buildinpublicdaily", "x")
    assert "hashtag_case" in codes(result)
    assert "CamelCase" in next(f["fix"] for f in result["findings"] if f["code"] == "hashtag_case")


def test_short_or_camelcase_hashtags_are_left_alone():
    assert "hashtag_case" not in codes(lint.check("Shipping today #devops", "x"))
    assert "hashtag_case" not in codes(lint.check("Shipping today #BuildInPublicDaily", "x"))


@pytest.mark.parametrize("prefix", ["Image of", "photo of", "A photo of", "Screenshot of"])
def test_alt_text_that_restates_that_it_is_an_image_is_flagged(prefix):
    result = lint.check("Our latency chart.", "x", has_media=True, alt_text=f"{prefix} a latency chart dropping.")
    assert "alt_text_prefix" in codes(result)


def test_overlong_alt_text_is_flagged_below_the_platform_cap():
    # X caps alt text at 1000; the readable range is much shorter than that.
    result = lint.check("A chart.", "x", has_media=True, alt_text="A latency chart. " * 12)
    assert "alt_text_long" in codes(result)
    assert "alt_too_long" not in codes(result), "this is guidance, not the platform's hard cap"


def test_accessibility_findings_are_advisory_not_blocking():
    result = lint.check("Shipping #buildinpublicdaily", "x", has_media=True, alt_text="Image of a chart.")
    assert result["verdict"] != "blocked"
    assert levels(result, "hashtag_case") == ["info"]
