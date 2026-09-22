"""LLM client abstraction.

This module defines a typed interface (``LLMClient``) between the agent loop
(``agent.py``) and whatever actually produces model output, plus the one real
implementation of it: ``RealLLMClient``, which talks to Groq's OpenAI-compatible
API using the official ``openai`` Python SDK.

Why bother with an interface at all: Chapter 34 (``projects/ch34-agentic-ai-system.html``)
stood in a hard-coded ``decide_next_action()`` for what, in a real system, is an
LLM API call, and told you to "swap that one function for a real LLM call [and]
the rest of the architecture is unchanged." This module IS that swap. Because
``agent.py`` only ever talks to the ``LLMClient`` protocol below, the exact same
``ReActAgent`` runs unmodified against:

  * ``RealLLMClient`` — a real network call to Groq, needs ``GROQ_API_KEY``.
  * ``FakeLLMClient`` (``tests/fake_llm.py``) — a scripted, in-memory double
    with zero network and zero cost, used by every hermetic test.

Given complete: this file has no learner TODOs. It is infrastructure/plumbing
that the lab's hermetic tests deliberately do not exercise (see README.md,
"What's graded offline vs. what needs a key"); the interesting, testable logic
for this lab lives in guardrail.py, memory.py, cost.py and agent.py.
"""
from __future__ import annotations

import json
import os
from collections.abc import Iterable
from dataclasses import dataclass
from typing import Any, Protocol, runtime_checkable

# Groq's OpenAI-compatible endpoint. Point the official `openai` SDK's `OpenAI`
# client at this base_url with a Groq API key, and the existing OpenAI
# tool-calling code paths (chat.completions.create, streaming, tool_calls...)
# work completely unchanged.
GROQ_BASE_URL = "https://api.groq.com/openai/v1"

# A Groq-hosted model that supports tool calling on the free tier as of this
# writing (2026). CHECK https://console.groq.com/docs/models for the current
# list — Groq deprecates and renames hosted models faster than most providers,
# and an old model id here will fail loudly (a 4xx from the API), not silently.
DEFAULT_MODEL = "llama-3.3-70b-versatile"

GROQ_API_KEY_ENV_VAR = "GROQ_API_KEY"


@dataclass(frozen=True, slots=True)
class ToolCall:
    """One tool invocation the model asked for."""

    id: str
    name: str
    arguments: dict[str, Any]


@dataclass(frozen=True, slots=True)
class LLMResponse:
    """A complete model turn — either assembled from one non-streamed API
    response, or reassembled from a stream of ``StreamEvent`` chunks by
    ``agent.assemble_stream_response``. Either way, the rest of the agent loop
    only ever sees this shape."""

    content: str | None
    tool_calls: tuple[ToolCall, ...]
    finish_reason: str
    prompt_tokens: int
    completion_tokens: int


@dataclass(frozen=True, slots=True)
class StreamEvent:
    """One incremental chunk of a streamed model turn, already normalised out
    of whichever provider's raw wire format produced it. A real streamed tool
    call arrives as MANY of these: one chunk carries the tool's id/name, and
    the arguments arrive as partial JSON string fragments across several more
    chunks, keyed by ``tool_call_index`` (a model can stream >1 tool call in
    parallel, each with its own index)."""

    content_delta: str = ""
    tool_call_index: int | None = None
    tool_call_id: str | None = None
    tool_call_name: str | None = None
    tool_call_arguments_delta: str = ""
    finish_reason: str | None = None
    prompt_tokens: int | None = None
    completion_tokens: int | None = None


@runtime_checkable
class LLMClient(Protocol):
    """What ``agent.ReActAgent`` needs from a model backend. ``RealLLMClient``
    and ``tests/fake_llm.py:FakeLLMClient`` both satisfy this structurally
    (duck typing via ``Protocol``) without either one importing the other."""

    model: str

    def chat(
        self, messages: list[dict[str, Any]], tools: list[dict[str, Any]]
    ) -> LLMResponse: ...

    def stream_chat(
        self, messages: list[dict[str, Any]], tools: list[dict[str, Any]]
    ) -> Iterable[StreamEvent]: ...


def _safe_json_loads(raw: str) -> dict[str, Any]:
    """A model can (rarely) emit malformed JSON arguments; never let that
    crash the agent — surface it as a marked, inspectable dict instead."""
    if not raw:
        return {}
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        return {"_raw": raw, "_parse_error": True}


class RealLLMClient:
    """Real OpenAI-compatible tool-calling client, pointed at Groq's free-tier
    endpoint by default.

    Needs ``GROQ_API_KEY`` in the environment (or an explicit ``api_key=``).
    Get a free key at https://console.groq.com/keys — see README.md.

    This is the ONLY class in this lab that ever makes a network call.
    Nothing under ``tests/`` except ``tests/test_live_llm.py`` (marked
    ``@pytest.mark.live``, skipped without a key) ever instantiates or calls
    this class — that boundary is what keeps ``LAB_TARGET=solution pytest``
    entirely offline, free and deterministic.
    """

    def __init__(
        self,
        model: str = DEFAULT_MODEL,
        api_key: str | None = None,
        base_url: str = GROQ_BASE_URL,
    ) -> None:
        try:
            from openai import OpenAI
        except ImportError as exc:  # pragma: no cover - openai is in requirements.txt
            raise RuntimeError(
                "The 'openai' package is required for RealLLMClient. "
                "Run: pip install -r requirements.txt"
            ) from exc

        key = api_key or os.environ.get(GROQ_API_KEY_ENV_VAR)
        if not key:
            raise RuntimeError(
                f"No API key found. Set the {GROQ_API_KEY_ENV_VAR} environment "
                "variable (see README.md, 'Getting a free Groq API key') or "
                "pass api_key= explicitly."
            )
        self.model = model
        self._client = OpenAI(api_key=key, base_url=base_url)

    def chat(
        self, messages: list[dict[str, Any]], tools: list[dict[str, Any]]
    ) -> LLMResponse:
        completion = self._client.chat.completions.create(
            model=self.model,
            messages=messages,
            tools=tools or None,
            tool_choice="auto" if tools else None,
        )
        choice = completion.choices[0]
        message = choice.message
        tool_calls = tuple(
            ToolCall(
                id=tc.id,
                name=tc.function.name,
                arguments=_safe_json_loads(tc.function.arguments),
            )
            for tc in (message.tool_calls or [])
        )
        usage = completion.usage
        return LLMResponse(
            content=message.content,
            tool_calls=tool_calls,
            finish_reason=choice.finish_reason,
            prompt_tokens=usage.prompt_tokens if usage else 0,
            completion_tokens=usage.completion_tokens if usage else 0,
        )

    def stream_chat(
        self, messages: list[dict[str, Any]], tools: list[dict[str, Any]]
    ) -> Iterable[StreamEvent]:
        stream = self._client.chat.completions.create(
            model=self.model,
            messages=messages,
            tools=tools or None,
            tool_choice="auto" if tools else None,
            stream=True,
            # Ask the API to emit one extra final chunk carrying real usage
            # (prompt/completion token counts) — without this, a streamed
            # response has no token counts at all, and cost.py cannot cost it.
            stream_options={"include_usage": True},
        )
        for chunk in stream:
            if not chunk.choices:
                # The final usage-only chunk (from stream_options above) has
                # an empty `choices` list and `usage` populated instead.
                if chunk.usage:
                    yield StreamEvent(
                        prompt_tokens=chunk.usage.prompt_tokens,
                        completion_tokens=chunk.usage.completion_tokens,
                    )
                continue
            choice = chunk.choices[0]
            delta = choice.delta
            tool_delta = (delta.tool_calls or [None])[0]
            yield StreamEvent(
                content_delta=delta.content or "",
                tool_call_index=tool_delta.index if tool_delta else None,
                tool_call_id=tool_delta.id if tool_delta else None,
                tool_call_name=(
                    tool_delta.function.name if tool_delta and tool_delta.function else None
                ),
                tool_call_arguments_delta=(
                    tool_delta.function.arguments
                    if tool_delta and tool_delta.function and tool_delta.function.arguments
                    else ""
                ),
                finish_reason=choice.finish_reason,
            )
