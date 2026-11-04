"""Local meeting file storage (MVP stand-in for Supabase Storage)."""

from __future__ import annotations

import hashlib
import re
import uuid
from pathlib import Path

# backend/data/uploads/meetings/...
_ROOT = Path(__file__).resolve().parents[2] / "data" / "uploads" / "meetings"


def ensure_root() -> Path:
    _ROOT.mkdir(parents=True, exist_ok=True)
    return _ROOT


def content_hash(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def save_meeting_file(
    *,
    account_id: str | None,
    filename: str,
    data: bytes,
) -> dict[str, str]:
    ensure_root()
    safe_account = re.sub(r"[^A-Za-z0-9_-]", "_", account_id or "unassigned")
    stem = Path(filename).stem
    safe_stem = re.sub(r"[^A-Za-z0-9._-]", "_", stem)[:80] or "meeting"
    ext = Path(filename).suffix.lower().lstrip(".") or "bin"
    meeting_id = f"mtg-{uuid.uuid4().hex[:12]}"
    rel = f"{safe_account}/{meeting_id}_{safe_stem}.{ext}"
    path = _ROOT / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(data)
    return {
        "meeting_id": meeting_id,
        "storage_path": f"meetings/{rel}".replace("\\", "/"),
        "absolute_path": str(path),
        "content_hash": content_hash(data),
        "uploaded_file_name": filename,
        "uploaded_file_type": ext,
    }
