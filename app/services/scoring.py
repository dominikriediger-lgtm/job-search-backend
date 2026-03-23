"""Job scoring engine - matches jobs against candidate profile."""

import re

from app.core.config import settings
from app.data.profile_seed import CANDIDATE_PROFILE
from app.models.schemas import (
    ClusterPriority,
    JobListing,
    ScoredJob,
    WorkMode,
)

# Seniority detection patterns
_JUNIOR_SIGNALS = re.compile(
    r"\b(intern\b|internship|praktik\w*|werkstudent\w*|working student|"
    r"junior\b|entry.level|graduate\b|trainee|azubi|ausbildung|"
    r"berufseinsteiger|student)\b",
    re.IGNORECASE,
)
_SENIOR_SIGNALS = re.compile(
    r"\b(senior|lead|head of|director|vp |vice president|"
    r"principal|staff\b|c-level|chief|managing director|"
    r"experienced|8\+?\s*years?|10\+?\s*years?)\b",
    re.IGNORECASE,
)
_MID_SIGNALS = re.compile(
    r"\b(manager|3\+?\s*years?|5\+?\s*years?|mid.?level|"
    r"berufserfahrung|experienced)\b",
    re.IGNORECASE,
)


def _normalize(text: str) -> str:
    return text.lower().strip()


def score_title_match(job: JobListing) -> tuple[float, ClusterPriority | None, str | None]:
    """Score how well the job title matches our target titles. Returns (score, cluster, matched_title)."""
    job_title_lower = _normalize(job.title)
    job_desc_lower = _normalize(job.description)
    best_score = 0.0
    best_cluster = None
    best_title = None

    cluster_bonus = {
        ClusterPriority.A: 1.0,
        ClusterPriority.B: 0.85,
        ClusterPriority.C: 0.7,
    }

    for target in CANDIDATE_PROFILE.job_titles:
        target_lower = _normalize(target.title)
        score = 0.0

        # Exact title match
        if target_lower in job_title_lower:
            score = 95.0
        else:
            # Keyword matching in title and description
            title_keyword_hits = sum(
                1 for kw in target.keywords if kw.lower() in job_title_lower
            )
            desc_keyword_hits = sum(
                1 for kw in target.keywords if kw.lower() in job_desc_lower
            )
            if target.keywords:
                title_ratio = title_keyword_hits / len(target.keywords)
                desc_ratio = desc_keyword_hits / len(target.keywords)
                # Title keywords worth more than description keywords
                score = (title_ratio * 70) + (desc_ratio * 20)

        # Apply cluster priority bonus
        score *= cluster_bonus.get(target.cluster, 0.7)

        if score > best_score:
            best_score = score
            best_cluster = target.cluster
            best_title = target.title

    return min(best_score, 100.0), best_cluster, best_title


def score_company_fit(job: JobListing) -> float:
    """Score company fit based on size, sector, and type."""
    score = 50.0  # baseline

    cf = CANDIDATE_PROFILE.company_filter

    # Company size check
    if job.company_size is not None:
        if job.company_size < cf.min_employees:
            score -= 30
        elif 20 <= job.company_size <= 500:
            score += 25  # sweet spot: scale-up
        elif job.company_size <= 5000:
            score += 10
        else:
            score -= 10  # too corporate

    # Funding check for startups
    if job.company_size and job.company_size < 50 and job.company_funding_eur is not None:
        if job.company_funding_eur >= cf.min_funding_eur:
            score += 20
        else:
            score -= 15

    # Sector match
    if job.company_sector:
        sector_lower = _normalize(job.company_sector)
        if any(s in sector_lower for s in cf.excluded_sectors):
            score -= 40
        if any(s in sector_lower for s in cf.preferred_sectors):
            score += 25

    return max(0.0, min(100.0, score))


def score_location(job: JobListing) -> float:
    """Score location and work mode fit."""
    prefs = CANDIDATE_PROFILE.search_preferences
    score = 50.0
    loc_lower = _normalize(job.location)

    # Location match
    munich_keywords = ["münchen", "munich", "muc"]
    if any(kw in loc_lower for kw in munich_keywords):
        score += 30
    elif "remote" in loc_lower or "germany" in loc_lower or "deutschland" in loc_lower:
        score += 15
    else:
        score -= 20

    # Work mode match
    if job.work_mode:
        if job.work_mode in prefs.work_modes:
            score += 20
        elif job.work_mode == WorkMode.ONSITE and prefs.accept_onsite_if_excellent:
            score += 5  # small bonus, acceptable if job is great
        else:
            score -= 10

    return max(0.0, min(100.0, score))


def score_tech_depth(job: JobListing) -> float:
    """Score how 'true tech' the company/role is. Penalizes light-tech / GPT wrappers."""
    desc_lower = _normalize(job.description)
    score = 50.0

    # True tech indicators
    true_tech_signals = [
        "saas", "platform", "api", "infrastructure", "machine learning",
        "data science", "engineering", "product", "r&d", "research",
        "deep tech", "robotics", "hardware", "fintech", "healthtech",
        "sportstech", "defensetech", "energytech", "cybersecurity",
    ]
    # Light tech / wrapper red flags
    wrapper_signals = [
        "gpt wrapper", "chatgpt plugin", "prompt engineering only",
        "no-code agency", "wordpress",
    ]

    tech_hits = sum(1 for s in true_tech_signals if s in desc_lower)
    wrapper_hits = sum(1 for s in wrapper_signals if s in desc_lower)

    score += min(tech_hits * 8, 40)
    score -= wrapper_hits * 20

    return max(0.0, min(100.0, score))


def score_ai_resilience(job: JobListing) -> float:
    """Score how resilient the role is against AI disruption."""
    desc_lower = _normalize(job.description)
    title_lower = _normalize(job.title)
    score = 50.0

    # Roles involving human judgment, strategy, stakeholder management are more resilient
    resilient_signals = [
        "strategy", "stakeholder", "leadership", "cross-functional",
        "negotiation", "c-level", "executive", "transformation",
        "change management", "board", "investor", "partnership",
        "people management", "team lead",
    ]
    # Roles that AI might replace more easily
    vulnerable_signals = [
        "data entry", "manual reporting", "copy paste",
        "basic admin", "routine processing",
    ]

    resilient_hits = sum(
        1 for s in resilient_signals if s in desc_lower or s in title_lower
    )
    vulnerable_hits = sum(
        1 for s in vulnerable_signals if s in desc_lower or s in title_lower
    )

    score += min(resilient_hits * 7, 40)
    score -= vulnerable_hits * 15

    return max(0.0, min(100.0, score))


def score_salary(job: JobListing) -> float:
    """Score salary fit."""
    prefs = CANDIDATE_PROFILE.search_preferences
    score = 50.0

    if job.salary_max is not None:
        if job.salary_max >= prefs.min_salary_eur:
            score += 40
        elif job.salary_max >= prefs.min_salary_eur * 0.85:
            score += 20  # close enough
        else:
            score -= 20

    if job.salary_min is not None and job.salary_min >= prefs.min_salary_eur:
        score += 10  # even the minimum is above target

    if job.has_equity:
        score += 15

    return max(0.0, min(100.0, score))


def score_seniority(job: JobListing) -> tuple[float, str]:
    """Score seniority fit. Candidate has 8+ years experience.

    Returns (score, reasoning_note).
    """
    text = f"{job.title} {job.description[:1000]}"
    title_lower = _normalize(job.title)

    # Hard penalty for junior/intern
    if _JUNIOR_SIGNALS.search(text):
        # Unless title also says senior/lead/manager
        if _SENIOR_SIGNALS.search(job.title):
            return 60.0, ""
        return 10.0, "Junior/Intern level - seniority mismatch"

    # Bonus for senior/lead/head titles
    if _SENIOR_SIGNALS.search(job.title):
        return 90.0, "Senior/Lead level - good seniority fit"

    # Mid-level is acceptable
    if _MID_SIGNALS.search(text):
        return 65.0, ""

    # Unknown seniority - neutral
    return 50.0, ""


def score_job(job: JobListing) -> ScoredJob:
    """Calculate the total weighted score for a job listing."""
    title_score, cluster, matched_title = score_title_match(job)
    company_score = score_company_fit(job)
    location_sc = score_location(job)
    tech_score = score_tech_depth(job)
    ai_score = score_ai_resilience(job)
    salary_sc = score_salary(job)
    seniority_sc, seniority_note = score_seniority(job)

    w = settings
    # Seniority acts as a multiplier on the title score
    # A junior job with perfect title match should still score low
    adjusted_title = title_score * (seniority_sc / 100.0)

    total = (
        adjusted_title * w.weight_title_match
        + company_score * w.weight_company_fit
        + location_sc * w.weight_location
        + tech_score * w.weight_tech_depth
        + ai_score * w.weight_ai_resilience
        + salary_sc * w.weight_salary
    ) / 100

    reasoning_parts = []
    if cluster:
        reasoning_parts.append(f"Cluster {cluster.value} match: {matched_title}")
    if title_score >= 70:
        reasoning_parts.append("Strong title match")
    if company_score >= 70:
        reasoning_parts.append("Great company fit")
    if tech_score < 40:
        reasoning_parts.append("Low tech depth - possible light-tech")
    if ai_score >= 70:
        reasoning_parts.append("AI-resilient role")
    if seniority_note:
        reasoning_parts.append(seniority_note)

    return ScoredJob(
        job=job,
        total_score=round(total, 1),
        title_match_score=round(title_score, 1),
        company_fit_score=round(company_score, 1),
        location_score=round(location_sc, 1),
        tech_depth_score=round(tech_score, 1),
        ai_resilience_score=round(ai_score, 1),
        salary_score=round(salary_sc, 1),
        cluster_match=cluster,
        matched_title=matched_title,
        reasoning="; ".join(reasoning_parts) if reasoning_parts else "No strong signals",
    )


def score_and_rank_jobs(jobs: list[JobListing]) -> list[ScoredJob]:
    """Score all jobs and return them ranked by total score descending."""
    scored = [score_job(job) for job in jobs]
    scored.sort(key=lambda s: s.total_score, reverse=True)
    return [s for s in scored if s.total_score >= settings.min_score_threshold]
