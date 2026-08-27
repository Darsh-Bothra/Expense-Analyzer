# HTTP API

FastAPI on port 8000. The Next.js app on 5173 rewrites `/api/backend/*` to these paths.

Interactive docs: http://localhost:8000/docs

## Endpoints

| Method | Path | Purpose |
| --- | --- | --- |
| `GET` | `/health` | `{ "ok": true }` |
| `POST` | `/analyze` | Upload CSV/XLSX; return rows, facts, insights, `dataset_id` |
| `GET` | `/observability` | Last 50 analyze/chat runs (latency, tokens, cost) |
| `GET` | `/datasets/{id}` | Reload a persisted upload |
| `POST` | `/datasets/{id}/chat` | Ask a question about that dataset |
| `GET` | `/datasets/{id}/messages` | Chat history for that dataset |

## `POST /analyze`

Multipart field `file` (`.csv` or `.xlsx`).

Success body (`AnalyzeResponse`):

```json
{
  "rows": [{ "date": "2025-01-01", "merchant": "Swiggy", "amount": 450, "type": "Debit", "category": "Food" }],
  "facts": {
    "income": 50000,
    "expense": 12345,
    "savings": 37655,
    "transaction_count": 30,
    "top_merchants": [{ "name": "Amazon", "amount": 1500, "count": 1 }],
    "most_frequent_merchant": { "name": "Swiggy", "count": 4 },
    "highest_spend_merchant": { "name": "Amazon", "amount": 1500 },
    "categories": [{ "name": "Food", "amount": 2000, "pct_of_expense": 16.2 }],
    "weekend_pct_of_expense": 22.5
  },
  "insights": {
    "headline": "Food delivery dominated this month's spending.",
    "highlights": ["You spent 42% of expenses on Food."],
    "watchouts": ["Food spend is significantly higher than Shopping."]
  },
  "insights_source": "llm",
  "dataset_id": "uuid"
}
```

`insights_source` is `"llm"` or `"template"`.

Errors: `400` invalid file/type/parse, `413` file or row limit, `429` rate limit.

### Guardrails (environment)

| Variable | Default | Meaning |
| --- | --- | --- |
| `ANALYZE_MAX_FILE_BYTES` | `5242880` (5 MB) | Max uploaded CSV/XLSX size |
| `ANALYZE_MAX_ROWS` | `100000` | Max rows after parsing |
| `ANALYZE_RATE_LIMIT` | `20` | Max `/analyze` uploads per 60s per IP |

## `GET /datasets/{dataset_id}`

Returns filename, `created_at`, rows, facts, insights, and `insights_source`. `404` if unknown.

## `POST /datasets/{dataset_id}/chat`

JSON body: `{ "message": "How much did I spend on Swiggy?" }` (`message` length 1–2000).

Response (`ChatResponse`):

```json
{
  "reply": "You spent ₹1,670 on Swiggy (4 debit transactions).",
  "tool_calls": [{ "name": "spend_by_merchant", "args": { "merchant": "Swiggy" } }],
  "source": "llm"
}
```

`source` is `"llm"` or `"template"`. See [chat.md](chat.md).

## `GET /datasets/{dataset_id}/messages`

List of `{ role, content, tool_trace, created_at }`.

## `GET /observability`

See [observability.md](observability.md).

## Frontend proxy

Rewrites in `frontend/next.config.ts`:

- `/api/backend/analyze` → `/analyze`
- `/api/backend/health` → `/health`
- `/api/backend/observability` → `/observability`
- `/api/backend/datasets/:path*` → `/datasets/:path*`

`API_ORIGIN` defaults to `http://127.0.0.1:8000` and is `http://backend:8000` in Docker.
