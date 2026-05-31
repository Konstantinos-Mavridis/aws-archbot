"""Integration tests for the /generate endpoint.

All AWS calls are mocked via the shared conftest pipeline fixture.
These tests exercise the full FastAPI request → response cycle without
requiring real AWS credentials.
"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient


class TestHealthEndpoint:
    def test_health_returns_ok(self, client: TestClient) -> None:
        response = client.get("/health")
        assert response.status_code == 200
        assert response.json() == {"status": "ok"}


class TestGenerateEndpoint:
    def test_general_workload(self, client: TestClient) -> None:
        payload = {
            "workload_description": "A simple e-commerce site with product catalogue and checkout",
            "lens": "general",
            "non_functionals": {},
        }
        response = client.post("/generate", json=payload)
        assert response.status_code == 200
        data = response.json()
        assert data["architecture_summary"]
        assert isinstance(data["service_recommendations"], list)
        assert len(data["service_recommendations"]) >= 1
        assert data["mermaid_diagram"]
        assert "operational_excellence" in data["well_architected_checklist"]
        assert isinstance(data["cost_tiers"], list)

    def test_fsi_lens_workload(self, client: TestClient) -> None:
        payload = {
            "workload_description": "Regulated trade finance platform, CQRS, multi-region, 99.99% SLA",
            "lens": "fsi",
            "non_functionals": {
                "sla_percent": 99.99,
                "regions": 2,
                "rto_minutes": 15,
                "rpo_minutes": 5,
                "compliance_flags": ["PCI-DSS", "SOX"],
            },
        }
        response = client.post("/generate", json=payload)
        assert response.status_code == 200
        data = response.json()
        assert data["architecture_summary"]
        # FSI workloads should have security checklist items
        checklist = data["well_architected_checklist"]
        all_pillars = [
            "operational_excellence", "security", "reliability",
            "performance_efficiency", "cost_optimization", "sustainability",
        ]
        for pillar in all_pillars:
            assert pillar in checklist, f"Missing pillar: {pillar}"

    def test_healthcare_lens_workload(self, client: TestClient) -> None:
        payload = {
            "workload_description": "EHR system handling PHI data, HIPAA, single region",
            "lens": "healthcare",
            "non_functionals": {
                "compliance_flags": ["HIPAA"],
            },
        }
        response = client.post("/generate", json=payload)
        assert response.status_code == 200
        data = response.json()
        assert data["mermaid_diagram"]

    def test_description_too_short_returns_422(self, client: TestClient) -> None:
        payload = {"workload_description": "too short"}
        response = client.post("/generate", json=payload)
        assert response.status_code == 422

    def test_description_too_long_returns_422(self, client: TestClient) -> None:
        payload = {"workload_description": "x" * 2001}
        response = client.post("/generate", json=payload)
        assert response.status_code == 422

    def test_invalid_lens_returns_422(self, client: TestClient) -> None:
        payload = {
            "workload_description": "A basic data pipeline on AWS",
            "lens": "invalid_lens_value",
        }
        response = client.post("/generate", json=payload)
        assert response.status_code == 422

    def test_cost_tiers_have_required_fields(self, client: TestClient) -> None:
        payload = {
            "workload_description": "Serverless event-driven platform on AWS Lambda and SQS",
            "lens": "general",
        }
        response = client.post("/generate", json=payload)
        assert response.status_code == 200
        for tier in response.json()["cost_tiers"]:
            assert "tier" in tier
            assert "monthly_estimate_hint" in tier
            assert "assumptions" in tier

    def test_service_recommendations_have_required_fields(self, client: TestClient) -> None:
        payload = {
            "workload_description": "Real-time analytics platform using Kinesis and Redshift",
            "lens": "general",
        }
        response = client.post("/generate", json=payload)
        assert response.status_code == 200
        for rec in response.json()["service_recommendations"]:
            assert "category" in rec
            assert "service" in rec
            assert "reasoning" in rec
