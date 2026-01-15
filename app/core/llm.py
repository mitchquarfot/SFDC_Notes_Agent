from __future__ import annotations

import os

from app.core.summarizers.base import Summarizer
from app.core.summarizers.mock import MockSummarizer


def get_summarizer() -> Summarizer:
    backend = (os.getenv("LLM_BACKEND", "mock") or "mock").strip().lower()

    if backend == "mock":
        return MockSummarizer()

    if backend == "openai":
        from app.core.summarizers.openai_backend import OpenAISummarizer

        return OpenAISummarizer()

    if backend in {"snowflake_cortex", "cortex", "snowflake"}:
        from app.core.summarizers.snowflake_cortex import SnowflakeCortexSummarizer

        return SnowflakeCortexSummarizer()

    raise ValueError(f"Unknown LLM_BACKEND: {backend}")

