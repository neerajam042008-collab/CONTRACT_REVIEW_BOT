import json
import os
import sys
from pathlib import Path

import streamlit as st
try:
    from dotenv import load_dotenv
except Exception:
    # If python-dotenv isn't installed in the environment (e.g. on Streamlit Cloud),
    # provide a no-op fallback so the app can still run using real environment vars
    def load_dotenv(*args, **kwargs):
        return False

BASE_DIR = Path(__file__).resolve().parent
PROJECT_DIR = BASE_DIR / "contract-review-bot"

if str(PROJECT_DIR) not in sys.path:
    sys.path.insert(0, str(PROJECT_DIR))

load_dotenv(PROJECT_DIR / ".env")

from main import review_contract  # noqa: E402

st.set_page_config(page_title="Contract Review Bot", page_icon="📄", layout="wide")

st.title("Contract Review Bot")
st.write("Upload a contract or paste the text to get a structured review.")

with st.sidebar:
    st.header("Setup")
    st.caption("Set your Groq/OpenAI and LangSmith keys in the environment or in .env")
    st.info("The app uses the existing LangGraph pipeline behind the scenes.")

SAMPLE_TEXT = """
Either party may terminate this contract with [Number] days written notice.

5. Governing Law
This contract is governed by the laws of [Jurisdiction].

Signed:

_____________________
Party A

_____________________
Party B
"""

SAMPLE_REPORT = {
    "contract_type": "Mutual Non-Disclosure Agreement",
    "parties": [
        {"name": "Acme Robotics Inc.", "role": "a Delaware corporation"},
        {"name": "Beta Logistics LLC", "role": "a California limited liability company"}
    ],
    "clauses": [
        {"type": "term_and_termination", "present": True, "quoted_text": "Either party may terminate this contract with [Number] days written notice.", "location": "3. Term", "confidence": "high"},
        {"type": "governing_law", "present": True, "quoted_text": "This contract is governed by the laws of [Jurisdiction].", "location": "5. Governing Law", "confidence": "high"}
    ],
    "risks": [
        {"related_clause": "term_and_termination", "quoted_text": "Either party may terminate this contract...", "issue": "short notice period", "severity": "medium", "suggested_action": "Consider lengthening notice for continuity."}
    ],
    "obligations_summary": [
        {"party": "Acme Robotics Inc.", "obligations": ["Hold confidential information in strict confidence"]},
        {"party": "Beta Logistics LLC", "obligations": ["Hold confidential information in strict confidence"]}
    ],
    "missing_standard_clauses": ["payment_terms","force_majeure"],
    "executive_summary": "This sample NDA includes term and governing law clauses. Reviewers should check notice periods and missing payment/force majeure clauses.",
    "disclaimer": "This is a demo analysis and not legal advice."
}


# Use session state to keep text and report across interactions
# Avoid assigning into `st.session_state` at import time (Streamlit may raise),
# instead read with .get() to provide defaults and only set state inside
# interaction branches.
text_input = st.text_area("Contract text", value=st.session_state.get("contract_text", SAMPLE_TEXT), key="contract_text", height=300)

uploaded_file = st.file_uploader("Or upload a text file", type=["txt", "md"])
if uploaded_file is not None:
    try:
        st.session_state.contract_text = uploaded_file.read().decode("utf-8")
        text_input = st.session_state.contract_text
    except UnicodeDecodeError:
        st.error("Could not read the uploaded file as UTF-8 text.")
        st.stop()


col1, col2, col3 = st.columns([1,1,1])
do_review = col1.button("Review contract")
do_demo = col2.button("Use Demo Sample")
do_clear = col3.button("Clear")

def render_report(report):
    st.subheader("Executive summary")
    st.write(report.get("executive_summary", ""))

    st.subheader("Parties")
    parties = report.get("parties", [])
    if parties:
        for p in parties:
            name = p.get("name", "")
            role = p.get("role", "")
            st.markdown(f"- **{name}** — {role}")
    else:
        st.write("No parties extracted.")

    st.subheader("Clauses")
    clauses = report.get("clauses", [])
    if clauses:
        for c in clauses:
            ctype = c.get("type", "").replace("_", " ").title()
            present = "Present" if c.get("present") else "Missing"
            location = c.get("location") or "—"
            st.markdown(f"- **{ctype}** ({present}) — {location}")
            quoted = c.get("quoted_text")
            if quoted:
                st.markdown(f"    > {quoted}")
    else:
        st.write("No clauses found.")

    st.subheader("Risks")
    risks = report.get("risks", [])
    if risks:
        for r in risks:
            issue = r.get("issue") or r.get("related_clause") or "Unknown issue"
            severity = r.get("severity", "")
            st.markdown(f"- **{issue}** — Severity: {severity}")
            if r.get("quoted_text"):
                st.markdown(f"    > {r.get('quoted_text')}")
            if r.get("suggested_action"):
                st.markdown(f"    Suggested action: {r.get('suggested_action')}")
    else:
        st.write("No risks identified.")

    st.subheader("Critical obligations")
    obligations = report.get("obligations_summary", [])
    if obligations:
        for o in obligations:
            st.markdown(f"- **{o.get('party','')}**: {', '.join(o.get('obligations', []))}")
    else:
        st.write("No obligations extracted.")

    st.subheader("Missing standard clauses")
    missing = report.get("missing_standard_clauses", [])
    if missing:
        st.write(", ".join(missing))
    else:
        st.write("None")

    # Disclaimer
    if report.get("disclaimer"):
        st.caption(report.get("disclaimer"))

    # Raw JSON (hidden by default)
    with st.expander("Show raw JSON report"):
        st.json(report)


if do_demo:
    st.session_state.contract_text = SAMPLE_TEXT
    st.session_state.report = SAMPLE_REPORT
    render_report(SAMPLE_REPORT)

elif do_clear:
    st.session_state.contract_text = ""
    st.session_state.report = None
    st.experimental_rerun()

elif do_review:
    # If no keys are configured, fall back to demo report but warn the user.
    if not os.getenv("GROQ_API_KEY") and not os.getenv("OPENAI_API_KEY"):
        st.warning("No API key found. Showing demo analysis instead. Set GROQ_API_KEY or OPENAI_API_KEY to run the real pipeline.")
        st.session_state.report = SAMPLE_REPORT
        render_report(SAMPLE_REPORT)
    else:
        with st.spinner("Reviewing contract..."):
            try:
                report = review_contract(st.session_state.contract_text, doc_id="streamlit-run")
                st.session_state.report = report
                st.success("Review completed")
                render_report(report)
            except Exception as exc:
                st.error(f"Review failed: {exc}")

else:
    if st.session_state.get("report"):
        render_report(st.session_state.get("report"))
    else:
        st.info("Paste contract text or upload a file, then click Review contract, or click Use Demo Sample to load a demo report.")
