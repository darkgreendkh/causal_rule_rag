import os
from uuid import uuid4

import pytest
from neo4j import GraphDatabase
from test_research_service import Chat, Embedder, corpus

from app.config import Settings
from app.research import ResearchService
from app.research_store import ResearchRepository


@pytest.mark.integration
@pytest.mark.skipif(
    os.getenv("RUN_RESEARCH_NEO4J_TESTS") != "1", reason="Explicit isolated Neo4j verification"
)
def test_snapshot_projection_review_and_invalidation_are_isolated(tmp_path):
    settings = Settings()
    driver = GraphDatabase.driver(
        settings.neo4j_uri, auth=(settings.neo4j_user, settings.neo4j_password)
    )
    namespace = "engineering-test-" + uuid4().hex
    repository = ResearchRepository(driver, tmp_path, namespace=namespace)
    service = ResearchService(
        repository, Embedder(), Chat(), tmp_path, tmp_path / "cache", builder=lambda _: corpus()
    )
    try:
        service.build("full")
        snapshot = repository.load("full")
        assert snapshot["corpus"]["units"][0]["text"] == corpus()["units"][0]["text"]
        rows, _, _ = driver.execute_query(
            "MATCH (n:ResearchNode {namespace:$namespace}) RETURN count(n) AS count",
            namespace=namespace,
        )
        assert rows[0]["count"] == len(snapshot["graph"]["nodes"])
        service.build("without_micro")
        assert repository.load("full")["build_id"] == snapshot["build_id"]
        service.review(["r"], "disable")
        assert repository.load("without_micro") is None
        rows, _, _ = driver.execute_query(
            "MATCH (n:ResearchNode {namespace:$namespace})-[r:RESEARCH_LINK]->() "
            "WHERE n.build_id <> $bid RETURN count(r) AS count",
            namespace=namespace,
            bid=repository.load("full")["build_id"],
        )
        assert rows[0]["count"] == 0
        repository.invalidate("engineering test complete")
        assert repository.load("full") is None
    finally:
        repository.invalidate("engineering test cleanup")
        driver.execute_query(
            "MATCH (s:KnowledgeSnapshot {namespace:$namespace}) DELETE s", namespace=namespace
        )
        driver.close()
