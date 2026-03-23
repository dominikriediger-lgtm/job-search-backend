"""ATS (Applicant Tracking System) API scrapers.

Greenhouse, Lever, and Ashby all expose free, public JSON APIs
for their job boards. No API key required.
"""

import httpx

from app.models.schemas import JobListing, WorkMode

HEADERS = {
    "User-Agent": "Mozilla/5.0 (compatible; JobSearchAgent/1.0)",
    "Accept": "application/json",
}


def _detect_work_mode(text: str) -> WorkMode | None:
    t = text.lower()
    if "remote" in t:
        return WorkMode.REMOTE
    if "hybrid" in t:
        return WorkMode.HYBRID
    if "on-site" in t or "onsite" in t or "vor ort" in t:
        return WorkMode.ONSITE
    return None


async def scrape_greenhouse(board_slug: str, company_name: str, eu: bool = False) -> list[JobListing]:
    """Fetch jobs from Greenhouse boards API.

    API: https://boards-api.greenhouse.io/v1/boards/{slug}/jobs
    EU companies use: https://boards-api.eu.greenhouse.io/v1/boards/{slug}/jobs
    """
    host = "boards-api.eu.greenhouse.io" if eu else "boards-api.greenhouse.io"
    url = f"https://{host}/v1/boards/{board_slug}/jobs?content=true"
    async with httpx.AsyncClient(timeout=15.0, headers=HEADERS) as client:
        try:
            resp = await client.get(url)
            # If non-EU fails, try EU endpoint (and vice versa)
            if resp.status_code == 404:
                alt_host = "boards-api.greenhouse.io" if eu else "boards-api.eu.greenhouse.io"
                resp = await client.get(f"https://{alt_host}/v1/boards/{board_slug}/jobs?content=true")
            resp.raise_for_status()
        except httpx.HTTPError:
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
    return jobs


async def scrape_lever(company_slug: str, company_name: str) -> list[JobListing]:
    """Fetch jobs from Lever postings API.

    API: https://api.lever.co/v0/postings/{slug}
    """
    url = f"https://api.lever.co/v0/postings/{company_slug}?mode=json"
    async with httpx.AsyncClient(timeout=15.0, headers=HEADERS) as client:
        try:
            resp = await client.get(url)
            resp.raise_for_status()
        except httpx.HTTPError:
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
    return jobs


async def scrape_ashby(board_slug: str, company_name: str) -> list[JobListing]:
    """Fetch jobs from Ashby job board API.

    API: https://api.ashbyhq.com/posting-api/job-board/{slug}
    """
    url = f"https://api.ashbyhq.com/posting-api/job-board/{board_slug}"
    async with httpx.AsyncClient(timeout=15.0, headers=HEADERS) as client:
        try:
            resp = await client.get(url)
            resp.raise_for_status()
        except httpx.HTTPError:
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
    return jobs


async def scrape_personio_xml(company_slug: str, company_name: str) -> list[JobListing]:
    """Fetch jobs from Personio job board XML feed.

    URL pattern: https://{slug}.jobs.personio.de/xml
    """
    url = f"https://{company_slug}.jobs.personio.de/xml"
    async with httpx.AsyncClient(timeout=15.0, headers=HEADERS) as client:
        try:
            resp = await client.get(url)
            resp.raise_for_status()
        except httpx.HTTPError:
            return []

    # Parse simple XML without lxml dependency
    import re
    jobs = []
    # Extract position blocks
    positions = re.findall(r"<position>(.*?)</position>", resp.text, re.DOTALL)
    for pos in positions:
        title = _xml_tag(pos, "name")
        location = _xml_tag(pos, "office")
        department = _xml_tag(pos, "department")
        job_id = _xml_tag(pos, "id")
        job_url = f"https://{company_slug}.jobs.personio.de/job/{job_id}" if job_id else ""

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
    return jobs


async def scrape_smartrecruiters(company_slug: str, company_name: str) -> list[JobListing]:
    """Fetch jobs from SmartRecruiters API.

    API: https://api.smartrecruiters.com/v1/companies/{slug}/postings
    """
    url = f"https://api.smartrecruiters.com/v1/companies/{company_slug}/postings"
    async with httpx.AsyncClient(timeout=15.0, headers=HEADERS) as client:
        try:
            resp = await client.get(url)
            resp.raise_for_status()
        except httpx.HTTPError:
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
    return jobs


def _xml_tag(xml: str, tag: str) -> str:
    """Extract text from a simple XML tag."""
    import re
    match = re.search(rf"<{tag}>(.*?)</{tag}>", xml, re.DOTALL)
    return match.group(1).strip() if match else ""
