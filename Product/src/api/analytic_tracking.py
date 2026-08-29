"""Unauthenticated analytic tracking payload endpoint.

GET /api/_public/analytic-tracking  (mounted on /api, exempt from signed-header DI)
and also alias on noauth for completeness: GET /_public/analytic-tracking

No authentication, no session, no DB. Returns:
- 200 text/html; charset=utf-8 with effective script string when enabled
- 204 No Content when suppressed (empty token/script, whitelist block, etc.)

Cache-Control: no-store, private — client owns sessionStorage caching.
"""

from fastapi import APIRouter
from fastapi.responses import PlainTextResponse, Response

from ..utils.analytic_tracking import get_effective_tracking_script

# Router intended for external app at /api (path relative => /api/_public/...)
external_router = APIRouter()

# Alias router for noauth app at /auth-ws (path relative => /auth-ws/_public/...)
noauth_router = APIRouter()


def _build_response() -> Response:
    payload = get_effective_tracking_script()
    if payload is None or not payload.strip():
        # 204 distinguishes "off" from error; no body
        return Response(status_code=204, headers={"Cache-Control": "no-store, private"})
    return PlainTextResponse(
        content=payload,
        media_type="text/html; charset=utf-8",
        headers={"Cache-Control": "no-store, private"},
    )


@external_router.get(
    "/_public/analytic-tracking",
    summary="Unauthenticated analytic tracking script payload",
    description="Returns the effective <script> string after token substitution and whitelist check, or 204 when disabled. No authentication required; works pre-login and for shared sessions. Restart required for config changes.",
    tags=["public"],
    response_class=PlainTextResponse,
)
def get_analytic_tracking_external():
    return _build_response()


@noauth_router.get(
    "/_public/analytic-tracking",
    summary="Unauthenticated analytic tracking script payload (noauth alias)",
    description="Alias for /api/_public/analytic-tracking on the no-auth app. Same payload/contract.",
    tags=["public"],
    response_class=PlainTextResponse,
)
def get_analytic_tracking_noauth():
    return _build_response()
