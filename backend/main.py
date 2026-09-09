"""FastAPI-App: API + statisches Frontend."""
from __future__ import annotations

import secrets
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.responses import FileResponse, JSONResponse, Response
from fastapi.staticfiles import StaticFiles

from . import db, jobs
from .api import router
from .config import FRONTEND_DIR, PANEL_PASSWORD, PANEL_USER


@asynccontextmanager
async def lifespan(_app: FastAPI):
    db.init()
    # Jobs, die beim letzten Stopp noch liefen, sind nicht mehr aktiv.
    db.execute(
        "UPDATE jobs SET status = 'interrupted', finished_at = ?"
        " WHERE status IN ('running', 'queued')",
        (db.now(),),
    )
    # Zuweisungen aus abgebrochenen Laeufen freigeben - pausierte Vorgaenge
    # behalten ihre Eintraege und warten weiter auf ihr „Go“.
    jobs.release_orphaned_claims()
    yield


app = FastAPI(title="Telegram Panel", lifespan=lifespan)


@app.middleware("http")
async def basic_auth(request: Request, call_next):
    """Optionaler Schutz - aktiv sobald PANEL_PASSWORD gesetzt ist."""
    if not PANEL_PASSWORD:
        return await call_next(request)

    header = request.headers.get("authorization", "")
    if header.startswith("Basic "):
        import base64

        try:
            decoded = base64.b64decode(header[6:]).decode()
            user, _, password = decoded.partition(":")
            if secrets.compare_digest(user, PANEL_USER) and secrets.compare_digest(
                password, PANEL_PASSWORD
            ):
                return await call_next(request)
        except Exception:
            pass

    return Response(
        status_code=401,
        headers={"WWW-Authenticate": 'Basic realm="Telegram Panel"'},
        content="Zugang erforderlich.",
    )


@app.exception_handler(Exception)
async def unhandled(_request: Request, exc: Exception) -> JSONResponse:
    return JSONResponse(status_code=500, content={"detail": str(exc)})


app.include_router(router)
app.mount("/static", StaticFiles(directory=FRONTEND_DIR), name="static")


@app.get("/")
def index() -> FileResponse:
    return FileResponse(FRONTEND_DIR / "index.html")
