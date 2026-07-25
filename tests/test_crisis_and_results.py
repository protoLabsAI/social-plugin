"""The queue hold, and the learning loop.

The hold has to actually bite — a "pause" that still lets the publish pack build is
theatre. The performance read-back has to under-claim: refusing to rank six posts is
the feature, not a limitation.
"""

from __future__ import annotations

import sqlite3

import pytest
import social
from social import performance, store


def tool_call(reg, name, **kwargs):
    return reg.tool(name).invoke(kwargs)


@pytest.fixture
def tools(registry):
    social.register(registry)
    return registry


# ── the hold ──────────────────────────────────────────────────────────────────
def test_no_hold_by_default():
    assert store.hold_state() is None


def test_hold_records_a_reason_and_a_time():
    state = store.hold("outage at the datacentre, 2026-07-25")
    assert state["reason"].startswith("outage")
    assert store.hold_state()["since"]


def test_a_hold_needs_a_reason():
    with pytest.raises(ValueError, match="reason"):
        store.hold("   ")
    assert store.hold_state() is None


def test_release_reports_whether_there_was_anything_to_release():
    assert store.release() is False
    store.hold("something happened")
    assert store.release() is True
    assert store.hold_state() is None


def test_export_refuses_while_held(tools):
    store.add(platform="x", status="approved", body="Cheerful product post.")
    assert "Exported 1 post(s)" in tool_call(tools, "social_export")

    store.hold("a public tragedy")
    out = tool_call(tools, "social_export")
    assert "HELD" in out
    assert "Refusing to build a publish pack" in out
    assert "a public tragedy" in out


def test_export_can_be_overridden_but_only_deliberately(tools):
    store.add(platform="x", status="approved", body="A genuinely necessary post.")
    store.hold("a public tragedy")
    out = tool_call(tools, "social_export", override_hold=True)
    assert "Exported 1 post(s)" in out


def test_the_calendar_leads_with_the_hold(tools):
    from datetime import date, timedelta

    soon = (date.today() + timedelta(days=1)).isoformat()
    store.add(platform="x", body="Scheduled.", scheduled_for=f"{soon}T09:00")
    store.hold("an outage")
    out = tool_call(tools, "social_calendar", days=7)
    assert out.startswith("⛔ QUEUE HELD")
    assert "an outage" in out


def test_an_empty_calendar_still_surfaces_the_hold(tools):
    store.hold("an outage")
    assert "QUEUE HELD" in tool_call(tools, "social_calendar", days=7)


def test_hold_tool_reports_what_it_blocked(tools):
    store.add(platform="x", status="approved", body="One.")
    store.add(platform="x", status="scheduled", body="Two.")
    store.add(platform="x", status="idea", body="Three.")
    out = tool_call(tools, "social_hold_queue", reason="a story is breaking")
    assert "2 approved/scheduled post(s) are now blocked" in out
    assert ("queue_held", {"reason": "a story is breaking"}) in tools.events


def test_release_tool_says_so_when_there_is_no_hold(tools):
    assert "no hold on the queue" in tool_call(tools, "social_release_queue")


def test_release_tool_tells_the_agent_to_re_read_before_resuming(tools):
    store.hold("an outage")
    out = tool_call(tools, "social_release_queue", note="operator confirmed resolved")
    assert "Hold lifted" in out
    assert "Re-read them" in out


# ── results ───────────────────────────────────────────────────────────────────
def test_recording_results_marks_the_post_posted():
    row = store.add(platform="x", body="A post.", status="approved")
    updated = store.record_results(row["id"], {"impressions": 1000, "engagements": 50})
    assert updated["status"] == "posted"
    assert updated["results"]["impressions"] == 1000
    assert updated["posted_at"]


def test_results_merge_so_later_numbers_do_not_erase_earlier_ones():
    row = store.add(platform="x", body="A post.")
    store.record_results(row["id"], {"impressions": 1000})
    store.record_results(row["id"], {"engagements": 50, "outcome": "a customer replied"})
    results = store.get(row["id"])["results"]
    assert results == {"impressions": 1000, "engagements": 50, "outcome": "a customer replied"}


def test_recording_against_a_missing_post_is_not_an_error():
    assert store.record_results(999, {"impressions": 1}) is None


def test_with_results_ignores_posts_that_have_none():
    a = store.add(platform="x", body="Measured.")
    store.add(platform="x", body="Never measured.", status="posted")
    store.record_results(a["id"], {"impressions": 10})
    assert [r["id"] for r in store.with_results()] == [a["id"]]


# ── the performance read-back ─────────────────────────────────────────────────
def test_no_results_says_what_to_do_about_it():
    out = performance.report()
    assert "No results recorded" in out
    assert "social_record_results" in out


def seed(n, *, platform="x", pillar="A", impressions=1000, engagements=50, body="A post."):
    for _ in range(n):
        row = store.add(platform=platform, pillar=pillar, body=body)
        store.record_results(row["id"], {"impressions": impressions, "engagements": engagements})


def test_below_the_floor_it_refuses_to_compare():
    seed(4)
    out = performance.report()
    assert "below the" in out and "floor for comparing" in out
    assert "noise" in out
    assert "By platform" not in out, "no groupings may be offered below the floor"


def test_above_the_floor_it_groups_and_states_every_sample_size():
    seed(6, platform="x", pillar="Build in public")
    seed(6, platform="linkedin", pillar="Teardowns")
    out = performance.report()
    assert "By platform" in out and "By pillar" in out and "By length" in out
    assert "over 6 post(s)" in out


def test_groups_too_small_to_compare_are_marked_not_ranked():
    seed(8, platform="x")
    seed(2, platform="linkedin")
    out = performance.report()
    assert "only 2, not comparable" in out


def test_a_single_group_is_never_presented_as_a_ranking():
    seed(9, platform="x")
    out = performance.report()
    assert "nothing ranked" in out


def test_qualitative_outcomes_lead_and_are_called_out_as_the_real_signal():
    row = store.add(platform="x", body="A post.")
    store.record_results(row["id"], {"impressions": 900, "engagements": 40, "outcome": "two demo requests"})
    out = performance.report()
    assert "What actually came of it" in out
    assert "two demo requests" in out
    assert out.index("What actually came of it") < out.index("Highest engagement rate")


def test_posts_without_impressions_are_excluded_and_the_exclusion_is_reported():
    a = store.add(platform="x", body="Measured.")
    b = store.add(platform="x", body="Only a note.")
    store.record_results(a["id"], {"impressions": 100, "engagements": 10})
    store.record_results(b["id"], {"outcome": "someone emailed"})
    out = performance.report()
    assert "1 post(s) have results but no impressions/engagements" in out


def test_the_report_refuses_to_read_as_a_verdict():
    seed(10)
    assert "not a verdict" in performance.report()


def test_record_results_tool_says_when_there_is_still_too_little(tools):
    row = store.add(platform="x", body="A post.")
    out = tool_call(tools, "social_record_results", post_id=row["id"], impressions=500, engagements=20)
    assert "Too few yet" in out
    seed(8)
    row2 = store.add(platform="x", body="Another.")
    out2 = tool_call(tools, "social_record_results", post_id=row2["id"], impressions=500, engagements=20)
    assert "Enough to look for patterns" in out2


# ── migration ─────────────────────────────────────────────────────────────────
def test_an_existing_database_gains_the_new_columns_without_losing_rows(isolated_data_dir):
    # A queue built before this release must survive the upgrade — the operator's
    # weeks of drafts are not an acceptable cost for a schema change.
    path = store.db_path()
    legacy = sqlite3.connect(path)
    legacy.executescript(
        "CREATE TABLE posts (id INTEGER PRIMARY KEY AUTOINCREMENT, created TEXT NOT NULL,"
        " updated TEXT NOT NULL, platform TEXT NOT NULL, status TEXT NOT NULL,"
        " pillar TEXT NOT NULL DEFAULT '', campaign TEXT NOT NULL DEFAULT '',"
        " scheduled_for TEXT NOT NULL DEFAULT '', title TEXT NOT NULL DEFAULT '',"
        " body TEXT NOT NULL DEFAULT '', hashtags TEXT NOT NULL DEFAULT '',"
        " alt_text TEXT NOT NULL DEFAULT '', assets TEXT NOT NULL DEFAULT '[]',"
        " source TEXT NOT NULL DEFAULT '', notes TEXT NOT NULL DEFAULT '',"
        " score INTEGER NOT NULL DEFAULT 0);"
        "INSERT INTO posts (created, updated, platform, status, body)"
        " VALUES ('2026-01-01', '2026-01-01', 'x', 'drafted', 'An old draft.');"
    )
    legacy.commit()
    legacy.close()

    rows = store.list_posts()
    assert len(rows) == 1
    assert rows[0]["body"] == "An old draft."
    assert rows[0]["material_connection"] == ""
    assert rows[0]["results"] == {}

    assert store.update(rows[0]["id"], material_connection="gifted")["material_connection"] == "gifted"
