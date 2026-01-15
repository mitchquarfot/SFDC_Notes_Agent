from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

import pandas as pd

from app.core.models import OpportunityNotes


@dataclass(frozen=True)
class ExportPaths:
    csv_path: Path


def notes_to_dataframe(notes: list[OpportunityNotes]) -> pd.DataFrame:
    rows = []
    for n in notes:
        rows.append(
            {
                "opportunity_name": n.opportunity_name,
                "account_name": n.account_name,
                "opportunity_id": n.opportunity_id,
                "executive_summary": n.executive_summary,
                "opportunity_comments": n.opportunity_comments,
                "customer_pain": "; ".join(n.customer_pain),
                "use_cases": "; ".join(n.use_cases),
                "stakeholders": "; ".join(n.stakeholders),
                "competitors_or_alternatives": "; ".join(n.competitors_or_alternatives),
                "products_or_features_discussed": "; ".join(n.products_or_features_discussed),
                "risks_or_blockers": "; ".join(n.risks_or_blockers),
                "next_steps": "; ".join(n.next_steps),
                "open_questions": "; ".join(n.open_questions),
                "confidence": n.confidence,
                "tags": "; ".join(n.tags),
                "model_name": n.model_name,
            }
        )
    return pd.DataFrame(rows)


def export_notes_csv(notes: list[OpportunityNotes], outputs_dir: Path, filename: Optional[str] = None) -> ExportPaths:
    outputs_dir.mkdir(parents=True, exist_ok=True)
    ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    fname = filename or f"sfdc_notes_{ts}.csv"
    csv_path = outputs_dir / fname
    df = notes_to_dataframe(notes)
    df.to_csv(csv_path, index=False)
    return ExportPaths(csv_path=csv_path)


def push_notes_to_salesforce(*args, **kwargs):  # pragma: no cover
    raise RuntimeError("Deprecated: use app.core.salesforce_push.push_solution_assessment_opportunity_comments")

