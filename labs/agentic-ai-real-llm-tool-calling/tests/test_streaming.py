"""Tests for reassembling a stream of StreamEvent chunks into one LLMResponse
— the same assembly logic used for a real Groq stream (see
lab.llm_client.RealLLMClient.stream_chat) and for FakeLLMClient's scripted
streams, so it is worth testing thoroughly on its own, independent of the
agent loop."""
from lab.agent import assemble_stream_response
from lab.llm_client import StreamEvent


def test_empty_stream_yields_a_default_response():
    response = assemble_stream_response(iter([]))
    assert response.content is None
    assert response.tool_calls == ()
    assert response.finish_reason == "stop"
    assert response.prompt_tokens == 0
    assert response.completion_tokens == 0


def test_pure_text_content_is_reassembled_in_order():
    events = [
        StreamEvent(content_delta="Hel"),
        StreamEvent(content_delta="lo, "),
        StreamEvent(content_delta="world!"),
        StreamEvent(finish_reason="stop"),
    ]
    response = assemble_stream_response(iter(events))
    assert response.content == "Hello, world!"
    assert response.tool_calls == ()


def test_on_token_callback_fires_once_per_content_delta_in_order():
    events = [StreamEvent(content_delta="a"), StreamEvent(content_delta="b"), StreamEvent(content_delta="c")]
    seen = []
    assemble_stream_response(iter(events), on_token=seen.append)
    assert seen == ["a", "b", "c"]


def test_on_token_is_not_called_for_chunks_with_no_content_delta():
    events = [StreamEvent(tool_call_index=0, tool_call_name="calculator", tool_call_arguments_delta="{}")]
    seen = []
    assemble_stream_response(iter(events), on_token=seen.append)
    assert seen == []


def test_tool_call_arguments_split_across_many_chunks_reassemble_correctly():
    events = [
        StreamEvent(tool_call_index=0, tool_call_id="call_1", tool_call_name="calculator"),
        StreamEvent(tool_call_index=0, tool_call_arguments_delta='{"expr'),
        StreamEvent(tool_call_index=0, tool_call_arguments_delta='ession"'),
        StreamEvent(tool_call_index=0, tool_call_arguments_delta=': "2+2"}'),
        StreamEvent(finish_reason="tool_calls"),
    ]
    response = assemble_stream_response(iter(events))
    assert len(response.tool_calls) == 1
    call = response.tool_calls[0]
    assert call.id == "call_1"
    assert call.name == "calculator"
    assert call.arguments == {"expression": "2+2"}
    assert response.finish_reason == "tool_calls"


def test_two_parallel_tool_calls_are_reassembled_independently_and_sorted_by_index():
    events = [
        StreamEvent(tool_call_index=1, tool_call_id="call_b", tool_call_name="get_current_time"),
        StreamEvent(tool_call_index=0, tool_call_id="call_a", tool_call_name="calculator"),
        StreamEvent(tool_call_index=1, tool_call_arguments_delta='{"timezone_name": "UTC"}'),
        StreamEvent(tool_call_index=0, tool_call_arguments_delta='{"expression": "1+1"}'),
    ]
    response = assemble_stream_response(iter(events))
    assert [c.name for c in response.tool_calls] == ["calculator", "get_current_time"]
    assert response.tool_calls[0].arguments == {"expression": "1+1"}
    assert response.tool_calls[1].arguments == {"timezone_name": "UTC"}


def test_malformed_tool_call_json_does_not_raise():
    events = [
        StreamEvent(tool_call_index=0, tool_call_id="call_1", tool_call_name="calculator"),
        StreamEvent(tool_call_index=0, tool_call_arguments_delta="{not valid json"),
    ]
    response = assemble_stream_response(iter(events))
    call = response.tool_calls[0]
    assert call.arguments["_parse_error"] is True
    assert "not valid json" in call.arguments["_raw"]


def test_tool_call_with_no_arguments_at_all_gets_an_empty_dict():
    events = [StreamEvent(tool_call_index=0, tool_call_id="call_1", tool_call_name="get_current_time")]
    response = assemble_stream_response(iter(events))
    assert response.tool_calls[0].arguments == {}


def test_final_usage_only_chunk_sets_prompt_and_completion_tokens():
    events = [
        StreamEvent(content_delta="hi"),
        StreamEvent(prompt_tokens=42, completion_tokens=7),
    ]
    response = assemble_stream_response(iter(events))
    assert response.prompt_tokens == 42
    assert response.completion_tokens == 7


def test_missing_tool_call_id_falls_back_to_a_synthetic_call_id():
    events = [StreamEvent(tool_call_index=3, tool_call_name="calculator", tool_call_arguments_delta="{}")]
    response = assemble_stream_response(iter(events))
    assert response.tool_calls[0].id == "call_3"
