"""Multi-turn conversation memory, trimmed by (approximate) token count so a
long-running agent conversation never silently exceeds the model's context
window.

A real production system would trim by the provider's EXACT tokenizer (e.g.
``tiktoken`` for OpenAI-family models). Groq/Llama models don't ship a
pip-installable exact tokenizer, so ``approx_token_count`` below uses a
documented approximation (~4 characters per token — the same rule of thumb
OpenAI's own docs give for English text): good enough to decide when to trim,
not good enough to bill a customer to the cent (billing uses the real
``prompt_tokens``/``completion_tokens`` the API returns, see ``cost.py``).
"""
from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass


def approx_token_count(text: str) -> int:
    """~4 chars/token approximation. Never returns 0 for non-empty text, so a
    single-character message still "costs" something in the trim budget."""
    if not text:
        return 0
    return max(1, (len(text) + 3) // 4)


@dataclass(slots=True)
class Message:
    role: str  # "system" | "user" | "assistant" | "tool"
    content: str
    name: str | None = None  # tool name, only set for role="tool"
    tool_call_id: str | None = None  # links a "tool" message back to its call


class ConversationMemory:
    """A trimmed rolling buffer of ``Message``s.

    Trim policy: while the buffer's total (approximate) token count exceeds
    ``max_tokens``, drop the OLDEST non-system message. System messages (the
    agent's own instructions) are never dropped — a memory buffer that forgets
    its own instructions to save room for chat history is worse than one that
    forgets old chat history, which is the same policy every production chat
    memory implementation uses.
    """

    def __init__(
        self,
        max_tokens: int,
        count_tokens: Callable[[str], int] = approx_token_count,
    ) -> None:
        if max_tokens <= 0:
            raise ValueError("max_tokens must be positive")
        self.max_tokens = max_tokens
        self._count_tokens = count_tokens
        self._messages: list[Message] = []

    def add(
        self,
        role: str,
        content: str,
        *,
        name: str | None = None,
        tool_call_id: str | None = None,
    ) -> None:
        """TODO: append a new Message(role, content, name, tool_call_id) to
        self._messages, then call self._trim() so the buffer never grows past
        max_tokens after an add."""
        raise NotImplementedError

    def _trim(self) -> None:
        """TODO: while self._total_tokens() > self.max_tokens, find the index
        of the OLDEST message whose role != "system" and delete it. If no
        such message exists (only system messages remain) stop trimming
        instead of deleting a system message — even if still over budget."""
        raise NotImplementedError

    def _total_tokens(self) -> int:
        return sum(self._count_tokens(m.content) for m in self._messages)

    def as_messages(self) -> list[dict[str, str]]:
        """TODO: return the provider wire format: a list of
        {"role": ..., "content": ...} dicts in order, ready to pass as
        ``messages=`` to an ``LLMClient``. Include "name" in the dict only
        when a message's .name is not None, and "tool_call_id" only when a
        message's .tool_call_id is not None (most messages have neither)."""
        raise NotImplementedError

    def __len__(self) -> int:
        return len(self._messages)

    @property
    def total_tokens(self) -> int:
        return self._total_tokens()
