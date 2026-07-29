from __future__ import annotations

from types import SimpleNamespace

from noname.config import Settings
from noname.llm import GeneratedReply, LLMClient, _extract_json


class CompatibilityError(Exception):
    status_code = 400


class FakeCompletions:
    def __init__(self) -> None:
        self.calls: list[dict] = []

    async def create(self, **kwargs):  # noqa: ANN003, ANN201
        self.calls.append(kwargs)
        if "response_format" in kwargs:
            raise CompatibilityError("unsupported parameter: response_format")
        return SimpleNamespace(
            choices=[
                SimpleNamespace(
                    message=SimpleNamespace(content='```json\n{"ok": true}\n```')
                )
            ]
        )


class FakeClient:
    def __init__(self) -> None:
        self.chat = SimpleNamespace(completions=FakeCompletions())


def test_generated_reply_normalizes_and_deduplicates_quick_replies() -> None:
    reply = GeneratedReply(
        reply="  听起来   你很在意这件事。  ",
        quick_replies=[" 少困一点。 ", "少困一点", " 先继续聊聊 ", ""],
    )

    assert reply.reply == "听起来 你很在意这件事。"
    assert reply.quick_replies == ["少困一点", "先继续聊聊"]


def test_extract_json_accepts_fenced_provider_output() -> None:
    assert _extract_json('```json\n{"reply": "听起来"}\n```') == {"reply": "听起来"}


async def test_provider_check_falls_back_when_json_mode_is_unsupported() -> None:
    settings = Settings(
        _env_file=None,
        LLM_API_KEY="test-key",
        LLM_BASE_URL="https://provider.example/v1",
        LLM_MODEL="test-model",
    )
    client = LLMClient(settings)
    fake_client = FakeClient()
    client.client = fake_client  # type: ignore[assignment]

    result = await client.check_connection()

    assert result.ok is True
    assert result.endpoint_host == "provider.example"
    assert result.completion_mode == "prompt-json"
    assert len(fake_client.chat.completions.calls) == 2
    assert "response_format" in fake_client.chat.completions.calls[0]
    assert "response_format" not in fake_client.chat.completions.calls[1]


async def test_provider_check_is_disabled_without_api_key() -> None:
    settings = Settings(_env_file=None, LLM_API_KEY="")
    result = await LLMClient(settings).check_connection()

    assert result.ok is False
    assert result.completion_mode == "disabled"
    assert "API Key" in (result.error or "")
