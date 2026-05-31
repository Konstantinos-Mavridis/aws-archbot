#!/usr/bin/env python3
"""ArchBot CDK application entry point.

Stacks:
  - ArchBotRagStack       RAG store (Bedrock Knowledge Base + S3 source bucket)
  - ArchBotBackendStack   FastAPI on Lambda + API Gateway (or Fargate + ALB)
  - ArchBotFrontendStack  S3 static website + CloudFront distribution

Deploy all:   cdk deploy --all
Deploy one:   cdk deploy ArchBotRagStack

Cross-stack references:
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

rag_stack = ArchBotRagStack(app, "ArchBotRagStack", env=env)

backend_stack = ArchBotBackendStack(
    app,
    "ArchBotBackendStack",
    docs_bucket=rag_stack.docs_bucket,
    knowledge_base_id=rag_stack.knowledge_base_id,
    data_source_id=rag_stack.data_source_id,
    env=env,
)
backend_stack.add_dependency(rag_stack)

frontend_stack = ArchBotFrontendStack(
    app,
    "ArchBotFrontendStack",
    api_url=backend_stack.api_url,
    env=env,
)
frontend_stack.add_dependency(backend_stack)

app.synth()
