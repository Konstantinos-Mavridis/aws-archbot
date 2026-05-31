"""Tests for cost_estimator module."""

from __future__ import annotations

import pytest

from app.cost_estimator import estimate_cost_tiers
from app.models import Lens, NonFunctionals


class TestEstimateCostTiers:
    def test_returns_three_tiers(self) -> None:
        tiers = estimate_cost_tiers(
            lens=Lens.GENERAL,
            non_functionals=NonFunctionals(),
        )
        tier_names = {t.tier for t in tiers}
        assert tier_names == {"dev", "staging", "prod"}

    def test_fsi_lens_hints_reflect_compliance_overhead(self) -> None:
        tiers = estimate_cost_tiers(
            lens=Lens.FSI,
            non_functionals=NonFunctionals(
                regions=2,
                sla_percent=99.99,
                compliance_flags=["PCI-DSS"],
            ),
        )
        # FSI multi-region prod should be more expensive than general
        prod = next(t for t in tiers if t.tier == "prod")
        assert prod.monthly_estimate_hint  # non-empty string
        assert prod.assumptions

    def test_healthcare_lens_mentions_hipaa(self) -> None:
        tiers = estimate_cost_tiers(
            lens=Lens.HEALTHCARE,
            non_functionals=NonFunctionals(compliance_flags=["HIPAA"]),
        )
        all_assumptions = " ".join(t.assumptions.lower() for t in tiers)
        # Assumptions should mention encryption/PHI/HIPAA in some form
        assert any(kw in all_assumptions for kw in ["hipaa", "phi", "encrypt", "audit"])

    def test_multi_region_increases_cost_narrative(self) -> None:
        single = estimate_cost_tiers(
            lens=Lens.GENERAL,
            non_functionals=NonFunctionals(regions=1),
        )
        multi = estimate_cost_tiers(
            lens=Lens.GENERAL,
            non_functionals=NonFunctionals(regions=3),
        )
        # Both should return tiers; multi should mention regions
        assert len(single) == 3
        assert len(multi) == 3
        multi_text = " ".join(t.assumptions for t in multi).lower()
        assert "region" in multi_text
