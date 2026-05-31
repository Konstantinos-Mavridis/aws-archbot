"""RAG pipeline: retrieval from Bedrock Knowledge Base (or OpenSearch)
then generation via Amazon Bedrock (Claude).

Retrieval options (controlled by environment variables):
  - Option A (default): Amazon Bedrock Knowledge Bases — fully managed,
    zero vector-index maintenance, native AWS integration.
  - Option B: OpenSearch Serverless vector index — more flexibility,
    supports custom metadata filters, lower latency for complex queries.

See docs/adr/0002-rag-store-choice.md for the decision rationale.
"""

from __future__ import annotations

import json
import logging
import os

import boto3
from tenacity import retry, stop_after_attempt, wait_exponential

from app.models import (
    ArchitectureRequest,
    ArchitectureResponse,
    Lens,
)

logger = logging.getLogger(__name__)

_REGION = os.environ.get("AWS_REGION", "us-east-1")
_MODEL_ID = os.environ.get(
    "BEDROCK_MODEL_ID",
    "anthropic.claude-3-5-sonnet-20241022-v2:0",
)
_KB_ID = os.environ.get("KNOWLEDGE_BASE_ID")  # Option A
_OPENSEARCH_ENDPOINT = os.environ.get("OPENSEARCH_ENDPOINT")  # Option B
_VECTOR_INDEX = os.environ.get("VECTOR_INDEX_NAME", "archbot-wa-index")
_TOP_K = int(os.environ.get("RAG_TOP_K", "20"))

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
    """Orchestrates retrieval and Bedrock generation."""

    def __init__(self) -> None:
        self._bedrock_agent = boto3.client("bedrock-agent-runtime", region_name=_REGION)
        self._bedrock_runtime = boto3.client("bedrock-runtime", region_name=_REGION)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    async def run(self, request: ArchitectureRequest) -> ArchitectureResponse:
        """Execute the full RAG → generation pipeline."""
        context_chunks = await self._retrieve(request)
        raw_json = await self._generate(request, context_chunks)
        return ArchitectureResponse.model_validate_json(raw_json)

    # ------------------------------------------------------------------
    # Retrieval
    # ------------------------------------------------------------------

    async def _retrieve(self, request: ArchitectureRequest) -> list[dict]:
        """Retrieve relevant WA chunks for the workload + lens."""
        query = self._build_query(request)
        if _KB_ID:
            return self._retrieve_from_knowledge_base(query, request.lens)
        if _OPENSEARCH_ENDPOINT:
            return self._retrieve_from_opensearch(query, request.lens)
        logger.warning("No RAG store configured — using empty context (demo mode)")
        return []

    def _build_query(self, request: ArchitectureRequest) -> str:
        """Compose a retrieval query incorporating workload text + NFRs."""
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
    def _retrieve_from_knowledge_base(
        self, query: str, lens: Lens
    ) -> list[dict]:
        """Option A: Bedrock Knowledge Base retrieve API."""
        filter_expr: dict = {"equals": {"key": "lens", "value": lens.value}}
        if lens != Lens.GENERAL:
            # Include general docs alongside lens-specific docs
            filter_expr = {
                "orAll": [
                    {"equals": {"key": "lens", "value": "general"}},
                    {"equals": {"key": "lens", "value": lens.value}},
                ]
            }
        response = self._bedrock_agent.retrieve(
            knowledgeBaseId=_KB_ID,
            retrievalQuery={"text": query},
            retrievalConfiguration={
                "vectorSearchConfiguration": {
                    "numberOfResults": _TOP_K,
                    "filter": filter_expr,
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

    def _retrieve_from_opensearch(self, query: str, lens: Lens) -> list[dict]:
        """Option B: OpenSearch Serverless k-NN query (placeholder).

        Requires: embed query with Bedrock embedding model, then
        run a k-NN search with a metadata filter on the `lens` field.
        Full implementation omitted for brevity — see scripts/ingest_docs.py
        for the indexing logic which mirrors this retrieval contract.
        """
        raise NotImplementedError("OpenSearch retrieval not yet implemented")

    # ------------------------------------------------------------------
    # Generation
    # ------------------------------------------------------------------

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=2, max=16))
    async def _generate(
        self, request: ArchitectureRequest, chunks: list[dict]
    ) -> str:
        """Call Amazon Bedrock (Claude) with structured prompt + retrieved context."""
        context_block = "\n\n".join(
            f"[{i+1}] (source: {c.get('source','')}, lens: {c.get('metadata',{}).get('lens','')}, "
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

        body = json.dumps(
            {
                "anthropic_version": "bedrock-2023-05-31",
                "max_tokens": 8192,
                "system": system_prompt,
                "messages": [{"role": "user", "content": user_message}],
            }
        )

        response = self._bedrock_runtime.invoke_model(
            modelId=_MODEL_ID,
            contentType="application/json",
            accept="application/json",
            body=body,
        )
        result = json.loads(response["body"].read())
        return result["content"][0]["text"]
