"""HTTP surface — two routers, two prefixes.

Rule 1 of plugin views: the page is mounted on the PUBLIC prefix (an iframe
navigation can't carry a bearer token), and everything it reads lives under the
GATED ``/api`` prefix, where the operator bearer applies. Keeping them in separate
routers is what makes that split real rather than aspirational.
"""

from __future__ import annotations

import json


def build_view_router():
    """The public page router — mounted at /plugins/social."""
    from fastapi import APIRouter
    from fastapi.responses import HTMLResponse

    from .view import PAGE

    router = APIRouter()

    @router.get("/view", response_class=HTMLResponse)
    async def _view() -> HTMLResponse:
        return HTMLResponse(PAGE)

    return router


def build_data_router():
    """The gated data router — mounted at /api/plugins/social."""
    from fastapi import APIRouter
    from fastapi.responses import JSONResponse

    from . import brandkit, store

    router = APIRouter()

    @router.get("/queue")
    async def _queue() -> JSONResponse:
        brand = ""
        try:
            brand = (brandkit.load() or {}).get("brand", "")
        except Exception:  # noqa: BLE001 — a broken kit shouldn't blank the board
            brand = ""
        return JSONResponse(
            {
                "counts": store.counts(),
                "posts": store.list_posts(limit=200),
                "pillars": store.pillar_balance(),
                "brand": brand,
                "hold": store.hold_state(),
            }
        )

    @router.get("/brand-kit")
    async def _brand_kit() -> JSONResponse:
        try:
            return JSONResponse({"exists": brandkit.exists(), "kit": brandkit.load() or {}})
        except Exception as e:  # noqa: BLE001 — report the parse error to the panel
            return JSONResponse({"exists": brandkit.exists(), "kit": {}, "error": str(e)})

    return router


def queue_json() -> str:
    """The board snapshot as JSON — handy for tests and headless callers."""
    from . import store

    return json.dumps({"counts": store.counts(), "posts": store.list_posts(limit=200)})
