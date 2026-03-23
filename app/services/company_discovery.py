"""Discover new startups and scale-ups via funding news and press mentions.

Uses SerpAPI to search for recent funding rounds, awards, and press mentions
of startups in the München area, then extracts company names and career URLs.
"""

import logging
import re

import httpx

from app.core.config import settings
from app.data.target_companies import TARGET_COMPANIES

logger = logging.getLogger(__name__)

# Search queries to discover new companies
DISCOVERY_QUERIES = [
    # Funding rounds - German
    '"Finanzierungsrunde" "München" (startup OR scaleup) 2025..2026',
    '"Series A" OR "Series B" "München" startup 2025..2026',
    '"Millionen" "München" startup (finanzierung OR investment) 2025..2026',
    # Funding rounds - English
    '"funding round" "Munich" (startup OR "scale-up") series 2025..2026',
    '"Series A" OR "Series B" "Munich" startup 2025..2026',
    '"raises" "million" "Munich" startup 2025..2026',
    # Awards and recognition
    '"Munich" startup award 2025..2026 winner',
    '"München" startup (auszeichnung OR preis) 2025..2026',
    # Specific ecosystems / news sites
    'site:eu-startups.com Munich 2025..2026',
    'site:tech.eu Munich funding 2025..2026',
    'site:gruenderszene.de München funding 2025..2026',
    'site:deutsche-startups.de München 2025..2026',
    'site:t3n.de München startup 2025..2026',
    # Scale-ups hiring signals
    '"Munich" OR "München" scale-up hiring 2025..2026 (operations OR "chief of staff")',
]

# Known target company names (lowercase) to avoid duplicates
_KNOWN_NAMES = {c["name"].lower() for c in TARGET_COMPANIES}

# Common false positives to ignore
_STOP_WORDS = {
    "the", "our", "new", "das", "die", "der", "ein", "its", "for", "and", "mit",
    "munich", "münchen", "series", "startup", "germany", "deutschland",
    "europe", "european", "funding", "million", "millionen", "billion",
    "raising", "raises", "round", "investment", "investor", "venture",
    "capital", "award", "awards", "finalist", "winner", "best",
    "company", "companies", "tech", "digital", "growth", "market",
}


async def discover_companies(max_queries: int = 4) -> dict:
    """Search news for recently funded/awarded startups near München.

    Returns a list of discovered company mentions with source URLs.
    Uses SerpAPI; skips if no key is configured.
    """
    api_key = settings.serpapi_key
    if not api_key:
        return {"error": "SERPAPI_KEY not configured — add it to .env", "companies": []}

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
        "hint": "Review these companies and add promising ones via POST /api/v1/companies/add",
    }


def _extract_companies(mentions: list[dict]) -> list[dict]:
    """Extract unique company names from search result mentions."""
    seen: set[str] = set()
    companies: list[dict] = []

    for m in mentions:
        text = f"{m['title']} {m['snippet']}"
        url = m["url"]

        # Try to extract company names from common patterns
        patterns = [
            # "CompanyName raises €XM", "CompanyName secures funding"
            r"(?:^|\b)([A-Z][a-zA-ZäöüÄÖÜß0-9]+(?:\s[A-Z][a-zA-ZäöüÄÖÜß0-9]+){0,2})\s+(?:raises?|secures?|closes?|announces?|gets?|receives?|sichert|erhält|schließt|sammelt)",
            # "startup CompanyName"
            r"(?:startup|scale-?up|unternehmen|firma)\s+([A-Z][a-zA-ZäöüÄÖÜß0-9]+(?:\s[A-Z][a-zA-ZäöüÄÖÜß0-9]+){0,1})",
            # "CompanyName Series A/B/C"
            r"([A-Z][a-zA-ZäöüÄÖÜß0-9]+(?:\s[A-Z][a-zA-ZäöüÄÖÜß0-9]+){0,1})\s+(?:Series\s+[A-C]|Seed|funding|Finanzierung)",
            # "CompanyName, a Munich-based..."
            r"([A-Z][a-zA-ZäöüÄÖÜß0-9]+(?:\s[A-Z][a-zA-ZäöüÄÖÜß0-9]+){0,1}),?\s+(?:a |ein |das |die )?(?:Munich|München|Münchner)",
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
                if name_lower in _STOP_WORDS:
                    continue
                if name_lower in seen:
                    continue
                # Skip if it's all common English/German words
                if all(w.lower() in _STOP_WORDS for w in name.split()):
                    continue

                seen.add(name_lower)
                companies.append({
                    "name": name,
                    "source_title": m["title"][:120],
                    "source_url": url,
                    "snippet": m["snippet"][:250],
                })

    return companies


# ----- Runtime company management -----
# Companies discovered at runtime that get added to the crawl list
_runtime_companies: list[dict] = []


def add_runtime_company(company: dict) -> dict:
    """Add a discovered company to the runtime list for crawling.

    Expected fields: name, sector, careers_url
    Optional: ats, size_estimate, funding_eur, why
    """
    name = company.get("name", "").strip()
    if not name:
        return {"error": "Company name is required"}

    # Check for duplicates in both static and runtime lists
    all_names = {c["name"].lower() for c in TARGET_COMPANIES} | {c["name"].lower() for c in _runtime_companies}
    if name.lower() in all_names:
        return {"error": f"'{name}' already exists"}

    entry = {
        "name": name,
        "sector": company.get("sector", "unknown"),
        "careers_url": company.get("careers_url", ""),
        "ats": company.get("ats"),
        "size_estimate": company.get("size_estimate", 0),
        "funding_eur": company.get("funding_eur", 0),
        "why": company.get("why", "Discovered via news/press"),
    }
    _runtime_companies.append(entry)
    logger.info("Added runtime company: %s (%s)", name, entry["careers_url"])
    return {"added": entry}


def get_all_companies() -> list[dict]:
    """Return both static TARGET_COMPANIES and runtime-added companies."""
    return TARGET_COMPANIES + _runtime_companies
