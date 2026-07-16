"""Thin async clients for the Gemini and Groq chat-completion REST APIs.

No provider SDKs: both APIs are one POST away, and httpx keeps the
dependency surface small. Gemini is preferred when both keys are set.
"""

from __future__ import annotations
import asyncio

from dataclasses import dataclass
from typing import Any

import httpx
import structlog

from app.core.config import Settings
from app.core.errors import ServiceUnavailableError

logger = structlog.get_logger(__name__)

async def _post_with_retry(
    client: httpx.AsyncClient,
    url: str,
    *,
    params: dict[str, Any] | None = None,
    headers: dict[str, str] | None = None,
    json: dict[str, Any] | None = None,
    retries: int = 2,
    initial_delay: float = 0.5,
    backoff_factor: float = 2.0,
) -> httpx.Response:
    delay = initial_delay
    for attempt in range(retries + 1):
        try:
            response = await client.post(url, params=params, headers=headers, json=json)
            if response.status_code >= 500:
                response.raise_for_status()
            return response
        except (httpx.HTTPError, httpx.TimeoutException) as exc:
            if attempt == retries:
                raise
            logger.warning("llm_http_call_failed_retrying", attempt=attempt, error=str(exc))
            await asyncio.sleep(delay)
            delay *= backoff_factor
    raise httpx.HTTPError("Max retries exceeded")

GEMINI_ENDPOINT = "https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"
GROQ_ENDPOINT = "https://api.groq.com/openai/v1/chat/completions"


@dataclass(frozen=True)
class LLMResult:
    text: str
    provider: str
    model: str


class LLMClient:
    """Provider-agnostic completion call: Gemini first, Groq as fallback."""

    def __init__(self, settings: Settings) -> None:
        self.settings = settings

    @property
    def is_configured(self) -> bool:
        return bool(self.settings.gemini_api_key or self.settings.groq_api_key)

    async def complete(
        self,
        *,
        system_prompt: str,
        messages: list[dict[str, str]],
        temperature: float = 0.4,
        max_tokens: int = 1024,
        json_mode: bool = False,
    ) -> LLMResult:
        """Run a chat completion over ``{"role": "user"|"assistant", "content": str}`` turns."""
        if not self.is_configured:
            raise ServiceUnavailableError(
                "No LLM provider configured. Set FIOS_GEMINI_API_KEY or FIOS_GROQ_API_KEY."
            )

        errors: list[str] = []
        if self.settings.gemini_api_key:
            try:
                return await self._gemini(
                    system_prompt=system_prompt,
                    messages=messages,
                    temperature=temperature,
                    max_tokens=max_tokens,
                    json_mode=json_mode,
                )
            except Exception as exc:
                logger.warning("gemini_call_failed", error=str(exc))
                errors.append(f"gemini: {exc}")
        if self.settings.groq_api_key:
            try:
                return await self._groq(
                    system_prompt=system_prompt,
                    messages=messages,
                    temperature=temperature,
                    max_tokens=max_tokens,
                    json_mode=json_mode,
                )
            except Exception as exc:
                logger.warning("groq_call_failed", error=str(exc))
                errors.append(f"groq: {exc}")

        raise ServiceUnavailableError(f"All LLM providers failed ({'; '.join(errors)}).")

    async def _gemini(
        self,
        *,
        system_prompt: str,
        messages: list[dict[str, str]],
        temperature: float,
        max_tokens: int,
        json_mode: bool,
    ) -> LLMResult:
        model = self.settings.gemini_model
        contents: list[dict[str, Any]] = [
            {
                "role": "model" if m["role"] == "assistant" else "user",
                "parts": [{"text": m["content"]}],
            }
            for m in messages
        ]
        payload: dict[str, Any] = {
            "contents": contents,
            "systemInstruction": {"parts": [{"text": system_prompt}]},
            "generationConfig": {
                "temperature": temperature,
                "maxOutputTokens": max_tokens,
            },
        }
        if json_mode:
            payload["generationConfig"]["responseMimeType"] = "application/json"

        async with httpx.AsyncClient(timeout=self.settings.llm_timeout_seconds) as client:
            response = await _post_with_retry(
                client,
                GEMINI_ENDPOINT.format(model=model),
                params={"key": self.settings.gemini_api_key},
                json=payload,
            )
            if response.status_code >= 400:
                raise ValueError(f"Gemini HTTP {response.status_code}: {response.text[:500]}")
            data = response.json()

        candidates = data.get("candidates") or []
        if not candidates:
            raise ValueError(f"Gemini returned no candidates: {data.get('promptFeedback')}")
        parts = candidates[0].get("content", {}).get("parts", [])
        text = "".join(p.get("text", "") for p in parts).strip()
        if not text:
            raise ValueError("Gemini returned an empty completion.")
        return LLMResult(text=text, provider="gemini", model=model)

    async def _groq(
        self,
        *,
        system_prompt: str,
        messages: list[dict[str, str]],
        temperature: float,
        max_tokens: int,
        json_mode: bool,
    ) -> LLMResult:
        model = self.settings.groq_model
        payload: dict[str, Any] = {
            "model": model,
            "messages": [{"role": "system", "content": system_prompt}, *messages],
            "temperature": temperature,
            "max_tokens": max_tokens,
        }
        if json_mode:
            payload["response_format"] = {"type": "json_object"}

        async with httpx.AsyncClient(timeout=self.settings.llm_timeout_seconds) as client:
            response = await _post_with_retry(
                client,
                GROQ_ENDPOINT,
                headers={"Authorization": f"Bearer {self.settings.groq_api_key}"},
                json=payload,
            )
            if response.status_code >= 400:
                raise ValueError(f"Groq HTTP {response.status_code}: {response.text[:500]}")
            data = response.json()

        choices = data.get("choices") or []
        if not choices:
            raise ValueError("Groq returned no choices.")
        text = (choices[0].get("message") or {}).get("content", "").strip()
        if not text:
            raise ValueError("Groq returned an empty completion.")
        return LLMResult(text=text, provider="groq", model=model)

    async def embed_text(self, text: str) -> list[float]:
        """Generate embedding vector using Gemini's text-embedding-004 model."""
        if not self.settings.gemini_api_key:
            raise ValueError("Gemini API key is not configured.")

        endpoint = "https://generativelanguage.googleapis.com/v1beta/models/text-embedding-004:embedContent"
        payload = {
            "model": "models/text-embedding-004",
            "content": {
                "parts": [{"text": text}]
            }
        }
        async with httpx.AsyncClient(timeout=self.settings.llm_timeout_seconds) as client:
            response = await _post_with_retry(
                client,
                endpoint,
                params={"key": self.settings.gemini_api_key},
                json=payload,
            )
            if response.status_code >= 400:
                raise ValueError(f"Gemini Embedding HTTP {response.status_code}: {response.text[:500]}")
            data = response.json()

        embedding = data.get("embedding", {}).get("values")
        if not embedding:
            raise ValueError("Gemini Embedding API returned no values.")
        return [float(v) for v in embedding]
