"""ATS (Applicant Tracking System) API scrapers.

Greenhouse, Lever, and Ashby all expose free, public JSON APIs
for their job boards. No API key required.
"""

import asyncio
import logging
import re

import httpx

from app.models.schemas import JobListing, WorkMode

logger = logging.getLogger(__name__)

# Use a realistic browser User-Agent — some APIs/CDNs block bot-like agents
HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/131.0.0.0 Safari/537.36"
    ),
    "Accept": "application/json, text/html, application/xml, */*",
    "Accept-Language": "de-DE,de;q=0.9,en-US;q=0.8,en;q=0.7",
}

# Default timeout (seconds) — some boards are slow
_TIMEOUT = 25.0

# Max retries for transient errors (502, 503, 429)
_MAX_RETRIES = 2


def _detect_work_mode(text: str) -> WorkMode | None:
    t = text.lower()
    if "remote" in t:
        return WorkMode.REMOTE
    if "hybrid" in t:
        return WorkMode.HYBRID
    if "on-site" in t or "onsite" in t or "vor ort" in t:
        return WorkMode.ONSITE
    return None


async def _get_with_retry(client: httpx.AsyncClient, url: str) -> httpx.Response:
    """GET with retry on transient errors (429, 502, 503)."""
    last_exc = None
    for attempt in range(_MAX_RETRIES + 1):
        try:
            resp = await client.get(url)
            if resp.status_code in (429, 502, 503) and attempt < _MAX_RETRIES:
                wait = 2 ** attempt
                logger.info("Retrying %s in %ds (status %d)", url[:80], wait, resp.status_code)
                await asyncio.sleep(wait)
                continue
            return resp
        except (httpx.ConnectError, httpx.ReadTimeout, httpx.ConnectTimeout) as exc:
            last_exc = exc
            if attempt < _MAX_RETRIES:
                wait = 2 ** attempt
                logger.info("Retrying %s in %ds (%s)", url[:80], wait, type(exc).__name__)
                await asyncio.sleep(wait)
    raise last_exc  # type: ignore[misc]


async def scrape_greenhouse(board_slug: str, company_name: str, eu: bool = False) -> list[JobListing]:
    """Fetch jobs from Greenhouse boards API.

    API: https://boards-api.greenhouse.io/v1/boards/{slug}/jobs
    EU companies use: https://boards-api.eu.greenhouse.io/v1/boards/{slug}/jobs

    Automatically tries the alternate endpoint if the primary returns 404.
    """
    host = "boards-api.eu.greenhouse.io" if eu else "boards-api.greenhouse.io"
    url = f"https://{host}/v1/boards/{board_slug}/jobs?content=true"
    async with httpx.AsyncClient(timeout=_TIMEOUT, headers=HEADERS, follow_redirects=True) as client:
        try:
            resp = await _get_with_retry(client, url)
            # If primary fails with 404, try alternate endpoint
            if resp.status_code == 404:
                alt_host = "boards-api.greenhouse.io" if eu else "boards-api.eu.greenhouse.io"
                alt_url = f"https://{alt_host}/v1/boards/{board_slug}/jobs?content=true"
                resp = await _get_with_retry(client, alt_url)
            resp.raise_for_status()
        except httpx.HTTPError as exc:
            logger.warning("Greenhouse API failed for %s (slug=%s): %s", company_name, board_slug, exc)
            return []

    data = resp.json()
    jobs = []
    for j in data.get("jobs", []):
        location = j.get("location", {}).get("name", "See posting")
        desc = j.get("content", "")[:2000]
        job_url = j.get("absolute_url", "")
        jobs.append(JobListing(
            title=j.get("title", ""),
            company=company_name,
            location=location,
            work_mode=_detect_work_mode(f"{location} {desc}"),
            description=desc,
            url=job_url,
            source="greenhouse_api",
        ))
    logger.info("Greenhouse %s: %d jobs found", company_name, len(jobs))
    return jobs


async def scrape_lever(board_slug: str, company_name: str, eu: bool = False) -> list[JobListing]:
    """Fetch jobs from Lever postings API.

    API: https://api.lever.co/v0/postings/{slug}
    EU:  https://api.eu.lever.co/v0/postings/{slug}
    """
    host = "api.eu.lever.co" if eu else "api.lever.co"
    url = f"https://{host}/v0/postings/{board_slug}?mode=json"
    async with httpx.AsyncClient(timeout=_TIMEOUT, headers=HEADERS, follow_redirects=True) as client:
        try:
            resp = await _get_with_retry(client, url)
            # Try alternate region on 404
            if resp.status_code == 404:
                alt_host = "api.lever.co" if eu else "api.eu.lever.co"
                resp = await _get_with_retry(client, f"https://{alt_host}/v0/postings/{board_slug}?mode=json")
            resp.raise_for_status()
        except httpx.HTTPError as exc:
            logger.warning("Lever API failed for %s (slug=%s): %s", company_name, board_slug, exc)
            return []

    data = resp.json()
    jobs = []
    for j in data if isinstance(data, list) else []:
        categories = j.get("categories", {})
        location = categories.get("location", "See posting")
        commitment = categories.get("commitment", "")
        desc = j.get("descriptionPlain", "")[:2000]
        job_url = j.get("hostedUrl", "")
        jobs.append(JobListing(
            title=j.get("text", ""),
            company=company_name,
            location=location,
            work_mode=_detect_work_mode(f"{location} {commitment}"),
            description=desc,
            url=job_url,
            source="lever_api",
        ))
    logger.info("Lever %s: %d jobs found", company_name, len(jobs))
    return jobs


async def scrape_ashby(board_slug: str, company_name: str) -> list[JobListing]:
    """Fetch jobs from Ashby job board API.

    API: https://api.ashbyhq.com/posting-api/job-board/{slug}
    """
    url = f"https://api.ashbyhq.com/posting-api/job-board/{board_slug}"
    async with httpx.AsyncClient(timeout=_TIMEOUT, headers=HEADERS, follow_redirects=True) as client:
        try:
            resp = await _get_with_retry(client, url)
            resp.raise_for_status()
        except httpx.HTTPError as exc:
            logger.warning("Ashby API failed for %s (slug=%s): %s", company_name, board_slug, exc)
            return []

    data = resp.json()
    jobs = []
    for j in data.get("jobs", []):
        location = j.get("location", "See posting")
        if isinstance(location, dict):
            location = location.get("name", "See posting")
        desc = j.get("descriptionPlain", j.get("description", ""))[:2000]
        job_url = j.get("jobUrl", j.get("hostedUrl", ""))
        jobs.append(JobListing(
            title=j.get("title", ""),
            company=company_name,
            location=location,
            work_mode=_detect_work_mode(f"{location} {desc}"),
            description=desc,
            url=job_url,
            source="ashby_api",
        ))
    logger.info("Ashby %s: %d jobs found", company_name, len(jobs))
    return jobs


async def scrape_personio_xml(board_slug: str, company_name: str) -> list[JobListing]:
    """Fetch jobs from Personio job board XML feed.

    URL pattern: https://{slug}.jobs.personio.de/xml
    """
    url = f"https://{board_slug}.jobs.personio.de/xml"
    async with httpx.AsyncClient(timeout=_TIMEOUT, headers=HEADERS, follow_redirects=True) as client:
        try:
            resp = await _get_with_retry(client, url)
            resp.raise_for_status()
        except httpx.HTTPError as exc:
            logger.warning("Personio API failed for %s (slug=%s): %s", company_name, board_slug, exc)
            return []

    jobs = []
    # Extract position blocks
    positions = re.findall(r"<position>(.*?)</position>", resp.text, re.DOTALL)
    for pos in positions:
        title = _xml_tag(pos, "name")
        location = _xml_tag(pos, "office")
        department = _xml_tag(pos, "department")
        job_id = _xml_tag(pos, "id")
        job_url = f"https://{board_slug}.jobs.personio.de/job/{job_id}" if job_id else ""

        if title:
            jobs.append(JobListing(
                title=title,
                company=company_name,
                location=location or "See posting",
                work_mode=_detect_work_mode(f"{location} {department}"),
                description=f"Department: {department}" if department else "",
                url=job_url,
                source="personio_api",
            ))
    logger.info("Personio %s: %d jobs found", company_name, len(jobs))
    return jobs


async def scrape_smartrecruiters(board_slug: str, company_name: str) -> list[JobListing]:
    """Fetch jobs from SmartRecruiters API.

    API: https://api.smartrecruiters.com/v1/companies/{slug}/postings
    """
    url = f"https://api.smartrecruiters.com/v1/companies/{board_slug}/postings"
    async with httpx.AsyncClient(timeout=_TIMEOUT, headers=HEADERS, follow_redirects=True) as client:
        try:
            resp = await _get_with_retry(client, url)
            resp.raise_for_status()
        except httpx.HTTPError as exc:
            logger.warning("SmartRecruiters API failed for %s (slug=%s): %s", company_name, board_slug, exc)
            return []

    data = resp.json()
    jobs = []
    for j in data.get("content", []):
        location = j.get("location", {})
        loc_str = location.get("city", "") or location.get("name", "See posting")
        country = location.get("country", "")
        if country:
            loc_str = f"{loc_str}, {country}"
        desc = j.get("name", "")
        job_url = j.get("ref", j.get("applyUrl", ""))

        jobs.append(JobListing(
            title=j.get("name", ""),
            company=company_name,
            location=loc_str,
            work_mode=_detect_work_mode(loc_str),
            description="",
            url=job_url,
            source="smartrecruiters_api",
        ))
    logger.info("SmartRecruiters %s: %d jobs found", company_name, len(jobs))
    return jobs


def _xml_tag(xml: str, tag: str) -> str:
    """Extract text from a simple XML tag."""
    match = re.search(rf"<{tag}>(.*?)</{tag}>", xml, re.DOTALL)
    return match.group(1).strip() if match else ""
