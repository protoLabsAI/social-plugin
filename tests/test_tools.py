"""The tool surface, driven the way the agent drives it."""

from __future__ import annotations

import pytest
import social


@pytest.fixture
def tools(registry):
    social.register(registry)
    return registry


def call(reg, name, **kwargs):
    return reg.tool(name).invoke(kwargs)


# ── brand kit ─────────────────────────────────────────────────────────────────
def test_brand_kit_tool_points_at_the_setup_skill_when_there_is_none(tools):
    out = call(tools, "social_brand_kit")
    assert "No brand kit yet" in out
    assert "brand-kit-setup" in out


def test_save_brand_kit_reports_gaps_without_refusing_the_save(tools):
    out = call(tools, "social_save_brand_kit", yaml_text="brand: Testco\n")
    assert "Saved the brand kit" in out
    assert "Gaps worth filling" in out
    assert "audiences" in out


def test_save_brand_kit_refuses_an_invalid_document(tools):
    out = call(tools, "social_save_brand_kit", yaml_text="positioning: nameless\n")
    from social import brandkit

    assert out.startswith("Did not save")
    assert not brandkit.exists()


def test_save_brand_kit_template_will_not_clobber_an_existing_kit(tools, kit):
    out = call(tools, "social_save_brand_kit", yaml_text="template")
    assert "already exists" in out
    from social import brandkit

    assert brandkit.load()["brand"] == "Testco"


def test_save_brand_kit_template_writes_the_starter_when_empty(tools):
    out = call(tools, "social_save_brand_kit", yaml_text="template")
    assert "starter template" in out


def test_brand_kit_tool_surfaces_a_parse_error_instead_of_crashing(tools):
    from social import brandkit

    brandkit.path().write_text("- broken\n", encoding="utf-8")
    assert "Could not read the brand kit" in call(tools, "social_brand_kit")


# ── platforms + lint ──────────────────────────────────────────────────────────
def test_platform_spec_tool_returns_a_table_then_a_brief(tools):
    assert "| Platform |" in call(tools, "social_platform_spec")
    assert "## LinkedIn" in call(tools, "social_platform_spec", platform="LinkedIn")


def test_check_requires_a_platform(tools):
    assert "Which platform" in call(tools, "social_check", text="Hello.")


def test_check_lints_against_the_brand_kit(tools, kit):
    out = call(tools, "social_check", text="Pure synergy.", platform="x")
    assert "BLOCKED" in out
    assert "banned_phrase" in out


def test_check_notes_when_no_brand_kit_limited_the_review(tools):
    out = call(tools, "social_check", text="Deploys take 40 seconds now. Try it?", platform="x")
    assert "no brand kit yet" in out


def test_check_by_post_id_records_the_score_on_the_row(tools):
    from social import store

    row = store.add(platform="x", body="Deploys dropped to 40 seconds. Try it?", status="drafted")
    out = call(tools, "social_check", post_id=row["id"])
    assert "Recorded score" in out
    assert store.get(row["id"])["score"] > 0


def test_check_by_post_id_reports_a_missing_row(tools):
    assert "No queued post with id 42" in call(tools, "social_check", post_id=42)


def test_check_by_post_id_infers_media_from_attached_assets(tools):
    from social import store

    row = store.add(platform="bluesky", body="A chart.", assets=["chart.png"])
    assert "missing_alt_text" in call(tools, "social_check", post_id=row["id"])


# ── the queue ─────────────────────────────────────────────────────────────────
def test_queue_add_normalises_the_platform_name(tools):
    out = call(tools, "social_queue_add", platform="Twitter", body="Hi.")
    assert "— x (idea)" in out
    from social import store

    assert store.list_posts()[0]["platform"] == "x"


def test_queue_add_rejects_an_unknown_status_with_a_readable_message(tools):
    out = call(tools, "social_queue_add", platform="x", status="published")
    assert out.startswith("Not queued")
    assert "unknown status" in out


def test_queue_add_emits_for_the_rail_notification_dot(tools):
    call(tools, "social_queue_add", platform="x", body="Hi.")
    assert ("queue_changed", {"action": "add", "id": 1, "platform": "x"}) in tools.events


def test_queue_list_guides_the_agent_when_empty(tools):
    assert "content-calendar" in call(tools, "social_queue_list")


def test_queue_list_shows_status_platform_slot_and_score(tools):
    from social import store

    store.add(
        platform="linkedin",
        body="A specific story about the rewrite.",
        status="drafted",
        pillar="Teardowns",
        scheduled_for="2026-08-03T09:30",
        score=91,
    )
    out = call(tools, "social_queue_list")
    assert "#1 [drafted] linkedin · 2026-08-03T09:30 · Teardowns · score 91" in out
    assert "A specific story about the rewrite." in out
    assert "Queue: drafted 1" in out


def test_queue_list_reports_the_counts_when_a_filter_matches_nothing(tools):
    from social import store

    store.add(platform="x", status="idea")
    out = call(tools, "social_queue_list", status="approved")
    assert "Nothing matches" in out and "idea 1" in out


def test_queue_update_changes_only_what_is_passed(tools):
    from social import store

    row = store.add(platform="x", body="Original.", pillar="Teardowns")
    out = call(tools, "social_queue_update", post_id=row["id"], status="needs_edit", notes="Thin.")
    assert "is now 'needs_edit'" in out
    stored = store.get(row["id"])
    assert stored["body"] == "Original." and stored["pillar"] == "Teardowns"
    assert stored["notes"] == "Thin."


def test_queue_update_reports_a_missing_row(tools):
    assert "No queued post with id 7" in call(tools, "social_queue_update", post_id=7, status="drafted")


# ── calendar ──────────────────────────────────────────────────────────────────
def test_calendar_is_empty_helpfully(tools):
    assert "Nothing scheduled" in call(tools, "social_calendar", days=7)


def test_calendar_shows_slots_and_compares_the_pillar_mix_to_target(tools, kit):
    from datetime import date, timedelta

    from social import store

    soon = (date.today() + timedelta(days=1)).isoformat()
    store.add(platform="x", body="One.", pillar="Build in public", scheduled_for=f"{soon}T09:30")
    store.add(platform="x", body="Two.", pillar="Build in public", scheduled_for=f"{soon}T15:00")

    out = call(tools, "social_calendar", days=7)
    assert soon in out
    assert "09:30" in out and "15:00" in out
    assert "Build in public: 2 post(s), 100% (target 60%)" in out
    assert "Nothing scheduled for: Teardowns" in out


# ── export ────────────────────────────────────────────────────────────────────
def test_export_says_what_to_do_when_nothing_is_approved(tools):
    assert "Approve some drafts first." in call(tools, "social_export")


def test_export_writes_a_file_and_previews_it(tools, isolated_data_dir):
    from social import store

    for i in range(3):
        store.add(platform="x", status="approved", body=f"Post {i}.")

    out = call(tools, "social_export")
    assert "Exported 3 post(s)" in out
    assert "plus 1 more in the file." in out
    files = list((isolated_data_dir / "exports").glob("*.md"))
    assert len(files) == 1
    assert "Post 0." in files[0].read_text(encoding="utf-8")


def test_export_rejects_an_unknown_format(tools):
    from social import store

    store.add(platform="x", status="approved", body="Hi.")
    assert "Not exported" in call(tools, "social_export", fmt="pdf")


def test_export_emits_so_the_panel_can_light_up(tools):
    from social import store

    store.add(platform="x", status="approved", body="Hi.")
    call(tools, "social_export")
    assert any(topic == "export_ready" for topic, _ in tools.events)


def test_queue_list_can_read_one_post_in_full(tools):
    # Found by dogfooding: told to fix a post in place, the agent had no way to READ
    # it — the list view truncates bodies, so it asked the operator to paste the text.
    from social import store

    body = "A complete post body that runs well past the point where the list view would cut it off. " * 3
    row = store.add(
        platform="linkedin",
        body=body,
        status="drafted",
        pillar="Teardowns",
        hashtags="#devops",
        alt_text="A latency chart.",
        material_connection="gifted",
        notes="needs a disclosure",
    )
    out = call(tools, "social_queue_list", post_id=row["id"])
    assert body.strip() in out, "the complete body must come back untruncated"
    assert "material connection: gifted" in out
    assert "#devops" in out and "A latency chart." in out
    assert "needs a disclosure" in out


def test_reading_a_missing_post_by_id_is_reported(tools):
    assert "No queued post with id 99" in call(tools, "social_queue_list", post_id=99)


def test_the_blocked_hint_names_the_read_call_too(tools):
    from social import store

    row = store.add(platform="x", body="a" * 400)
    out = call(tools, "social_check", post_id=row["id"])
    assert f"social_queue_list(post_id={row['id']})" in out
