import pytest
import httpx
import respx
from ling.config import TranslatorConfig
from ling.translator import TranslatorClient

OPENAI_CONFIG = TranslatorConfig(
    provider="openai",
    api_key="sk-test",
    model="gpt-4o",
    base_url="https://api.openai.com",
    request_timeout=10,
    fallback_on_timeout=True,
)

ANTHROPIC_CONFIG = TranslatorConfig(
    provider="anthropic",
    api_key="sk-ant-test",
    model="claude-opus-4-6",
    base_url="https://api.anthropic.com",
    request_timeout=10,
    fallback_on_timeout=True,
)

OPENAI_RESPONSE = {
    "choices": [{"message": {"content": "你好世界"}}]
}

ANTHROPIC_RESPONSE = {
    "content": [{"type": "text", "text": "你好世界"}]
}

@respx.mock
async def test_translate_openai_format():
    respx.post("https://api.openai.com/v1/chat/completions").mock(
        return_value=httpx.Response(200, json=OPENAI_RESPONSE)
    )
    client = TranslatorClient(OPENAI_CONFIG)
    result = await client.translate("Hello world", target_lang="zh")
    assert result == "你好世界"
    await client.close()

@respx.mock
async def test_translate_anthropic_format():
    respx.post("https://api.anthropic.com/v1/messages").mock(
        return_value=httpx.Response(200, json=ANTHROPIC_RESPONSE)
    )
    client = TranslatorClient(ANTHROPIC_CONFIG)
    result = await client.translate("Hello world", target_lang="zh")
    assert result == "你好世界"
    await client.close()

@respx.mock
async def test_openai_sends_correct_headers():
    route = respx.post("https://api.openai.com/v1/chat/completions").mock(
        return_value=httpx.Response(200, json=OPENAI_RESPONSE)
    )
    client = TranslatorClient(OPENAI_CONFIG)
    await client.translate("test", target_lang="zh")
    assert route.called
    request = route.calls[0].request
    assert request.headers["authorization"] == "Bearer sk-test"
    await client.close()

@respx.mock
async def test_anthropic_sends_correct_headers():
    route = respx.post("https://api.anthropic.com/v1/messages").mock(
        return_value=httpx.Response(200, json=ANTHROPIC_RESPONSE)
    )
    client = TranslatorClient(ANTHROPIC_CONFIG)
    await client.translate("test", target_lang="zh")
    assert route.called
    request = route.calls[0].request
    assert request.headers["x-api-key"] == "sk-ant-test"
    await client.close()

@respx.mock
async def test_fallback_on_timeout_returns_original():
    respx.post("https://api.openai.com/v1/chat/completions").mock(
        side_effect=httpx.TimeoutException("timeout")
    )
    client = TranslatorClient(OPENAI_CONFIG)
    result = await client.translate("Hello world", target_lang="zh")
    assert result == "Hello world"  # fallback to original
    await client.close()

@respx.mock
async def test_custom_base_url():
    config = TranslatorConfig(
        provider="openai",
        api_key="sk-test",
        model="gpt-4o",
        base_url="https://custom.proxy.com",
        request_timeout=10,
    )
    route = respx.post("https://custom.proxy.com/v1/chat/completions").mock(
        return_value=httpx.Response(200, json=OPENAI_RESPONSE)
    )
    client = TranslatorClient(config)
    await client.translate("test", target_lang="zh")
    assert route.called
    await client.close()
