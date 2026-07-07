"""
Thin wrapper around ChatGroq that:
  1. Calls the model with a prompt expecting raw JSON back
  2. Strips markdown fences if the model adds them anyway
  3. Validates against a Pydantic schema
  4. On failure, retries with the validation error appended (self-repair loop)

This is needed because Groq-hosted OSS models don't all honor
response_format={"type": "json_object"} as reliably as OpenAI's models do,
so we treat JSON-mode as a hint, not a guarantee, and always validate.
"""

from __future__ import annotations
import json
import os
import re
from typing import Type, TypeVar

from pydantic import BaseModel, ValidationError

# Support multiple LLM backends; default is Groq.
from langchain_groq import ChatGroq
try:
    from langchain.chat_models import ChatOpenAI
except Exception:  # pragma: no cover - optional dependency
    ChatOpenAI = None
    try:
        import openai
        from types import SimpleNamespace

        class OpenAIWrapper:
            def __init__(self, model: str, temperature: float = 0.0):
                self.model = model
                self.temperature = temperature

            def invoke(self, prompt: str):
                try:
                    from openai import OpenAI
                    client = OpenAI()
                    resp = client.chat.completions.create(
                        model=self.model,
                        messages=[{"role": "user", "content": prompt}],
                        temperature=self.temperature,
                    )
                    # New client returns objects with nested attributes
                    content = resp.choices[0].message.content
                except Exception:
                    # fallback to older openai interface if present
                    resp = openai.ChatCompletion.create(
                        model=self.model,
                        messages=[{"role": "user", "content": prompt}],
                        temperature=self.temperature,
                    )
                    content = resp["choices"][0]["message"]["content"]
                return SimpleNamespace(content=content)

    except Exception:  # pragma: no cover
        OpenAIWrapper = None


class MockLLM:
    """A tiny offline LLM shim that returns structured JSON based on
    simple heuristics. Used when no external API key is available.
    The `.invoke(prompt)` method returns an object with a `content` attr
    to match the shape used elsewhere in the codebase.
    """
    def __init__(self, size: str = "large", temperature: float = 0.0):
        from types import SimpleNamespace

        self.size = size
        self.temperature = temperature
        self._ns = SimpleNamespace

    def invoke(self, prompt: str):
        import json
        from types import SimpleNamespace

        text = prompt

        # Heuristic: detect which task the prompt requests by presence
        # of key phrases from the prompt templates.
        if "Identify the contract type" in text:
            contract_type = "Unknown"
            if "NDA" in text or "Non-Disclosure" in text or "confidential" in text.lower():
                contract_type = "NDA"
            body = {
                "contract_type": contract_type,
                "is_confident": True if contract_type != "Unknown" else False,
                "reasoning": "Detected NDA-like confidentiality language." if contract_type == "NDA" else "Could not confidently classify from preview.",
            }
            return SimpleNamespace(content=json.dumps(body))

        if "Extract parties" in text or "Clause types to look for" in text:
            # attempt to pull parties using a simple regex
            import re

            contract_text = text.split("CONTRACT TEXT:", 1)[-1] if "CONTRACT TEXT:" in text else text
            m = re.search(r"[Bb]etween\s+([^,\n]+?)\s+(?:and|&)\s+([^,\n]+)", contract_text)
            parties = []
            if m:
                a = m.group(1).strip(" \"'.")
                b = m.group(2).strip(" \"'.")
                parties = [{"name": a, "role": "party"}, {"name": b, "role": "party"}]

            clause_types = [
                "term_and_termination",
                "payment_terms",
                "liability_and_indemnification",
                "confidentiality",
                "intellectual_property",
                "non_compete_non_solicit",
                "dispute_resolution_and_governing_law",
                "auto_renewal",
                "force_majeure",
            ]

            keywords = {
                "confidentiality": ["confidential", "nondisclosure", "non-disclosure"],
                "payment_terms": ["payment", "fee", "compensation"],
                "term_and_termination": ["termination", "terminate", "term of this agreement"],
                "liability_and_indemnification": ["liability", "indemnif"],
                "intellectual_property": ["intellectual property", "ip", "ownership"],
                "non_compete_non_solicit": ["non-compete", "non compete", "non-solicit"],
                "dispute_resolution_and_governing_law": ["governing law", "jurisdiction", "arbitration", "dispute"],
                "auto_renewal": ["renew", "renewal"],
                "force_majeure": ["force majeure", "act of god"],
            }

            clauses = []
            # simple sentence extractor
            sentences = re.split(r"(?<=[.\n])\s+", contract_text)

            for ctype in clause_types:
                found = False
                quote = None
                location = None
                for kw in keywords.get(ctype, []):
                    for s in sentences:
                        if kw.lower() in s.lower():
                            found = True
                            quote = s.strip()
                            location = None
                            break
                    if found:
                        break

                clauses.append(
                    {
                        "type": ctype,
                        "present": bool(found),
                        "quoted_text": quote if found else None,
                        "location": location,
                        "confidence": "high" if found else "low",
                    }
                )

            body = {"parties": parties, "clauses": clauses}
            return SimpleNamespace(content=json.dumps(body))

        if "Given the extracted clauses" in text or "identify risky or unusual terms" in text:
            # Expecting clauses_json in prompt
            import json
            try:
                clauses_json = json.loads(text.split("EXTRACTED CLAUSES (JSON):", 1)[-1].strip())
            except Exception:
                clauses_json = {"clauses": []}

            risks = []
            missing = [c["type"] for c in clauses_json.get("clauses", []) if not c.get("present")]
            body = {"risks": risks, "missing_standard_clauses": missing}
            return SimpleNamespace(content=json.dumps(body))

        if "Summarize each party's key obligations" in text or "obligations_summary" in text:
            import json
            try:
                payload = json.loads(text.split("PARTIES AND CLAUSES (JSON):", 1)[-1].strip())
            except Exception:
                payload = {"parties": [], "clauses": []}
            obligations = []
            for p in payload.get("parties", []):
                obligations.append({"party": p.get("name", "Unknown"), "obligations": []})
            body = {"obligations_summary": obligations}
            return SimpleNamespace(content=json.dumps(body))

        if "Write a plain-English executive summary" in text or "EXEC_SUMMARY_PROMPT" in text:
            # create a short executive summary using partial report
            import json
            try:
                report = json.loads(text.split("REPORT (JSON):", 1)[-1].strip())
            except Exception:
                report = {}
            ctype = report.get("contract_type") or report.get("contract_type") or "contract"
            missing = report.get("missing_standard_clauses", [])
            highest = "none"
            summary = f"This {ctype} appears to be a {ctype}. Missing clauses: {', '.join(missing) if missing else 'none detected'}."
            return SimpleNamespace(content=summary)

        # Fallback: return a minimal empty JSON
        return SimpleNamespace(content="{}")


T = TypeVar("T", bound=BaseModel)

_JSON_FENCE_RE = re.compile(r"^```(?:json)?\s*|\s*```$", re.MULTILINE)


def _strip_fences(text: str) -> str:
    return _JSON_FENCE_RE.sub("", text).strip()


def get_llm(size: str = "large", temperature: float = 0.0):
    """
    size: "large" for extraction/reasoning nodes, "small" for cheap
    classification-style nodes.
    """
    provider = os.environ.get("LLM_PROVIDER", "groq").lower()

    if provider == "groq":
        model_name = (
            os.environ.get("GROQ_MODEL_LARGE", "llama-3.3-70b-versatile")
            if size == "large"
            else os.environ.get("GROQ_MODEL_SMALL", "llama-3.1-8b-instant")
        )
        if not os.environ.get("GROQ_API_KEY"):
            print("[warning] GROQ_API_KEY not set — using offline MockLLM for testing.")
            return MockLLM(size=size, temperature=temperature)

        return ChatGroq(
            model=model_name,
            temperature=temperature,
            # Ask for JSON mode where supported; harmless if ignored.
            model_kwargs={"response_format": {"type": "json_object"}},
        )

    if provider in ("openai", "chatgpt"):
        # Pick names that approximate the Groq sizes; users should set
        # `OPENAI_MODEL` env var to control the exact model if desired.
        model_name = os.environ.get(
            "OPENAI_MODEL", "gpt-4o" if size == "large" else "gpt-4o-mini"
        )
        if not os.environ.get("OPENAI_API_KEY"):
            print("[warning] OPENAI_API_KEY not set — using offline MockLLM for testing.")
            return MockLLM(size=size, temperature=temperature)

        if ChatOpenAI is not None:
            return ChatOpenAI(model=model_name, temperature=temperature)

        if 'OpenAIWrapper' in globals() and OpenAIWrapper is not None:
            # configure the openai client from env
            try:
                import openai
                openai.api_key = os.environ.get("OPENAI_API_KEY")
            except Exception:
                pass
            return OpenAIWrapper(model_name, temperature=temperature)

        raise ImportError(
            "OpenAI chat model requested but neither `langchain` ChatOpenAI nor a local OpenAI client are available."
        )

    raise ValueError(f"Unsupported LLM_PROVIDER: {provider}")


def call_structured(
    llm: ChatGroq,
    prompt: str,
    schema: Type[T],
    max_retries: int = 2,
) -> T:
    """
    Calls the LLM, parses JSON, validates against `schema`.
    Retries with the error fed back to the model on failure.
    """
    last_error = None
    current_prompt = prompt

    for attempt in range(max_retries + 1):
        try:
            response = llm.invoke(current_prompt)
        except Exception as e:
            print(f"[warning] LLM invocation failed: {e}. Falling back to MockLLM.")
            llm = MockLLM(size="large", temperature=0.0)
            response = llm.invoke(current_prompt)
        raw_text = response.content if hasattr(response, "content") else str(response)
        cleaned = _strip_fences(raw_text)

        try:
            data = json.loads(cleaned)
            return schema.model_validate(data)
        except (json.JSONDecodeError, ValidationError) as e:
            last_error = e
            current_prompt = (
                f"{prompt}\n\n"
                f"Your previous response failed validation with this error:\n"
                f"{str(e)}\n\n"
                f"Your previous response was:\n{cleaned}\n\n"
                f"Return ONLY corrected, valid JSON matching the required schema. "
                f"No commentary, no markdown fences."
            )
            continue

    raise ValueError(
        f"Failed to get valid structured output after {max_retries + 1} attempts. "
        f"Last error: {last_error}"
    )


def call_plain_text(llm: ChatGroq, prompt: str) -> str:
    try:
        response = llm.invoke(prompt)
    except Exception as e:
        print(f"[warning] LLM invocation failed: {e}. Falling back to MockLLM.")
        llm = MockLLM(size="large", temperature=0.2)
        response = llm.invoke(prompt)

    text = response.content if hasattr(response, "content") else str(response)
    return _strip_fences(text)
