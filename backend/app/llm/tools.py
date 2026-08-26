import json
from typing import Literal

import pandas as pd
from langchain_core.tools import StructuredTool
from pydantic import BaseModel, Field

from app.pipeline.analytics import EXPENSE_CATEGORIES, build_facts
from app.db import load_transactions_df

VALID_CATEGORIES = (*EXPENSE_CATEGORIES, "Income")
VALID_TYPES = ("Credit", "Debit")
LIST_LIMIT = 25


def _parse_day(value: str | None, field: str) -> pd.Timestamp | None:
    if value is None or str(value).strip() == "":
        return None
    parsed = pd.to_datetime(str(value).strip(), errors="coerce")
    if pd.isna(parsed):
        raise ValueError(f"{field} must be a valid date (YYYY-MM-DD).")
    return pd.Timestamp(parsed).normalize()


def _apply_filters(
    df: pd.DataFrame,
    *,
    date_from: str | None = None,
    date_to: str | None = None,
    merchant: str | None = None,
    txn_type: str | None = None,
    category: str | None = None,
    amount_min: float | None = None,
    amount_max: float | None = None,
) -> pd.DataFrame:
    out = df
    start = _parse_day(date_from, "date_from")
    end = _parse_day(date_to, "date_to")
    if start is not None and end is not None and start > end:
        raise ValueError("date_from must be on or before date_to.")
    if start is not None:
        out = out[out["date"] >= start]
    if end is not None:
        out = out[out["date"] < end + pd.Timedelta(days=1)]
    if merchant:
        needle = merchant.strip()
        if needle:
            out = out[out["merchant"].str.contains(needle, case=False, na=False, regex=False)]
    if txn_type:
        title = txn_type.strip().title()
        if title not in VALID_TYPES:
            raise ValueError("type must be Credit or Debit.")
        out = out[out["type"] == title]
    if category:
        name = category.strip()
        if name not in VALID_CATEGORIES:
            raise ValueError(
                f"category must be one of: {', '.join(VALID_CATEGORIES)}."
            )
        out = out[out["category"] == name]
    if amount_min is not None:
        out = out[out["amount"] >= float(amount_min)]
    if amount_max is not None:
        out = out[out["amount"] <= float(amount_max)]
    return out


def _kpis_dict(df: pd.DataFrame) -> dict:
    if df.empty:
        return {
            "income": 0.0,
            "expense": 0.0,
            "savings": 0.0,
            "transaction_count": 0,
        }
    facts = build_facts(df)
    return {
        "income": facts.income,
        "expense": facts.expense,
        "savings": facts.savings,
        "transaction_count": facts.transaction_count,
        "weekend_pct_of_expense": facts.weekend_pct_of_expense,
    }


def _dumps(payload: dict) -> str:
    return json.dumps(payload, default=str)


class EmptyInput(BaseModel):
    pass


class DateRangeInput(BaseModel):
    date_from: str | None = Field(None, description="Inclusive start date YYYY-MM-DD")
    date_to: str | None = Field(None, description="Inclusive end date YYYY-MM-DD")


class SpendByMerchantInput(DateRangeInput):
    merchant: str | None = Field(
        None,
        description="Optional merchant name substring (case-insensitive)",
    )
    top_n: int = Field(5, ge=1, le=20, description="How many merchants to return")


class SpendByCategoryInput(DateRangeInput):
    category: str | None = Field(
        None,
        description="Optional category: Food, Travel, Shopping, Bills, Entertainment, Others, Income",
    )


class ListTransactionsInput(DateRangeInput):
    merchant: str | None = Field(None, description="Optional merchant substring")
    type: Literal["Credit", "Debit"] | None = Field(
        None, description="Credit or Debit"
    )
    category: str | None = Field(
        None,
        description="Food, Travel, Shopping, Bills, Entertainment, Others, or Income",
    )
    amount_min: float | None = Field(None, ge=0)
    amount_max: float | None = Field(None, ge=0)
    limit: int = Field(25, ge=1, le=LIST_LIMIT)


class PeriodCompareInput(BaseModel):
    preset: Literal["this_month_vs_last"] | None = Field(
        None,
        description="If set, compare the latest month in the data with the previous month",
    )
    date_from_a: str | None = Field(None, description="Period A start YYYY-MM-DD")
    date_to_a: str | None = Field(None, description="Period A end YYYY-MM-DD")
    date_from_b: str | None = Field(None, description="Period B start YYYY-MM-DD")
    date_to_b: str | None = Field(None, description="Period B end YYYY-MM-DD")


def _month_windows(df: pd.DataFrame) -> tuple[pd.Timestamp, pd.Timestamp, pd.Timestamp, pd.Timestamp]:
    if df.empty:
        raise ValueError("No transactions in this dataset.")
    max_d = pd.Timestamp(df["date"].max()).normalize()
    this_start = max_d.replace(day=1)
    this_end = max_d
    last_end = this_start - pd.Timedelta(days=1)
    last_start = last_end.replace(day=1)
    return last_start, last_end, this_start, this_end


def make_tools(dataset_id: str) -> list[StructuredTool]:
    def get_kpis() -> str:
        """Return income, expense, savings, transaction count, and weekend spend share for the whole statement."""
        try:
            df = load_transactions_df(dataset_id)
            facts = build_facts(df)
            return facts.model_dump_json()
        except Exception as exc:
            return _dumps({"error": str(exc)})

    def spend_by_merchant(
        merchant: str | None = None,
        top_n: int = 5,
        date_from: str | None = None,
        date_to: str | None = None,
    ) -> str:
        """Debit spend grouped by merchant, optionally filtered by name substring and date range."""
        try:
            df = load_transactions_df(dataset_id)
            filtered = _apply_filters(
                df, date_from=date_from, date_to=date_to, merchant=merchant
            )
            debits = filtered[filtered["type"] == "Debit"]
            if debits.empty:
                return _dumps({"merchants": [], "match_count": 0})
            grouped = (
                debits.groupby("merchant", as_index=False)
                .agg(amount=("amount", "sum"), count=("amount", "size"))
                .sort_values(["amount", "count", "merchant"], ascending=[False, False, True])
            )
            n = max(1, min(int(top_n), 20))
            merchants = [
                {
                    "name": str(row["merchant"]),
                    "amount": round(float(row["amount"]), 2),
                    "count": int(row["count"]),
                }
                for _, row in grouped.head(n).iterrows()
            ]
            return _dumps({"merchants": merchants, "match_count": int(len(grouped))})
        except Exception as exc:
            return _dumps({"error": str(exc)})

    def spend_by_category(
        category: str | None = None,
        date_from: str | None = None,
        date_to: str | None = None,
    ) -> str:
        """Debit spend grouped by category (Food, Travel, Shopping, Bills, Entertainment, Others)."""
        try:
            df = load_transactions_df(dataset_id)
            scoped = _apply_filters(df, date_from=date_from, date_to=date_to)
            if scoped.empty:
                return _dumps({"categories": [], "expense": 0})
            facts = build_facts(scoped)
            cats = [c.model_dump() for c in facts.categories]
            if category and category != "Income":
                cats = [c for c in cats if c["name"] == category]
            return _dumps(
                {
                    "categories": cats,
                    "expense": facts.expense,
                    "income": facts.income,
                }
            )
        except Exception as exc:
            return _dumps({"error": str(exc)})

    def list_transactions(
        merchant: str | None = None,
        type: str | None = None,
        category: str | None = None,
        amount_min: float | None = None,
        amount_max: float | None = None,
        date_from: str | None = None,
        date_to: str | None = None,
        limit: int = LIST_LIMIT,
    ) -> str:
        """Return a capped list of matching transactions (never more than 25 rows)."""
        try:
            df = load_transactions_df(dataset_id)
            filtered = _apply_filters(
                df,
                date_from=date_from,
                date_to=date_to,
                merchant=merchant,
                txn_type=type,
                category=category,
                amount_min=amount_min,
                amount_max=amount_max,
            )
            cap = max(1, min(int(limit), LIST_LIMIT))
            sample = filtered.head(cap)
            rows = [
                {
                    "date": row.date.strftime("%Y-%m-%d"),
                    "merchant": row.merchant,
                    "amount": round(float(row.amount), 2),
                    "type": row.type,
                    "category": row.category,
                }
                for row in sample.itertuples()
            ]
            return _dumps(
                {
                    "match_count": int(len(filtered)),
                    "returned": len(rows),
                    "limit": cap,
                    "rows": rows,
                }
            )
        except Exception as exc:
            return _dumps({"error": str(exc)})

    def period_compare(
        preset: str | None = None,
        date_from_a: str | None = None,
        date_to_a: str | None = None,
        date_from_b: str | None = None,
        date_to_b: str | None = None,
    ) -> str:
        """Compare income/expense/savings between two date ranges, or this month vs last month."""
        try:
            df = load_transactions_df(dataset_id)
            if preset == "this_month_vs_last":
                a_from, a_to, b_from, b_to = _month_windows(df)
                date_from_a = a_from.strftime("%Y-%m-%d")
                date_to_a = a_to.strftime("%Y-%m-%d")
                date_from_b = b_from.strftime("%Y-%m-%d")
                date_to_b = b_to.strftime("%Y-%m-%d")
            elif not all([date_from_a, date_to_a, date_from_b, date_to_b]):
                raise ValueError(
                    "Provide preset=this_month_vs_last or all four dates: "
                    "date_from_a, date_to_a, date_from_b, date_to_b."
                )
            period_a = _apply_filters(df, date_from=date_from_a, date_to=date_to_a)
            period_b = _apply_filters(df, date_from=date_from_b, date_to=date_to_b)
            return _dumps(
                {
                    "period_a": {
                        "date_from": date_from_a,
                        "date_to": date_to_a,
                        **_kpis_dict(period_a),
                    },
                    "period_b": {
                        "date_from": date_from_b,
                        "date_to": date_to_b,
                        **_kpis_dict(period_b),
                    },
                }
            )
        except Exception as exc:
            return _dumps({"error": str(exc)})

    return [
        StructuredTool.from_function(
            func=get_kpis,
            name="get_kpis",
            description=(
                "Return overall income, expense, net savings, transaction count, "
                "top merchants, categories, and weekend spend share."
            ),
            args_schema=EmptyInput,
        ),
        StructuredTool.from_function(
            func=spend_by_merchant,
            name="spend_by_merchant",
            description=(
                "Sum debit spend by merchant. Filter with merchant substring and optional dates."
            ),
            args_schema=SpendByMerchantInput,
        ),
        StructuredTool.from_function(
            func=spend_by_category,
            name="spend_by_category",
            description="Sum debit spend by category with optional category name and dates.",
            args_schema=SpendByCategoryInput,
        ),
        StructuredTool.from_function(
            func=list_transactions,
            name="list_transactions",
            description=(
                "List matching transactions with filters. At most 25 rows are returned."
            ),
            args_schema=ListTransactionsInput,
        ),
        StructuredTool.from_function(
            func=period_compare,
            name="period_compare",
            description=(
                "Compare KPIs for two date ranges, or use preset this_month_vs_last "
                "based on the latest date in the statement."
            ),
            args_schema=PeriodCompareInput,
        ),
    ]
