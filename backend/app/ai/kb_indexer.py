"""Chunk + embed knowledge_base markdown into revenue_recovery.kb_chunks (pgvector)."""

from __future__ import annotations

import hashlib
import json
import logging
import re
import uuid
from pathlib import Path
from typing import Any

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.ai.embeddings import AzureOpenAIEmbeddings, vector_literal
from app.core.config import get_settings

logger = logging.getLogger("app.ai.kb_indexer")

KB_DIR = Path(__file__).resolve().parents[2] / "data" / "crm_master" / "knowledge_base"
UPLOAD_DIR = Path(__file__).resolve().parents[2] / "data" / "uploads" / "knowledge"

_tables_ready = False


def _parse_front_matter(raw: str) -> tuple[dict[str, Any], str]:
    if not raw.startswith("---"):
        return {}, raw
    end = raw.find("\n---", 3)
    if end < 0:
        return {}, raw
    header = raw[3:end].strip()
    body = raw[end + 4 :].lstrip("\n")
    meta: dict[str, Any] = {}
    for line in header.splitlines():
        if ":" not in line:
            continue
        key, val = line.split(":", 1)
        key = key.strip()
        val = val.strip().strip('"').strip("'")
        if val.startswith("[") and val.endswith("]"):
            inner = val[1:-1]
            meta[key] = [p.strip().strip('"').strip("'") for p in inner.split(",") if p.strip()]
        else:
            meta[key] = val
    return meta, body


def chunk_markdown_text(
    raw: str,
    *,
    doc_id: str,
    title: str,
    version: str = "1.0",
    classification: str = "SYNTHETIC",
    source_url: str | None = None,
    categories: list[str] | None = None,
    source_kind: str = "bundled_kb",
    account_id: str | None = None,
) -> list[dict[str, Any]]:
    meta, body = _parse_front_matter(raw)
    doc_id = str(meta.get("doc_id") or doc_id)
    title = str(meta.get("title") or title)
    version = str(meta.get("version") or version)
    label = str(meta.get("label") or "")
    if "PUBLIC_VERIFIED" in label.upper() or doc_id.startswith("KB-OFF"):
        classification = "PUBLIC_VERIFIED"
    source_urls = meta.get("source_urls") or []
    if isinstance(source_urls, str):
        source_urls = [source_urls]
    if source_urls and not source_url:
        source_url = source_urls[0]
    categories = meta.get("blocker_categories") or categories or []

    parts = re.split(r"(?m)^##\s+", body)
    chunks: list[dict[str, Any]] = []
    if parts and parts[0].strip() and len(parts[0].strip()) > 40:
        chunks.append(
            _make_chunk(
                doc_id, title, version, "Overview", parts[0].strip(),
                source_url, classification, categories, source_kind, account_id,
            )
        )
    for part in parts[1:]:
        if not part.strip():
            continue
        lines = part.splitlines()
        section = lines[0].strip()
        content = "\n".join(lines[1:]).strip() or lines[0].strip()
        full = f"## {section}\n{content}".strip()
        chunks.append(
            _make_chunk(
                doc_id, title, version, section, full,
                source_url, classification, categories, source_kind, account_id,
            )
        )
    if not chunks and body.strip():
        chunks.append(
            _make_chunk(
                doc_id, title, version, "Body", body.strip(),
                source_url, classification, categories, source_kind, account_id,
            )
        )
    return chunks


def chunk_markdown(path: Path) -> list[dict[str, Any]]:
    raw = path.read_text(encoding="utf-8")
    stem = path.stem
    doc_id = stem.split("_")[0]
    return chunk_markdown_text(raw, doc_id=doc_id, title=stem)


def _make_chunk(
    doc_id: str,
    title: str,
    version: str,
    section: str,
    content: str,
    source_url: str | None,
    classification: str,
    categories: list[str],
    source_kind: str,
    account_id: str | None,
) -> dict[str, Any]:
    digest = hashlib.sha256(f"{doc_id}|{section}|{content}".encode("utf-8")).hexdigest()
    return {
        "chunk_id": str(uuid.uuid5(uuid.NAMESPACE_URL, digest)),
        "doc_id": doc_id,
        "title": title,
        "version": version,
        "section": section,
        "content": content,
        "source_url": source_url,
        "classification": classification,
        "source_kind": source_kind,
        "account_id": account_id,
        "content_hash": digest,
        "categories": categories,
    }


async def ensure_kb_tables(session: AsyncSession) -> None:
    global _tables_ready
    if _tables_ready:
        return
    settings = get_settings()
    # Supabase installs pgvector in schema "extensions"
    ext = await session.scalar(
        text("select 1 from pg_extension where extname = 'vector' limit 1")
    )
    if not ext:
        await session.execute(
            text("create extension if not exists vector with schema extensions")
        )
    vec = f"extensions.vector({settings.embedding_dimensions})"
    await session.execute(
        text(
            f"""
            create table if not exists kb_chunks (
              chunk_id text primary key,
              doc_id text not null,
              title text not null,
              version text,
              section text,
              content text not null,
              source_url text,
              classification text,
              source_kind text not null default 'bundled_kb',
              account_id text,
              content_hash text not null,
              categories jsonb default '[]'::jsonb,
              embedding {vec},
              embedding_model text,
              created_at timestamptz default now()
            )
            """
        )
    )
    # Migrate older jsonb embedding column if present
    col = await session.scalar(
        text(
            """
            select udt_name from information_schema.columns
            where table_schema = current_schema()
              and table_name = 'kb_chunks' and column_name = 'embedding'
            """
        )
    )
    if col and col.lower() in {"json", "jsonb"}:
        await session.execute(text("alter table kb_chunks drop column embedding"))
        await session.execute(text(f"alter table kb_chunks add column embedding {vec}"))
    elif col is None:
        await session.execute(
            text(f"alter table kb_chunks add column if not exists embedding {vec}")
        )
    await session.execute(
        text(
            """
            alter table kb_chunks
              add column if not exists embedding_model text
            """
        )
    )
    await session.execute(
        text(
            """
            create table if not exists blocker_answer_drafts (
              answer_id text primary key,
              account_id text not null,
              question text not null,
              answer_status text not null,
              answer_text text,
              citations jsonb default '[]'::jsonb,
              missing jsonb default '[]'::jsonb,
              recommended_action text,
              model_called boolean default false,
              state text not null default 'draft',
              notice text,
              created_at timestamptz default now(),
              updated_at timestamptz default now()
            )
            """
        )
    )
    await session.commit()
    _tables_ready = True


async def _embed_and_insert(session: AsyncSession, chunks: list[dict[str, Any]]) -> dict[str, Any]:
    settings = get_settings()
    embedder = AzureOpenAIEmbeddings(settings)
    embedded = 0
    mode = "lexical_only"
    vectors: list[list[float]] | None = None
    if embedder.configured and chunks:
        try:
            # Cap content for embedding API
            texts = [c["content"][:6000] for c in chunks]
            vectors = await embedder.embed_texts(texts)
            mode = "azure_embeddings"
            embedded = len(vectors)
        except Exception:
            logger.exception("Embedding failed; storing chunks without vectors")
            vectors = None
            mode = "lexical_fallback"

    for i, ch in enumerate(chunks):
        params = {
            **{k: ch[k] for k in (
                "chunk_id", "doc_id", "title", "version", "section", "content",
                "source_url", "classification", "source_kind", "account_id", "content_hash",
            )},
            "categories": json.dumps(ch.get("categories") or []),
        }
        if vectors is not None:
            params["embedding"] = vector_literal(vectors[i])
            params["embedding_model"] = settings.embedding_model
            sql = """
                insert into kb_chunks (
                  chunk_id, doc_id, title, version, section, content, source_url,
                  classification, source_kind, account_id, content_hash, categories,
                  embedding, embedding_model
                ) values (
                  :chunk_id, :doc_id, :title, :version, :section, :content, :source_url,
                  :classification, :source_kind, :account_id, :content_hash,
                  cast(:categories as jsonb), CAST(:embedding AS extensions.vector), :embedding_model
                )
                on conflict (chunk_id) do update set
                  content = excluded.content,
                  title = excluded.title,
                  section = excluded.section,
                  content_hash = excluded.content_hash,
                  embedding = excluded.embedding,
                  embedding_model = excluded.embedding_model
                """
        else:
            sql = """
                insert into kb_chunks (
                  chunk_id, doc_id, title, version, section, content, source_url,
                  classification, source_kind, account_id, content_hash, categories
                ) values (
                  :chunk_id, :doc_id, :title, :version, :section, :content, :source_url,
                  :classification, :source_kind, :account_id, :content_hash,
                  cast(:categories as jsonb)
                )
                on conflict (chunk_id) do update set
                  content = excluded.content,
                  title = excluded.title,
                  section = excluded.section,
                  content_hash = excluded.content_hash
                """
        await session.execute(text(sql), params)
    await session.commit()
    return {"embedded_chunks": embedded, "retrieval_mode": mode}


async def index_bundled_kb(session: AsyncSession) -> dict[str, Any]:
    await ensure_kb_tables(session)
    files = sorted(KB_DIR.glob("KB-*.md"))
    all_chunks: list[dict[str, Any]] = []
    for path in files:
        all_chunks.extend(chunk_markdown(path))

    await session.execute(text("delete from kb_chunks where source_kind = 'bundled_kb'"))
    await session.commit()
    emb_info = await _embed_and_insert(session, all_chunks)
    docs = sorted({c["doc_id"] for c in all_chunks})
    return {
        "indexed_docs": len(docs),
        "indexed_chunks": len(all_chunks),
        "doc_ids": docs,
        "source": "bundled_kb",
        "embedding_model": get_settings().embedding_model,
        "embedding_dimensions": get_settings().embedding_dimensions,
        **emb_info,
    }


async def upload_knowledge_document(
    session: AsyncSession,
    *,
    filename: str,
    data: bytes,
    account_id: str | None = None,
    title: str | None = None,
) -> dict[str, Any]:
    await ensure_kb_tables(session)
    ext = Path(filename).suffix.lower().lstrip(".")
    if ext not in {"txt", "md"}:
        from app.core.errors import AppError

        class Unsupported(AppError):
            status_code = 415
            code = "UNSUPPORTED_MEDIA"
            message = "Upload txt or md for MVP knowledge indexing."

        raise Unsupported()

    text_body = data.decode("utf-8", errors="replace")
    UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
    doc_id = f"KB-UP-{uuid.uuid4().hex[:8].upper()}"
    safe_name = re.sub(r"[^A-Za-z0-9._-]", "_", filename)[:120]
    path = UPLOAD_DIR / f"{doc_id}_{safe_name}"
    path.write_bytes(data)

    chunks = chunk_markdown_text(
        text_body,
        doc_id=doc_id,
        title=title or Path(filename).stem,
        classification="SYNTHETIC",
        source_kind="salesperson_upload",
        account_id=account_id,
        categories=["Uploaded"],
    )
    if not chunks:
        from app.core.errors import AppError

        class EmptyDoc(AppError):
            status_code = 422
            code = "VALIDATION_ERROR"
            message = "Document produced no chunks."

        raise EmptyDoc()

    emb_info = await _embed_and_insert(session, chunks)
    return {
        "doc_id": doc_id,
        "title": chunks[0]["title"],
        "chunk_count": len(chunks),
        "storage_path": str(path.relative_to(UPLOAD_DIR.parent.parent)).replace("\\", "/"),
        "account_id": account_id,
        "source_kind": "salesperson_upload",
        **emb_info,
        "notice": "Uploaded document indexed for retrieval. Not a Pearson official source.",
    }


async def list_documents(session: AsyncSession) -> dict[str, Any]:
    await ensure_kb_tables(session)
    rows = (
        await session.execute(
            text(
                """
                select distinct on (doc_id)
                  doc_id, title, version, classification, categories, source_kind,
                  account_id,
                  (embedding is not null) as has_embedding
                from kb_chunks
                order by doc_id, title
                """
            )
        )
    ).mappings().all()
    items = []
    for r in rows:
        cats = r["categories"]
        if isinstance(cats, str):
            try:
                cats = json.loads(cats)
            except json.JSONDecodeError:
                cats = []
        items.append(
            {
                "doc_id": r["doc_id"],
                "title": r["title"],
                "version": r["version"],
                "classification": r["classification"],
                "blocker_categories": cats or [],
                "source_kind": r["source_kind"],
                "account_id": r["account_id"],
                "has_embedding": bool(r["has_embedding"]),
            }
        )
    embedded = sum(1 for i in items if i["has_embedding"])
    return {
        "items": items,
        "total": len(items),
        "expected_bundled": 21,
        "docs_with_embeddings": embedded,
        "embedding_model": get_settings().embedding_model,
        "embedding_dimensions": get_settings().embedding_dimensions,
        "similarity_gate": get_settings().embedding_similarity_gate,
        "data_label": "Fictional demo data / PUBLIC_VERIFIED excerpts",
    }
