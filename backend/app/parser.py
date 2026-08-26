from io import BytesIO

import pandas as pd

REQUIRED_COLUMNS = {"date", "merchant", "amount", "type"}


class ParseError(ValueError):
    pass


def parse_csv(content: bytes) -> pd.DataFrame:
    try:
        df = pd.read_csv(BytesIO(content))
    except Exception as exc:
        raise ParseError("Could not read CSV. Check the file encoding and commas.") from exc

    df.columns = [str(c).strip().lower() for c in df.columns]
    missing = REQUIRED_COLUMNS - set(df.columns)
    if missing:
        raise ParseError(f"Missing columns: {', '.join(sorted(missing))}. Expected date,merchant,amount,type")

    df = df[list(REQUIRED_COLUMNS)].copy()
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
