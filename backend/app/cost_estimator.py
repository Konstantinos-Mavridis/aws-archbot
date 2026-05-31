"""Qualitative cost tier heuristics.

Does NOT produce real dollar estimates — that requires AWS Pricing API
calls and is out of scope for the MVP. Instead, this module maps workload
characteristics to qualitative bands so the LLM output remains honest.

Two public functions:
- cost_context_hint: returns a string for inclusion in the LLM system prompt.
- estimate_cost_tiers: returns typed CostTier objects for use in tests or
  when operating in demo mode (no LLM call).
"""

from __future__ import annotations

from app.models import CostTier, Lens, NonFunctionals


def cost_context_hint(nfr: NonFunctionals) -> str:
    """Return a cost guidance string to include in the LLM prompt."""
    hints: list[str] = []

    regions = nfr.regions or 1
    if regions >= 3:
        hints.append("Multi-region active-active roughly triples base infrastructure cost.")
    elif regions == 2:
        hints.append("Active-passive multi-region adds ~50–80% to base cost for standby capacity.")

    sla = nfr.sla_percent
    if sla and sla >= 99.99:
        hints.append(
            "99.99% SLA requires redundant NAT gateways, multi-AZ deployments, and "
            "potentially Route 53 ARC health checks — adds meaningfully to monthly cost."
        )

    if nfr.compliance_flags:
        flags = ", ".join(nfr.compliance_flags)
        hints.append(
            f"Compliance requirements ({flags}) may require dedicated HSMs, "
            "additional logging/monitoring infrastructure, and audit tooling."
        )

    if not hints:
        hints.append("Standard single-region, multi-AZ deployment cost profile.")

    return " ".join(hints)


def estimate_cost_tiers(lens: Lens, non_functionals: NonFunctionals) -> list[CostTier]:
    """Return qualitative CostTier objects based on workload characteristics.

    Used in demo mode (no Bedrock call) and directly in unit tests.
    The LLM generates richer narratives in production; this provides
    a deterministic fallback with sensible qualitative bands.
    """
    regions = non_functionals.regions or 1
    compliance = ", ".join(non_functionals.compliance_flags) if non_functionals.compliance_flags else None
    multi_region_note = f"{regions} regions. " if regions > 1 else ""
    compliance_note = f"Compliance: {compliance}. " if compliance else ""

    lens_note = {
        Lens.FSI: "CMK encryption, CloudTrail, audit logging, KMS key rotation. ",
        Lens.HEALTHCARE: "HIPAA-eligible services, PHI encryption, audit log retention. ",
        Lens.GENERAL: "",
    }[lens]

    base_assumptions = f"{multi_region_note}{compliance_note}{lens_note}"

    return [
        CostTier(
            tier="dev",
            monthly_estimate_hint="Under $300/month",
            assumptions=(
                base_assumptions
                + "Single region, minimal traffic, Fargate Spot where applicable, no Savings Plans."
            ).strip(),
        ),
        CostTier(
            tier="staging",
            monthly_estimate_hint="$500–$2,000/month",
            assumptions=(
                base_assumptions
                + "Multi-AZ, moderate load, On-Demand pricing, basic observability stack."
            ).strip(),
        ),
        CostTier(
            tier="prod",
            monthly_estimate_hint="$3,000–$20,000/month",
            assumptions=(
                base_assumptions
                + "Full HA, "
                + ("multi-region active-active, " if regions > 1 else "")
                + "WAF, Shield Standard, Savings Plans, dedicated monitoring."
            ).strip(),
        ),
    ]
