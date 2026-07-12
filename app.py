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

st.set_page_config(page_title="Contract Review Bot", page_icon="📄", layout="wide")

HTML_PATH = PROJECT_DIR / "groq_run_output_fixed.html"

try:
    html_content = HTML_PATH.read_text(encoding="utf-8")
except FileNotFoundError:
    html_content = "<p>Unable to load HTML template.</p>"

# Render the new HTML content using Streamlit components to avoid modifying the HTML file.
components.html(html_content, height=1000, scrolling=True)
st.stop()

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


# Lightweight CSS to improve visuals (larger text, light accents)
st.markdown(
    """
    <style>
    :root { --accent:#e6f4ff; --accent-2:#fff7ed; --muted:#4b5563; }
    body, .stApp {font-size:16px;}
    h1, .streamlit-expanderHeader {font-size:28px;}
    h2, .stMarkdown h2 {font-size:22px;}
    .report-card {background:#ffffff;padding:20px;border-radius:12px;box-shadow:0 6px 20px rgba(15,23,42,0.05);}
    .muted {color:var(--muted);}
    .badge {display:inline-block;padding:6px 10px;border-radius:999px;background:var(--accent);color:#0f172a;font-weight:700}
    .exec-summary {background:var(--accent);padding:12px;border-radius:10px;margin-bottom:12px}
    .risk-low {background:#ecfdf5;color:#064e3b;padding:6px 8px;border-radius:6px}
    .risk-medium {background:#fff7ed;color:#92400e;padding:6px 8px;border-radius:6px}
    .risk-high {background:#fff1f2;color:#7f1d1d;padding:6px 8px;border-radius:6px}
    .large-text {font-size:18px;}
    </style>
    """,
    unsafe_allow_html=True,
)

# Determine initial text from query params (supports demo flag)
# Use safe getattr fallback because some Streamlit deployments may not expose
# the experimental query API the same way.
get_q = getattr(st, "experimental_get_query_params", None)
if callable(get_q):
    try:
        q = get_q()
    except Exception:
        q = {}
else:
    q = {}

# If demo flag is present, prefill with SAMPLE_TEXT; otherwise leave empty.
initial_text = SAMPLE_TEXT if q.get("demo") == ["1"] else ""

def _on_text_change():
    st.session_state.auto_review = True

# Use a named key so we can reference the textarea state reliably
if "contract_text" not in st.session_state:
    st.session_state.contract_text = initial_text

text_area = st.text_area("Contract text", value=st.session_state.contract_text, height=340, key="contract_text", on_change=_on_text_change)

uploaded_file = st.file_uploader("Or upload a text file", type=["txt", "md"])
if uploaded_file is not None:
    try:
        content = uploaded_file.read().decode("utf-8")
        st.session_state.contract_text = content
        # Trigger auto-review when a file is uploaded
        st.session_state.auto_review = True
    except UnicodeDecodeError:
        st.error("Could not read the uploaded file as UTF-8 text.")
        st.stop()


col1, col2, col3 = st.columns([1,1,1])
do_review = col1.button("Review contract")
do_demo = col2.button("Use Demo Sample")
do_clear = col3.button("Clear")
# Track whether a recent text change/upload should auto-trigger a review
auto_flag = st.session_state.pop("auto_review", False)

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



def perform_review(text_input):
    if not os.getenv("GROQ_API_KEY") and not os.getenv("OPENAI_API_KEY"):
        st.warning("No API key found. Showing demo analysis instead. Set GROQ_API_KEY or OPENAI_API_KEY to run the real pipeline.")
        render_report(SAMPLE_REPORT)
    else:
        with st.spinner("Reviewing contract..."):
            try:
                report = review_contract(text_input, doc_id="streamlit-run")
                st.success("Review completed")
                render_report(report)
            except Exception as exc:
                st.error(f"Review failed: {exc}")

if do_demo:
    # Set a query param and rerun so the textarea is populated with demo text
    set_q = getattr(st, "experimental_set_query_params", None)
    if callable(set_q):
        try:
            set_q(demo="1")
        except Exception:
            pass
    # Safe rerun call
    rerun = getattr(st, "experimental_rerun", None)
    if callable(rerun):
        try:
            rerun()
        except Exception:
            pass

elif do_clear:
    set_q = getattr(st, "experimental_set_query_params", None)
    if callable(set_q):
        try:
            set_q()
        except Exception:
            pass
    # Safe rerun call
    rerun = getattr(st, "experimental_rerun", None)
    if callable(rerun):
        try:
            rerun()
        except Exception:
            pass

elif do_review:
    perform_review(st.session_state.get("contract_text", ""))

# If the text area changed (paste) or a file was uploaded, auto-review
elif auto_flag and st.session_state.get("contract_text", "").strip():
    perform_review(st.session_state.get("contract_text", ""))

else:
    st.info("Paste contract text or upload a file, then click Review contract, or click Use Demo Sample to load a demo report.")
