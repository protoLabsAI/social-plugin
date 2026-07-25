"""Where this plugin keeps its state — instance-scoped, host-free.

Follows the same convention as the notes and careercoach plugins (ADR 0004): a base
dir under the user's protoAgent data dir, plus a per-instance subdir when
``PROTOAGENT_INSTANCE`` is set, so the dev sandbox never writes into the default
instance's calendar. ``SOCIAL_DIR`` overrides the base outright — that's the hook the
test suite uses to point everything at a temp dir.
"""

from __future__ import annotations

import os
from pathlib import Path

# Set by register() from plugin config; the env var still wins.
_CONFIGURED_DIR: str = ""


def configure(directory: str) -> None:
    """Point the plugin at an operator-configured data dir (blank = default)."""
    global _CONFIGURED_DIR
    _CONFIGURED_DIR = (directory or "").strip()


def data_dir() -> Path:
    """The directory holding the brand kit, the queue database, and exports."""
    base = os.environ.get("SOCIAL_DIR", "").strip() or _CONFIGURED_DIR
    root = Path(base).expanduser() if base else (Path.home() / ".protoagent" / "social")
    if not base:
        # Only the default location gets the per-instance subdir; an explicitly
        # configured directory is taken literally.
        inst = os.environ.get("PROTOAGENT_INSTANCE", "").strip()
        if inst:
            root = root / inst
    root.mkdir(parents=True, exist_ok=True)
    return root
