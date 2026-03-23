"""Tests for seed data integrity - target companies and profile."""

import re

import pytest

from app.data.profile_seed import CANDIDATE_PROFILE, JOB_TITLES, COMPANY_FILTER
from app.data.target_companies import TARGET_COMPANIES, get_career_urls
from app.models.schemas import ClusterPriority


class TestTargetCompanies:
    def test_all_have_required_fields(self):
        for i, c in enumerate(TARGET_COMPANIES):
            assert "name" in c, f"Company #{i} missing name"
            assert "sector" in c, f"Company {c.get('name', i)} missing sector"
            assert "careers_url" in c, f"Company {c.get('name', i)} missing careers_url"
            assert "size_estimate" in c, f"Company {c.get('name', i)} missing size_estimate"
            assert "why" in c, f"Company {c.get('name', i)} missing why"

    def test_no_duplicate_names(self):
        names = [c["name"] for c in TARGET_COMPANIES]
        dupes = [n for n in names if names.count(n) > 1]
        assert len(dupes) == 0, f"Duplicate company names: {set(dupes)}"

    def test_no_duplicate_urls(self):
        urls = [c["careers_url"] for c in TARGET_COMPANIES]
        dupes = [u for u in urls if urls.count(u) > 1]
        assert len(dupes) == 0, f"Duplicate career URLs: {set(dupes)}"

    def test_careers_urls_are_valid(self):
        url_pattern = re.compile(r"^https?://")
        for c in TARGET_COMPANIES:
            assert url_pattern.match(c["careers_url"]), \
                f"{c['name']}: invalid URL '{c['careers_url']}'"

    def test_ats_structure_valid(self):
        valid_platforms = {"greenhouse", "lever", "ashby", "personio", "smartrecruiters"}
        for c in TARGET_COMPANIES:
            ats = c.get("ats")
            if ats is None:
                continue
            assert "platform" in ats, f"{c['name']}: ATS missing platform"
            assert "slug" in ats, f"{c['name']}: ATS missing slug"
            assert ats["platform"] in valid_platforms, \
                f"{c['name']}: unknown ATS platform '{ats['platform']}'"

    def test_size_estimates_reasonable(self):
        for c in TARGET_COMPANIES:
            size = c["size_estimate"]
            assert 1 <= size <= 100_000, \
                f"{c['name']}: unreasonable size {size}"

    def test_at_least_50_companies(self):
        assert len(TARGET_COMPANIES) >= 50, \
            f"Expected 50+ companies, got {len(TARGET_COMPANIES)}"

    def test_get_career_urls(self):
        urls = get_career_urls()
        assert len(urls) == len(TARGET_COMPANIES)
        for u in urls:
            assert "company" in u
            assert "url" in u
            assert "sector" in u


class TestCandidateProfile:
    def test_has_job_titles(self):
        assert len(CANDIDATE_PROFILE.job_titles) > 0

    def test_all_clusters_represented(self):
        clusters = {jt.cluster for jt in CANDIDATE_PROFILE.job_titles}
        assert ClusterPriority.A in clusters
        assert ClusterPriority.B in clusters
        assert ClusterPriority.C in clusters

    def test_job_titles_have_keywords(self):
        for jt in CANDIDATE_PROFILE.job_titles:
            assert len(jt.keywords) > 0, f"Title '{jt.title}' has no keywords"

    def test_cluster_a_has_most_titles(self):
        a_count = sum(1 for jt in CANDIDATE_PROFILE.job_titles if jt.cluster == ClusterPriority.A)
        b_count = sum(1 for jt in CANDIDATE_PROFILE.job_titles if jt.cluster == ClusterPriority.B)
        assert a_count >= b_count, "Cluster A should have at least as many titles as B"

    def test_search_preferences_sane(self):
        prefs = CANDIDATE_PROFILE.search_preferences
        assert prefs.min_salary_eur > 0
        assert len(prefs.work_modes) > 0
        assert prefs.max_distance_km > 0

    def test_company_filter_sane(self):
        cf = CANDIDATE_PROFILE.company_filter
        assert cf.min_employees > 0
        assert cf.min_funding_eur > 0
        assert len(cf.preferred_sectors) > 0
        assert len(cf.excluded_sectors) > 0
