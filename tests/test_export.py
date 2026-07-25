"""The export pack — the deliverable in a draft-only workflow."""

from __future__ import annotations

import csv
import io

import pytest
from social import export, store


@pytest.fixture
def posts():
    store.add(
        platform="x",
        status="approved",
        body="Deploys went from 9 minutes to 40 seconds.",
        scheduled_for="2026-08-03T09:30",
        pillar="Build in public",
        hashtags="#devops",
    )
    store.add(
        platform="instagram",
        status="approved",
        body="Behind the rewrite.",
        scheduled_for="2026-08-04T17:00",
        alt_text="A latency chart dropping sharply.",
        assets=["chart.png"],
    )
    return store.list_posts(status="approved")


def test_markdown_groups_by_day_and_fences_each_body(posts):
    md = export.to_markdown(posts)
    assert "## 2026-08-03" in md and "## 2026-08-04" in md
    assert md.count("```text") == 2, "each body needs its own copy block"
    assert "Deploys went from 9 minutes to 40 seconds." in md
    assert "**Alt text:** A latency chart dropping sharply." in md
    assert "**Assets:** chart.png" in md
    assert "**Hashtags:** #devops" in md


def test_markdown_shows_the_character_budget_against_the_platform_cap(posts):
    md = export.to_markdown(posts)
    assert "/280 characters" in md


def test_markdown_labels_unscheduled_posts_rather_than_dropping_them():
    store.add(platform="x", status="approved", body="Whenever.")
    md = export.to_markdown(store.list_posts(status="approved"))
    assert "## Unscheduled" in md
    assert "Whenever." in md


def test_empty_export_says_so():
    assert "Nothing to export." in export.to_markdown([])


def test_csv_has_stable_columns_and_flattens_assets(posts):
    rows = list(csv.DictReader(io.StringIO(export.to_csv(posts))))
    assert list(rows[0]) == export.CSV_COLUMNS
    assert len(rows) == 2
    ig = next(r for r in rows if r["platform"] == "instagram")
    assert ig["assets"] == "chart.png"
    assert ig["alt_text"] == "A latency chart dropping sharply."


def test_render_rejects_an_unknown_format(posts):
    with pytest.raises(ValueError, match="unknown format"):
        export.render(posts, "pdf")


def test_write_saves_under_the_exports_dir_with_the_right_extension(posts, isolated_data_dir):
    md_path = export.write(posts, "markdown")
    csv_path = export.write(posts, "csv")
    assert md_path.parent == isolated_data_dir / "exports"
    assert md_path.suffix == ".md" and csv_path.suffix == ".csv"
    assert "```text" in md_path.read_text(encoding="utf-8")
    assert csv_path.read_text(encoding="utf-8").startswith("scheduled_for,")
