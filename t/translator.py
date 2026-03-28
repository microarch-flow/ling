from __future__ import annotations
import httpx
from .config import TranslatorConfig

_ZH_PROMPT = (
    "You are a professional technical translator. "
    "Translate the following English text to Chinese. "
    "Preserve all technical terms, command names, and formatting exactly. "
    "Output only the translation, nothing else."
)
_EN_PROMPT = (
    "You are a professional technical translator. "
    "Translate the following Chinese text to English. "
    "Preserve all technical terms, command names, and formatting exactly. "
    "Output only the translation, nothing else."
)

class TranslatorClient:
    def __init__(self, config: TranslatorConfig):
        self._config = config
        self._client = httpx.AsyncClient(timeout=config.request_timeout)

    async def translate(self, text: str, target_lang: str = "zh") -> str:
        """
        Translate text. target_lang: 'zh' (→Chinese) or 'en' (→English).
        Returns original text on timeout if fallback_on_timeout is True.
        """
        try:
            if self._config.provider == "openai":
                return await self._call_openai(text, target_lang)
            else:
                return await self._call_anthropic(text, target_lang)
        except httpx.TimeoutException:
            if self._config.fallback_on_timeout:
                return text
            raise

    async def _call_openai(self, text: str, target_lang: str) -> str:
        base = (self._config.base_url or "https://api.openai.com").rstrip("/")
        system = _ZH_PROMPT if target_lang == "zh" else _EN_PROMPT
        resp = await self._client.post(
            f"{base}/v1/chat/completions",
            headers={"Authorization": f"Bearer {self._config.api_key}"},
            json={
                "model": self._config.model,
                "messages": [
                    {"role": "system", "content": system},
                    {"role": "user", "content": text},
                ],
            },
        )
        resp.raise_for_status()
        return resp.json()["choices"][0]["message"]["content"]

    async def _call_anthropic(self, text: str, target_lang: str) -> str:
        base = (self._config.base_url or "https://api.anthropic.com").rstrip("/")
        system = _ZH_PROMPT if target_lang == "zh" else _EN_PROMPT
        resp = await self._client.post(
            f"{base}/v1/messages",
            headers={
                "x-api-key": self._config.api_key,
                "anthropic-version": "2023-06-01",
            },
            json={
                "model": self._config.model,
                "max_tokens": 4096,
                "system": system,
                "messages": [{"role": "user", "content": text}],
            },
        )
        resp.raise_for_status()
        return resp.json()["content"][0]["text"]

    async def close(self):
        await self._client.aclose()
