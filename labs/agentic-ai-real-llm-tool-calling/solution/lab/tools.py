"""Example tools the agent can call.

Given complete — the interesting, learner-implemented parts of this lab are
the guardrail (``guardrail.py``), the memory buffer (``memory.py``), the cost
tracker (``cost.py``) and the ReAct loop itself (``agent.py``). These tools
exist so those pieces have something real to exercise.

``calculator`` is deliberately NOT ``eval(expression)`` — that is the classic
"calculator tool" remote-code-execution bug in toy agent demos (a model that
echoes attacker-controlled text into a tool argument can make ``eval`` run
arbitrary Python). It instead parses the expression into an AST and walks a
small whitelist of arithmetic node types.
"""
from __future__ import annotations

import ast
import operator
from collections.abc import Callable
from datetime import datetime, timezone
from typing import Any

_ALLOWED_BINOPS: dict[type, Callable[[float, float], float]] = {
    ast.Add: operator.add,
    ast.Sub: operator.sub,
    ast.Mult: operator.mul,
    ast.Div: operator.truediv,
    ast.Pow: operator.pow,
    ast.Mod: operator.mod,
}
_ALLOWED_UNARYOPS: dict[type, Callable[[float], float]] = {
    ast.UAdd: operator.pos,
    ast.USub: operator.neg,
}


def _eval_node(node: ast.AST) -> float:
    if isinstance(node, ast.Constant) and isinstance(node.value, (int, float)):
        return node.value
    if isinstance(node, ast.BinOp) and type(node.op) in _ALLOWED_BINOPS:
        return _ALLOWED_BINOPS[type(node.op)](_eval_node(node.left), _eval_node(node.right))
    if isinstance(node, ast.UnaryOp) and type(node.op) in _ALLOWED_UNARYOPS:
        return _ALLOWED_UNARYOPS[type(node.op)](_eval_node(node.operand))
    raise ValueError(f"disallowed expression element: {ast.dump(node)}")


def calculator(expression: str) -> dict[str, Any]:
    """Evaluate a basic arithmetic expression safely: + - * / % ** and parens.
    Never calls eval()/exec() on the raw string. Anything outside the
    whitelisted AST node types (name lookups, attribute access, calls,
    comprehensions, ...) is rejected before it can run."""
    try:
        tree = ast.parse(expression, mode="eval")
        result = _eval_node(tree.body)
    except (SyntaxError, ValueError, ZeroDivisionError, TypeError) as exc:
        return {"error": f"invalid expression: {exc}"}
    return {"result": result}


def get_current_time(
    timezone_name: str = "UTC", *, _now: Callable[[], datetime] | None = None
) -> dict[str, Any]:
    """Return the current time. ``_now`` is an injectable clock used only by
    tests (see tests/test_agent_loop.py); a real caller never passes it, so
    it defaults to the genuine wall clock — this tool is still "real time",
    just deterministically testable."""
    now = (_now or (lambda: datetime.now(timezone.utc)))()
    return {"timezone_name": timezone_name, "iso": now.isoformat()}


_LOCAL_DOCS = [
    "Groq serves open models (Llama, etc.) over an OpenAI-compatible API with a free tier.",
    "The ReAct pattern is Thought -> Action -> Observation, repeated until a final answer.",
    "max_steps is a hard cap that stops an agent loop from running forever.",
    "A prompt-injection guardrail rejects tool arguments that try to override the agent's instructions.",
    "Conversation memory must be trimmed by token count so a long chat does not blow the context window.",
]


def search_local_docs(query: str) -> dict[str, Any]:
    """Case-insensitive substring search over a small fixed local corpus —
    stands in for a real retrieval tool without needing a vector DB, an
    embeddings model, or any network call (see labs/rag-real-vector-db-deploy
    for the real thing)."""
    q = query.lower().strip()
    hits = [doc for doc in _LOCAL_DOCS if q in doc.lower()]
    return {"query": query, "matches": hits}


TOOL_REGISTRY: dict[str, Callable[..., dict[str, Any]]] = {
    "calculator": calculator,
    "get_current_time": get_current_time,
    "search_local_docs": search_local_docs,
}

# OpenAI/Groq "function calling" tool schemas — the exact shape sent as the
# `tools=` argument to `chat.completions.create` (real or fake, same shape).
TOOL_SPECS: list[dict[str, Any]] = [
    {
        "type": "function",
        "function": {
            "name": "calculator",
            "description": "Evaluate a basic arithmetic expression, e.g. '(3 + 4) * 2'.",
            "parameters": {
                "type": "object",
                "properties": {"expression": {"type": "string"}},
                "required": ["expression"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_current_time",
            "description": "Get the current date/time.",
            "parameters": {
                "type": "object",
                "properties": {
                    "timezone_name": {"type": "string", "description": "e.g. 'UTC'"}
                },
                "required": [],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "search_local_docs",
            "description": "Search a small local knowledge base about this lab's own concepts.",
            "parameters": {
                "type": "object",
                "properties": {"query": {"type": "string"}},
                "required": ["query"],
            },
        },
    },
]
