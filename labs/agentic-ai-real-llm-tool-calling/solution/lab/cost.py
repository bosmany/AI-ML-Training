"""Token/cost usage logging using a small, explicitly-pinned per-model price
table.

No LLM API exposes a "$" figure directly — every provider's usage response
gives you ``prompt_tokens``/``completion_tokens`` (real ``RealLLMClient`` calls
get these from Groq's real response; the offline tests get them from
``FakeLLMClient``'s scripted responses), and converting that into money is
always a local table lookup like this one.

CHECK CURRENT PRICING at https://groq.com/pricing before relying on these
numbers for a real budget: provider pricing changes without notice, and this
table is a snapshot taken while building this lab, not a live feed.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from decimal import Decimal

# USD per 1,000,000 tokens. Snapshot of Groq's published on-demand pricing for
# the models this lab's RealLLMClient defaults to / can be pointed at.
# CHECK CURRENT PRICING before trusting this for a real budget.
PRICE_TABLE_USD_PER_MILLION_TOKENS: dict[str, dict[str, Decimal]] = {
    "llama-3.3-70b-versatile": {"input": Decimal("0.59"), "output": Decimal("0.79")},
    "llama-3.1-8b-instant": {"input": Decimal("0.05"), "output": Decimal("0.08")},
    "llama3-70b-8192": {"input": Decimal("0.59"), "output": Decimal("0.79")},
    "llama3-8b-8192": {"input": Decimal("0.05"), "output": Decimal("0.08")},
}

_MILLION = Decimal(1_000_000)


def compute_cost(model: str, prompt_tokens: int, completion_tokens: int) -> Decimal:
    """USD cost of one LLM call.

    Unknown models raise ``KeyError`` on purpose: a silent $0.00 for an
    unpriced model is exactly how real cost-tracking bill-shock happens —
    better to fail loudly the first time a new model is used than to quietly
    under-report spend forever.
    """
    if prompt_tokens < 0 or completion_tokens < 0:
        raise ValueError("token counts cannot be negative")
    try:
        prices = PRICE_TABLE_USD_PER_MILLION_TOKENS[model]
    except KeyError as exc:
        raise KeyError(
            f"no pinned price for model {model!r}; add it to "
            "PRICE_TABLE_USD_PER_MILLION_TOKENS (check https://groq.com/pricing "
            "for the current rate) before relying on cost tracking for it"
        ) from exc
    cost = (
        Decimal(prompt_tokens) * prices["input"] + Decimal(completion_tokens) * prices["output"]
    ) / _MILLION
    return cost


@dataclass(slots=True)
class UsageRecord:
    model: str
    prompt_tokens: int
    completion_tokens: int
    cost_usd: Decimal


@dataclass(slots=True)
class UsageLogger:
    """Accumulates one ``UsageRecord`` per LLM call, so a whole agent run
    (which is one or more calls — one per ReAct step) can report a total cost
    and total tokens, not just the last call's."""

    records: list[UsageRecord] = field(default_factory=list)

    def log(self, model: str, prompt_tokens: int, completion_tokens: int) -> UsageRecord:
        record = UsageRecord(
            model=model,
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
            cost_usd=compute_cost(model, prompt_tokens, completion_tokens),
        )
        self.records.append(record)
        return record

    def total_cost(self) -> Decimal:
        return sum((r.cost_usd for r in self.records), Decimal("0"))

    def total_tokens(self) -> tuple[int, int]:
        return (
            sum(r.prompt_tokens for r in self.records),
            sum(r.completion_tokens for r in self.records),
        )
