import os
import tempfile
from pathlib import Path
from unittest import mock

import pytest

# Force a temporary SQLite DB before any app module imports db helpers.
_TMP_DIR = tempfile.mkdtemp(prefix="npci-test-")
os.environ["NPCI_TEST_DB_PATH"] = str(Path(_TMP_DIR) / "test.db")


@pytest.fixture(autouse=True)
def isolated_db(monkeypatch, tmp_path):
    """Each test gets a fresh SQLite database."""
    db_path = tmp_path / "app.db"
    monkeypatch.setattr("app.db.sqlite.DB_PATH", db_path)
    # Re-init the schema for this fresh path.
    from app.db import init_db

    init_db()
    yield


@pytest.fixture
def sample_csv_bytes() -> bytes:
    rows = [
        "date,merchant,amount,type",
        "2025-01-01,Swiggy,450,Debit",
        "2025-01-02,Uber,280,Debit",
        "2025-01-03,Amazon,1500,Debit",
        "2025-01-04,Salary,50000,Credit",
        "2025-01-05,Netflix,199,Debit",
        "2025-01-06,Swiggy,320,Debit",
        "2025-01-12,Uber,560,Debit",
    ]
    return "\n".join(rows).encode()


def make_paytm_workbook_bytes() -> bytes:
    """Synthetic Paytm export: Summary + Passbook Payment History (fake counterparties)."""
    from io import BytesIO

    import pandas as pd

    buf = BytesIO()
    with pd.ExcelWriter(buf, engine="openpyxl") as writer:
        pd.DataFrame(
            [
                ["Sample User"],
                ["paytm-sample@example.com"],
                ["Paytm Statement for :", "01 AUG'26 - 25 AUG'26"],
                ["Money Paid (Amount in Rs.)", "-3,293.89"],
            ]
        ).to_excel(writer, sheet_name="Summary", header=False, index=False)
        pd.DataFrame(
            {
                "Date": ["25/08/2026", "24/08/2026", "01/08/2026", "19/08/2026"],
                "Time": ["19:11:57", "12:42:15", "10:00:00", "23:06:10"],
                "Transaction Details": [
                    "Paid to Apollo Pharmacy",
                    "Money sent to Test Person",
                    "Received from Acme Corp",
                    "Automatic payment for Google Play Store",
                ],
                "Other Transaction Details (UPI ID or A/c No)": [
                    "merchant@upi",
                    "9999999999@upi",
                    "acme@upi",
                    "playstore@upi",
                ],
                "Your Account": ["State Bank Of India - 00"] * 4,
                "Amount": ["-393.89", "-2,400.00", "+1,500.00", "-299.00"],
                "UPI Ref No.": [111, 222, 333, 444],
                "Order ID": [None] * 4,
                "Remarks": [None] * 4,
                "Tags": ["#🏥 Medical", "#💵 Money Transfer", "#💵 Money Received", "#🎈 Entertainment"],
                "Comment": [None] * 4,
            }
        ).to_excel(writer, sheet_name="Passbook Payment History", index=False)
    return buf.getvalue()


@pytest.fixture
def paytm_workbook_bytes() -> bytes:
    return make_paytm_workbook_bytes()


@pytest.fixture
def no_llm_key(monkeypatch):
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.delenv("GROQ_API_KEY", raising=False)
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    monkeypatch.delenv("GOOGLE_API_KEY", raising=False)
    monkeypatch.setenv("LLM_PROVIDER", "openai")
    monkeypatch.setenv("LLM_MODEL", "gpt-4o-mini")
    with (
        mock.patch("app.llm.client.provider_api_key_present", return_value=False),
        mock.patch("app.llm.chat.provider_api_key_present", return_value=False),
        mock.patch("app.llm.insights.provider_api_key_present", return_value=False),
    ):
        yield
