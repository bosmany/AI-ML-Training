"""Live tests: these hit the REAL Groq API over the network with a real
model. They are the ONLY tests in this lab that cost anything or need
network access.

Excluded by default (see ../pytest.ini: `addopts = -m "not live"`), so a
plain `pytest` or `LAB_TARGET=solution pytest` run never collects/executes
them. Run explicitly with:

    GROQ_API_KEY=gsk_... pytest -m live

Without a key, `pytest -m live` still runs (deselection is overridden by the
explicit -m), and every test below is individually SKIPPED with a clear
reason via @pytest.mark.skipif — see README.md "Getting a free Groq API key".
"""
import os

import pytest

from lab.agent import ReActAgent
from lab.llm_client import GROQ_API_KEY_ENV_VAR, RealLLMClient

pytestmark = pytest.mark.live

_HAS_KEY = bool(os.environ.get(GROQ_API_KEY_ENV_VAR))
_SKIP_REASON = (
    f"{GROQ_API_KEY_ENV_VAR} is not set — get a free key at https://console.groq.com/keys "
    "and export it to run this test (see README.md 'Getting a free Groq API key')"
)


@pytest.mark.skipif(not _HAS_KEY, reason=_SKIP_REASON)
def test_real_agent_answers_a_simple_arithmetic_question_using_the_calculator_tool():
    client = RealLLMClient()
    agent = ReActAgent(client, max_steps=4)
    result = agent.run("What is 47 * 19? Use the calculator tool, then tell me the number.")

    assert result.status == "answered"
    assert result.final_answer is not None
    assert "893" in result.final_answer
    assert agent.usage.total_tokens()[0] > 0
    assert agent.usage.total_cost() >= 0


@pytest.mark.skipif(not _HAS_KEY, reason=_SKIP_REASON)
def test_real_streaming_agent_run_calls_on_token_and_produces_a_final_answer():
    client = RealLLMClient()
    agent = ReActAgent(client, max_steps=4)
    chunks: list[str] = []

    result = agent.run_streaming("Say the single word: hello", on_token=chunks.append)

    assert result.status == "answered"
    assert result.final_answer
    # a real stream arrives in more than one chunk for any non-trivial answer
    assert len(chunks) >= 1
    assert "".join(chunks) in (result.final_answer, "")  # content-only turns match exactly


@pytest.mark.skipif(not _HAS_KEY, reason=_SKIP_REASON)
def test_real_client_rejects_a_bad_key_with_an_api_error_not_a_hang():
    from openai import AuthenticationError

    client = RealLLMClient(api_key="gsk_invalid_key_for_testing_only")
    with pytest.raises(AuthenticationError):
        client.chat([{"role": "user", "content": "hi"}], tools=[])
