# ADR 0002 — RAG Store: Bedrock Knowledge Bases vs OpenSearch Serverless

**Status:** Accepted  
**Date:** 2026-05-31  
**Authors:** Konstantinos Mavridis  

---

## Context

ArchBot requires a vector index over ~500–2,000 chunked passages from the AWS Well-Architected Framework and its FSI and Healthcare lenses. The index must support:
- Semantic similarity search (dense vector k-NN)
- Metadata filtering by `lens` (general / fsi / healthcare) and `pillar`
- Integration with Amazon Bedrock generation

Two viable options:

### Option A — Amazon Bedrock Knowledge Bases
- Fully managed: AWS provisions and maintains the OpenSearch Serverless (AOSS) collection.
- Native integration with `bedrock-agent-runtime:Retrieve` API.
- Supports metadata attribute filters.
- Chunking configured declaratively in CDK (`CfnDataSource`).
- **No vector index schema management required.**

### Option B — OpenSearch Serverless (self-managed)
- Full control over index mapping, k-NN parameters (`ef_construction`, `m`, `ef_search`).
- Custom embedding pipeline (embed → index via `_bulk` API).
- Requires managing AOSS collection policies, data access policies, and network policies.
- Lower per-query latency for complex filter combinations.
- More flexible for multi-modal indexing (sparse + dense hybrid).

---

## Decision

**Option A (Bedrock Knowledge Bases) for MVP.** OpenSearch Serverless is documented as the upgrade path.

---

## Rationale

| Factor | Bedrock KB (A) | OpenSearch Serverless (B) |
|---|---|---|
| Operational burden | Minimal — AWS-managed | High — index policies, mappings, upgrades |
| Setup complexity | CDK L1 construct + data source | AOSS collection + policies + ingest script |
| Metadata filtering | Supported natively | Full flexibility |
| Latency | ~200–500ms p99 | ~50–200ms p99 (tunable) |
| Cost (MVP scale) | ~$0/month at 0 queries + Storage | ~$87/month minimum (AOSS OCU floor) |
| FSI/Healthcare compliance | HIPAA-eligible, PCI-compliant | HIPAA-eligible, PCI-compliant |
| Data residency | In-region only | In-region only |
| Encryption | AWS-managed KMS | AWS-managed or CMK |
| Audit | CloudTrail for all API calls | CloudTrail for all API calls |

**The AOSS OCU minimum cost (~$87/month) makes Option B economically unviable at MVP scale.** Option A costs near-zero until query volume justifies the switch.

### FSI / Healthcare considerations
Both options are HIPAA-eligible and PCI-DSS compliant when deployed in eligible regions. For FSI workloads requiring Customer-Managed Keys (CMK) for the vector index, Option B with explicit KMS configuration is the correct choice. **This is documented as the trigger for migrating from A to B.**

---

## Migration Path A → B

1. Create an AOSS collection with KMS CMK encryption and VPC endpoint.
2. Implement `_retrieve_from_opensearch()` in `rag_pipeline.py` (stub exists).
3. Update `ArchBotRagStack` to provision the collection and pass its endpoint to the Lambda.
4. Re-run `scripts/ingest_docs.py` to populate the new index.
5. Toggle the `OPENSEARCH_ENDPOINT` environment variable; `_KB_ID` takes precedence otherwise.

---

## Well-Architected Pillar Mapping

| Pillar | Impact |
|---|---|
| **Operational Excellence** | Option A reduces toil (no index maintenance) |
| **Security** | Both options: in-region data, IAM-authenticated, CloudTrail audited |
| **Reliability** | Bedrock KB is AWS-managed; AOSS has SLA-backed availability |
| **Cost Optimization** | Option A near-zero at MVP; Option B justified only at production scale |
