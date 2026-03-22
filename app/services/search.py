"""Job search service - generates search queries and orchestrates scraping."""

from app.data.profile_seed import CANDIDATE_PROFILE, EXAMPLE_COMPANIES
from app.models.schemas import ClusterPriority


def generate_search_queries(max_queries: int = 30) -> list[dict]:
    """Generate search queries for job boards based on profile.

    Returns a list of dicts with 'query', 'source', and 'cluster' keys.
    """
    queries = []
    prefs = CANDIDATE_PROFILE.search_preferences
    location = prefs.location

    # Group titles by cluster for prioritized searching
    cluster_order = [ClusterPriority.A, ClusterPriority.B, ClusterPriority.C]

    for cluster in cluster_order:
        titles = [jt for jt in CANDIDATE_PROFILE.job_titles if jt.cluster == cluster]
        for title in titles:
            # LinkedIn-style query
            queries.append({
                "query": f'"{title.title}" {location}',
                "source": "linkedin",
                "cluster": cluster.value,
                "title": title.title,
            })
            # German variation for German boards
            queries.append({
                "query": f"{title.title} München Hybrid",
                "source": "stepstone",
                "cluster": cluster.value,
                "title": title.title,
            })

    # Company-specific queries
    for company in EXAMPLE_COMPANIES:
        queries.append({
            "query": f'{company["name"]} jobs {location}',
            "source": "karriereseite",
            "cluster": "company_specific",
            "title": company["name"],
        })

    # Limit to max_queries, prioritizing Cluster A
    return queries[:max_queries]


def get_supported_sources() -> list[dict]:
    """Return list of supported job sources with their status."""
    return [
        {
            "name": "linkedin",
            "display_name": "LinkedIn Jobs",
            "status": "planned",
            "method": "api/scraping",
        },
        {
            "name": "stepstone",
            "display_name": "StepStone",
            "status": "planned",
            "method": "api",
        },
        {
            "name": "indeed",
            "display_name": "Indeed",
            "status": "planned",
            "method": "api/scraping",
        },
        {
            "name": "glassdoor",
            "display_name": "Glassdoor",
            "status": "planned",
            "method": "scraping",
        },
        {
            "name": "karriereseite",
            "display_name": "Company Career Pages",
            "status": "planned",
            "method": "scraping",
        },
        {
            "name": "weworkremotely",
            "display_name": "We Work Remotely",
            "status": "planned",
            "method": "api",
        },
    ]
