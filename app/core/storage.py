from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from pathlib import Path

from app.core.models import RunResult, run_result_to_dict


def _root_dir() -> Path:
    # repo root = .../SFDC_Notes_Agent
    return Path(__file__).resolve().parents[2]


def data_dir() -> Path:
    d = _root_dir() / "data"
    d.mkdir(parents=True, exist_ok=True)
    return d


def outputs_dir() -> Path:
    d = _root_dir() / "outputs"
    d.mkdir(parents=True, exist_ok=True)
    return d


def new_run_id() -> str:
    ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    rand = os.urandom(3).hex()
    return f"run_{ts}_{rand}"


def save_run(result: RunResult) -> Path:
    path = data_dir() / f"{result.run_id}.json"
    path.write_text(json.dumps(run_result_to_dict(result), indent=2, ensure_ascii=False), encoding="utf-8")
    return path

