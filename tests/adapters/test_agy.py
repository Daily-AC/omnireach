import json
from pathlib import Path
from unittest.mock import AsyncMock

from omnireach.adapters.agy import (
    AgyGroundedAdapter,
    GroundedSearchResponse,
    _agentapi_address,
    parse_grounded_content,
    read_grounded_response,
    run_grounded_search,
)


# Reduced from two real agy SEARCH_WEB steps captured on 2026-07-15.
_REAL_SEARCH_WEB_CONTENT = """Created At: 2026-07-15T16:34:41+08:00
Completed At: 2026-07-15T16:34:45+08:00
The search for "OpenAI GPT-5.6 official release July 2026" returned the following summary:
OpenAI officially released the GPT-5.6 family of models on July 9, 2026[1][2].

Sources:
[1] [wikipedia.org](https://vertexaisearch.cloud.google.com/grounding-api-redirect/first)
[2] [openai.com](https://vertexaisearch.cloud.google.com/grounding-api-redirect/second)
"""


def test_parse_grounded_content_uses_observed_search_web_shape():
    summary, sources = parse_grounded_content(_REAL_SEARCH_WEB_CONTENT)

    assert summary == (
        "OpenAI officially released the GPT-5.6 family of models on July 9, "
        "2026[1][2]."
    )
    assert sources == [
        (
            "wikipedia.org",
            "https://vertexaisearch.cloud.google.com/grounding-api-redirect/first",
        ),
        (
            "openai.com",
            "https://vertexaisearch.cloud.google.com/grounding-api-redirect/second",
        ),
    ]


def test_read_grounded_response_allows_transient_error_before_success(tmp_path: Path):
    transcript = tmp_path / "transcript_full.jsonl"
    steps = [
        {
            "step_index": 1,
            "type": "ERROR_MESSAGE",
            "status": "DONE",
            "error": "streamGenerateContent: EOF",
        },
        {
            "step_index": 2,
            "type": "SEARCH_WEB",
            "status": "DONE",
            "content": _REAL_SEARCH_WEB_CONTENT,
        },
    ]
    transcript.write_text(
        "\n".join(json.dumps(step) for step in steps) + "\n", encoding="utf-8"
    )

    response = read_grounded_response(transcript, "conversation-id")

    assert response is not None
    assert response.conversation_id == "conversation-id"
    assert len(response.sources) == 2


async def test_adapter_maps_grounded_summary_and_citations(monkeypatch):
    run = AsyncMock(
        return_value=GroundedSearchResponse(
            conversation_id="789bfb59-fd66-4d24-9394-d6f2107d4df2",
            summary="Grounded summary",
            sources=[
                ("openai.com", "https://example.com/one"),
                ("python.org", "https://example.com/two"),
            ],
        )
    )
    monkeypatch.setattr("omnireach.adapters.agy.run_grounded_search", run)

    results = await AgyGroundedAdapter().search("query", limit=2)

    assert [result.title for result in results] == ["openai.com", "python.org"]
    assert all(result.source == "agy" for result in results)
    assert all(result.adapter == "agy-grounded-search" for result in results)
    assert results[0].content == "Grounded summary"
    assert results[1].content == ""
    assert results[0].raw["conversation_id"] == (
        "789bfb59-fd66-4d24-9394-d6f2107d4df2"
    )


async def test_runner_sends_to_configured_conversation_and_polls_new_steps(
    tmp_path, monkeypatch
):
    captured: list[str] = []
    process_kwargs: dict[str, object] = {}

    class Process:
        returncode = 0

        async def communicate(self):
            return json.dumps(
                {
                    "response": {
                        "sendMessage": {
                            "recipientId": "789bfb59-fd66-4d24-9394-d6f2107d4df2"
                        }
                    }
                }
            ).encode(), b""

    async def create_process(*args, **kwargs):
        captured.extend(args)
        process_kwargs.update(kwargs)
        return Process()

    expected = GroundedSearchResponse(
        conversation_id="789bfb59-fd66-4d24-9394-d6f2107d4df2",
        summary="summary",
        sources=[("example.com", "https://example.com")],
    )
    monkeypatch.setattr("omnireach.adapters.agy._agentapi_command", lambda: ("agentapi",))
    monkeypatch.setattr(
        "omnireach.adapters.agy.configured_conversation_id",
        lambda: "789bfb59-fd66-4d24-9394-d6f2107d4df2",
    )
    monkeypatch.setattr(
        "omnireach.adapters.agy._agentapi_address", lambda: "localhost:51863"
    )
    monkeypatch.setattr(
        "omnireach.adapters.agy._transcript_path",
        lambda _: tmp_path / "transcript_full.jsonl",
    )
    monkeypatch.setattr(
        "omnireach.adapters.agy.asyncio.create_subprocess_exec", create_process
    )
    monkeypatch.setattr(
        "omnireach.adapters.agy.read_grounded_response",
        lambda *_, **__: expected,
    )

    response = await run_grounded_search("Python 3.14", timeout=1)

    assert response == expected
    assert captured[:4] == [
        "agentapi",
        "send-message",
        "--title=Omnireach grounded search",
        "789bfb59-fd66-4d24-9394-d6f2107d4df2",
    ]
    assert "built-in WebSearch tool exactly once" in captured[4]
    assert "Python 3.14" in captured[4]
    assert process_kwargs["env"]["ANTIGRAVITY_LS_ADDRESS"] == "localhost:51863"


def test_read_grounded_response_ignores_results_at_or_before_baseline(tmp_path):
    transcript = tmp_path / "transcript_full.jsonl"
    transcript.write_text(
        json.dumps(
            {
                "step_index": 27,
                "type": "SEARCH_WEB",
                "status": "DONE",
                "content": _REAL_SEARCH_WEB_CONTENT,
            }
        )
        + "\n",
        encoding="utf-8",
    )

    assert (
        read_grounded_response(
            transcript, "conversation-id", after_step_index=27
        )
        is None
    )


def test_agentapi_address_discovers_live_http_port_from_latest_log(tmp_path, monkeypatch):
    log_dir = tmp_path / "log"
    log_dir.mkdir()
    (log_dir / "cli-20260715_190146.log").write_text(
        "Language server listening on random port at 51862 for HTTPS (gRPC)\n"
        "Language server listening on random port at 51863 for HTTP\n",
        encoding="utf-8",
    )
    monkeypatch.delenv("ANTIGRAVITY_LS_ADDRESS", raising=False)
    monkeypatch.setattr("omnireach.adapters.agy._agy_home", lambda: tmp_path)
    monkeypatch.setattr("omnireach.adapters.agy._port_is_open", lambda port: port == 51863)

    assert _agentapi_address() == "localhost:51863"
