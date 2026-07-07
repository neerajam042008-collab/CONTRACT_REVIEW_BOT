"""
Usage:
    python main.py path/to/contract.txt

Requires GROQ_API_KEY (and optionally LangSmith vars) set in your
environment or a .env file — see .env.example.
"""

import json
import os
import sys
import uuid

from dotenv import load_dotenv

load_dotenv()

def _sanitize_langsmith_env() -> None:
    key = os.environ.get("LANGCHAIN_API_KEY", "").strip()
    if not key or key.startswith("your_"):
        print(
            "[warning] LangSmith tracing disabled because LANGCHAIN_API_KEY is missing or placeholder."
        )
        os.environ["LANGCHAIN_TRACING_V2"] = "false"

_sanitize_langsmith_env()

from app.graph import contract_review_app  # noqa: E402


def review_contract(text: str, doc_id: str | None = None) -> dict:
    doc_id = doc_id or str(uuid.uuid4())
    initial_state = {"raw_text": text, "doc_id": doc_id}

    # config.tags/metadata show up in LangSmith traces for filtering
    config = {
        "configurable": {"thread_id": doc_id},
        "tags": ["contract-review"],
        "metadata": {"doc_id": doc_id},
    }

    final_state = contract_review_app.invoke(initial_state, config=config)
    return final_state["final_report"]


def main():
    if len(sys.argv) < 2:
        print("Usage: python main.py path/to/contract.txt")
        sys.exit(1)

    path = sys.argv[1]
    with open(path, "r", encoding="utf-8") as f:
        text = f.read()

    report = review_contract(text)
    print(json.dumps(report, indent=2))
    print("\n--- EXECUTIVE SUMMARY ---")
    print(report["executive_summary"])
    print(f"\n{report['disclaimer']}")


if __name__ == "__main__":
    main()
