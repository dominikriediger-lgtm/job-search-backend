from fastapi import FastAPI

from app.api.routes import router
from app.core.config import settings

app = FastAPI(
    title=settings.app_name,
    description="Backend for job search aggregation, scoring, and AI enrichment",
    version="0.1.0",
)

app.include_router(router, prefix="/api/v1")


@app.get("/")
def root():
    return {
        "app": settings.app_name,
        "version": "0.1.0",
        "docs": "/docs",
    }
