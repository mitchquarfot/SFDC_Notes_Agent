from __future__ import annotations

import json
import os
from typing import Any

import requests

from app.core.models import OpportunityNotes, TranscriptInput
from app.core.models import opportunity_notes_from_dict
from app.core.prompts import build_notes_prompt
from app.core.summarizers.base import Summarizer


class OpenAISummarizer(Summarizer):
    """
    Minimal OpenAI Chat Completions call via HTTP (no openai SDK).
    Expects strict JSON output (enforced by our prompt + response_format when available).
    """

    def __init__(self) -> None:
        self.api_key = os.getenv("OPENAI_API_KEY", "").strip()
        self.model = os.getenv("OPENAI_MODEL", "gpt-4o-mini").strip()
        self.base_url = os.getenv("OPENAI_BASE_URL", "https://api.openai.com").strip().rstrip("/")

        if not self.api_key:
            raise ValueError("OPENAI_API_KEY is required for LLM_BACKEND=openai")

    def summarize(self, transcript: TranscriptInput) -> OpportunityNotes:
        prompt = build_notes_prompt(transcript)

        url = f"{self.base_url}/v1/chat/completions"
        headers = {"Authorization": f"Bearer {self.api_key}", "Content-Type": "application/json"}

        payload: dict[str, Any] = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": "You output strict JSON only."},
                {"role": "user", "content": prompt},
            ],
            # If the model supports it, this improves JSON reliability:
            "response_format": {"type": "json_object"},
            "temperature": 0.2,
        }

        resp = requests.post(url, headers=headers, json=payload, timeout=120)
        resp.raise_for_status()
        data = resp.json()
        content = data["choices"][0]["message"]["content"]

        obj = json.loads(content)
        notes = opportunity_notes_from_dict(obj)
        notes.model_name = self.model
        return notes

