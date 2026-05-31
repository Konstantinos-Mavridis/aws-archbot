# Well-Architected Checklist — Example Output

This example illustrates the checklist structure ArchBot generates for a regulated FSI trade finance platform with multi-region, 99.99% SLA requirements.

---

## Workload

> "Regulated FSI trade finance platform, CQRS event sourcing, multi-region active-active, 99.99% SLA, PCI-DSS compliant"

**Lens:** Financial Services (FSI)

---

## Operational Excellence

| Question | Risk | Finding | Improvement |
|---|---|---|---|
| Are runbooks documented for all operational events? | MEDIUM | No operational runbook referenced in the description. | Define runbooks in AWS Systems Manager Documents (SSM); trigger via EventBridge rules. |
| Is distributed tracing enabled across service boundaries? | MEDIUM | CQRS with multiple services increases tracing complexity. | Implement AWS X-Ray across all Lambda/Fargate services and the event bus. |
| Are deployment change sets reviewed before production pushes? | GOOD_PRACTICE | CDK diff in CI/CD pipeline provides pre-deployment change visibility. | — |

---

## Security

| Question | Risk | Finding | Improvement |
|---|---|---|---|
| Is data encrypted at rest with customer-managed keys? | HIGH | PCI-DSS requires demonstrable key management control. | Use AWS KMS Customer Managed Keys (CMK) for S3, DynamoDB, and OpenSearch. |
| Is network traffic between services restricted to VPC? | HIGH | Multi-region active-active without VPC peering risks data traversing public internet. | Deploy all services in VPCs; use AWS PrivateLink for cross-service calls. |
| Is immutable audit logging in place? | HIGH | FSI Lens requires tamper-proof audit trail. | Enable CloudTrail with S3 Object Lock (COMPLIANCE mode, 7-year retention). |
| Are secrets managed in AWS Secrets Manager? | MEDIUM | Hardcoded credentials not detected, but not confirmed absent. | Enforce Secrets Manager for all credentials; enable automatic rotation. |
| Is MFA enforced for all IAM users? | GOOD_PRACTICE | Assumed enforced for production accounts. | Confirm via IAM credential report; set SCP to require MFA. |

---

## Reliability

| Question | Risk | Finding | Improvement |
|---|---|---|---|
| Does the architecture meet the stated 99.99% SLA? | HIGH | Single-region Lambda + API Gateway achieves ~99.95%; multi-region active-active required. | Deploy Route 53 latency routing + health-check failover across ≥2 regions. |
| Is the RTO/RPO defined and tested? | MEDIUM | Not specified in workload description. | Define RTO < 15 min, RPO < 5 min for FSI trade data; automate DR drills quarterly. |
| Are circuit breakers implemented for downstream dependencies? | MEDIUM | CQRS event sourcing with upstream dependencies (market data, settlement) needs isolation. | Implement AWS Lambda Destinations + SQS dead-letter queues for event processing. |

---

## Performance Efficiency

| Question | Risk | Finding | Improvement |
|---|---|---|---|
| Is the read model (CQRS query side) optimised for latency? | MEDIUM | No caching layer mentioned. | Add ElastiCache (Redis) for query-side read model; target < 10ms p99 for trade queries. |
| Are auto-scaling policies tuned for traffic patterns? | LOW | Lambda scales automatically; ECS Fargate needs scaling policy tuning. | Set target tracking scaling on ECS; configure Bedrock Provisioned Throughput for consistent LLM latency. |

---

## Cost Optimization

| Question | Risk | Finding | Improvement |
|---|---|---|---|
| Is multi-region active-active cost impact documented? | MEDIUM | Multi-region roughly triples base infrastructure cost. | Document cost model: base region × 2 + Route 53 health checks + S3 CRR egress. |
| Are Savings Plans applied for predictable Fargate workloads? | LOW | Not applicable at MVP; relevant at production scale. | Apply Compute Savings Plans for ≥1 year commitment once baseline traffic is established. |

---

## Sustainability

| Question | Risk | Finding | Improvement |
|---|---|---|---|
| Are workloads scheduled to avoid idle resource consumption? | LOW | Lambda scales to zero; no idle compute. | For Fargate, implement scheduled scaling to reduce capacity during off-market hours (weekends, overnight). |
| Is the AWS region selected for renewable energy availability? | LOW | `us-east-1` has committed to 100% renewable energy by 2030. | Consider `eu-west-1` (Ireland, high renewable mix) for the secondary region. |
