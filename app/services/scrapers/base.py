"""Base class for all job scrapers."""

from abc import ABC, abstractmethod

from app.models.schemas import JobListing


class BaseScraper(ABC):
    """Interface that all job source scrapers must implement."""

    @property
    @abstractmethod
    def source_name(self) -> str:
        """Unique identifier for this source (e.g. 'adzuna', 'arbeitnow')."""
        ...

    @property
    @abstractmethod
    def display_name(self) -> str:
        """Human-readable name."""
        ...

    @abstractmethod
    async def search(self, query: str, location: str = "München", max_results: int = 25) -> list[JobListing]:
        """Search for jobs and return normalized JobListing objects."""
        ...

    @abstractmethod
    def is_configured(self) -> bool:
        """Check if required API keys / config are set."""
        ...
