"""Tests for the trimmed conversation memory buffer."""
import pytest

from lab.memory import ConversationMemory, approx_token_count


def test_default_token_counter_matches_approx_token_count_once_a_message_is_added():
    # exercises the DEFAULT count_tokens=approx_token_count wiring (every other
    # test below passes an explicit count_tokens=len for easy arithmetic), so
    # this is the one place the ~4-chars/token approximation itself is pinned.
    mem = ConversationMemory(max_tokens=1000)
    mem.add("user", "hello world")
    assert mem.total_tokens == approx_token_count("hello world")
    assert approx_token_count("") == 0
    assert approx_token_count("x" * 40) == 10


def test_max_tokens_must_be_positive_and_a_valid_memory_still_works():
    with pytest.raises(ValueError):
        ConversationMemory(max_tokens=0)
    with pytest.raises(ValueError):
        ConversationMemory(max_tokens=-5)
    mem = ConversationMemory(max_tokens=1000)
    mem.add("user", "hi")
    assert mem.as_messages() == [{"role": "user", "content": "hi"}]


def test_empty_memory_has_no_messages():
    mem = ConversationMemory(max_tokens=1000)
    assert len(mem) == 0
    assert mem.as_messages() == []
    assert mem.total_tokens == 0


def test_as_messages_preserves_order_and_content():
    mem = ConversationMemory(max_tokens=1000)
    mem.add("system", "be helpful")
    mem.add("user", "hello")
    mem.add("assistant", "hi there")
    assert mem.as_messages() == [
        {"role": "system", "content": "be helpful"},
        {"role": "user", "content": "hello"},
        {"role": "assistant", "content": "hi there"},
    ]


def test_tool_messages_include_name_and_tool_call_id():
    mem = ConversationMemory(max_tokens=1000)
    mem.add("tool", '{"result": 4}', name="calculator", tool_call_id="call_1")
    assert mem.as_messages() == [
        {"role": "tool", "content": '{"result": 4}', "name": "calculator", "tool_call_id": "call_1"}
    ]


def test_regular_messages_omit_name_and_tool_call_id_keys():
    mem = ConversationMemory(max_tokens=1000)
    mem.add("user", "hello")
    (msg,) = mem.as_messages()
    assert "name" not in msg
    assert "tool_call_id" not in msg


def test_over_budget_drops_the_oldest_non_system_message_first():
    # count_tokens=len so budgeting is exact and easy to reason about
    mem = ConversationMemory(max_tokens=10, count_tokens=len)
    mem.add("user", "1234567890")  # exactly at budget
    mem.add("user", "22222")  # pushes over budget -> oldest ("1234567890") must go
    assert [m["content"] for m in mem.as_messages()] == ["22222"]


def test_system_message_is_never_dropped_even_when_over_budget():
    mem = ConversationMemory(max_tokens=3, count_tokens=len)
    mem.add("system", "a huge system prompt far past the budget")
    mem.add("user", "hi")  # cannot fit either, but system must survive
    contents = [m["content"] for m in mem.as_messages()]
    assert "a huge system prompt far past the budget" in contents


def test_a_single_message_that_alone_exceeds_budget_gets_dropped_once_trimmed():
    # documents a real limitation: the trimmer has no special case for "this
    # one message alone is too big" — it just keeps dropping the oldest
    # non-system message, which can end up being the only message present.
    mem = ConversationMemory(max_tokens=3, count_tokens=len)
    mem.add("user", "this single message is already far too long")
    assert mem.as_messages() == []


def test_multiple_oldest_messages_are_dropped_in_order_until_back_under_budget():
    mem = ConversationMemory(max_tokens=6, count_tokens=len)
    mem.add("user", "aa")
    mem.add("user", "bb")
    mem.add("user", "cc")
    mem.add("user", "dddddd")  # forces dropping "aa", "bb", and "cc" to fit
    assert [m["content"] for m in mem.as_messages()] == ["dddddd"]


def test_total_tokens_property_matches_the_sum_of_current_messages():
    mem = ConversationMemory(max_tokens=1000, count_tokens=len)
    mem.add("user", "abc")
    mem.add("assistant", "de")
    assert mem.total_tokens == 5
    assert len(mem) == 2
