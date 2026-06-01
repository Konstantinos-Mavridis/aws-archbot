"""Integration-style tests for the /generate endpoint."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

from fastapi.testclient import TestClient

from app.main import app
from app.models import ArchitectureResponse


def _make_mock_response() -> ArchitectureResponse:
    return ArchitectureResponse(
        architecture_summary="Test summary",
        service_recommendations=[
            {"category": "compute", "service": "ECS Fargate", "reasoning": "Managed containers"}
        ],
        mermaid_diagram="flowchart LR\n  A --> B",
        well_architected_checklist={
            "operational_excellence": [],
            "security": [],
            "reliability": [],
            "performance_efficiency": [],
            "cost_optimization": [],
            "sustainability": [],
        },
        cost_tiers=[
            {
                "tier": "dev",
                "monthly_estimate_hint": "<$100",
                "assumptions": "Low traffic",
            }
        ],
    )


def _mock_pipeline() -> MagicMock:
    """Return a MagicMock that looks like a RagPipeline."""
    mock = MagicMock()
    mock.run = AsyncMock(return_value=_make_mock_response())
    return mock


def test_generate_returns_200(sample_request_payload: dict) -> None:
    # Patch get_pipeline — the factory called inside the endpoint — so the
    # real RagPipeline (which needs AWS credentials) is never instantiated.
    with patch("app.main.get_pipeline", return_value=_mock_pipeline()):
        client = TestClient(app)
        response = client.post("/generate", json=sample_request_payload)
    assert response.status_code == 200
    data = response.json()
    assert "architecture_summary" in data
    assert "mermaid_diagram" in data
    assert "well_architected_checklist" in data


def test_generate_missing_description() -> None:
    client = TestClient(app)
    response = client.post("/generate", json={"workload_description": ""})
    assert response.status_code == 422


def test_generate_default_lens(sample_request_payload: dict) -> None:
    payload = {"workload_description": "Simple web application"}
    with patch("app.main.get_pipeline", return_value=_mock_pipeline()):
        client = TestClient(app)
        response = client.post("/generate", json=payload)
    assert response.status_code == 200


def test_health_endpoint() -> None:
    client = TestClient(app)
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"
