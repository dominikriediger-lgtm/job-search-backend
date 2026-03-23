"""Direct career page scraper - crawls company career pages with httpx + BeautifulSoup.

No API key needed. Falls back to Firecrawl only if a page blocks us.
"""

import re
from urllib.parse import urljoin

import httpx
from bs4 import BeautifulSoup

from app.models.schemas import JobListing, WorkMode
from app.services.scrapers.base import BaseScraper

# Common patterns for job listing links on career pages
JOB_LINK_PATTERNS = [
    re.compile(r"/jobs?/", re.IGNORECASE),
    re.compile(r"/career", re.IGNORECASE),
    re.compile(r"/position", re.IGNORECASE),
    re.compile(r"/opening", re.IGNORECASE),
    re.compile(r"/stell", re.IGNORECASE),  # German: Stellenangebot
    re.compile(r"/vacanc", re.IGNORECASE),
    re.compile(r"/apply", re.IGNORECASE),
    re.compile(r"lever\.co/", re.IGNORECASE),
    re.compile(r"greenhouse\.io/", re.IGNORECASE),
    re.compile(r"ashbyhq\.com/", re.IGNORECASE),
    re.compile(r"recruitee\.com/", re.IGNORECASE),
    re.compile(r"personio\.de/", re.IGNORECASE),
    re.compile(r"workable\.com/", re.IGNORECASE),
    re.compile(r"breezy\.hr/", re.IGNORECASE),
    re.compile(r"smartrecruiters\.com/", re.IGNORECASE),
]

# Words that indicate a link is a job posting (not navigation)
JOB_TITLE_SIGNALS = [
    "manager", "lead", "head", "director", "chief", "staff",
    "engineer", "developer", "analyst", "specialist", "consultant",
    "associate", "coordinator", "operations", "strategy", "product",
    "transformation", "automation", "crm", "revenue", "growth",
    "commercial", "business", "digital", "data", "ai",
    # German
    "leiter", "berater", "spezialist", "referent",
]

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "de-DE,de;q=0.9,en-US;q=0.8,en;q=0.7",
}


class CareerPageScraper(BaseScraper):
    """Scrapes company career pages directly using httpx + BeautifulSoup."""

    @property
    def source_name(self) -> str:
        return "career_page"

    @property
    def display_name(self) -> str:
        return "Direct Career Page Crawler"

    def is_configured(self) -> bool:
        return True

    def _detect_work_mode(self, text: str) -> WorkMode | None:
        text_lower = text.lower()
        if "remote" in text_lower:
            return WorkMode.REMOTE
        if "hybrid" in text_lower:
            return WorkMode.HYBRID
        if "vor ort" in text_lower or "on-site" in text_lower:
            return WorkMode.ONSITE
        return None

    def _is_job_link(self, href: str, text: str) -> bool:
        """Check if a link likely points to a job posting."""
        if not href:
            return False
        # Check URL patterns
        for pattern in JOB_LINK_PATTERNS:
            if pattern.search(href):
                return True
        # Check link text for job-related words
        text_lower = text.lower()
        return any(signal in text_lower for signal in JOB_TITLE_SIGNALS)

    def _extract_jobs_from_html(self, html: str, base_url: str, company: str) -> list[dict]:
        """Extract job postings from a career page HTML."""
        soup = BeautifulSoup(html, "lxml")
        jobs = []
        seen_urls = set()

        # Strategy 1: Find job listing containers (common patterns)
        # Many career pages use structured lists/cards
        for link in soup.find_all("a", href=True):
            href = link["href"]
            text = link.get_text(strip=True)

            if not text or len(text) < 5 or len(text) > 200:
                continue

            if not self._is_job_link(href, text):
                continue

            # Build absolute URL
            full_url = urljoin(base_url, href)

            if full_url in seen_urls:
                continue
            seen_urls.add(full_url)

            # Try to find location/department info near the link
            parent = link.parent
            context_text = parent.get_text(separator=" | ", strip=True) if parent else ""

            jobs.append({
                "title": text,
                "url": full_url,
                "context": context_text,
                "company": company,
            })

        return jobs

    async def crawl_career_page(self, url: str, company: str) -> list[JobListing]:
        """Crawl a single career page and extract job listings."""
        async with httpx.AsyncClient(timeout=20.0, follow_redirects=True, headers=HEADERS) as client:
            try:
                resp = await client.get(url)
                resp.raise_for_status()
            except httpx.HTTPError:
                return []

        if resp.status_code != 200:
            return []

        raw_jobs = self._extract_jobs_from_html(resp.text, url, company)

        listings = []
        for raw in raw_jobs:
            listings.append(JobListing(
                title=raw["title"],
                company=company,
                location=self._extract_location(raw["context"]) or "See posting",
                work_mode=self._detect_work_mode(raw["context"]),
                description=raw["context"][:2000],
                url=raw["url"],
                source=self.source_name,
            ))

        return listings

    def _extract_location(self, context: str) -> str | None:
        """Try to extract location from context text."""
        location_patterns = [
            r"(München|Munich|Berlin|Hamburg|Frankfurt|Köln|Stuttgart|Remote|Hybrid)",
            r"(Germany|Deutschland|DACH)",
        ]
        for pattern in location_patterns:
            match = re.search(pattern, context, re.IGNORECASE)
            if match:
                return match.group(1)
        return None

    async def search(self, query: str, location: str = "München", max_results: int = 25) -> list[JobListing]:
        """For career page scraper, 'query' is the career page URL.

        Use crawl_career_page() directly for better control.
        """
        # Assume query is a URL
        if query.startswith("http"):
            return await self.crawl_career_page(query, company="Unknown")
        return []

    async def crawl_all_companies(self, companies: list[dict], max_per_company: int = 50) -> dict:
        """Crawl career pages of all provided companies.

        Args:
            companies: List of dicts with 'name' and 'careers_url' keys.
            max_per_company: Max jobs to extract per company.

        Returns:
            Summary dict with results per company.
        """
        results = {}
        all_jobs = []

        for company in companies:
            name = company["name"]
            url = company["careers_url"]

            jobs = await self.crawl_career_page(url, name)
            jobs = jobs[:max_per_company]

            results[name] = {
                "url": url,
                "jobs_found": len(jobs),
                "status": "ok" if jobs else "no_jobs_found",
            }
            all_jobs.extend(jobs)

        return {
            "companies_crawled": len(companies),
            "total_jobs_found": len(all_jobs),
            "per_company": results,
            "jobs": all_jobs,
        }
