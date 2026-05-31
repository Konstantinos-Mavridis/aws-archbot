#!/usr/bin/env python3
"""ArchBot CDK application entry point.

Stacks:
  - ArchBotRagStack       RAG store (Bedrock Knowledge Base + S3 source bucket)
  - ArchBotBackendStack   FastAPI on Lambda + API Gateway (or Fargate + ALB)
  - ArchBotFrontendStack  S3 static website + CloudFront distribution

Deploy all: cdk deploy --all
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
