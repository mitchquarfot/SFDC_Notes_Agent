from __future__ import annotations

import json
import os

import snowflake.connector

from app.core.models import OpportunityNotes, TranscriptInput, opportunity_notes_from_dict
from app.core.prompts import build_notes_prompt
from app.core.summarizers.base import Summarizer


class SnowflakeCortexSummarizer(Summarizer):
    """
    Uses Snowflake Cortex via SQL.

    Note: Cortex function signatures can vary by account features.
    This implementation uses a common pattern:
      SELECT SNOWFLAKE.CORTEX.COMPLETE(<model>, <prompt>) AS RESPONSE;
    """

    def __init__(self) -> None:
        self.model = os.getenv("SNOWFLAKE_CORTEX_MODEL", "llama3.1-70b").strip()

        self._conn = snowflake.connector.connect(
            account=os.getenv("SNOWFLAKE_ACCOUNT"),
            user=os.getenv("SNOWFLAKE_USER"),
            password=os.getenv("SNOWFLAKE_PASSWORD"),
            role=os.getenv("SNOWFLAKE_ROLE") or None,
            warehouse=os.getenv("SNOWFLAKE_WAREHOUSE") or None,
            database=os.getenv("SNOWFLAKE_DATABASE") or None,
            schema=os.getenv("SNOWFLAKE_SCHEMA") or None,
        )

    def summarize(self, transcript: TranscriptInput) -> OpportunityNotes:
        prompt = build_notes_prompt(transcript)

        sql = "SELECT SNOWFLAKE.CORTEX.COMPLETE(%s, %s) AS RESPONSE"

        with self._conn.cursor() as cur:
            cur.execute(sql, (self.model, prompt))
            row = cur.fetchone()

        if not row or row[0] is None:
            raise RuntimeError("Cortex returned empty response.")

        content = row[0]
        obj = json.loads(content)
        notes = opportunity_notes_from_dict(obj)
        notes.model_name = f"cortex:{self.model}"
        return notes

