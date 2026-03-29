from __future__ import annotations
import re
import httpx
from .config import TranslatorConfig

_EN_PROMPT = (
    "You are a translation engine. Translate the text between <text> and </text> from Chinese to English.\n"
    "Rules: keep file paths, variable names, commands unchanged. Output only the translation.\n\n"
    "Example:\n"
    "<text>帮我列出当前目录的文件</text>\n"
    "List the files in the current directory\n\n"
    "Now translate:\n"
)
_ZH_PROMPT = (
    "You are a translation engine. Translate the text between <text> and </text> from English to Chinese.\n"
    "Rules: keep file paths, variable names, commands, code identifiers unchanged. Output only the translation.\n\n"
    "Example:\n"
    "<text>Reading file src/main.py...</text>\n"
    "正在读取文件 src/main.py...\n\n"
    "Now translate:\n"
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
        from .log import log
        import time
        t0 = time.monotonic()
        try:
            if self._config.provider == "openai":
                result = await self._call_openai(text, target_lang)
            else:
                result = await self._call_anthropic(text, target_lang)
            # Strip any <text>...</text> wrapper the model may have echoed back
            result = re.sub(r'^<text>(.*)</text>$', r'\1', result.strip(), flags=re.DOTALL)
            log.debug(f"[translator] {target_lang} 耗时{time.monotonic()-t0:.1f}s 原文={repr(text[:60])} 译文={repr(result[:60])}")
            return result
        except httpx.TimeoutException:
            log.warning(f"[translator] 超时({time.monotonic()-t0:.1f}s), fallback原文")
            if self._config.fallback_on_timeout:
                return text
            raise

    def _wrap(self, text: str) -> str:
        return f"<text>{text}</text>"

    async def _call_openai(self, text: str, target_lang: str) -> str:
        base = (self._config.base_url or "https://api.openai.com").rstrip("/")
        if base.endswith("/v1"):
            base = base[:-3]
        system = _ZH_PROMPT if target_lang == "zh" else _EN_PROMPT
        resp = await self._client.post(
            f"{base}/v1/chat/completions",
            headers={"Authorization": f"Bearer {self._config.api_key}"},
            json={
                "model": self._config.model,
                "messages": [
                    {"role": "system", "content": system},
                    {"role": "user", "content": self._wrap(text)},
                ],
            },
        )
        resp.raise_for_status()
        return resp.json()["choices"][0]["message"]["content"]

    async def _call_anthropic(self, text: str, target_lang: str) -> str:
        base = (self._config.base_url or "https://api.anthropic.com").rstrip("/")
        if base.endswith("/v1"):
            base = base[:-3]
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
                "messages": [{"role": "user", "content": self._wrap(text)}],
            },
        )
        resp.raise_for_status()
        return resp.json()["content"][0]["text"]

    async def close(self):
        await self._client.aclose()
