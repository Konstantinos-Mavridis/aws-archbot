"""ArchBot FastAPI application.

Serves as both a standalone ASGI app (uvicorn, Fargate) and an AWS Lambda
handler via Mangum. The single endpoint `/generate` performs RAG retrieval
over Well-Architected Framework documents and calls Amazon Bedrock (Claude)
to produce a structured architecture response.
"""

from __future__ import annotations

import logging

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from mangum import Mangum

from app.models import ArchitectureRequest, ArchitectureResponse
from app.rag_pipeline import RagPipeline

logger = logging.getLogger(__name__)

app = FastAPI(
    title="ArchBot",
    description="AI-powered AWS architecture advisor",
    version="0.1.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # tighten in production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

_pipeline: RagPipeline | None = None


def get_pipeline() -> RagPipeline:
    global _pipeline
    if _pipeline is None:
        _pipeline = RagPipeline()
    return _pipeline


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}


@app.post("/generate", response_model=ArchitectureResponse)
async def generate(request: ArchitectureRequest) -> ArchitectureResponse:
    """Generate a reference architecture from a workload description.

    Steps:
    1. Build a retrieval query from workload description + lens metadata.
    2. Retrieve top-N chunks from the vector store (Knowledge Base or OpenSearch).
    3. Construct a structured prompt with retrieved context.
    4. Call Amazon Bedrock (Claude) and parse the JSON response.
    5. Return the typed ArchitectureResponse.
    """
    pipeline = get_pipeline()
    try:
        return await pipeline.run(request)
    except Exception as exc:
        logger.exception("Pipeline error")
        raise HTTPException(status_code=500, detail=str(exc)) from exc


# Lambda entry point
handler = Mangum(app, lifespan="off")
