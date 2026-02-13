import asyncio
import logging
from typing import Tuple

import httpx
import openai
from google import genai

from ..settings import Settings


logger = logging.getLogger(__name__)


class LLMGateway:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self._openai_client: openai.AsyncOpenAI | None = None
        self._local_client: openai.AsyncOpenAI | None = None
        self._gemini_client: genai.Client | None = None

    def available_providers(self) -> list[str]:
        return [p for p in self.settings.llm_provider_chain if self.settings.provider_has_required_config(p)]

    async def close(self) -> None:
        if self._openai_client is not None:
            await self._openai_client.close()
            self._openai_client = None
        if self._local_client is not None:
            await self._local_client.close()
            self._local_client = None

    async def generate(self, system_prompt: str, user_prompt: str) -> Tuple[str, str, str]:
        providers = self.available_providers()
        if not providers:
            raise RuntimeError("No configured LLM provider is available")

        last_error = None
        for provider in providers:
            provider = provider.lower()
            try:
                if provider == "openai":
                    text = await self._generate_openai(system_prompt, user_prompt)
                    return text, "openai", self.settings.openai_model_name
                if provider == "gemini":
                    text, model_name = await self._generate_gemini(system_prompt, user_prompt)
                    return text, "gemini", model_name
                if provider == "local":
                    text = await self._generate_local(system_prompt, user_prompt)
                    return text, "local", self.settings.local_model_name
            except Exception as exc:
                last_error = exc
                logger.warning("Provider %s failed: %s", provider, exc)
                continue
        raise RuntimeError(f"All configured providers failed: {last_error}")

    def _get_openai_client(self) -> openai.AsyncOpenAI:
        if self._openai_client is None:
            self._openai_client = openai.AsyncOpenAI(
                api_key=self.settings.openai_api_key,
                base_url=self.settings.openai_base_url,
                timeout=httpx.Timeout(60.0, connect=10.0),
            )
        return self._openai_client

    def _get_local_client(self) -> openai.AsyncOpenAI:
        if self._local_client is None:
            self._local_client = openai.AsyncOpenAI(
                api_key=self.settings.local_api_key,
                base_url=self.settings.local_base_url,
                timeout=httpx.Timeout(120.0, connect=10.0),
            )
        return self._local_client

    def _get_gemini_client(self) -> genai.Client:
        if self._gemini_client is None:
            self._gemini_client = genai.Client(api_key=self.settings.gemini_api_key)
        return self._gemini_client

    async def _generate_openai(self, system_prompt: str, user_prompt: str) -> str:
        if not self.settings.openai_api_key:
            raise RuntimeError("OPENAI_API_KEY is missing")
        client = self._get_openai_client()
        resp = await client.chat.completions.create(
            model=self.settings.openai_model_name,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            temperature=0.2,
            max_tokens=420,
        )
        if not resp.choices:
            raise RuntimeError("OpenAI returned no choices")
        return (resp.choices[0].message.content or "").strip()

    async def _generate_local(self, system_prompt: str, user_prompt: str) -> str:
        client = self._get_local_client()
        resp = await client.chat.completions.create(
            model=self.settings.local_model_name,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            temperature=0.2,
            max_tokens=420,
        )
        if not resp.choices:
            raise RuntimeError("Local provider returned no choices")
        return (resp.choices[0].message.content or "").strip()

    async def _generate_gemini(self, system_prompt: str, user_prompt: str) -> Tuple[str, str]:
        if not self.settings.gemini_api_key:
            raise RuntimeError("GEMINI_API_KEY is missing")

        client = self._get_gemini_client()
        models = [self.settings.gemini_model_name] + list(self.settings.gemini_fallback_models)
        seen = set()
        candidates = []
        for model_name in models:
            if model_name and model_name not in seen:
                candidates.append(model_name)
                seen.add(model_name)

        content = f"{system_prompt}\n\n{user_prompt}"
        last_error = None
        for model_name in candidates:
            for attempt in range(self.settings.gemini_max_retries + 1):
                try:
                    response = await asyncio.to_thread(
                        client.models.generate_content,
                        model=model_name,
                        contents=content,
                    )
                    text = (response.text or "").strip()
                    if not text:
                        raise RuntimeError("Gemini returned empty text")
                    return text, model_name
                except Exception as exc:
                    last_error = exc
                    error_text = str(exc).upper()
                    retryable = any(k in error_text for k in ["429", "503", "UNAVAILABLE", "RESOURCE_EXHAUSTED"])
                    if retryable and attempt < self.settings.gemini_max_retries:
                        delay = self.settings.gemini_retry_base_seconds * (2**attempt)
                        await asyncio.sleep(delay)
                        continue
                    break
        raise RuntimeError(f"Gemini failed: {last_error}")
