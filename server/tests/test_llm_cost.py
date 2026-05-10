"""Tests for per-call token cost accounting in services.llm.

Covers:
    - MODEL_PRICING is populated for every model in MAPLE's MODEL_CHAIN.
    - _estimate_cost returns input_tokens/1K * in_rate + output_tokens/1K * out_rate.
    - Unknown model returns 0.0 (safe default — never block a call over pricing).
"""

import pytest

from app.services.llm import (
    MODEL_CHAIN,
    MODEL_PRICING,
    _estimate_cost,
)


def test_pricing_covers_every_model_in_chain():
    for spec in MODEL_CHAIN:
        assert spec.name in MODEL_PRICING, (
            f"MODEL_PRICING missing entry for {spec.name!r} — "
            f"observability will silently record $0 for this model"
        )


@pytest.mark.parametrize("model_name", list(MODEL_PRICING.keys()))
def test_estimate_cost_matches_rate_card(model_name: str):
    in_rate, out_rate = MODEL_PRICING[model_name]
    # 1000 input + 2000 output — easy mental math.
    cost = _estimate_cost(model_name, 1000, 2000)
    expected = (1000 / 1000.0) * in_rate + (2000 / 1000.0) * out_rate
    assert cost == pytest.approx(expected, rel=1e-9)


def test_estimate_cost_zero_tokens_is_zero():
    for name in MODEL_PRICING:
        assert _estimate_cost(name, 0, 0) == 0.0


def test_estimate_cost_unknown_model_returns_zero():
    assert _estimate_cost("nonexistent-model", 1_000_000, 1_000_000) == 0.0
