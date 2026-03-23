from pathlib import Path

from pydantic_settings import BaseSettings

# Resolve .env relative to the project root (two levels up from this file)
_ENV_FILE = Path(__file__).resolve().parent.parent.parent / ".env"


class Settings(BaseSettings):
    app_name: str = "Job Search Agent"
    debug: bool = True
    database_url: str = "sqlite:///./jobs.db"

    # Scoring weights (sum should be 100)
    weight_title_match: float = 25
    weight_company_fit: float = 20
    weight_location: float = 15
    weight_tech_depth: float = 15
    weight_ai_resilience: float = 15
    weight_salary: float = 10

    # Minimum score to surface a job
    min_score_threshold: float = 40

    # Adzuna API (free: 250 calls/month, sign up at developer.adzuna.com)
    adzuna_app_id: str = ""
    adzuna_api_key: str = ""

    # Firecrawl API (free: 500 credits/month, sign up at firecrawl.dev)
    firecrawl_api_key: str = ""

    # SerpAPI (free: 100 searches/month, sign up at serpapi.com)
    serpapi_key: str | None = None

    model_config = {
        "env_file": str(_ENV_FILE),
        "env_prefix": "JOBSEARCH_",
        "env_file_encoding": "utf-8",
    }


settings = Settings()
