"""One-time ingestion script: chunk Well-Architected Framework documents,
generate embeddings, and store in the configured vector store.

Usage:
    # AWS mode (Bedrock Knowledge Base)
    python scripts/ingest_docs.py --lens general [--source-dir ./wa_docs] [--store kb]

    # AWS mode (OpenSearch Serverless)
    python scripts/ingest_docs.py --lens fsi --store opensearch

    # Local mode (no AWS account — Chroma + sentence-transformers)
    python scripts/ingest_docs.py --lens general --store chroma
    python scripts/ingest_docs.py --lens fsi --store chroma

Document sources (download manually before running):
    - AWS Well-Architected Framework:  https://docs.aws.amazon.com/wellarchitected/
    - FSI Lens:  https://docs.aws.amazon.com/wellarchitected/latest/financial-services-industry-lens/
    - Healthcare Lens: https://docs.aws.amazon.com/wellarchitected/latest/healthcare-industry-lens/

Save pages as .txt or .md files in --source-dir before running.

For --store chroma:
    - Requires the [local] extras: pip install -e '.[local]'
    - CHROMA_PATH env var determines where the DB is persisted
      (default: ./chroma_db)

For --store kb:
    Requires: DOCS_S3_BUCKET, KNOWLEDGE_BASE_ID, KB_DATA_SOURCE_ID

For --store opensearch:
    Requires: OPENSEARCH_ENDPOINT, VECTOR_INDEX_NAME
"""

from __future__ import annotations

import argparse
import json
import logging
import os
import time
from collections.abc import Iterator
from pathlib import Path

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")

_REGION = os.environ.get("AWS_REGION", "us-east-1")
_S3_BUCKET = os.environ.get("DOCS_S3_BUCKET", "archbot-wa-docs")
_KB_ID = os.environ.get("KNOWLEDGE_BASE_ID", "")
_KB_DS_ID = os.environ.get("KB_DATA_SOURCE_ID", "")
_OPENSEARCH_ENDPOINT = os.environ.get("OPENSEARCH_ENDPOINT", "")
_VECTOR_INDEX = os.environ.get("VECTOR_INDEX_NAME", "archbot-wa-index")
_EMBEDDING_MODEL = "amazon.titan-embed-text-v2:0"
_CHUNK_SIZE = 1500
_OVERLAP = 150
_VECTOR_DIM = 1024

# Local mode
_CHROMA_PATH = os.environ.get("CHROMA_PATH", "./chroma_db")
_CHROMA_COLLECTION = "archbot-wa"
_LOCAL_EMBED_MODEL = "all-MiniLM-L6-v2"

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


def _build_chunks(source_files: list[Path], lens: str) -> list[dict]:
    """Chunk all source files and tag with pillar metadata. No embedding here."""
    chunks: list[dict] = []
    for path in source_files:
        logger.info("Processing %s", path.name)
        text = path.read_text(encoding="utf-8")
        for i, chunk in enumerate(_chunk_text(text)):
            chunks.append({
                "text": chunk,
                "metadata": {"lens": lens, "pillar": _tag_pillar(chunk), "source": path.name, "chunk_index": i},
            })
    logger.info("Built %d chunks from %d files", len(chunks), len(source_files))
    return chunks


# ---------------------------------------------------------------------------
# Store: Bedrock Knowledge Base
# ---------------------------------------------------------------------------

def _upload_to_s3_for_kb(chunks: list[dict], lens: str, s3_client: object) -> None:
    lines = [json.dumps({"content": c["text"], "metadata": c["metadata"]}) for c in chunks]
    key = f"kb/{lens}/wa_chunks.jsonl"
    s3_client.put_object(  # type: ignore[attr-defined]
        Bucket=_S3_BUCKET, Key=key,
        Body="\n".join(lines).encode(),
        ContentType="application/x-ndjson",
    )
    logger.info("Uploaded %d chunks → s3://%s/%s", len(chunks), _S3_BUCKET, key)


def _start_kb_ingestion(bedrock_agent_client: object) -> str:
    if not _KB_ID or not _KB_DS_ID:
        raise OSError("KNOWLEDGE_BASE_ID and KB_DATA_SOURCE_ID must be set")
    resp = bedrock_agent_client.start_ingestion_job(  # type: ignore[attr-defined]
        knowledgeBaseId=_KB_ID, dataSourceId=_KB_DS_ID,
    )
    job_id: str = resp["ingestionJob"]["ingestionJobId"]
    logger.info("Started KB ingestion job: %s", job_id)
    return job_id


def _poll_kb_ingestion(bedrock_agent_client: object, job_id: str, timeout_sec: int = 600) -> None:
    start = time.time()
    while time.time() - start < timeout_sec:
        resp = bedrock_agent_client.get_ingestion_job(  # type: ignore[attr-defined]
            knowledgeBaseId=_KB_ID, dataSourceId=_KB_DS_ID, ingestionJobId=job_id,
        )
        status: str = resp["ingestionJob"]["status"]
        logger.info("KB ingestion status: %s", status)
        if status == "COMPLETE":
            return
        if status == "FAILED":
            raise RuntimeError(f"KB ingestion failed: {resp['ingestionJob'].get('failureReasons', [])}")
        time.sleep(15)
    raise TimeoutError(f"KB ingestion {job_id} timed out after {timeout_sec}s")


def ingest_to_kb(chunks: list[dict], lens: str) -> None:
    import boto3
    s3 = boto3.client("s3", region_name=_REGION)
    bedrock_agent = boto3.client("bedrock-agent", region_name=_REGION)
    _upload_to_s3_for_kb(chunks, lens, s3)
    job_id = _start_kb_ingestion(bedrock_agent)
    _poll_kb_ingestion(bedrock_agent, job_id)


# ---------------------------------------------------------------------------
# Store: OpenSearch Serverless
# ---------------------------------------------------------------------------

def _get_opensearch_client() -> object:
    import boto3
    from opensearchpy import OpenSearch, RequestsHttpConnection
    from requests_aws4auth import AWS4Auth
    if not _OPENSEARCH_ENDPOINT:
        raise OSError("OPENSEARCH_ENDPOINT must be set")
    creds = boto3.Session().get_credentials().get_frozen_credentials()
    auth = AWS4Auth(creds.access_key, creds.secret_key, _REGION, "aoss", session_token=creds.token)
    return OpenSearch(
        hosts=[{"host": _OPENSEARCH_ENDPOINT.replace("https://", ""), "port": 443}],
        http_auth=auth, use_ssl=True, verify_certs=True,
        connection_class=RequestsHttpConnection, timeout=30,
    )


def _ensure_index(client: object) -> None:
    from opensearchpy import OpenSearch
    _client: OpenSearch = client  # type: ignore[assignment]
    if _client.indices.exists(index=_VECTOR_INDEX):
        return
    body = {
        "settings": {"index.knn": True, "index.knn.space_type": "cosinesimil"},
        "mappings": {"properties": {
            "embedding": {"type": "knn_vector", "dimension": _VECTOR_DIM,
                          "method": {"name": "hnsw", "space_type": "cosinesimil",
                                     "engine": "nmslib", "parameters": {"ef_construction": 128, "m": 16}}},
            "text": {"type": "text"}, "lens": {"type": "keyword"},
            "pillar": {"type": "keyword"}, "source": {"type": "keyword"},
            "chunk_index": {"type": "integer"},
        }},
    }
    _client.indices.create(index=_VECTOR_INDEX, body=body)
    logger.info("Created k-NN index: %s", _VECTOR_INDEX)


def _embed_bedrock(text: str) -> list[float]:
    import boto3
    bedrock = boto3.client("bedrock-runtime", region_name=_REGION)
    resp = bedrock.invoke_model(
        modelId=_EMBEDDING_MODEL, contentType="application/json",
        accept="application/json", body=json.dumps({"inputText": text}),
    )
    return json.loads(resp["body"].read())["embedding"]


def ingest_to_opensearch(chunks: list[dict]) -> None:
    from opensearchpy import OpenSearch
    client: OpenSearch = _get_opensearch_client()  # type: ignore[assignment]
    _ensure_index(client)
    logger.info("Embedding %d chunks via Bedrock Titan...", len(chunks))
    actions: list[dict] = []
    for chunk in chunks:
        embedding = _embed_bedrock(chunk["text"])
        actions.append({"index": {"_index": _VECTOR_INDEX}})
        actions.append({"embedding": embedding, "text": chunk["text"], **chunk["metadata"]})
    resp = client.bulk(body=actions)
    if resp.get("errors"):
        failed = sum(1 for item in resp["items"] if "error" in item.get("index", {}))
        logger.error("Bulk index: %d errors", failed)
    else:
        logger.info("Indexed %d docs into OpenSearch", len(chunks))


# ---------------------------------------------------------------------------
# Store: Chroma (local / no AWS)
# ---------------------------------------------------------------------------

def ingest_to_chroma(chunks: list[dict]) -> None:
    """Index chunks into a local Chroma persistent vector DB.

    Embeddings are generated with sentence-transformers (all-MiniLM-L6-v2),
    which runs on CPU with no external API calls.
    Requires: pip install -e '.[local]'
    """
    try:
        import chromadb  # type: ignore[import]
        from sentence_transformers import SentenceTransformer  # type: ignore[import]
    except ImportError as exc:
        raise SystemExit(
            "Local extras not installed. Run: pip install -e '.[local]'"
        ) from exc

    logger.info("Loading local embedding model: %s", _LOCAL_EMBED_MODEL)
    model = SentenceTransformer(_LOCAL_EMBED_MODEL)

    client = chromadb.PersistentClient(path=_CHROMA_PATH)
    collection = client.get_or_create_collection(
        name=_CHROMA_COLLECTION,
        metadata={"hnsw:space": "cosine"},
    )

    logger.info("Embedding and indexing %d chunks into Chroma at %s...", len(chunks), _CHROMA_PATH)
    batch_size = 64
    for batch_start in range(0, len(chunks), batch_size):
        batch = chunks[batch_start : batch_start + batch_size]
        texts = [c["text"] for c in batch]
        embeddings = model.encode(texts, show_progress_bar=False).tolist()
        ids = [
            f"{c['metadata']['lens']}-{c['metadata']['source']}-{c['metadata']['chunk_index']}"
            for c in batch
        ]
        collection.add(
            ids=ids,
            documents=texts,
            embeddings=embeddings,
            metadatas=[c["metadata"] for c in batch],
        )
        logger.info("Indexed batch %d-%d", batch_start, batch_start + len(batch))

    logger.info("Done. Chroma collection '%s' now has %d documents.", _CHROMA_COLLECTION, collection.count())


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def main() -> None:
    parser = argparse.ArgumentParser(description="Ingest WA docs into the vector store")
    parser.add_argument("--lens", required=True, choices=["general", "fsi", "healthcare"])
    parser.add_argument("--source-dir", default="./wa_docs",
                        help="Directory containing .txt or .md WA documents")
    parser.add_argument("--store", choices=["kb", "opensearch", "chroma"], default="kb",
                        help="Vector store backend (default: kb)")
    args = parser.parse_args()

    source_dir = Path(args.source_dir)
    source_files = list(source_dir.glob("*.txt")) + list(source_dir.glob("*.md"))
    if not source_files:
        logger.error("No .txt or .md files found in %s — download WA docs first", source_dir)
        raise SystemExit(1)

    chunks = _build_chunks(source_files, args.lens)

    if args.store == "kb":
        ingest_to_kb(chunks, args.lens)
    elif args.store == "opensearch":
        ingest_to_opensearch(chunks)
    else:
        ingest_to_chroma(chunks)


if __name__ == "__main__":
    main()
