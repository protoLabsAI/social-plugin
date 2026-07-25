"""social — Social Studio: brand-voice social content, planned and drafted, never auto-posted.

``register(registry)`` is the only place plugin code runs (ADR 0018). Every host-only
import stays inside a function so the test suite imports these modules with no
protoAgent present, and each contribution group is wrapped so one failure doesn't
take the rest of the plugin down with it.
"""

from __future__ import annotations

import logging

log = logging.getLogger("protoagent.plugins.social")

__version__ = "0.2.1"


def register(registry) -> None:
    cfg = registry.config or {}

    # Point the host-free modules at the operator's configured locations before
    # anything reads them. Blank config keeps the instance-scoped defaults.
    try:
        from . import brandkit, paths, platforms

        paths.configure(str(cfg.get("data_dir", "") or ""))
        brandkit.configure(str(cfg.get("brand_kit_path", "") or ""))
        active = cfg.get("active_platforms") or []
        if isinstance(active, str):  # a comma-separated string from the settings UI
            active = [p.strip() for p in active.split(",") if p.strip()]
        platforms.configure_active(list(active))
    except Exception:
        log.exception("[social] configuring paths failed")

    # Tools — the planning/drafting/lint/export surface.
    try:
        from .tools import build_tools

        registry.register_tools(build_tools(registry))
    except Exception:
        log.exception("[social] registering tools failed")

    # The crew: a writer and an editor, one platform at a time.
    try:
        from .subagents import register_subagents

        register_subagents(registry)
    except Exception:
        log.exception("[social] registering subagents failed")

    # Console view (public page) + its data API (bearer-gated).
    try:
        from .api import build_data_router, build_view_router

        registry.register_router(build_view_router(), prefix="/plugins/social")
        registry.register_router(build_data_router(), prefix="/api/plugins/social")
    except Exception:
        log.exception("[social] mounting routers failed")

    log.info("[social] registered: tools, crew, board")
