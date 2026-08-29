"""FastAPI exception handlers installed by pvf_app_runner on the composed applications."""
import json
from traceback import format_exc

from ddtrace import tracer
from fastapi import HTTPException, Request
from fastapi.exception_handlers import http_exception_handler
from fastapi.exceptions import RequestValidationError
from fastapi.responses import HTMLResponse, JSONResponse

from .log_event import log_event


def _report_to_tracer(exc: Exception) -> None:
    span = tracer.current_span()
    if span:
        span.set_exc_info(type(exc), exc, exc.__traceback__)
    else:
        log_event("Warning: No active DataDog span available for error logging. No errors will be reported to DataDog.")


async def handle_500_internal_error(request: Request, exc: Exception):
    traceback_msg = format_exc()
    log_event(f"Uncaught 500 error: {exc}. \n\nTraceback: {traceback_msg}", severity=9, ex_info=exc, url_path=request.url.path)
    _report_to_tracer(exc)

    # Ensure exc is an HTTPException or subclass; otherwise, wrap it
    if not isinstance(exc, HTTPException):
        http_exception = HTTPException(status_code=500, detail="We encountered an error on our end. Please try again later.")
    else:
        http_exception = exc

    return await http_exception_handler(request, http_exception)


async def handle_422_unprocessable_entity(request: Request, exc: RequestValidationError):
    # Log the error with traceback
    traceback_msg = format_exc()
    try:
        body = json.loads(await request.body())
    except Exception as e:
        body = f"Could not retrieve body: {e}"
    log_event(
        f"Uncaught 422 error: {exc}. \n\nTraceback: {traceback_msg}\n\nRequest body: {body}\n",
        severity=9,
        ex_info=exc,
        url_path=request.url.path
    )
    _report_to_tracer(exc)

    return JSONResponse(status_code=422, content={"detail": "Unprocessable Entity", "error": str(exc)})


def make_spa_fallback_404_handler(static_client_dir: str, reserved_prefixes: list[str]):
    """Root-app 404 handler: JSON for reserved API prefixes, SPA index.html otherwise."""

    async def handle_404_not_found(request, exc):
        url_path = request.url.path
        for pref in reserved_prefixes:
            if url_path.startswith(pref):
                return JSONResponse({"detail": exc.detail}, status_code=exc.status_code)
        with open(static_client_dir + '/index.html', mode='rb') as f:
            index_page = f.read()
        # SPA shell must not be cached: stale index.html is the classic
        # `client 0.7.88 → server 0.7.89` banner-that-survives-reload bug.
        return HTMLResponse(
            content=index_page,
            headers={
                "Cache-Control": "no-store, no-cache, must-revalidate, max-age=0",
                "Pragma": "no-cache",
                "Expires": "0",
            },
        )

    return handle_404_not_found
