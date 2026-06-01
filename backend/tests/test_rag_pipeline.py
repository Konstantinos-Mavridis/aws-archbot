"""Tests for the RAG pipeline (mocked AWS calls)."""

from __future__ import annotations

import json
from unittest.mock import MagicMock, patch

import pytest

from app.models import ArchitectureRequest
from app.rag_pipeline import RagPipeline


@pytest.fixture()
def local_pipeline(tmp_path) -> RagPipeline:  # type: ignore[type-arg]
    """RagPipeline configured for local Chroma + Ollama mode."""
    with (
        patch.dict(
            "os.environ",
            {
                "CHROMA_PATH": str(tmp_path / "chroma"),
                "OLLAMA_BASE_URL": "http://localhost:11434",
                "OLLAMA_MODEL": "llama3",
            },
        ),
        patch("app.rag_pipeline.RagPipeline._init_local_embed"),
    ):
        pipeline = RagPipeline()
        pipeline._local_embed_model = MagicMock()
        pipeline._local_embed_model.encode.return_value = MagicMock(
            tolist=lambda: [0.1] * 384
        )
        yield pipeline


@pytest.mark.asyncio()
async def test_retrieve_returns_empty_without_store() -> None:
    """With no store env vars, _retrieve returns []."""
    with patch.dict("os.environ", {}, clear=True):
        with patch("app.rag_pipeline.RagPipeline._init_local_embed"):
            pipeline = RagPipeline()
        request = ArchitectureRequest(workload_description="Simple REST API on EC2")
        chunks = await pipeline._retrieve(request)
    assert chunks == []


@pytest.mark.asyncio()
async def test_generate_ollama_calls_http(local_pipeline: RagPipeline) -> None:
    """_generate_ollama sends the correct payload to the Ollama API."""
    import httpx

    sample_json = json.dumps(
        {
            "architecture_summary": "ok",
            "service_recommendations": [],
            "mermaid_diagram": "flowchart LR\n  A-->B",
            "well_architected_checklist": {
                "operational_excellence": [],
                "security": [],
                "reliability": [],
                "performance_efficiency": [],
                "cost_optimization": [],
                "sustainability": [],
            },
            "cost_tiers": [],
        }
    )

    mock_response = MagicMock(spec=httpx.Response)
    mock_response.raise_for_status = MagicMock()
    mock_response.json.return_value = {"response": sample_json}

    with patch("httpx.AsyncClient.post", return_value=mock_response):
        request = ArchitectureRequest(workload_description="Microservices on EKS")
        result = await local_pipeline._generate_ollama(request, [])

    assert result == sample_json
