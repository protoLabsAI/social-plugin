"""The content queue."""

from __future__ import annotations

from datetime import date, timedelta

import pytest
from social import store


def test_add_returns_the_stored_row_with_defaults():
    row = store.add(platform="x", body="Hello.")
    assert row["id"] > 0
    assert row["status"] == "idea"
    assert row["assets"] == []
    assert row["created"] and row["updated"]


def test_unknown_status_is_rejected_on_add_and_update():
    with pytest.raises(ValueError, match="unknown status"):
        store.add(platform="x", status="published")
    row = store.add(platform="x")
    with pytest.raises(ValueError, match="unknown status"):
        store.update(row["id"], status="published")


def test_update_patches_only_what_is_passed():
    row = store.add(platform="x", body="First.", pillar="Build in public")
    updated = store.update(row["id"], status="drafted")
    assert updated["status"] == "drafted"
    assert updated["body"] == "First."
    assert updated["pillar"] == "Build in public"


def test_update_ignores_keys_that_are_not_columns():
    row = store.add(platform="x")
    updated = store.update(row["id"], nonsense="hack", body="real")
    assert updated["body"] == "real"
    assert "nonsense" not in updated


def test_assets_roundtrip_as_a_list():
    row = store.add(platform="instagram", assets=["chart.png"])
    assert store.get(row["id"])["assets"] == ["chart.png"]
    assert store.update(row["id"], assets=["a.png", "b.png"])["assets"] == ["a.png", "b.png"]


def test_get_and_delete_missing_rows_are_not_errors():
    assert store.get(999) is None
    assert store.delete(999) is False
    row = store.add(platform="x")
    assert store.delete(row["id"]) is True
    assert store.get(row["id"]) is None


def test_list_filters_by_status_platform_and_campaign():
    store.add(platform="x", status="drafted", campaign="launch")
    store.add(platform="linkedin", status="approved", campaign="launch")
    store.add(platform="linkedin", status="approved", campaign="evergreen")

    assert len(store.list_posts(status="approved")) == 2
    assert len(store.list_posts(platform="linkedin")) == 2
    assert len(store.list_posts(campaign="launch")) == 2
    assert len(store.list_posts(status="approved", campaign="evergreen")) == 1


def test_open_is_a_shorthand_for_everything_still_needing_work():
    store.add(platform="x", status="idea")
    store.add(platform="x", status="drafted")
    store.add(platform="x", status="needs_edit")
    store.add(platform="x", status="posted")
    assert len(store.list_posts(status="open")) == 3


def test_scheduled_posts_sort_before_unscheduled_ones():
    store.add(platform="x", body="unscheduled")
    store.add(platform="x", body="later", scheduled_for="2026-09-01")
    store.add(platform="x", body="sooner", scheduled_for="2026-08-01")
    bodies = [r["body"] for r in store.list_posts()]
    assert bodies[:2] == ["sooner", "later"]
    assert bodies[-1] == "unscheduled"


def test_counts_cover_every_status_even_the_empty_ones():
    store.add(platform="x", status="drafted")
    counts = store.counts()
    assert set(counts) == set(store.STATUSES)
    assert counts["drafted"] == 1
    assert counts["posted"] == 0


def test_calendar_window_excludes_outside_and_archived_rows():
    today = date.today()
    store.add(platform="x", scheduled_for=(today + timedelta(days=1)).isoformat())
    store.add(platform="x", scheduled_for=(today + timedelta(days=30)).isoformat())
    store.add(platform="x", scheduled_for=(today + timedelta(days=2)).isoformat(), status="archived")
    store.add(platform="x", body="unscheduled")

    rows = store.calendar(days=14)
    assert len(rows) == 1


def test_calendar_accepts_an_explicit_start():
    store.add(platform="x", scheduled_for="2026-08-05")
    assert len(store.calendar(days=7, start="2026-08-01")) == 1
    assert len(store.calendar(days=7, start="2026-09-01")) == 0


def test_pillar_balance_groups_unassigned_rows_visibly():
    store.add(platform="x", pillar="Teardowns")
    store.add(platform="x", pillar="Teardowns")
    store.add(platform="x")
    balance = store.pillar_balance()
    assert balance["Teardowns"] == 2
    assert balance["(unassigned)"] == 1


def test_pillar_balance_can_be_scoped_to_a_status():
    store.add(platform="x", pillar="A", status="approved")
    store.add(platform="x", pillar="A", status="idea")
    assert store.pillar_balance(status="approved") == {"A": 1}


def test_the_database_lands_in_the_isolated_data_dir(isolated_data_dir):
    store.add(platform="x")
    assert store.db_path().parent == isolated_data_dir
    assert store.db_path().is_file()
