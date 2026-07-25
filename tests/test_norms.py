"""Platform norms — researched, dated, sourced, and never invented.

The behaviour under test is mostly a refusal: with nothing on file the linter must
say what it didn't check rather than reach for a plausible number.
"""

from __future__ import annotations

from datetime import timedelta

import pytest
from social import lint, norms


def codes(result):
    return {f["code"] for f in result["findings"]}


# ── recording ─────────────────────────────────────────────────────────────────
def test_nothing_is_on_file_until_someone_researches_it():
    assert norms.load() == {}
    assert norms.get("linkedin") is None
    assert norms.freshness("linkedin") == "never checked"


def test_record_stamps_the_date_and_roundtrips():
    row = norms.record("linkedin", {"sources": ["https://example.test/a"], "hashtag_norm": [3, 5]})
    assert row["checked"] == norms.today().isoformat()
    assert norms.get("linkedin")["hashtag_norm"] == [3, 5]
    assert norms.age_days("linkedin") == 0


def test_record_normalises_the_platform_name():
    norms.record("Twitter", {"sources": ["https://example.test/x"]})
    assert norms.get("x") is not None


def test_record_rejects_an_unknown_platform():
    with pytest.raises(ValueError, match="unknown platform"):
        norms.record("myspace", {"sources": ["https://example.test/a"]})


def test_sources_are_required_because_an_unattributable_norm_is_a_guess():
    for bad in ({}, {"sources": []}, {"sources": [""]}, {"hashtag_norm": [1, 2]}):
        with pytest.raises(ValueError, match="sources"):
            norms.record("x", bad)
    assert norms.get("x") is None, "a rejected norm must not be written"


@pytest.mark.parametrize(
    ("row", "match"),
    [
        ({"sources": ["u"], "hashtag_norm": [5, 2]}, "min, max"),
        ({"sources": ["u"], "sweet_spot": [100]}, "two-item"),
        ({"sources": ["u"], "sweet_spot": ["a", "b"]}, "whole numbers"),
        ({"sources": ["u"], "fold": -5}, "positive"),
        ({"sources": ["u"], "link_penalty": "yes"}, "true or false"),
        ({"sources": ["u"], "alt_text": "vital"}, "alt_text"),
    ],
)
def test_malformed_norms_are_refused_with_a_readable_reason(row, match):
    with pytest.raises(ValueError, match=match):
        norms.record("x", row)


def test_recording_merges_so_rechecking_one_field_keeps_the_rest():
    norms.record("x", {"sources": ["https://example.test/1"], "hashtag_norm": [0, 1], "sweet_spot": [70, 240]})
    norms.record("x", {"sources": ["https://example.test/2"], "hashtag_norm": [0, 2]})
    row = norms.get("x")
    assert row["hashtag_norm"] == [0, 2], "the re-checked field updates"
    assert row["sweet_spot"] == [70, 240], "the untouched field survives"


def test_link_penalty_without_a_workaround_warns_but_still_saves():
    row = norms.record("x", {"sources": ["https://example.test/1"], "link_penalty": True})
    assert any("link_workaround" in w for w in norms.validate(row))
    assert norms.get("x")["link_penalty"] is True


def test_record_yaml_accepts_the_document_the_tool_documents():
    norms.record_yaml("bluesky", "sources: ['https://example.test/b']\nhashtag_norm: [0, 2]\nalt_text: expected\n")
    assert norms.get("bluesky")["alt_text"] == "expected"
    with pytest.raises(ValueError, match="mapping"):
        norms.record_yaml("bluesky", "- not a mapping")


def test_a_broken_norms_file_does_not_silently_become_no_norms():
    norms.path().write_text("- a list\n", encoding="utf-8")
    with pytest.raises(ValueError, match="mapping"):
        norms.load()


# ── staleness ─────────────────────────────────────────────────────────────────
def test_staleness_is_visible_rather_than_assumed():
    fresh = (norms.today() - timedelta(days=10)).isoformat()
    old = (norms.today() - timedelta(days=norms.STALE_AFTER_DAYS + 30)).isoformat()

    norms.record("x", {"sources": ["u"]}, checked=fresh)
    assert norms.is_stale("x") is False
    assert "10d" in norms.freshness("x") and "stale" not in norms.freshness("x")

    norms.record("linkedin", {"sources": ["u"]}, checked=old)
    assert norms.is_stale("linkedin") is True
    assert "stale" in norms.freshness("linkedin")
    assert "Re-check" in norms.brief("linkedin") or "⚠" in norms.brief("linkedin")


def test_undated_norms_report_as_undated_not_fresh():
    norms.save({"x": {"sources": ["u"], "checked": "not-a-date"}})
    assert norms.age_days("x") is None
    assert norms.freshness("x") == "undated"


# ── what the linter does with, and without, norms ─────────────────────────────
def test_with_no_norms_the_linter_says_what_it_did_not_check():
    result = lint.check("A short post about deploys.", "linkedin")
    assert "no_norms" in codes(result)
    assert result["norms_checked"] is False
    # The checks that depend on a researched threshold must not fire at all.
    assert not ({"under_sweet_spot", "over_sweet_spot", "fold", "too_many_hashtags", "link_in_body"} & codes(result))
    assert "No norms on file for linkedin" in lint.render(result)


def test_missing_norms_do_not_cost_the_draft_points():
    # Reporting the gap is honesty about coverage, not a defect in the copy.
    result = lint.check("Deploys dropped from nine minutes to forty seconds. What's your slowest step?", "linkedin")
    assert "no_norms" in codes(result)
    assert result["score"] == 100
    assert result["verdict"] == "ship"
    assert "Clean — nothing to fix." in lint.render(result)


def test_stale_norms_are_flagged_without_costing_points(seeded_norms):
    old = (norms.today() - timedelta(days=norms.STALE_AFTER_DAYS + 1)).isoformat()
    norms.record("x", {"sources": ["u"]}, checked=old)
    result = lint.check("Deploys dropped to 40 seconds after the rewrite. What's your slowest step?", "x")
    assert "stale_norms" in codes(result)
    assert result["score"] == 100


def test_hard_limits_and_brand_rules_hold_with_no_norms_at_all(kit):
    from social import brandkit

    result = lint.check("a" * 400 + " synergy", "x", kit=brandkit.load())
    assert "too_long" in codes(result)  # hard limit
    assert "banned_phrase" in codes(result)  # brand rule
    assert "no_norms" in codes(result)  # and it admits the gap
    assert result["verdict"] == "blocked"


def test_links_that_are_not_clickable_are_a_hard_fact_not_a_norm():
    # Instagram captions don't render links at all — that's platform behaviour, so it
    # holds with nothing researched. Whether links are *demoted* is a norm and doesn't.
    result = lint.check("Details at https://example.com", "instagram")
    assert "link_not_clickable" in codes(result)
    assert "link_in_body" not in codes(result)


def test_alt_text_holds_without_norms_because_accessibility_is_a_value():
    result = lint.check("A chart of our uptime.", "x", has_media=True)
    assert "missing_alt_text" in codes(result)
    assert [f["level"] for f in result["findings"] if f["code"] == "missing_alt_text"] == ["warn"]


def test_researched_norms_can_raise_alt_text_to_a_hard_requirement(seeded_norms):
    result = lint.check("A chart of our uptime.", "bluesky", has_media=True)
    assert [f["level"] for f in result["findings"] if f["code"] == "missing_alt_text"] == ["error"]


def test_norms_marked_not_applicable_switch_the_check_off():
    norms.record("youtube", {"sources": ["u"], "alt_text": "n/a"})
    assert "missing_alt_text" not in codes(lint.check("A description.", "youtube", has_media=True))


def test_house_rules_beat_researched_norms(seeded_norms):
    # The operator decided; the agent merely read. The operator wins.
    kit = {"platforms": {"linkedin": {"link_penalty": False}}}
    assert "link_in_body" in codes(lint.check("See https://example.com", "linkedin"))
    assert "link_in_body" not in codes(lint.check("See https://example.com", "linkedin", kit=kit))


def test_effective_norms_merges_the_two_layers(seeded_norms):
    merged = lint.effective_norms("linkedin", {"platforms": {"linkedin": {"hashtag_norm": [0, 1]}}})
    assert merged["hashtag_norm"] == [0, 1]  # house rule
    assert merged["sweet_spot"] == [900, 1800]  # researched, untouched
