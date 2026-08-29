import random
from pathlib import Path

from fastapi import APIRouter
from fastapi.responses import FileResponse
from ..config.pvf_config_settings import pvf_settings as settings

router = APIRouter()

# Resolve paths relative to this file so the server works regardless of CWD
_STATIC_CLIENT_DIR = str(Path(__file__).resolve().parents[3] / "static_client")  # api -> pvf -> src -> workspace root

@router.get("/alive", tags=['dev'], summary="Unauthenticated endpoint to test uvicorn/FastAPI server resposne")
def hello():
    if random.random() > 0.6:
        return f"Goodbye world, I've had enough! ENV: {settings.is_local()}"
    else:
        return f"Hello world, It's a beautiful day today! ENV: {settings.is_local()}"


@router.get("/", response_class=FileResponse, tags=["client"], 
             summary="Return a home page index.html single page application from static/index.html")
def serve_root_index():
    # HTML entry point must never be cached — otherwise a stale index.html keeps
    # a previous appVersion (e.g. 0.7.88) and the version mismatch banner survives
    # reloads/refreshes even after static_client was rebuilt. _nuxt assets are
    # hash-fingerprinted and may be long-cached via the StaticFiles mount.
    return FileResponse(
        path=_STATIC_CLIENT_DIR + "/index.html",
        media_type="text/html",
        headers={
            "Cache-Control": "no-store, no-cache, must-revalidate, max-age=0",
            "Pragma": "no-cache",
            "Expires": "0",
        },
    )

