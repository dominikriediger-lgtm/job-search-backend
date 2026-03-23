"""Arbeitnow API scraper - free, no API key needed, German/EU startup jobs."""

import httpx

from app.models.schemas import JobListing, WorkMode
from app.services.scrapers.base import BaseScraper


class ArbeitnowScraper(BaseScraper):
    """Scraper using the Arbeitnow API (https://arbeitnow.com/api).

    Completely free, no API key required. Focuses on German and EU tech/startup jobs.
    """

    BASE_URL = "https://arbeitnow.com/api/job-board-api"

    @property
    def source_name(self) -> str:
        return "arbeitnow"

    @property
    def display_name(self) -> str:
        return "Arbeitnow (DE/EU Startups)"

    def is_configured(self) -> bool:
        return True  # No API key needed

    def _detect_work_mode(self, remote: bool, title: str, description: str) -> WorkMode | None:
        if remote:
            return WorkMode.REMOTE
        text = f"{title} {description}".lower()
        if "hybrid" in text:
            return WorkMode.HYBRID
        return WorkMode.ONSITE

    async def search(self, query: str, location: str = "München", max_results: int = 25) -> list[JobListing]:
        async with httpx.AsyncClient(timeout=15.0) as client:
            try:
                resp = await client.get(self.BASE_URL)
                resp.raise_for_status()
                data = resp.json()
            except (httpx.HTTPError, ValueError):
                return []

        query_lower = query.lower()
        location_lower = location.lower()
        jobs = []

        for item in data.get("data", []):
            title = item.get("title", "")
            company = item.get("company_name", "Unknown")
            item_location = item.get("location", "")
            description = item.get("description", "")
            url = item.get("url", "")
            remote = item.get("remote", False)
            tags = [t.lower() for t in item.get("tags", [])]

            # Filter: query must match title, description, or tags
            searchable = f"{title} {description} {' '.join(tags)}".lower()
            if query_lower not in searchable:
                continue

            # Filter: location match (or remote)
            if not remote and location_lower not in item_location.lower():
                continue

            jobs.append(JobListing(
                title=title,
                company=company,
                location=item_location if item_location else ("Remote" if remote else "Unknown"),
                work_mode=self._detect_work_mode(remote, title, description),
                description=description[:2000],  # Truncate long HTML descriptions
                url=url,
                source=self.source_name,
            ))

            if len(jobs) >= max_results:
                break

        return jobs
