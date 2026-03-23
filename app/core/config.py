import logging
from pathlib import Path

from dotenv import load_dotenv
from pydantic_settings import BaseSettings

_logger = logging.getLogger(__name__)

# Explicitly load .env into os.environ BEFORE pydantic-settings reads it.
# pydantic-settings' built-in env_file support is unreliable on Windows
# with long paths (OneDrive). python-dotenv handles this correctly.
_ENV_FILE = Path(__file__).resolve().parent.parent.parent / ".env"
if _ENV_FILE.exists():
    load_dotenv(_ENV_FILE, override=False)
else:
    _logger.warning(
        ".env file not found at %s — copy .env.example to .env and add your API keys!",
        _ENV_FILE,
    )


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

    model_config = {"env_prefix": "JOBSEARCH_"}


settings = Settings()
