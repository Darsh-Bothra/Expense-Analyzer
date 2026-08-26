# Expense Analyzer

Upload a UPI-style transaction CSV or Excel (.xlsx), get spend totals, merchant and category breakdowns, then a grounded JSON summary from a small LLM (or a template if no API key).

See [CONTEXT.md](CONTEXT.md) for architecture, schemas, and how the hybrid pipeline works.

## Layout

```
backend/
  app/
    main.py                 FastAPI app + CORS + router registration
    schemas/                Pydantic request/response models
    db/                     SQLite persistence
    pipeline/               CSV/XLSX parse, merchant categories, KPI analytics
      parser.py
      categorize.py
      analytics.py
    llm/                    model factory, insights, chat agent, tools
      client.py
      insights.py
      chat.py
      tools.py
    observability/          step timing + token/cost tracking
    prompts/                LLM system prompts (separate from runtime logic)
      insights.py
      chat.py
    routes/                 HTTP route handlers (one router per concern)
      health.py             GET /health
      observability.py      GET /observability
      analyze.py            POST /analyze (+ rate limiter + guardrails)
      datasets.py           GET /datasets/{id}, POST .../chat, GET .../messages
frontend/                   Next.js + shadcn UI (port 5173)
  /                         Analyzer
  /observability            Latency + token/cost dashboard
sample_data/                Example CSV and XLSX
docker-compose.yml          One-command run (backend + frontend + healthcheck)
```

## Run

### Option A — Docker Compose (one command)

```bash
docker compose up --build
```

Backend on http://localhost:8000, frontend on http://localhost:5173.
The backend container has a `/health` healthcheck; the frontend waits for it
(`depends_on: condition: service_healthy`). SQLite is persisted in a named
volume (`backend-data`) so observability timings and datasets survive restarts.

Set an LLM key via env before bringing the stack up (optional — without it,
insights and chat fall back to the template):

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

Open http://localhost:5173 and upload `sample_data/transactions.csv` or `sample_data/transactions.xlsx`.

Observability lives in the same app at http://localhost:5173/observability. It
polls `GET /observability` every 2s via a Next.js rewrite to port 8000. Analyze
still goes 5173 → 8000 only.

Without `OPENAI_API_KEY`, insights still appear (`insights_source: template`).

## Tests

Backend (pytest), from `backend/`:

```bash
uv sync                 # installs the dev dependency group (pytest, httpx)
uv run pytest
```

Frontend (vitest + React Testing Library), from `frontend/`:

```bash
npm install             # installs vitest + @testing-library/react
npm test               # one-shot
npm run test:watch     # watch mode
```

Backend tests cover the parser, analytics, categorization, agent tools, the
chat template fallback, and the `/analyze` + `/observability` endpoints.
Frontend tests cover the pure aggregation utilities in
`frontend/src/lib/aggregate.ts`.

## `/analyze` guardrails

Configurable via environment variables (backend):

| Variable | Default | Meaning |
| --- | --- | --- |
| `ANALYZE_MAX_FILE_BYTES` | `5242880` (5 MB) | Max uploaded CSV/XLSX size |
| `ANALYZE_MAX_ROWS` | `100000` | Max rows after parsing |
| `ANALYZE_RATE_LIMIT` | `20` | Max `/analyze` uploads per 60s per IP |

Oversized files and over-limit row counts return `413`; rate-limited requests
return `429`.

## Observability

`GET /observability` returns per-step latency averages/maxes, the bottleneck
step, and LLM token (`tokens_in`/`tokens_out`) and estimated `cost_usd` totals
for the last 50 `/analyze` and `/chat` runs. Timings are persisted in SQLite
(`backend/data/app.db`) and survive uvicorn restarts.

## Switch LLM (no code change)

In `backend/.env`:

```
LLM_PROVIDER=openai
LLM_MODEL=gpt-4o-mini
OPENAI_API_KEY=your_key
```

Examples: `groq` + `llama-3.1-8b-instant` + `GROQ_API_KEY`, or `google_genai` + `gemini-2.0-flash` + `GOOGLE_API_KEY` (install the matching `langchain-*` package if needed).

CSV or Excel columns: `date,merchant,amount,type` with `Credit` / `Debit`. Excel uses the first worksheet.
