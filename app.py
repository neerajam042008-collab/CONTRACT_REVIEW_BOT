import json
import os
import sys
from pathlib import Path

import streamlit as st
import streamlit.components.v1 as components

try:
    from dotenv import load_dotenv
except Exception:
    def load_dotenv(*args, **kwargs):
        return False

BASE_DIR = Path(__file__).resolve().parent
PROJECT_DIR = BASE_DIR / "contract-review-bot"

if str(PROJECT_DIR) not in sys.path:
    sys.path.insert(0, str(PROJECT_DIR))

load_dotenv(PROJECT_DIR / ".env")

from importlib import import_module

try:
    review_contract = import_module("main").review_contract
except ModuleNotFoundError:
    review_contract = import_module("contract_review_bot.main").review_contract

st.set_page_config(page_title="Clause Whisperer", page_icon="📄", layout="wide")

TEMPLATE_PATH = PROJECT_DIR / "groq_run_output_fixed.html"
try:
    HTML_TEMPLATE = TEMPLATE_PATH.read_text(encoding="utf-8")
except FileNotFoundError:
    HTML_TEMPLATE = "<p>Unable to load HTML template. Make sure groq_run_output_fixed.html exists in contract-review-bot/.</p>"

SAMPLE_TEXT = """Mutual Non-Disclosure Agreement

This Agreement is made between Acme Robotics Inc., a Delaware corporation ("Acme"), and Beta Logistics LLC, a California limited liability company ("Beta").

2. Confidential Information
Each party agrees to hold in strict confidence all non-public information disclosed by the other party, whether oral or written, and to use such information solely for the purpose of evaluating the potential business relationship.

3. Term
This Agreement shall remain in effect for a period of two (2) years from the Effective Date, unless earlier terminated by either party upon thirty (30) days written notice. This Agreement shall automatically renew for successive one (1) year terms unless either party provides written notice of non-renewal at least sixty (60) days prior to the end of the then-current term.

4. Indemnification
Beta agrees to indemnify, defend, and hold harmless Acme from any and all claims, damages, losses, and expenses (including attorneys' fees) arising out of or related to Beta's breach of this Agreement, without any limitation on the amount of such liability.

5. Governing Law
This Agreement shall be governed by the laws of the State of Delaware. Any disputes arising under this Agreement shall be resolved exclusively in the state or federal courts located in Delaware.

7. No License
Nothing in this Agreement shall be construed as granting any license or rights to either party's intellectual property.
"""

SAMPLE_REPORT = {
    "contract_type": "Mutual Non-Disclosure Agreement",
    "parties": [
        {"name": "Acme Robotics Inc.", "role": "a Delaware corporation"},
        {"name": "Beta Logistics LLC", "role": "a California limited liability company"},
    ],
    "clauses": [
        {"type": "term_and_termination", "present": True, "quoted_text": "This Agreement shall remain in effect for a period of two (2) years from the Effective Date, unless earlier terminated by either party upon thirty (30) days written notice.", "location": "3. Term", "confidence": "high"},
        {"type": "payment_terms", "present": False, "quoted_text": None, "location": None, "confidence": "low"},
        {"type": "liability_and_indemnification", "present": True, "quoted_text": "Beta agrees to indemnify, defend, and hold harmless Acme from any and all claims, damages, losses, and expenses arising out of or related to Beta's breach of this Agreement, without any limitation on the amount of such liability.", "location": "4. Indemnification", "confidence": "high"},
        {"type": "confidentiality", "present": True, "quoted_text": "Each party agrees to hold in strict confidence all non-public information disclosed by the other party, whether oral or written.", "location": "2. Confidential Information", "confidence": "high"},
        {"type": "intellectual_property", "present": True, "quoted_text": "Nothing in this Agreement shall be construed as granting any license or rights to either party's intellectual property.", "location": "7. No License", "confidence": "high"},
        {"type": "non_compete_non_solicit", "present": False, "quoted_text": None, "location": None, "confidence": "low"},
        {"type": "dispute_resolution_and_governing_law", "present": True, "quoted_text": "This Agreement shall be governed by the laws of the State of Delaware. Any disputes shall be resolved exclusively in the state or federal courts located in Delaware.", "location": "5. Governing Law", "confidence": "high"},
        {"type": "auto_renewal", "present": True, "quoted_text": "This Agreement shall automatically renew for successive one (1) year terms unless either party provides written notice of non-renewal at least sixty (60) days prior to the end of the then-current term.", "location": "3. Term", "confidence": "high"},
        {"type": "force_majeure", "present": False, "quoted_text": None, "location": None, "confidence": "low"},
    ],
    "risks": [
        {"related_clause": "liability_and_indemnification", "quoted_text": "without any limitation on the amount of such liability", "issue": "uncapped/unlimited liability", "severity": "high", "suggested_action": "This clause may warrant review by a licensed attorney because it could lead to significant financial exposure for Beta."},
        {"related_clause": "auto_renewal", "quoted_text": "unless either party provides written notice of non-renewal at least sixty (60) days prior to the end of the then-current term", "issue": "auto-renewal without adequate notice", "severity": "medium", "suggested_action": "Consider negotiating a longer notice period to ensure sufficient time for review and decision-making."},
    ],
    "obligations_summary": [
        {"party": "Acme Robotics Inc.", "obligations": ["Hold in strict confidence all non-public information disclosed by Beta Logistics LLC", "Use disclosed information solely for evaluating the potential business relationship"]},
        {"party": "Beta Logistics LLC", "obligations": ["Indemnify, defend, and hold harmless Acme Robotics Inc. from claims arising out of Beta's breach of the Agreement", "Hold in strict confidence all non-public information disclosed by Acme Robotics Inc.", "Use disclosed information solely for evaluating the potential business relationship", "Provide written notice of non-renewal at least sixty (60) days prior to the end of the then-current term if Beta does not want the Agreement to automatically renew"]},
    ],
    "missing_standard_clauses": ["payment_terms", "non_compete_non_solicit", "force_majeure"],
    "executive_summary": '{"summary": "This Mutual Non-Disclosure Agreement between Acme Robotics Inc. and Beta Logistics LLC has several key clauses, including term and termination, liability and indemnification, confidentiality, intellectual property, and dispute resolution. High-severity risks include uncapped liability for Beta and auto-renewal without adequate notice. Critically missing clauses include payment terms, non-compete/non-solicit, and force majeure."}',
    "disclaimer": "This analysis is generated by an AI system for informational purposes only and does not constitute legal advice. Consult a licensed attorney before making decisions based on this contract.",
}

# ---- session state ----
if "contract_text" not in st.session_state:
    st.session_state.contract_text = ""
if "report" not in st.session_state:
    st.session_state.report = None
if "theme" not in st.session_state:
    st.session_state.theme = "dark"

is_light = st.session_state.theme == "light"

if is_light:
    _bg = "linear-gradient(180deg,#f6f4ef,#efece3)"
    _card_bg = "#faf9f5"
    _border = "rgba(20,20,20,0.12)"
    _text = "#171a1e"
else:
    _bg = "linear-gradient(180deg,#0a0d13,#0d1119)"
    _card_bg = "#12161f"
    _border = "rgba(232,236,244,0.12)"
    _text = "#e7ebf3"

st.markdown(
    f"""
    <link href="https://fonts.googleapis.com/css2?family=Fraunces:opsz,wght@9..144,600&family=Inter:wght@400;500;600;700&family=JetBrains+Mono:wght@400;500&display=swap" rel="stylesheet">
    <style>
    [data-testid="stAppViewContainer"], .stApp {{ background:{_bg} !important; }}
    .block-container {{ padding-top: 2.2rem; max-width: 1200px; }}
    h1,h2,h3,h4,h5,h6,p,label,span,div {{ color:{_text}; }}
    div[data-testid="stFileUploaderDropzone"] {{
        background-color:{_card_bg} !important;
        border:1px dashed {_border} !important;
        border-radius:12px !important;
    }}
    textarea {{
        background-color:{_card_bg} !important;
        border:1px solid {_border} !important;
        border-radius:12px !important;
        color:{_text} !important;
        font-family:'JetBrains Mono','Courier New',monospace !important;
    }}
    textarea:focus {{ border-color:#5b9dff !important; box-shadow:none !important; }}
    .stButton>button {{
        border-radius:10px !important;
        font-weight:600 !important;
        border:1px solid {_border} !important;
        background-color:{_card_bg} !important;
        color:{_text} !important;
    }}
    div[data-testid="column"]:nth-of-type(1) .stButton>button {{
        background:linear-gradient(135deg,#5b9dff,#8f7cff) !important;
        border:none !important; color:white !important;
    }}
    div[data-testid="column"]:nth-of-type(2) .stButton>button {{
        background:linear-gradient(135deg,#3fb893,#2f9b7d) !important;
        border:none !important; color:white !important;
    }}
    div[data-testid="column"]:nth-of-type(3) .stButton>button {{
        background-color:{_card_bg} !important; color:{_text} !important;
        border:1px solid {_border} !important;
    }}
    div[data-testid="stExpander"] {{
        background-color:{_card_bg} !important;
        border:1px solid {_border} !important;
        border-radius:12px !important;
    }}
    iframe {{ border:none !important; }}
    </style>

    <div style="display:flex;align-items:center;gap:16px;margin-bottom:6px;">
      <div style="width:52px;height:52px;border-radius:14px;flex-shrink:0;background:linear-gradient(150deg,#5b9dff,#8f7cff);display:flex;align-items:center;justify-content:center;box-shadow:0 12px 28px rgba(91,157,255,0.25);">
        <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="white" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><path d="M20 4 9 15"/><path d="M20 4 14 20l-3-6-6-3 15-7Z"/></svg>
      </div>
      <div>
        <div style="font-family:'Fraunces',serif;font-weight:600;font-size:24px;color:{_text};display:none">Clause Whisperer</div>
        <div style="color:#8b93a7;font-size:13px;margin-top:2px;">AI-assisted contract review — paste a contract and get clauses, risks, and obligations.</div>
      </div>
    </div>
    """,
    unsafe_allow_html=True,
)

st.text_area("Contract text", height=220, key="contract_text")

col1, col2, col3 = st.columns([1.4, 1.4, 1])
do_review = col1.button("🔍 Review Contract", use_container_width=True)

def _use_demo():
    st.session_state.contract_text = SAMPLE_TEXT
    st.session_state.report = SAMPLE_REPORT

do_demo = col2.button("✨ Use Sample Data (Demo)", on_click=_use_demo, use_container_width=True)
do_theme_toggle = col3.button("☀️ Light" if not is_light else "🌙 Dark", use_container_width=True)

if do_theme_toggle:
    st.session_state.theme = "light" if not is_light else "dark"
    st.rerun()


def run_review(text_input: str):
    if not text_input.strip():
        st.warning("Paste contract text first.")
        return
    with st.spinner("Reviewing contract…"):
        try:
            report = review_contract(text_input, doc_id="streamlit-run")
            st.session_state.report = report
            st.success("Review completed.")
        except Exception as exc:
            st.error(f"Review failed: {exc}")
            # Fallback to demo analysis so users can still see output
            # when the external LLM call fails (rate limit, missing creds, etc.)
            st.session_state.report = SAMPLE_REPORT


if do_review:
    run_review(st.session_state.contract_text)

report = st.session_state.report
data_json = json.dumps(report) if report else "null"
html = HTML_TEMPLATE.replace("__THEME_CLASS__", "light" if is_light else "").replace("__DATA_JSON__", data_json)
components.html(html, height=900, scrolling=True)

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