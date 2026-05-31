"""One-time ingestion script: chunk Well-Architected Framework documents,
generate embeddings via Bedrock, and store in the configured vector store.

Usage:
    python scripts/ingest_docs.py --lens general [--source-dir ./wa_docs] [--store kb|opensearch]
    python scripts/ingest_docs.py --lens fsi --store kb
    python scripts/ingest_docs.py --lens healthcare --store opensearch

Document sources (download manually before running):
    - AWS Well-Architected Framework:  https://docs.aws.amazon.com/wellarchitected/
    - FSI Lens:  https://docs.aws.amazon.com/wellarchitected/latest/financial-services-industry-lens/
    - Healthcare Lens: https://docs.aws.amazon.com/wellarchitected/latest/healthcare-industry-lens/

Save pages as .txt or .md files in --source-dir before running.

For the Bedrock Knowledge Base (--store kb):
    1. Chunks are uploaded to S3 as JSONL (one doc per line, Bedrock metadata schema).
    2. An ingestion job is started on the KB data source; the script polls until complete.
    Requires env vars: DOCS_S3_BUCKET, KNOWLEDGE_BASE_ID, KB_DATA_SOURCE_ID

For OpenSearch Serverless (--store opensearch):
    1. Chunks are embedded via Bedrock Titan Embeddings.
    2. Embeddings are bulk-indexed into the AOSS collection.
    Requires env vars: OPENSEARCH_ENDPOINT, VECTOR_INDEX_NAME
"""

from __future__ import annotations

import argparse
import json
import logging
import os
import time
from pathlib import Path
from typing import Iterator

import boto3
from opensearchpy import AWSV4SignerAuth, OpenSearch, RequestsHttpConnection
from requests_aws4auth import AWS4Auth

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")

_REGION = os.environ.get("AWS_REGION", "us-east-1")
_S3_BUCKET = os.environ.get("DOCS_S3_BUCKET", "archbot-wa-docs")
_KB_ID = os.environ.get("KNOWLEDGE_BASE_ID", "")
_KB_DS_ID = os.environ.get("KB_DATA_SOURCE_ID", "")
_OPENSEARCH_ENDPOINT = os.environ.get("OPENSEARCH_ENDPOINT", "")
_VECTOR_INDEX = os.environ.get("VECTOR_INDEX_NAME", "archbot-wa-index")
_EMBEDDING_MODEL = "amazon.titan-embed-text-v2:0"
_CHUNK_SIZE = 1500  # approximate tokens (words used as proxy)
_OVERLAP = 150
_VECTOR_DIM = 1024  # Titan v2 output dimension

# Pillar detection by keyword heuristic
_PILLAR_KEYWORDS: dict[str, list[str]] = {
    "operational_excellence": ["operational", "operations", "runbook", "observability", "deployment"],
    "security": ["security", "iam", "identity", "encryption", "kms", "audit", "compliance", "threat"],
    "reliability": ["reliability", "fault", "recovery", "rto", "rpo", "multi-region", "failover", "availability"],
    "performance_efficiency": ["performance", "latency", "throughput", "scaling", "auto scaling", "cache"],
    "cost_optimization": ["cost", "pricing", "savings", "reserved", "spot", "rightsizing", "budget"],
    "sustainability": ["sustainability", "carbon", "green", "energy", "power", "efficient"],
}


def _tag_pillar(text: str) -> str:
    lower = text.lower()
    for pillar, keywords in _PILLAR_KEYWORDS.items():
        if any(kw in lower for kw in keywords):
            return pillar
    return "general"


def _chunk_text(text: str, chunk_size: int = _CHUNK_SIZE, overlap: int = _OVERLAP) -> Iterator[str]:
    words = text.split()
    start = 0
    while start < len(words):
        end = min(start + chunk_size, len(words))
        yield " ".join(words[start:end])
        if end == len(words):
            break
        start += chunk_size - overlap


def _embed(text: str, bedrock_client: object) -> list[float]:
    body = json.dumps({"inputText": text})
    response = bedrock_client.invoke_model(  # type: ignore[attr-defined]
        modelId=_EMBEDDING_MODEL,
        contentType="application/json",
        accept="application/json",
        body=body,
    )
    return json.loads(response["body"].read())["embedding"]


def _build_chunks(source_files: list[Path], lens: str, bedrock_client: object) -> list[dict]:
    """Chunk all source files, tag metadata, and optionally embed."""
    chunks: list[dict] = []
    for path in source_files:
        logger.info("Processing %s", path.name)
        text = path.read_text(encoding="utf-8")
        for i, chunk in enumerate(_chunk_text(text)):
            pillar = _tag_pillar(chunk)
            chunks.append(
                {
                    "text": chunk,
                    "metadata": {"lens": lens, "pillar": pillar, "source": path.name, "chunk_index": i},
                }
            )
    logger.info("Built %d chunks from %d files", len(chunks), len(source_files))
    return chunks


# ---------------------------------------------------------------------------
# Store: Bedrock Knowledge Base via S3 + StartIngestionJob
# ---------------------------------------------------------------------------

def _upload_to_s3_for_kb(chunks: list[dict], lens: str, s3_client: object) -> str:
    """Upload chunks as JSONL in Bedrock Knowledge Base metadata format.

    Bedrock KB expects one document per JSONL line with keys:
        {"content": "...", "metadata": {"lens": ..., "pillar": ..., ...}}
    Returns the S3 key prefix uploaded.
    """
    lines = [
        json.dumps({"content": c["text"], "metadata": c["metadata"]})
        for c in chunks
    ]
    key = f"kb/{lens}/wa_chunks.jsonl"
    s3_client.put_object(  # type: ignore[attr-defined]
        Bucket=_S3_BUCKET,
        Key=key,
        Body="\n".join(lines).encode(),
        ContentType="application/x-ndjson",
    )
    logger.info("Uploaded %d chunks → s3://%s/%s", len(chunks), _S3_BUCKET, key)
    return key


def _start_kb_ingestion(bedrock_agent_client: object) -> str:
    """Trigger a Bedrock Knowledge Base StartIngestionJob and return job ID."""
    if not _KB_ID or not _KB_DS_ID:
        raise EnvironmentError("KNOWLEDGE_BASE_ID and KB_DATA_SOURCE_ID must be set for KB ingestion")
    response = bedrock_agent_client.start_ingestion_job(  # type: ignore[attr-defined]
        knowledgeBaseId=_KB_ID,
        dataSourceId=_KB_DS_ID,
    )
    job_id: str = response["ingestionJob"]["ingestionJobId"]
    logger.info("Started Bedrock KB ingestion job: %s", job_id)
    return job_id


def _poll_kb_ingestion(bedrock_agent_client: object, job_id: str, timeout_sec: int = 600) -> None:
    """Poll until the ingestion job reaches COMPLETE or FAILED."""
    start = time.time()
    while time.time() - start < timeout_sec:
        resp = bedrock_agent_client.get_ingestion_job(  # type: ignore[attr-defined]
            knowledgeBaseId=_KB_ID,
            dataSourceId=_KB_DS_ID,
            ingestionJobId=job_id,
        )
        status: str = resp["ingestionJob"]["status"]
        stats = resp["ingestionJob"].get("statistics", {})
        logger.info("KB ingestion status: %s | stats: %s", status, stats)
        if status == "COMPLETE":
            logger.info("Ingestion job %s completed successfully", job_id)
            return
        if status == "FAILED":
            failures = resp["ingestionJob"].get("failureReasons", [])
            raise RuntimeError(f"KB ingestion job {job_id} failed: {failures}")
        time.sleep(15)
    raise TimeoutError(f"KB ingestion job {job_id} did not complete within {timeout_sec}s")


def ingest_to_kb(chunks: list[dict], lens: str) -> None:
    s3 = boto3.client("s3", region_name=_REGION)
    bedrock_agent = boto3.client("bedrock-agent", region_name=_REGION)
    _upload_to_s3_for_kb(chunks, lens, s3)
    job_id = _start_kb_ingestion(bedrock_agent)
    _poll_kb_ingestion(bedrock_agent, job_id)


# ---------------------------------------------------------------------------
# Store: OpenSearch Serverless direct indexing
# ---------------------------------------------------------------------------

def _get_opensearch_client() -> OpenSearch:
    """Return an authenticated OpenSearch client for AOSS."""
    if not _OPENSEARCH_ENDPOINT:
        raise EnvironmentError("OPENSEARCH_ENDPOINT must be set for OpenSearch ingestion")
    session = boto3.Session()
    credentials = session.get_credentials().get_frozen_credentials()
    auth = AWS4Auth(
        credentials.access_key,
        credentials.secret_key,
        _REGION,
        "aoss",
        session_token=credentials.token,
    )
    return OpenSearch(
        hosts=[{"host": _OPENSEARCH_ENDPOINT.replace("https://", ""), "port": 443}],
        http_auth=auth,
        use_ssl=True,
        verify_certs=True,
        connection_class=RequestsHttpConnection,
        timeout=30,
    )


def _ensure_index(client: OpenSearch) -> None:
    """Create the k-NN index if it does not exist."""
    if client.indices.exists(index=_VECTOR_INDEX):
        logger.info("Index %s already exists — skipping creation", _VECTOR_INDEX)
        return
    body = {
        "settings": {
            "index.knn": True,
            "index.knn.space_type": "cosinesimil",
        },
        "mappings": {
            "properties": {
                "embedding": {
                    "type": "knn_vector",
                    "dimension": _VECTOR_DIM,
                    "method": {"name": "hnsw", "space_type": "cosinesimil",
                               "engine": "nmslib", "parameters": {"ef_construction": 128, "m": 16}},
                },
                "text": {"type": "text"},
                "lens": {"type": "keyword"},
                "pillar": {"type": "keyword"},
                "source": {"type": "keyword"},
                "chunk_index": {"type": "integer"},
            }
        },
    }
    client.indices.create(index=_VECTOR_INDEX, body=body)
    logger.info("Created k-NN index: %s", _VECTOR_INDEX)


def _bulk_index(client: OpenSearch, chunks_with_embeddings: list[dict]) -> None:
    """Bulk index chunks into OpenSearch."""
    actions: list[dict] = []
    for chunk in chunks_with_embeddings:
        actions.append({"index": {"_index": _VECTOR_INDEX}})
        actions.append({
            "embedding": chunk["embedding"],
            "text": chunk["text"],
            **chunk["metadata"],
        })
    response = client.bulk(body=actions)
    if response.get("errors"):
        failed = sum(1 for item in response["items"] if "error" in item.get("index", {}))
        logger.error("Bulk index completed with %d errors", failed)
    else:
        logger.info("Bulk indexed %d documents", len(chunks_with_embeddings))


def ingest_to_opensearch(chunks: list[dict], bedrock_client: object) -> None:
    client = _get_opensearch_client()
    _ensure_index(client)
    logger.info("Embedding %d chunks via Bedrock Titan...", len(chunks))
    for chunk in chunks:
        chunk["embedding"] = _embed(chunk["text"], bedrock_client)
    _bulk_index(client, chunks)


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def main() -> None:
    parser = argparse.ArgumentParser(description="Ingest WA docs into the vector store")
    parser.add_argument("--lens", required=True, choices=["general", "fsi", "healthcare"])
    parser.add_argument("--source-dir", default="./wa_docs",
                        help="Directory containing downloaded WA documents (.txt or .md)")
    parser.add_argument("--store", choices=["kb", "opensearch"], default="kb",
                        help="Vector store backend (default: kb = Bedrock Knowledge Base)")
    args = parser.parse_args()

    source_dir = Path(args.source_dir)
    source_files = list(source_dir.glob("*.txt")) + list(source_dir.glob("*.md"))
    if not source_files:
        logger.error("No .txt or .md files found in %s — download WA docs first", source_dir)
        raise SystemExit(1)

    bedrock = boto3.client("bedrock-runtime", region_name=_REGION)
    chunks = _build_chunks(source_files, args.lens, bedrock)

    if args.store == "kb":
        ingest_to_kb(chunks, args.lens)
    else:
        ingest_to_opensearch(chunks, bedrock)


if __name__ == "__main__":
    main()
