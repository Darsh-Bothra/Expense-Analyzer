import pandas as pd

from app.pipeline.analytics import build_facts
from app.pipeline.categorize import categorize_merchant


def _df(rows):
    base = pd.DataFrame(rows)
    base["date"] = pd.to_datetime(base["date"])
    base["amount"] = pd.to_numeric(base["amount"])
    return base


def test_categorize_known_merchants():
    assert categorize_merchant("Swiggy") == "Food"
    assert categorize_merchant("UBER") == "Travel"
    assert categorize_merchant("Salary") == "Income"
    assert categorize_merchant("Unknown Merchant") == "Others"


def test_build_facts_kpis():
    df = _df(
        [
            {"date": "2025-01-01", "merchant": "Swiggy", "amount": 450, "type": "Debit", "category": "Food"},
            {"date": "2025-01-02", "merchant": "Uber", "amount": 280, "type": "Debit", "category": "Travel"},
            {"date": "2025-01-04", "merchant": "Salary", "amount": 50000, "type": "Credit", "category": "Income"},
        ]
    )
    facts = build_facts(df)
    assert facts.income == 50000.0
    assert facts.expense == 730.0
    assert facts.savings == 49270.0
    assert facts.transaction_count == 3
    assert facts.highest_spend_merchant.name == "Swiggy"
    assert facts.most_frequent_merchant.name == "Swiggy"


def test_build_facts_categories_exclude_income():
    df = _df(
        [
            {"date": "2025-01-01", "merchant": "Swiggy", "amount": 450, "type": "Debit", "category": "Food"},
            {"date": "2025-01-04", "merchant": "Salary", "amount": 50000, "type": "Credit", "category": "Income"},
        ]
    )
    facts = build_facts(df)
    names = {c.name for c in facts.categories}
    assert "Income" not in names
    food = next(c for c in facts.categories if c.name == "Food")
    assert food.pct_of_expense == 100.0


def test_build_facts_weekend_share():
    # 2025-01-04 is a Saturday; 2025-01-06 is a Monday.
    df = _df(
        [
            {"date": "2025-01-04", "merchant": "Swiggy", "amount": 100, "type": "Debit", "category": "Food"},
            {"date": "2025-01-06", "merchant": "Uber", "amount": 100, "type": "Debit", "category": "Travel"},
        ]
    )
    facts = build_facts(df)
    assert facts.weekend_pct_of_expense == 50.0


def test_build_facts_empty_debits():
    df = _df(
        [
            {"date": "2025-01-04", "merchant": "Salary", "amount": 50000, "type": "Credit", "category": "Income"},
        ]
    )
    facts = build_facts(df)
    assert facts.expense == 0.0
    assert facts.categories == []
    assert facts.highest_spend_merchant is None
    assert facts.most_frequent_merchant is None
