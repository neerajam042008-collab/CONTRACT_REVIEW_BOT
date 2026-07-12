import json
import os
import sys
from pathlib import Path
 
import streamlit as st
import streamlit.components.v1 as components
 
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
 
st.set_page_config(page_title="Clause Whisperer", page_icon="📄", layout="wide")
 
# The HTML template — keeping your existing filename/path, just with the
# redesigned dark-mode content (paste the template contents into this file).
TEMPLATE_PATH = PROJECT_DIR / "groq_run_output_fixed.html"
try:
    HTML_TEMPLATE = TEMPLATE_PATH.read_text(encoding="utf-8")
except FileNotFoundError:
    HTML_TEMPLATE = "<p>Unable to load HTML template. Make sure groq_run_output_fixed.html exists in contract-review-bot/.</p>"
 
SAMPLE_TEXT = """Service Agreement
 
Parties
This Agreement is made between Orion Tech Services Ltd ("Service Provider") and Nova Enterprises LLC ("Client").
 
Scope of Services
The Service Provider agrees to deliver IT consulting and software development services as described in Annex A.
 
Payment Terms
The Client shall pay invoices within 30 days of receipt. Late payments will incur interest at 5% per month.
 
Confidentiality
Both parties agree to maintain the confidentiality of proprietary information and not disclose it to third parties.
 
Indemnity
The Service Provider shall indemnify the Client against claims arising from negligence or breach of intellectual property rights.
 
Termination
Either party may terminate this Agreement with 30 days' written notice. Immediate termination is permitted in the event of a material breach.
 
Arbitration
Any disputes shall be resolved by binding arbitration in Mumbai under the rules of the Indian Arbitration Council.
 
Governing Law
This Agreement shall be governed by the laws of India.
"""
 
SAMPLE_REPORT = {
    "contract_type": "Service Agreement",
    "parties": [
        {"name": "Orion Tech Services Ltd", "role": "Service Provider"},
        {"name": "Nova Enterprises LLC", "role": "Client"},
    ],
    "clauses": [
        {"type": "payment_terms", "present": True, "quoted_text": "The Client shall pay invoices within 30 days of receipt.", "location": "Payment Terms", "confidence": "high"},
        {"type": "confidentiality", "present": True, "quoted_text": "Both parties agree to maintain the confidentiality of proprietary information.", "location": "Confidentiality", "confidence": "high"},
        {"type": "liability_and_indemnification", "present": True, "quoted_text": "The Service Provider shall indemnify the Client against claims arising from negligence.", "location": "Indemnity", "confidence": "high"},
        {"type": "term_and_termination", "present": True, "quoted_text": "Either party may terminate this Agreement with 30 days' written notice.", "location": "Termination", "confidence": "high"},
        {"type": "dispute_resolution_and_governing_law", "present": True, "quoted_text": "Any disputes shall be resolved by binding arbitration in Mumbai.", "location": "Arbitration", "confidence": "high"},
        {"type": "force_majeure", "present": False, "quoted_text": None, "location": None, "confidence": "low"},
    ],
    "risks": [
        {"related_clause": "payment_terms", "quoted_text": "Late payments will incur interest at 5% per month.", "issue": "high late-payment interest rate", "severity": "medium", "suggested_action": "Confirm the 5% monthly rate is enforceable in the governing jurisdiction and reasonable for the industry."},
        {"related_clause": "liability_and_indemnification", "quoted_text": "indemnify the Client against claims arising from negligence or breach of intellectual property rights", "issue": "one-sided, uncapped indemnity", "severity": "high", "suggested_action": "Consider a liability cap and mutual indemnification obligations."},
    ],
    "obligations_summary": [
        {"party": "Orion Tech Services Ltd", "obligations": ["Deliver IT consulting and software development services per Annex A", "Indemnify the Client against negligence or IP breach claims", "Maintain confidentiality of Client's proprietary information"]},
        {"party": "Nova Enterprises LLC", "obligations": ["Pay invoices within 30 days of receipt", "Maintain confidentiality of Service Provider's proprietary information"]},
    ],
    "missing_standard_clauses": ["force_majeure", "non_compete_non_solicit"],
    "executive_summary": '{"summary": "This Service Agreement between Orion Tech Services and Nova Enterprises covers IT consulting, payment, confidentiality, indemnity, termination, and arbitration under Indian law. The indemnity clause is one-sided and uncapped, and force majeure and non-compete clauses are absent \\u2014 both worth flagging for review."}',
    "disclaimer": "This is a demo analysis and not legal advice.",
}
 
st.title("📄 Clause Whisperer")
st.caption("AI-assisted contract review — paste a contract and get clauses, risks, and obligations.")
 
with st.sidebar:
    st.header("Setup")
    st.caption("Set your Groq/OpenAI and LangSmith keys in the environment or in .env")
    st.info("The app uses the existing LangGraph pipeline behind the scenes.")
 
# ---- session state ----
if "contract_text" not in st.session_state:
    st.session_state.contract_text = ""
if "report" not in st.session_state:
    st.session_state.report = None
 
# File upload happens BEFORE the text_area is created, so the update is
# reflected immediately without needing a rerun.
uploaded_file = st.file_uploader("Or upload a text file", type=["txt", "md"])
if uploaded_file is not None:
    try:
        st.session_state.contract_text = uploaded_file.read().decode("utf-8")
    except UnicodeDecodeError:
        st.error("Could not read the uploaded file as UTF-8 text.")
        st.stop()
 
st.text_area("Contract text", height=280, key="contract_text")
 
col1, col2, col3 = st.columns([1, 1, 1])
do_review = col1.button("🔍 Review Contract", type="primary", use_container_width=True)
do_demo = col2.button("✨ Use Sample Data (Demo)", use_container_width=True)
do_clear = col3.button("🧹 Clear", use_container_width=True)
 
 
def run_review(text_input: str):
    if not text_input.strip():
        st.warning("Paste contract text first.")
        return
    if not os.getenv("GROQ_API_KEY") and not os.getenv("OPENAI_API_KEY"):
        st.warning(
            "No API key found — showing demo analysis instead. "
            "Set GROQ_API_KEY or OPENAI_API_KEY to run the real pipeline."
        )
        st.session_state.report = SAMPLE_REPORT
        return
    with st.spinner("Reviewing contract…"):
        try:
            report = review_contract(text_input, doc_id="streamlit-run")
            st.session_state.report = report
            st.success("Review completed.")
        except Exception as exc:
            st.error(f"Review failed: {exc}")
 
 
if do_demo:
    st.session_state.contract_text = SAMPLE_TEXT
    st.session_state.report = SAMPLE_REPORT
    st.rerun()
elif do_clear:
    st.session_state.contract_text = ""
    st.session_state.report = None
    st.rerun()
elif do_review:
    run_review(st.session_state.contract_text)
 
# ---- render the report card ----
report = st.session_state.report
data_json = json.dumps(report) if report else "null"
html = HTML_TEMPLATE.replace("__DATA_JSON__", data_json)
components.html(html, height=1000, scrolling=True)
 
# ---- reliable copy / download, native Streamlit widgets (not inside the iframe) ----
if report:
    st.download_button(
        "⬇️ Download JSON report",
        data=json.dumps(report, indent=2),
        file_name="clause_whisperer_report.json",
        mime="application/json",
        use_container_width=False,
    )
    with st.expander("🧾 Raw JSON (click the copy icon in the top-right of the code block)"):
        st.code(json.dumps(report, indent=2), language="json")
else:
    st.info("Paste contract text or upload a file, then click Review Contract, or click Use Sample Data to load a demo report.")
 