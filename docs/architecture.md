# Architecture

UPI-style spending insights: users upload a transaction CSV or Excel (`.xlsx`), the app computes totals and breakdowns in code, then a small LLM writes a grounded JSON summary. Chat on a persisted upload uses the same split: pandas owns the money; the model only narrates tool results.

## Hybrid approach

- **Pandas / Python owns the money.** Totals, rankings, category %, and weekend share are computed from the file (and again inside chat tools).
- **LLM last, and only as a narrator.** Insights never see raw rows. The model receives aggregated facts (~20 numbers and names) and must not invent merchants, amounts, or percentages.
- **Structured output.** LangChain `with_structured_output(InsightSummary)` so the UI does not parse free prose.
- **Template fallback.** If the current provider key is missing or the call fails, the **same JSON schema** is filled from templates. `insights_source` is `"llm"` or `"template"`. Chat uses the same idea (`source` on the chat response).
- **No LLM categorization.** Merchant → category is a dictionary in `backend/app/pipeline/categorize.py`.

## Analytics definitions

UI, insights, and chat tools must agree:

- Income = sum of Credit amounts
- Expense = sum of Debit amounts
- Net savings = Income − Expense
- Highest spend merchant = max debit **sum**
- Most frequent merchant = max debit **count** (tie: higher spend, then name)
- Category % = category debit / **total expense** (never divide by income)
- Credits such as Salary stay **Income** and are not in the expense pie

Expense categories: Food, Travel, Shopping, Bills, Entertainment, Others.

## Pipeline

1. Accept CSV or `.xlsx` (`date`, `merchant`, `amount`, `type`; Excel: first sheet).
2. Parse and drop invalid rows (bad dates, empty merchant, negative amount, type not Credit/Debit).
3. Assign categories from the merchant map.
4. Compute `FactsPayload` (KPIs, top merchants, categories, weekend share).
5. Generate `InsightSummary` JSON (`headline`, `highlights`, `watchouts`).
6. Persist the dataset in SQLite and return rows + facts + insights + `dataset_id`.
7. Chat loads that dataset and calls typed tools (see [chat.md](chat.md)).

## Tech stack

| Layer | Choice |
| --- | --- |
| API | FastAPI |
| Data | pandas (+ openpyxl for `.xlsx`) |
| Persistence | SQLite (`backend/data/app.db`) |
| LLM | LangChain `init_chat_model("{LLM_PROVIDER}:{LLM_MODEL}")` |
| Default model | OpenAI `gpt-4o-mini` |
| Insights output | Pydantic `InsightSummary` JSON |
| Frontend | Next.js + shadcn/ui (`frontend/` on 5173) |
| Python tooling | **uv** (`backend/pyproject.toml` + lock) |

No auth, RAG, or vector store. Chat is a constrained tool-calling agent, not free SQL.

## File layout

```
CONTEXT.md                 Pointer to this folder
README.md
docs/
  architecture.md
  api.md
  chat.md
  observability.md
sample_data/transactions.csv
sample_data/transactions.xlsx
sample_data/transactions_1000.csv
backend/
  pyproject.toml
  .env.example
  app/
    main.py
    schemas/
    db/
    pipeline/            parser.py, categorize.py, analytics.py
    llm/                 client.py, insights.py, chat.py, tools.py
    observability/
    prompts/             insights.py, chat.py
    routes/              health, observability, analyze, datasets
frontend/
  src/app/page.tsx
  src/app/observability/page.tsx
```

## Switch LLM (env only)

In `backend/.env`:

```
LLM_PROVIDER=openai
LLM_MODEL=gpt-4o-mini
OPENAI_API_KEY=...
```

Change provider name + model + that provider’s API key. App code does not import provider-specific SDKs beyond LangChain’s factory. `langchain-openai` and `langchain-groq` are already in project deps; install `langchain-google-genai` or `langchain-anthropic` if you switch to those.

## Run

See [README.md](../README.md).
