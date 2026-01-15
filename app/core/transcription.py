from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Literal, Optional


TranscriptionBackend = Literal["none", "openai"]


@dataclass(frozen=True)
class TranscriptionResult:
    text: str
    model: str = ""


def transcribe_audio(
    *,
    audio_bytes: bytes,
    filename: str,
    language: Optional[str] = None,
) -> TranscriptionResult:
    backend = (os.getenv("TRANSCRIPTION_BACKEND", "none") or "none").strip().lower()
    if backend == "none":
        raise RuntimeError("TRANSCRIPTION_BACKEND is 'none'. Set TRANSCRIPTION_BACKEND=openai to enable audio transcription.")
    if backend == "openai":
        return _transcribe_openai(audio_bytes=audio_bytes, filename=filename, language=language)
    raise ValueError(f"Unknown TRANSCRIPTION_BACKEND: {backend}")


def _transcribe_openai(*, audio_bytes: bytes, filename: str, language: Optional[str]) -> TranscriptionResult:
    import requests

    api_key = (os.getenv("OPENAI_API_KEY") or "").strip()
    if not api_key:
        raise RuntimeError("OPENAI_API_KEY is required for TRANSCRIPTION_BACKEND=openai")

    model = (os.getenv("OPENAI_AUDIO_MODEL") or "whisper-1").strip()
    base_url = (os.getenv("OPENAI_BASE_URL") or "https://api.openai.com").strip().rstrip("/")

    url = f"{base_url}/v1/audio/transcriptions"
    headers = {"Authorization": f"Bearer {api_key}"}

    data = {"model": model}
    if language:
        data["language"] = language

    # OpenAI expects multipart form:
    # - file: audio binary
    # - model: whisper-1
    files = {"file": (filename, audio_bytes)}

    resp = requests.post(url, headers=headers, data=data, files=files, timeout=180)
    resp.raise_for_status()
    payload = resp.json()
    text = (payload.get("text") or "").strip()
    if not text:
        raise RuntimeError("Transcription returned empty text.")
    return TranscriptionResult(text=text, model=model)

