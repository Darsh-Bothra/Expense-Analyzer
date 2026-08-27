# Chat agent

After `/analyze`, the upload is stored in SQLite and the UI can ask questions about **that** statement. The model never runs free SQL and is not given the full row list in the system prompt.

## Persistence

Each successful analyze writes:

- `datasets` — id, filename, facts JSON, insights JSON, source
- `transactions` — categorized rows for that dataset
- later `chat_messages` — user/assistant turns plus optional tool traces

The analyzer keeps `dataset_id` in `localStorage` (`expense-analyzer-dataset-id`) so a refresh can `GET /datasets/{id}` and reload chat history.

## How a turn works

1. The user message is appended to `chat_messages`.
2. If no provider API key (or the LLM call fails), the reply is a **template** KPI sentence from stored facts (`source: template`). No tools run.
3. Otherwise the model is bound to five tools scoped to this `dataset_id`. Up to **3** tool rounds; then a stop message forces a text answer.
4. The last **10** stored user/assistant turns are sent as history (not tool JSON).
5. Dates in “this month / this year” are interpreted from the **statement span**, not today’s calendar.

## Tools

Implemented in `backend/app/llm/tools.py`. Each tool loads the dataset with pandas and returns JSON.

| Tool | What it computes |
| --- | --- |
| `get_kpis` | Full `FactsPayload` (income, expense, savings, top merchants, categories, weekend %) |
| `spend_by_merchant` | Debit totals by merchant; optional name substring and date range; `top_n` 1–20 |
| `spend_by_category` | Debit spend by category; optional category and dates |
| `list_transactions` | Filtered rows, **at most 25** returned (`match_count` still reports the full hit count) |
| `period_compare` | KPIs for two date ranges, or `preset=this_month_vs_last` from the latest date in the file |

Filters (where applicable): inclusive `date_from` / `date_to` (`YYYY-MM-DD`), merchant substring (case-insensitive, not regex), `Credit`/`Debit`, category (including Income), amount min/max.

## Grounding rules

The chat system prompt requires the model to call tools for numbers, use only tool JSON, and speak in INR. Unknown tools or tool exceptions come back as `{"error": "..."}` so the model can retry arguments.

## UI

`frontend/src/components/expense-chat.tsx` sits on the analyzer page. Suggested prompts: spend on Swiggy, Food vs Shopping, top merchant. Assistant bubbles can show which tools ran.
