"""Tests for ATS API scrapers - using mocked HTTP responses."""

import pytest
from unittest.mock import AsyncMock, patch, MagicMock

from app.services.scrapers.ats_apis import (
    scrape_greenhouse,
    scrape_lever,
    scrape_ashby,
    scrape_personio_xml,
    scrape_smartrecruiters,
    _detect_work_mode,
    _xml_tag,
)
from app.models.schemas import WorkMode


# --- Work mode detection ---

class TestDetectWorkMode:
    def test_remote(self):
        assert _detect_work_mode("Remote - Worldwide") == WorkMode.REMOTE

    def test_hybrid(self):
        assert _detect_work_mode("Munich (Hybrid)") == WorkMode.HYBRID

    def test_onsite(self):
        assert _detect_work_mode("On-site in Munich") == WorkMode.ONSITE

    def test_onsite_german(self):
        assert _detect_work_mode("Vor Ort, München") == WorkMode.ONSITE

    def test_none(self):
        assert _detect_work_mode("Munich, Germany") is None


# --- XML tag extraction ---

class TestXmlTag:
    def test_simple_tag(self):
        assert _xml_tag("<name>Test Job</name>", "name") == "Test Job"

    def test_missing_tag(self):
        assert _xml_tag("<name>Test</name>", "other") == ""

    def test_multiline(self):
        xml = "<description>\n  Some text\n</description>"
        assert _xml_tag(xml, "description") == "Some text"


# --- Mocked ATS scrapers ---

def _mock_response(json_data=None, text="", status_code=200):
    resp = MagicMock()
    resp.status_code = status_code
    resp.json.return_value = json_data or {}
    resp.text = text
    resp.raise_for_status = MagicMock()
    if status_code >= 400:
        from httpx import HTTPStatusError, Request, Response
        resp.raise_for_status.side_effect = HTTPStatusError(
            "error", request=MagicMock(), response=resp
        )
    return resp


@pytest.mark.asyncio
class TestGreenhouseScraper:
    async def test_parses_jobs(self):
        mock_data = {
            "jobs": [
                {
                    "title": "Revenue Operations Manager",
                    "location": {"name": "Munich, Germany"},
                    "content": "Build our RevOps function in a hybrid SaaS environment",
                    "absolute_url": "https://boards.greenhouse.io/test/jobs/123",
                },
                {
                    "title": "Senior Engineer",
                    "location": {"name": "Remote"},
                    "content": "Build stuff",
                    "absolute_url": "https://boards.greenhouse.io/test/jobs/456",
                },
            ]
        }
        with patch("app.services.scrapers.ats_apis.httpx.AsyncClient") as mock_client:
            mock_instance = AsyncMock()
            mock_client.return_value.__aenter__ = AsyncMock(return_value=mock_instance)
            mock_client.return_value.__aexit__ = AsyncMock(return_value=False)
            mock_instance.get.return_value = _mock_response(json_data=mock_data)

            jobs = await scrape_greenhouse("test-board", "TestCorp")
            assert len(jobs) == 2
            assert jobs[0].title == "Revenue Operations Manager"
            assert jobs[0].company == "TestCorp"
            assert jobs[0].source == "greenhouse_api"
            assert jobs[1].work_mode == WorkMode.REMOTE

    async def test_handles_api_error(self):
        with patch("app.services.scrapers.ats_apis.httpx.AsyncClient") as mock_client:
            mock_instance = AsyncMock()
            mock_client.return_value.__aenter__ = AsyncMock(return_value=mock_instance)
            mock_client.return_value.__aexit__ = AsyncMock(return_value=False)
            mock_instance.get.return_value = _mock_response(status_code=500)

            jobs = await scrape_greenhouse("bad-board", "TestCorp")
            assert jobs == []


@pytest.mark.asyncio
class TestLeverScraper:
    async def test_parses_jobs(self):
        mock_data = [
            {
                "text": "Chief of Staff",
                "categories": {
                    "location": "Munich",
                    "commitment": "Full-time",
                },
                "descriptionPlain": "Work directly with the CEO on strategy and cross-functional leadership",
                "hostedUrl": "https://jobs.lever.co/test/123",
            },
        ]
        with patch("app.services.scrapers.ats_apis.httpx.AsyncClient") as mock_client:
            mock_instance = AsyncMock()
            mock_client.return_value.__aenter__ = AsyncMock(return_value=mock_instance)
            mock_client.return_value.__aexit__ = AsyncMock(return_value=False)
            mock_instance.get.return_value = _mock_response(json_data=mock_data)

            jobs = await scrape_lever("test-board", "TestCorp")
            assert len(jobs) == 1
            assert jobs[0].title == "Chief of Staff"
            assert jobs[0].source == "lever_api"


@pytest.mark.asyncio
class TestAshbyScraper:
    async def test_parses_jobs(self):
        mock_data = {
            "jobs": [
                {
                    "title": "GTM Operations Manager",
                    "location": "Munich (Hybrid)",
                    "descriptionPlain": "Own our GTM operations stack",
                    "jobUrl": "https://jobs.ashbyhq.com/test/123",
                },
            ]
        }
        with patch("app.services.scrapers.ats_apis.httpx.AsyncClient") as mock_client:
            mock_instance = AsyncMock()
            mock_client.return_value.__aenter__ = AsyncMock(return_value=mock_instance)
            mock_client.return_value.__aexit__ = AsyncMock(return_value=False)
            mock_instance.get.return_value = _mock_response(json_data=mock_data)

            jobs = await scrape_ashby("test-board", "TestCorp")
            assert len(jobs) == 1
            assert jobs[0].title == "GTM Operations Manager"
            assert jobs[0].work_mode == WorkMode.HYBRID

    async def test_location_as_dict(self):
        """Ashby sometimes returns location as a dict."""
        mock_data = {
            "jobs": [
                {
                    "title": "Test",
                    "location": {"name": "Berlin"},
                    "description": "Test",
                    "jobUrl": "https://example.com",
                },
            ]
        }
        with patch("app.services.scrapers.ats_apis.httpx.AsyncClient") as mock_client:
            mock_instance = AsyncMock()
            mock_client.return_value.__aenter__ = AsyncMock(return_value=mock_instance)
            mock_client.return_value.__aexit__ = AsyncMock(return_value=False)
            mock_instance.get.return_value = _mock_response(json_data=mock_data)

            jobs = await scrape_ashby("test-board", "TestCorp")
            assert jobs[0].location == "Berlin"


@pytest.mark.asyncio
class TestPersonioScraper:
    async def test_parses_xml(self):
        xml = """<?xml version="1.0"?>
        <workzag-jobs>
            <position>
                <id>12345</id>
                <name>Operations Manager</name>
                <office>Munich</office>
                <department>Operations</department>
            </position>
            <position>
                <id>67890</id>
                <name>Software Engineer</name>
                <office>Berlin</office>
                <department>Engineering</department>
            </position>
        </workzag-jobs>"""
        with patch("app.services.scrapers.ats_apis.httpx.AsyncClient") as mock_client:
            mock_instance = AsyncMock()
            mock_client.return_value.__aenter__ = AsyncMock(return_value=mock_instance)
            mock_client.return_value.__aexit__ = AsyncMock(return_value=False)
            mock_instance.get.return_value = _mock_response(text=xml)

            jobs = await scrape_personio_xml("test-company", "TestCorp")
            assert len(jobs) == 2
            assert jobs[0].title == "Operations Manager"
            assert jobs[0].source == "personio_api"
            assert "12345" in jobs[0].url


@pytest.mark.asyncio
class TestSmartRecruitersScraper:
    async def test_parses_jobs(self):
        mock_data = {
            "content": [
                {
                    "name": "Strategy Manager",
                    "location": {"city": "Munich", "country": "DE"},
                    "ref": "https://api.smartrecruiters.com/test/123",
                },
            ]
        }
        with patch("app.services.scrapers.ats_apis.httpx.AsyncClient") as mock_client:
            mock_instance = AsyncMock()
            mock_client.return_value.__aenter__ = AsyncMock(return_value=mock_instance)
            mock_client.return_value.__aexit__ = AsyncMock(return_value=False)
            mock_instance.get.return_value = _mock_response(json_data=mock_data)

            jobs = await scrape_smartrecruiters("test-board", "TestCorp")
            assert len(jobs) == 1
            assert jobs[0].title == "Strategy Manager"
            assert "Munich" in jobs[0].location
