"""Tests for cost_estimator module."""

from __future__ import annotations

from app.cost_estimator import cost_context_hint, estimate_cost_tiers
from app.models import Lens, NonFunctionals


class TestCostContextHint:
    def test_single_region_default(self) -> None:
        hint = cost_context_hint(NonFunctionals())
        assert "single-region" in hint.lower()

    def test_multi_region_two(self) -> None:
        hint = cost_context_hint(NonFunctionals(regions=2))
        assert "multi-region" in hint.lower()

    def test_multi_region_three_plus(self) -> None:
        hint = cost_context_hint(NonFunctionals(regions=3))
        assert "triple" in hint.lower() or "three" in hint.lower() or "3" in hint

    def test_high_sla_mentioned(self) -> None:
        hint = cost_context_hint(NonFunctionals(sla_percent=99.99))
        assert "99.99" in hint

    def test_compliance_flags_included(self) -> None:
        hint = cost_context_hint(NonFunctionals(compliance_flags=["PCI-DSS", "SOX"]))
        assert "PCI-DSS" in hint
        assert "SOX" in hint


class TestEstimateCostTiers:
    def test_returns_three_tiers(self) -> None:
        tiers = estimate_cost_tiers(lens=Lens.GENERAL, non_functionals=NonFunctionals())
        tier_names = {t.tier for t in tiers}
        assert tier_names == {"dev", "staging", "prod"}

    def test_all_tiers_have_required_fields(self) -> None:
        tiers = estimate_cost_tiers(lens=Lens.GENERAL, non_functionals=NonFunctionals())
        for t in tiers:
            assert t.tier in {"dev", "staging", "prod"}
            assert t.monthly_estimate_hint
            assert t.assumptions

    def test_fsi_lens_includes_kms_in_assumptions(self) -> None:
        tiers = estimate_cost_tiers(
            lens=Lens.FSI,
            non_functionals=NonFunctionals(regions=2, sla_percent=99.99, compliance_flags=["PCI-DSS"]),
        )
        all_text = " ".join(t.assumptions for t in tiers).lower()
        assert any(kw in all_text for kw in ["kms", "encrypt", "audit", "cmk"])

    def test_healthcare_lens_includes_hipaa_terms(self) -> None:
        tiers = estimate_cost_tiers(
            lens=Lens.HEALTHCARE,
            non_functionals=NonFunctionals(compliance_flags=["HIPAA"]),
        )
        all_text = " ".join(t.assumptions for t in tiers).lower()
        assert any(kw in all_text for kw in ["hipaa", "phi", "encrypt", "audit"])

    def test_multi_region_mentions_regions_in_assumptions(self) -> None:
        tiers = estimate_cost_tiers(
            lens=Lens.GENERAL,
            non_functionals=NonFunctionals(regions=3),
        )
        multi_text = " ".join(t.assumptions for t in tiers).lower()
        assert "region" in multi_text

    def test_compliance_flags_appear_in_assumptions(self) -> None:
        tiers = estimate_cost_tiers(
            lens=Lens.FSI,
            non_functionals=NonFunctionals(compliance_flags=["SOX", "PCI-DSS"]),
        )
        all_text = " ".join(t.assumptions for t in tiers)
        assert "SOX" in all_text or "PCI-DSS" in all_text
