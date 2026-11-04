"""KB retrieval — Azure embedding cosine search (parent gate 0.72) + lexical fallback."""

from __future__ import annotations

import logging
import math
import re
from collections import Counter
from typing import Any

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.ai.embeddings import AzureOpenAIEmbeddings, vector_literal
from app.core.config import get_settings

logger = logging.getLogger("app.ai.retrieval")


def _tokenize(text: str) -> list[str]:
    return re.findall(r"[a-z0-9+]{2,}", (text or "").lower())


def _lexical_score(question: str, content: str) -> float:
    q = _tokenize(question)
    if not q:
        return 0.0
    c = Counter(_tokenize(content))
    if not c:
        return 0.0
    hits = sum(1 for t in q if c[t] > 0)
    overlap = hits / max(len(set(q)), 1)
    dens = hits / math.sqrt(len(c) + 1)
    return min(1.0, overlap * 0.75 + dens * 0.2)


async def retrieve(
    session: AsyncSession, question: str, *, top_k: int | None = None
) -> list[dict[str, Any]]:
    settings = get_settings()
    k = top_k or settings.retrieval_top_k
    embedder = AzureOpenAIEmbeddings(settings)

    # Prefer pgvector cosine search when embeddings exist
    has_vectors = await session.scalar(
        text("select exists(select 1 from kb_chunks where embedding is not null limit 1)")
    )
    if has_vectors and embedder.configured:
        try:
            qvec = await embedder.embed_query(question)
            rows = (
                await session.execute(
                    text(
                        """
                        select chunk_id, doc_id, title, version, section, content, source_url,
                               classification, content_hash, source_kind, account_id,
                               1 - (embedding OPERATOR(extensions.<=>) CAST(:q AS extensions.vector))
                                 AS similarity
                        from kb_chunks
                        where embedding is not null
                        order by embedding OPERATOR(extensions.<=>) CAST(:q AS extensions.vector)
                        limit :k
                        """
                    ),
                    {"q": vector_literal(qvec), "k": k},
                )
            ).mappings().all()
            out = []
            for r in rows:
                item = dict(r)
                item["similarity"] = float(item["similarity"] or 0)
                item["retrieval"] = "embedding"
                out.append(item)
            return out
        except Exception:
            logger.exception("Embedding retrieval failed; falling back to lexical")
            await session.rollback()

    # Lexical fallback
    rows = (
        await session.execute(
            text(
                """
                select chunk_id, doc_id, title, version, section, content, source_url,
                       classification, content_hash, source_kind, account_id
                from kb_chunks
                """
            )
        )
    ).mappings().all()
    scored: list[tuple[float, dict[str, Any]]] = []
    for r in rows:
        s = _lexical_score(question, f"{r['title']} {r['section']} {r['content']}")
        if s > 0:
            item = dict(r)
            item["similarity"] = round(s, 4)
            item["retrieval"] = "lexical"
            scored.append((s, item))
    scored.sort(key=lambda x: x[0], reverse=True)
    return [item for _, item in scored[:k]]


def gate_chunks(chunks: list[dict[str, Any]]) -> list[dict[str, Any]]:
    settings = get_settings()
    gate = settings.embedding_similarity_gate
    # Lexical scores are lower scale — use a softer gate when retrieval mode is lexical
    out = []
    for c in chunks:
        sim = float(c.get("similarity") or 0)
        mode = c.get("retrieval") or "embedding"
        threshold = gate if mode == "embedding" else min(0.08, gate)
        if sim >= threshold:
            out.append(c)
    return out
