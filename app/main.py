import logging
from pathlib import Path

from fastapi import FastAPI
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s [%(name)s] %(message)s",
)

from app.api.routes import router
from app.core.config import settings

logger = logging.getLogger(__name__)

STATIC_DIR = Path(__file__).parent / "static"

app = FastAPI(
    title=settings.app_name,
    description="Backend for job search aggregation, scoring, and AI enrichment",
    version="0.1.0",
)

app.include_router(router, prefix="/api/v1")
app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")


@app.on_event("startup")
def _log_config():
    logger.info("=== Job Search Agent starting ===")
    logger.info("SERPAPI_KEY configured: %s", "YES" if settings.serpapi_key else "NO")
    logger.info("ADZUNA configured: %s", "YES" if settings.adzuna_app_id else "NO")
    logger.info("FIRECRAWL configured: %s", "YES" if settings.firecrawl_api_key else "NO")


@app.get("/")
def root():
    return FileResponse(STATIC_DIR / "index.html")
