from __future__ import annotations

import json

from app.core.models import TranscriptInput


def build_notes_prompt(transcript: TranscriptInput) -> str:
    """
    Prompt asks for *strict JSON only* so we can validate with Pydantic and export cleanly to SFDC.
    """
    schema_hint = {
        "opportunity_name": "string",
        "account_name": "string",
        "executive_summary": "string (1-3 sentences)",
        "opportunity_comments": "string (SFDC block: 'XX - YYYY.MM.DD\\n* ...' with 2-4 concise bullets)",
        "customer_pain": ["string"],
        "use_cases": ["string"],
        "stakeholders": ["string"],
        "competitors_or_alternatives": ["string"],
        "products_or_features_discussed": ["string"],
        "risks_or_blockers": ["string"],
        "next_steps": ["string"],
        "open_questions": ["string"],
        "confidence": "low|medium|high",
        "tags": ["string"],
    }

    md = transcript.metadata
    meta_block = {
        "opportunity_name": md.opportunity_name,
        "account_name": md.account_name,
        "call_date": md.call_date.isoformat() if md.call_date else None,
        "source": md.source,
        "owner": md.owner,
        "stage": md.stage,
        "filename": transcript.filename,
    }

    return f"""You are a Snowflake Sales Engineer / Snowflake engineer writing concise Salesforce pipeline notes.

Goal: produce VERY concise, high-signal notes that help an AE/SE update the opportunity quickly.

Constraints:
- Output MUST be valid JSON (no markdown, no code fences, no commentary).
- Keep executive_summary to 1-3 sentences.
- opportunity_comments MUST be a ready-to-paste Salesforce "Opportunity Comments" entry:
  - First line: "<INITIALS> - <YYYY.MM.DD>"
  - Then 2-4 bullets, each starting with "* "
  - Bullets should focus on next steps, risks/blockers, and critical updates for leadership
  - Keep each bullet <= ~18 words
- Prefer short bullet-like strings in arrays (max ~12 words each).
- If unknown, use empty string or empty array (not null), except call_date which is already provided above.

Metadata (authoritative if filled in):
{json.dumps(meta_block, ensure_ascii=False)}

Return JSON with this shape:
{json.dumps(schema_hint, ensure_ascii=False)}

Transcript:
{transcript.cleaned_text}
"""

