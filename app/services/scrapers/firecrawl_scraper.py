"""Firecrawl-based scraper for company career pages and job boards."""

import httpx

from app.core.config import settings
from app.models.schemas import JobListing, WorkMode
from app.services.scrapers.base import BaseScraper


class FirecrawlScraper(BaseScraper):
    """Scraper using Firecrawl API to crawl career pages.

    Handles JavaScript rendering and anti-bot measures.
    Free tier: 500 credits/month. Sign up at firecrawl.dev.
    """

    BASE_URL = "https://api.firecrawl.dev/v1"

    @property
    def source_name(self) -> str:
        return "firecrawl"

    @property
    def display_name(self) -> str:
        return "Firecrawl (Career Pages)"

    def is_configured(self) -> bool:
        return bool(settings.firecrawl_api_key)

    async def scrape_career_page(self, url: str) -> str:
        """Scrape a single career page and return markdown content."""
        if not self.is_configured():
            return ""

        headers = {
            "Authorization": f"Bearer {settings.firecrawl_api_key}",
            "Content-Type": "application/json",
        }
        payload = {
            "url": url,
            "formats": ["markdown"],
        }

        async with httpx.AsyncClient(timeout=30.0) as client:
            try:
                resp = await client.post(f"{self.BASE_URL}/scrape", json=payload, headers=headers)
                resp.raise_for_status()
                data = resp.json()
                return data.get("data", {}).get("markdown", "")
            except (httpx.HTTPError, ValueError):
                return ""

    async def search(self, query: str, location: str = "München", max_results: int = 25) -> list[JobListing]:
        """For Firecrawl, 'query' is expected to be a career page URL."""
        if not self.is_configured():
            return []

        content = await self.scrape_career_page(query)
        if not content:
            return []

        # Return raw scraped content as a single job listing for further AI processing
        # In production, an LLM would parse this into structured job listings
        return [JobListing(
            title=f"[Scraped] Jobs from {query}",
            company="See description",
            location=location,
            description=content[:5000],
            url=query,
            source=self.source_name,
        )]
