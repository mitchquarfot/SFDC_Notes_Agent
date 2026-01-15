from __future__ import annotations

import os
import sys
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Optional

import streamlit as st
from dotenv import load_dotenv

# Ensure repo root is on sys.path when running `streamlit run app/main.py`
# (Streamlit sets sys.path[0] to the script directory: .../app)
_REPO_ROOT = Path(__file__).resolve().parents[1]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from app.core.llm import get_summarizer
from app.core.models import OpportunityNotes, RunResult, TranscriptInput, TranscriptMetadata
from app.core.parsing import clean_transcript_text
from app.core.salesforce_export import export_notes_csv, notes_to_dataframe
from app.core.salesforce_push import PushConfig, push_solution_assessment_opportunity_comments
from app.core.storage import new_run_id, outputs_dir, save_run


def _read_uploaded_file(f) -> str:
    b = f.read()
    try:
        return b.decode("utf-8")
    except UnicodeDecodeError:
        return b.decode("latin-1", errors="replace")


def _parse_date(d: Optional[date]) -> Optional[date]:
    return d


def main() -> None:
    load_dotenv()
    st.set_page_config(page_title="SFDC Notes Agent", layout="wide")

    st.title("SFDC Notes Agent (Local)")
    st.caption("Upload Gong/Zoom transcripts, generate concise opportunity notes, export to Salesforce-friendly CSV.")

    with st.sidebar:
        st.subheader("LLM backend")
        st.code(f"LLM_BACKEND={os.getenv('LLM_BACKEND', 'mock')}", language=None)
        st.caption("Set `.env` to `mock`, `snowflake_cortex`, or `openai`.")

    files = st.file_uploader(
        "Upload transcripts (.txt, .vtt, .srt) — you can select multiple",
        type=["txt", "vtt", "srt"],
        accept_multiple_files=True,
    )

    if not files:
        st.info("Upload one or more transcripts to get started.")
        return

    st.divider()
    st.subheader("Opportunity metadata (per transcript)")

    transcripts: list[TranscriptInput] = []
    default_initials = st.text_input(
        "Your initials for the Opportunity Comments header (e.g., MQ)",
        value=os.getenv("SFDC_INITIALS", "MQ"),
        help="Used to format: 'MQ - YYYY.MM.DD' at the top of each Opportunity Comments entry.",
    ).strip()[:4].upper()

    for idx, f in enumerate(files):
        raw = _read_uploaded_file(f)
        cleaned = clean_transcript_text(f.name, raw)

        with st.expander(f"{idx+1}. {f.name}", expanded=(idx == 0)):
            c1, c2, c3, c4, c5 = st.columns([2, 2, 1, 1, 1])
            opp = c1.text_input("Opportunity name", value=_guess_opp_from_filename(f.name), key=f"opp_{idx}")
            acct = c2.text_input("Account name", value="", key=f"acct_{idx}")
            src = c3.selectbox("Source", options=["gong", "zoom", "other"], index=2, key=f"src_{idx}")
            use_today = c4.checkbox("Use today's date", value=True, key=f"use_today_{idx}")
            call_date = date.today() if use_today else c4.date_input("Call date", value=date.today(), key=f"date_{idx}")
            opp_id = c5.text_input(
                "Opportunity ID (optional)",
                value="",
                key=f"oppid_{idx}",
                help="If provided (15/18-char Id), Salesforce push will use this for exact matching.",
            ).strip()

            c6, c7 = st.columns([1, 1])
            owner = c6.text_input("Owner (AE/SE or initials)", value=default_initials, key=f"owner_{idx}")
            stage = c7.text_input("Stage", value="", key=f"stage_{idx}")

            st.caption(f"Cleaned transcript length: {len(cleaned):,} chars")
            st.text_area("Preview (cleaned)", cleaned[:6000], height=180, key=f"preview_{idx}")

        md = TranscriptMetadata(
            opportunity_name=opp.strip(),
            account_name=acct.strip(),
            opportunity_id=opp_id,
            call_date=_parse_date(call_date),
            source=src,  # type: ignore[arg-type]
            owner=owner.strip(),
            stage=stage.strip(),
        )
        transcripts.append(TranscriptInput(filename=f.name, raw_text=raw, cleaned_text=cleaned, metadata=md))

    st.divider()
    c_run, c_opts = st.columns([1, 2])
    with c_run:
        run = st.button("Generate notes", type="primary")
    with c_opts:
        st.caption("Tip: Start with `LLM_BACKEND=mock` to validate flow, then switch to Cortex/OpenAI for real notes.")

    if not run:
        return

    summarizer = get_summarizer()
    st.info(f"Running summarizer: {summarizer.name}")

    results: list[OpportunityNotes] = []
    errors: list[str] = []

    prog = st.progress(0)
    for i, t in enumerate(transcripts):
        try:
            notes = summarizer.summarize(t)
            # Ensure metadata flows through even if model omits it
            notes.opportunity_name = notes.opportunity_name or t.metadata.opportunity_name
            notes.account_name = notes.account_name or t.metadata.account_name
            notes.opportunity_id = notes.opportunity_id or t.metadata.opportunity_id
            results.append(notes)
        except Exception as e:  # noqa: BLE001
            errors.append(f"{t.filename}: {e}")
        prog.progress((i + 1) / max(1, len(transcripts)))

    if errors:
        st.error("Some transcripts failed:")
        for e in errors:
            st.write(f"- {e}")

    if not results:
        st.warning("No notes generated.")
        return

    run_id = new_run_id()
    run_result = RunResult(
        run_id=run_id,
        created_at_iso=st.session_state.get("run_created_at_iso") or datetime.now(timezone.utc).isoformat(),
        notes=results,
    )
    save_path = save_run(run_result)

    st.success(f"Generated {len(results)} note sets. Saved run JSON to: {save_path}")

    st.subheader("Results")
    df = notes_to_dataframe(results)
    st.dataframe(df, use_container_width=True, hide_index=True)

    st.subheader("Salesforce-ready Opportunity Comments (copy/paste)")
    for i, n in enumerate(results):
        title = n.opportunity_name or n.account_name or f"Result {i+1}"
        with st.expander(title, expanded=(i == 0)):
            st.text_area("Opportunity Comments", n.opportunity_comments, height=140, key=f"opp_comments_{i}")

    exp = export_notes_csv(results, outputs_dir())
    st.download_button(
        "Download CSV",
        data=exp.csv_path.read_bytes(),
        file_name=exp.csv_path.name,
        mime="text/csv",
    )

    st.divider()
    st.subheader("Optional: Salesforce API push")
    st.caption(
        "This will try to: find Opportunity by name, then find related Solution Assessment by Opportunity lookup, "
        "then append the new entry to Solution Assessment → Opportunity Comments."
    )

    with st.expander("Salesforce settings"):
        login_url = st.text_input("Login URL", value=os.getenv("SALESFORCE_LOGIN_URL", "https://login.salesforce.com"))
        username = st.text_input("Username", value=os.getenv("SALESFORCE_USERNAME", ""))
        password = st.text_input("Password", value=os.getenv("SALESFORCE_PASSWORD", ""), type="password")
        token = st.text_input("Security token", value=os.getenv("SALESFORCE_SECURITY_TOKEN", ""), type="password")
        st.markdown("**Solution Assessment mapping**")
        sa_obj = st.text_input(
            "Solution Assessment object API name",
            value=os.getenv("SALESFORCE_SOLUTION_ASSESSMENT_OBJECT_API_NAME", ""),
            help="Often a custom object, e.g. Solution_Assessment__c (varies by org).",
        ).strip()
        sa_opp_lookup = st.text_input(
            "Solution Assessment → Opportunity lookup field API name",
            value=os.getenv("SALESFORCE_SOLUTION_ASSESSMENT_OPPORTUNITY_LOOKUP_FIELD_API_NAME", ""),
            help="Often Opportunity__c (varies by org).",
        ).strip()
        sa_comments_field = st.text_input(
            "Solution Assessment → Opportunity Comments field API name",
            value=os.getenv("SALESFORCE_SOLUTION_ASSESSMENT_OPPORTUNITY_COMMENTS_FIELD_API_NAME", ""),
            help="The API name behind the 'Opportunity Comments' field in the Solution Assessment section.",
        ).strip()
        append_mode = st.checkbox("Append new entry to top (recommended)", value=True)

    if st.button("Push Opportunity Comments to Salesforce"):
        try:
            if not sa_obj or not sa_opp_lookup or not sa_comments_field:
                st.error("Fill in Solution Assessment object + lookup field + Opportunity Comments field API names before pushing.")
                return

            cfg = PushConfig(
                login_url=login_url,
                username=username,
                password=password,
                security_token=token,
                solution_assessment_object=sa_obj,
                solution_assessment_opportunity_lookup_field=sa_opp_lookup,
                solution_assessment_opportunity_comments_field=sa_comments_field,
                append_mode=append_mode,
            )
            outcomes = push_solution_assessment_opportunity_comments(notes=results, config=cfg)
            st.dataframe(
                [
                    {
                        "opportunity_name": o.opportunity_name,
                        "account_name": o.account_name,
                        "status": o.status,
                        "detail": o.detail,
                        "opportunity_id": o.opportunity_id,
                        "solution_assessment_id": o.solution_assessment_id,
                    }
                    for o in outcomes
                ],
                use_container_width=True,
                hide_index=True,
            )
            updated = sum(1 for o in outcomes if o.status == "updated")
            skipped = sum(1 for o in outcomes if o.status == "skipped")
            errored = sum(1 for o in outcomes if o.status == "error")
            st.success(f"Push complete. Updated={updated} Skipped={skipped} Errors={errored}")
        except Exception as e:  # noqa: BLE001
            st.error(str(e))


def _guess_opp_from_filename(filename: str) -> str:
    base = filename.rsplit(".", 1)[0]
    base = base.replace("_", " ").replace("-", " ").strip()
    return base[:80]


if __name__ == "__main__":
    main()

