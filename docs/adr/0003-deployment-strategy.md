# ADR 0003 — Deployment and Environment Strategy

**Status:** Accepted  
**Date:** 2026-05-31  
**Updated:** 2026-06-01  
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

#### `ci.yml` — runs on every push and PR

```
backend-lint-test  ─────────────────────────────────────────► (pass/fail)

frontend-lint      ── eslint + tsc + next build ──────────────► upload frontend/out artifact
                                                                        │
cdk-synth          ── needs: frontend-lint ──────────────────────────── ┘
                      downloads frontend/out → cdk synth → (pass/fail)
```

> `cdk-synth` depends on `frontend-lint` so that `frontend/out` is present
> when the `FrontendStack` construct runs. Without the built static export,
> CDK emits a `DeployWebsite skipped` warning and the S3 asset is missing.

#### `cdk-deploy.yml` — runs on merge to `main`

```
build-frontend  ── npm ci + next build ──► upload frontend/out artifact
                                                    │
cdk-diff (PR)   ── needs: build-frontend ───────────┘ cdk diff → post PR comment

cdk-deploy      ── needs: build-frontend ───────────┘ cdk deploy --require-approval=never → dev
```

**CDK diff** runs on every PR, publishing the changeset as a PR comment — reviewers see infra changes alongside code changes.

> When `AWS_DEPLOY_ROLE_ARN` is not configured (e.g. forks or contributor PRs),
> the pipeline falls back to a `cdk-diff-dry-run` job that runs `cdk synth`
> without AWS credentials and posts the output as a PR comment instead.

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
