from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Optional

from app.core.models import OpportunityNotes


@dataclass(frozen=True)
class PushConfig:
    login_url: str
    username: str
    password: str
    security_token: str

    solution_assessment_object: str
    solution_assessment_opportunity_lookup_field: str
    solution_assessment_opportunity_comments_field: str

    append_mode: bool = True


@dataclass(frozen=True)
class PushOutcome:
    opportunity_name: str
    account_name: str
    status: str  # updated | skipped | error
    detail: str
    opportunity_id: Optional[str] = None
    solution_assessment_id: Optional[str] = None


def push_solution_assessment_opportunity_comments(
    *,
    notes: list[OpportunityNotes],
    config: PushConfig,
) -> list[PushOutcome]:
    """
    For each note:
      1) Find Opportunity by Name (+ optional Account Name)
      2) Find related Solution Assessment record via lookup field
      3) Append (or overwrite) the Opportunity Comments field
    """
    sf = _login(
        login_url=config.login_url,
        username=config.username,
        password=config.password,
        security_token=config.security_token,
    )

    outcomes: list[PushOutcome] = []
    for n in notes:
        try:
            if not n.opportunity_name and not n.opportunity_id:
                outcomes.append(
                    PushOutcome(
                        opportunity_name=n.opportunity_name,
                        account_name=n.account_name,
                        status="skipped",
                        detail="Missing opportunity_name and opportunity_id (cannot lookup Opportunity).",
                    )
                )
                continue

            opp = _find_opportunity(
                sf,
                opportunity_id=n.opportunity_id or None,
                opportunity_name=n.opportunity_name,
                account_name=n.account_name or None,
            )
            if opp is None:
                outcomes.append(
                    PushOutcome(
                        opportunity_name=n.opportunity_name,
                        account_name=n.account_name,
                        status="skipped",
                        detail="Opportunity not found or ambiguous (multiple matches). Provide OpportunityId for exact matching.",
                    )
                )
                continue

            sa = _find_latest_solution_assessment(
                sf,
                object_api_name=config.solution_assessment_object,
                opportunity_lookup_field=config.solution_assessment_opportunity_lookup_field,
                opportunity_id=opp["Id"],
                comments_field=config.solution_assessment_opportunity_comments_field,
            )
            if sa is None:
                outcomes.append(
                    PushOutcome(
                        opportunity_name=n.opportunity_name,
                        account_name=n.account_name,
                        status="skipped",
                        detail="No Solution Assessment record found for Opportunity.",
                        opportunity_id=opp["Id"],
                    )
                )
                continue

            old_val = sa.get(config.solution_assessment_opportunity_comments_field) or ""
            new_val = _merge_comments(old_val, n.opportunity_comments, append=config.append_mode)

            _update_record_field(
                sf,
                object_api_name=config.solution_assessment_object,
                record_id=sa["Id"],
                field_api_name=config.solution_assessment_opportunity_comments_field,
                value=new_val,
            )

            outcomes.append(
                PushOutcome(
                    opportunity_name=n.opportunity_name,
                    account_name=n.account_name,
                    status="updated",
                    detail="Updated Solution Assessment Opportunity Comments.",
                    opportunity_id=opp["Id"],
                    solution_assessment_id=sa["Id"],
                )
            )
        except Exception as e:  # noqa: BLE001
            outcomes.append(
                PushOutcome(
                    opportunity_name=n.opportunity_name,
                    account_name=n.account_name,
                    status="error",
                    detail=str(e),
                )
            )

    return outcomes


def _merge_comments(existing: str, new_block: str, *, append: bool) -> str:
    existing = (existing or "").strip()
    new_block = (new_block or "").strip()
    if not new_block:
        return existing
    if not existing:
        return new_block
    if not append:
        return new_block
    # Prepend newest entry to the top with a blank line separation
    return f"{new_block}\n\n{existing}"


def _find_opportunity(
    sf,
    *,
    opportunity_id: Optional[str],
    opportunity_name: str,
    account_name: Optional[str],
) -> Optional[dict[str, Any]]:
    if opportunity_id:
        opp_id = opportunity_id.strip()
        if opp_id:
            res = sf.query(f"SELECT Id, Name, Account.Name FROM Opportunity WHERE Id = {_soql_quote(opp_id)} LIMIT 1")
            records = res.get("records", [])
            return records[0] if records else None
    if not opportunity_name:
        return None
    return _find_single_opportunity(sf, opportunity_name=opportunity_name, account_name=account_name)


def _find_single_opportunity(sf, *, opportunity_name: str, account_name: Optional[str]) -> Optional[dict[str, Any]]:
    where = f"Name = {_soql_quote(opportunity_name)}"
    if account_name:
        where += f" AND Account.Name = {_soql_quote(account_name)}"
    soql = f"SELECT Id, Name, Account.Name FROM Opportunity WHERE {where} ORDER BY LastModifiedDate DESC LIMIT 5"
    res = sf.query(soql)
    records = res.get("records", [])
    if len(records) != 1:
        return None
    return records[0]


def _find_latest_solution_assessment(
    sf,
    *,
    object_api_name: str,
    opportunity_lookup_field: str,
    opportunity_id: str,
    comments_field: str,
) -> Optional[dict[str, Any]]:
    soql = (
        f"SELECT Id, {comments_field} "
        f"FROM {object_api_name} "
        f"WHERE {opportunity_lookup_field} = {_soql_quote(opportunity_id)} "
        f"ORDER BY LastModifiedDate DESC "
        f"LIMIT 1"
    )
    res = sf.query(soql)
    records = res.get("records", [])
    if not records:
        return None
    return records[0]


def _update_record_field(sf, *, object_api_name: str, record_id: str, field_api_name: str, value: str) -> None:
    obj = getattr(sf, object_api_name)
    obj.update(record_id, {field_api_name: value})


def _login(*, login_url: str, username: str, password: str, security_token: str):
    from simple_salesforce import Salesforce  # lazy import

    domain = _domain_from_login_url(login_url)
    return Salesforce(username=username, password=password, security_token=security_token, domain=domain)


def _domain_from_login_url(login_url: str) -> str:
    if "test.salesforce.com" in (login_url or ""):
        return "test"
    return "login"


def _soql_quote(value: str) -> str:
    # Very small helper to make SOQL string literals safer.
    v = (value or "").replace("\\", "\\\\").replace("'", "\\'")
    return f"'{v}'"

