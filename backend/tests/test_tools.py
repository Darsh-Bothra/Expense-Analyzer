import json

import pandas as pd
import pytest

from app.db import persist_dataset
from app.llm.insights import template_insights
from app.llm.tools import _apply_filters, make_tools
from app.pipeline.analytics import build_facts
from app.pipeline.categorize import add_categories


def _seed_dataset(rows) -> str:
    df = pd.DataFrame(rows)
    df["date"] = pd.to_datetime(df["date"])
    df["amount"] = pd.to_numeric(df["amount"])
    df = add_categories(df)
    facts = build_facts(df)
    insights = template_insights(facts)
    return persist_dataset("sample.csv", df, facts, insights, "template")


SAMPLE_ROWS = [
    {"date": "2025-01-01", "merchant": "Swiggy", "amount": 450, "type": "Debit"},
    {"date": "2025-01-02", "merchant": "Uber", "amount": 280, "type": "Debit"},
    {"date": "2025-01-03", "merchant": "Amazon", "amount": 1500, "type": "Debit"},
    {"date": "2025-01-04", "merchant": "Salary", "amount": 50000, "type": "Credit"},
    {"date": "2025-01-05", "merchant": "Netflix", "amount": 199, "type": "Debit"},
    {"date": "2025-01-06", "merchant": "Swiggy", "amount": 320, "type": "Debit"},
    {"date": "2025-02-01", "merchant": "Swiggy", "amount": 410, "type": "Debit"},
    {"date": "2025-02-02", "merchant": "Uber", "amount": 560, "type": "Debit"},
]


def _result_json(tool_output: str) -> dict:
    return json.loads(tool_output)


def test_get_kpis_tool():
    dataset_id = _seed_dataset(SAMPLE_ROWS)
    tools = {t.name: t for t in make_tools(dataset_id)}
    out = _result_json(tools["get_kpis"].invoke({}))
    assert out["income"] == 50000.0
    assert out["expense"] == pytest.approx(450 + 280 + 1500 + 199 + 320 + 410 + 560)
    assert out["transaction_count"] == 8


def test_spend_by_merchant_tool():
    dataset_id = _seed_dataset(SAMPLE_ROWS)
    tools = {t.name: t for t in make_tools(dataset_id)}
    out = _result_json(tools["spend_by_merchant"].invoke({"merchant": "swig", "top_n": 5}))
    merchants = out["merchants"]
    assert len(merchants) == 1
    assert merchants[0]["name"] == "Swiggy"
    assert merchants[0]["count"] == 3
    assert merchants[0]["amount"] == pytest.approx(450 + 320 + 410)


def test_spend_by_category_tool():
    dataset_id = _seed_dataset(SAMPLE_ROWS)
    tools = {t.name: t for t in make_tools(dataset_id)}
    out = _result_json(tools["spend_by_category"].invoke({"category": "Food"}))
    cats = out["categories"]
    assert len(cats) == 1
    assert cats[0]["name"] == "Food"


def test_list_transactions_tool_capped():
    dataset_id = _seed_dataset(SAMPLE_ROWS)
    tools = {t.name: t for t in make_tools(dataset_id)}
    out = _result_json(tools["list_transactions"].invoke({"limit": 25}))
    assert out["match_count"] == 8
    assert out["returned"] == 8
    assert out["limit"] == 25


def test_list_transactions_tool_filter_category():
    dataset_id = _seed_dataset(SAMPLE_ROWS)
    tools = {t.name: t for t in make_tools(dataset_id)}
    out = _result_json(tools["list_transactions"].invoke({"category": "Food"}))
    assert out["match_count"] == 3
    for row in out["rows"]:
        assert row["category"] == "Food"


def test_period_compare_preset():
    dataset_id = _seed_dataset(SAMPLE_ROWS)
    tools = {t.name: t for t in make_tools(dataset_id)}
    out = _result_json(tools["period_compare"].invoke({"preset": "this_month_vs_last"}))
    assert "period_a" in out and "period_b" in out
    # period_b is the latest month (Feb 2025); should include the two Feb debits.
    assert out["period_b"]["expense"] == pytest.approx(410 + 560)


def test_period_compare_invalid_args():
    dataset_id = _seed_dataset(SAMPLE_ROWS)
    tools = {t.name: t for t in make_tools(dataset_id)}
    out = _result_json(tools["period_compare"].invoke({}))
    assert "error" in out


def test_apply_filters_date_order():
    df = pd.DataFrame(SAMPLE_ROWS)
    df["date"] = pd.to_datetime(df["date"])
    df["amount"] = pd.to_numeric(df["amount"])
    df["category"] = "Others"
    with pytest.raises(ValueError, match="date_from must be on or before date_to"):
        _apply_filters(df, date_from="2025-02-01", date_to="2025-01-01")
