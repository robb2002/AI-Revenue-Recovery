"""Azure OpenAI embeddings — same pattern as AI Sales Intelligence System.

Deployment: text-embedding-ada-002 (1536 dims).
"""

from __future__ import annotations

import logging

import httpx

from app.core.config import Settings, get_settings

logger = logging.getLogger("app.ai.embeddings")


class AzureOpenAIEmbeddings:
    def __init__(self, settings: Settings | None = None) -> None:
        self.settings = settings or get_settings()

    @property
    def configured(self) -> bool:
        return self.settings.embedding_configured

    async def embed_texts(self, texts: list[str]) -> list[list[float]]:
        if not self.configured:
            raise RuntimeError("Azure embeddings are not configured")
        cleaned = [t.strip() for t in texts if t and t.strip()]
        if not cleaned:
            return []

        endpoint = self.settings.azure_openai_endpoint.rstrip("/")
        deployment = self.settings.embedding_model
        url = (
            f"{endpoint}/openai/deployments/{deployment}/embeddings"
            f"?api-version={self.settings.azure_openai_api_version}"
        )
        vectors: list[list[float]] = []
        batch_size = 16
        timeout = self.settings.embedding_timeout_seconds
        async with httpx.AsyncClient(timeout=timeout) as client:
            for i in range(0, len(cleaned), batch_size):
                batch = cleaned[i : i + batch_size]
                response = await client.post(
                    url,
                    headers={
                        "api-key": self.settings.llm_api_key,
                        "Content-Type": "application/json",
                    },
                    json={"input": batch},
                )
                if response.status_code >= 400:
                    logger.error(
                        "Azure embedding failed status=%s body=%s",
                        response.status_code,
                        response.text[:500],
                    )
                    response.raise_for_status()
                payload = response.json()
                data = payload.get("data") or []
                data_sorted = sorted(data, key=lambda item: int(item.get("index", 0)))
                for item in data_sorted:
                    emb = item.get("embedding")
                    if not isinstance(emb, list):
                        raise RuntimeError("Embedding response missing vector")
                    if len(emb) != self.settings.embedding_dimensions:
                        raise RuntimeError(
                            f"Embedding width {len(emb)} != "
                            f"{self.settings.embedding_dimensions}"
                        )
                    vectors.append([float(x) for x in emb])
        if len(vectors) != len(cleaned):
            raise RuntimeError("Embedding count mismatch")
        return vectors

    async def embed_query(self, text: str) -> list[float]:
        vectors = await self.embed_texts([text])
        return vectors[0]


def vector_literal(values: list[float]) -> str:
    """pgvector text form for CAST(:q AS vector)."""
    return "[" + ",".join(f"{v:.8f}" for v in values) + "]"
