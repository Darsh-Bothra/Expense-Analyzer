import pandas as pd
import pytest

from app.pipeline.parser import ParseError, parse_csv


def test_parse_csv_basic():
    content = b"date,merchant,amount,type\n2025-01-01,Swiggy,450,Debit\n2025-01-04,Salary,50000,Credit\n"
    df = parse_csv(content)
    assert len(df) == 2
    assert list(df.columns) == ["date", "merchant", "amount", "type"]
    assert df["type"].tolist() == ["Debit", "Credit"]


def test_parse_csv_strips_and_lowercases_columns():
    content = b"Date, Merchant, Amount, Type\n2025-01-01,Swiggy,450,debit\n"
    df = parse_csv(content)
    assert df["type"].iloc[0] == "Debit"


def test_parse_csv_drops_invalid_rows():
    content = (
        b"date,merchant,amount,type\n"
        b"2025-01-01,Swiggy,450,Debit\n"
        b"not-a-date,Swiggy,100,Debit\n"
        b"2025-01-02,,100,Debit\n"
        b"2025-01-03,Swiggy,-5,Debit\n"
        b"2025-01-04,Swiggy,100,Refund\n"
    )
    df = parse_csv(content)
    assert len(df) == 1
    assert df["merchant"].iloc[0] == "Swiggy"


def test_parse_csv_missing_columns():
    with pytest.raises(ParseError, match="Missing columns"):
        parse_csv(b"date,merchant,amount\n2025-01-01,Swiggy,450\n")


def test_parse_csv_empty_after_validation():
    with pytest.raises(ParseError, match="No valid transactions"):
        parse_csv(b"date,merchant,amount,type\n2025-01-01,Swiggy,450,Refund\n")


def test_parse_csv_unreadable():
    with pytest.raises(ParseError, match="Could not read CSV"):
        parse_csv(b"\xff\xfe\x00\x01binary garbage")
