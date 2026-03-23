"""Orchestrates scraping across all configured sources."""

import asyncio
import logging
import re

from app.data.profile_seed import CANDIDATE_PROFILE
from app.data.target_companies import TARGET_COMPANIES
from app.models.schemas import ClusterPriority, JobListing, WorkMode
from app.services.job_store import job_store
from app.services.scrapers.adzuna import AdzunaScraper
from app.services.scrapers.arbeitnow import ArbeitnowScraper
from app.services.scrapers.ats_apis import (
    scrape_ashby,
    scrape_greenhouse,
    scrape_lever,
    scrape_personio_xml,
    scrape_smartrecruiters,
)
from app.services.scrapers.base import BaseScraper
from app.services.scrapers.career_page import CareerPageScraper
from app.services.scrapers.firecrawl_scraper import FirecrawlScraper
from app.services.scrapers.google_search import (
    GoogleBooleanSearchScraper,
    generate_boolean_queries,
)
from app.services.scoring import score_and_rank_jobs

logger = logging.getLogger(__name__)

# Locations considered reachable from München area
_GOOD_LOCATIONS_RE = re.compile(
    r"münchen|munich|muc|remote|germany|deutschland|dach|"
    r"berlin|hamburg|frankfurt|köln|cologne|düsseldorf|stuttgart|nürnberg|nuremberg|"
    r"augsburg|ingolstadt|rosenheim|regensburg|salzburg|innsbruck|"
    r"see posting|nicht angegeben|tbd",
    re.IGNORECASE,
)
# Locations that are clearly too far unless remote
_BAD_LOCATIONS_RE = re.compile(
    r"\b(usa|us|united states|new york|san francisco|sf|bay area|boston|seattle|"
    r"los angeles|la|london|uk|paris|france|amsterdam|singapore|sydney|tokyo|"
    r"tel aviv|israel|india|bangalore|hyderabad|canada|toronto|vancouver|"
    r"china|beijing|shanghai|brazil|são paulo|dubai|uae|chicago|austin|denver|"
    r"washington dc|miami|atlanta|philadelphia|dallas|portland|"
    r"heidelberg|mannheim|karlsruhe|freiburg|saarbrücken|kiel|rostock)\b",
    re.IGNORECASE,
)


def _is_location_relevant(job: JobListing) -> bool:
    """Check if a job location is relevant (München area, major DE cities, or remote)."""
    loc = job.location or ""
    # Remote jobs are always relevant
    if job.work_mode == WorkMode.REMOTE:
        return True
    if "remote" in loc.lower():
        return True
    # If location matches a bad pattern AND not remote, skip
    if _BAD_LOCATIONS_RE.search(loc):
        return False
    # If location matches good pattern, keep
    if _GOOD_LOCATIONS_RE.search(loc):
        return True
    # Unknown location - keep it (might be relevant)
    return True


ALL_SCRAPERS: list[BaseScraper] = [
    AdzunaScraper(),
    ArbeitnowScraper(),
    FirecrawlScraper(),
]

career_scraper = CareerPageScraper()
google_scraper = GoogleBooleanSearchScraper()

# Map ATS platform names to scraper functions
ATS_SCRAPERS = {
    "greenhouse": scrape_greenhouse,
    "lever": scrape_lever,
    "ashby": scrape_ashby,
    "personio": scrape_personio_xml,
    "smartrecruiters": scrape_smartrecruiters,
}


def get_active_scrapers() -> list[dict]:
    """Return status of all scrapers."""
    scrapers = [
        {
            "name": s.source_name,
            "display_name": s.display_name,
            "configured": s.is_configured(),
        }
        for s in ALL_SCRAPERS
    ]
    scrapers.append({
        "name": career_scraper.source_name,
        "display_name": career_scraper.display_name,
        "configured": True,
    })
    scrapers.append({
        "name": "ats_apis",
        "display_name": "ATS APIs (Greenhouse, Lever, Ashby, Personio, SmartRecruiters)",
        "configured": True,
    })
    return scrapers


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


async def _crawl_company_ats(company: dict) -> list[JobListing]:
    """Try to fetch jobs from a company's ATS API. Falls back to HTML scraping."""
    ats = company.get("ats")
    name = company["name"]

    if ats:
        platform = ats["platform"]
        slug = ats["slug"]
        scraper_fn = ATS_SCRAPERS.get(platform)
        if scraper_fn:
            try:
                # Pass eu=True for Greenhouse EU companies
                kwargs = {"board_slug": slug, "company_name": name}
                if platform == "greenhouse" and ats.get("eu"):
                    kwargs["eu"] = True
                jobs = await scraper_fn(**kwargs)
                if jobs:
                    logger.info(f"ATS API ({platform}): {name} -> {len(jobs)} jobs")
                    return jobs
                logger.info(f"ATS API ({platform}): {name} -> 0 jobs, falling back to HTML")
            except Exception as e:
                logger.warning(f"ATS API ({platform}) failed for {name}: {e}")

    # Fallback: HTML scraping
    try:
        jobs = await career_scraper.crawl_career_page(company["careers_url"], name)
        logger.info(f"HTML scrape: {name} -> {len(jobs)} jobs")
        return jobs
    except Exception as e:
        logger.warning(f"HTML scrape failed for {name}: {e}")
        return []


async def crawl_target_companies() -> dict:
    """Crawl all target company career pages via ATS APIs + HTML fallback."""
    # Run all company crawls concurrently (with semaphore to avoid flooding)
    sem = asyncio.Semaphore(5)

    async def _crawl_with_sem(company):
        async with sem:
            return company["name"], await _crawl_company_ats(company)

    tasks = [_crawl_with_sem(c) for c in TARGET_COMPANIES]
    results = await asyncio.gather(*tasks)

    per_company = {}
    all_jobs = []
    new_count = 0
    filtered_count = 0

    for name, jobs in results:
        company = next(c for c in TARGET_COMPANIES if c["name"] == name)
        ats = company.get("ats")

        relevant = [j for j in jobs if _is_location_relevant(j)]
        skipped = len(jobs) - len(relevant)
        if skipped:
            logger.info("%s: filtered out %d jobs with irrelevant location", name, skipped)
        filtered_count += skipped

        per_company[name] = {
            "url": company["careers_url"],
            "ats": ats["platform"] if ats else "html",
            "jobs_found": len(jobs),
            "jobs_relevant": len(relevant),
            "status": "ok" if relevant else ("no_relevant_jobs" if jobs else "no_jobs_found"),
        }

        for job in relevant:
            if not job_store.exists_by_url(job.url):
                job_store.add(job)
                new_count += 1
        all_jobs.extend(relevant)

    scored = score_and_rank_jobs(job_store.get_all())
    blocked = [name for name, info in per_company.items() if info["status"] != "ok"]

    return {
        "companies_crawled": len(TARGET_COMPANIES),
        "total_jobs_found": len(all_jobs),
        "location_filtered": filtered_count,
        "new_added": new_count,
        "blocked_companies": blocked,
        "total_in_store": job_store.count(),
        "jobs_above_threshold": len(scored),
        "per_company": per_company,
    }


async def crawl_single_company(company_name: str) -> dict:
    """Crawl a single company's career page by name."""
    company = next(
        (c for c in TARGET_COMPANIES if c["name"].lower() == company_name.lower()),
        None,
    )
    if not company:
        return {"error": f"Company '{company_name}' not found in target list"}

    jobs = await _crawl_company_ats(company)

    new_count = 0
    for job in jobs:
        if not job_store.exists_by_url(job.url):
            job_store.add(job)
            new_count += 1

    return {
        "company": company["name"],
        "url": company["careers_url"],
        "ats": company.get("ats", {}).get("platform", "html") if company.get("ats") else "html",
        "jobs_found": len(jobs),
        "new_added": new_count,
        "jobs": [{"title": j.title, "url": j.url, "location": j.location} for j in jobs],
    }


async def run_google_boolean_search() -> dict:
    """Run all generated boolean queries through Google and store results."""
    queries = generate_boolean_queries(CANDIDATE_PROFILE.job_titles)

    total_found = 0
    total_new = 0
    total_filtered = 0
    results_per_query = []

    for q in queries:
        logger.info("Running query: %s", q["name"])
        jobs = await google_scraper.search(q["query"], max_results=20)
        relevant = [j for j in jobs if _is_location_relevant(j)]
        filtered = len(jobs) - len(relevant)
        total_filtered += filtered

        new_count = 0
        for job in relevant:
            if not job_store.exists_by_url(job.url):
                job_store.add(job)
                new_count += 1

        total_found += len(relevant)
        total_new += new_count
        results_per_query.append({
            "name": q["name"],
            "cluster": q["cluster"],
            "strategy": q["strategy"],
            "found": len(jobs),
            "relevant": len(relevant),
            "new": new_count,
        })

    scored = score_and_rank_jobs(job_store.get_all())

    return {
        "queries_run": len(queries),
        "total_found": total_found,
        "location_filtered": total_filtered,
        "new_added": total_new,
        "total_in_store": job_store.count(),
        "jobs_above_threshold": len(scored),
        "top_job": {
            "title": scored[0].job.title,
            "company": scored[0].job.company,
            "score": scored[0].total_score,
        } if scored else None,
        "per_query": results_per_query,
    }


async def run_single_boolean_query(query: str) -> dict:
    """Run a single custom boolean query through Google."""
    jobs = await google_scraper.search(query, max_results=30)

    new_count = 0
    for job in jobs:
        if not job_store.exists_by_url(job.url):
            job_store.add(job)
            new_count += 1

    scored = score_and_rank_jobs(job_store.get_all())

    return {
        "query": query,
        "found": len(jobs),
        "new_added": new_count,
        "total_in_store": job_store.count(),
        "jobs": [
            {"title": j.title, "company": j.company, "url": j.url}
            for j in jobs
        ],
    }
