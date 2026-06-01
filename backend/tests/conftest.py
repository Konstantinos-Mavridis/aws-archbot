"""Shared pytest fixtures for ArchBot backend tests."""

from __future__ import annotations

import json
from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.rag_pipeline import RagPipeline


@pytest.fixture()
def client() -> TestClient:
    return TestClient(app)


@pytest.fixture()
def mock_rag_pipeline() -> MagicMock:
    """Return a MagicMock that satisfies the RagPipeline interface."""
    mock = MagicMock(spec=RagPipeline)
    mock.run.return_value = _sample_response()
    return mock


@pytest.fixture()
def sample_request_payload() -> dict:
    return {
        "workload_description": "Regulated FSI trade finance platform using CQRS",
        "lens": "fsi",
        "non_functionals": {
            "sla_percent": 99.99,
            "regions": 2,
            "rto_minutes": 15,
            "rpo_minutes": 5,
            "compliance_flags": ["PCI-DSS", "SOX"],
        },
    }


@pytest.fixture()
def patched_pipeline(mock_rag_pipeline: MagicMock):
    """Patch the global pipeline singleton in app.main."""
    with patch("app.main.pipeline", mock_rag_pipeline):
        yield mock_rag_pipeline


def _sample_response() -> dict:
    return {
        "architecture_summary": "A sample FSI architecture summary.",
        "service_recommendations": [
            {"category": "compute", "service": "AWS Fargate", "reasoning": "Serverless containers"}
        ],
        "mermaid_diagram": "flowchart LR\n  A --> B",
        "well_architected_checklist": {
            "operational_excellence": [],
            "security": [
                {
                    "question": "Is data encrypted at rest?",
                    "risk_level": "HIGH",
                    "finding": "No KMS policy defined.",
                    "improvement_suggestion": "Enable SSE-KMS on all S3 buckets.",
                }
            ],
            "reliability": [],
            "performance_efficiency": [],
            "cost_optimization": [],
            "sustainability": [],
        },
        "cost_tiers": [
            {
                "tier": "dev",
                "monthly_estimate_hint": "Under $150/month",
                "assumptions": "Single region, minimal traffic",
            }
        ],
    }
