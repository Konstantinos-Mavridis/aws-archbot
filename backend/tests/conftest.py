"""Shared pytest fixtures for ArchBot backend tests."""

from __future__ import annotations

import json
from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.rag_pipeline import RagPipeline


_SAMPLE_RESPONSE = {
    "architecture_summary": (
        "A regulated FSI trade finance platform using CQRS, multi-region active-active "
        "deployment across us-east-1 and eu-west-1, targeting 99.99% SLA."
    ),
    "service_recommendations": [
        {"category": "compute", "service": "AWS Fargate", "reasoning": "Serverless containers; no EC2 patch burden."},
        {"category": "messaging", "service": "Amazon MSK", "reasoning": "Managed Kafka for CQRS event bus."},
        {"category": "database", "service": "Amazon Aurora Global Database", "reasoning": "Sub-second RPO for multi-region."},
        {"category": "networking", "service": "AWS Global Accelerator", "reasoning": "Anycast routing for 99.99% SLA."},
    ],
    "mermaid_diagram": (
        "flowchart LR\n"
        "  user[Trader] --> ga[Global Accelerator]\n"
        "  ga --> alb1[ALB us-east-1]\n"
        "  ga --> alb2[ALB eu-west-1]\n"
        "  alb1 --> svc1[Command Service]\n"
        "  svc1 --> msk[Amazon MSK]\n"
        "  msk --> query[Query Service]\n"
        "  query --> aurora[(Aurora Global DB)]"
    ),
    "well_architected_checklist": {
        "operational_excellence": [
            {
                "question": "Do you use infrastructure as code for all resources?",
                "risk_level": "GOOD_PRACTICE",
                "finding": "CDK stacks cover all resources.",
                "improvement_suggestion": "Add CDK Aspects for org-wide guardrails.",
            }
        ],
        "security": [
            {
                "question": "Are customer-managed KMS keys used for sensitive data at rest?",
                "risk_level": "HIGH",
                "finding": "Not explicitly configured.",
                "improvement_suggestion": "Add CMK for Aurora, MSK, and S3 buckets; enforce via SCP.",
            }
        ],
        "reliability": [
            {
                "question": "Is the workload deployed across multiple Availability Zones and Regions?",
                "risk_level": "GOOD_PRACTICE",
                "finding": "Multi-region active-active specified.",
                "improvement_suggestion": "Implement Route 53 ARC readiness checks.",
            }
        ],
        "performance_efficiency": [],
        "cost_optimization": [
            {
                "question": "Are Compute Savings Plans applied to predictable Fargate usage?",
                "risk_level": "MEDIUM",
                "finding": "No Savings Plans mentioned.",
                "improvement_suggestion": "Purchase 1-year Compute Savings Plan after steady-state load profiling.",
            }
        ],
        "sustainability": [],
    },
    "cost_tiers": [
        {"tier": "dev", "monthly_estimate_hint": "Under $300/month", "assumptions": "Single region, minimal traffic, Fargate spot."},
        {"tier": "staging", "monthly_estimate_hint": "$800–$1,500/month", "assumptions": "Two regions, moderate load, no Savings Plans."},
        {"tier": "prod", "monthly_estimate_hint": "$5,000–$15,000/month", "assumptions": "Full multi-region, Aurora Global, MSK, GA, WAF."},
    ],
}


@pytest.fixture()
def mock_bedrock_response() -> dict:
    """Canonical Bedrock response payload used across test modules."""
    return {
        "body": MagicMock(
            read=lambda: json.dumps(
                {"content": [{"text": json.dumps(_SAMPLE_RESPONSE)}]}
            ).encode()
        )
    }


@pytest.fixture()
def pipeline(mock_bedrock_response: dict) -> RagPipeline:  # type: ignore[return]
    with patch("boto3.client") as mock_boto:
        instance = MagicMock()
        instance.invoke_model.return_value = mock_bedrock_response
        instance.retrieve.return_value = {"retrievalResults": []}
        mock_boto.return_value = instance
        yield RagPipeline()


@pytest.fixture()
def client(pipeline: RagPipeline) -> TestClient:
    """FastAPI TestClient with a fully mocked RagPipeline injected."""
    import app.main as main_module
    main_module._pipeline = pipeline  # inject mock pipeline
    return TestClient(app)
