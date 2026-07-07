"""
Each function is one LangGraph node. They all take the full state dict
and return a partial dict of updates (standard LangGraph pattern).

Graph shape:
  ingest -> classify -> extract_clauses -> verify_clauses ->
  risk_analysis -> obligations -> summarize -> format_output
"""

from __future__ import annotations
import json
import re
from typing import List

from langsmith import traceable

from .schemas import (
    ContractType,
    ClauseExtractionResult,
    RiskAnalysisResult,
    ObligationsResult,
    FinalReport,
)
from .prompts import (
    SYSTEM_BASE,
    CLASSIFY_PROMPT,
    EXTRACT_CLAUSES_PROMPT,
    RISK_ANALYSIS_PROMPT,
    OBLIGATIONS_PROMPT,
    EXEC_SUMMARY_PROMPT,
)
from .llm import get_llm, call_structured, call_plain_text
from .verify import filter_unverified_clauses, filter_unverified_risks
from .state import ContractReviewState


# ---------------------------------------------------------------------------
# 1. Ingest / chunk
# ---------------------------------------------------------------------------

SECTION_HEADER_RE = re.compile(
    r"^\s*(?:ARTICLE|Article|SECTION|Section)?\s*\d+[.)]\s+.+$", re.MULTILINE
)


@traceable(name="ingest_and_chunk")
def ingest_node(state: ContractReviewState) -> dict:
    """
    Splits the contract by section/clause headers rather than fixed token
    windows, so a single clause never gets cut in half across chunks.
    Falls back to paragraph splitting if no headers are detected.
    """
    text = state["raw_text"]
    headers = list(SECTION_HEADER_RE.finditer(text))

    if len(headers) >= 2:
        chunks = []
        for i, h in enumerate(headers):
            start = h.start()
            end = headers[i + 1].start() if i + 1 < len(headers) else len(text)
            chunks.append(text[start:end].strip())
    else:
        # fallback: split on double newlines (paragraphs)
        chunks = [p.strip() for p in text.split("\n\n") if p.strip()]

    return {"chunks": chunks}


# ---------------------------------------------------------------------------
# 2. Classify doc type (cheap model)
# ---------------------------------------------------------------------------

@traceable(name="classify_doc_type")
def classify_node(state: ContractReviewState) -> dict:
    llm = get_llm(size="small")
    # Use only the first ~3000 chars for classification - it's usually enough
    # and keeps the cheap model fast.
    preview = state["raw_text"][:3000]
    prompt = CLASSIFY_PROMPT.format(system=SYSTEM_BASE, text=preview)
    result = call_structured(llm, prompt, ContractType)
    return {
        "doc_type": result.contract_type,
        "doc_type_confident": result.is_confident,
    }


# ---------------------------------------------------------------------------
# 3. Extract clauses (large model, per chunk then merged)
# ---------------------------------------------------------------------------

@traceable(name="extract_clauses")
def extract_clauses_node(state: ContractReviewState) -> dict:
    llm = get_llm(size="large")
    chunks = state["chunks"]
    doc_type = state.get("doc_type", "Unknown")

    # For short contracts, one pass is enough. For long ones, run per-chunk
    # and merge, since smaller Groq context windows can choke on very long
    # documents and start dropping earlier clauses.
    full_text = state["raw_text"]
    CHAR_LIMIT_FOR_SINGLE_PASS = 12000

    all_parties = []
    all_clauses = {}  # keyed by clause type to dedupe/merge across chunks

    if len(full_text) <= CHAR_LIMIT_FOR_SINGLE_PASS:
        text_batches = [full_text]
    else:
        # group chunks into batches under the char limit
        text_batches, current, cur_len = [], [], 0
        for c in chunks:
            if cur_len + len(c) > CHAR_LIMIT_FOR_SINGLE_PASS and current:
                text_batches.append("\n\n".join(current))
                current, cur_len = [], 0
            current.append(c)
            cur_len += len(c)
        if current:
            text_batches.append("\n\n".join(current))

    for batch in text_batches:
        prompt = EXTRACT_CLAUSES_PROMPT.format(
            system=SYSTEM_BASE, doc_type=doc_type, text=batch
        )
        result: ClauseExtractionResult = call_structured(
            llm, prompt, ClauseExtractionResult
        )

        for p in result.parties:
            if p.model_dump() not in all_parties:
                all_parties.append(p.model_dump())

        for c in result.clauses:
            key = c.type
            # keep the version with a present=True and higher confidence
            if key not in all_clauses or (
                c.present and not all_clauses[key]["present"]
            ):
                all_clauses[key] = c.model_dump()

    return {
        "parties": all_parties,
        "clauses": list(all_clauses.values()),
    }


# ---------------------------------------------------------------------------
# 4. Verify extracted clauses against source (hallucination check)
# ---------------------------------------------------------------------------

@traceable(name="verify_clauses")
def verify_clauses_node(state: ContractReviewState) -> dict:
    from .schemas import Clause

    clause_objs = [Clause.model_validate(c) for c in state["clauses"]]
    verified, dropped = filter_unverified_clauses(state["raw_text"], clause_objs)
    return {
        "clauses": [c.model_dump() for c in verified],
        "dropped_clauses": [c.model_dump() for c in dropped],
    }


# ---------------------------------------------------------------------------
# 5. Risk analysis (large model)
# ---------------------------------------------------------------------------

@traceable(name="risk_analysis")
def risk_analysis_node(state: ContractReviewState) -> dict:
    llm = get_llm(size="large")
    clauses_json = json.dumps(state["clauses"], indent=2)
    prompt = RISK_ANALYSIS_PROMPT.format(system=SYSTEM_BASE, clauses_json=clauses_json)
    result: RiskAnalysisResult = call_structured(llm, prompt, RiskAnalysisResult)

    verified_risks, dropped_risks = filter_unverified_risks(
        state["raw_text"], result.risks
    )

    return {
        "risks": [r.model_dump() for r in verified_risks],
        "dropped_risks": [r.model_dump() for r in dropped_risks],
        "missing_standard_clauses": result.missing_standard_clauses,
    }


# ---------------------------------------------------------------------------
# 6. Obligations summary (large model)
# ---------------------------------------------------------------------------

@traceable(name="obligations_summary")
def obligations_node(state: ContractReviewState) -> dict:
    llm = get_llm(size="large")
    payload = {"parties": state["parties"], "clauses": state["clauses"]}
    prompt = OBLIGATIONS_PROMPT.format(
        system=SYSTEM_BASE, clauses_json=json.dumps(payload, indent=2)
    )
    result: ObligationsResult = call_structured(llm, prompt, ObligationsResult)
    return {"obligations_summary": [o.model_dump() for o in result.obligations_summary]}


# ---------------------------------------------------------------------------
# 7. Executive summary (plain text, large model)
# ---------------------------------------------------------------------------

@traceable(name="executive_summary")
def summarize_node(state: ContractReviewState) -> dict:
    llm = get_llm(size="large", temperature=0.2)
    partial_report = {
        "contract_type": state.get("doc_type"),
        "parties": state.get("parties"),
        "clauses": state.get("clauses"),
        "risks": state.get("risks"),
        "missing_standard_clauses": state.get("missing_standard_clauses"),
    }
    prompt = EXEC_SUMMARY_PROMPT.format(
        system=SYSTEM_BASE, report_json=json.dumps(partial_report, indent=2)
    )
    summary = call_plain_text(llm, prompt)
    return {"executive_summary": summary}


# ---------------------------------------------------------------------------
# 8. Format final output
# ---------------------------------------------------------------------------

@traceable(name="format_output")
def format_output_node(state: ContractReviewState) -> dict:
    report = FinalReport(
        contract_type=state.get("doc_type", "Unknown"),
        parties=state.get("parties", []),
        clauses=state.get("clauses", []),
        risks=state.get("risks", []),
        obligations_summary=state.get("obligations_summary", []),
        missing_standard_clauses=state.get("missing_standard_clauses", []),
        executive_summary=state.get("executive_summary", ""),
    )
    return {"final_report": report.model_dump()}
