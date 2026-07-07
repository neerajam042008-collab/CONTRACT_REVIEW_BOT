"""
Hallucination check: every quoted_text the model emits for a clause or risk
must actually appear (or closely match) somewhere in the source contract.
We use fuzzy matching to tolerate whitespace/OCR noise from PDF extraction,
but reject anything below the threshold — those get dropped and logged
rather than shown to the user as fact.
"""

from __future__ import annotations
from typing import List, Tuple
from rapidfuzz import fuzz

MATCH_THRESHOLD = 85  # 0-100, partial_ratio score


def verify_quote(source_text: str, quote: str, threshold: int = MATCH_THRESHOLD) -> bool:
    if not quote or not quote.strip():
        return False
    score = fuzz.partial_ratio(quote.strip(), source_text)
    return score >= threshold


def filter_unverified_clauses(source_text: str, clauses: list) -> Tuple[list, list]:
    """Returns (verified_clauses, dropped_clauses) for a list of Clause objects."""
    verified, dropped = [], []
    for c in clauses:
        if not c.present:
            verified.append(c)
            continue
        if verify_quote(source_text, c.quoted_text or ""):
            verified.append(c)
        else:
            c.confidence = "low"
            c.location = (c.location or "") + " [UNVERIFIED - quote not found in source]"
            dropped.append(c)
    return verified, dropped


def filter_unverified_risks(source_text: str, risks: list) -> Tuple[list, list]:
    verified, dropped = [], []
    for r in risks:
        if verify_quote(source_text, r.quoted_text):
            verified.append(r)
        else:
            dropped.append(r)
    return verified, dropped
