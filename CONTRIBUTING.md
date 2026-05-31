# Contributing to ArchBot

Thank you for your interest in contributing! This document covers local setup, branch conventions, and the CI/CD workflow.

---

## Prerequisites

| Tool | Version |
|---|---|
| Python | 3.12+ |
| Node.js | 20 LTS |
| AWS CDK CLI | 2.x (`npm i -g aws-cdk`) |
| Docker | 24+ (for Fargate builds) |
| AWS CLI | 2.x (configured with a dev account) |

---

## Local Setup

### Backend

```bash
cd backend
python -m venv .venv && source .venv/bin/activate
pip install -e '.[dev]'
```

Run tests (no AWS credentials required — all AWS calls are mocked):
```bash
pytest --cov=app -q
```

Lint + type-check:
```bash
ruff check app tests scripts
mypy app
```

Start the API locally (demo mode — no Bedrock calls):
```bash
uvicorn app.main:app --reload
# Visit http://localhost:8000/docs for the OpenAPI UI
```

### Frontend

```bash
cd frontend
npm ci
npm run dev
# Visit http://localhost:3000
```

Point the frontend at the local backend:
```bash
echo 'NEXT_PUBLIC_API_URL=http://localhost:8000' > .env.local
```

### Infrastructure (CDK)

```bash
cd infra/cdk
pip install -r requirements.txt
CDK_DEFAULT_ACCOUNT=000000000000 CDK_DEFAULT_REGION=us-east-1 cdk synth
```

---

## Ingesting WA Documents

Before running with a live RAG store, download the Well-Architected docs and run the ingest script:

```bash
mkdir -p backend/wa_docs
# Download WA Framework, FSI Lens, Healthcare Lens as .txt or .md files
# into backend/wa_docs/

cd backend
# Ingest general WA framework into Bedrock Knowledge Base
python scripts/ingest_docs.py --lens general --store kb

# Ingest FSI lens
python scripts/ingest_docs.py --lens fsi --store kb

# Ingest Healthcare lens
python scripts/ingest_docs.py --lens healthcare --store kb
```

Required environment variables:
```
AWS_REGION=us-east-1
DOCS_S3_BUCKET=archbot-wa-docs
KNOWLEDGE_BASE_ID=<from CDK outputs>
KB_DATA_SOURCE_ID=<from CDK outputs>
```

For OpenSearch Serverless instead:
```bash
python scripts/ingest_docs.py --lens general --store opensearch
```
```
OPENSEARCH_ENDPOINT=https://<collection-id>.us-east-1.aoss.amazonaws.com
VECTOR_INDEX_NAME=archbot-wa-index
```

---

## Branch & PR Conventions

- Branch off `main`: `feat/<topic>`, `fix/<topic>`, `chore/<topic>`
- One logical change per PR
- PR title format: `feat: <description>` / `fix: <description>` / `chore: <description>`
- Squash merge into `main`

### CI checks (must pass)

| Job | What it checks |
|---|---|
| `backend-lint-test` | ruff, mypy, pytest with coverage |
| `frontend-lint` | eslint, tsc --noEmit, next build |
| `cdk-synth` | CDK synthesises without errors |

---

## Architecture Decision Records

For significant design decisions, add an ADR to `docs/adr/` using the template:

```markdown
# ADR NNNN — Title

**Status:** Proposed | Accepted | Superseded by ADR-XXXX
**Date:** YYYY-MM-DD

## Context
## Decision
## Rationale
## Consequences
## Well-Architected Pillar Mapping
```

See existing ADRs in `docs/adr/` for examples.

---

## Deployment

Deployment is handled by `.github/workflows/cdk-deploy.yml` on merge to `main`.

To deploy manually to your own account:
```bash
cd infra/cdk
cdk deploy --all --require-approval=never
```

CDK outputs the API URL and CloudFront distribution domain after deployment.

---

## Questions?

Open a GitHub issue with the `question` label.
