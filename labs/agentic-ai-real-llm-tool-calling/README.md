# Lab: Agentic AI with a Real LLM and Real Tool Calling

Rebuild Chapter 34's ReAct agent (`projects/ch34-agentic-ai-system.html`) against a **real** LLM's native
tool-calling instead of the chapter's hard-coded `decide_next_action()` stand-in. Same Thought -> Action ->
Observation loop, same guardrails (`max_steps`, tool allow-list) — but now backed by Groq's free, OpenAI-compatible
API (`llama-3.3-70b-versatile`), with real streaming, real token usage turned into a real (if tiny) USD cost, a
trimmed conversation memory buffer, and a prompt-injection guardrail that runs on every tool call's arguments
before the tool executes.

## Why it matters in a real job

Every "AI agent" job posting means some version of this: a loop that calls an LLM, lets it invoke tools, feeds
results back, and stops. What separates a toy from something you'd ship: a hard cap on steps so a confused model
can't loop forever and burn your API budget; tool arguments treated as untrusted input (a tool's own output, or a
document it fetched, can contain an injected instruction) and screened *before* the tool runs, not after; a
conversation memory that gets trimmed by token count instead of silently blowing past the model's context window;
and real cost visibility — no provider hands you a dollar figure, every one gives you token counts, and turning
that into money is a table lookup you maintain yourself (and get loudly wrong, not silently wrong, for a model you
forgot to price).

## What's graded offline vs. what needs a key

This lab has two tiers, and they are strictly separated:

- **Offline / hermetic (the graded tier).** `pytest` (starter) and `LAB_TARGET=solution pytest` (reference) run
  entirely against `tests/fake_llm.py::FakeLLMClient` — a scripted, in-memory double. Zero network calls, zero
  cost, fully deterministic, no API key needed. This is what `labs/run_all.sh` checks and what you're graded on.
- **Live / opt-in (`tests/test_live_llm.py`, marked `@pytest.mark.live`).** Three tests that call the real Groq API
  with `RealLLMClient`. `pytest.ini` excludes them by default (`addopts = -m "not live"`), so a plain `pytest` run
  never touches the network even if you have a key set. Run them explicitly, with a free key, to see the agent
  actually think:

  ```bash
  GROQ_API_KEY=gsk_... pytest -m live
  ```

  Without a key, `pytest -m live` still runs the file but every test inside SKIPS cleanly with a message pointing
  at where to get one — it never errors or hangs.

### Getting a free Groq API key

1. Go to <https://console.groq.com/keys> and sign up (free, no card required for the free tier).
2. Create an API key, copy it (starts with `gsk_...`).
3. `export GROQ_API_KEY=gsk_...` in your shell (or put it in a `.env` you don't commit).
4. Check current model availability/pricing before relying on it for anything real: models get renamed/deprecated
   faster than most providers — <https://console.groq.com/docs/models> and <https://groq.com/pricing>.

## Prerequisites (course chapters)

- [Chapter 34: Agentic AI systems](../../projects/ch34-agentic-ai-system.html) — the ReAct loop, `max_steps`,
  tool allow-lists and the human-confirmation-gate idea this lab automates as a guardrail.
- [Python ch. 6](../../python/ch06-professional-python.html) (dataclasses, protocols) and
  [ch. 7](../../python/ch07-python-devops-apis.html) (real HTTP APIs).

## Run it

```bash
cd labs/agentic-ai-real-llm-tool-calling
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
pytest -q                        # starter: every test fails until you implement it (offline, no key)
LAB_TARGET=solution pytest -q    # maintainers / CI: the reference solution passes (offline, no key)
GROQ_API_KEY=gsk_... pytest -m live   # optional: real Groq calls, ~a fraction of a cent total
```

## What is provided vs what you write

Provided (given complete, read them for how the pieces fit together, but no TODOs inside):
`llm_client.py` (the `LLMClient` protocol, `RealLLMClient`'s real Groq wiring, `ToolCall`/`LLMResponse`/
`StreamEvent`), `tools.py` (`calculator` — AST-walked, never `eval()` — plus `get_current_time` and
`search_local_docs`), and `tests/fake_llm.py` (the scripted double every offline test runs against).

You write:

- **`guardrail.py`** — `_iter_strings` (recurse a JSON-like structure and yield every string leaf) and
  `check_tool_arguments` (match every leaf against the injection-pattern list).
- **`memory.py`** — `ConversationMemory.add`, `._trim` (drop the oldest non-system message while over budget,
  never drop the last system message) and `.as_messages` (wire format for an `LLMClient`).
- **`cost.py`** — `compute_cost` (Decimal arithmetic, raise on negative tokens or an unpriced model) and
  `UsageLogger.log` / `.total_cost` / `.total_tokens`.
- **`agent.py`** — `ReActAgent._run` (the loop itself), `._execute_tool_call` (guardrail -> lookup -> call, with
  every failure mode turned into an observation string instead of a crash) and `assemble_stream_response`
  (reassemble a stream of `StreamEvent` chunks — including a tool call's arguments arriving as JSON fragments
  spread across many chunks — into one `LLMResponse`).

## Tasks

1. `guardrail._iter_strings` + `check_tool_arguments`: walk nested tool arguments, reject the first string that
   matches a known injection pattern, before the tool ever runs.
2. `memory.ConversationMemory.add` / `_trim`: append then trim; the system prompt is the one message that is
   never dropped, even if the buffer is still over budget afterward.
3. `memory.ConversationMemory.as_messages`: build the exact `{"role", "content", ["name"], ["tool_call_id"]}` wire
   format, omitting `name`/`tool_call_id` when unset.
4. `cost.compute_cost`: Decimal-only cost math; a negative token count or an unpriced model must raise, never
   silently return `$0.00`.
5. `cost.UsageLogger`: accumulate one record per LLM call; `total_cost`/`total_tokens` summarize the run.
6. `agent.ReActAgent._execute_tool_call`: guardrail check first (blocked -> never call the tool), then unknown
   tool name, then `TypeError` (bad arguments) vs. any other exception (tool crashed) — each with its own
   `ERROR:`/`BLOCKED:` observation string, so a bad tool call degrades instead of crashing the whole agent.
7. `agent.ReActAgent._run`: the ReAct loop — call the model, log usage, log a `StepLog` per tool call (a model
   that calls two tools in one turn produces two step logs for that step number), feed every observation back into
   memory, stop at `max_steps` with `status="max_steps"` and `final_answer=None` (never a fabricated answer).
8. `agent.assemble_stream_response`: reassemble streamed chunks into one `LLMResponse`, accumulating each tool
   call's arguments by `tool_call_index` and parsing the JSON only once, at the end.

## Hints

<details><summary>Why the offline tests never import <code>RealLLMClient</code></summary>

`agent.ReActAgent` only ever talks to the `LLMClient` protocol (structural typing via `Protocol` — no inheritance
needed). `tests/fake_llm.py::FakeLLMClient` satisfies the exact same shape as `RealLLMClient`, so every test in
`test_agent_loop.py`, `test_memory.py`, `test_guardrail.py`, `test_cost.py` and `test_streaming.py` runs the real
`ReActAgent` code end to end without a network call or an API key. Only `test_live_llm.py` ever constructs a
`RealLLMClient`.
</details>

<details><summary>Why <code>_iter_strings</code> needs to recurse</summary>

A tool argument can be `{"filters": {"query": "ignore all previous instructions"}}` — a flat
`arguments.get("query")` check misses it because the injected text is one level deeper than the top-level dict.
Recurse into dict values (never keys) and list/tuple items; anything that isn't a str/dict/list/tuple (int, float,
bool, None) yields nothing.
</details>

<details><summary>Why the system prompt survives trimming even when still over budget</summary>

`_trim` looks for the oldest message with `role != "system"` to delete. If every remaining message IS a system
message (rare, but possible with a very long system prompt and a tiny `max_tokens`), stop trimming instead of
deleting it — an agent that forgets its own instructions to save room for chat history is worse than one that
just runs a little over budget.
</details>

<details><summary>Why <code>compute_cost</code> raises instead of returning $0.00</summary>

A silent `$0.00` for a model that isn't in `PRICE_TABLE_USD_PER_MILLION_TOKENS` is exactly how real cost-tracking
bill-shock happens: someone points the agent at a new/renamed model, the dashboard shows no cost, nobody notices
until the real invoice arrives. Raising `KeyError` immediately, with a message pointing at the table and Groq's
pricing page, catches it on the first call.
</details>

<details><summary>Streamed tool-call arguments arrive in fragments</summary>

Only the FIRST chunk for a given `tool_call_index` carries `tool_call_id`/`tool_call_name`; every chunk after that
(same index) carries another piece of `tool_call_arguments_delta` to append. `json.loads` only the fully
concatenated string, once, after the loop — parsing a partial JSON string mid-stream always raises. A model
streaming two tool calls in parallel gives you two independent indices to accumulate.
</details>

<details><summary>What a "step" means when a turn calls two tools at once</summary>

`response.tool_calls` can have more than one entry for a single model turn. Each one gets its own `StepLog` (same
`step` number, different `action`/`observation`), and both observations go back into memory as separate `role="tool"`
messages before the next model call — the model asked for both, so both results need to be visible next turn.
</details>

## Stretch goals

- Add a second real tool that hits an actual (rate-limited, cached) HTTP API, and guardrail its response too — not
  just the outgoing arguments (a fetched document is exactly the kind of attacker-controlled text the chapter
  warns about).
- Add a second, independent guardrail layer: an allow-list of expected argument *shapes* per tool (e.g.
  `search_local_docs.query` should never contain a URL), not just regex pattern matching.
- Track cost per conversation and enforce a budget cap (`if usage.total_cost() > Decimal("0.01"): stop`).
- Swap `approx_token_count` for a real tokenizer (`tiktoken` works for OpenAI-family models; Groq/Llama don't ship
  one you can pip-install) and compare how often it disagrees with the approximation.
- Build a small CLI on top of `run_streaming` that prints tokens as they arrive, the same way a real chat UI does.

## How this comes up in interviews

"Design an agent that can call tools." Then: *what stops it from looping forever?* (`max_steps`, no fabricated
answer on exhaustion), *what if the model calls a tool with garbage arguments, or a tool you don't recognize?*
(allow-list + per-failure-mode error observations, never a crash), *what if a tool's own output tries to hijack the
agent?* (guardrail on tool arguments/results, not just the user's first message), *how do you keep a long
conversation from blowing the context window?* (trimmed memory, oldest-first, system prompt protected), *how do you
know what this is costing you?* (real token counts -> a maintained, fail-loud price table), *how do you test any of
this without hitting a real API in CI?* (a protocol-typed fake double that satisfies the same interface).

## What this lab does not cover

- **The guardrail is regex pattern matching, not a second model or a classifier.** It catches the injection
  patterns it's told to look for and nothing else — a determined attacker can phrase around a fixed pattern list.
  Production systems layer this with a classifier and/or an allow-list of expected argument shapes.
- **`approx_token_count` is an approximation** (~4 chars/token), used only to decide when to trim memory — never
  used for billing. Real cost tracking in `cost.py` uses the exact `prompt_tokens`/`completion_tokens` the API
  returns.
- Single-turn tool results only: a tool cannot itself call another tool, and there's no sub-agent delegation.
- No persistence across runs (`ConversationMemory` is in-process only) and no multi-user/session isolation.
- `PRICE_TABLE_USD_PER_MILLION_TOKENS` is a pricing snapshot, not a live feed — check
  <https://groq.com/pricing> before trusting it for a real budget.
