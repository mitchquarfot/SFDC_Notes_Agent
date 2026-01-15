from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

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

        conn_kwargs: dict[str, Any] = {
            "account": os.getenv("SNOWFLAKE_ACCOUNT"),
            "user": os.getenv("SNOWFLAKE_USER"),
            "role": os.getenv("SNOWFLAKE_ROLE") or None,
            "warehouse": os.getenv("SNOWFLAKE_WAREHOUSE") or None,
            "database": os.getenv("SNOWFLAKE_DATABASE") or None,
            "schema": os.getenv("SNOWFLAKE_SCHEMA") or None,
        }

        auth_method = (os.getenv("SNOWFLAKE_AUTH_METHOD") or "keypair").strip().lower()
        if auth_method in {"keypair", "key_pair", "rsa"}:
            private_key_path = (os.getenv("SNOWFLAKE_PRIVATE_KEY_PATH") or "").strip()
            if not private_key_path:
                raise ValueError("SNOWFLAKE_PRIVATE_KEY_PATH is required for SNOWFLAKE_AUTH_METHOD=keypair")
            passphrase = (os.getenv("SNOWFLAKE_PRIVATE_KEY_PASSPHRASE") or "").strip() or None
            conn_kwargs["private_key"] = _load_private_key_der(private_key_path, passphrase)
        else:
            conn_kwargs["password"] = os.getenv("SNOWFLAKE_PASSWORD")

        self._conn = snowflake.connector.connect(**conn_kwargs)

    def summarize(self, transcript: TranscriptInput) -> OpportunityNotes:
        prompt = build_notes_prompt(transcript)

        sql = "SELECT SNOWFLAKE.CORTEX.COMPLETE(%s, %s) AS RESPONSE"

        with self._conn.cursor() as cur:
            cur.execute(sql, (self.model, prompt))
            row = cur.fetchone()

        if not row or row[0] is None:
            raise RuntimeError("Cortex returned empty response.")

        content = row[0]
        obj = _parse_cortex_json(content)
        notes = opportunity_notes_from_dict(obj)
        notes.model_name = f"cortex:{self.model}"
        return notes


def _parse_cortex_json(content: Any) -> dict[str, Any]:
    """
    Cortex sometimes returns:
    - JSON string
    - JSON-with-preamble text ("Sure, here's the JSON: {...}")
    - empty string on transient failures
    """
    if isinstance(content, dict):
        return content
    if content is None:
        raise RuntimeError("Cortex returned null response.")
    if not isinstance(content, str):
        raise RuntimeError(f"Cortex returned unexpected type: {type(content).__name__}")

    text = content.strip()
    if not text:
        raise RuntimeError("Cortex returned empty string response.")

    try:
        obj = json.loads(text)
        if isinstance(obj, dict):
            return obj
        raise RuntimeError(f"Cortex JSON was not an object (got {type(obj).__name__}).")
    except json.JSONDecodeError:
        pass

    # Try to extract the first top-level JSON object from the response
    start = text.find("{")
    end = text.rfind("}")
    if start != -1 and end != -1 and end > start:
        candidate = text[start : end + 1]
        try:
            obj = json.loads(candidate)
            if isinstance(obj, dict):
                return obj
        except json.JSONDecodeError:
            pass

    snippet = text[:400].replace("\n", "\\n")
    raise RuntimeError(f"Could not parse Cortex response as JSON. First 400 chars: {snippet}")


def _load_private_key_der(private_key_path: str, passphrase: str | None) -> bytes:
    """
    Snowflake connector expects a DER-encoded PKCS8 private key in bytes via `private_key=...`.
    """
    from cryptography.hazmat.primitives.serialization import Encoding, NoEncryption, PrivateFormat, load_pem_private_key

    pem_bytes = Path(private_key_path).expanduser().read_bytes()
    pw: bytes | None = None
    if passphrase is not None:
        p = passphrase.strip()
        pw = p.encode("utf-8") if p else None

    try:
        key = load_pem_private_key(pem_bytes, password=pw)
    except TypeError as e:
        # Common case: user set a passphrase but the key is actually unencrypted.
        msg = str(e).lower()
        if pw is not None and ("not encrypted" in msg or "private key is not encrypted" in msg):
            key = load_pem_private_key(pem_bytes, password=None)
        else:
            raise
    return key.private_bytes(encoding=Encoding.DER, format=PrivateFormat.PKCS8, encryption_algorithm=NoEncryption())

