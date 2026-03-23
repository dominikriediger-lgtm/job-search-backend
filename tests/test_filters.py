"""Tests for location and seniority filters in scrape_orchestrator."""

from app.models.schemas import JobListing, WorkMode
from app.services.scrape_orchestrator import _is_location_relevant, _is_seniority_relevant, _is_job_relevant


def _make_job(title="Test", location="München", work_mode=None, description="Test desc") -> JobListing:
    return JobListing(
        title=title,
        company="TestCorp",
        location=location,
        work_mode=work_mode,
        description=description,
        url="https://example.com/test",
        source="test",
    )


class TestLocationFilter:
    def test_munich_is_relevant(self):
        assert _is_location_relevant(_make_job(location="München")) is True

    def test_munich_english_is_relevant(self):
        assert _is_location_relevant(_make_job(location="Munich, Germany")) is True

    def test_remote_always_relevant(self):
        assert _is_location_relevant(_make_job(location="Anywhere", work_mode=WorkMode.REMOTE)) is True

    def test_remote_in_location_string(self):
        assert _is_location_relevant(_make_job(location="Remote - Germany")) is True

    def test_berlin_is_relevant(self):
        assert _is_location_relevant(_make_job(location="Berlin")) is True

    def test_san_francisco_not_relevant(self):
        assert _is_location_relevant(_make_job(location="San Francisco, CA")) is False

    def test_new_york_not_relevant(self):
        assert _is_location_relevant(_make_job(location="New York")) is False

    def test_london_not_relevant(self):
        assert _is_location_relevant(_make_job(location="London, UK")) is False

    def test_unknown_location_kept(self):
        """Unknown locations are kept (might be relevant)."""
        assert _is_location_relevant(_make_job(location="Unknown City")) is True

    def test_augsburg_is_relevant(self):
        assert _is_location_relevant(_make_job(location="Augsburg")) is True

    def test_empty_location_kept(self):
        assert _is_location_relevant(_make_job(location="")) is True


class TestSeniorityFilter:
    def test_senior_kept(self):
        assert _is_seniority_relevant(_make_job(title="Senior Operations Manager")) is True

    def test_junior_filtered(self):
        assert _is_seniority_relevant(_make_job(title="Junior Analyst")) is False

    def test_intern_filtered(self):
        assert _is_seniority_relevant(_make_job(title="Intern - Business Development")) is False

    def test_werkstudent_filtered(self):
        assert _is_seniority_relevant(_make_job(title="Werkstudent Operations")) is False

    def test_trainee_filtered(self):
        assert _is_seniority_relevant(_make_job(title="Trainee Program")) is False

    def test_senior_manager_with_intern_desc(self):
        """Senior title should override junior keywords in description."""
        job = _make_job(title="Senior Manager", description="You will supervise interns and working students")
        assert _is_seniority_relevant(job) is True

    def test_normal_title_kept(self):
        assert _is_seniority_relevant(_make_job(title="Revenue Operations Manager")) is True

    def test_head_of_kept(self):
        assert _is_seniority_relevant(_make_job(title="Head of Operations")) is True


class TestCombinedFilter:
    def test_munich_senior_passes(self):
        job = _make_job(title="Senior Manager", location="München")
        assert _is_job_relevant(job) is True

    def test_sf_junior_fails(self):
        job = _make_job(title="Junior Analyst", location="San Francisco")
        assert _is_job_relevant(job) is False

    def test_remote_intern_fails(self):
        """Even remote, interns should be filtered."""
        job = _make_job(title="Intern", location="Remote", work_mode=WorkMode.REMOTE)
        assert _is_job_relevant(job) is False

    def test_munich_intern_fails(self):
        job = _make_job(title="Praktikum Operations", location="München")
        assert _is_job_relevant(job) is False
