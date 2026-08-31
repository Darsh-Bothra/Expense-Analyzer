# Expense Analyzer

Upload a UPI-style transaction CSV or Excel (`.xlsx`), get spend totals plus merchant and category breakdowns, then a grounded JSON summary from a small LLM (or a template if no API key). After upload, ask questions about that statement in chat; the model calls typed analytics tools instead of inventing numbers.

**Live demo:** [https://expenseanalyze.work.gd](https://expenseanalyze.work.gd) — AWS EC2, Docker Compose, Nginx, HTTPS. The instance may be stopped when idle; see [docs/deployment/](docs/deployment/).

## Docs

| File | Contents |
| --- | --- |
| [docs/architecture.md](docs/architecture.md) | Hybrid pipeline, analytics definitions, layout, LLM switch |
| [docs/api.md](docs/api.md) | HTTP endpoints, request/response shapes, `/analyze` guardrails |
| [docs/chat.md](docs/chat.md) | Persisted datasets, tool-calling agent, template fallback |
| [docs/observability.md](docs/observability.md) | Step latency, tokens, estimated cost |
| [docs/deployment/](docs/deployment/) | AWS EC2 layout, TLS, day-to-day ops, shipping updates |

## Layout

```
backend/app/
  main.py                 FastAPI app + CORS + router registration
  schemas/                Pydantic request/response models
  db/                     SQLite (datasets, rows, chat, run timings)
  pipeline/               CSV/XLSX parse, merchant categories, KPI analytics
  llm/                    model factory, insights, chat agent, tools
  observability/          step timing + token/cost tracking
  prompts/                LLM system prompts
  routes/                 health, observability, analyze, datasets/chat
frontend/                 Next.js + shadcn UI (port 5173)
  /                       Analyzer + chat
  /observability          Latency + token/cost dashboard
observability-ui/         Compatibility stub (dashboard lives in frontend)
sample_data/              Example CSV and XLSX
docker-compose.yml        Backend + frontend with healthchecks
docs/                     Architecture, API, and deployment notes
```

## Run

### Option A — Docker Compose

```bash
docker compose up --build
```

Backend: http://localhost:8000  
Frontend: http://localhost:5173

The backend container has a `/health` healthcheck; the frontend waits until it is healthy. SQLite is stored in the `backend-data` volume so datasets, chat history, and observability timings survive restarts.

Optional LLM key (without it, insights and chat use the template fallback):

```bash
OPENAI_API_KEY=sk-... docker compose up --build
```

### Option B — Local dev

Backend uses **uv** (not pip / `python -m venv`). From `backend/`:

```bash
cp .env.example .env   # first time only
uv sync
uv run uvicorn app.main:app --reload --port 8000
```

Frontend (from `frontend/`):

```bash
npm install
npm run dev
```

Open http://localhost:5173 and upload `sample_data/transactions.csv`, `sample_data/transactions.xlsx`, or `sample_data/paytm_passbook_sample.xlsx` (select **Passbook Payment History**).

Observability is in the same app at http://localhost:5173/observability. Next.js rewrites `/api/backend/*` to FastAPI on port 8000.

Without an API key, insights still appear (`insights_source: template`) and chat returns a KPI summary (`source: template`).

## Tests

Backend, from `backend/`:

```bash
uv sync
uv run pytest
```

Frontend, from `frontend/`:

```bash
npm install
npm test
npm run test:watch
```

Backend tests cover the parser, analytics, categorization, agent tools, chat template fallback, and `/analyze` + `/observability`. Frontend tests cover aggregation helpers in `frontend/src/lib/aggregate.ts`.

## File format

Columns: `date,merchant,amount,type` with `Credit` / `Debit`. Excel uses the first worksheet only (`.xlsx`, not legacy `.xls`).

## Switch LLM (no code change)

In `backend/.env`:

```
LLM_PROVIDER=openai
LLM_MODEL=gpt-4o-mini
OPENAI_API_KEY=your_key
```

Examples: `groq` + `llama-3.1-8b-instant` + `GROQ_API_KEY`, or `google_genai` + `gemini-2.0-flash` + `GOOGLE_API_KEY` (install the matching `langchain-*` package if needed). See [docs/architecture.md](docs/architecture.md).
