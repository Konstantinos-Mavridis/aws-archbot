"""ArchBotFrontendStack — S3 static website + CloudFront distribution.

The Next.js app is built with `output: export` (static HTML/JS/CSS).
Artifacts are uploaded to S3 and served globally via CloudFront.

The `api_url` parameter is accepted for documentation and future use
(e.g. injecting a runtime config.json). For the MVP the API URL is baked
into the Next.js static export at CI build time via NEXT_PUBLIC_API_URL.

Alternative: Replace S3+CloudFront with AWS Amplify Hosting for CI/CD-managed
frontend deployments directly from the GitHub repo.
"""

from __future__ import annotations

import aws_cdk as cdk
from aws_cdk import (
    aws_cloudfront as cloudfront,
    aws_cloudfront_origins as origins,
    aws_s3 as s3,
    aws_s3_deployment as s3deploy,
)
from constructs import Construct


class ArchBotFrontendStack(cdk.Stack):
    def __init__(
        self,
        scope: Construct,
        construct_id: str,
        api_url: str,  # noqa: ARG002  # baked into the static export at CI build time
        **kwargs: object,
    ) -> None:
        super().__init__(scope, construct_id, **kwargs)  # type: ignore[arg-type]

        # ----------------------------------------------------------------
        # S3 bucket for static assets (not public — served via CloudFront OAC)
        # ----------------------------------------------------------------
        website_bucket = s3.Bucket(
            self,
            "ArchBotWebsiteBucket",
            bucket_name=f"archbot-frontend-{self.account}-{self.region}",
            encryption=s3.BucketEncryption.S3_MANAGED,
            block_public_access=s3.BlockPublicAccess.BLOCK_ALL,
            removal_policy=cdk.RemovalPolicy.DESTROY,
            auto_delete_objects=True,
        )

        # ----------------------------------------------------------------
        # CloudFront Origin Access Control (OAC)
        # ----------------------------------------------------------------
        oac = cloudfront.S3OriginAccessControl(
            self,
            "ArchBotOAC",
            description="OAC for ArchBot frontend",
        )

        # ----------------------------------------------------------------
        # CloudFront distribution
        # ----------------------------------------------------------------
        self.distribution = cloudfront.Distribution(
            self,
            "ArchBotDistribution",
            comment="ArchBot frontend",
            default_behavior=cloudfront.BehaviorOptions(
                origin=origins.S3BucketOrigin.with_origin_access_control(
                    website_bucket,
                    origin_access_control=oac,
                ),
                viewer_protocol_policy=cloudfront.ViewerProtocolPolicy.REDIRECT_TO_HTTPS,
                cache_policy=cloudfront.CachePolicy.CACHING_OPTIMIZED,
                compress=True,
            ),
            default_root_object="index.html",
            error_responses=[
                cloudfront.ErrorResponse(
                    http_status=403,
                    response_http_status=200,
                    response_page_path="/index.html",
                ),
                cloudfront.ErrorResponse(
                    http_status=404,
                    response_http_status=200,
                    response_page_path="/index.html",
                ),
            ],
            price_class=cloudfront.PriceClass.PRICE_CLASS_100,
        )

        # ----------------------------------------------------------------
        # Deploy Next.js static export to S3 + invalidate CloudFront cache
        # Assumes `npm run build` has already produced frontend/out/
        # (handled by the build-frontend job in cdk-deploy.yml)
        # ----------------------------------------------------------------
        s3deploy.BucketDeployment(
            self,
            "DeployWebsite",
            sources=[s3deploy.Source.asset("../../frontend/out")],
            destination_bucket=website_bucket,
            distribution=self.distribution,
            distribution_paths=["/*"],
            memory_limit=512,
        )

        # ----------------------------------------------------------------
        # CloudFormation Outputs
        # ----------------------------------------------------------------
        cdk.CfnOutput(
            self,
            "CloudFrontUrl",
            value=f"https://{self.distribution.domain_name}",
            description="ArchBot CloudFront distribution URL",
        )
        cdk.CfnOutput(self, "WebsiteBucketName", value=website_bucket.bucket_name)
