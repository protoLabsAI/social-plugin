"""Manifest coherence, register() contributions, and the view's four rules.

These are the tests that catch the failures which only show up in a running host:
a view mounted on a path the router doesn't serve, a settings key that doesn't
match a config key, a tool whose docstring got f-stringed into None.
"""

from __future__ import annotations

import re
import tomllib
from pathlib import Path

import pytest
import social
import yaml
from fastapi import FastAPI
from fastapi.testclient import TestClient
from social import api, view

ROOT = Path(__file__).resolve().parent.parent
MANIFEST = yaml.safe_load((ROOT / "protoagent.plugin.yaml").read_text(encoding="utf-8"))


# ── manifest ──────────────────────────────────────────────────────────────────
def test_identity_and_trust_defaults():
    assert MANIFEST["id"] == "social"
    assert MANIFEST["config_section"] == "social", "must be a string — a list trips the reserved-section check"
    assert MANIFEST["enabled"] is False, "install is not consent; the operator enables it"


def test_version_is_in_lockstep_across_the_three_places_it_appears():
    pyproject = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))
    assert MANIFEST["version"] == pyproject["project"]["version"] == social.__version__


def test_every_config_key_has_a_settings_row_and_vice_versa():
    config_keys = set(MANIFEST["config"])
    settings_keys = {s["key"] for s in MANIFEST["settings"]}
    assert config_keys == settings_keys, "a config key with no settings row is invisible to the operator"


def test_declared_capabilities_match_reality():
    # The plugin holds no credentials and makes no outbound calls of its own —
    # if that ever changes, this test should fail and the manifest be updated.
    assert MANIFEST["capabilities"]["network"] == []
    sources = "\n".join(p.read_text(encoding="utf-8") for p in ROOT.glob("*.py"))
    assert "import httpx" not in sources and "import requests" not in sources


def test_active_platforms_default_to_real_platform_ids():
    from social import platforms

    for pid in MANIFEST["config"]["active_platforms"]:
        assert platforms.get(pid) is not None, f"{pid} is not a known platform"


# ── register() ────────────────────────────────────────────────────────────────
def test_register_contributes_tools_and_both_routers(registry):
    social.register(registry)

    names = registry.tool_names()
    assert len(names) == 9
    assert set(names) == {
        "social_brand_kit",
        "social_save_brand_kit",
        "social_platform_spec",
        "social_check",
        "social_queue_add",
        "social_queue_list",
        "social_queue_update",
        "social_calendar",
        "social_export",
    }

    prefixes = [p for p, _ in registry.routers]
    assert prefixes == ["/plugins/social", "/api/plugins/social"]


def test_register_survives_the_host_only_pieces_being_absent(registry):
    # graph.subagents.config can't import with no host — the crew registration must
    # fail alone rather than taking the tools and routers down with it.
    social.register(registry)
    assert registry.subagents == []
    assert registry.tools and registry.routers


def test_register_threads_config_through_to_the_path_helpers(tmp_path, registry):
    from social import brandkit, paths, platforms

    registry.config = {
        "data_dir": str(tmp_path / "custom"),
        "brand_kit_path": str(tmp_path / "custom" / "kit.yaml"),
        "active_platforms": ["threads", "bluesky"],
    }
    social.register(registry)
    # SOCIAL_DIR is set autouse and must still win over configured values.
    paths.configure(str(tmp_path / "custom"))
    assert brandkit.path() == tmp_path / "custom" / "kit.yaml"
    assert platforms.active() == ["threads", "bluesky"]


def test_active_platforms_accepts_a_comma_separated_string(tmp_path, registry):
    from social import platforms

    registry.config = {"active_platforms": "twitter, bluesky"}
    social.register(registry)
    assert platforms.active() == ["x", "bluesky"]


def test_every_tool_ships_a_description(registry):
    social.register(registry)
    for tool in registry.tools:
        assert tool.description, f"{tool.name} has no description — is its docstring an f-string?"
        assert len(tool.description) > 60, f"{tool.name}'s description is too thin to route on"


# ── the view's four rules ─────────────────────────────────────────────────────
@pytest.fixture
def client(registry):
    social.register(registry)
    app = FastAPI()
    for prefix, router in registry.routers:
        app.include_router(router, prefix=prefix)
    return TestClient(app)


def test_the_declared_view_path_is_the_path_actually_served(client):
    declared = MANIFEST["views"][0]["path"]
    assert declared == "/plugins/social/view"
    assert client.get(declared).status_code == 200


def test_the_page_is_public_and_the_data_is_not(client):
    # Rule 2: the page must NOT live under /api (an iframe navigation carries no bearer),
    # and the data must.
    assert client.get("/api/plugins/social/view").status_code == 404
    assert client.get("/plugins/social/queue").status_code == 404
    assert client.get("/api/plugins/social/queue").status_code == 200


def test_queue_route_returns_the_board_shape(client):
    from social import store

    store.add(platform="x", body="Hello.", pillar="Build in public")
    data = client.get("/api/plugins/social/queue").json()
    assert set(data) == {"counts", "posts", "pillars", "brand"}
    assert data["posts"][0]["body"] == "Hello."
    assert data["pillars"]["Build in public"] == 1


def test_brand_kit_route_reports_a_broken_kit_instead_of_500ing(client):
    from social import brandkit

    brandkit.path().write_text("- not a mapping\n", encoding="utf-8")
    body = client.get("/api/plugins/social/brand-kit").json()
    assert body["exists"] is True
    assert "error" in body


def test_page_follows_the_slug_and_design_system_rules():
    page = view.PAGE
    # Rule 3 — derive the base, never hardcode a prefix.
    assert 'location.pathname.split("/plugins/")[0]' in page
    # Rule 4 — the DS kit, CSS off BASE and the JS via dynamic import (it's an ES module).
    assert 'BASE+"/_ds/plugin-kit.css"' in page
    assert 'import(BASE + "/_ds/plugin-kit.js")' in page
    # Rules 2+3 — data through the kit's slug-aware authed fetch, not a bare fetch.
    assert 'kit.apiFetch("/api/plugins/social/queue")' in page
    # The kit owns the handshake and the theme; hand-rolling either breaks live re-theming.
    assert ":root{" not in page
    assert 'addEventListener("message"' not in page


def test_page_themes_from_tokens_rather_than_hardcoded_colours():
    # Hex is allowed only as a var() fallback: var(--pl-color-bg,#111).
    for match in re.finditer(r"#[0-9a-fA-F]{3,6}\b", view.PAGE):
        line = view.PAGE[: match.start()].rsplit("\n", 1)[-1] + view.PAGE[match.start() :].split("\n", 1)[0]
        assert "var(--pl-" in line or "&#" in line, f"hardcoded colour outside a token fallback: {line.strip()}"


def test_page_escapes_queued_copy_before_rendering_it():
    # Post bodies are model- and operator-authored; they reach the DOM as text.
    assert "const esc = (s) =>" in view.PAGE
    assert "esc(text)" in view.PAGE


def test_queue_json_helper_is_serialisable():
    import json

    from social import store, tools

    store.add(platform="x", body="Hi.")
    assert json.loads(tools.queue_snapshot())["counts"]["idea"] == 1
    assert json.loads(api.queue_json())["posts"][0]["body"] == "Hi."


# ── skills ────────────────────────────────────────────────────────────────────
SKILL_FILES = sorted((ROOT / "skills").glob("*/SKILL.md"))


def test_the_expected_skills_ship():
    assert {p.parent.name for p in SKILL_FILES} == {
        "brand-kit-setup",
        "content-calendar",
        "draft-post",
        "repurpose",
        "engagement-prep",
    }


@pytest.mark.parametrize("skill_path", SKILL_FILES, ids=lambda p: p.parent.name)
def test_skill_frontmatter_is_valid_and_names_real_tools(skill_path, registry):
    social.register(registry)
    known = set(registry.tool_names())

    text = skill_path.read_text(encoding="utf-8")
    assert text.startswith("---\n"), "a skill needs YAML frontmatter to be discoverable"
    front = yaml.safe_load(text.split("---", 2)[1])

    assert front["name"] == skill_path.parent.name, "frontmatter name must match the directory"
    assert len(front["description"]) > 80, "the description is what routes the skill — make it specific"
    assert "Triggers" in front["description"] or "triggers" in front["description"]

    for tool_name in front.get("tools", []):
        if tool_name.startswith("social_"):
            assert tool_name in known, f"{skill_path.parent.name} declares unknown tool {tool_name}"
