from __future__ import annotations
import httpx
from .config import TranslatorConfig

_EN_PROMPT = (
    "You are a bilingual AI assistant helping a Chinese-speaking engineer use Claude Code. "
    "Rewrite the user's Chinese message as a precise, well-structured English instruction for Claude Code. "
    "Rules:\n"
    "- Keep all technical terms, file paths, variable names, and commands in English\n"
    "- Preserve the user's intent exactly, but use natural engineering English\n"
    "- If the input is already in English or is a mix, keep the technical parts unchanged\n"
    "- Output only the rewritten instruction, nothing else."
)
_ZH_PROMPT = (
    "You are translating Claude Code's English output to Chinese for a Chinese-speaking engineer. "
    "Rules:\n"
    "- Translate explanatory text, step descriptions, and status messages naturally to Chinese\n"
    "- Keep all file paths, command names, variable names, function names, and code identifiers in English\n"
    "- Preserve markdown structure (headings, bullet points, bold, italics) exactly\n"
    "- For tool status lines like 'Reading file...', 'Running command...', use natural Chinese equivalents\n"
    "- Do not translate content inside backtick inline code or code blocks\n"
    "- Output only the translation, nothing else."
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
                    {"role": "user", "content": text},
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
                "messages": [{"role": "user", "content": text}],
            },
        )
        resp.raise_for_status()
        return resp.json()["content"][0]["text"]

    async def close(self):
        await self._client.aclose()
