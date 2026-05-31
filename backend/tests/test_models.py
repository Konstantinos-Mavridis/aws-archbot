"""Unit tests for Pydantic models."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from app.models import (
    ArchitectureRequest,
    ChecklistItem,
    Lens,
    NonFunctionals,
)


def test_default_request() -> None:
    req = ArchitectureRequest(workload_description="simple web app")
    assert req.lens == Lens.GENERAL
    assert req.non_functionals.regions is None


def test_fsi_lens() -> None:
    req = ArchitectureRequest(
        workload_description="trade finance platform",
        lens=Lens.FSI,
        non_functionals=NonFunctionals(sla_percent=99.99, regions=2, compliance_flags=["PCI-DSS"]),
    )
    assert req.lens == Lens.FSI
    assert req.non_functionals.compliance_flags == ["PCI-DSS"]


def test_short_description_rejected() -> None:
    with pytest.raises(ValidationError):
        ArchitectureRequest(workload_description="hi")


def test_checklist_item_risk_levels() -> None:
    item = ChecklistItem(
        question="Do you use MFA?",
        risk_level="HIGH",
        finding="MFA not enforced",
        improvement_suggestion="Enable MFA on all IAM users",
    )
    assert item.risk_level == "HIGH"


def test_invalid_risk_level_rejected() -> None:
    with pytest.raises(ValidationError):
        ChecklistItem(
            question="?",
            risk_level="CRITICAL",  # not in Literal
            finding="x",
            improvement_suggestion="y",
        )
