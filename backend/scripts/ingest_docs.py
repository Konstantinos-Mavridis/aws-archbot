"""One-time ingestion script: chunk Well-Architected Framework documents,
generate embeddings via Bedrock, and store in the configured vector store.

Usage:
    python scripts/ingest_docs.py --lens general [--source-dir ./docs]
    python scripts/ingest_docs.py --lens fsi
    python scripts/ingest_docs.py --lens healthcare

Document sources:
    - AWS Well-Architected Framework:  https://docs.aws.amazon.com/wellarchitected/
    - FSI Lens:  https://docs.aws.amazon.com/wellarchitected/latest/financial-services-industry-lens/
    - Healthcare Lens: https://docs.aws.amazon.com/wellarchitected/latest/healthcare-industry-lens/

This script downloads, chunks (~1.5k tokens), tags, embeds, and uploads
to S3 (for Bedrock KB sync) or directly to OpenSearch Serverless.
"""

from __future__ import annotations

import argparse
import json
import logging
import os
import textwrap
from pathlib import Path

import boto3

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO)

_REGION = os.environ.get("AWS_REGION", "us-east-1")
_S3_BUCKET = os.environ.get("DOCS_S3_BUCKET", "archbot-wa-docs")
_EMBEDDING_MODEL = "amazon.titan-embed-text-v2:0"
_CHUNK_SIZE = 1500  # tokens (approximate)
_OVERLAP = 150

# Pillar tags for metadata labelling
_PILLAR_KEYWORDS: dict[str, list[str]] = {
    "operational_excellence": ["operational", "operations", "runbook", "observability"],
    "security": ["security", "iam", "encryption", "kms", "audit", "compliance"],
    "reliability": ["reliability", "fault", "recovery", "rto", "rpo", "multi-region"],
    "performance_efficiency": ["performance", "latency", "scaling", "auto scaling"],
    "cost_optimization": ["cost", "pricing", "savings", "reserved", "spot"],
    "sustainability": ["sustainability", "carbon", "green", "energy"],
}


def tag_pillar(text: str) -> str:
    lower = text.lower()
    for pillar, keywords in _PILLAR_KEYWORDS.items():
        if any(kw in lower for kw in keywords):
            return pillar
    return "general"


def chunk_text(text: str, chunk_size: int = _CHUNK_SIZE, overlap: int = _OVERLAP) -> list[str]:
    """Simple word-boundary chunking."""
    words = text.split()
    chunks: list[str] = []
    start = 0
    while start < len(words):
        end = min(start + chunk_size, len(words))
        chunks.append(" ".join(words[start:end]))
        start += chunk_size - overlap
    return chunks


def embed(text: str, client: "boto3.client") -> list[float]:  # type: ignore[name-defined]
    body = json.dumps({"inputText": text})
    response = client.invoke_model(
        modelId=_EMBEDDING_MODEL,
        contentType="application/json",
        accept="application/json",
        body=body,
    )
    return json.loads(response["body"].read())["embedding"]


def upload_to_s3(chunks: list[dict], lens: str, s3_client: "boto3.client") -> None:  # type: ignore[name-defined]
    for i, chunk in enumerate(chunks):
        key = f"{lens}/{chunk['pillar']}/chunk_{i:05d}.json"
        s3_client.put_object(
            Bucket=_S3_BUCKET,
            Key=key,
            Body=json.dumps(chunk),
            ContentType="application/json",
        )
    logger.info("Uploaded %d chunks for lens=%s to s3://%s", len(chunks), lens, _S3_BUCKET)


def ingest(lens: str, source_dir: Path) -> None:
    bedrock = boto3.client("bedrock-runtime", region_name=_REGION)
    s3 = boto3.client("s3", region_name=_REGION)

    source_files = list(source_dir.glob("*.txt")) + list(source_dir.glob("*.md"))
    if not source_files:
        logger.warning("No source documents found in %s", source_dir)
        return

    all_chunks: list[dict] = []
    for path in source_files:
        text = path.read_text(encoding="utf-8")
        for chunk_text_ in chunk_text(text):
            pillar = tag_pillar(chunk_text_)
            vector = embed(chunk_text_, bedrock)
            all_chunks.append(
                {
                    "text": chunk_text_,
                    "embedding": vector,
                    "lens": lens,
                    "pillar": pillar,
                    "source": path.name,
                }
            )

    upload_to_s3(all_chunks, lens, s3)
    logger.info("Ingestion complete: %d total chunks", len(all_chunks))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Ingest WA docs into the vector store")
    parser.add_argument(
        "--lens",
        required=True,
        choices=["general", "fsi", "healthcare"],
        help="Which lens to ingest",
    )
    parser.add_argument(
        "--source-dir",
        default="./wa_docs",
        help="Directory containing downloaded WA documents (.txt or .md)",
    )
    args = parser.parse_args()
    ingest(args.lens, Path(args.source_dir))
