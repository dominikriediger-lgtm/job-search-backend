"""Dominik Riediger's candidate profile - seed data for job matching."""

from app.models.schemas import (
    CandidateProfile,
    ClusterPriority,
    CompanyFilter,
    JobTitle,
    SearchPreferences,
    WorkMode,
)

JOB_TITLES = [
    # Cluster A: Hohe Passung
    JobTitle(
        title="AI Transformation Manager",
        cluster=ClusterPriority.A,
        keywords=["ai transformation", "digital transformation", "ai strategy", "process automation"],
    ),
    JobTitle(
        title="Revenue Operations Manager",
        cluster=ClusterPriority.A,
        keywords=["revops", "revenue operations", "revenue ops", "sales operations"],
    ),
    JobTitle(
        title="Revenue Operations Lead",
        cluster=ClusterPriority.A,
        keywords=["revops lead", "revenue operations lead", "head of revops"],
    ),
    JobTitle(
        title="Business Operations Manager",
        cluster=ClusterPriority.A,
        keywords=["business ops", "biz ops", "operations manager"],
    ),
    JobTitle(
        title="GTM Operations Manager",
        cluster=ClusterPriority.A,
        keywords=["go-to-market", "gtm ops", "gtm operations", "go to market"],
    ),
    JobTitle(
        title="Commercial Excellence Manager",
        cluster=ClusterPriority.A,
        keywords=["commercial excellence", "commercial strategy", "commercial ops"],
    ),
    JobTitle(
        title="CRM & Automation Lead",
        cluster=ClusterPriority.A,
        keywords=["crm lead", "marketing automation", "crm manager", "automation lead"],
    ),
    JobTitle(
        title="Business Systems Lead",
        cluster=ClusterPriority.A,
        keywords=["business systems", "systems lead", "business tools", "tech stack owner"],
    ),
    # Cluster B: Etwas strategischer
    JobTitle(
        title="Chief of Staff",
        cluster=ClusterPriority.B,
        keywords=["chief of staff", "cos", "ceo office", "executive office"],
    ),
    JobTitle(
        title="Founder's Associate",
        cluster=ClusterPriority.B,
        keywords=["founders associate", "founder associate", "ceo associate"],
    ),
    JobTitle(
        title="Strategy & Operations Manager",
        cluster=ClusterPriority.B,
        keywords=["strategy ops", "stratops", "strategy and operations"],
    ),
    JobTitle(
        title="Operational Excellence Manager",
        cluster=ClusterPriority.B,
        keywords=["opex", "operational excellence", "process excellence"],
    ),
    # Cluster C: Unternehmerisch
    JobTitle(
        title="Fractional RevOps Lead",
        cluster=ClusterPriority.C,
        keywords=["fractional", "part-time revops", "interim revops"],
    ),
    JobTitle(
        title="Fractional AI Transformation Lead",
        cluster=ClusterPriority.C,
        keywords=["fractional ai", "interim ai", "ai consultant"],
    ),
    JobTitle(
        title="CRM & Automation Consultant",
        cluster=ClusterPriority.C,
        keywords=["crm consultant", "automation consultant", "crm beratung"],
    ),
    JobTitle(
        title="Vertical AI Solutions Builder",
        cluster=ClusterPriority.C,
        keywords=["ai solutions", "vertical ai", "industry ai"],
    ),
    # Additional titles derived from CV analysis
    JobTitle(
        title="Digital Transformation Manager",
        cluster=ClusterPriority.A,
        keywords=["digital transformation", "digitalisierung", "digital change"],
    ),
    JobTitle(
        title="Growth Operations Manager",
        cluster=ClusterPriority.A,
        keywords=["growth ops", "growth operations", "growth manager"],
    ),
    JobTitle(
        title="Head of Business Automation",
        cluster=ClusterPriority.A,
        keywords=["business automation", "process automation", "automation head"],
    ),
    JobTitle(
        title="AI Implementation Lead",
        cluster=ClusterPriority.A,
        keywords=["ai implementation", "ai rollout", "ai deployment"],
    ),
    JobTitle(
        title="Customer Operations Lead",
        cluster=ClusterPriority.A,
        keywords=["customer ops", "customer operations", "customer success ops"],
    ),
]

COMPANY_FILTER = CompanyFilter(
    min_employees=20,
    min_funding_eur=20_000_000,
    preferred_sectors=[
        "saas",
        "software",
        "fintech",
        "healthtech",
        "sportstech",
        "defensetech",
        "energytech",
        "ai",
        "ai-consulting",
        "platform",
    ],
    excluded_sectors=[
        "traditional-automotive",
        "old-fashioned-corporate",
        "gpt-wrapper",
    ],
    preferred_company_types=[
        "scale-up",
        "growth-stage-startup",
        "tech-company",
        "vc-backed",
    ],
)

SEARCH_PREFERENCES = SearchPreferences(
    location="München",
    max_distance_km=50,
    work_modes=[WorkMode.HYBRID, WorkMode.REMOTE],
    accept_onsite_if_excellent=True,
    languages=["de", "en"],
    min_salary_eur=100_000,
    equity_preferred=True,
)

CANDIDATE_PROFILE = CandidateProfile(
    name="Dominik Riediger",
    email="dominikriediger@web.de",
    phone="+49 176 85938004",
    location="Bad Tölz, Germany",
    languages=["de", "en", "es"],
    years_experience=8,
    job_titles=JOB_TITLES,
    company_filter=COMPANY_FILTER,
    search_preferences=SEARCH_PREFERENCES,
    cv_summary=(
        "Commercial strategist with entrepreneurial drive and passion for technology-enabled "
        "transformation. Built award-winning startup (€1.6M raised), drove €10M+ CRM revenue "
        "at FC Bayern Munich, founded AI automation venture delivering measurable process "
        "improvements. Combines strategic thinking with hands-on execution, from stakeholder "
        "alignment and process design to low-code and AI implementation."
    ),
    cover_letter_style=(
        "Personal and specific. Opens with a warm connection (personal reference or product "
        "experience), bridges corporate discipline (FC Bayern, BMW) with entrepreneurial "
        "ownership (Founder/CEO). Uses concrete numbers (€10M+, €1.6M, 300M+ contacts). "
        "Closes with genuine enthusiasm. Tone: confident but approachable, Bavarian groundedness "
        "meets international outlook."
    ),
    key_achievements=[
        "€60K+ contracts in 2 months as solo AI consultant (IsaRDrive)",
        "80% reduction in claims processing time with 0% error rate",
        "€10M+ CRM merchandising revenue at FC Bayern (25%+ YoY growth)",
        "€1.6M+ raised for Qwicklane, ISPO Best Newcomer 2023",
        "300M+ fan contacts managed, 300K+ leads in 50+ countries",
        "30+ retail partners secured, Dynafit strategic partnership",
        "GDPR-compliant AI infrastructure for regulated industries",
    ],
    technical_skills=[
        "GenAI / LLM integration",
        "No-code platforms (Top 1% Lovable users)",
        "CRM systems & automation",
        "Cursor / AI-assisted development",
        "Supabase",
        "Process automation",
        "Data-driven marketing",
        "Low-code development",
    ],
)

# Example companies of interest (for reference and search seeding)
EXAMPLE_COMPANIES = [
    {"name": "Orbeem", "why": "Fast-growing tech company in Munich"},
    {"name": "Arx Robotics", "why": "DefenseTech, fast-growing, Munich-based"},
]
