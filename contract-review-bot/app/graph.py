from __future__ import annotations
from langgraph.graph import StateGraph, END

from .state import ContractReviewState
from .nodes import (
    ingest_node,
    classify_node,
    extract_clauses_node,
    verify_clauses_node,
    risk_analysis_node,
    obligations_node,
    summarize_node,
    format_output_node,
)


def build_graph():
    graph = StateGraph(ContractReviewState)

    graph.add_node("ingest", ingest_node)
    graph.add_node("classify", classify_node)
    graph.add_node("extract_clauses", extract_clauses_node)
    graph.add_node("verify_clauses", verify_clauses_node)
    graph.add_node("risk_analysis", risk_analysis_node)
    graph.add_node("obligations", obligations_node)
    graph.add_node("summarize", summarize_node)
    graph.add_node("format_output", format_output_node)

    graph.set_entry_point("ingest")
    graph.add_edge("ingest", "classify")
    graph.add_edge("classify", "extract_clauses")
    graph.add_edge("extract_clauses", "verify_clauses")
    graph.add_edge("verify_clauses", "risk_analysis")
    graph.add_edge("risk_analysis", "obligations")
    graph.add_edge("obligations", "summarize")
    graph.add_edge("summarize", "format_output")
    graph.add_edge("format_output", END)

    return graph.compile()


# Singleton compiled app, importable elsewhere
contract_review_app = build_graph()
