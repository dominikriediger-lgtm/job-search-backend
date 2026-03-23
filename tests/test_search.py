"""Tests for search query generation."""

from app.services.search import generate_search_queries, get_supported_sources


class TestSearchQueries:
    def test_generates_queries(self):
        queries = generate_search_queries()
        assert len(queries) > 0
        assert len(queries) <= 30  # default max

    def test_max_queries_limit(self):
        queries = generate_search_queries(max_queries=5)
        assert len(queries) <= 5

    def test_query_structure(self):
        queries = generate_search_queries(max_queries=5)
        for q in queries:
            assert "query" in q
            assert "source" in q
            assert "cluster" in q
            assert isinstance(q["query"], str)
            assert len(q["query"]) > 0

    def test_cluster_a_first(self):
        """Cluster A titles should appear before B and C."""
        queries = generate_search_queries(max_queries=100)
        if len(queries) > 2:
            # First queries should be cluster A
            assert queries[0]["cluster"] == "A"

    def test_includes_company_specific(self):
        queries = generate_search_queries(max_queries=100)
        company_queries = [q for q in queries if q["cluster"] == "company_specific"]
        assert len(company_queries) > 0


class TestSupportedSources:
    def test_returns_sources(self):
        sources = get_supported_sources()
        assert len(sources) > 0
        for s in sources:
            assert "name" in s
            assert "display_name" in s
            assert "status" in s
