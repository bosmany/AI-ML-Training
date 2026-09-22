"""agentic-ai-real-llm-tool-calling: a ReAct agent driven by a real
OpenAI-compatible tool-calling LLM API (Groq's free tier), with a
prompt-injection guardrail, token-trimmed multi-turn memory and a pinned
cost/usage logger — see README.md."""
from .agent import AgentResult, ReActAgent, StepLog, assemble_stream_response
from .cost import (
    PRICE_TABLE_USD_PER_MILLION_TOKENS,
    UsageLogger,
    UsageRecord,
    compute_cost,
)
from .guardrail import GuardrailResult, check_tool_arguments
from .llm_client import (
    DEFAULT_MODEL,
    GROQ_API_KEY_ENV_VAR,
    GROQ_BASE_URL,
    LLMClient,
    LLMResponse,
    RealLLMClient,
    StreamEvent,
    ToolCall,
)
from .memory import ConversationMemory, Message, approx_token_count
from .tools import TOOL_REGISTRY, TOOL_SPECS, calculator, get_current_time, search_local_docs

__all__ = [
    "AgentResult",
    "ReActAgent",
    "StepLog",
    "assemble_stream_response",
    "PRICE_TABLE_USD_PER_MILLION_TOKENS",
    "UsageLogger",
    "UsageRecord",
    "compute_cost",
    "GuardrailResult",
    "check_tool_arguments",
    "DEFAULT_MODEL",
    "GROQ_API_KEY_ENV_VAR",
    "GROQ_BASE_URL",
    "LLMClient",
    "LLMResponse",
    "RealLLMClient",
    "StreamEvent",
    "ToolCall",
    "ConversationMemory",
    "Message",
    "approx_token_count",
    "TOOL_REGISTRY",
    "TOOL_SPECS",
    "calculator",
    "get_current_time",
    "search_local_docs",
]
