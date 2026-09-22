"""A scripted, in-memory ``LLMClient`` double used by every hermetic test in
this lab.

It structurally satisfies ``lab.llm_client.LLMClient`` (``.model``, ``.chat``,
``.stream_chat``) without ever touching the network, so ``lab.agent.ReActAgent``
runs COMPLETELY UNMODIFIED against it — the same class a human points at
``RealLLMClient`` + a real ``GROQ_API_KEY`` in ``tests/test_live_llm.py``.
This is the dependency-injection boundary the spec asks for.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from lab.llm_client import LLMResponse, StreamEvent, ToolCall


@dataclass
class FakeLLMClient:
    """Pops one scripted ``LLMResponse`` per ``.chat()`` call, in order, and
    one scripted list of ``StreamEvent``\\ s per ``.stream_chat()`` call.

    Raises ``AssertionError`` if called more times than scripted — a bug that
    makes the agent loop further than a test expects should fail that test
    loudly and immediately, not hang or silently pass.
    """

    # A real, PRICED model id (see lab.cost.PRICE_TABLE_USD_PER_MILLION_TOKENS)
    # so agent.usage.log() — which deliberately raises on an unpinned model —
    # works out of the box for every test that does not care about pricing.
    model: str = "llama-3.1-8b-instant"
    responses: list[LLMResponse] = field(default_factory=list)
    stream_events: list[list[StreamEvent]] = field(default_factory=list)
    calls: list[dict[str, Any]] = field(default_factory=list)

    def chat(self, messages, tools):
        self.calls.append({"messages": messages, "tools": tools, "mode": "chat"})
        if not self.responses:
            raise AssertionError(
                "FakeLLMClient.chat() called more times than scripted responses "
                "provided — the agent looped further than the test expected."
            )
        return self.responses.pop(0)

    def stream_chat(self, messages, tools):
        self.calls.append({"messages": messages, "tools": tools, "mode": "stream"})
        if not self.stream_events:
            raise AssertionError(
                "FakeLLMClient.stream_chat() called more times than scripted "
                "event lists provided — the agent looped further than the test expected."
            )
        return iter(self.stream_events.pop(0))


def text_response(
    content: str, *, prompt_tokens: int = 10, completion_tokens: int = 5
) -> LLMResponse:
    """A final-answer turn: content, no tool calls."""
    return LLMResponse(
        content=content,
        tool_calls=(),
        finish_reason="stop",
        prompt_tokens=prompt_tokens,
        completion_tokens=completion_tokens,
    )


def tool_call_response(
    name: str,
    arguments: dict[str, Any],
    *,
    call_id: str = "call_1",
    content: str | None = None,
    prompt_tokens: int = 10,
    completion_tokens: int = 5,
) -> LLMResponse:
    """A turn where the model asks for exactly one tool call."""
    return LLMResponse(
        content=content,
        tool_calls=(ToolCall(id=call_id, name=name, arguments=arguments),),
        finish_reason="tool_calls",
        prompt_tokens=prompt_tokens,
        completion_tokens=completion_tokens,
    )


def multi_tool_call_response(
    calls: list[tuple[str, dict[str, Any]]],
    *,
    content: str | None = None,
    prompt_tokens: int = 10,
    completion_tokens: int = 5,
) -> LLMResponse:
    """A turn where the model asks for several tool calls in parallel."""
    tool_calls = tuple(
        ToolCall(id=f"call_{i}", name=name, arguments=args) for i, (name, args) in enumerate(calls)
    )
    return LLMResponse(
        content=content,
        tool_calls=tool_calls,
        finish_reason="tool_calls",
        prompt_tokens=prompt_tokens,
        completion_tokens=completion_tokens,
    )
