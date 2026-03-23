"""API routes for the job search agent."""

from fastapi import APIRouter, HTTPException

from app.data.profile_seed import CANDIDATE_PROFILE
from app.data.target_companies import TARGET_COMPANIES, get_career_urls
from app.models.schemas import JobListing, JobStatus, ScoredJob
from app.services.company_discovery import add_runtime_company, discover_companies, get_all_companies
from app.services.job_store import job_store
from app.services.scrape_orchestrator import (
    crawl_single_company,
    crawl_target_companies,
    get_active_scrapers,
    run_full_search,
    run_google_boolean_search,
    run_single_boolean_query,
    scrape_all_sources,
)
from app.services.scrapers.google_search import generate_boolean_queries
from app.services.scoring import score_and_rank_jobs, score_job
from app.services.search import generate_search_queries, get_supported_sources

router = APIRouter()


@router.get("/profile")
def get_profile():
    """Return the candidate profile."""
    return CANDIDATE_PROFILE


@router.get("/profile/titles")
def get_target_titles():
    """Return all target job titles grouped by cluster."""
    clusters = {}
    for jt in CANDIDATE_PROFILE.job_titles:
        cluster_key = jt.cluster.value
        if cluster_key not in clusters:
            clusters[cluster_key] = []
        clusters[cluster_key].append({"title": jt.title, "keywords": jt.keywords})
    return clusters


@router.get("/search/queries")
def get_search_queries(max_queries: int = 30):
    """Generate search queries based on profile."""
    return generate_search_queries(max_queries)


@router.get("/search/sources")
def get_sources():
    """Return supported job sources."""
    return get_supported_sources()


@router.post("/jobs", response_model=JobListing)
def add_job(job: JobListing):
    """Add a new job listing."""
    if job.url and job_store.exists_by_url(job.url):
        raise HTTPException(status_code=409, detail="Job with this URL already exists")
    return job_store.add(job)


@router.post("/jobs/batch", response_model=list[JobListing])
def add_jobs_batch(jobs: list[JobListing]):
    """Add multiple job listings at once."""
    added = []
    for job in jobs:
        if not job_store.exists_by_url(job.url):
            added.append(job_store.add(job))
    return added


@router.get("/jobs", response_model=list[JobListing])
def list_jobs(status: JobStatus | None = None):
    """List all jobs, optionally filtered by status."""
    return job_store.get_all(status)


@router.get("/jobs/{job_id}", response_model=JobListing)
def get_job(job_id: str):
    """Get a specific job by ID."""
    job = job_store.get(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    return job


@router.patch("/jobs/{job_id}/status")
def update_job_status(job_id: str, status: JobStatus):
    """Update job status (e.g. applied, interview, rejected)."""
    job = job_store.update_status(job_id, status)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    return job


@router.post("/jobs/score", response_model=ScoredJob)
def score_single_job(job: JobListing):
    """Score a single job against the profile."""
    return score_job(job)


@router.get("/jobs/scored/all", response_model=list[ScoredJob])
def get_scored_jobs(include_below_threshold: bool = False):
    """Score and rank all stored jobs.

    By default only returns jobs above the min score threshold.
    Pass include_below_threshold=true to see everything.
    """
    jobs = job_store.get_all()
    if include_below_threshold:
        scored = [score_job(job) for job in jobs]
        scored.sort(key=lambda s: s.total_score, reverse=True)
        return scored
    return score_and_rank_jobs(jobs)


@router.get("/scrapers")
def list_scrapers():
    """Show all scrapers and their configuration status."""
    return get_active_scrapers()


@router.post("/scrape")
async def scrape_query(query: str, location: str = "München", max_per_source: int = 25):
    """Scrape all configured sources for a single query."""
    return await scrape_all_sources(query, location, max_per_source)


@router.post("/scrape/full")
async def scrape_full():
    """Run a full search across all target titles and all configured sources."""
    return await run_full_search()


@router.post("/crawl/companies")
async def crawl_all_companies():
    """Crawl all 22 target company career pages directly."""
    return await crawl_target_companies()


@router.post("/crawl/company/{company_name}")
async def crawl_company(company_name: str):
    """Crawl a single company's career page by name."""
    return await crawl_single_company(company_name)


@router.get("/google/queries")
def get_boolean_queries():
    """Preview all generated Google boolean search queries."""
    return generate_boolean_queries(CANDIDATE_PROFILE.job_titles)


@router.post("/google/search")
async def google_boolean_search():
    """Run all boolean queries through Google and store+score results."""
    return await run_google_boolean_search()


@router.post("/google/custom")
async def google_custom_query(query: str):
    """Run a custom boolean query through Google.

    Example: ("Chief of Staff" OR "Founders Associate") "München" site:linkedin.com/jobs
    """
    return await run_single_boolean_query(query)


@router.get("/companies")
def list_target_companies():
    """List all target companies (static + runtime-added)."""
    return get_all_companies()


@router.get("/companies/careers")
def list_career_urls():
    """List all career page URLs for crawling."""
    return get_career_urls()


@router.post("/companies/add")
def add_company(company: dict):
    """Add a new company to the crawl list at runtime.

    Required: name, careers_url
    Optional: sector, ats, size_estimate, funding_eur, why

    Example:
    {"name": "CoolStartup", "sector": "saas", "careers_url": "https://coolstartup.com/careers"}
    """
    return add_runtime_company(company)


@router.post("/discover/companies")
async def discover_new_companies(max_queries: int = 4):
    """Search news/press for recently funded startups near München.

    Uses SerpAPI to find funding rounds, awards, and press mentions.
    Returns company names, source URLs, and snippets for manual review.
    """
    return await discover_companies(max_queries)


@router.get("/stats")
def get_stats():
    """Return overview stats."""
    all_jobs = job_store.get_all()
    scored = score_and_rank_jobs(all_jobs)
    return {
        "total_jobs": job_store.count(),
        "jobs_above_threshold": len(scored),
        "avg_score": round(sum(s.total_score for s in scored) / len(scored), 1) if scored else 0,
        "top_score": scored[0].total_score if scored else 0,
        "by_status": {
            status.value: len([j for j in all_jobs if j.status == status])
            for status in JobStatus
        },
    }
