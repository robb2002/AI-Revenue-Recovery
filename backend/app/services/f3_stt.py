"""Speech-to-text adapter — Groq Whisper. Audio in, text out; never stores audio."""

from __future__ import annotations

import logging
from pathlib import Path

import httpx

from app.core.config import get_settings
from app.core.errors import AppError

logger = logging.getLogger("app.stt")

GROQ_TRANSCRIPTIONS_URL = "https://api.groq.com/openai/v1/audio/transcriptions"
ALLOWED_AUDIO_EXT = {"mp3", "wav", "m4a", "webm", "ogg", "mpeg", "mp4"}


class UnsupportedAudioError(AppError):
    status_code = 415
    code = "UNSUPPORTED_MEDIA"
    message = "Unsupported audio type."


class AudioTooLargeError(AppError):
    status_code = 413
    code = "TRANSCRIPT_TOO_LARGE"
    message = "Audio exceeds the maximum allowed size."


class SttUnavailableError(AppError):
    status_code = 502
    code = "STT_UNAVAILABLE"
    message = "Speech-to-text is unavailable."


class SttTimeoutError(AppError):
    status_code = 504
    code = "STT_TIMEOUT"
    message = "Speech-to-text timed out."


class SttRateLimitedError(AppError):
    status_code = 429
    code = "STT_RATE_LIMITED"
    message = "Speech-to-text rate limit reached."


def _ext(filename: str) -> str:
    return Path(filename).suffix.lower().lstrip(".")


async def transcribe_audio(*, filename: str, data: bytes) -> dict[str, str]:
    """Send one audio file to Groq Whisper and return text only."""
    settings = get_settings()
    if not settings.stt_configured:
        raise SttUnavailableError(
            "STT is not configured. Set STT_API_KEY and STT_MODEL in backend/.env."
        )

    ext = _ext(filename)
    if ext not in ALLOWED_AUDIO_EXT:
        raise UnsupportedAudioError(
            f".{ext or 'unknown'} is not supported. Use mp3, wav, or m4a."
        )

    max_bytes = max(1, settings.stt_max_audio_mb) * 1024 * 1024
    if len(data) > max_bytes:
        raise AudioTooLargeError(
            f"Audio exceeds {settings.stt_max_audio_mb} MB limit."
        )
    if not data:
        raise UnsupportedAudioError("Audio file is empty.")

    safe_name = Path(filename).name or f"audio.{ext}"
    try:
        async with httpx.AsyncClient(timeout=settings.stt_timeout_seconds) as client:
            response = await client.post(
                GROQ_TRANSCRIPTIONS_URL,
                headers={"Authorization": f"Bearer {settings.stt_api_key}"},
                data={
                    "model": settings.stt_model,
                    "response_format": "json",
                    "temperature": "0",
                },
                files={"file": (safe_name, data, f"audio/{ext}")},
            )
    except httpx.TimeoutException as exc:
        logger.warning("STT timeout (%s)", type(exc).__name__)
        raise SttTimeoutError() from exc
    except httpx.HTTPError as exc:
        logger.warning("STT transport error (%s)", type(exc).__name__)
        raise SttUnavailableError() from exc

    if response.status_code == 429:
        raise SttRateLimitedError()
    if response.status_code >= 400:
        # Never log the STT key or audio bytes.
        detail = ""
        try:
            payload = response.json()
            detail = str(payload.get("error", {}).get("message") or "")
        except Exception:
            detail = response.reason_phrase or ""
        logger.warning("STT provider error status=%s", response.status_code)
        raise SttUnavailableError(detail or "Speech-to-text failed.")

    payload = response.json()
    text = str(payload.get("text") or "").strip()
    return {
        "transcript": text,
        "source": "audio",
        "model": settings.stt_model,
        "notice": "Machine-transcribed text. Review before save. Audio was not stored.",
        "data_label": "Fictional demo data",
    }
