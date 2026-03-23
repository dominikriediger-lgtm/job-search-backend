"""Tests for the FastAPI endpoints - no external API calls."""

import pytest
from unittest.mock import patch
from fastapi.testclient import TestClient

from app.main import app
from app.services.job_store import JobStore

client = TestClient(app)


@pytest.fixture(autouse=True)
def reset_store(tmp_path):
    """Reset the job store before each test by patching the singleton."""
    fresh = JobStore(db_path=tmp_path / "test.db")
    with patch("app.services.job_store.job_store", fresh), \
         patch("app.api.routes.job_store", fresh), \
         patch("app.services.scrape_orchestrator.job_store", fresh):
        yield


class TestProfileEndpoints:
    def test_get_profile(self):
        resp = client.get("/api/v1/profile")
        assert resp.status_code == 200
        data = resp.json()
        assert "name" in data
        assert "job_titles" in data
        assert len(data["job_titles"]) > 0

    def test_get_target_titles(self):
        resp = client.get("/api/v1/profile/titles")
        assert resp.status_code == 200
        data = resp.json()
        assert "A" in data
        assert len(data["A"]) > 0


class TestJobEndpoints:
    def _add_job(self, **overrides):
        defaults = {
            "title": "Test Job",
            "company": "TestCorp",
            "location": "München",
            "description": "Test description",
            "url": "https://example.com/test",
            "source": "test",
        }
        defaults.update(overrides)
        return client.post("/api/v1/jobs", json=defaults)

    def test_add_job(self):
        resp = self._add_job()
        assert resp.status_code == 200
        data = resp.json()
        assert data["id"] is not None
        assert data["title"] == "Test Job"

    def test_add_duplicate_url_fails(self):
        self._add_job(url="https://example.com/dupe")
        resp = self._add_job(url="https://example.com/dupe")
        assert resp.status_code == 409

    def test_list_jobs_empty(self):
        resp = client.get("/api/v1/jobs")
        assert resp.status_code == 200
        assert resp.json() == []

    def test_list_jobs_after_add(self):
        self._add_job()
        resp = client.get("/api/v1/jobs")
        assert resp.status_code == 200
        assert len(resp.json()) == 1

    def test_get_job_by_id(self):
        add_resp = self._add_job()
        job_id = add_resp.json()["id"]
        resp = client.get(f"/api/v1/jobs/{job_id}")
        assert resp.status_code == 200
        assert resp.json()["id"] == job_id

    def test_get_nonexistent_job(self):
        resp = client.get("/api/v1/jobs/nonexistent")
        assert resp.status_code == 404

    def test_update_status(self):
        add_resp = self._add_job()
        job_id = add_resp.json()["id"]
        resp = client.patch(f"/api/v1/jobs/{job_id}/status?status=applied")
        assert resp.status_code == 200
        assert resp.json()["status"] == "applied"

    def test_batch_add(self):
        jobs = [
            {"title": "Job 1", "company": "A", "location": "München",
             "description": "x", "url": "https://example.com/1", "source": "test"},
            {"title": "Job 2", "company": "B", "location": "Berlin",
             "description": "y", "url": "https://example.com/2", "source": "test"},
        ]
        resp = client.post("/api/v1/jobs/batch", json=jobs)
        assert resp.status_code == 200
        assert len(resp.json()) == 2

    def test_batch_deduplicates(self):
        self._add_job(url="https://example.com/existing")
        jobs = [
            {"title": "New", "company": "A", "location": "München",
             "description": "x", "url": "https://example.com/existing", "source": "test"},
            {"title": "Also New", "company": "B", "location": "Berlin",
             "description": "y", "url": "https://example.com/fresh", "source": "test"},
        ]
        resp = client.post("/api/v1/jobs/batch", json=jobs)
        assert resp.status_code == 200
        assert len(resp.json()) == 1  # only the fresh one


class TestScoringEndpoints:
    def test_score_single_job(self):
        job = {
            "title": "Revenue Operations Manager",
            "company": "TestCorp",
            "location": "München",
            "description": "SaaS platform",
            "url": "https://example.com/test",
            "source": "test",
        }
        resp = client.post("/api/v1/jobs/score", json=job)
        assert resp.status_code == 200
        data = resp.json()
        assert "total_score" in data
        assert 0 <= data["total_score"] <= 100

    def test_scored_all_empty(self):
        resp = client.get("/api/v1/jobs/scored/all")
        assert resp.status_code == 200
        assert resp.json() == []


class TestCompanyEndpoints:
    def test_list_companies(self):
        resp = client.get("/api/v1/companies")
        assert resp.status_code == 200
        data = resp.json()
        assert len(data) > 0

    def test_list_career_urls(self):
        resp = client.get("/api/v1/companies/careers")
        assert resp.status_code == 200
        data = resp.json()
        assert len(data) > 0
        assert "company" in data[0]
        assert "url" in data[0]


class TestStatsEndpoint:
    def test_stats_empty(self):
        resp = client.get("/api/v1/stats")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total_jobs"] == 0
        assert "by_status" in data

    def test_stats_after_add(self):
        client.post("/api/v1/jobs", json={
            "title": "Test", "company": "X", "location": "München",
            "description": "d", "url": "https://example.com/1", "source": "t",
        })
        resp = client.get("/api/v1/stats")
        assert resp.status_code == 200
        assert resp.json()["total_jobs"] == 1


class TestScrapersEndpoint:
    def test_list_scrapers(self):
        resp = client.get("/api/v1/scrapers")
        assert resp.status_code == 200
        data = resp.json()
        assert len(data) > 0
        for s in data:
            assert "name" in s
            assert "configured" in s


class TestSearchEndpoints:
    def test_search_queries(self):
        resp = client.get("/api/v1/search/queries")
        assert resp.status_code == 200
        data = resp.json()
        assert len(data) > 0

    def test_search_sources(self):
        resp = client.get("/api/v1/search/sources")
        assert resp.status_code == 200
        assert len(resp.json()) > 0

    def test_google_queries(self):
        resp = client.get("/api/v1/google/queries")
        assert resp.status_code == 200
        data = resp.json()
        assert len(data) > 0
