"""Tests for the in-memory job store."""

import pytest

from app.models.schemas import JobListing, JobStatus, WorkMode
from app.services.job_store import JobStore


@pytest.fixture
def store():
    """Fresh store for each test."""
    return JobStore()


def _make_job(title="Test Job", url="https://example.com/1", **kw) -> JobListing:
    defaults = {
        "title": title,
        "company": "TestCorp",
        "location": "München",
        "description": "Test",
        "url": url,
        "source": "test",
    }
    defaults.update(kw)
    return JobListing(**defaults)


class TestJobStore:
    def test_add_assigns_id(self, store):
        job = _make_job()
        result = store.add(job)
        assert result.id is not None
        assert len(result.id) > 0

    def test_add_assigns_discovered_at(self, store):
        job = _make_job()
        result = store.add(job)
        assert result.discovered_at is not None

    def test_get_by_id(self, store):
        job = store.add(_make_job())
        fetched = store.get(job.id)
        assert fetched is not None
        assert fetched.title == "Test Job"

    def test_get_nonexistent(self, store):
        assert store.get("nonexistent") is None

    def test_count(self, store):
        assert store.count() == 0
        store.add(_make_job(url="https://example.com/1"))
        store.add(_make_job(url="https://example.com/2"))
        assert store.count() == 2

    def test_exists_by_url(self, store):
        store.add(_make_job(url="https://example.com/test"))
        assert store.exists_by_url("https://example.com/test") is True
        assert store.exists_by_url("https://example.com/other") is False

    def test_add_many(self, store):
        jobs = [
            _make_job(url="https://example.com/1"),
            _make_job(url="https://example.com/2"),
            _make_job(url="https://example.com/3"),
        ]
        results = store.add_many(jobs)
        assert len(results) == 3
        assert store.count() == 3
        assert all(j.id is not None for j in results)

    def test_get_all_sorted_by_discovered_at(self, store):
        store.add(_make_job(title="First", url="https://example.com/1"))
        store.add(_make_job(title="Second", url="https://example.com/2"))
        all_jobs = store.get_all()
        assert len(all_jobs) == 2
        # Most recent first
        assert all_jobs[0].discovered_at >= all_jobs[1].discovered_at

    def test_get_all_filter_by_status(self, store):
        j1 = store.add(_make_job(url="https://example.com/1"))
        j2 = store.add(_make_job(url="https://example.com/2"))
        store.update_status(j1.id, JobStatus.APPLIED)

        applied = store.get_all(status=JobStatus.APPLIED)
        assert len(applied) == 1
        assert applied[0].id == j1.id

        new = store.get_all(status=JobStatus.NEW)
        assert len(new) == 1
        assert new[0].id == j2.id

    def test_update_status(self, store):
        job = store.add(_make_job())
        assert job.status == JobStatus.NEW
        updated = store.update_status(job.id, JobStatus.INTERVIEW)
        assert updated.status == JobStatus.INTERVIEW

    def test_update_status_nonexistent(self, store):
        result = store.update_status("nonexistent", JobStatus.APPLIED)
        assert result is None
