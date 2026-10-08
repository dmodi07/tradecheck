"""FastAPI app: POST /screen returns a graded verdict + evidence for a name.

Run:  uvicorn app.main:app --reload
      open http://127.0.0.1:8000
"""

from __future__ import annotations

from pathlib import Path

from fastapi import FastAPI
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from match.screen import screen, status

STATIC_DIR = Path(__file__).resolve().parent / "static"

app = FastAPI(title="TradeCheck", description="Free US + Canada sanctions screening for small businesses.")


@app.middleware("http")
async def revalidate_pages(request, call_next):
    """no-cache on the page and its assets: browsers revalidate, so a new design shows up on the next load."""
    response = await call_next(request)
    if request.url.path == "/" or request.url.path.startswith("/static/"):
        response.headers["Cache-Control"] = "no-cache"
    return response


class ScreenRequest(BaseModel):
    name: str


@app.get("/health")
def health() -> dict:
    return {"status": "ok"}


@app.get("/status")
def status_endpoint() -> dict:
    return status()


@app.post("/screen")
def screen_endpoint(req: ScreenRequest) -> dict:
    return screen(req.name)


@app.get("/")
def index() -> FileResponse:
    return FileResponse(STATIC_DIR / "index.html")


# Serve the static assets (index.html and anything added later).
app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")
