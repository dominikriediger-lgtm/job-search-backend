"""Google Boolean Search scraper for job postings.

Uses Google search with boolean operators to find job postings across
LinkedIn, StepStone, Indeed, Greenhouse, Lever, and company career pages.
Prefers SerpAPI when SERPAPI_KEY is set; falls back to direct scraping.
"""

import asyncio
import logging
import re
import time
from urllib.parse import quote_plus, urljoin

import httpx
from bs4 import BeautifulSoup

from app.core.config import settings
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
        api_key = settings.serpapi_key
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
                logger.info("SerpAPI query: %s", query[:120])
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
        api_key = settings.serpapi_key
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
            url = r["url"]
            title = r["title"]
            snippet = r.get("snippet", "")

            # Filter out non-job URLs
            if not self._is_job_url(url, title, snippet):
                logger.debug("Skipping non-job result: %s", title[:80])
                continue

            jobs.append(JobListing(
                title=self._clean_title(title),
                company=self._extract_company(url, title),
                location=self._extract_location(snippet) or location,
                work_mode=self._detect_work_mode(f"{title} {snippet}"),
                description=snippet,
                url=url,
                source=self.source_name,
            ))

        logger.info("Kept %d job results out of %d total", len(jobs), len(results))
        return jobs

    def _is_job_url(self, url: str, title: str, snippet: str) -> bool:
        """Check if a search result is actually a job posting, not a profile/article/noise."""
        url_lower = url.lower()
        text = f"{title} {snippet}".lower()

        # LinkedIn: only accept /jobs/ URLs, reject /in/ (profiles), /pulse/ (articles), /company/ (pages)
        if "linkedin.com" in url_lower:
            if "/jobs/" in url_lower or "/job/" in url_lower:
                return True
            # Reject profiles, articles, company pages
            return False

        # Job board / ATS URLs are always valid
        job_domains = [
            "greenhouse.io", "lever.co", "ashbyhq.com", "personio.de",
            "smartrecruiters.com", "workable.com", "breezy.hr",
            "stepstone.de", "indeed.com", "de.indeed.com",
            "glassdoor.", "xing.com/jobs", "monster.de",
            "arbeitnow.com", "join.com", "stellenanzeigen.de",
        ]
        if any(d in url_lower for d in job_domains):
            return True

        # Company career pages (contains /career, /jobs, /stelle, etc.)
        career_signals = ["/career", "/jobs", "/job/", "/stelle", "/vacancies", "/openings", "/open-positions"]
        if any(s in url_lower for s in career_signals):
            return True

        # Reject obvious non-job content
        noise_patterns = [
            r"\b(wikipedia|arxiv|academia\.edu|researchgate|scholar\.google)\b",
            r"\b(spirit of 1914|freelance.*teaching|english teach)\b",
            r"\b(news|blog|press|article|podcast|interview|review)\b.*\b(about|with|how|why)\b",
        ]
        for pattern in noise_patterns:
            if re.search(pattern, text, re.IGNORECASE):
                return False

        # If the URL doesn't match any known job pattern, check if title looks job-like
        job_title_signals = [
            "manager", "lead", "head", "director", "chief", "officer",
            "analyst", "coordinator", "specialist", "associate",
            "stelle", "job", "position", "hiring", "karriere", "career",
            "(m/w/d)", "(m/f/d)", "(all genders)", "(gn)",
        ]
        if any(s in text for s in job_title_signals):
            return True

        # Default: reject unknown URLs (better to be strict than to show noise)
        logger.debug("Rejecting unknown URL pattern: %s", url[:100])
        return False

    def _clean_title(self, title: str) -> str:
        """Clean up search result titles to extract the actual job title."""
        # Remove common suffixes like " | Company", " - Company", " — Company"
        # But keep the job title part
        title = re.sub(r"\s*[|–—]\s*LinkedIn$", "", title)
        title = re.sub(r"\s*[|–—]\s*StepStone$", "", title)
        title = re.sub(r"\s*[|–—]\s*Indeed\.com$", "", title)
        title = re.sub(r"\s*[|–—]\s*Glassdoor$", "", title)
        return title.strip()

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

    # Exclusions — filter out junior/intern level (candidate has 8+ years experience)
    # and irrelevant job types
    default_exclude = [
        "intern", "internship", "praktikum", "praktikant",
        "werkstudent", "working student",
        "junior", "trainee", "azubi", "ausbildung",
        "graduate program", "entry level", "berufseinsteiger",
        "freelance", "teaching", "teacher", "Nachhilfe",
    ]
    all_exclude = default_exclude + (exclude or [])
    for ex in all_exclude:
        query += f" -{ex}"

    return query


def _batch_titles(titles: list[str], batch_size: int = 3) -> list[list[str]]:
    """Split titles into small batches so queries stay short enough for Google."""
    return [titles[i:i + batch_size] for i in range(0, len(titles), batch_size)]


def generate_boolean_queries(job_titles: list[dict], location: str = "München") -> list[dict]:
    """Generate a set of boolean queries from the candidate profile.

    Groups titles by cluster and creates targeted queries for different platforms.
    Keeps each query short (max 3 titles) so Google/SerpAPI can handle them.
    """
    queries = []

    # Group titles by cluster
    clusters: dict[str, list[str]] = {}
    for jt in job_titles:
        cluster = jt.cluster.value if hasattr(jt, 'cluster') else jt.get("cluster", "A")
        cluster_key = cluster.value if hasattr(cluster, 'value') else cluster
        if cluster_key not in clusters:
            clusters[cluster_key] = []
        title = jt.title if hasattr(jt, 'title') else jt.get("title", "")
        clusters[cluster_key].append(title)

    for cluster_key, titles in clusters.items():
        for i, batch in enumerate(_batch_titles(titles)):
            suffix = f" (batch {i+1})" if len(titles) > 3 else ""

            # LinkedIn + major boards (most results)
            queries.append({
                "name": f"Cluster {cluster_key} - LinkedIn{suffix}",
                "query": build_boolean_query(batch, location, SITE_LINKEDIN),
                "cluster": cluster_key,
                "strategy": "linkedin",
            })

            # ATS platforms (Greenhouse, Lever, Ashby, Personio)
            ats_sites = f"({SITE_GREENHOUSE} OR {SITE_LEVER} OR {SITE_ASHBY} OR {SITE_PERSONIO})"
            queries.append({
                "name": f"Cluster {cluster_key} - ATS{suffix}",
                "query": build_boolean_query(batch, location, ats_sites),
                "cluster": cluster_key,
                "strategy": "ats",
            })

            # German job boards
            queries.append({
                "name": f"Cluster {cluster_key} - StepStone/Indeed{suffix}",
                "query": build_boolean_query(batch, location, GERMAN_JOB_BOARDS),
                "cluster": cluster_key,
                "strategy": "german",
            })

    # Special: AI/Tech focused query
    ai_titles = [
        "AI Transformation Manager",
        "Head of Business Automation",
        "AI Implementation Lead",
    ]
    queries.append({
        "name": "AI/Tech Focus - Scale-ups",
        "query": build_boolean_query(
            ai_titles, location,
            include_keywords=["scale-up", "startup"],
            exclude=["senior developer", "senior engineer"],
        ),
        "cluster": "A",
        "strategy": "ai_focused",
    })

    # Special: Chief of Staff / Founder's Associate
    cos_titles = ["Chief of Staff", "Founder's Associate"]
    queries.append({
        "name": "CoS/FA - Funded Startups",
        "query": build_boolean_query(
            cos_titles, location,
            include_keywords=["series A", "series B", "funded"],
        ),
        "cluster": "B",
        "strategy": "cos_focused",
    })

    # Special: RevOps without location restriction (remote-friendly)
    queries.append({
        "name": "RevOps - Remote Germany",
        "query": build_boolean_query(
            ["Revenue Operations Manager", "RevOps Manager", "Revenue Operations Lead"],
            location="Germany",
            site_filter=SITE_LINKEDIN,
        ),
        "cluster": "A",
        "strategy": "revops_remote",
    })

    return queries
