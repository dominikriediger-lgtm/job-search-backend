from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Optional

from pydantic import BaseModel, Field


class ClusterPriority(str, Enum):
    A = "A"  # Hohe Passung
    B = "B"  # Etwas strategischer
    C = "C"  # Unternehmerisch


class WorkMode(str, Enum):
    REMOTE = "remote"
    HYBRID = "hybrid"
    ONSITE = "onsite"


class JobStatus(str, Enum):
    NEW = "new"
    SCORED = "scored"
    APPLIED = "applied"
    INTERVIEW = "interview"
    REJECTED = "rejected"
    ARCHIVED = "archived"


class JobTitle(BaseModel):
    title: str
    cluster: ClusterPriority
    keywords: list[str] = Field(default_factory=list)


class CompanyFilter(BaseModel):
    min_employees: int = 20
    min_funding_eur: int = 20_000_000  # for startups
    preferred_sectors: list[str] = Field(default_factory=list)
    excluded_sectors: list[str] = Field(default_factory=list)
    preferred_company_types: list[str] = Field(default_factory=list)


class SearchPreferences(BaseModel):
    location: str = "München"
    max_distance_km: int = 50
    work_modes: list[WorkMode] = Field(default_factory=lambda: [WorkMode.HYBRID, WorkMode.REMOTE])
    accept_onsite_if_excellent: bool = True
    languages: list[str] = Field(default_factory=lambda: ["de", "en"])
    min_salary_eur: int = 100_000
    equity_preferred: bool = True


class CandidateProfile(BaseModel):
    name: str
    email: str
    phone: str
    location: str
    languages: list[str]
    years_experience: int
    job_titles: list[JobTitle]
    company_filter: CompanyFilter
    search_preferences: SearchPreferences
    cv_summary: str
    cover_letter_style: str
    key_achievements: list[str]
    technical_skills: list[str]


class JobListing(BaseModel):
    id: Optional[str] = None
    title: str
    company: str
    company_size: Optional[int] = None
    company_funding_eur: Optional[int] = None
    company_sector: Optional[str] = None
    location: str
    work_mode: Optional[WorkMode] = None
    salary_min: Optional[int] = None
    salary_max: Optional[int] = None
    has_equity: Optional[bool] = None
    description: str
    url: str
    source: str  # e.g. "linkedin", "stepstone", "karriereseite"
    posted_at: Optional[datetime] = None
    discovered_at: datetime = Field(default_factory=datetime.utcnow)
    status: JobStatus = JobStatus.NEW


class ScoredJob(BaseModel):
    job: JobListing
    total_score: float = Field(ge=0, le=100)
    title_match_score: float = Field(ge=0, le=100)
    company_fit_score: float = Field(ge=0, le=100)
    location_score: float = Field(ge=0, le=100)
    tech_depth_score: float = Field(ge=0, le=100)
    ai_resilience_score: float = Field(ge=0, le=100)
    salary_score: float = Field(ge=0, le=100)
    cluster_match: Optional[ClusterPriority] = None
    matched_title: Optional[str] = None
    reasoning: str = ""
