"""ArchBotBackendStack — FastAPI on Lambda (via Mangum) + API Gateway.

For higher-throughput or VPC-required deployments, swap the Lambda construct
for an ECS Fargate service + ALB. The `main.py` handler supports both
execution models without code changes (Mangum wraps ASGI -> Lambda event).

See docs/adr/0001-architecture-overview.md and 0003-deployment-strategy.md.
"""

from __future__ import annotations

import aws_cdk as cdk
from aws_cdk import (
    aws_apigateway as apigw,
    aws_iam as iam,
    aws_lambda as lambda_,
    aws_logs as logs,
    aws_s3 as s3,
)
from constructs import Construct


class ArchBotBackendStack(cdk.Stack):
    def __init__(
        self,
        scope: Construct,
        construct_id: str,
        docs_bucket: s3.IBucket,
        knowledge_base_id: str,
        data_source_id: str,
        **kwargs: object,
    ) -> None:
        super().__init__(scope, construct_id, **kwargs)  # type: ignore[arg-type]

        # ----------------------------------------------------------------
        # Lambda execution role
        # ----------------------------------------------------------------
        lambda_role = iam.Role(
            self,
            "ArchBotLambdaRole",
            assumed_by=iam.ServicePrincipal("lambda.amazonaws.com"),
            managed_policies=[
                iam.ManagedPolicy.from_aws_managed_policy_name(
                    "service-role/AWSLambdaBasicExecutionRole"
                )
            ],
        )

        # Bedrock: invoke Claude generation model + Titan embedding model
        lambda_role.add_to_policy(
            iam.PolicyStatement(
                actions=[
                    "bedrock:InvokeModel",
                    "bedrock:InvokeModelWithResponseStream",
                ],
                resources=[
                    f"arn:aws:bedrock:{self.region}::foundation-model/anthropic.claude-3-5-sonnet-20241022-v2:0",
                    f"arn:aws:bedrock:{self.region}::foundation-model/amazon.titan-embed-text-v2:0",
                ],
            )
        )

        # Bedrock: Knowledge Base retrieve (scoped to specific KB)
        lambda_role.add_to_policy(
            iam.PolicyStatement(
                actions=["bedrock:Retrieve"],
                resources=[
                    cdk.Stack.of(self).format_arn(
                        service="bedrock",
                        resource="knowledge-base",
                        resource_name=knowledge_base_id,
                    )
                ],
            )
        )

        docs_bucket.grant_read(lambda_role)

        # ----------------------------------------------------------------
        # Explicit log group (avoids deprecated log_retention prop)
        # ----------------------------------------------------------------
        log_group = logs.LogGroup(
            self,
            "ArchBotFunctionLogs",
            retention=logs.RetentionDays.ONE_WEEK,
            removal_policy=cdk.RemovalPolicy.DESTROY,
        )

        # ----------------------------------------------------------------
        # Lambda function (Docker image for full Python dependency support)
        # ----------------------------------------------------------------
        # Note: AWS_REGION is reserved by the Lambda runtime and injected
        # automatically — do NOT set it manually. Use AWS_DEFAULT_REGION
        # only if you need a fallback for boto3 in non-Lambda contexts.
        self.fn = lambda_.DockerImageFunction(
            self,
            "ArchBotFunction",
            code=lambda_.DockerImageCode.from_image_asset(
                "../../backend",
                file="Dockerfile",
            ),
            memory_size=1024,
            timeout=cdk.Duration.seconds(60),
            role=lambda_role,
            log_group=log_group,
            environment={
                "BEDROCK_MODEL_ID": "anthropic.claude-3-5-sonnet-20241022-v2:0",
                # Cross-stack references: resolved at deploy time from RagStack outputs
                "KNOWLEDGE_BASE_ID": knowledge_base_id,
                "KB_DATA_SOURCE_ID": data_source_id,
            },
        )

        # ----------------------------------------------------------------
        # API Gateway REST API
        # ----------------------------------------------------------------
        api = apigw.LambdaRestApi(
            self,
            "ArchBotApi",
            handler=self.fn,
            rest_api_name="archbot-api",
            description="ArchBot architecture advisor API",
            default_cors_preflight_options=apigw.CorsOptions(
                allow_origins=apigw.Cors.ALL_ORIGINS,
                allow_methods=apigw.Cors.ALL_METHODS,
                allow_headers=["Content-Type", "Authorization"],
            ),
            deploy_options=apigw.StageOptions(
                stage_name="prod",
                throttling_rate_limit=100,
                throttling_burst_limit=200,
                logging_level=apigw.MethodLoggingLevel.INFO,
                data_trace_enabled=False,
            ),
        )

        self.api_url = api.url

        # ----------------------------------------------------------------
        # CloudFormation Outputs
        # ----------------------------------------------------------------
        cdk.CfnOutput(self, "ApiUrl", value=api.url, description="ArchBot API Gateway URL")
        cdk.CfnOutput(self, "LambdaFunctionName", value=self.fn.function_name)
