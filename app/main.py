"""
Job Search Backend API

Backend for aggregation, scoring, and AI enrichment of job offers
from APIs and career sites.
"""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

app = FastAPI(
    title="Job Search Backend",
    description="Backend für Aggregation, Scoring und KI-Anreicherung von Jobangeboten aus APIs und Karriereseiten.",
    version="0.1.0",
)

# Configure CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/")
async def root():
    """Root endpoint returning API status."""
    return {
        "status": "ok",
        "message": "Job Search Backend API is running",
        "version": "0.1.0",
    }


@app.get("/health")
async def health_check():
    """Health check endpoint."""
    return {"status": "healthy"}
