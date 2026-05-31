# ArchBot Backend

FastAPI application deployable as an AWS Lambda function (via Mangum) or as a Fargate service.

## Structure

```
app/
  main.py           — FastAPI app entrypoint + Lambda handler via Mangum
  rag_pipeline.py   — RAG retrieval + Bedrock (Claude) orchestration
  models.py         — Pydantic request/response schemas
  cost_estimator.py — Qualitative cost tier heuristics
scripts/
  ingest_docs.py    — One-time ingestion of WA Framework + Lens documents
tests/
  test_rag_pipeline.py
  test_models.py
```

## Running locally

```bash
pip install -e '.[dev]'
uvicorn app.main:app --reload --port 8000
```

Set environment variables:

```bash
export AWS_REGION=us-east-1
export BEDROCK_MODEL_ID=anthropic.claude-3-5-sonnet-20241022-v2:0
export KNOWLEDGE_BASE_ID=your-kb-id          # Option A
export OPENSEARCH_ENDPOINT=https://...        # Option B
export VECTOR_INDEX_NAME=archbot-wa-index
```

## Testing

```bash
pytest tests/ -v --cov=app
```
