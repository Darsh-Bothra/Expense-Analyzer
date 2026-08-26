from io import BytesIO

import pandas as pd
import pytest

from app.pipeline.parser import ParseError, parse_csv, parse_upload, parse_xlsx


def _xlsx_bytes(df: pd.DataFrame) -> bytes:
    buf = BytesIO()
    df.to_excel(buf, index=False, engine="openpyxl")
    return buf.getvalue()


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


def test_parse_xlsx_matches_csv():
    csv = b"date,merchant,amount,type\n2025-01-01,Swiggy,450,Debit\n2025-01-04,Salary,50000,Credit\n"
    csv_df = parse_csv(csv)
    xlsx = _xlsx_bytes(
        pd.DataFrame(
            {
                "date": ["2025-01-01", "2025-01-04"],
                "merchant": ["Swiggy", "Salary"],
                "amount": [450, 50000],
                "type": ["Debit", "Credit"],
            }
        )
    )
    xlsx_df = parse_xlsx(xlsx)
    assert len(xlsx_df) == 2
    pd.testing.assert_frame_equal(csv_df.reset_index(drop=True), xlsx_df.reset_index(drop=True))


def test_parse_xlsx_missing_columns():
    content = _xlsx_bytes(
        pd.DataFrame({"date": ["2025-01-01"], "merchant": ["Swiggy"], "amount": [450]})
    )
    with pytest.raises(ParseError, match="Missing columns"):
        parse_xlsx(content)


def test_parse_xlsx_unreadable():
    with pytest.raises(ParseError, match="Could not read Excel"):
        parse_xlsx(b"not an excel workbook")


def test_parse_upload_routes_by_extension():
    csv = b"date,merchant,amount,type\n2025-01-01,Swiggy,450,Debit\n"
    df = parse_upload(csv, "statement.CSV")
    assert len(df) == 1
    with pytest.raises(ParseError, match="csv or .xlsx"):
        parse_upload(csv, "statement.xls")
