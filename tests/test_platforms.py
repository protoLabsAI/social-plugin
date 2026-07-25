"""Platform capabilities — the hard, platform-enforced facts only."""

from __future__ import annotations

import pytest
from social import norms, platforms


def test_every_spec_is_internally_coherent():
    for pid, spec in platforms.SPECS.items():
        assert spec.id == pid, "the dict key must match the spec id — lookups use both"
        assert spec.max_chars > 0
        assert spec.media
        if not spec.links_clickable:
            assert spec.link_note, f"{pid}: links don't work in the body but nothing says where they go"


def test_no_soft_norms_leaked_back_into_the_spec():
    # The whole point of the norms layer: nothing that drifts is compiled in. If a
    # field like this reappears on the dataclass, the plugin is back to asserting
    # last year's folklore as fact.
    banned_fields = {"sweet_spot", "hashtag_norm", "link_penalty", "truncate_at", "fold", "hook_note", "dies_here"}
    present = set(platforms.PlatformSpec.__dataclass_fields__)
    assert not (present & banned_fields), (
        f"soft norms must live in norms.py, not platforms.py: {present & banned_fields}"
    )


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


def test_brief_for_one_platform_states_hard_limits_and_admits_missing_norms():
    text = platforms.brief("x")
    assert "280" in text
    assert "Hard limit" in text and "Media" in text
    assert "No norms on file for x" in text, "with nothing researched it must say so, not invent a band"


def test_brief_folds_in_the_norms_once_they_exist(seeded_norms):
    text = platforms.brief("linkedin")
    assert "3,000 characters" in text  # hard limit, compiled in
    assert "Sweet spot: 900–1800" in text  # norm, researched
    assert "first comment" in text
    assert "example.test/li" in text, "a norm must carry its source wherever it's shown"


def test_field_caps_are_surfaced_in_the_brief():
    assert "Title caps at 100" in platforms.brief("youtube")
    assert "Alt text caps at 100" in platforms.brief("instagram")


def test_comparison_table_marks_active_platforms_and_norm_freshness(seeded_norms):
    platforms.configure_active(["twitter", "linkedin"])
    assert platforms.active() == ["x", "linkedin"]
    table = platforms.brief()
    x_row = next(line for line in table.splitlines() if line.startswith("| X"))
    tiktok_row = next(line for line in table.splitlines() if line.startswith("| TikTok"))
    assert "●" in x_row and "(today)" in x_row
    assert "●" not in tiktok_row and "never checked" in tiktok_row


def test_active_falls_back_to_defaults_and_drops_unknowns():
    platforms.configure_active([])
    assert platforms.active() == platforms.DEFAULT_PLATFORMS
    platforms.configure_active(["nonsense", "bsky"])
    assert platforms.active() == ["bluesky"]


def test_norms_status_names_the_in_scope_platforms_nobody_researched():
    platforms.configure_active(["x", "threads"])
    norms.record("x", {"sources": ["https://example.test/x"], "hashtag_norm": [0, 1]})
    status = norms.status()
    assert "In scope but never researched: threads." in status
