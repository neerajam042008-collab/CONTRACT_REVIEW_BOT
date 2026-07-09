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

sample_text = """Sample contract text goes here. Replace this with your contract text or upload a .txt file."""

text_input = st.text_area("Contract text", value=sample_text, height=300)

uploaded_file = st.file_uploader("Or upload a text file", type=["txt", "md"])

if uploaded_file is not None:
    try:
        text_input = uploaded_file.read().decode("utf-8")
    except UnicodeDecodeError:
        st.error("Could not read the uploaded file as UTF-8 text.")
        st.stop()

if st.button("Review contract") and text_input.strip():
    if not os.getenv("GROQ_API_KEY") and not os.getenv("OPENAI_API_KEY"):
        st.error("No API key found. Set GROQ_API_KEY or OPENAI_API_KEY before running the app.")
        st.stop()

    with st.spinner("Reviewing contract..."):
        try:
            report = review_contract(text_input, doc_id="streamlit-demo")
        except Exception as exc:
            st.error(f"Review failed: {exc}")
            st.stop()

    st.success("Review completed")

    st.subheader("Executive summary")
    st.write(report.get("executive_summary", ""))

    st.subheader("Risks")
    st.json(report.get("risks", []))

    st.subheader("Full JSON report")
    st.json(report)

else:
    st.info("Paste contract text or upload a file, then click Review contract.")
