# ADR 0003 — Deployment and Environment Strategy

**Status:** Accepted  
**Date:** 2026-05-31  
**Authors:** Konstantinos Mavridis  

---

## Context

ArchBot needs a deployment strategy that:
1. Supports rapid iteration during development.
2. Demonstrates infrastructure automation discipline (SA portfolio signal).
3. Can evolve toward a multi-region, 99.99% SLA target without major rework.
4. Stays within a solo-developer operational budget.

---

## Decision

**Single-region, multi-AZ deployment for MVP** with a documented path to multi-region active-active.

### Environments

| Environment | AWS Account | Region | Deployment trigger |
|---|---|---|---|
| `dev` | Shared / personal | `us-east-1` | Push to `main` (auto) |
| `staging` | Separate account (optional) | `us-east-1` | PR merge to `release/*` |
| `prod` | Production account | `us-east-1` + `eu-west-1` (future) | Manual approval gate |

### CI/CD Pipeline (GitHub Actions)

```
PR opened
  └─ ci.yml: lint (ruff, eslint) + unit tests (pytest, jest) + CDK synth

Merge to main
  └─ cdk-deploy.yml: CDK diff → CDK deploy --require-approval=never → dev
```

**CDK diff** runs on every PR, publishing the changeset as a PR comment — reviewers see infra changes alongside code changes.

---

## Multi-Region Path

To achieve 99.99% SLA (downtime < 52 minutes/year) for FSI/Healthcare scenarios:

### Phase 1 — Multi-AZ (current)
- Lambda + API Gateway: inherently multi-AZ within a region.
- Bedrock Knowledge Base: AOSS is multi-AZ within the region.
- CloudFront: global edge network, not region-specific.
- **Estimated availability: ~99.95%** (within-region Lambda + APIGW SLA).

### Phase 2 — Active-Passive Multi-Region
- Promote Lambda to Fargate (for VPC placement and consistent networking).
- Add a second region (`eu-west-1` for GDPR scenarios).
- Route 53 health-check-based failover (primary: `us-east-1`, secondary: `eu-west-1`).
- Knowledge Base data source S3 bucket replicated via S3 Cross-Region Replication.
- **Estimated availability: ~99.99%** (Route 53 failover SLA + multi-region compute).

### Phase 3 — Active-Active Multi-Region
- DynamoDB Global Tables for any session state (if added).
- Route 53 latency-based routing.
- Bedrock availability permitting (model availability varies by region).
- **Cost impact: ~3× base infrastructure cost.** Explicitly flagged in `cost_estimator.py`.

---

## Environment Parity

- CDK stacks are identical across environments; environment-specific config is injected via CDK context (`-c account=... -c region=...`).
- No environment-specific code paths in application logic.
- `dev` uses the same CDK stacks as `prod` — only resource sizing differs (Lambda memory: `dev=512MB`, `prod=1024MB`).

---

## Well-Architected Pillar Mapping

| Pillar | How this decision addresses it |
|---|---|
| **Operational Excellence** | IaC parity across environments; CDK diff in PRs; automated deployment |
| **Reliability** | Multi-AZ Lambda/APIGW; documented path to multi-region; health checks |
| **Security** | Separate AWS accounts per environment; least-privilege IAM per stack |
| **Cost Optimization** | Scale-to-zero Lambda; single-region MVP avoids unnecessary replication cost |
