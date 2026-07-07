from __future__ import annotations
from typing import TypedDict, List, Optional, Any


class ContractReviewState(TypedDict, total=False):
    # ---- input ----
    raw_text: str
    doc_id: str

    # ---- ingest / chunk ----
    chunks: List[str]

    # ---- classify ----
    doc_type: str
    doc_type_confident: bool

    # ---- extract_clauses ----
    parties: List[dict]
    clauses: List[dict]

    # ---- risk_analysis ----
    risks: List[dict]
    missing_standard_clauses: List[str]

    # ---- obligations ----
    obligations_summary: List[dict]

    # ---- verification / QA ----
    dropped_clauses: List[dict]
    dropped_risks: List[dict]

    # ---- final ----
    executive_summary: str
    final_report: dict

    # ---- error tracking ----
    errors: List[str]
