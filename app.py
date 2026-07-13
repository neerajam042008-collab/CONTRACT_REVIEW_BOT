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

from importlib import import_module

try:
    review_contract = import_module("main").review_contract
except ModuleNotFoundError:
    review_contract = import_module("contract_review_bot.main").review_contract

st.set_page_config(page_title="Clause Whisperer", page_icon="📄", layout="wide")

# The HTML template — keeping your existing filename/path, just with the
# redesigned dark-mode content (paste the template contents into this file).
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
if "report" not in st.session_state:
    st.session_state.report = SAMPLE_REPORT

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