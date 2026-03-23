"""Tests for the scoring engine - no external API calls."""

import pytest

from app.models.schemas import ClusterPriority, JobListing, WorkMode
from app.services.scoring import (
    score_ai_resilience,
    score_company_fit,
    score_job,
    score_location,
    score_salary,
    score_seniority,
    score_tech_depth,
    score_title_match,
    score_and_rank_jobs,
)


def _make_job(**overrides) -> JobListing:
    """Helper to create test jobs with sensible defaults."""
    defaults = {
        "title": "Revenue Operations Manager",
        "company": "TestCorp",
        "location": "München",
        "work_mode": WorkMode.HYBRID,
        "description": "We are looking for a Revenue Operations Manager to join our SaaS platform team.",
        "url": "https://example.com/job/1",
        "source": "test",
    }
    defaults.update(overrides)
    return JobListing(**defaults)


# --- Title matching ---

class TestTitleMatch:
    def test_exact_cluster_a_match(self):
        job = _make_job(title="Revenue Operations Manager")
        score, cluster, title = score_title_match(job)
        assert score >= 80, f"Exact Cluster A title should score high, got {score}"
        assert cluster == ClusterPriority.A

    def test_exact_cluster_b_match(self):
        job = _make_job(title="Chief of Staff")
        score, cluster, title = score_title_match(job)
        assert score >= 60, f"Exact Cluster B title should score well, got {score}"
        assert cluster == ClusterPriority.B

    def test_keyword_match_in_title(self):
        # Keywords are multi-word phrases like "revenue operations", so use one
        job = _make_job(title="Revenue Operations Lead - Growth", description="")
        score, cluster, _ = score_title_match(job)
        assert score > 0, "Keywords in title should produce a score"

    def test_no_match_garbage_title(self):
        job = _make_job(title="Plumber", description="Fix pipes and drains")
        score, cluster, _ = score_title_match(job)
        assert score < 20, f"Unrelated title should score low, got {score}"

    def test_keyword_match_in_description_lower_than_title(self):
        job_title = _make_job(title="Revenue Operations Manager", description="")
        job_desc = _make_job(title="Generic Role", description="revenue operations automation CRM")
        score_t, _, _ = score_title_match(job_title)
        score_d, _, _ = score_title_match(job_desc)
        assert score_t > score_d, "Title match should score higher than description-only match"

    def test_score_capped_at_100(self):
        # Even with perfect match + cluster A bonus, should not exceed 100
        job = _make_job(title="Revenue Operations Manager", description="revenue operations CRM automation saas")
        score, _, _ = score_title_match(job)
        assert score <= 100

    def test_cluster_c_scores_lower_than_a(self):
        job_a = _make_job(title="Revenue Operations Manager")
        job_c = _make_job(title="Fractional RevOps Lead")
        score_a, _, _ = score_title_match(job_a)
        score_c, _, _ = score_title_match(job_c)
        assert score_a >= score_c, f"Cluster A ({score_a}) should >= Cluster C ({score_c})"


# --- Company fit ---

class TestCompanyFit:
    def test_sweet_spot_scaleup(self):
        job = _make_job(company_size=200, company_sector="saas")
        score = score_company_fit(job)
        assert score >= 70, f"SaaS scaleup (200 emp) should score high, got {score}"

    def test_too_small_unfunded(self):
        job = _make_job(company_size=5, company_funding_eur=100_000)
        score = score_company_fit(job)
        assert score < 50, f"Tiny unfunded startup should score low, got {score}"

    def test_small_but_well_funded(self):
        job = _make_job(company_size=30, company_funding_eur=50_000_000, company_sector="ai")
        score = score_company_fit(job)
        assert score >= 70, f"Small but well-funded AI company should score well, got {score}"

    def test_excluded_sector(self):
        # Excluded sectors are: "traditional-automotive", "old-fashioned-corporate", "gpt-wrapper"
        job = _make_job(company_size=200, company_sector="traditional-automotive")
        score = score_company_fit(job)
        assert score < 50, f"Excluded sector should be penalized, got {score}"

    def test_corporate_penalty(self):
        job = _make_job(company_size=10000)
        score = score_company_fit(job)
        # Large corp gets -10 instead of +25
        job_scaleup = _make_job(company_size=200)
        score_scaleup = score_company_fit(job_scaleup)
        assert score < score_scaleup, "Large corp should score lower than scaleup"

    def test_no_info_baseline(self):
        job = _make_job()
        score = score_company_fit(job)
        assert score == 50, f"No company info should return baseline 50, got {score}"


# --- Location ---

class TestLocation:
    def test_munich_hybrid(self):
        job = _make_job(location="München", work_mode=WorkMode.HYBRID)
        score = score_location(job)
        assert score >= 80, f"München + Hybrid should score very high, got {score}"

    def test_remote_anywhere(self):
        job = _make_job(location="Remote", work_mode=WorkMode.REMOTE)
        score = score_location(job)
        assert score >= 70, f"Remote should score well, got {score}"

    def test_us_location_penalized(self):
        job = _make_job(location="San Francisco, CA", work_mode=WorkMode.ONSITE)
        score = score_location(job)
        assert score < 50, f"US onsite should score low, got {score}"

    def test_germany_generic(self):
        job = _make_job(location="Germany", work_mode=None)
        score = score_location(job)
        assert score >= 50, f"Germany should be acceptable, got {score}"

    def test_munich_onsite_acceptable(self):
        job = _make_job(location="Munich", work_mode=WorkMode.ONSITE)
        score = score_location(job)
        # accept_onsite_if_excellent is True, so should get small bonus
        assert score >= 50, f"Munich onsite should be acceptable, got {score}"


# --- Tech depth ---

class TestTechDepth:
    def test_saas_platform(self):
        job = _make_job(description="Build our SaaS platform with API integrations and machine learning models")
        score = score_tech_depth(job)
        assert score >= 70, f"SaaS + ML should score high, got {score}"

    def test_gpt_wrapper(self):
        job = _make_job(description="We are a GPT wrapper building ChatGPT plugin")
        score = score_tech_depth(job)
        assert score < 40, f"GPT wrapper should score low, got {score}"

    def test_no_description(self):
        job = _make_job(description="")
        score = score_tech_depth(job)
        assert score == 50, f"No description should return baseline, got {score}"


# --- AI resilience ---

class TestAIResilience:
    def test_strategic_role(self):
        job = _make_job(
            title="Strategy & Operations Manager",
            description="Cross-functional leadership, stakeholder management, board presentations, transformation"
        )
        score = score_ai_resilience(job)
        assert score >= 70, f"Strategic role should score high, got {score}"

    def test_vulnerable_role(self):
        job = _make_job(
            title="Data Entry Clerk",
            description="Manual reporting, data entry, routine processing of invoices"
        )
        score = score_ai_resilience(job)
        assert score < 30, f"Data entry should score low, got {score}"


# --- Salary ---

class TestSalary:
    def test_above_minimum(self):
        job = _make_job(salary_min=100_000, salary_max=130_000, has_equity=True)
        score = score_salary(job)
        assert score >= 90, f"Above minimum + equity should score very high, got {score}"

    def test_below_minimum(self):
        job = _make_job(salary_max=60_000)
        score = score_salary(job)
        assert score < 50, f"Well below minimum should score low, got {score}"

    def test_close_to_minimum(self):
        job = _make_job(salary_max=90_000)  # 90% of 100k
        score = score_salary(job)
        assert score >= 50, f"Close to minimum should be acceptable, got {score}"

    def test_no_salary_info(self):
        job = _make_job()
        score = score_salary(job)
        assert score == 50, f"No salary info should return baseline, got {score}"

    def test_equity_bonus(self):
        job_no_equity = _make_job(salary_max=100_000)
        job_equity = _make_job(salary_max=100_000, has_equity=True)
        score_no = score_salary(job_no_equity)
        score_eq = score_salary(job_equity)
        assert score_eq > score_no, "Equity should provide a bonus"


# --- Seniority ---

class TestSeniority:
    def test_junior_penalized(self):
        job = _make_job(title="Junior Business Analyst", description="Entry level position")
        score, note = score_seniority(job)
        assert score <= 20, f"Junior should be heavily penalized, got {score}"
        assert "junior" in note.lower() or "intern" in note.lower()

    def test_senior_bonus(self):
        job = _make_job(title="Senior Revenue Operations Lead", description="10+ years experience required")
        score, note = score_seniority(job)
        assert score >= 80, f"Senior title should score high, got {score}"

    def test_intern_penalized(self):
        job = _make_job(title="Intern - Operations", description="Praktikum")
        score, _ = score_seniority(job)
        assert score <= 20, f"Intern should be penalized, got {score}"

    def test_senior_with_junior_in_desc(self):
        """Senior title + junior mention in description should still pass."""
        job = _make_job(title="Senior Manager", description="You will mentor junior team members")
        score, _ = score_seniority(job)
        assert score >= 60, f"Senior title should override junior in desc, got {score}"

    def test_neutral_title(self):
        job = _make_job(title="Operations Specialist", description="Various tasks")
        score, _ = score_seniority(job)
        assert 40 <= score <= 60, f"Neutral title should get middle score, got {score}"


# --- Full scoring pipeline ---

class TestScoreJob:
    def test_ideal_job_scores_high(self):
        job = _make_job(
            title="Revenue Operations Manager",
            company_size=200,
            company_sector="saas",
            company_funding_eur=50_000_000,
            location="München",
            work_mode=WorkMode.HYBRID,
            salary_max=120_000,
            has_equity=True,
            description="SaaS platform, cross-functional leadership, strategy, API, machine learning",
        )
        scored = score_job(job)
        assert scored.total_score >= 60, f"Ideal job should score 60+, got {scored.total_score}"
        assert scored.cluster_match == ClusterPriority.A
        assert scored.matched_title is not None

    def test_terrible_job_scores_low(self):
        job = _make_job(
            title="Junior Data Entry Clerk",
            company_size=5,
            company_sector="gambling",
            location="San Francisco",
            work_mode=WorkMode.ONSITE,
            salary_max=30_000,
            description="Manual data entry, routine processing, GPT wrapper",
        )
        scored = score_job(job)
        assert scored.total_score < 30, f"Terrible job should score low, got {scored.total_score}"

    def test_scored_job_has_all_fields(self):
        job = _make_job()
        scored = score_job(job)
        assert scored.job == job
        assert 0 <= scored.total_score <= 100
        assert 0 <= scored.title_match_score <= 100
        assert 0 <= scored.company_fit_score <= 100
        assert 0 <= scored.location_score <= 100
        assert 0 <= scored.tech_depth_score <= 100
        assert 0 <= scored.ai_resilience_score <= 100
        assert 0 <= scored.salary_score <= 100
        assert isinstance(scored.reasoning, str)

    def test_seniority_multiplier_effect(self):
        """Junior title match should get penalized even with good title."""
        job_senior = _make_job(title="Senior Revenue Operations Manager")
        job_junior = _make_job(title="Junior Revenue Operations Manager")
        scored_senior = score_job(job_senior)
        scored_junior = score_job(job_junior)
        assert scored_senior.total_score > scored_junior.total_score, \
            f"Senior ({scored_senior.total_score}) should beat Junior ({scored_junior.total_score})"


# --- Ranking ---

class TestRanking:
    def test_rank_order(self):
        jobs = [
            _make_job(title="Plumber", description="Fix pipes", url="https://example.com/1"),
            _make_job(title="Revenue Operations Manager", url="https://example.com/2",
                      description="SaaS platform, strategy, cross-functional leadership"),
        ]
        scored = score_and_rank_jobs(jobs)
        if len(scored) >= 2:
            assert scored[0].total_score >= scored[1].total_score

    def test_threshold_filter(self):
        """Jobs below threshold should be filtered out."""
        jobs = [
            _make_job(title="Random Unrelated Job", description="Nothing relevant",
                      location="Tokyo", url="https://example.com/garbage"),
        ]
        scored = score_and_rank_jobs(jobs)
        for s in scored:
            assert s.total_score >= 40, "All returned jobs should be above threshold"

    def test_empty_list(self):
        scored = score_and_rank_jobs([])
        assert scored == []
