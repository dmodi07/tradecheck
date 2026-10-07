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

from match.screen import screen

STATIC_DIR = Path(__file__).resolve().parent / "static"

app = FastAPI(title="TradeCheck", description="Free US + Canada sanctions screening for small businesses.")


class ScreenRequest(BaseModel):
    name: str


@app.get("/health")
def health() -> dict:
    return {"status": "ok"}


@app.post("/screen")
def screen_endpoint(req: ScreenRequest) -> dict:
    return screen(req.name)


@app.get("/")
def index() -> FileResponse:
    return FileResponse(STATIC_DIR / "index.html")


# Serve the static assets (index.html and anything added later).
app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")
