from fastapi.testclient import TestClient
from test_qa_api import APIStore, NoopDocumentService, StaticQAService
from test_research_service import service

from app.main import create_app


def test_research_endpoints_use_actual_computation(tmp_path):
    research = service(tmp_path)
    app = create_app(
        store=APIStore(),
        document_service=NoopDocumentService(),
        qa_service=StaticQAService(),
        research_service=research,
    )
    with TestClient(app) as client:
        assert client.get("/api/research/summary").json()["build_id"] is None
        assert client.post("/api/research/build", json={"profile": "full"}).status_code == 202
        assert client.get("/api/research/status").json()["status"] == "ready"
        assert len(client.get("/api/research/matters").json()) == 1
        assert client.get("/api/research/units?document_id=d").json()[0]["id"] == "u"
        assert client.get("/api/research/source/u").status_code == 200
        assert client.get("/api/research/coverage").json()[0]["disposition"] == "mapped"
        assert client.get("/api/research/actions?matter_id=m").json()[0]["id"] == "a"
        assert client.get("/api/graph?layer=micro&matter_id=m").json()["nodes"]
        case = {
            "matter_id": "m",
            "region": "武汉",
            "as_of": "2024-01-01",
            "facts": {"age": 19, "form": True},
            "steps": ["a"],
        }
        assert (
            client.post("/api/research/workflow/check", json=case).json()["status"] == "satisfied"
        )
        case["facts"]["form"] = False
        assert client.post("/api/research/workflow/check", json=case).json()["status"] == "violated"
        assert client.post("/api/qa", json=dict(case, question="申请条件", mode="causal")).json()[
            "rule_checks"
        ]
        assert (
            client.post(
                "/api/research/rules/review", json={"rule_ids": ["r"], "action": "disable"}
            ).status_code
            == 200
        )
        assert client.get("/api/research/rules?status=disabled").json()[0]["id"] == "r"


def test_bad_research_requests_are_client_errors(tmp_path):
    app = create_app(
        store=APIStore(),
        document_service=NoopDocumentService(),
        qa_service=StaticQAService(),
        research_service=service(tmp_path),
    )
    with TestClient(app) as client:
        assert client.post("/api/research/build", json={"profile": "bogus"}).status_code == 422
        assert client.get("/api/research/graph?layer=bogus").status_code == 422
        assert client.post("/api/research/workflow/check", json={}).status_code == 422
        assert (
            client.post("/api/qa", json={"question": "条件", "mode": "causal"}).status_code == 422
        )
