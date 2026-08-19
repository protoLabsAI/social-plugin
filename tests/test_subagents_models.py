"""The crew's per-member model overrides (flat `*_model` plugin config) — host-free.

`_configs()` imports the host (graph.subagents.config), so these tests stub it
out and verify only the wiring register_subagents owns: reading the flat config
keys, mapping them to crew members, and leaving members alone when no override
names them.
"""

from types import SimpleNamespace

import social.subagents as subagents
from tests.conftest import FakeRegistry


def _fake_configs():
    return [
        SimpleNamespace(name="social_writer", model=""),
        SimpleNamespace(name="social_editor", model=""),
        SimpleNamespace(name="deslop_editor", model=""),
    ]


def test_deslop_model_pins_only_the_deslop_editor(monkeypatch):
    monkeypatch.setattr(subagents, "_configs", _fake_configs)
    reg = FakeRegistry(config={"deslop_model": "gw/creative"})
    subagents.register_subagents(reg)
    by_name = {c.name: c for c in reg.subagents}
    assert by_name["deslop_editor"].model == "gw/creative"
    assert by_name["social_writer"].model == ""  # untouched


def test_each_crew_member_reads_its_own_key(monkeypatch):
    monkeypatch.setattr(subagents, "_configs", _fake_configs)
    reg = FakeRegistry(config={"writer_model": "gw/fast", "editor_model": "gw/smart"})
    subagents.register_subagents(reg)
    by_name = {c.name: c for c in reg.subagents}
    assert by_name["social_writer"].model == "gw/fast"
    assert by_name["social_editor"].model == "gw/smart"
    assert by_name["deslop_editor"].model == ""


def test_no_overrides_registers_the_crew_untouched(monkeypatch):
    monkeypatch.setattr(subagents, "_configs", _fake_configs)
    reg = FakeRegistry(config={})
    subagents.register_subagents(reg)
    assert [c.model for c in reg.subagents] == ["", "", ""]


def test_every_model_key_is_a_declared_config_key(monkeypatch):
    # The mapping and the manifest must not drift: an override key that isn't in
    # the manifest is invisible to the operator (the settings-row invariant).
    from tests.test_plugin import MANIFEST

    for key in subagents._MODEL_KEYS.values():
        assert key in MANIFEST["config"], key
