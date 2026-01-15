from __future__ import annotations

import re

from app.core.models import OpportunityNotes, TranscriptInput
from app.core.summarizers.base import Summarizer


def _today_stamp() -> str:
    from datetime import datetime

    return datetime.now().strftime("%Y.%m.%d")


def _first_sentences(text: str, max_chars: int = 260) -> str:
    t = re.sub(r"\s+", " ", text).strip()
    if not t:
        return ""
    # naive sentence split
    parts = re.split(r"(?<=[.!?])\s+", t)
    out = ""
    for p in parts[:3]:
        if not p:
            continue
        candidate = (out + " " + p).strip()
        if len(candidate) > max_chars and out:
            break
        out = candidate
        if len(out) >= max_chars:
            break
    return out[:max_chars].strip()


def _extract_lines_matching(text: str, patterns: list[str], limit: int = 6) -> list[str]:
    lines = [l.strip("-• \t") for l in text.splitlines()]
    hits: list[str] = []
    for line in lines:
        if len(line) < 5:
            continue
        low = line.lower()
        if any(re.search(p, low) for p in patterns):
            clipped = re.sub(r"\s+", " ", line).strip()
            if clipped and clipped not in hits:
                hits.append(clipped[:140])
        if len(hits) >= limit:
            break
    return hits


class MockSummarizer(Summarizer):
    """
    No-LLM fallback. Produces a structured placeholder so you can validate the UI and flow.
    """

    def summarize(self, transcript: TranscriptInput) -> OpportunityNotes:
        md = transcript.metadata
        text = transcript.cleaned_text

        next_steps = _extract_lines_matching(
            text,
            patterns=[r"\bnext step\b", r"\bnext steps\b", r"\baction item\b", r"\bfollow[- ]?up\b", r"\bwe will\b"],
            limit=6,
        )
        open_qs = _extract_lines_matching(text, patterns=[r"\bquestion\b", r"\bopen question\b", r"\bunknown\b"], limit=5)

        summary = _first_sentences(text) or "Transcript uploaded. Enable an LLM backend for real summarization."

        initials = (md.owner or "SE").strip()
        initials = initials.split()[0][:3].upper() if initials else "SE"
        opp_comments = "\n".join(
            [
                f"{initials} - {_today_stamp()}",
                "* Enable an LLM backend (Cortex/OpenAI) for real summaries",
                "* Review transcript and confirm next steps & risks",
            ]
        )

        return OpportunityNotes(
            opportunity_name=md.opportunity_name,
            account_name=md.account_name,
            opportunity_id=md.opportunity_id,
            executive_summary=summary,
            opportunity_comments=opp_comments,
            next_steps=next_steps,
            open_questions=open_qs,
            confidence="low" if "enable an llm" in summary.lower() else "medium",
            model_name=self.name,
            debug={"source": "mock"},
        )

