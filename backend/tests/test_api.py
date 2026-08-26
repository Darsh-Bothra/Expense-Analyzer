import pytest
from fastapi.testclient import TestClient

from app.main import app


@pytest.fixture
def client():
    return TestClient(app)


def _csv_bytes() -> bytes:
    rows = [
        "date,merchant,amount,type",
        "2025-01-01,Swiggy,450,Debit",
        "2025-01-02,Uber,280,Debit",
        "2025-01-04,Salary,50000,Credit",
    ]
    return "\n".join(rows).encode()


def test_health(client):
    res = client.get("/health")
    assert res.status_code == 200
    assert res.json() == {"ok": True}


def test_analyze_success(client):
    res = client.post(
        "/analyze",
        files={"file": ("transactions.csv", _csv_bytes(), "text/csv")},
    )
    assert res.status_code == 200
    body = res.json()
    assert body["insights_source"] == "template"
    assert body["dataset_id"]
    assert len(body["rows"]) == 3
    assert body["facts"]["income"] == 50000.0


def test_analyze_rejects_non_csv(client):
    res = client.post(
        "/analyze",
        files={"file": ("data.txt", b"foo", "text/plain")},
    )
    assert res.status_code == 400
    assert "csv or .xlsx" in res.json()["detail"]


def test_analyze_rejects_xls(client):
    res = client.post(
        "/analyze",
        files={"file": ("data.xls", b"foo", "application/vnd.ms-excel")},
    )
    assert res.status_code == 400


def test_analyze_xlsx_success(client):
    from io import BytesIO

    import pandas as pd

    buf = BytesIO()
    pd.DataFrame(
        {
            "date": ["2025-01-01", "2025-01-02", "2025-01-04"],
            "merchant": ["Swiggy", "Uber", "Salary"],
            "amount": [450, 280, 50000],
            "type": ["Debit", "Debit", "Credit"],
        }
    ).to_excel(buf, index=False, engine="openpyxl")
    res = client.post(
        "/analyze",
        files={
            "file": (
                "transactions.xlsx",
                buf.getvalue(),
                "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            )
        },
    )
    assert res.status_code == 200
    body = res.json()
    assert len(body["rows"]) == 3
    assert body["facts"]["income"] == 50000.0


def test_analyze_rejects_bad_columns(client):
    res = client.post(
        "/analyze",
        files={"file": ("bad.csv", b"date,merchant,amount\n2025-01-01,Swiggy,450\n", "text/csv")},
    )
    assert res.status_code == 400


def test_observability_records_run(client):
    client.post(
        "/analyze",
        files={"file": ("transactions.csv", _csv_bytes(), "text/csv")},
    )
    snap = client.get("/observability").json()
    assert snap["request_count"] >= 1
    assert snap["recent"][0]["endpoint"] == "/analyze"
    assert snap["recent"][0]["ok"] is True


def test_analyze_dataset_roundtrip(client):
    res = client.post(
        "/analyze",
        files={"file": ("transactions.csv", _csv_bytes(), "text/csv")},
    )
    dataset_id = res.json()["dataset_id"]
    got = client.get(f"/datasets/{dataset_id}").json()
    assert got["dataset_id"] == dataset_id
    assert len(got["rows"]) == 3


def test_chat_template_path(client):
    res = client.post(
        "/analyze",
        files={"file": ("transactions.csv", _csv_bytes(), "text/csv")},
    )
    dataset_id = res.json()["dataset_id"]
    chat = client.post(
        f"/datasets/{dataset_id}/chat", json={"message": "Summarize my spending"}
    ).json()
    assert chat["source"] == "template"
    assert "₹" in chat["reply"]
