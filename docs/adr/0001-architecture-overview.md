# ADR 0001 — Overall Architecture Style

**Status:** Accepted  
**Date:** 2026-05-31  
**Authors:** Konstantinos Mavridis  

---

## Context

ArchBot needs to accept free-text workload descriptions, perform retrieval-augmented generation over AWS Well-Architected Framework documentation, and return structured architecture outputs (narrative, service recommendations, Mermaid diagram, Well-Architected checklist, cost tiers).

Key drivers:
- **Scalability** — traffic is bursty (demos, SA pitches); must scale to zero between bursts.
- **Operability** — team of one; minimal operational overhead.
- **Security** — no persistent user data; LLM calls must be IAM-authenticated, not key-based.
- **Reuse of AWS managed services** — aligns with the Well-Architected Reliability and Operational Excellence pillars.
- **SA portfolio signal** — IaC-first approach demonstrates infrastructure automation discipline.

---

## Decision

Adopt a **stateless API + external vector store + managed LLM** architecture:

```
User → CloudFront/S3 (frontend) → API Gateway → Lambda (FastAPI/Mangum)
                                                     ↓
                                            Bedrock Knowledge Base
                                                     ↓
                                            Amazon Bedrock (Claude)
```

**Component choices:**

| Concern | Choice | Alternative considered |
|---|---|---|
| Compute | Lambda (Mangum wraps FastAPI) | ECS Fargate |
| API layer | API Gateway REST | ALB |
| LLM | Bedrock (Claude 3.5 Sonnet) | OpenAI API |
| Vector store | Bedrock Knowledge Bases | OpenSearch Serverless |
| Frontend hosting | S3 + CloudFront | Amplify |
| IaC | AWS CDK (Python) | Terraform |

---

## Rationale

### Stateless API over monolith
A stateless Lambda function with no session state or local persistence simplifies horizontal scaling, removes the need for session affinity, and aligns with the Well-Architected **Reliability** pillar (design for failure, scale out).

### Lambda over Fargate (for MVP)
Lambda + API Gateway eliminates container lifecycle management and reduces cold-start risk with Provisioned Concurrency if needed. The `Mangum` adapter means the same FastAPI codebase runs on both Lambda and Fargate without modification — a migration path is preserved.

### Amazon Bedrock over OpenAI
Bedrock keeps all data in the AWS account (no data leaving the AWS network), uses IAM authentication (no API key rotation), and is already HIPAA-eligible and PCI-compliant — critical for FSI and Healthcare lens scenarios. References Well-Architected **Security** pillar: *"Apply security at all layers."*

### AWS CDK (Python) over Terraform
The backend is Python; CDK Python gives strong typing, code reuse across stacks, and native AWS L2 constructs. CDK synthesises to CloudFormation, which is natively auditable — aligns with **Operational Excellence** pillar.

---

## Well-Architected Pillar Mapping

| Pillar | How this decision addresses it |
|---|---|
| **Operational Excellence** | IaC-first (CDK), structured logging, Lambda managed scaling |
| **Security** | IAM-only Bedrock auth, no user PII stored, S3 Block Public Access |
| **Reliability** | Stateless compute, multi-AZ Lambda, CloudFront global caching |
| **Performance Efficiency** | Serverless burst scaling, CloudFront edge caching of frontend |
| **Cost Optimization** | Scale-to-zero Lambda, pay-per-invocation Bedrock pricing |
| **Sustainability** | No idle EC2/Fargate capacity; Lambda runs only on demand |

---

## Consequences

- **Positive:** Low operational overhead; straightforward CI/CD (`cdk deploy --all`); IAM-native security.
- **Negative:** Lambda cold starts (~1-2s) add latency on first invocation after idle period. Mitigated with Provisioned Concurrency if SLA demands it.
- **Future work:** For multi-region 99.99% SLA targets, promote to Fargate + ALB behind Route 53 with health-check-based failover. The FastAPI codebase is already Fargate-compatible.
