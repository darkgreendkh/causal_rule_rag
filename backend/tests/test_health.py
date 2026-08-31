from fastapi.testclient import TestClient

from app.main import create_app


class HealthyStore:
    def health(self) -> bool:
        return True


def test_health_reports_service_readiness() -> None:
    app = create_app(store=HealthyStore())

    with TestClient(app) as client:
        response = client.get("/api/health")

    assert response.status_code == 200
    assert response.json() == {
        "status": "ready",
        "neo4j": True,
        "embedding_model": "BAAI/bge-m3",
        "llm_configured": False,
    }
