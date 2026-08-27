from __future__ import annotations

import sys
from types import ModuleType

from social import paths


def _install_sdk(monkeypatch, target):
    calls = []

    class FakeSdk:
        @staticmethod
        def plugin_store(*, plugin_id):
            calls.append(plugin_id)
            target.mkdir(parents=True, exist_ok=True)
            return target

    graph = ModuleType("graph")
    graph.sdk = FakeSdk
    monkeypatch.setitem(sys.modules, "graph", graph)
    return calls


def test_blank_default_uses_plugin_store(monkeypatch, tmp_path):
    monkeypatch.delenv("SOCIAL_DIR", raising=False)
    paths.configure("")
    monkeypatch.setattr(paths, "_legacy_data_dir", lambda: tmp_path / "missing")
    target = tmp_path / "instance" / "social"
    calls = _install_sdk(monkeypatch, target)

    assert paths.data_dir() == target
    assert calls == ["social"]


def test_env_and_config_overrides_remain_literal_and_skip_the_sdk(monkeypatch, tmp_path):
    configured = tmp_path / "configured"
    environment = tmp_path / "environment"
    calls = _install_sdk(monkeypatch, tmp_path / "sdk")

    paths.configure(str(configured))
    monkeypatch.delenv("SOCIAL_DIR", raising=False)
    assert paths.data_dir() == configured

    monkeypatch.setenv("SOCIAL_DIR", str(environment))
    assert paths.data_dir() == environment
    assert calls == []


def test_legacy_state_copies_once_without_overwriting_destination(monkeypatch, tmp_path):
    monkeypatch.delenv("SOCIAL_DIR", raising=False)
    paths.configure("")
    legacy = tmp_path / "legacy"
    legacy.mkdir()
    (legacy / "social.db").write_text("old-db")
    (legacy / "brand-kit.yaml").write_text("old-brand")
    (legacy / "platform-norms.yaml").write_text("old-norms")
    (legacy / "exports").mkdir()
    (legacy / "exports" / "old.md").write_text("old-export")

    target = tmp_path / "instance" / "social"
    target.mkdir(parents=True)
    (target / "brand-kit.yaml").write_text("new-brand")
    monkeypatch.setattr(paths, "_legacy_data_dir", lambda: legacy)
    _install_sdk(monkeypatch, target)

    assert paths.data_dir() == target
    assert (target / "social.db").read_text() == "old-db"
    assert (target / "brand-kit.yaml").read_text() == "new-brand"
    assert (target / "platform-norms.yaml").read_text() == "old-norms"
    assert (target / "exports" / "old.md").read_text() == "old-export"

    (legacy / "social.db").write_text("changed-old-db")
    assert paths.data_dir() == target
    assert (target / "social.db").read_text() == "old-db"
