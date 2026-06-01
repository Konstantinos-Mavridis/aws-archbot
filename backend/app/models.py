"""Pydantic models for ArchBot request / response contracts.

The JSON schema defined here is also embedded in the LLM system prompt
so that Claude outputs exactly the shape we expect.
"""

from __future__ import annotations

from enum import StrEnum
from typing import Literal

from pydantic import BaseModel, Field


class Lens(StrEnum):
    GENERAL = "general"
    FSI = "fsi"
    HEALTHCARE = "healthcare"


class NonFunctionals(BaseModel):
    sla_percent: float | None = Field(None, ge=0, le=100, description="Target SLA, e.g. 99.99")
    regions: int | None = Field(None, ge=1, description="Number of AWS regions")
    rto_minutes: int | None = Field(None, ge=0, description="Recovery Time Objective in minutes")
    rpo_minutes: int | None = Field(None, ge=0, description="Recovery Point Objective in minutes")
    compliance_flags: list[str] = Field(
        default_factory=list,
        description="e.g. ['PCI-DSS', 'HIPAA', 'SOC2']",
    )


class ArchitectureRequest(BaseModel):
    workload_description: str = Field(
        ...,
        min_length=10,
        max_length=2000,
        description="Free-text description of the workload",
    )
    # Use lambda so mypy sees a Callable[[], NonFunctionals] not a bare type.
    non_functionals: NonFunctionals = Field(default_factory=lambda: NonFunctionals())
    lens: Lens = Field(Lens.GENERAL)


class ServiceRecommendation(BaseModel):
    category: str = Field(..., description="e.g. 'compute', 'storage', 'networking'")
    service: str = Field(..., description="AWS service name")
    reasoning: str


class ChecklistItem(BaseModel):
    question: str
    risk_level: Literal["HIGH", "MEDIUM", "LOW", "GOOD_PRACTICE"]
    finding: str
    improvement_suggestion: str


class WellArchitectedChecklist(BaseModel):
    operational_excellence: list[ChecklistItem] = Field(default_factory=list)
    security: list[ChecklistItem] = Field(default_factory=list)
    reliability: list[ChecklistItem] = Field(default_factory=list)
    performance_efficiency: list[ChecklistItem] = Field(default_factory=list)
    cost_optimization: list[ChecklistItem] = Field(default_factory=list)
    sustainability: list[ChecklistItem] = Field(default_factory=list)


class CostTier(BaseModel):
    tier: Literal["dev", "staging", "prod"]
    monthly_estimate_hint: str = Field(
        ..., description="Qualitative hint, e.g. 'Under $200/month'"
    )
    assumptions: str


class ArchitectureResponse(BaseModel):
    architecture_summary: str
    service_recommendations: list[ServiceRecommendation]
    mermaid_diagram: str
    well_architected_checklist: WellArchitectedChecklist
    cost_tiers: list[CostTier]
