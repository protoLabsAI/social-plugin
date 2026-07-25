"""Test bootstrap — import the plugin with NO protoAgent host present.

The host loads a plugin under a synthetic package; the suite does the same so the
modules' relative imports (``from . import store``) resolve standalone. Executing
``__init__.py`` is safe precisely because every host-only import lives inside a
function — if that ever regresses, this file is where it surfaces first.

Every test runs against a temp data dir: ``SOCIAL_DIR`` is redirected autouse, so a
bug in a path helper can never write into the developer's real queue.
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
PKG = "social"

if PKG not in sys.modules:
    _spec = importlib.util.spec_from_file_location(PKG, ROOT / "__init__.py", submodule_search_locations=[str(ROOT)])
    assert _spec and _spec.loader
    _mod = importlib.util.module_from_spec(_spec)
    sys.modules[PKG] = _mod
    _spec.loader.exec_module(_mod)


@pytest.fixture(autouse=True)
def isolated_data_dir(tmp_path, monkeypatch):
    """Point every path helper at a temp dir and clear the module-level overrides."""
    from social import brandkit, paths, platforms

    monkeypatch.setenv("SOCIAL_DIR", str(tmp_path))
    monkeypatch.delenv("SOCIAL_BRAND_KIT", raising=False)
    monkeypatch.delenv("PROTOAGENT_INSTANCE", raising=False)
    paths.configure("")
    brandkit.configure("")
    platforms.configure_active([])
    yield tmp_path


@pytest.fixture
def seeded_norms():
    """Researched norms on file for the platforms the tests exercise.

    Nothing in the plugin ships these — the point of the norms layer is that they're
    researched and dated, not compiled in — so any test asserting a norm-dependent
    check has to put them there first, exactly as the agent would.
    """
    from social import norms

    norms.record(
        "x",
        {
            "sources": ["https://example.test/x"],
            "sweet_spot": [70, 240],
            "hashtag_norm": [0, 1],
            "link_penalty": True,
            "link_workaround": "put the link in a reply to your own post",
            "alt_text": "recommended",
        },
    )
    norms.record(
        "linkedin",
        {
            "sources": ["https://example.test/li"],
            "sweet_spot": [900, 1800],
            "hashtag_norm": [3, 5],
            "fold": 210,
            "link_penalty": True,
            "link_workaround": "drop the link in the first comment and say so in the post",
            "alt_text": "recommended",
        },
    )
    norms.record(
        "bluesky",
        {
            "sources": ["https://example.test/bsky"],
            "sweet_spot": [80, 260],
            "hashtag_norm": [0, 2],
            "link_penalty": False,
            "alt_text": "expected",
        },
    )
    norms.record(
        "instagram",
        {
            "sources": ["https://example.test/ig"],
            "sweet_spot": [140, 800],
            "hashtag_norm": [3, 5],
            "fold": 125,
            "alt_text": "recommended",
        },
    )
    return norms.load()


@pytest.fixture
def kit():
    """A small but complete brand kit, saved to the temp dir."""
    from social import brandkit

    data = {
        "brand": "Testco",
        "positioning": "Deployment tooling for teams too small to have a platform team.",
        "audiences": [{"name": "Solo founders", "cares_about": "shipping without a devops hire"}],
        "pillars": [
            {"name": "Build in public", "description": "what shipped and what broke", "mix": 60},
            {"name": "Teardowns", "description": "how other people's infra works", "mix": 40},
        ],
        "voice": {
            "traits": ["direct", "specific"],
            "person": "first-person singular",
            "emoji": "sparing",
            "do": ["name the number"],
            "dont": ["open with a rhetorical question"],
            "banned": ["synergy", "leverage"],
            "avoid": ["best-in-class"],
        },
        "proof": ["4,000 developers deploy with it weekly"],
        "ctas": ["Try it free"],
        "offers": [{"name": "Free tier", "url": "https://testco.dev/start"}],
    }
    brandkit.save(data)
    return data


class FakeRegistry:
    """Stands in for the host's PluginRegistry — records what register() contributes."""

    def __init__(self, config=None):
        self.config = config or {}
        self.tools = []
        self.routers = []
        self.subagents = []
        self.skill_dirs = []
        self.events = []

    def register_tool(self, t):
        self.tools.append(t)

    def register_tools(self, ts):
        self.tools.extend(ts)

    def register_router(self, router, prefix):
        self.routers.append((prefix, router))

    def register_subagent(self, cfg):
        self.subagents.append(cfg)

    def register_skill_dir(self, path):
        self.skill_dirs.append(path)

    def emit(self, topic, data):
        self.events.append((topic, data))

    def tool_names(self):
        return [getattr(t, "name", getattr(t, "__name__", "?")) for t in self.tools]

    def tool(self, name):
        for t in self.tools:
            if getattr(t, "name", None) == name:
                return t
        raise KeyError(f"no tool named {name!r} — have {self.tool_names()}")


@pytest.fixture
def registry():
    return FakeRegistry()
