# Expense Analyzer — project context

UPI-style spending insights: users upload a transaction CSV, the app computes totals and breakdowns in code, then a small LLM writes a grounded JSON summary. Built as an assignment-style web app (BHIM / GPay / PhonePe / Paytm problem: people transact a lot but rarely review spend).

## What we are building

A web app that:

1. Accepts a CSV (`date,merchant,amount,type` with Credit/Debit).
2. Parses and shows uploaded rows.
3. Computes basic analytics: total income, total expense, net savings, transaction count.
4. Merchant analysis: top merchants, most frequent, highest spend.
5. Rule-based categories: Food, Travel, Shopping, Bills, Entertainment, Others (credits like Salary stay Income, not in the expense pie).
6. AI insights in natural language as **JSON** (`headline`, `highlights`, `watchouts`).

UI is a dark Next.js + shadcn dashboard (analyzer + observability).

## Hybrid approach (locked)

- **Pandas / Python owns the money.** Totals, rankings, category %, weekend share are computed from the file.
- **LLM last, and only as a narrator.** It never sees raw rows. It receives ~20 aggregated facts and must not invent merchants, amounts, or percentages.
- **Structured output.** LangChain `with_structured_output(InsightSummary)` so the UI does not parse free prose.
- **Template fallback.** If `OPENAI_API_KEY` (or the current provider key) is missing or the call fails, the **same JSON schema** is filled from templates. `insights_source` is `"llm"` or `"template"`.
- **No LLM categorization.** Merchant → category is a dictionary in `backend/app/pipeline/categorize.py`.

Analytics definitions (UI and LLM must agree):

- Income = sum of Credit amounts
- Expense = sum of Debit amounts
- Net savings = Income − Expense
- Highest spend merchant = max debit **sum**
- Most frequent merchant = max debit **count** (tie: higher spend, then name)
- Category % = category debit / **total expense** (never divide by income)

## Tech stack

| Layer | Choice |
| --- | --- |
| API | FastAPI (`POST /analyze`, `GET /health`, `GET /observability`) |
| Data | pandas |
| LLM | LangChain `init_chat_model("{LLM_PROVIDER}:{LLM_MODEL}")` |
| Default model | OpenAI `gpt-4o-mini` |
| Output | Pydantic `InsightSummary` JSON |
| Frontend | Next.js + shadcn/ui (`frontend/` on 5173; `/observability` for latency) |
| Python tooling | **uv** (`backend/pyproject.toml` + lock). Do not use pip / `python -m venv` as the workflow. |

No database, auth, agents, RAG, or vector store.

## File layout

```
CONTEXT.md
README.md
sample_data/transactions.csv
backend/
  pyproject.toml
  .env.example
  app/
    main.py              FastAPI app + CORS + router registration
    schemas/             Pydantic models (FactsPayload, InsightSummary, ...)
    db/                  SQLite persistence
    pipeline/            CSV parse, merchant categories, KPI analytics
      parser.py
      categorize.py
      analytics.py
    llm/                 model factory, insights, chat agent, tools
      client.py
      insights.py
      chat.py
      tools.py
    observability/       step timing + token/cost tracking
    prompts/             LLM system prompts (separate from runtime logic)
      insights.py
      chat.py
    routes/              HTTP route handlers (one router per concern)
      health.py          GET /health
      observability.py   GET /observability
      analyze.py         POST /analyze (+ rate limiter + guardrails)
      datasets.py        GET /datasets/{id}, POST .../chat, GET .../messages
frontend/
  src/app/page.tsx                 analyzer
  src/app/observability/page.tsx   latency dashboard
```

## Endpoints

- `GET /health` → `{ "ok": true }`
- `POST /analyze` multipart field `file` (`.csv`) → `{ rows, facts, insights, insights_source }`
- `GET /observability` → in-memory step timings for the last 50 `/analyze` calls (`avg_ms`, `max_ms`, `bottleneck`, `recent`). Steps: `read_file`, `parse_csv`, `categorize`, `analytics`, `insights`, `serialize_rows`.

Frontend (port 5173) rewrites `/api/backend/analyze`, `/api/backend/health`, and `/api/backend/observability` to FastAPI on port 8000. Observability is `/observability` in the same app. Restarting uvicorn clears in-memory timings.

## Insight JSON

```json
{
  "headline": "Food delivery dominated this month's spending.",
  "highlights": ["You spent 42% of expenses on Food."],
  "watchouts": ["Food spend is significantly higher than Shopping."]
}
```

Facts sent to the model (example shape): `income`, `expense`, `savings`, `transaction_count`, `top_merchants`, `most_frequent_merchant`, `highest_spend_merchant`, `categories` (`name`, `amount`, `pct_of_expense`), `weekend_pct_of_expense`.

## Switch LLM (env only)

In `backend/.env`:

```
LLM_PROVIDER=openai
LLM_MODEL=gpt-4o-mini
OPENAI_API_KEY=...
```

Change provider name + model + that provider’s API key. No provider-specific SDKs in app code. Install the matching `langchain-*` package if you leave OpenAI/Groq (both are already in project deps).

## Run

See [README.md](README.md). Backend: `cd backend && uv sync && uv run uvicorn app.main:app --reload --port 8000`. Frontend: `cd frontend && npm run dev` (analyzer at `/`, latency at `/observability`).
