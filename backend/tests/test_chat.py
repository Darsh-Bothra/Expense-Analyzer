import pandas as pd

from app.db import persist_dataset
from app.llm.chat import run_chat, template_chat_reply
from app.llm.insights import template_insights
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
    {"date": "2025-01-04", "merchant": "Salary", "amount": 50000, "type": "Credit"},
]


def test_template_chat_reply_mentions_kpis():
    df = pd.DataFrame(SAMPLE_ROWS)
    df["date"] = pd.to_datetime(df["date"])
    df["amount"] = pd.to_numeric(df["amount"])
    df = add_categories(df)
    facts = build_facts(df)
    text = template_chat_reply(facts)
    assert "₹50,000" in text
    assert "₹450" in text
    assert "2 transactions" in text


def test_run_chat_falls_back_to_template_without_key(no_llm_key):
    dataset_id = _seed_dataset(SAMPLE_ROWS)
    reply, traces, source, tokens_in, tokens_out, cost = run_chat(dataset_id, "How much did I spend?")
    assert source == "template"
    assert traces == []
    assert tokens_in == 0 and tokens_out == 0 and cost == 0.0
    assert "₹50,000" in reply


def test_run_chat_missing_dataset():
    import pytest

    with pytest.raises(KeyError):
        run_chat("does-not-exist", "hi")
