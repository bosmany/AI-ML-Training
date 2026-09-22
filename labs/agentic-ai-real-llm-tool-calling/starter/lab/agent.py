"""The ReAct agent loop.

This is the same Thought -> Action -> Observation cycle Chapter 34
(``projects/ch34-agentic-ai-system.html``) built with a hard-coded
``decide_next_action()`` standing in for an LLM call — rebuilt here against a
REAL LLM's native tool-calling (any ``LLMClient``, see ``llm_client.py``)
instead of parsing Thought/Action text out of a completion:

  * Thought  -> whatever ``content`` the model produces on a turn (it may be
                empty on a turn that's pure tool-calling — that's normal for
                native tool calling, unlike the chapter's text-parsed version).
  * Action   -> a ``ToolCall`` (name + arguments) the model asked for.
  * Observation -> the tool's real result, fed back as a ``role="tool"``
                message so the next turn's Thought can use it.

Guardrails, matching Chapter 34's own list:
  * ``max_steps`` — a hard cap on how many ReAct steps one run may take
    (34.5). Hitting it returns ``status="max_steps"`` and NO final answer —
    never a silently-returned partial/wrong-looking answer, per the chapter's
    explicit warning.
  * a tool allow-list — only names present in ``tool_registry`` are ever
    executed; an unknown tool name becomes an error Observation, not a crash.
  * the prompt-injection guardrail (``guardrail.py``) runs on every tool
    call's arguments before it is executed — the "pause right before the tool
    CALL" the chapter's interview notes describe for destructive actions,
    just automated (reject + explain) instead of asking a human.
"""
from __future__ import annotations

import json
from collections.abc import Callable, Iterable
from dataclasses import dataclass, field
from typing import Any

from .cost import UsageLogger
from .guardrail import check_tool_arguments
from .llm_client import LLMClient, LLMResponse, StreamEvent, ToolCall
from .memory import ConversationMemory
from .tools import TOOL_REGISTRY, TOOL_SPECS

DEFAULT_SYSTEM_PROMPT = (
    "You are a helpful assistant with tools. Use a tool when it would give a "
    "more accurate answer than guessing. When you have enough information, "
    "answer the user directly instead of calling another tool."
)


@dataclass(slots=True)
class StepLog:
    """One ReAct step, logged for the same reason Chapter 34's ``agent.trace``
    was: debugging an agent from only its final answer is nearly impossible."""

    step: int
    thought: str | None
    action: str | None  # tool name, or None if the model just answered
    action_args: dict[str, Any] | None
    observation: str | None


@dataclass(slots=True)
class AgentResult:
    final_answer: str | None
    status: str  # "answered" | "max_steps"
    steps: list[StepLog]
    usage: UsageLogger


class ReActAgent:
    def __init__(
        self,
        llm_client: LLMClient,
        tool_registry: dict[str, Callable[..., dict[str, Any]]] | None = None,
        tool_specs: list[dict[str, Any]] | None = None,
        max_steps: int = 6,
        system_prompt: str = DEFAULT_SYSTEM_PROMPT,
        memory_max_tokens: int = 4000,
    ) -> None:
        self.llm_client = llm_client
        self.tool_registry = tool_registry if tool_registry is not None else TOOL_REGISTRY
        self.tool_specs = tool_specs if tool_specs is not None else TOOL_SPECS
        self.max_steps = max_steps
        self.memory = ConversationMemory(max_tokens=memory_max_tokens)
        if system_prompt:
            self.memory.add("system", system_prompt)
        self.usage = UsageLogger()

    def run(self, user_message: str) -> AgentResult:
        """One full ReAct run for a single user message, using the
        non-streaming ``LLMClient.chat``. See ``run_streaming`` for the
        streaming path (same loop, real token-by-token output)."""
        return self._run(user_message, streaming=False, on_token=None)

    def run_streaming(
        self, user_message: str, on_token: Callable[[str], None] | None = None
    ) -> AgentResult:
        """Same ReAct loop as ``run``, but every model turn is requested via
        ``LLMClient.stream_chat`` and reassembled with
        ``assemble_stream_response``. ``on_token`` (if given) is called with
        each real content delta as it streams in — the actual "real
        streaming responses" this lab's spec asks for; a CLI would print each
        delta as it arrives instead of waiting for the full answer."""
        return self._run(user_message, streaming=True, on_token=on_token)

    def _run(
        self,
        user_message: str,
        *,
        streaming: bool,
        on_token: Callable[[str], None] | None,
    ) -> AgentResult:
        """TODO: the ReAct loop itself.

        - self.memory.add("user", user_message)
        - for step_num in range(1, self.max_steps + 1):
            - get a response for this turn:
                - if streaming: events = self.llm_client.stream_chat(self.memory.as_messages(), self.tool_specs)
                                response = assemble_stream_response(events, on_token=on_token)
                - else:         response = self.llm_client.chat(self.memory.as_messages(), self.tool_specs)
            - self.usage.log(self.llm_client.model, response.prompt_tokens, response.completion_tokens)
            - self.memory.add("assistant", response.content or "")
            - if response.tool_calls is empty: this is the final answer.
              append a StepLog(step_num, response.content, None, None, None)
              to a running `steps` list and return
              AgentResult(response.content, "answered", steps, self.usage)
            - otherwise, for EACH call in response.tool_calls:
                - observation = self._execute_tool_call(call)
                - append StepLog(step_num, response.content, call.name, call.arguments, observation)
                - self.memory.add("tool", observation, name=call.name, tool_call_id=call.id)
              (so a model that calls 2 tools in one turn produces 2 StepLogs
              for that step_num, and both observations go back into memory
              before the next model call)
        - if the loop finishes without returning (max_steps exhausted):
          return AgentResult(None, "max_steps", steps, self.usage) — NEVER a
          made-up final_answer.
        """
        raise NotImplementedError

    def _execute_tool_call(self, call: ToolCall) -> str:
        """TODO:
        - run check_tool_arguments(call.name, call.arguments); if not
          .allowed, return f"BLOCKED: {guard.reason}" WITHOUT calling the tool
        - look up call.name in self.tool_registry; if missing, return
          f"ERROR: unknown tool '{call.name}'" WITHOUT calling anything
        - otherwise call tool_fn(**call.arguments):
            - on TypeError (wrong/missing arguments), return
              f"ERROR: invalid arguments for '{call.name}': {exc}"
            - on any other Exception, return
              f"ERROR: '{call.name}' raised {exc.__class__.__name__}: {exc}"
              (a tool crashing must never crash the agent)
            - on success, return json.dumps(result) — the observation is
              always a string, since it becomes a chat message's content
        """
        raise NotImplementedError


def assemble_stream_response(
    events: Iterable[StreamEvent],
    on_token: Callable[[str], None] | None = None,
) -> LLMResponse:
    """Reassemble a stream of ``StreamEvent`` chunks into one ``LLMResponse``.

    The tricky real-world part: a streamed tool call's ARGUMENTS arrive as a
    sequence of partial JSON string fragments spread across many chunks (only
    the id/name arrive once, on the first chunk for that tool call's index —
    see ``llm_client.RealLLMClient.stream_chat``), and a model can stream more
    than one tool call in parallel, each with its own ``tool_call_index``. You
    must accumulate each index's fragments separately and ``json.loads`` only
    once, at the very end — parsing too early raises on every intermediate
    chunk, since a partial JSON string is not valid JSON.

    TODO:
    - iterate every event in `events`, in order, keeping:
        - a list of content string pieces (append event.content_delta when
          truthy; call on_token(event.content_delta) too, if on_token is not None)
        - a dict `pending: dict[int, dict]` keyed by event.tool_call_index,
          each value shaped {"id": None, "name": None, "arguments": ""} —
          use .setdefault to create it the first time an index is seen, then
          overwrite "id"/"name" when the event carries them (truthy) and
          APPEND (+=) to "arguments" when event.tool_call_arguments_delta is
          truthy (arguments arrive in fragments; id/name arrive once)
        - the latest non-None event.finish_reason (default "stop" if none ever arrives)
        - the latest non-None event.prompt_tokens / event.completion_tokens
          (default 0 if never set — a stream with no usage chunk still must
          return an LLMResponse, just with 0 tokens)
    - after the loop, build tool_calls: for each (index, slot) in `pending`,
      sorted by index, build a ToolCall(id=slot["id"] or f"call_{index}",
      name=slot["name"] or "", arguments=<slot["arguments"] parsed as JSON,
      or {"_raw": ..., "_parse_error": True} if it fails to parse, or {} if empty>)
    - return LLMResponse(content="".join(content pieces) or None, tool_calls=tuple(...),
      finish_reason=..., prompt_tokens=..., completion_tokens=...)
    """
    raise NotImplementedError
