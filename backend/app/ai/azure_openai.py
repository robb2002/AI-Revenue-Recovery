"""Minimal Azure OpenAI chat client (same endpoint pattern as Sales Intelligence)."""

from __future__ import annotations

import json
import logging
import re
from typing import Any

import httpx

from app.core.config import Settings, get_settings

logger = logging.getLogger("app.ai.azure_openai")


class AzureChatClient:
    def __init__(self, settings: Settings | None = None) -> None:
        self.settings = settings or get_settings()

    @property
    def configured(self) -> bool:
        return self.settings.llm_configured

    async def chat_json(
        self,
        *,
        system: str,
        user: str,
        temperature: float = 0.3,
        timeout_seconds: float | None = None,
    ) -> dict[str, Any] | None:
        if not self.configured:
            return None
        endpoint = self.settings.azure_openai_endpoint.rstrip("/")
        deployment = self.settings.llm_model
        url = (
            f"{endpoint}/openai/deployments/{deployment}/chat/completions"
            f"?api-version={self.settings.azure_openai_api_version}"
        )
        payload = {
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
            "temperature": temperature,
            "response_format": {"type": "json_object"},
        }
        headers = {
            "api-key": self.settings.llm_api_key,
            "Content-Type": "application/json",
        }
        timeout = timeout_seconds if timeout_seconds is not None else self.settings.llm_timeout_seconds
        try:
            async with httpx.AsyncClient(timeout=timeout) as client:
                response = await client.post(url, headers=headers, json=payload)
                response.raise_for_status()
                data = response.json()
            content = data["choices"][0]["message"]["content"]
            return _parse_json_object(content)
        except Exception:
            logger.exception("Azure OpenAI chat failed; caller should fall back")
            return None


def _parse_json_object(content: str) -> dict[str, Any] | None:
    text = (content or "").strip()
    if not text:
        return None
    try:
        value = json.loads(text)
        return value if isinstance(value, dict) else None
    except json.JSONDecodeError:
        match = re.search(r"\{[\s\S]*\}", text)
        if not match:
            return None
        try:
            value = json.loads(match.group(0))
            return value if isinstance(value, dict) else None
        except json.JSONDecodeError:
            return None
