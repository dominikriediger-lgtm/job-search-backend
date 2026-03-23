"""Target companies to monitor - Top Scale-Ups and Tech Companies in Munich area.

This list is the core of the direct-crawl strategy: we check their career pages
regularly instead of relying only on job board aggregators.

Each company has an `ats` field mapping to the ATS platform and board slug,
so we can use the free public JSON/XML APIs instead of scraping HTML.
"""

TARGET_COMPANIES = [
    # --- AI & Data ---
    {
        "name": "Celonis",
        "sector": "ai",
        "careers_url": "https://www.celonis.com/careers/jobs/",
        "ats": {"platform": "greenhouse", "slug": "celonis"},
        "size_estimate": 3000,
        "funding_eur": 1_000_000_000,
        "why": "Process Mining Unicorn, Munich HQ",
    },
    {
        "name": "Helsing",
        "sector": "defensetech",
        "careers_url": "https://helsing.ai/careers",
        "ats": {"platform": "ashby", "slug": "helsing"},
        "size_estimate": 400,
        "funding_eur": 450_000_000,
        "why": "DefenseTech AI, Munich-based, fast-growing",
    },
    {
        "name": "Aleph Alpha",
        "sector": "ai",
        "careers_url": "https://aleph-alpha.com/careers/",
        "ats": {"platform": "greenhouse", "slug": "alephalpha"},
        "size_estimate": 150,
        "funding_eur": 500_000_000,
        "why": "European LLM company, enterprise AI",
    },
    {
        "name": "DeepL",
        "sector": "ai",
        "careers_url": "https://www.deepl.com/en/careers/jobs",
        "ats": {"platform": "greenhouse", "slug": "deepl"},
        "size_estimate": 900,
        "funding_eur": 300_000_000,
        "why": "AI translation, Cologne but remote-friendly",
    },
    # --- SaaS / Platform ---
    {
        "name": "Personio",
        "sector": "saas",
        "careers_url": "https://www.personio.com/about-personio/careers/",
        "ats": {"platform": "smartrecruiters", "slug": "Personio"},
        "size_estimate": 2000,
        "funding_eur": 700_000_000,
        "why": "HR-Tech Unicorn, Munich HQ",
    },
    {
        "name": "Brainly / Photomath",
        "sector": "edtech",
        "careers_url": "https://careers.brainly.com/",
        "ats": {"platform": "lever", "slug": "brainly"},
        "size_estimate": 700,
        "funding_eur": 150_000_000,
        "why": "EdTech, Munich office",
    },
    {
        "name": "Contentful",
        "sector": "saas",
        "careers_url": "https://www.contentful.com/careers/",
        "ats": {"platform": "greenhouse", "slug": "contentful"},
        "size_estimate": 800,
        "funding_eur": 350_000_000,
        "why": "Headless CMS, Berlin + Munich",
    },
    {
        "name": "Adjust (AppLovin)",
        "sector": "saas",
        "careers_url": "https://www.adjust.com/company/careers/",
        "ats": {"platform": "greenhouse", "slug": "adjust"},
        "size_estimate": 500,
        "funding_eur": 250_000_000,
        "why": "Mobile Analytics, Munich-founded",
    },
    # --- FinTech ---
    {
        "name": "Scalable Capital",
        "sector": "fintech",
        "careers_url": "https://de.scalable.capital/karriere#jobs",
        "ats": {"platform": "greenhouse", "slug": "scalablecapital"},
        "size_estimate": 500,
        "funding_eur": 200_000_000,
        "why": "Digital wealth management, Munich HQ",
    },
    {
        "name": "Wayflyer",
        "sector": "fintech",
        "careers_url": "https://www.wayflyer.com/careers",
        "ats": {"platform": "ashby", "slug": "wayflyer"},
        "size_estimate": 300,
        "funding_eur": 300_000_000,
        "why": "Revenue-based financing, Dublin + Munich",
    },
    # --- DefenseTech / DeepTech ---
    {
        "name": "Arx Robotics",
        "sector": "defensetech",
        "careers_url": "https://www.arx-robotics.com/careers",
        "ats": {"platform": "personio", "slug": "arx-robotics"},
        "size_estimate": 30,
        "funding_eur": 25_000_000,
        "why": "DefenseTech robotics, Munich, fast-growing",
    },
    {
        "name": "Isar Aerospace",
        "sector": "spacetech",
        "careers_url": "https://www.isaraerospace.com/careers",
        "ats": {"platform": "greenhouse", "slug": "isaraerospace"},
        "size_estimate": 400,
        "funding_eur": 300_000_000,
        "why": "SpaceTech, Munich area",
    },
    {
        "name": "Lilium",
        "sector": "deeptech",
        "careers_url": "https://lilium.com/careers",
        "ats": {"platform": "greenhouse", "slug": "lilium"},
        "size_estimate": 800,
        "funding_eur": 1_500_000_000,
        "why": "eVTOL / urban air mobility, Munich",
    },
    # --- EnergyTech ---
    {
        "name": "Tado",
        "sector": "energytech",
        "careers_url": "https://www.tado.com/de-en/careers",
        "ats": {"platform": "greenhouse", "slug": "tado56"},
        "size_estimate": 200,
        "funding_eur": 100_000_000,
        "why": "Smart home climate, Munich HQ",
    },
    {
        "name": "Reverion",
        "sector": "energytech",
        "careers_url": "https://reverion.com/careers/",
        "ats": {"platform": "personio", "slug": "reverion"},
        "size_estimate": 60,
        "funding_eur": 50_000_000,
        "why": "Fuel cell tech, Munich area, TUM spin-off",
    },
    # --- SportsTech / Consumer ---
    {
        "name": "Freeletics",
        "sector": "sportstech",
        "careers_url": "https://www.freeletics.com/en/corporate/jobs/",
        "ats": {"platform": "personio", "slug": "freeletics"},
        "size_estimate": 200,
        "funding_eur": 60_000_000,
        "why": "Fitness AI, Munich HQ",
    },
    {
        "name": "Tonies",
        "sector": "consumer-tech",
        "careers_url": "https://tonies.com/de-de/careers/",
        "ats": {"platform": "greenhouse", "slug": "tonies"},
        "size_estimate": 600,
        "funding_eur": 200_000_000,
        "why": "Audio platform for kids, Düsseldorf but remote",
    },
    {
        "name": "BestSecret",
        "sector": "ecommerce",
        "careers_url": "https://www.bestsecret.com/company/careers/",
        "ats": {"platform": "greenhouse", "slug": "bestsecret"},
        "size_estimate": 1000,
        "funding_eur": 500_000_000,
        "why": "Members-only fashion, Munich - personal connection",
    },
    # --- Other notable Scale-Ups ---
    {
        "name": "Orbeem",
        "sector": "software",
        "careers_url": "https://orbeem.com/careers",
        "ats": None,
        "size_estimate": 50,
        "funding_eur": 30_000_000,
        "why": "Fast-growing tech, Munich",
    },
    {
        "name": "FINN",
        "sector": "mobility",
        "careers_url": "https://www.finn.com/careers",
        "ats": {"platform": "greenhouse", "slug": "finn-auto"},
        "size_estimate": 300,
        "funding_eur": 300_000_000,
        "why": "Car subscription, Munich HQ",
    },
    {
        "name": "Avi Medical",
        "sector": "healthtech",
        "careers_url": "https://avi-medical.com/en/career",
        "ats": {"platform": "personio", "slug": "avi-medical"},
        "size_estimate": 250,
        "funding_eur": 100_000_000,
        "why": "Digital-first healthcare, Munich",
    },
    {
        "name": "Quantum Systems",
        "sector": "defensetech",
        "careers_url": "https://www.quantum-systems.com/career/",
        "ats": {"platform": "personio", "slug": "quantum-systems"},
        "size_estimate": 200,
        "funding_eur": 70_000_000,
        "why": "Drone tech, dual-use defense, Munich area",
    },
]


def get_career_urls() -> list[dict]:
    """Return all career page URLs for crawling."""
    return [
        {
            "company": c["name"],
            "url": c["careers_url"],
            "sector": c["sector"],
            "size": c["size_estimate"],
            "ats": c.get("ats"),
        }
        for c in TARGET_COMPANIES
    ]
