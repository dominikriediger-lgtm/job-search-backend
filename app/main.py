import logging
from pathlib import Path

from fastapi import FastAPI

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s [%(name)s] %(message)s",
)
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from app.api.routes import router
from app.core.config import settings

STATIC_DIR = Path(__file__).parent / "static"

app = FastAPI(
    title=settings.app_name,
    description="Backend for job search aggregation, scoring, and AI enrichment",
    version="0.1.0",
)

app.include_router(router, prefix="/api/v1")
app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")


@app.get("/")
def root():
    return FileResponse(STATIC_DIR / "index.html")
