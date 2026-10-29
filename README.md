# Procurement Assistant — LLM agent over California procurement data

A conversational assistant that answers natural-language questions about **346,018 purchase-order
line items** from the State of California (FY 2012–2015). An LLM agent built with **LangGraph**
translates each question into a **MongoDB aggregation pipeline**, executes it, self-corrects on
errors, and explains the result — with an auto-generated chart and a fully transparent query trace.

```
frontend/  React (Vite) chat UI — charts (Recharts), markdown answers, query trace
backend/   FastAPI + LangGraph agent + PyMongo, data loader, evaluation suite
archive/   Kaggle dataset (CSV not committed)
```

## Architecture

```
 React UI ──POST /api/chat──▶ FastAPI ──▶ LangGraph agent ──aggregate()──▶ MongoDB
                                             │
                     ┌──────── plan ◀────────┤  (loop ≤ 4 queries)
                     │   query? ──▶ execute ─┘   validate (read-only guard) → run → record rows / error
                     └─ answer / respond ──▶ answer ──▶ markdown + chart spec + trace
```

| Node | Responsibility |
|---|---|
| **plan** | LLM sees the schema, conversation history and previous steps; returns a structured `Plan`: run another `query` (pipeline as Extended JSON), `answer`, or `respond` directly (greeting / clarification / out of scope). |
| **execute** | Parses Extended JSON (`{"$date": ...}` → datetime), rejects write / JS operators (`$out`, `$merge`, `$function`, `$where`…), enforces a `$limit` and `maxTimeMS`, runs the pipeline. Errors are stored in the step and fed back to **plan** → self-correction. |
| **answer** | LLM writes the final answer from the collected results only (same language as the user), and proposes a chart (`bar` / `line` / `pie`) that the backend validates against the actual result columns. |

Conversation memory uses the LangGraph checkpointer keyed by `session_id`, so follow-ups like
*"And in February?"* work.

## Design choices

- **Data modelling for the LLM, not just loading.** The loader (`backend/scripts/load_data.py`)
  converts the raw CSV into typed, snake_case documents: dates → `Date`, `"$1,234.00"` → number,
  `Location` → GeoJSON, `Supplier Qualifications` → array, `CalCard` → bool. It also precomputes
  `year`, `quarter`, `year_month`, `year_quarter`, and the **California fiscal quarter** (Jul–Jun).
  Generated pipelines become shorter and far less error-prone than doing date math in the query.
- **Schema grounding.** The prompt contains a field dictionary with business meaning, plus values
  pulled live from the database (date range, all department names, acquisition types/methods, UNSPSC
  segments), so the model filters on values that exist instead of guessing spellings.
- **Domain rules encoded in the prompt.** "Orders" = distinct `po_number` (a PO has 1.7 line items on
  average), "spending" = `sum(total_price)`, `creation_date` is the primary date (`Purchase Date` contains
  invalid values such as 1911 and 6070, so they are removed on load), calendar vs fiscal quarters.
- **Multi-step reasoning.** The plan → execute loop lets the agent use one result to build the next query
  (e.g. *"In the quarter with the highest spending, which department spent the most?"*).
- **Safety.** Only `aggregate` is ever called; a recursive validator blocks write / server-side JS
  operators; results are capped and time-limited.
- **Transparency.** Every answer in the UI expands into the exact pipelines run, their timings, results
  and any self-corrected errors — procurement users can verify the numbers.
- **Provider-agnostic.** `init_chat_model` lets you switch between OpenAI, Anthropic and Google with
  two env vars.

### Data notes found during exploration
- 346,018 line items, 200,533 distinct POs, 111 departments, ~25k suppliers.
- 1,438 negative `total_price` lines (credits/adjustments) and a few extreme outliers (> $1B per line);
  they are kept as in the source, and the answer prompt asks the model to flag suspicious results.

## Setup

Prerequisites: Python 3.11+, Node 18+, MongoDB 6+ running locally (or a MongoDB Atlas URI), an LLM API key.

```bash
# 1. Backend
cd backend
python -m venv .venv
.venv\Scripts\activate          # Windows  (macOS/Linux: source .venv/bin/activate)
pip install -r requirements.txt
cp .env.example .env            # add your API key / Mongo URI

# 2. Load data — download the CSV from Kaggle into ../archive/
python -m scripts.load_data     # ~1 min, creates procurement.purchases + indexes

# 3. Run API
uvicorn app.main:app --reload --port 8000

# 4. Frontend (new terminal)
cd frontend
npm install
npm run dev                     # http://localhost:5173  (proxies /api to :8000)
```

## API

| Method | Path | Description |
|---|---|---|
| POST | `/api/chat` | `{message, session_id?}` → `{session_id, answer, chart, chart_rows, steps[]}` |
| GET | `/api/health` | MongoDB document count and active model |
| GET | `/api/examples` | Suggested questions |
| GET | `/api/schema` | Field dictionary |

Interactive docs: http://localhost:8000/docs

## Evaluation

`backend/eval/` contains 14 test cases across categories (time-period counts, highest-spending quarter,
most frequent items, rankings, array filters, multi-step, follow-up context, Arabic questions). Each case
has a **hand-written ground-truth pipeline**; the runner executes it, extracts the expected values, runs
the agent, and checks the answer (numbers within 1%, names case-insensitive).

```bash
cd backend
python -m eval.run_eval              # all cases → prints accuracy, latency; saves eval/results.json
python -m eval.run_eval multi_step   # a single case
```

## Example questions
- How many orders were created in March 2014?
- Which quarter had the highest spending?
- What are the 10 most frequently ordered items?
- Top 5 departments by total spending in fiscal year 2013-2014
- Show the monthly spending trend for 2014
- In the quarter with the highest spending, which department spent the most?
- كم عدد الطلبات في الربع الأول من 2015؟
