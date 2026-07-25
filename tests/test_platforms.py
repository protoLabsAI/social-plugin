"""Platform specs — the lookups the whole plugin depends on."""

from __future__ import annotations

import pytest
from social import platforms


def test_every_spec_is_internally_coherent():
    for pid, spec in platforms.SPECS.items():
        assert spec.id == pid, "the dict key must match the spec id — lookups use both"
        lo, hi = spec.sweet_spot
        assert 0 < lo < hi <= spec.max_chars, f"{pid}: sweet spot must sit inside the hard limit"
        hmin, hmax = spec.hashtag_norm
        assert 0 <= hmin <= hmax
        assert spec.alt_text in ("expected", "recommended", "n/a")
        if spec.link_penalty or spec.id in ("instagram", "tiktok"):
            assert spec.link_workaround, f"{pid}: penalises links but offers no alternative"
        assert spec.truncate_at < spec.max_chars


@pytest.mark.parametrize(
    ("given", "expected"),
    [
        ("twitter", "x"),
        ("Twitter", "x"),
        ("X", "x"),
        ("IG", "instagram"),
        ("insta", "instagram"),
        ("bsky", "bluesky"),
        ("LinkedIn", "linkedin"),
        ("linked-in", "linkedin"),
        ("YouTube Shorts", "youtube"),
        ("subreddit", "reddit"),
    ],
)
def test_normalize_maps_the_names_people_actually_type(given, expected):
    assert platforms.normalize(given) == expected


def test_unknown_platform_is_reported_not_guessed():
    assert platforms.get("myspace") is None
    assert "Unknown platform" in platforms.brief("myspace")
    assert "myspace" in platforms.brief("myspace")


def test_brief_for_one_platform_carries_the_drafting_facts():
    text = platforms.brief("x")
    assert "280" in text
    assert "Hashtags" in text and "Hook" in text and "Flops here" in text
    assert platforms.NORMS_CHECKED in text, "a reader must be able to see how stale the norms are"


def test_comparison_table_marks_the_active_platforms():
    platforms.configure_active(["twitter", "linkedin"])
    assert platforms.active() == ["x", "linkedin"]
    table = platforms.brief()
    x_row = next(line for line in table.splitlines() if line.startswith("| X"))
    tiktok_row = next(line for line in table.splitlines() if line.startswith("| TikTok"))
    assert "●" in x_row
    assert "●" not in tiktok_row


def test_active_falls_back_to_defaults_and_drops_unknowns():
    platforms.configure_active([])
    assert platforms.active() == platforms.DEFAULT_PLATFORMS
    platforms.configure_active(["nonsense", "bsky"])
    assert platforms.active() == ["bluesky"]
