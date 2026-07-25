"""The brand kit — load/save, validation, and the drafting brief."""

from __future__ import annotations

import pytest
import yaml
from social import brandkit


def test_missing_kit_says_where_it_looked_and_what_to_do():
    assert brandkit.load() is None
    assert brandkit.exists() is False
    text = brandkit.brief()
    assert "No brand kit yet" in text
    assert str(brandkit.path()) in text
    assert "brand-kit-setup" in text


def test_save_and_load_roundtrip(kit):
    loaded = brandkit.load()
    assert loaded["brand"] == "Testco"
    assert loaded["voice"]["banned"] == ["synergy", "leverage"]
    assert brandkit.exists()


def test_configured_path_wins_over_the_default(tmp_path):
    target = tmp_path / "elsewhere" / "kit.yaml"
    brandkit.configure(str(target))
    brandkit.save({"brand": "Configured"})
    assert target.is_file()
    assert brandkit.load()["brand"] == "Configured"


def test_env_override_beats_configured_path(tmp_path, monkeypatch):
    monkeypatch.setenv("SOCIAL_BRAND_KIT", str(tmp_path / "env.yaml"))
    brandkit.configure(str(tmp_path / "config.yaml"))
    assert brandkit.path() == tmp_path / "env.yaml"


def test_malformed_yaml_raises_rather_than_drafting_in_a_generic_voice():
    brandkit.path().parent.mkdir(parents=True, exist_ok=True)
    brandkit.path().write_text("- just\n- a list\n", encoding="utf-8")
    with pytest.raises(ValueError, match="mapping"):
        brandkit.load()


def test_validate_flags_the_things_that_break_drafting():
    problems = brandkit.validate({"pillars": "not a list", "voice": {"emoji": "loud"}})
    joined = " ".join(problems)
    assert "error: `brand`" in joined
    assert "error: `pillars` must be a list" in joined
    assert "voice.emoji" in joined


def test_validate_warns_when_the_pillar_mix_does_not_total_100():
    problems = brandkit.validate(
        {"brand": "X", "pillars": [{"name": "a", "mix": 30}, {"name": "b", "mix": 30}], "voice": {}}
    )
    assert any("totals 60%" in p for p in problems)


def test_save_yaml_rejects_a_kit_with_a_fatal_problem():
    with pytest.raises(ValueError, match="brand"):
        brandkit.save_yaml("positioning: no name here\n")
    assert not brandkit.exists(), "a rejected kit must not be written"


def test_shipped_template_parses_and_has_no_fatal_errors():
    parsed = yaml.safe_load(brandkit.TEMPLATE)
    assert isinstance(parsed, dict)
    fatal = [p for p in brandkit.validate(parsed) if p.startswith("error:")]
    # The template ships with an empty `brand` for the operator to fill in — that's
    # the only thing allowed to be fatal, and it must be the thing the setup asks for first.
    assert all("`brand`" in f for f in fatal), fatal


def test_pillar_mix_spreads_the_remainder_over_unmixed_pillars():
    mix = brandkit.pillar_mix({"pillars": [{"name": "a", "mix": 50}, {"name": "b"}, {"name": "c"}]})
    assert mix["a"] == 50
    assert mix["b"] == pytest.approx(25)
    assert mix["c"] == pytest.approx(25)


def test_machine_readable_slices(kit):
    data = brandkit.load()
    assert brandkit.banned_phrases(data) == ["synergy", "leverage"]
    assert brandkit.avoid_phrases(data) == ["best-in-class"]
    assert brandkit.emoji_policy(data) == "sparing"
    assert brandkit.ctas(data) == ["Try it free"]
    assert brandkit.pillar_names(data) == ["Build in public", "Teardowns"]


def test_emoji_policy_defaults_to_sparing_when_absent_or_junk():
    assert brandkit.emoji_policy(None) == "sparing"
    assert brandkit.emoji_policy({"voice": {"emoji": "nonsense"}}) == "sparing"


def test_platform_overrides_are_scoped_to_one_platform():
    data = {"platforms": {"linkedin": {"hashtag_norm": [2, 3]}}}
    assert brandkit.platform_overrides(data, "linkedin") == {"hashtag_norm": [2, 3]}
    assert brandkit.platform_overrides(data, "x") == {}


def test_brief_carries_the_rules_a_writer_must_follow(kit):
    text = brandkit.brief()
    assert "# Brand kit — Testco" in text
    assert "NEVER use: synergy, leverage" in text
    assert "4,000 developers" in text, "proof points must reach the writer — they gate every number"
    assert "**Build in public** (60%)" in text


def test_brief_section_narrows_and_reports_unknown_sections(kit):
    voice = brandkit.brief(section="voice")
    assert voice.startswith("## Voice")
    assert "Audiences" not in voice
    assert brandkit.brief(section="audience").startswith("## Audiences"), "aliases should resolve"
    assert "No `nonsense` section" in brandkit.brief(section="nonsense")


def test_brand_name_resolves_from_either_shape():
    # Found at wind-down on the live agent: it wrote `brand:` as a mapping from its
    # own interview, which validated fine and rendered as "[object Object]" in the
    # console header. Accept both rather than rejecting a kit already in use.
    assert brandkit.brand_name({"brand": "Testco"}) == "Testco"
    assert brandkit.brand_name({"brand": {"name": "Testco", "product": "protoAgent"}}) == "Testco"
    assert brandkit.brand_name({"brand": {"product": "protoAgent"}}) == "protoAgent"
    assert brandkit.brand_name({"brand": {}}) == ""
    assert brandkit.brand_name(None) == ""


def test_a_nested_brand_is_loadable_but_flagged():
    problems = brandkit.validate({"brand": {"name": "Testco"}, "voice": {}})
    assert not [p for p in problems if p.startswith("error:")]
    assert any("`brand` is a mapping" in p for p in problems)


def test_an_empty_nested_brand_still_fails_the_required_check():
    # A dict stringifies truthy, so the naive check would have passed this.
    assert any("`brand` (the name) is required" in p for p in brandkit.validate({"brand": {}}))


def test_the_brief_header_uses_the_resolved_name():
    brandkit.save({"brand": {"name": "Testco", "product": "protoAgent"}})
    assert "# Brand kit — Testco" in brandkit.brief()
