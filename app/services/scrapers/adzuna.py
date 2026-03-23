"""Adzuna API scraper - aggregates jobs from multiple boards (free tier: 250 calls/month)."""

import httpx

from app.core.config import settings
from app.models.schemas import JobListing, WorkMode
from app.services.scrapers.base import BaseScraper


class AdzunaScraper(BaseScraper):
    """Scraper using the Adzuna API (https://developer.adzuna.com).

    Adzuna aggregates jobs from LinkedIn, StepStone, Indeed, Monster, etc.
    Free tier: 250 API calls/month. Sign up at developer.adzuna.com.
    """

    BASE_URL = "https://api.adzuna.com/v1/api/jobs/de/search"

    @property
    def source_name(self) -> str:
        return "adzuna"

    @property
    def display_name(self) -> str:
        return "Adzuna (Aggregator)"

    def is_configured(self) -> bool:
        return bool(settings.adzuna_app_id and settings.adzuna_api_key)

    def _detect_work_mode(self, title: str, description: str) -> WorkMode | None:
        text = f"{title} {description}".lower()
        if "remote" in text:
            return WorkMode.REMOTE
        if "hybrid" in text:
            return WorkMode.HYBRID
        if "vor ort" in text or "on-site" in text or "onsite" in text:
            return WorkMode.ONSITE
        return None

    async def search(self, query: str, location: str = "München", max_results: int = 25) -> list[JobListing]:
        if not self.is_configured():
            return []

        params = {
            "app_id": settings.adzuna_app_id,
            "app_key": settings.adzuna_api_key,
            "results_per_page": min(max_results, 50),
            "what": query,
            "where": location,
            "sort_by": "relevance",
            "content-type": "application/json",
        }

        async with httpx.AsyncClient(timeout=15.0) as client:
            try:
                resp = await client.get(f"{self.BASE_URL}/1", params=params)
                resp.raise_for_status()
                data = resp.json()
            except (httpx.HTTPError, ValueError):
                return []

        jobs = []
        for result in data.get("results", []):
            title = result.get("title", "")
            description = result.get("description", "")
            company = result.get("company", {}).get("display_name", "Unknown")
            location_name = result.get("location", {}).get("display_name", location)
            url = result.get("redirect_url", "")

            salary_min = result.get("salary_min")
            salary_max = result.get("salary_max")

            jobs.append(JobListing(
                title=title,
                company=company,
                location=location_name,
                work_mode=self._detect_work_mode(title, description),
                salary_min=int(salary_min) if salary_min else None,
                salary_max=int(salary_max) if salary_max else None,
                description=description,
                url=url,
                source=self.source_name,
            ))

        return jobs
