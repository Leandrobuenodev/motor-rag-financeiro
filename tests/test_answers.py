import json

import httpx
import pytest

from app.infrastructure.answers import (
    AnswerConfigurationError,
    AnswerProviderError,
    GroundingPassage,
    OpenCodeGoAnswerService,
)


@pytest.mark.anyio
async def test_opencode_go_request_contains_only_internal_ids_and_text() -> None:
    captured: dict[str, object] = {}

    async def handler(request: httpx.Request) -> httpx.Response:
        captured["url"] = str(request.url)
        captured["authorization"] = request.headers["authorization"]
        captured["payload"] = json.loads(request.content)
        return httpx.Response(
            200,
            json={
                "choices": [
                    {
                        "message": {
                            "content": json.dumps(
                                {
                                    "answer": "O índice foi 14,2%.",
                                    "source_ids": [1],
                                    "insufficient_evidence": False,
                                }
                            )
                        }
                    }
                ]
            },
        )

    client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    service = OpenCodeGoAnswerService(
        api_key="test-key",
        endpoint="https://example.test/v1/chat/completions",
        model="deepseek-v4-pro",
        client=client,
    )
    result = await service.generate(
        "Qual foi o índice?",
        [GroundingPassage(source_id=1, text="O índice de Basileia foi 14,2%.")],
    )

    payload = captured["payload"]
    assert isinstance(payload, dict)
    assert payload["model"] == "deepseek-v4-pro"
    messages = payload["messages"]
    assert isinstance(messages, list)
    prompt = messages[1]["content"]
    assert 'source_id="1"' in prompt
    assert "O índice de Basileia foi 14,2%." in prompt
    assert ".pdf" not in prompt
    assert captured["authorization"] == "Bearer test-key"
    assert result.source_ids == [1]
    await client.aclose()


@pytest.mark.anyio
async def test_opencode_go_accepts_json_in_markdown_fence() -> None:
    async def handler(_: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={
                "choices": [
                    {
                        "message": {
                            "content": (
                                "```json\n"
                                '{"answer":"Grounded.","source_ids":[1],'
                                '"insufficient_evidence":false}\n```'
                            )
                        }
                    }
                ]
            },
        )

    client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    service = OpenCodeGoAnswerService(api_key="test-key", client=client)

    result = await service.generate(
        "Question", [GroundingPassage(source_id=1, text="Evidence")]
    )

    assert result.answer == "Grounded."
    await client.aclose()


@pytest.mark.anyio
async def test_opencode_go_requires_api_key_before_request() -> None:
    service = OpenCodeGoAnswerService(api_key="")

    with pytest.raises(AnswerConfigurationError, match="OPENCODE_GO_API_KEY"):
        await service.generate(
            "Question", [GroundingPassage(source_id=1, text="Evidence")]
        )
    await service.close()


@pytest.mark.anyio
async def test_opencode_go_rejects_invalid_structured_output() -> None:
    async def handler(_: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={"choices": [{"message": {"content": "not json"}}]},
        )

    client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    service = OpenCodeGoAnswerService(api_key="test-key", client=client)

    with pytest.raises(AnswerProviderError, match="required JSON"):
        await service.generate(
            "Question", [GroundingPassage(source_id=1, text="Evidence")]
        )
    await client.aclose()
