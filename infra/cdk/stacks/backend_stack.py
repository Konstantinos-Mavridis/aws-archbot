"""ArchBotBackendStack — FastAPI on Lambda (via Mangum) + API Gateway.

For higher-throughput or VPC-required deployments, swap the Lambda construct
for an ECS Fargate service + ALB. The `main.py` handler supports both
execution models without code changes (Mangum wraps ASGI -> Lambda event).

See docs/adr/0001-architecture-overview.md and 0003-deployment-strategy.md.

LLM provider selection
----------------------
Pass CDK context to choose the generation backend at deploy time:

  cdk deploy -c llm_provider=openrouter -c openrouter_api_key=sk-or-v1-...
  cdk deploy -c llm_provider=bedrock          # default

When llm_provider=openrouter the Bedrock IAM grants are omitted and the
OpenRouter API key is injected as a Lambda environment variable.
The key is passed via CDK context (not hardcoded) so it never appears in
synthesised CloudFormation templates committed to source control.
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
        # LLM provider config (from CDK context)
        # ----------------------------------------------------------------
        # Deploy with:  cdk deploy -c llm_provider=openrouter \
        #                          -c openrouter_api_key=sk-or-v1-...
        # Defaults to "bedrock" when context key is absent.
        llm_provider: str = str(self.node.try_get_context("llm_provider") or "bedrock").lower()
        openrouter_api_key: str = str(self.node.try_get_context("openrouter_api_key") or "")
        openrouter_model: str = str(
            self.node.try_get_context("openrouter_model")
            or "meta-llama/llama-3.1-8b-instruct:free"
        )

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

        # Bedrock IAM grants are only needed when using the Bedrock provider.
        # Skipping them in OpenRouter mode keeps the Lambda role least-privilege.
        if llm_provider == "bedrock":
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
        # Lambda environment variables
        # ----------------------------------------------------------------
        # Note: AWS_REGION is reserved by the Lambda runtime — do NOT set it.
        lambda_env: dict[str, str] = {
            "LLM_PROVIDER": llm_provider,
            # Cross-stack references resolved at deploy time from RagStack outputs
            "KNOWLEDGE_BASE_ID": knowledge_base_id,
            "KB_DATA_SOURCE_ID": data_source_id,
        }

        if llm_provider == "bedrock":
            lambda_env["BEDROCK_MODEL_ID"] = "anthropic.claude-3-5-sonnet-20241022-v2:0"

        if llm_provider == "openrouter":
            if not openrouter_api_key:
                raise ValueError(
                    "CDK context key 'openrouter_api_key' is required when "
                    "llm_provider=openrouter. Pass it with: "
                    "-c openrouter_api_key=sk-or-v1-..."
                )
            lambda_env["OPENROUTER_API_KEY"] = openrouter_api_key
            lambda_env["OPENROUTER_MODEL"] = openrouter_model

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
            log_group=log_group,
            environment=lambda_env,
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
        cdk.CfnOutput(self, "LlmProvider", value=llm_provider, description="Active LLM provider")
