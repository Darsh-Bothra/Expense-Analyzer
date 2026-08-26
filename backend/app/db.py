import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4

import pandas as pd

from app.schemas import FactsPayload, InsightSummary, TransactionRow

DB_PATH = Path(__file__).resolve().parents[1] / "data" / "app.db"

_SCHEMA = """
CREATE TABLE IF NOT EXISTS datasets (
  id TEXT PRIMARY KEY,
  filename TEXT NOT NULL,
  created_at TEXT NOT NULL,
  facts_json TEXT NOT NULL,
  insights_json TEXT NOT NULL,
  insights_source TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS transactions (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  dataset_id TEXT NOT NULL,
  date TEXT NOT NULL,
  merchant TEXT NOT NULL,
  amount REAL NOT NULL,
  type TEXT NOT NULL,
  category TEXT NOT NULL,
  FOREIGN KEY (dataset_id) REFERENCES datasets(id)
);

CREATE INDEX IF NOT EXISTS idx_txn_dataset_date ON transactions(dataset_id, date);
CREATE INDEX IF NOT EXISTS idx_txn_dataset_merchant ON transactions(dataset_id, merchant);

CREATE TABLE IF NOT EXISTS chat_messages (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  dataset_id TEXT NOT NULL,
  role TEXT NOT NULL,
  content TEXT NOT NULL,
  tool_trace TEXT,
  created_at TEXT NOT NULL,
  FOREIGN KEY (dataset_id) REFERENCES datasets(id)
);

CREATE INDEX IF NOT EXISTS idx_chat_dataset ON chat_messages(dataset_id, id);

CREATE TABLE IF NOT EXISTS runs (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  at TEXT NOT NULL,
  endpoint TEXT NOT NULL,
  filename TEXT,
  row_count INTEGER,
  insights_source TEXT,
  ok INTEGER NOT NULL,
  error TEXT,
  steps_ms TEXT,
  total_ms REAL,
  slowest_step TEXT,
  tokens_in INTEGER,
  tokens_out INTEGER,
  cost_usd REAL
);

CREATE INDEX IF NOT EXISTS idx_runs_at ON runs(at DESC);
"""


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def connect() -> sqlite3.Connection:
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def init_db() -> None:
    with connect() as conn:
        conn.executescript(_SCHEMA)
        conn.commit()


def persist_dataset(
    filename: str,
    df: pd.DataFrame,
    facts: FactsPayload,
    insights: InsightSummary,
    insights_source: str,
) -> str:
    dataset_id = str(uuid4())
    rows = [
        (
            dataset_id,
            row.date.strftime("%Y-%m-%d"),
            str(row.merchant),
            float(row.amount),
            str(row.type),
            str(row.category),
        )
        for row in df.itertuples()
    ]
    with connect() as conn:
        conn.execute(
            """
            INSERT INTO datasets (id, filename, created_at, facts_json, insights_json, insights_source)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (
                dataset_id,
                filename,
                _utc_now(),
                facts.model_dump_json(),
                insights.model_dump_json(),
                insights_source,
            ),
        )
        conn.executemany(
            """
            INSERT INTO transactions (dataset_id, date, merchant, amount, type, category)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            rows,
        )
        conn.commit()
    return dataset_id


def dataset_exists(dataset_id: str) -> bool:
    with connect() as conn:
        row = conn.execute("SELECT 1 FROM datasets WHERE id = ?", (dataset_id,)).fetchone()
    return row is not None


def get_dataset_meta(dataset_id: str) -> dict | None:
    with connect() as conn:
        row = conn.execute(
            """
            SELECT id, filename, created_at, facts_json, insights_json, insights_source
            FROM datasets WHERE id = ?
            """,
            (dataset_id,),
        ).fetchone()
    if row is None:
        return None
    return {
        "dataset_id": row["id"],
        "filename": row["filename"],
        "created_at": row["created_at"],
        "facts": FactsPayload.model_validate_json(row["facts_json"]),
        "insights": InsightSummary.model_validate_json(row["insights_json"]),
        "insights_source": row["insights_source"],
    }


def load_transactions_df(dataset_id: str) -> pd.DataFrame:
    with connect() as conn:
        df = pd.read_sql_query(
            """
            SELECT date, merchant, amount, type, category
            FROM transactions
            WHERE dataset_id = ?
            ORDER BY date, id
            """,
            conn,
            params=(dataset_id,),
        )
    if df.empty:
        return df
    df["date"] = pd.to_datetime(df["date"])
    df["amount"] = pd.to_numeric(df["amount"])
    return df


def list_transaction_rows(dataset_id: str) -> list[TransactionRow]:
    df = load_transactions_df(dataset_id)
    return [
        TransactionRow(
            date=row.date.strftime("%Y-%m-%d"),
            merchant=row.merchant,
            amount=float(row.amount),
            type=row.type,
            category=row.category,
        )
        for row in df.itertuples()
    ]


def append_chat_message(
    dataset_id: str,
    role: str,
    content: str,
    tool_trace: list | None = None,
) -> None:
    with connect() as conn:
        conn.execute(
            """
            INSERT INTO chat_messages (dataset_id, role, content, tool_trace, created_at)
            VALUES (?, ?, ?, ?, ?)
            """,
            (
                dataset_id,
                role,
                content,
                json.dumps(tool_trace) if tool_trace is not None else None,
                _utc_now(),
            ),
        )
        conn.commit()


def list_chat_messages(dataset_id: str, limit: int | None = None) -> list[dict]:
    sql = """
        SELECT role, content, tool_trace, created_at
        FROM chat_messages
        WHERE dataset_id = ?
        ORDER BY id
    """
    with connect() as conn:
        rows = conn.execute(sql, (dataset_id,)).fetchall()
    messages = []
    for row in rows:
        trace = json.loads(row["tool_trace"]) if row["tool_trace"] else None
        messages.append(
            {
                "role": row["role"],
                "content": row["content"],
                "tool_trace": trace,
                "created_at": row["created_at"],
            }
        )
    if limit is not None and len(messages) > limit:
        return messages[-limit:]
    return messages


def insert_run(entry: dict) -> None:
    with connect() as conn:
        conn.execute(
            """
            INSERT INTO runs (
              at, endpoint, filename, row_count, insights_source, ok, error,
              steps_ms, total_ms, slowest_step, tokens_in, tokens_out, cost_usd
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                entry["at"],
                entry["endpoint"],
                entry.get("filename"),
                entry.get("row_count"),
                entry.get("insights_source"),
                1 if entry.get("ok") else 0,
                entry.get("error"),
                json.dumps(entry.get("steps_ms") or {}),
                entry.get("total_ms"),
                entry.get("slowest_step"),
                entry.get("tokens_in"),
                entry.get("tokens_out"),
                entry.get("cost_usd"),
            ),
        )
        conn.commit()


def list_recent_runs(limit: int = 50) -> list[dict]:
    with connect() as conn:
        rows = conn.execute(
            """
            SELECT at, endpoint, filename, row_count, insights_source, ok, error,
                   steps_ms, total_ms, slowest_step, tokens_in, tokens_out, cost_usd
            FROM runs
            ORDER BY id DESC
            LIMIT ?
            """,
            (limit,),
        ).fetchall()
    out = []
    for row in rows:
        out.append(
            {
                "at": row["at"],
                "endpoint": row["endpoint"],
                "filename": row["filename"],
                "row_count": row["row_count"],
                "insights_source": row["insights_source"],
                "ok": bool(row["ok"]),
                "error": row["error"],
                "steps_ms": json.loads(row["steps_ms"]) if row["steps_ms"] else {},
                "total_ms": row["total_ms"],
                "slowest_step": row["slowest_step"],
                "tokens_in": row["tokens_in"],
                "tokens_out": row["tokens_out"],
                "cost_usd": row["cost_usd"],
            }
        )
    return out
