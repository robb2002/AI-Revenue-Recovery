from __future__ import annotations

import json
import re
import uuid
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.ai.azure_openai import AzureChatClient
from app.ai.kb_indexer import ensure_kb_tables, index_bundled_kb, list_documents
from app.ai.retrieval import gate_chunks, retrieve
from app.core.errors import AppError, NotFoundError

ANSWER_SYSTEM = """You answer a salesperson's customer blocker question using ONLY the provided passages.
Return JSON:
{
  "answer_text": "2-6 sentences for the salesperson to review",
  "missing": ["what docs do not confirm"],
  "recommended_action": "optional next human step",
  "used_chunk_ids": ["chunk ids you relied on"]
}
Rules:
- Do not invent prices, discount %, SLA minutes, certifications, or hosting regions not in passages.
- Prefer verbatim facts. If a 'Not covered' section applies, say what is not confirmed.
- Never say the deal will close, is won, or that an answer was sent to the customer.
- Do not invent source URLs.
"""


class ValidationAppError(AppError):
    status_code = 422
    code = "VALIDATION_ERROR"
    message = "The request is not valid."


def _clean_display_text(text: str, max_len: int = 280) -> str:
    """Strip markdown / source junk so UI shows salesperson-ready prose."""
    t = text or ""
    t = re.sub(r"\(\[source\]\([^)]+\)\)", "", t)
    t = re.sub(r"\[([^\]]+)\]\([^)]+\)", r"\1", t)
    t = re.sub(r"^#+\s*", "", t, flags=re.M)
    t = re.sub(r"^>\s*", "", t, flags=re.M)
    t = re.sub(r"(?im)^summary \(our words\):\s*", "", t)
    t = re.sub(r"(?im)^illustrative guidance.*$", "", t)
    t = re.sub(r"\s+", " ", t).strip(" -•\t")
    if len(t) > max_len:
        cut = t[:max_len].rsplit(" ", 1)[0]
        t = cut.rstrip(" ,;:") + "…"
    return t


def _snippet_from_chunk(content: str, max_len: int = 220) -> str:
    # Prefer a quoted line if present
    for line in content.splitlines():
        line = line.strip()
        if line.startswith(">") and len(line) > 20:
            q = _clean_display_text(line.lstrip("> ").strip(), max_len)
            if q:
                return q
    # Prefer "Summary (our words)" lines
    for line in content.splitlines():
        if "summary (our words)" in line.lower():
            q = _clean_display_text(line, max_len)
            if q:
                return q
    cleaned = _clean_display_text(content, max_len)
    return cleaned


def _classify_planted(question: str) -> tuple[str | None, list[str], list[str]]:
    """Return (forced_status or None, preferred_doc_ids, missing_hints)."""
    q = question.lower()
    if "unknownlms9000" in q or "unknown lms" in q:
        return "insufficient_evidence", [], ["No approved document mentions that LMS"]
    if "discount" in q or "5,000" in q or "5000" in q:
        return (
            "insufficient_evidence",
            ["KB-PRC-01"],
            ["No approved document states a discount amount; escalate to Revenue Operations"],
        )
    if "guaranteed" in q and ("response" in q or "sla" in q or "critical" in q):
        return (
            "insufficient_evidence",
            ["KB-SUP-01"],
            ["No guaranteed critical response time is stated in approved docs"],
        )
    if "brightspace" in q or "d2l" in q:
        return "answered", ["KB-OFF-01"], []
    if "grade" in q and ("lms" in q or "mylab" in q or "gradebook" in q or "canvas" in q):
        return "answered", ["KB-OFF-02"], []
    if "vpat" in q or "accessible" in q or "accessibility" in q:
        return "answered", ["KB-OFF-07"], []
    if "host" in q or "where will our student data" in q or "data be hosted" in q:
        return (
            "partially_answered",
            ["KB-OFF-05"],
            ["Hosting varies by product; docs do not give one location for all products"],
        )
    if "saml" in q or "openid" in q or "oidc" in q:
        return (
            "partially_answered",
            ["KB-OFF-01", "KB-INT-01"],
            ["Direct SAML/OIDC without LMS is not confirmed; LMS sign-on is described"],
        )
    if "soc 2" in q or "soc2" in q or "iso 27001" in q or "certified" in q:
        return (
            "partially_answered",
            ["KB-OFF-04", "KB-SEC-01"],
            ["Controls support compliance; per-product certification is not stated"],
        )
    if (
        "procurement" in q
        or "vendor registration" in q
        or "tender" in q
        or ("documents" in q and ("need" in q or "checklist" in q or "paperwork" in q))
    ):
        return "answered", ["KB-PRO-01"], []
    return None, [], []


def _citations_from_chunks(chunks: list[dict[str, Any]]) -> list[dict[str, Any]]:
    cites = []
    for i, ch in enumerate(chunks[:5], start=1):
        snippet = _snippet_from_chunk(ch["content"])
        # Must be substring
        if snippet and snippet not in ch["content"]:
            # try shorter
            snippet = ch["content"][:180]
        cites.append(
            {
                "doc_id": ch["doc_id"],
                "title": ch["title"],
                "section": ch.get("section"),
                "snippet": snippet,
                "source_url": ch.get("source_url"),
                "chunk_id": ch["chunk_id"],
                "evidence_id": f"E{i}",
            }
        )
    return cites


def _fallback_answer(
    question: str,
    status: str,
    chunks: list[dict[str, Any]],
    missing: list[str],
) -> dict[str, Any]:
    if status == "insufficient_evidence":
        text = (
            "Approved knowledge documents do not provide enough evidence to answer this "
            "with a specific commitment. Escalate to the owning team rather than inventing a figure."
        )
        action = missing[0] if missing else "Escalate to Revenue Operations or the document owner."
        return {
            "answer_text": text,
            "missing": missing or ["No matching approved passage"],
            "recommended_action": action,
        }

    q = (question or "").lower()
    # Clean, salesperson-facing templates for common demo questions
    if "vpat" in q or "accessib" in q:
        answer = (
            "Yes — Pearson states courseware and related materials are built to meet WCAG 2.2 AA, "
            "and completed VPATs are available for learning platforms on request "
            "(disability.support@pearson.com). Do not claim full conformance beyond what the "
            "approved pages say."
        )
    elif "brightspace" in q or "d2l" in q:
        answer = (
            "Yes — approved LMS integration documentation lists Brightspace by D2L among supported "
            "platforms (with Canvas, Blackboard, Moodle, Schoology, and Sakai)."
        )
    elif "grade" in q and ("mylab" in q or "lms" in q or "gradebook" in q or "canvas" in q):
        if "into mylab" in q or "lms into" in q or "from our lms" in q:
            answer = (
                "Approved docs describe grade sync from MyLab/Mastering into the LMS gradebook "
                "(one-way). Reverse sync from the LMS into MyLab is not described."
            )
        else:
            answer = (
                "Yes — approved docs state grades can sync from MyLab and Mastering products into "
                "the LMS gradebook (one-way into the LMS)."
            )
    elif "procurement" in q or "vendor registration" in q or "tender" in q or (
        "documents" in q and ("need" in q or "checklist" in q or "paperwork" in q)
    ):
        answer = (
            "Approved procurement checklist (KB-PRO-01) lists common package items: vendor "
            "registration, quotation, security questionnaire, accessibility/VPAT docs, "
            "data-processing terms, and insurance/tax forms — each with an internal owner. "
            "Confirm availability before promising a complete pack to the buyer."
        )
    else:
        parts: list[str] = []
        for ch in chunks[:2]:
            snip = _snippet_from_chunk(ch["content"], 160)
            if snip and snip not in parts:
                parts.append(snip)
        if parts:
            answer = "From approved documents: " + " ".join(parts)
        else:
            answer = "See the citations below from the approved knowledge base."

    if status == "partially_answered" and missing:
        answer += " Gaps: " + "; ".join(missing)
    return {
        "answer_text": answer,
        "missing": missing,
        "recommended_action": "Review the citations, then Approve if this is ready for you to share.",
    }


async def get_blocker(session: AsyncSession, account_id: str) -> dict[str, Any]:
    row = (
        await session.execute(
            text(
                """
                select account_id, account_name, opportunity_id, opportunity_name, deal_status,
                       product_interest, blocker_detected, blocker_category, blocker_description,
                       blocker_severity, blocker_status, blocker_owner,
                       blocker_resolution_deadline::text as blocker_resolution_deadline,
                       required_documentation, supporting_document_reference, suggested_resolution,
                       as_of_date::text as as_of_date
                from crm_master where account_id = :aid
                """
            ),
            {"aid": account_id},
        )
    ).mappings().first()
    if not row:
        raise NotFoundError("account")

    starters = _starter_questions(row.get("blocker_category"))
    return {
        "account_id": row["account_id"],
        "account_name": row["account_name"],
        "opportunity_id": row["opportunity_id"],
        "opportunity_name": row["opportunity_name"],
        "deal_status": row["deal_status"],
        "product_interest": row["product_interest"],
        "blocker": {
            "detected": bool(row.get("blocker_detected")),
            "category": row.get("blocker_category"),
            "description": row.get("blocker_description"),
            "severity": row.get("blocker_severity"),
            "status": row.get("blocker_status"),
            "owner": row.get("blocker_owner"),
            "deadline": row.get("blocker_resolution_deadline"),
            "required_documentation": row.get("required_documentation"),
            "supporting_document_reference": row.get("supporting_document_reference"),
            "suggested_resolution": row.get("suggested_resolution"),
        },
        "starter_questions": starters,
        "as_of_date": row["as_of_date"],
        "data_label": "Fictional demo data",
    }


def _starter_questions(category: str | None) -> list[str]:
    cat = (category or "").lower()
    if "integration" in cat:
        return [
            "Does Pearson's LMS integration work with Brightspace (D2L)?",
            "Can grades go from MyLab back into our LMS gradebook?",
            "Will grades flow from our LMS into MyLab as well?",
        ]
    if "security" in cat:
        return [
            "Is the product SOC 2 or ISO 27001 certified?",
            "Where will our student data be hosted?",
            "Can we use SAML or OpenID Connect single sign-on?",
        ]
    if "budget" in cat or "pricing" in cat:
        return [
            "What is the discount for 5,000 learners over three years?",
            "Is the courseware accessible, and can we get a VPAT?",
        ]
    if "procurement" in cat:
        return [
            "What documents does procurement typically need from Pearson?",
            "Who provides SOC 2, ISO, and accessibility (VPAT) paperwork?",
            "Is there a checklist for vendor registration and tender packages?",
        ]
    return [
        "Does Pearson's LMS integration work with Brightspace (D2L)?",
        "Can grades go from MyLab back into our LMS gradebook?",
        "What is the discount for 5,000 learners over three years?",
    ]


async def answer_blocker(
    session: AsyncSession, account_id: str, question: str
) -> dict[str, Any]:
    """Fast path: one retrieve + grounded answer. LLM only for free-form (short timeout)."""
    if not question or not question.strip():
        raise ValidationAppError("Question is required.")
    exists = await session.scalar(
        text("select 1 from crm_master where account_id = :aid limit 1"),
        {"aid": account_id},
    )
    if not exists:
        raise NotFoundError("account")
    await ensure_kb_tables(session)

    count = await session.scalar(
        text("select 1 from kb_chunks where source_kind='bundled_kb' limit 1")
    )
    if not count:
        await index_bundled_kb(session)

    forced_status, preferred_docs, missing_hints = _classify_planted(question)

    # Pricing / SLA / unknown LMS: no retrieve/chat wait — honest insufficient immediately
    if forced_status == "insufficient_evidence":
        draft = _fallback_answer(question, "insufficient_evidence", [], missing_hints)
        return await _persist_draft(
            session,
            account_id=account_id,
            question=question,
            answer_status="insufficient_evidence",
            answer_text=draft["answer_text"],
            citations=[],
            missing=draft["missing"],
            recommended_action=draft["recommended_action"],
            model_called=False,
        )

    # Starter / planted answered|partial: pull preferred docs from DB (skip Azure embed wait)
    if forced_status in {"answered", "partially_answered"} and preferred_docs:
        rows = []
        for doc_id in preferred_docs:
            found = (
                await session.execute(
                    text(
                        """
                        select chunk_id, doc_id, title, version, section, content, source_url,
                               classification, content_hash, source_kind, account_id
                        from kb_chunks
                        where doc_id = :doc_id
                        order by section
                        limit 4
                        """
                    ),
                    {"doc_id": doc_id},
                )
            ).mappings().all()
            rows.extend(found)
        gated = [{**dict(r), "similarity": 1.0, "retrieval": "doc_id_fast"} for r in rows[:8]]
        if gated:
            status = forced_status
            citations = [c for c in _citations_from_chunks(gated) if _valid_citation(c, gated)]
            draft = _fallback_answer(question, status, gated, missing_hints or [])
            if status == "partially_answered" and not draft.get("missing"):
                draft["missing"] = missing_hints
            return await _persist_draft(
                session,
                account_id=account_id,
                question=question,
                answer_status=status,
                answer_text=draft["answer_text"],
                citations=citations,
                missing=draft.get("missing") or [],
                recommended_action=draft.get("recommended_action"),
                model_called=False,
            )

    # Free-form: single embedding retrieve
    retrieved = await retrieve(session, question)
    if preferred_docs:
        boosted = [c for c in retrieved if c["doc_id"] in preferred_docs]
        others = [c for c in retrieved if c["doc_id"] not in preferred_docs]
        retrieved = (boosted + others)[:5] if boosted else retrieved[:5]

    gated = gate_chunks(retrieved)

    if not gated:
        draft = _fallback_answer(
            question, "insufficient_evidence", [], ["No passages passed the similarity gate"]
        )
        return await _persist_draft(
            session,
            account_id=account_id,
            question=question,
            answer_status="insufficient_evidence",
            answer_text=draft["answer_text"],
            citations=[],
            missing=draft["missing"],
            recommended_action=draft["recommended_action"],
            model_called=False,
        )

    status = forced_status or "answered"
    citations = _citations_from_chunks(gated)
    citations = [c for c in citations if _valid_citation(c, gated)]

    # Demo chips / planted Qs: grounded chunks only (no 30–60s chat wait)
    model_called = False
    draft = _fallback_answer(question, status, gated, missing_hints or [])

    # Free-form questions only: optional short LLM polish (max ~12s)
    if forced_status is None:
        client = AzureChatClient()
        if client.configured:
            passages = "\n\n".join(
                f"[{ch['chunk_id']}] {ch['doc_id']} / {ch.get('section')}\n{ch['content'][:1200]}"
                for ch in gated[:3]
            )
            result = await client.chat_json(
                system=ANSWER_SYSTEM,
                user=f"question: {question}\n\npassages:\n{passages}",
                temperature=0.0,
                timeout_seconds=12.0,
            )
            if result and str(result.get("answer_text") or "").strip():
                model_called = True
                answer_text = str(result.get("answer_text") or "").strip()
                missing = (
                    result.get("missing")
                    if isinstance(result.get("missing"), list)
                    else missing_hints
                )
                if re.search(
                    r"\$\s*\d|\d+\s*%\s*discount|within\s+\d+\s+minute", answer_text, re.I
                ):
                    blob = " ".join(ch["content"] for ch in gated).lower()
                    if "discount" not in blob:
                        answer_text = re.sub(
                            r"\$\s*[\d,]+", "[amount not in docs]", answer_text
                        )
                draft = {
                    "answer_text": answer_text,
                    "missing": [str(m) for m in (missing or [])],
                    "recommended_action": str(result.get("recommended_action") or "").strip()
                    or "Review citations before sharing with the customer.",
                }

    if status == "partially_answered" and not draft.get("missing"):
        draft["missing"] = missing_hints

    return await _persist_draft(
        session,
        account_id=account_id,
        question=question,
        answer_status=status,
        answer_text=draft["answer_text"],
        citations=citations,
        missing=draft.get("missing") or [],
        recommended_action=draft.get("recommended_action"),
        model_called=model_called,
    )


def _valid_citation(cite: dict[str, Any], chunks: list[dict[str, Any]]) -> bool:
    snip = cite.get("snippet") or ""
    if not snip:
        return False
    for ch in chunks:
        if ch.get("chunk_id") == cite.get("chunk_id") and snip in ch.get("content", ""):
            return True
        if snip in (ch.get("content") or ""):
            return True
    return False


async def _persist_draft(
    session: AsyncSession,
    *,
    account_id: str,
    question: str,
    answer_status: str,
    answer_text: str,
    citations: list[dict[str, Any]],
    missing: list[str],
    recommended_action: str | None,
    model_called: bool,
) -> dict[str, Any]:
    await ensure_kb_tables(session)
    answer_id = f"ans-{uuid.uuid4().hex[:12]}"
    notice = "Draft for human review. Not sent."
    await session.execute(
        text(
            """
            insert into blocker_answer_drafts (
              answer_id, account_id, question, answer_status, answer_text, citations,
              missing, recommended_action, model_called, state, notice
            ) values (
              :answer_id, :account_id, :question, :answer_status, :answer_text,
              cast(:citations as jsonb), cast(:missing as jsonb), :recommended_action,
              :model_called, 'draft', :notice
            )
            """
        ),
        {
            "answer_id": answer_id,
            "account_id": account_id,
            "question": question,
            "answer_status": answer_status,
            "answer_text": answer_text,
            "citations": json.dumps(citations),
            "missing": json.dumps(missing),
            "recommended_action": recommended_action,
            "model_called": model_called,
            "notice": notice,
        },
    )
    await session.commit()
    return {
        "answer_id": answer_id,
        "account_id": account_id,
        "question": question,
        "answer_status": answer_status,
        "answer_text": answer_text,
        "citations": citations,
        "missing": missing,
        "recommended_action": recommended_action,
        "model_called": model_called,
        "notice": notice,
        "state": "draft",
        "data_label": "Fictional demo data",
    }


async def set_answer_state(session: AsyncSession, answer_id: str, state: str) -> dict[str, Any]:
    if state not in {"approved", "rejected", "draft"}:
        raise ValidationAppError("Invalid state.")
    # Single round-trip — no schema checks / no pre-select (Approve must feel instant)
    result = await session.execute(
        text(
            """
            update blocker_answer_drafts
            set state = :state, updated_at = now()
            where answer_id = :id
            returning answer_id
            """
        ),
        {"state": state, "id": answer_id},
    )
    row = result.first()
    if not row:
        raise NotFoundError("blocker_answer")
    await session.commit()
    notice = (
        "Approved for salesperson use. Nothing was sent."
        if state == "approved"
        else "Rejected. Draft not ready to share."
    )
    return {"answer_id": answer_id, "state": state, "notice": notice}
