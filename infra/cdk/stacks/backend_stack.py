"""ArchBotBackendStack — FastAPI on Lambda (via Mangum) + API Gateway.

For higher-throughput or VPC-required deployments, swap the Lambda construct
for an ECS Fargate service + ALB. The `main.py` handler supports both
execution models without code changes (Mangum wraps ASGI → Lambda event).

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

        # Bedrock: allow invoking Claude + embedding models + Knowledge Base retrieval
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
        lambda_role.add_to_policy(
            iam.PolicyStatement(
                actions=["bedrock:Retrieve"],
                resources=["*"],  # scope to KB ARN after first deploy
            )
        )

        docs_bucket.grant_read(lambda_role)

        # ----------------------------------------------------------------
        # Lambda function (Docker image for full Python dependency support)
        # ----------------------------------------------------------------
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
            environment={
                "AWS_REGION": self.region,
                "BEDROCK_MODEL_ID": "anthropic.claude-3-5-sonnet-20241022-v2:0",
                # KNOWLEDGE_BASE_ID is injected after rag_stack outputs are available
                # (use SSM Parameter Store or CDK cross-stack reference for runtime config)
            },
            log_retention=logs.RetentionDays.ONE_WEEK,
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
        # Outputs
        # ----------------------------------------------------------------
        cdk.CfnOutput(self, "ApiUrl", value=api.url, description="ArchBot API Gateway URL")
        cdk.CfnOutput(self, "LambdaFunctionName", value=self.fn.function_name)
