import pandas as pd

from app.categorize import add_categories


def test_add_categories_maps_known():
    df = pd.DataFrame(
        {
            "date": pd.to_datetime(["2025-01-01", "2025-01-02"]),
            "merchant": ["Swiggy", "Unknown Co"],
            "amount": [450.0, 100.0],
            "type": ["Debit", "Debit"],
        }
    )
    out = add_categories(df)
    assert out["category"].tolist() == ["Food", "Others"]
    # original df untouched
    assert "category" not in df.columns


def test_add_categories_income_merchants():
    df = pd.DataFrame(
        {
            "date": pd.to_datetime(["2025-01-01"]),
            "merchant": ["Salary"],
            "amount": [50000.0],
            "type": ["Credit"],
        }
    )
    out = add_categories(df)
    assert out["category"].iloc[0] == "Income"
