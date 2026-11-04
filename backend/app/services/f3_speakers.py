"""Label meeting transcript turns by speaker (Person N or real first names)."""

from __future__ import annotations

import re
from typing import Any

from app.ai.azure_openai import AzureChatClient
from app.core.errors import AppError

MAX_CHARS = 100_000
CHUNK_CHARS = 2200

STOP_NAMES = {
    "i",
    "we",
    "you",
    "he",
    "she",
    "they",
    "the",
    "a",
    "an",
    "and",
    "or",
    "but",
    "so",
    "if",
    "thanks",
    "thank",
    "hello",
    "hi",
    "good",
    "afternoon",
    "morning",
    "everyone",
    "today",
    "also",
    "yes",
    "okay",
    "ok",
    "well",
    "please",
    "university",
    "state",
    "solutions",
    "market",
    "canvas",
    "option",
}


class ValidationAppError(AppError):
    status_code = 422
    code = "VALIDATION_ERROR"
    message = "The request is not valid."


def _title_case(name: str) -> str:
    return " ".join(
        part[:1].upper() + part[1:].lower() if part else ""
        for part in name.strip().split()
    )


def _is_generic(name: str) -> bool:
    return bool(re.match(r"^person\s*\d+$", name.strip(), flags=re.I))


def _push_unique(names: list[str], name: str) -> None:
    clean = _title_case(re.sub(r"[^A-Za-z\-']", " ", name).strip())
    if not clean or len(clean) < 2 or len(clean) > 30:
        return
    if clean.lower() in STOP_NAMES or _is_generic(clean):
        return
    first = clean.split()[0]
    if not re.match(r"^[A-Z][a-zA-Z'\-]+$", first):
        return
    if any(item.lower() == clean.lower() for item in names):
        return
    names.append(clean)


def detect_candidate_names(transcript: str, known_speakers: list[str] | None = None) -> list[str]:
    found: list[str] = []
    for known in known_speakers or []:
        _push_unique(found, known)

    patterns = [
        re.compile(r"\bI am ([A-Z][a-zA-Z'\-]{1,20})\b"),
        re.compile(r"\bI'm ([A-Z][a-zA-Z'\-]{1,20})\b"),
        re.compile(r"\bmy name is ([A-Z][a-zA-Z'\-]{1,20})\b", re.I),
        re.compile(
            r"\b(?:thank you|thanks)\s+([A-Z][a-zA-Z'\-]{1,20})"
            r"(?:\s*,\s*([A-Z][a-zA-Z'\-]{1,20}))?"
            r"(?:\s*,?\s*and\s+([A-Z][a-zA-Z'\-]{1,20}))?",
            re.I,
        ),
        re.compile(
            r"\b(?:hi|hello)\s+(?:everyone[, ]+)?(?:I am|I'm)\s+([A-Z][a-zA-Z'\-]{1,20})\b",
            re.I,
        ),
        re.compile(r"(?:^|[.!?]\s+)([A-Z][a-zA-Z'\-]{1,20})\.\s+[A-Z]"),
    ]
    for pattern in patterns:
        for match in pattern.finditer(transcript):
            for group in match.groups():
                if group:
                    _push_unique(found, group)
    return found


def _turns_to_text(turns: list[dict[str, str]]) -> str:
    parts: list[str] = []
    for index, turn in enumerate(turns):
        text = (turn.get("text") or "").strip()
        if not text:
            continue
        speaker = (turn.get("speaker") or "").strip() or f"Person {index + 1}"
        parts.append(f"{speaker}:\n{text}")
    return "\n\n".join(parts)


def _unique_speakers(turns: list[dict[str, str]]) -> list[str]:
    out: list[str] = []
    for turn in turns:
        speaker = (turn.get("speaker") or "").strip()
        if speaker and not any(item.lower() == speaker.lower() for item in out):
            out.append(speaker)
    return out


def _normalize_turns(raw: Any) -> list[dict[str, str]]:
    if not isinstance(raw, list):
        return []
    turns: list[dict[str, str]] = []
    for index, item in enumerate(raw):
        if not isinstance(item, dict):
            continue
        text = str(item.get("text") or "").strip()
        if not text:
            continue
        speaker = str(item.get("speaker") or "").strip() or f"Person {index + 1}"
        turns.append({"speaker": _title_case(speaker), "text": text})
    return turns


def _remap_generic(turns: list[dict[str, str]], named: list[str]) -> list[dict[str, str]]:
    real = [_title_case(n) for n in named if n and not _is_generic(n)]
    if not real or not turns:
        return turns
    if not all(_is_generic(t["speaker"]) for t in turns):
        return turns
    remapped: list[dict[str, str]] = []
    for turn in turns:
        match = re.match(r"^person\s*(\d+)$", turn["speaker"], flags=re.I)
        if not match:
            remapped.append(turn)
            continue
        index = int(match.group(1)) - 1
        if 0 <= index < len(real):
            remapped.append({**turn, "speaker": real[index]})
        else:
            remapped.append(turn)
    return remapped


def name_aware_split(transcript: str, candidate_names: list[str]) -> list[dict[str, str]]:
    if not candidate_names:
        return []
    escaped = "|".join(re.escape(name) for name in candidate_names)
    cue_pattern = re.compile(rf"(?:^|[.!?]\s+|\n)\s*({escaped})(?:\.|:|,)?\s+", re.I)
    cues: list[tuple[str, int, int]] = []
    for match in cue_pattern.finditer(transcript):
        raw = match.group(1)
        canonical = next(
            (n for n in candidate_names if n.lower() == raw.lower()),
            _title_case(raw),
        )
        name_offset = match.group(0).lower().rfind(raw.lower())
        absolute_start = match.start() + max(name_offset, 0)
        cues.append((canonical, absolute_start, match.end()))
    if len(cues) < 2:
        return []
    turns: list[dict[str, str]] = []
    for i, (name, _start, end) in enumerate(cues):
        text_end = cues[i + 1][1] if i + 1 < len(cues) else len(transcript)
        text = transcript[end:text_end].strip()
        if text:
            turns.append({"speaker": name, "text": text})
    return turns


def heuristic_split(transcript: str, expected_count: int = 2) -> str:
    sentences = [s.strip() for s in re.split(r"(?<=[.?!])\s+", transcript) if s.strip()]
    if not sentences:
        return f"Person 1:\n{transcript.strip()}"
    count = max(2, min(expected_count, 8))
    turns = [
        {"speaker": f"Person {(index % count) + 1}", "text": sentence}
        for index, sentence in enumerate(sentences)
    ]
    return _turns_to_text(turns)


def _chunk_transcript(text: str, max_chars: int = CHUNK_CHARS) -> list[str]:
    if len(text) <= max_chars:
        return [text]
    chunks: list[str] = []
    remaining = text
    while len(remaining) > max_chars:
        cut = remaining.rfind(". ", 0, max_chars)
        if cut < max_chars * 0.4:
            cut = max_chars
        chunks.append(remaining[: cut + 1].strip())
        remaining = remaining[cut + 1 :].strip()
    if remaining:
        chunks.append(remaining)
    return chunks


async def _llm_turns_for_chunk(
    client: AzureChatClient,
    chunk: str,
    candidates: list[str],
    known_speakers: list[str],
) -> list[dict[str, str]]:
    name_hint = (
        f"Likely participants (use these exact first names as labels when they speak): "
        f"{', '.join(candidates)}."
        if candidates
        else "Identify all distinct participants."
    )
    remembered = (
        f"Remembered session names: {', '.join(known_speakers)}."
        if known_speakers
        else ""
    )
    system = f"""You split multi-person meeting transcripts into speaker turns.
Return ONLY JSON:
{{
  "speakers": ["John", "Sophie"],
  "turns": [
    {{ "speaker": "John", "text": "..." }},
    {{ "speaker": "Sophie", "text": "..." }}
  ]
}}

Rules:
- There may be MORE THAN TWO speakers. Never collapse everyone into only Person 1 and Person 2 if more people are present.
- When a person says "I am Sophie" / "I'm John", use that real first name as the speaker label.
- If the transcript has cues like "John. Good afternoon..." treat "John" as the speaker for the following words until the next name cue.
- {name_hint}
- {remembered}
- Use real first names whenever possible.
- Only use Person 1, Person 2, Person 3... when a real name cannot be determined.
- Keep each person on one consistent label.
- Do not invent dialogue. Keep wording as close as possible to the source."""
    result = await client.chat_json(
        system=system,
        user=f"Split ALL speakers in this transcript chunk into named turns JSON:\n\n{chunk}",
        temperature=0.0,
    )
    if not result:
        return []
    turns = _normalize_turns(result.get("turns"))
    speakers = result.get("speakers")
    if isinstance(speakers, list):
        named = [str(s) for s in speakers if str(s).strip()]
        turns = _remap_generic(turns, named + candidates)
    else:
        turns = _remap_generic(turns, candidates)
    return turns


async def format_speakers(
    *,
    transcript: str,
    known_speakers: list[str] | None = None,
) -> dict[str, Any]:
    trimmed = (transcript or "").strip()
    if not trimmed:
        raise ValidationAppError("Transcript is empty.")
    if len(trimmed) > MAX_CHARS:
        raise ValidationAppError("Transcript exceeds the maximum allowed size.")

    known = [s.strip() for s in (known_speakers or []) if s and str(s).strip()]
    candidates = detect_candidate_names(trimmed, known)
    cue_turns = name_aware_split(trimmed, candidates)

    if len(cue_turns) >= 3 and len(_unique_speakers(cue_turns)) >= 2:
        return {
            "formatted": _turns_to_text(cue_turns),
            "speakers": _unique_speakers(cue_turns),
            "source": "name_cues",
            "data_label": "Fictional demo data",
        }

    client = AzureChatClient()
    all_turns: list[dict[str, str]] = []
    source = "heuristic"
    if client.configured:
        try:
            for chunk in _chunk_transcript(trimmed):
                part = await _llm_turns_for_chunk(client, chunk, candidates, known)
                all_turns.extend(part)
            if all_turns:
                source = "azure_openai"
        except Exception:
            all_turns = []

    if all_turns:
        turns = _remap_generic(all_turns, candidates)
        speakers = _unique_speakers(turns)
        generic_only = all(_is_generic(s) for s in speakers)
        if (
            (generic_only and len(speakers) <= 2 and len(candidates) >= 3)
            or (len(speakers) <= 2 and len(candidates) >= 3 and len(cue_turns) >= 3)
        ):
            named_turns = cue_turns if len(cue_turns) >= 3 else name_aware_split(trimmed, candidates)
            if named_turns:
                turns = named_turns
                speakers = _unique_speakers(named_turns)
                source = "name_cues"
            else:
                return {
                    "formatted": heuristic_split(trimmed, len(candidates) or 2),
                    "speakers": candidates,
                    "source": "heuristic",
                    "data_label": "Fictional demo data",
                }
        merged_speakers = list(
            dict.fromkeys(
                [s for s in speakers if not _is_generic(s)] + candidates
            )
        )
        return {
            "formatted": _turns_to_text(turns),
            "speakers": merged_speakers,
            "source": source,
            "data_label": "Fictional demo data",
        }

    if cue_turns:
        return {
            "formatted": _turns_to_text(cue_turns),
            "speakers": _unique_speakers(cue_turns),
            "source": "name_cues",
            "data_label": "Fictional demo data",
        }

    return {
        "formatted": heuristic_split(trimmed, max(2, len(candidates))),
        "speakers": candidates,
        "source": "heuristic",
        "data_label": "Fictional demo data",
    }
