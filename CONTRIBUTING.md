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

The `FrontendStack` bundles `frontend/out/` into the S3 deployment. You must
build the frontend before synthesising or deploying:

```bash
# Build the frontend static export first
cd frontend && npm ci && npm run build && cd ..

# Then synthesise (no AWS credentials needed for synth)
cd infra/cdk
pip install -r requirements.txt
CDK_DEFAULT_ACCOUNT=000000000000 CDK_DEFAULT_REGION=us-east-1 cdk synth
```

> Skipping the frontend build will produce a `DeployWebsite skipped` warning
> from the CDK `FrontendStack` construct and the S3 deployment will be a no-op.

---

## LLM Provider

ArchBot supports three generation backends, selected via the `LLM_PROVIDER` env var:

| `LLM_PROVIDER` | Description | Requirements |
|---|---|---|
| `bedrock` | Amazon Bedrock (Claude) — **default** | AWS account + Bedrock access |
| `openrouter` | [OpenRouter](https://openrouter.ai/) HTTP API — **free tier available** | `OPENROUTER_API_KEY` |
| `ollama` | Local Ollama server — fully offline | Ollama running locally |

### Using OpenRouter locally

1. Get a free API key at <https://openrouter.ai/>
2. Copy the example env file and fill in your key:
   ```bash
   cp backend/.env.example backend/.env
   # Edit backend/.env: set OPENROUTER_API_KEY=sk-or-v1-...
   ```
3. Start the stack:
   ```bash
   docker compose -f docker-compose.local.yml up backend frontend
   # or without Docker:
   LLM_PROVIDER=openrouter OPENROUTER_API_KEY=sk-or-v1-... uvicorn app.main:app --reload
   ```

### Using OpenRouter in CI / GitHub Actions

CI tests are fully mocked — **no API key is needed for `backend-lint-test`**.

For deployment (`cdk-deploy.yml`) the key is passed as a CDK context value,
which is sourced from a GitHub Secret:

1. Add `OPENROUTER_API_KEY` to your repository secrets
   (Settings → Secrets and variables → Actions → New repository secret).
2. Pass it to CDK at deploy time in `.github/workflows/cdk-deploy.yml`:
   ```yaml
   - name: CDK deploy
     run: |
       cdk deploy --all --require-approval=never \
         -c llm_provider=openrouter \
         -c openrouter_api_key=${{ secrets.OPENROUTER_API_KEY }}
   ```
   The key is injected as a Lambda environment variable at deploy time and
   never appears in synthesised CloudFormation templates.

### Changing the OpenRouter model

Set `OPENROUTER_MODEL` to any model slug from <https://openrouter.ai/models>.
Free models are marked `:free`. The default is `meta-llama/llama-3.1-8b-instruct:free`.

```bash
# Higher quality free model
OPENROUTER_MODEL=meta-llama/llama-3.3-70b-instruct:free uvicorn app.main:app --reload
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

| Job | What it checks | Depends on |
|---|---|---|
| `backend-lint-test` | ruff, mypy, pytest with coverage | — |
| `frontend-lint` | eslint, tsc --noEmit, next build; uploads `frontend/out` artifact | — |
| `cdk-synth` | CDK synthesises without errors or warnings | `frontend-lint` (needs the built artifact) |

> `cdk-synth` runs **after** `frontend-lint` so that `frontend/out` exists on
> the runner. Without it the `FrontendStack` emits a `DeployWebsite skipped`
> warning and the S3 deployment asset is missing.

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

The `cdk-deploy.yml` workflow builds the frontend in a dedicated `build-frontend`
job and passes the resulting `frontend/out` artifact to the `cdk-deploy` job,
so manual pre-build steps are not required in CI.

To deploy manually to your own account:
```bash
# Build frontend first
cd frontend && npm ci && npm run build && cd ..

# Deploy with Bedrock (default)
cd infra/cdk
cdk deploy --all --require-approval=never

# Deploy with OpenRouter
cdk deploy --all --require-approval=never \
  -c llm_provider=openrouter \
  -c openrouter_api_key=sk-or-v1-...
```

CDK outputs the API URL, CloudFront distribution domain, and active LLM provider after deployment.

---

## Questions?

Open a GitHub issue with the `question` label.
