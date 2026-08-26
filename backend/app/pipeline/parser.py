from io import BytesIO

import pandas as pd

COLUMNS = ["date", "merchant", "amount", "type"]
REQUIRED_COLUMNS = set(COLUMNS)


class ParseError(ValueError):
    pass


def _normalize_transactions(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    df.columns = [str(c).strip().lower() for c in df.columns]
    missing = REQUIRED_COLUMNS - set(df.columns)
    if missing:
        raise ParseError(f"Missing columns: {', '.join(sorted(missing))}. Expected date,merchant,amount,type")

    df = df[COLUMNS].copy()
    df["merchant"] = df["merchant"].astype(str).str.strip()
    df["type"] = df["type"].astype(str).str.strip().str.title()
    df["date"] = pd.to_datetime(df["date"], errors="coerce")
    df["amount"] = pd.to_numeric(df["amount"], errors="coerce")

    df = df.dropna(subset=["date", "merchant", "amount", "type"])
    df = df[df["type"].isin(["Credit", "Debit"])]
    df = df[df["amount"] >= 0]
    df = df[df["merchant"].str.len() > 0]

    if df.empty:
        raise ParseError("No valid transactions after parsing.")

    return df.reset_index(drop=True)


def parse_csv(content: bytes) -> pd.DataFrame:
    try:
        df = pd.read_csv(BytesIO(content))
    except Exception as exc:
        raise ParseError("Could not read CSV. Check the file encoding and commas.") from exc
    return _normalize_transactions(df)


def parse_xlsx(content: bytes) -> pd.DataFrame:
    try:
        df = pd.read_excel(BytesIO(content), engine="openpyxl")
    except Exception as exc:
        raise ParseError("Could not read Excel. Use .xlsx with a header row on the first sheet.") from exc
    return _normalize_transactions(df)


def parse_upload(content: bytes, filename: str) -> pd.DataFrame:
    name = filename.lower()
    if name.endswith(".csv"):
        return parse_csv(content)
    if name.endswith(".xlsx"):
        return parse_xlsx(content)
    raise ParseError("Please upload a .csv or .xlsx file.")
