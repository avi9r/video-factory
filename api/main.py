"""YouTube Video Factory API."""

import sys
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import RedirectResponse
from fastapi.staticfiles import StaticFiles

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from api.routes import audio, channels, generate, status  # noqa: E402
from lib.config import OUTPUT_BASE, PROJECT_ROOT  # noqa: E402

app = FastAPI(title="YouTube Video Factory", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

ui_dir = PROJECT_ROOT / "ui"
output_dir = OUTPUT_BASE
ui_dir.mkdir(exist_ok=True)
output_dir.mkdir(exist_ok=True)

app.mount("/ui", StaticFiles(directory=str(ui_dir), html=True), name="ui")
app.mount("/output", StaticFiles(directory=str(output_dir)), name="output")

app.include_router(generate.router, prefix="/generate", tags=["generation"])
app.include_router(channels.router, prefix="/channels", tags=["channels"])
app.include_router(audio.router, prefix="/audio", tags=["audio"])
app.include_router(status.router, prefix="/status", tags=["status"])


@app.get("/health")
def health():
    return {"status": "ok", "version": "1.0.0"}


@app.get("/")
def root():
    return RedirectResponse(url="/ui/index.html")
