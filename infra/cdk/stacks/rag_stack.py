"""ArchBotRagStack — Bedrock Knowledge Base + S3 source bucket.

Option A (default): Amazon Bedrock Knowledge Bases managed RAG.
  - S3 bucket stores chunked WA + Lens documents (populated by scripts/ingest_docs.py).
  - Bedrock Knowledge Base references the S3 bucket as its data source.
  - No vector index management required — fully managed by AWS.

Cross-stack wiring:
  self.knowledge_base_id  — str, CDK token, passed to ArchBotBackendStack
  self.data_source_id     — str, CDK token, passed to ArchBotBackendStack
  self.docs_bucket        — s3.Bucket, passed to ArchBotBackendStack for read grants

See docs/adr/0002-rag-store-choice.md for the RAG store decision.
"""

from __future__ import annotations

import aws_cdk as cdk
from aws_cdk import (
    aws_bedrock as bedrock,
    aws_iam as iam,
    aws_s3 as s3,
)
from constructs import Construct


class ArchBotRagStack(cdk.Stack):
    # Public properties consumed by ArchBotBackendStack
    knowledge_base_id: str
    data_source_id: str
    docs_bucket: s3.Bucket

    def __init__(self, scope: Construct, construct_id: str, **kwargs: object) -> None:
        super().__init__(scope, construct_id, **kwargs)  # type: ignore[arg-type]

        # ----------------------------------------------------------------
        # S3 bucket for WA Framework + Lens documents
        # ----------------------------------------------------------------
        self.docs_bucket = s3.Bucket(
            self,
            "ArchBotDocsBucket",
            bucket_name=f"archbot-wa-docs-{self.account}-{self.region}",
            versioned=True,
            encryption=s3.BucketEncryption.S3_MANAGED,
            block_public_access=s3.BlockPublicAccess.BLOCK_ALL,
            removal_policy=cdk.RemovalPolicy.RETAIN,
            lifecycle_rules=[
                s3.LifecycleRule(
                    id="ExpireOldVersions",
                    noncurrent_version_expiration=cdk.Duration.days(30),
                )
            ],
        )

        # ----------------------------------------------------------------
        # IAM role that Bedrock Knowledge Base will assume to read from S3
        # ----------------------------------------------------------------
        kb_role = iam.Role(
            self,
            "ArchBotKbRole",
            assumed_by=iam.ServicePrincipal("bedrock.amazonaws.com"),
            description="Allows Bedrock Knowledge Base to read WA docs from S3",
        )
        self.docs_bucket.grant_read(kb_role)

        # ----------------------------------------------------------------
        # Bedrock Knowledge Base (L1 construct — CfnKnowledgeBase)
        # Embedding model: Amazon Titan Text Embeddings v2
        # Storage: managed Bedrock vector store (OpenSearch Serverless, auto-provisioned)
        # ----------------------------------------------------------------
        kb = bedrock.CfnKnowledgeBase(
            self,
            "ArchBotKnowledgeBase",
            name="archbot-wa-knowledge-base",
            description="Well-Architected Framework + FSI & Healthcare Lens documents",
            role_arn=kb_role.role_arn,
            knowledge_base_configuration=bedrock.CfnKnowledgeBase.KnowledgeBaseConfigurationProperty(
                type="VECTOR",
                vector_knowledge_base_configuration=bedrock.CfnKnowledgeBase.VectorKnowledgeBaseConfigurationProperty(
                    embedding_model_arn=(
                        f"arn:aws:bedrock:{self.region}::foundation-model/"
                        "amazon.titan-embed-text-v2:0"
                    )
                ),
            ),
            storage_configuration=bedrock.CfnKnowledgeBase.StorageConfigurationProperty(
                type="OPENSEARCH_SERVERLESS",
                # Bedrock creates and manages the AOSS collection automatically
                # when storage type is OPENSEARCH_SERVERLESS and no explicit collection
                # ARN is provided. Supply a collectionArn here to use an existing
                # collection (Option B migration path — see ADR-0002).
            ),
        )
        # Expose as typed property for cross-stack reference
        self.knowledge_base_id: str = kb.ref

        # S3 data source for the Knowledge Base
        ds = bedrock.CfnDataSource(
            self,
            "ArchBotDocsDataSource",
            name="archbot-wa-docs",
            knowledge_base_id=kb.ref,
            data_source_configuration=bedrock.CfnDataSource.DataSourceConfigurationProperty(
                type="S3",
                s3_configuration=bedrock.CfnDataSource.S3DataSourceConfigurationProperty(
                    bucket_arn=self.docs_bucket.bucket_arn,
                    inclusion_prefixes=["general/", "fsi/", "healthcare/"],
                ),
            ),
            vector_ingestion_configuration=bedrock.CfnDataSource.VectorIngestionConfigurationProperty(
                chunking_configuration=bedrock.CfnDataSource.ChunkingConfigurationProperty(
                    chunking_strategy="FIXED_SIZE",
                    fixed_size_chunking_configuration=bedrock.CfnDataSource.FixedSizeChunkingConfigurationProperty(
                        max_tokens=1500,
                        overlap_percentage=10,
                    ),
                )
            ),
        )
        # Expose data source ID for ingest script env var and cross-stack wiring
        self.data_source_id: str = ds.ref

        # ----------------------------------------------------------------
        # CloudFormation Outputs
        # ----------------------------------------------------------------
        cdk.CfnOutput(self, "DocsBucketName", value=self.docs_bucket.bucket_name)
        cdk.CfnOutput(self, "KnowledgeBaseId", value=kb.ref)
        cdk.CfnOutput(self, "DataSourceId", value=ds.ref)
