"""One resolver for Social Studio's operator overrides and plugin-owned state.

Explicit ``SOCIAL_DIR`` / ``data_dir`` values stay literal. The blank/default case
uses protoAgent's SDK so every instance is isolated by the host rather than by this
plugin reimplementing instance suffixes.
"""

from __future__ import annotations

import os
import shutil
from pathlib import Path

_CONFIGURED_DIR: str = ""
_MIGRATION_MARKER = ".legacy-social-dir-migrated"
_LEGACY_FILES = ("social.db", "brand-kit.yaml", "platform-norms.yaml")


def configure(directory: str) -> None:
    """Point the plugin at an operator-configured data dir (blank = SDK store)."""
    global _CONFIGURED_DIR
    _CONFIGURED_DIR = (directory or "").strip()


def _legacy_data_dir() -> Path:
    root = Path.home() / ".protoagent" / "social"
    instance = os.environ.get("PROTOAGENT_INSTANCE", "").strip()
    return root / instance if instance else root


def _copy_missing_tree(source: Path, target: Path) -> None:
    for item in source.rglob("*"):
        if not item.is_file():
            continue
        destination = target / item.relative_to(source)
        if destination.exists():
            continue
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(item, destination)


def _migrate_legacy(target: Path) -> None:
    """Copy known legacy state once; an existing destination always wins."""
    marker = target / _MIGRATION_MARKER
    if marker.exists():
        return
    source = _legacy_data_dir()
    if source.resolve() == target.resolve():
        marker.touch()
        return
    try:
        if source.is_dir():
            for name in _LEGACY_FILES:
                old, new = source / name, target / name
                if old.is_file() and not new.exists():
                    shutil.copy2(old, new)
            exports = source / "exports"
            if exports.is_dir():
                _copy_missing_tree(exports, target / "exports")
        marker.touch()
    except OSError:
        # Keep the destination usable and leave the marker absent so the next call
        # retries after a transient permission/disk failure.
        return


def data_dir() -> Path:
    """Directory holding the brand kit, queue database, norms, and exports."""
    override = os.environ.get("SOCIAL_DIR", "").strip() or _CONFIGURED_DIR
    if override:
        root = Path(override).expanduser()
        root.mkdir(parents=True, exist_ok=True)
        return root

    # Lazy so the repository's host-free test suite imports without protoAgent.
    from graph import sdk

    root = sdk.plugin_store(plugin_id="social")
    _migrate_legacy(root)
    return root
