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
    monkeypatch.setattr("app.db.DB_PATH", db_path)
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


@pytest.fixture
def no_llm_key(monkeypatch):
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.delenv("GROQ_API_KEY", raising=False)
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    monkeypatch.delenv("GOOGLE_API_KEY", raising=False)
    monkeypatch.setenv("LLM_PROVIDER", "openai")
    monkeypatch.setenv("LLM_MODEL", "gpt-4o-mini")
    with mock.patch("app.llm.provider_api_key_present", return_value=False):
        yield
