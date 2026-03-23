"""Discover new startups and scale-ups via funding news and press mentions.

Uses SerpAPI to search for recent funding rounds, awards, and press mentions
of startups in the München area, then extracts company names and career URLs.
"""

import logging
import re

from app.core.config import settings
from app.data.target_companies import TARGET_COMPANIES

logger = logging.getLogger(__name__)

# Search queries to discover new companies
DISCOVERY_QUERIES = [
    # Funding rounds
    '"Finanzierungsrunde" "München" (startup OR scaleup OR "scale-up") 2025..2026',
    '"funding round" "Munich" (startup OR "scale-up") (series OR seed OR "growth equity") 2025..2026',
    '"Series A" OR "Series B" "Munich" startup 2025..2026',
    '"Series A" OR "Series B" "München" startup 2025..2026',
    # Awards and recognition
    '"Munich" startup award 2025..2026 (winner OR finalist OR "best")',
    '"München" "startup" (auszeichnung OR preis OR award) 2025..2026',
    # Hiring signals
    '"Munich" startup hiring (engineering OR operations) 2025..2026',
    # Specific ecosystems
    'site:eu-startups.com Munich 2025..2026',
    'site:tech.eu Munich funding 2025..2026',
    'site:gruenderszene.de München 2025..2026',
    'site:deutsche-startups.de München 2025..2026',
]

# Known target company names (lowercase) to avoid duplicates
_KNOWN_NAMES = {c["name"].lower() for c in TARGET_COMPANIES}


async def discover_companies(max_queries: int = 6) -> dict:
    """Search news for recently funded/awarded startups near München.

    Returns a list of discovered company mentions with source URLs.
    Uses SerpAPI; skips if no key is configured.
    """
    import httpx

    api_key = settings.serpapi_key
    if not api_key:
        return {"error": "SERPAPI_KEY not configured", "companies": []}

    all_mentions: list[dict] = []
    queries_run = 0

    async with httpx.AsyncClient(timeout=20.0) as client:
        for query in DISCOVERY_QUERIES[:max_queries]:
            params = {
                "q": query,
                "num": 10,
                "hl": "de",
                "gl": "de",
                "engine": "google",
                "api_key": api_key,
            }
            try:
                logger.info("Discovery query: %s", query[:100])
                resp = await client.get("https://serpapi.com/search.json", params=params)
                resp.raise_for_status()
            except httpx.HTTPError as exc:
                logger.warning("Discovery search failed: %s", exc)
                continue

            data = resp.json()
            if "error" in data:
                logger.warning("SerpAPI error: %s", data["error"])
                continue

            queries_run += 1
            for item in data.get("organic_results", []):
                title = item.get("title", "")
                snippet = item.get("snippet", "")
                url = item.get("link", "")
                all_mentions.append({
                    "title": title,
                    "snippet": snippet,
                    "url": url,
                })

    # Extract unique company names from mentions
    companies = _extract_companies(all_mentions)

    logger.info("Discovery: %d queries, %d mentions, %d unique companies",
                queries_run, len(all_mentions), len(companies))

    return {
        "queries_run": queries_run,
        "total_mentions": len(all_mentions),
        "companies_discovered": len(companies),
        "companies": companies,
    }


def _extract_companies(mentions: list[dict]) -> list[dict]:
    """Extract unique company names from search result mentions."""
    seen = set()
    companies = []

    for m in mentions:
        text = f"{m['title']} {m['snippet']}"
        url = m["url"]

        # Try to extract company names from common patterns
        # "CompanyName raises €XM", "CompanyName secures funding", etc.
        patterns = [
            r"(?:^|\b)([A-Z][a-zA-ZäöüÄÖÜß]+(?:\s[A-Z][a-zA-ZäöüÄÖÜß]+)?)\s+(?:raises?|secures?|closes?|announces?|gets?|receives?|sichert|erhält|schließt)",
            r"(?:startup|scale-up|scaleup|unternehmen)\s+([A-Z][a-zA-ZäöüÄÖÜß]+(?:\s[A-Z][a-zA-ZäöüÄÖÜß]+)?)",
            r"([A-Z][a-zA-ZäöüÄÖÜß]+(?:\s[A-Z][a-zA-ZäöüÄÖÜß]+)?)\s+(?:Series\s+[A-C]|Seed|funding|Finanzierung)",
        ]

        for pattern in patterns:
            for match in re.finditer(pattern, text):
                name = match.group(1).strip()
                name_lower = name.lower()

                # Skip too short, known companies, or common false positives
                if len(name) < 3:
                    continue
                if name_lower in _KNOWN_NAMES:
                    continue
                if name_lower in {"the", "our", "new", "das", "die", "der", "ein", "its",
                                  "munich", "münchen", "series", "startup", "germany",
                                  "europe", "european", "funding", "million"}:
                    continue
                if name_lower in seen:
                    continue

                seen.add(name_lower)
                companies.append({
                    "name": name,
                    "source_title": m["title"][:100],
                    "source_url": url,
                    "snippet": m["snippet"][:200],
                })

    return companies
