# Contract Review Bot

A LangGraph + LangChain pipeline (running on Groq models, traced with LangSmith)
that reviews contracts, extracts key clauses, flags risky terms, and produces
a structured JSON report plus a plain-English executive summary.

**This is not legal advice.** Every output includes a disclaimer and is meant
as a first-pass research aid to be reviewed by a licensed attorney.

## Pipeline

```
ingest → classify → extract_clauses → verify_clauses (hallucination check)
       → risk_analysis → obligations → summarize → format_output
```

- **ingest**: splits the contract by section/clause headers (not fixed token
  windows) so clauses never get cut mid-way.
- **classify**: cheap Groq model (`llama-3.1-8b-instant`) identifies contract type.
- **extract_clauses**: large Groq model (`llama-3.3-70b-versatile`) pulls parties
  and 10 standard clause types, batching long contracts to stay under context limits.
- **verify_clauses**: fuzzy-matches every quoted clause against the source text
  and downgrades/flags anything that can't be verified — this is the
  hallucination guard.
- **risk_analysis**: flags one-sided indemnification, uncapped liability,
  auto-renewal traps, broad non-competes, etc., with severity and suggested action.
  Risk quotes are also verified against source.
- **obligations**: plain-language summary of each party's obligations.
- **summarize**: 200-word executive summary.
- **format_output**: validates everything against the `FinalReport` Pydantic
  schema before returning.

## Setup

```bash
python -m venv venv
source venv/bin/activate        # Windows: venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env            # then fill in GROQ_API_KEY and LangSmith keys
```

## Run

```bash
python main.py sample_contracts/sample_nda.txt
```

This prints the full JSON report, the executive summary, and the legal disclaimer.
Every node call is traced to LangSmith under the `contract-review-bot` project
(set `LANGCHAIN_PROJECT` in `.env` to change this) — open the LangSmith UI to
inspect prompts/responses per node, per document.

## Using it in your own code

```python
from main import review_contract

with open("my_contract.txt") as f:
    text = f.read()

report = review_contract(text, doc_id="contract-123")
print(report["risks"])
```

## Output schema

See `app/schemas.py` -> `FinalReport`. Top-level keys:
`contract_type, parties, clauses, risks, obligations_summary,
missing_standard_clauses, executive_summary, disclaimer`.

## Extending

- **PDF input**: extract text with `pypdf`/`pdfplumber` before passing to
  `review_contract()` — the `ingest` node already expects plain text.
- **Eval dataset**: create a LangSmith dataset of sample contracts + expected
  extractions, and use `langsmith.evaluate()` against `contract_review_app` to
  catch regressions when you change prompts or swap Groq models.
- **Streaming / async**: `contract_review_app.astream(...)` works out of the
  box if you want to stream node-by-node progress to a UI.
- **Human-in-the-loop**: LangGraph supports checkpointing + interrupts if you
  want a reviewer to approve/edit extracted clauses before risk analysis runs.

## Notes on Groq JSON mode

Not all Groq-hosted OSS models honor `response_format={"type": "json_object"}`
as strictly as OpenAI's models do. `app/llm.py` treats this as a hint only:
every response is parsed and validated against a Pydantic schema, and on
failure the pipeline automatically retries with the validation error fed
back into the prompt (self-repair loop, capped at 2 retries per node).

## Groq API / Provider selection

By default the project uses Groq models. Set your Groq API key in `.env` or
the environment:

```
GROQ_API_KEY=your_groq_api_key_here
```

If you need to switch providers (for example to OpenAI for comparison or
testing), set the `LLM_PROVIDER` env var to `openai` and provide an
`OPENAI_API_KEY`. The code will raise a clear error if the required API key
is absent.

```
LLM_PROVIDER=groq   # default
# or
LLM_PROVIDER=openai
```
