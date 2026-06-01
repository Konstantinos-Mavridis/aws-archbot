#!/usr/bin/env python3
"""ArchBot CDK application entry point.

Stacks:
  - ArchBotRagStack       RAG store (Bedrock Knowledge Base + S3 source bucket)
                          ⚠️  Provisions OpenSearch Serverless (~$700/mo).
                          Only deploy when RAG is required.
  - ArchBotBackendStack   FastAPI on Lambda + API Gateway
  - ArchBotFrontendStack  S3 static website + CloudFront distribution

Deploy without RAG (free tier friendly):
  cdk deploy ArchBotBackendStack ArchBotFrontendStack \\
    -c llm_provider=openrouter -c openrouter_api_key=sk-or-v1-...

Deploy all (includes OpenSearch Serverless cost):
  cdk deploy --all -c llm_provider=openrouter -c openrouter_api_key=sk-or-v1-...

Cross-stack references (when RAG stack is deployed):
  RagStack.knowledge_base_id  --> BackendStack env var KNOWLEDGE_BASE_ID
  RagStack.data_source_id     --> BackendStack env var KB_DATA_SOURCE_ID
  RagStack.docs_bucket        --> BackendStack IAM read grant
  BackendStack.api_url        --> FrontendStack CloudFront origin / env var
"""

import aws_cdk as cdk

from stacks.backend_stack import ArchBotBackendStack
from stacks.frontend_stack import ArchBotFrontendStack
from stacks.rag_stack import ArchBotRagStack

app = cdk.App()

env = cdk.Environment(
    account=app.node.try_get_context("account"),
    region=app.node.try_get_context("region") or "us-east-1",
)

# deploy_rag=true enables ArchBotRagStack (OpenSearch Serverless, ~$700/mo).
# Defaults to false — backend runs without RAG context.
deploy_rag: bool = str(app.node.try_get_context("deploy_rag") or "false").lower() == "true"

rag_stack: ArchBotRagStack | None = None
if deploy_rag:
    rag_stack = ArchBotRagStack(app, "ArchBotRagStack", env=env)

backend_stack = ArchBotBackendStack(
    app,
    "ArchBotBackendStack",
    docs_bucket=rag_stack.docs_bucket if rag_stack else None,
    knowledge_base_id=rag_stack.knowledge_base_id if rag_stack else None,
    data_source_id=rag_stack.data_source_id if rag_stack else None,
    env=env,
)
if rag_stack:
    backend_stack.add_dependency(rag_stack)

frontend_stack = ArchBotFrontendStack(
    app,
    "ArchBotFrontendStack",
    api_url=backend_stack.api_url,
    env=env,
)
frontend_stack.add_dependency(backend_stack)

app.synth()
