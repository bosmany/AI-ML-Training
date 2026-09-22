"""Tests for the pinned-price-table cost calculator and usage logger."""
from decimal import Decimal

import pytest

from lab.cost import PRICE_TABLE_USD_PER_MILLION_TOKENS, UsageLogger, compute_cost


def test_compute_cost_matches_a_hand_worked_example():
    # llama-3.1-8b-instant: $0.05 / 1M input, $0.08 / 1M output (see PRICE_TABLE)
    cost = compute_cost("llama-3.1-8b-instant", prompt_tokens=1_000_000, completion_tokens=1_000_000)
    assert cost == Decimal("0.05") + Decimal("0.08")


def test_compute_cost_is_zero_for_zero_tokens():
    assert compute_cost("llama-3.1-8b-instant", 0, 0) == Decimal("0")


def test_compute_cost_scales_linearly_with_tokens():
    small = compute_cost("llama-3.3-70b-versatile", 1000, 1000)
    large = compute_cost("llama-3.3-70b-versatile", 10_000, 10_000)
    assert large == small * 10


def test_compute_cost_returns_a_decimal_never_a_float():
    cost = compute_cost("llama-3.1-8b-instant", 123, 456)
    assert isinstance(cost, Decimal)


def test_compute_cost_rejects_negative_token_counts():
    with pytest.raises(ValueError):
        compute_cost("llama-3.1-8b-instant", -1, 0)
    with pytest.raises(ValueError):
        compute_cost("llama-3.1-8b-instant", 0, -1)


def test_compute_cost_raises_a_clear_error_for_an_unpinned_model():
    with pytest.raises(KeyError, match="no pinned price"):
        compute_cost("some-brand-new-model-nobody-priced-yet", 100, 100)


def test_every_price_table_entry_has_input_and_output_rates_and_prices_correctly():
    for model, prices in PRICE_TABLE_USD_PER_MILLION_TOKENS.items():
        assert set(prices) == {"input", "output"}, model
        assert prices["input"] > 0
        assert prices["output"] > 0
        assert compute_cost(model, 1_000_000, 1_000_000) == prices["input"] + prices["output"]


def test_usage_logger_log_appends_a_record_with_the_correct_cost():
    logger = UsageLogger()
    record = logger.log("llama-3.1-8b-instant", prompt_tokens=1_000_000, completion_tokens=0)
    assert record.model == "llama-3.1-8b-instant"
    assert record.cost_usd == Decimal("0.05")
    assert logger.records == [record]


def test_usage_logger_total_cost_sums_every_call():
    logger = UsageLogger()
    logger.log("llama-3.1-8b-instant", 1_000_000, 0)  # $0.05
    logger.log("llama-3.1-8b-instant", 0, 1_000_000)  # $0.08
    assert logger.total_cost() == Decimal("0.13")


def test_usage_logger_total_cost_is_zero_decimal_when_empty():
    logger = UsageLogger()
    assert logger.total_cost() == Decimal("0")
    assert isinstance(logger.total_cost(), Decimal)


def test_usage_logger_total_tokens_sums_prompt_and_completion_separately():
    logger = UsageLogger()
    logger.log("llama-3.1-8b-instant", 100, 20)
    logger.log("llama-3.1-8b-instant", 50, 10)
    assert logger.total_tokens() == (150, 30)


def test_usage_logger_total_tokens_is_zero_zero_when_empty():
    logger = UsageLogger()
    assert logger.total_tokens() == (0, 0)
