from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import date
from typing import Any, Literal, Optional, cast


SourceType = Literal["gong", "zoom", "other"]
ConfidenceType = Literal["low", "medium", "high"]


@dataclass
class TranscriptMetadata:
    opportunity_name: str = ""
    account_name: str = ""
    opportunity_id: str = ""
    call_date: Optional[date] = None
    source: SourceType = "other"
    owner: str = ""
    stage: str = ""


@dataclass
class TranscriptInput:
    filename: str
    raw_text: str
    cleaned_text: str
    metadata: TranscriptMetadata = field(default_factory=TranscriptMetadata)


@dataclass
class OpportunityNotes:
    opportunity_name: str = ""
    account_name: str = ""
    opportunity_id: str = ""

    executive_summary: str = ""
    opportunity_comments: str = ""
    customer_pain: list[str] = field(default_factory=list)
    use_cases: list[str] = field(default_factory=list)
    stakeholders: list[str] = field(default_factory=list)
    competitors_or_alternatives: list[str] = field(default_factory=list)
    products_or_features_discussed: list[str] = field(default_factory=list)
    risks_or_blockers: list[str] = field(default_factory=list)
    next_steps: list[str] = field(default_factory=list)
    open_questions: list[str] = field(default_factory=list)

    confidence: ConfidenceType = "medium"
    tags: list[str] = field(default_factory=list)

    model_name: str = ""
    debug: dict[str, Any] = field(default_factory=dict)


@dataclass
class RunResult:
    run_id: str
    created_at_iso: str
    notes: list[OpportunityNotes]


def run_result_to_dict(result: RunResult) -> dict[str, Any]:
    d = asdict(result)
    # dates are stored in metadata only; still keep this generic for future.
    return d


def opportunity_notes_from_dict(obj: dict[str, Any]) -> OpportunityNotes:
    """
    Minimal schema validation/coercion for LLM JSON outputs.
    """
    def _str(v: Any) -> str:
        return "" if v is None else str(v)

    def _str_list(v: Any) -> list[str]:
        if v is None:
            return []
        if isinstance(v, list):
            return [str(x) for x in v if x is not None and str(x).strip()]
        # allow newline-separated fallback
        if isinstance(v, str):
            parts = [p.strip("-• \t") for p in v.splitlines()]
            return [p for p in parts if p]
        return [str(v)]

    conf = _str(obj.get("confidence", "medium")).lower()
    if conf not in {"low", "medium", "high"}:
        conf = "medium"

    return OpportunityNotes(
        opportunity_name=_str(obj.get("opportunity_name", "")),
        account_name=_str(obj.get("account_name", "")),
        opportunity_id=_str(obj.get("opportunity_id", "")),
        executive_summary=_str(obj.get("executive_summary", "")),
        opportunity_comments=_str(obj.get("opportunity_comments", "")),
        customer_pain=_str_list(obj.get("customer_pain")),
        use_cases=_str_list(obj.get("use_cases")),
        stakeholders=_str_list(obj.get("stakeholders")),
        competitors_or_alternatives=_str_list(obj.get("competitors_or_alternatives")),
        products_or_features_discussed=_str_list(obj.get("products_or_features_discussed")),
        risks_or_blockers=_str_list(obj.get("risks_or_blockers")),
        next_steps=_str_list(obj.get("next_steps")),
        open_questions=_str_list(obj.get("open_questions")),
        confidence=cast(ConfidenceType, conf),
        tags=_str_list(obj.get("tags")),
        model_name=_str(obj.get("model_name", "")),
        debug=obj.get("debug") if isinstance(obj.get("debug"), dict) else {},
    )

