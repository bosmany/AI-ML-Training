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

    TODO:
    - raise ValueError if prompt_tokens < 0 or completion_tokens < 0
    - look up PRICE_TABLE_USD_PER_MILLION_TOKENS[model]; if the model is
      missing, raise KeyError with a message that names the model and points
      at PRICE_TABLE_USD_PER_MILLION_TOKENS + https://groq.com/pricing (a
      silent $0.00 for an unpriced model is exactly how real cost-tracking
      bill-shock happens — fail loudly instead)
    - cost = (prompt_tokens * price["input"] + completion_tokens * price["output"]) / 1_000_000
      using Decimal arithmetic throughout (never float — see
      labs/python-expense-tracker for why float money math is a real bug class)
    """
    raise NotImplementedError


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
        """TODO: build a UsageRecord (compute cost_usd via compute_cost),
        append it to self.records, and return it."""
        raise NotImplementedError

    def total_cost(self) -> Decimal:
        """TODO: sum of every record's cost_usd, as a Decimal (start the sum
        from Decimal("0"), not int 0, so an empty log returns Decimal("0")
        rather than plain int 0)."""
        raise NotImplementedError

    def total_tokens(self) -> tuple[int, int]:
        """TODO: return (sum of every record's prompt_tokens, sum of every
        record's completion_tokens)."""
        raise NotImplementedError
