"""Orchestrates scraping across all configured sources."""

import asyncio

from app.data.profile_seed import CANDIDATE_PROFILE
from app.models.schemas import ClusterPriority, JobListing
from app.services.job_store import job_store
from app.services.scrapers.adzuna import AdzunaScraper
from app.services.scrapers.arbeitnow import ArbeitnowScraper
from app.services.scrapers.base import BaseScraper
from app.services.scrapers.firecrawl_scraper import FirecrawlScraper
from app.services.scoring import score_and_rank_jobs

ALL_SCRAPERS: list[BaseScraper] = [
    AdzunaScraper(),
    ArbeitnowScraper(),
    FirecrawlScraper(),
]


def get_active_scrapers() -> list[dict]:
    """Return status of all scrapers."""
    return [
        {
            "name": s.source_name,
            "display_name": s.display_name,
            "configured": s.is_configured(),
        }
        for s in ALL_SCRAPERS
    ]


async def _scrape_source(scraper: BaseScraper, query: str, location: str, max_results: int) -> list[JobListing]:
    """Run a single scraper with error handling."""
    if not scraper.is_configured():
        return []
    try:
        return await scraper.search(query, location, max_results)
    except Exception:
        return []


async def scrape_all_sources(
    query: str,
    location: str = "München",
    max_per_source: int = 25,
) -> dict:
    """Run all configured scrapers for a single query. Returns summary."""
    tasks = [
        _scrape_source(scraper, query, location, max_per_source)
        for scraper in ALL_SCRAPERS
        if scraper.is_configured()
    ]
    results = await asyncio.gather(*tasks)

    all_jobs = []
    new_count = 0
    for job_list in results:
        for job in job_list:
            if not job_store.exists_by_url(job.url):
                job_store.add(job)
                new_count += 1
            all_jobs.append(job)

    return {
        "total_found": len(all_jobs),
        "new_added": new_count,
        "duplicates_skipped": len(all_jobs) - new_count,
    }


async def run_full_search(max_per_source: int = 15) -> dict:
    """Run search queries for all target job titles across all sources.

    Prioritizes Cluster A titles, then B, then C.
    """
    location = CANDIDATE_PROFILE.search_preferences.location
    cluster_order = [ClusterPriority.A, ClusterPriority.B, ClusterPriority.C]

    total_found = 0
    total_new = 0
    queries_run = 0

    for cluster in cluster_order:
        titles = [jt for jt in CANDIDATE_PROFILE.job_titles if jt.cluster == cluster]
        for title in titles:
            result = await scrape_all_sources(title.title, location, max_per_source)
            total_found += result["total_found"]
            total_new += result["new_added"]
            queries_run += 1

    # Score all new jobs
    all_jobs = job_store.get_all()
    scored = score_and_rank_jobs(all_jobs)

    return {
        "queries_run": queries_run,
        "total_found": total_found,
        "new_added": total_new,
        "total_in_store": job_store.count(),
        "jobs_above_threshold": len(scored),
        "top_score": scored[0].total_score if scored else 0,
        "top_job": {
            "title": scored[0].job.title,
            "company": scored[0].job.company,
            "score": scored[0].total_score,
        } if scored else None,
    }
