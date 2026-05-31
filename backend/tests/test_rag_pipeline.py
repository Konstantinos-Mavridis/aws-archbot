"""Tests for the RAG pipeline (mocked AWS calls)."""

from __future__ import annotations

import json
from unittest.mock import MagicMock, patch

import pytest

from app.models import ArchitectureRequest, Lens
from app.rag_pipeline import RagPipeline


_SAMPLE_RESPONSE = {
    "architecture_summary": "A simple web app on ECS Fargate.",
    "service_recommendations": [
        {"category": "compute", "service": "AWS Fargate", "reasoning": "Serverless containers"}
    ],
    "mermaid_diagram": "flowchart LR\n  user --> cf[CloudFront]",
    "well_architected_checklist": {
        "operational_excellence": [],
        "security": [],
        "reliability": [],
        "performance_efficiency": [],
        "cost_optimization": [],
        "sustainability": [],
    },
    "cost_tiers": [
        {"tier": "dev", "monthly_estimate_hint": "Under $50", "assumptions": "minimal traffic"}
    ],
}


@pytest.fixture()
def pipeline() -> RagPipeline:
    with patch("boto3.client"):
        return RagPipeline()


@pytest.mark.asyncio
async def test_run_no_store(pipeline: RagPipeline) -> None:
    """Pipeline should succeed with empty context (demo mode)."""
    bedrock_response = {
        "body": MagicMock(read=lambda: json.dumps({"content": [{"text": json.dumps(_SAMPLE_RESPONSE)}]}).encode())
    }
    pipeline._bedrock_runtime.invoke_model = MagicMock(return_value=bedrock_response)

    req = ArchitectureRequest(workload_description="A basic e-commerce website on AWS")
    result = await pipeline.run(req)
    assert result.architecture_summary
    assert len(result.service_recommendations) >= 1
