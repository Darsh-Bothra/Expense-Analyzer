# Observability

`GET /observability` returns aggregates over the last **50** `/analyze` and `/chat` runs. Rows live in SQLite (`runs` table in `backend/data/app.db`) so timings survive uvicorn restarts and Docker recreates the process (the compose volume `backend-data` mounts `/app/data`).

The dashboard at http://localhost:5173/observability polls this endpoint every 2 seconds. The old `observability-ui/` Vite app is a compatibility stub only.

## Snapshot shape

```json
{
  "request_count": 12,
  "bottleneck": { "step": "insights", "avg_ms": 410.2, "max_ms": 890.0 },
  "avg_ms": { "read_file": 1.2, "parse": 8.4, "insights": 410.2, "total": 430.1 },
  "max_ms": { "insights": 890.0, "total": 920.0 },
  "tokens_in": 12000,
  "tokens_out": 800,
  "cost_usd": 0.0021,
  "recent": []
}
```

`bottleneck` is the step with the highest **average** latency among named steps (not `total`). Token and cost fields are sums over the same 50-run window.

Each `recent` entry includes `at`, `endpoint` (`/analyze` or `/chat`), `filename`, `row_count`, `insights_source`, `ok`, `error`, `steps_ms`, `total_ms`, `slowest_step`, `tokens_in`, `tokens_out`, `cost_usd`. Parse errors and oversized files record a failed run. Rate-limited `/analyze` requests return `429` before `record_run`.

## Analyze steps

Timed in `POST /analyze`:

1. `read_file`
2. `parse`
3. `categorize`
4. `analytics`
5. `insights`
6. `serialize_rows` (includes persisting the dataset)

Chat records a wall-clock `total_ms` for the whole `/chat` call; it does not use the analyze step names.

## Tokens and cost

Usage is read from the LangChain AI message (`usage_metadata` or provider `response_metadata`). Cost is a best-effort estimate from `LLM_MODEL` and a small per-1M-token table in `backend/app/observability/tracker.py` (unknown models → `0`). Template fallbacks report zero tokens and zero cost.

Observability writes must not fail the user request: `record_run` swallows insert errors.
