"""RAG pipeline: retrieval then generation.

Retrieval options (selected automatically via environment variables):
  Option A — Amazon Bedrock Knowledge Bases     (KNOWLEDGE_BASE_ID set)
  Option B — OpenSearch Serverless k-NN         (OPENSEARCH_ENDPOINT set)
  Option C — Chroma + sentence-transformers     (CHROMA_PATH set, local/dev mode)
  Demo     — empty context                      (none of the above)

Generation options:
  AWS     — Amazon Bedrock (Claude)             (OLLAMA_BASE_URL not set)
  Local   — Ollama HTTP API                     (OLLAMA_BASE_URL set)

See docs/adr/0002-rag-store-choice.md for the decision rationale.
"""

from __future__ import annotations

import json
import logging
import os
from typing import TYPE_CHECKING, Any, cast

import boto3
from mypy_boto3_bedrock_agent_runtime.type_defs import RetrievalFilterTypeDef
from opensearchpy import OpenSearch, RequestsHttpConnection
from requests_aws4auth import AWS4Auth
from tenacity import retry, stop_after_attempt, wait_exponential

from app.models import (
    ArchitectureRequest,
    ArchitectureResponse,
    Lens,
)

if TYPE_CHECKING:
    pass

logger = logging.getLogger(__name__)

# AWS-mode settings
# AWS_REGION is injected automatically by the Lambda runtime; read it here
# as a fallback for non-Lambda contexts (local dev, ECS, etc.).
_REGION = os.environ.get("AWS_REGION") or os.environ.get("AWS_DEFAULT_REGION", "us-east-1")
_MODEL_ID = os.environ.get(
    "BEDROCK_MODEL_ID",
    "anthropic.claude-3-5-sonnet-20241022-v2:0",
)
_KB_ID = os.environ.get("KNOWLEDGE_BASE_ID")              # Option A
_OPENSEARCH_ENDPOINT = os.environ.get("OPENSEARCH_ENDPOINT")  # Option B
_VECTOR_INDEX = os.environ.get("VECTOR_INDEX_NAME", "archbot-wa-index")
_EMBEDDING_MODEL = "amazon.titan-embed-text-v2:0"
_VECTOR_DIM = 1024
_TOP_K = int(os.environ.get("RAG_TOP_K", "20"))

# Local-mode settings (Option C)
_CHROMA_PATH = os.environ.get("CHROMA_PATH")              # Option C
_CHROMA_COLLECTION = "archbot-wa"
_LOCAL_EMBED_MODEL = "all-MiniLM-L6-v2"                   # ~90 MB, runs on CPU

# Ollama generation settings
_OLLAMA_BASE_URL = os.environ.get("OLLAMA_BASE_URL")       # e.g. http://ollama:11434
_OLLAMA_MODEL = os.environ.get("OLLAMA_MODEL", "llama3")

# Lens-specific system prompt addenda
_LENS_INSTRUCTIONS: dict[Lens, str] = {
    Lens.GENERAL: "",
    Lens.FSI: (
        "This workload operates in a regulated Financial Services (FSI) context. "
        "Emphasise: data residency requirements, encryption at rest and in transit "
        "(AWS KMS, customer-managed keys), segregation of duties, immutable audit "
        "logging (CloudTrail + S3 Object Lock), PCI-DSS / SOX controls, and trade-data "
        "latency optimisation. Reference the AWS FSI Lens where applicable."
    ),
    Lens.HEALTHCARE: (
        "This workload processes Protected Health Information (PHI) in a Healthcare context. "
        "Emphasise: HIPAA safeguards, PHI de-identification strategies, VPC-isolated data "
        "tiers, access traceability (CloudTrail, audit logs), data lifecycle policies, "
        "and AWS HIPAA-eligible service selection. Reference the AWS Healthcare Lens."
    ),
}

_SYSTEM_PROMPT = """
You are an AWS Solutions Architect generating reference architectures and
Well-Architected Framework reviews. Use ONLY the context snippets provided below.
Output a single valid JSON object — no markdown fences, no explanation outside JSON —
with exactly these top-level keys:
  architecture_summary, service_recommendations, mermaid_diagram,
  well_architected_checklist, cost_tiers.

JSON schema:
{schema}

{lens_instructions}
"""


class RagPipeline:
    """Orchestrates retrieval and generation.

    Instantiated once at application startup (singleton via FastAPI lifespan).
    Lazy-loads heavy local deps (chromadb, sentence-transformers) only when
    CHROMA_PATH is set, so the production Lambda image stays lean.
    """

    def __init__(self) -> None:
        # AWS clients — only constructed when not in pure local mode
        if not (_CHROMA_PATH and _OLLAMA_BASE_URL):
            self._bedrock_agent = boto3.client("bedrock-agent-runtime", region_name=_REGION)
            self._bedrock_runtime = boto3.client("bedrock-runtime", region_name=_REGION)
        else:
            self._bedrock_agent = None  # type: ignore[assignment]
            self._bedrock_runtime = None  # type: ignore[assignment]

        # Local embedding model — loaded once, reused across requests
        self._local_embed_model: Any = None
        if _CHROMA_PATH:
            self._init_local_embed()

    def _init_local_embed(self) -> None:
        """Lazily load sentence-transformers (only in local mode)."""
        try:
            from sentence_transformers import SentenceTransformer  # type: ignore[import-untyped]
            self._local_embed_model = SentenceTransformer(_LOCAL_EMBED_MODEL)
            logger.info("Loaded local embedding model: %s", _LOCAL_EMBED_MODEL)
        except ImportError:
            logger.warning(
                "sentence-transformers not installed — Chroma retrieval disabled. "
                "Install with: pip install -e '.[local]'"
            )

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    async def run(self, request: ArchitectureRequest) -> ArchitectureResponse:
        """Execute the full RAG -> generation pipeline."""
        context_chunks = await self._retrieve(request)
        raw_json = await self._generate(request, context_chunks)
        return ArchitectureResponse.model_validate_json(raw_json)

    # ------------------------------------------------------------------
    # Retrieval
    # ------------------------------------------------------------------

    async def _retrieve(self, request: ArchitectureRequest) -> list[dict[str, Any]]:
        """Select the appropriate retrieval backend."""
        query = self._build_query(request)
        if _KB_ID:
            return self._retrieve_from_knowledge_base(query, request.lens)
        if _OPENSEARCH_ENDPOINT:
            return self._retrieve_from_opensearch(query, request.lens)
        if _CHROMA_PATH and self._local_embed_model is not None:
            return self._retrieve_from_chroma(query, request.lens)
        logger.warning("No RAG store configured — using empty context (demo mode)")
        return []

    def _build_query(self, request: ArchitectureRequest) -> str:
        parts = [request.workload_description]
        nfr = request.non_functionals
        if nfr.sla_percent:
            parts.append(f"SLA {nfr.sla_percent}%")
        if nfr.regions and nfr.regions > 1:
            parts.append(f"multi-region {nfr.regions} regions")
        if nfr.compliance_flags:
            parts.append(" ".join(nfr.compliance_flags))
        return " ".join(parts)

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=1, max=8))
    def _retrieve_from_knowledge_base(self, query: str, lens: Lens) -> list[dict[str, Any]]:
        """Option A: Bedrock Knowledge Base Retrieve API."""
        filter_expr: dict[str, Any] = {"equals": {"key": "lens", "value": lens.value}}
        if lens != Lens.GENERAL:
            filter_expr = {
                "orAll": [
                    {"equals": {"key": "lens", "value": "general"}},
                    {"equals": {"key": "lens", "value": lens.value}},
                ]
            }
        # _KB_ID is guaranteed non-None here (caller checks before dispatching)
        kb_id = _KB_ID or ""
        response = self._bedrock_agent.retrieve(
            knowledgeBaseId=kb_id,
            retrievalQuery={"text": query},
            retrievalConfiguration={
                "vectorSearchConfiguration": {
                    "numberOfResults": _TOP_K,
                    # cast: boto3 TypedDict is overly restrictive; our dict is
                    # structurally compatible with RetrievalFilterTypeDef at runtime.
                    "filter": cast(RetrievalFilterTypeDef, filter_expr),
                }
            },
        )
        return [
            {
                "text": r["content"]["text"],
                "score": r["score"],
                "source": r.get("location", {}).get("s3Location", {}).get("uri", ""),
                "metadata": r.get("metadata", {}),
            }
            for r in response.get("retrievalResults", [])
        ]

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=1, max=8))
    def _retrieve_from_opensearch(self, query: str, lens: Lens) -> list[dict[str, Any]]:
        """Option B: OpenSearch Serverless k-NN query."""
        embed_resp = self._bedrock_runtime.invoke_model(
            modelId=_EMBEDDING_MODEL,
            contentType="application/json",
            accept="application/json",
            body=json.dumps({"inputText": query}),
        )
        query_vector: list[float] = json.loads(embed_resp["body"].read())["embedding"]
        lens_values = ["general"]
        if lens != Lens.GENERAL:
            lens_values.append(lens.value)
        os_query: dict[str, Any] = {
            "size": _TOP_K,
            "query": {
                "bool": {
                    "must": [{"knn": {"embedding": {"vector": query_vector, "k": _TOP_K}}}],
                    "filter": [{"terms": {"lens": lens_values}}],
                }
            },
        }
        session = boto3.Session()
        raw_creds = session.get_credentials()
        if raw_creds is None:
            raise RuntimeError("No AWS credentials found for OpenSearch Serverless request")
        credentials = raw_creds.get_frozen_credentials()
        auth = AWS4Auth(
            credentials.access_key,
            credentials.secret_key,
            _REGION,
            "aoss",
            session_token=credentials.token,
        )
        # _OPENSEARCH_ENDPOINT is guaranteed non-None here (caller checks)
        endpoint = _OPENSEARCH_ENDPOINT or ""
        os_client = OpenSearch(
            hosts=[{"host": endpoint.replace("https://", ""), "port": 443}],
            http_auth=auth,
            use_ssl=True,
            verify_certs=True,
            connection_class=RequestsHttpConnection,
            timeout=10,
        )
        response = os_client.search(index=_VECTOR_INDEX, body=os_query)
        return [
            {
                "text": hit["_source"]["text"],
                "score": hit["_score"],
                "source": hit["_source"].get("source", ""),
                "metadata": {
                    "lens": hit["_source"].get("lens", ""),
                    "pillar": hit["_source"].get("pillar", ""),
                },
            }
            for hit in response["hits"]["hits"]
        ]

    def _retrieve_from_chroma(
        self, query: str, lens: Lens
    ) -> list[dict[str, Any]]:
        """Option C: Chroma persistent vector DB with local sentence-transformer embeddings."""
        import chromadb  # type: ignore[import-untyped]

        query_vector: list[float] = self._local_embed_model.encode(query).tolist()
        client = chromadb.PersistentClient(path=_CHROMA_PATH)
        collection = client.get_or_create_collection(
            name=_CHROMA_COLLECTION,
            metadata={"hnsw:space": "cosine"},
        )
        lens_values = ["general"]
        if lens != Lens.GENERAL:
            lens_values.append(lens.value)

        where_filter: dict[str, Any] = (
            {"lens": {"$in": lens_values}}
            if len(lens_values) > 1
            else {"lens": lens_values[0]}
        )
        try:
            results = collection.query(
                query_embeddings=[query_vector],
                n_results=min(_TOP_K, collection.count()),
                where=where_filter,
                include=["documents", "metadatas", "distances"],
            )
        except Exception:  # noqa: BLE001
            logger.warning("Chroma collection empty — run ingest_docs.py first")
            return []

        docs: list[str] = results["documents"][0]
        metas: list[dict[str, Any]] = results["metadatas"][0]
        distances: list[float] = results["distances"][0]
        return [
            {
                "text": doc,
                "score": round(1.0 - dist, 4),
                "source": meta.get("source", ""),
                "metadata": {
                    "lens": meta.get("lens", ""),
                    "pillar": meta.get("pillar", ""),
                },
            }
            for doc, meta, dist in zip(docs, metas, distances, strict=True)
        ]

    # ------------------------------------------------------------------
    # Generation
    # ------------------------------------------------------------------

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=2, max=16))
    async def _generate(self, request: ArchitectureRequest, chunks: list[dict[str, Any]]) -> str:
        """Dispatch to Ollama (local) or Bedrock (AWS)."""
        if _OLLAMA_BASE_URL:
            return await self._generate_ollama(request, chunks)
        return self._generate_bedrock(request, chunks)

    def _build_prompt_parts(
        self, request: ArchitectureRequest, chunks: list[dict[str, Any]]
    ) -> tuple[str, str]:
        """Return (system_prompt, user_message) shared by both generation paths."""
        context_block = "\n\n".join(
            f"[{i+1}] (source: {c.get('source','')}, "
            f"lens: {c.get('metadata',{}).get('lens','')}, "
            f"pillar: {c.get('metadata',{}).get('pillar','')})\n{c['text']}"
            for i, c in enumerate(chunks)
        ) or "[No context retrieved — operating in demo mode]"

        schema = ArchitectureResponse.model_json_schema()
        system_prompt = _SYSTEM_PROMPT.format(
            schema=json.dumps(schema, indent=2),
            lens_instructions=_LENS_INSTRUCTIONS[request.lens],
        )
        user_message = (
            f"Workload description: {request.workload_description}\n\n"
            f"Non-functional requirements: {request.non_functionals.model_dump_json()}\n\n"
            f"Lens: {request.lens.value}\n\n"
            f"Retrieved context:\n{context_block}"
        )
        return system_prompt, user_message

    def _generate_bedrock(self, request: ArchitectureRequest, chunks: list[dict[str, Any]]) -> str:
        """Call Amazon Bedrock (Claude) — production path."""
        system_prompt, user_message = self._build_prompt_parts(request, chunks)
        body = json.dumps({
            "anthropic_version": "bedrock-2023-05-31",
            "max_tokens": 8192,
            "system": system_prompt,
            "messages": [{"role": "user", "content": user_message}],
        })
        response = self._bedrock_runtime.invoke_model(
            modelId=_MODEL_ID,
            contentType="application/json",
            accept="application/json",
            body=body,
        )
        result: dict[str, Any] = json.loads(response["body"].read())
        return str(result["content"][0]["text"])

    async def _generate_ollama(
        self, request: ArchitectureRequest, chunks: list[dict[str, Any]]
    ) -> str:
        """Call Ollama local API — dev / local mode path."""
        import httpx  # type: ignore[import-untyped]

        system_prompt, user_message = self._build_prompt_parts(request, chunks)
        full_prompt = (
            f"{system_prompt}\n\nUser: {user_message}\n\n"
            "Assistant (output valid JSON only, no markdown fences):"
        )
        async with httpx.AsyncClient(timeout=180.0) as client:
            resp = await client.post(
                f"{_OLLAMA_BASE_URL}/api/generate",
                json={
                    "model": _OLLAMA_MODEL,
                    "prompt": full_prompt,
                    "stream": False,
                    "options": {"temperature": 0.2, "num_predict": 4096},
                },
            )
            resp.raise_for_status()
        return str(resp.json()["response"])
