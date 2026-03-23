"""Google Boolean Search scraper for job postings.

Uses Google search with boolean operators to find job postings across
LinkedIn, StepStone, Indeed, Greenhouse, Lever, and company career pages.
Prefers SerpAPI when SERPAPI_KEY is set; falls back to direct scraping.
"""

import asyncio
import logging
import os
import re
import time
from urllib.parse import quote_plus, urljoin

import httpx
from bs4 import BeautifulSoup

from app.models.schemas import JobListing, WorkMode
from app.services.scrapers.base import BaseScraper

logger = logging.getLogger(__name__)

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "de-DE,de;q=0.9,en-US;q=0.8,en;q=0.7",
}


class GoogleBooleanSearchScraper(BaseScraper):
    """Finds jobs via Google Boolean search queries.

    Combines site: operators, OR logic, and exclusion terms to find
    relevant job postings across all major platforms.
    """

    @property
    def source_name(self) -> str:
        return "google_boolean"

    @property
    def display_name(self) -> str:
        return "Google Boolean Search"

    _last_request_time: float = 0.0

    def is_configured(self) -> bool:
        return True

    def _detect_work_mode(self, text: str) -> WorkMode | None:
        text_lower = text.lower()
        if "remote" in text_lower:
            return WorkMode.REMOTE
        if "hybrid" in text_lower:
            return WorkMode.HYBRID
        return None

    async def _serpapi_search(self, query: str, num_results: int = 20) -> list[dict]:
        """Execute a search via SerpAPI JSON endpoint."""
        api_key = os.environ.get("SERPAPI_KEY")
        if not api_key:
            return []

        params = {
            "q": query,
            "num": num_results,
            "hl": "de",
            "gl": "de",
            "engine": "google",
            "api_key": api_key,
        }

        async with httpx.AsyncClient(timeout=20.0) as client:
            try:
                logger.debug("SerpAPI request: q=%s num=%d", query[:80], num_results)
                resp = await client.get("https://serpapi.com/search.json", params=params)
                resp.raise_for_status()
            except httpx.HTTPError as exc:
                logger.warning("SerpAPI request failed: %s (check your SERPAPI_KEY at serpapi.com/manage-api-key)", exc)
                return []

        data = resp.json()
        if "error" in data:
            logger.warning("SerpAPI error: %s", data["error"])
            return []
        results = []
        for item in data.get("organic_results", []):
            results.append({
                "title": item.get("title", ""),
                "url": item.get("link", ""),
                "snippet": item.get("snippet", ""),
            })

        logger.info("SerpAPI returned %d organic results", len(results))
        return results

    async def _direct_google_search(self, query: str, num_results: int = 20) -> list[dict]:
        """Execute a direct Google search with rate limiting."""
        # Rate-limit: wait at least 2s between direct requests
        now = time.monotonic()
        elapsed = now - GoogleBooleanSearchScraper._last_request_time
        if elapsed < 2.0:
            delay = 2.0 - elapsed
            logger.debug("Rate-limiting direct Google request: sleeping %.1fs", delay)
            await asyncio.sleep(delay)
        GoogleBooleanSearchScraper._last_request_time = time.monotonic()

        encoded = quote_plus(query)
        url = f"https://www.google.com/search?q={encoded}&num={num_results}&hl=de"

        async with httpx.AsyncClient(timeout=15.0, follow_redirects=True, headers=HEADERS) as client:
            try:
                resp = await client.get(url)
                if resp.status_code in (429, 403):
                    logger.warning(
                        "Google returned HTTP %d for direct search — possible rate limit",
                        resp.status_code,
                    )
                    return []
                resp.raise_for_status()
            except httpx.HTTPError as exc:
                logger.warning("Direct Google search failed: %s", exc)
                return []

        soup = BeautifulSoup(resp.text, "lxml")
        results = []

        # Parse Google search results
        for g in soup.select("div.g, div[data-sokoban-container]"):
            link_tag = g.select_one("a[href]")
            title_tag = g.select_one("h3")
            snippet_tag = g.select_one("div[data-sncf], span.aCOpRe, div.VwiC3b")

            if not link_tag or not title_tag:
                continue

            href = link_tag.get("href", "")
            if not href.startswith("http"):
                continue

            results.append({
                "title": title_tag.get_text(strip=True),
                "url": href,
                "snippet": snippet_tag.get_text(strip=True) if snippet_tag else "",
            })

        logger.info("Direct Google search returned %d results", len(results))
        return results

    async def _google_search(self, query: str, num_results: int = 20) -> list[dict]:
        """Execute a Google search — tries SerpAPI first, falls back to direct scraping."""
        api_key = os.environ.get("SERPAPI_KEY")
        if api_key:
            logger.debug("SERPAPI_KEY set, using SerpAPI as primary backend")
            results = await self._serpapi_search(query, num_results)
            if results:
                return results
            logger.warning("SerpAPI returned no results, falling back to direct scraping")

        return await self._direct_google_search(query, num_results)

    async def search(self, query: str, location: str = "München", max_results: int = 25) -> list[JobListing]:
        """Search Google with the provided boolean query."""
        results = await self._google_search(query, num_results=max_results)

        jobs = []
        for r in results:
            snippet = r.get("snippet", "")
            jobs.append(JobListing(
                title=r["title"],
                company=self._extract_company(r["url"], r["title"]),
                location=self._extract_location(snippet) or location,
                work_mode=self._detect_work_mode(f"{r['title']} {snippet}"),
                description=snippet,
                url=r["url"],
                source=self.source_name,
            ))

        return jobs

    def _extract_company(self, url: str, title: str) -> str:
        """Try to extract company name from URL or title."""
        # LinkedIn pattern: linkedin.com/jobs/view/... at CompanyName
        if "linkedin.com" in url:
            match = re.search(r"at\s+(.+?)(?:\s*[|\-–]|$)", title)
            if match:
                return match.group(1).strip()
        # Greenhouse: boards.greenhouse.io/companyname
        match = re.search(r"greenhouse\.io/(\w+)", url)
        if match:
            return match.group(1).replace("-", " ").title()
        # Lever: jobs.lever.co/companyname
        match = re.search(r"lever\.co/(\w+)", url)
        if match:
            return match.group(1).replace("-", " ").title()
        # Ashby
        match = re.search(r"jobs\.ashbyhq\.com/(\w+)", url)
        if match:
            return match.group(1).replace("-", " ").title()
        return "See posting"

    def _extract_location(self, text: str) -> str | None:
        """Extract location from snippet text."""
        patterns = [
            r"(München|Munich|Berlin|Hamburg|Frankfurt|Köln|Stuttgart|Düsseldorf)",
            r"(Remote|Hybrid)",
            r"(Germany|Deutschland|DACH)",
        ]
        for pattern in patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                return match.group(1)
        return None


# ---------------------------------------------------------------
# Boolean query builder - generates optimized Google search strings
# ---------------------------------------------------------------

# Job board site: filters
SITE_LINKEDIN = 'site:linkedin.com/jobs'
SITE_STEPSTONE = 'site:stepstone.de'
SITE_INDEED = 'site:indeed.com OR site:de.indeed.com'
SITE_GREENHOUSE = 'site:boards.greenhouse.io'
SITE_LEVER = 'site:jobs.lever.co'
SITE_ASHBY = 'site:jobs.ashbyhq.com'
SITE_PERSONIO = 'site:jobs.personio.de'
SITE_SMARTRECRUITERS = 'site:careers.smartrecruiters.com'

ALL_JOB_SITES = f"({SITE_LINKEDIN} OR {SITE_GREENHOUSE} OR {SITE_LEVER} OR {SITE_ASHBY} OR {SITE_PERSONIO} OR {SITE_SMARTRECRUITERS})"
GERMAN_JOB_BOARDS = f"({SITE_LINKEDIN} OR {SITE_STEPSTONE} OR {SITE_INDEED})"


def build_boolean_query(
    titles: list[str],
    location: str = "München",
    site_filter: str | None = None,
    exclude: list[str] | None = None,
    include_keywords: list[str] | None = None,
) -> str:
    """Build a Google boolean search query.

    Example output:
    ("Chief of Staff" OR "Revenue Operations Manager") "München" site:linkedin.com/jobs -intern -praktikum
    """
    # Title OR group
    title_group = " OR ".join(f'"{t}"' for t in titles)
    query = f"({title_group})"

    # Location
    if location:
        query += f' "{location}"'

    # Additional keywords
    if include_keywords:
        kw_group = " OR ".join(f'"{k}"' for k in include_keywords)
        query += f" ({kw_group})"

    # Site filter
    if site_filter:
        query += f" {site_filter}"

    # Exclusions
    default_exclude = ["intern", "praktikum", "werkstudent", "internship", "working student"]
    all_exclude = default_exclude + (exclude or [])
    for ex in all_exclude:
        query += f" -{ex}"

    return query


def generate_boolean_queries(job_titles: list[dict], location: str = "München") -> list[dict]:
    """Generate a set of boolean queries from the candidate profile.

    Groups titles by cluster and creates targeted queries for different platforms.
    """
    queries = []

    # Group titles by cluster
    clusters = {}
    for jt in job_titles:
        cluster = jt.cluster.value if hasattr(jt, 'cluster') else jt.get("cluster", "A")
        cluster_key = cluster.value if hasattr(cluster, 'value') else cluster
        if cluster_key not in clusters:
            clusters[cluster_key] = []
        title = jt.title if hasattr(jt, 'title') else jt.get("title", "")
        clusters[cluster_key].append(title)

    for cluster_key, titles in clusters.items():
        # Query 1: All job boards (broad)
        queries.append({
            "name": f"Cluster {cluster_key} - All Platforms",
            "query": build_boolean_query(titles, location, ALL_JOB_SITES),
            "cluster": cluster_key,
            "strategy": "broad",
        })

        # Query 2: German job boards
        queries.append({
            "name": f"Cluster {cluster_key} - German Boards",
            "query": build_boolean_query(titles, location, GERMAN_JOB_BOARDS),
            "cluster": cluster_key,
            "strategy": "german",
        })

        # Query 3: Open web (no site filter - catches company career pages)
        queries.append({
            "name": f"Cluster {cluster_key} - Open Web",
            "query": build_boolean_query(
                titles, location,
                include_keywords=["career", "karriere", "jobs", "stelle"],
            ),
            "cluster": cluster_key,
            "strategy": "open_web",
        })

        # Query 4: ATS platforms (Greenhouse, Lever, Ashby)
        ats_sites = f"({SITE_GREENHOUSE} OR {SITE_LEVER} OR {SITE_ASHBY})"
        queries.append({
            "name": f"Cluster {cluster_key} - ATS Platforms",
            "query": build_boolean_query(titles, location, ats_sites),
            "cluster": cluster_key,
            "strategy": "ats",
        })

    # Special: AI/Tech focused query
    ai_titles = [
        "AI Transformation Manager",
        "Head of Business Automation",
        "AI Implementation Lead",
        "Digital Transformation Manager",
    ]
    queries.append({
        "name": "AI/Tech Focus - Scale-ups",
        "query": build_boolean_query(
            ai_titles, location,
            include_keywords=["scale-up", "startup", "series"],
            exclude=["senior developer", "senior engineer"],
        ),
        "cluster": "A",
        "strategy": "ai_focused",
    })

    # Special: Chief of Staff / Founder's Associate at funded startups
    cos_titles = ["Chief of Staff", "Founder's Associate", "Founders Associate"]
    queries.append({
        "name": "CoS/FA - Funded Startups",
        "query": build_boolean_query(
            cos_titles, location,
            include_keywords=["series A", "series B", "funded", "venture"],
        ),
        "cluster": "B",
        "strategy": "cos_focused",
    })

    return queries
