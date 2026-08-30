from io import BytesIO

import pandas as pd

from app.pipeline.adapters.paytm import (
    is_paytm_passbook,
    is_paytm_summary,
    looks_like_paytm_headers,
    map_paytm_passbook,
)

COLUMNS = ["date", "merchant", "amount", "type"]
REQUIRED_COLUMNS = set(COLUMNS)


class ParseError(ValueError):
    pass


def _normalize_transactions(df: pd.DataFrame, *, dayfirst: bool = False) -> pd.DataFrame:
    df = df.copy()
    df.columns = [str(c).strip().lower() for c in df.columns]
    missing = REQUIRED_COLUMNS - set(df.columns)
    if missing:
        raise ParseError(f"Missing columns: {', '.join(sorted(missing))}. Expected date,merchant,amount,type")

    df = df[COLUMNS].copy()
    df["merchant"] = df["merchant"].astype(str).str.strip()
    df["type"] = df["type"].astype(str).str.strip().str.title()
    df["date"] = pd.to_datetime(df["date"], errors="coerce", dayfirst=dayfirst)
    df["amount"] = pd.to_numeric(df["amount"], errors="coerce")

    df = df.dropna(subset=["date", "merchant", "amount", "type"])
    df = df[df["type"].isin(["Credit", "Debit"])]
    df = df[df["amount"] >= 0]
    df = df[df["merchant"].str.len() > 0]
    df = df[df["merchant"].str.lower() != "nan"]

    if df.empty:
        raise ParseError("No valid transactions after parsing.")

    return df.reset_index(drop=True)


def inspect_upload(content: bytes, filename: str) -> dict:
    name = (filename or "").lower()
    if name.endswith(".csv"):
        return {"sheets": [], "suggested_sheet": None, "format": "csv"}
    if not name.endswith(".xlsx"):
        raise ParseError("Please upload a .csv or .xlsx file.")
    try:
        xl = pd.ExcelFile(BytesIO(content), engine="openpyxl")
    except Exception as exc:
        raise ParseError("Could not read Excel. Use .xlsx with a header row on the first sheet.") from exc

    sheets = list(xl.sheet_names)
    paytm_sheet = None
    for sheet in sheets:
        if is_paytm_passbook(sheet, []):
            paytm_sheet = sheet
            break
        try:
            header = pd.read_excel(xl, sheet_name=sheet, nrows=0)
        except Exception:
            continue
        if looks_like_paytm_headers(header.columns):
            paytm_sheet = sheet
            break

    suggested = paytm_sheet or (sheets[0] if sheets else None)
    return {
        "sheets": sheets,
        "suggested_sheet": suggested,
        "format": "paytm" if paytm_sheet else "generic",
    }


def parse_csv(content: bytes) -> pd.DataFrame:
    try:
        df = pd.read_csv(BytesIO(content))
    except Exception as exc:
        raise ParseError("Could not read CSV. Check the file encoding and commas.") from exc
    return _normalize_transactions(df)


def parse_xlsx(content: bytes, sheet_name: str | None = None) -> pd.DataFrame:
    try:
        xl = pd.ExcelFile(BytesIO(content), engine="openpyxl")
    except Exception as exc:
        raise ParseError("Could not read Excel. Use .xlsx with a header row on the first sheet.") from exc

    target: str | int
    if sheet_name and sheet_name.strip():
        target = sheet_name.strip()
        if target not in xl.sheet_names:
            raise ParseError(f"Sheet not found: {target}. Available: {', '.join(xl.sheet_names)}")
    else:
        target = 0

    try:
        df = pd.read_excel(xl, sheet_name=target)
    except Exception as exc:
        raise ParseError("Could not read Excel. Use .xlsx with a header row on the first sheet.") from exc

    resolved = target if isinstance(target, str) else xl.sheet_names[int(target)]
    if is_paytm_summary(resolved):
        raise ParseError(
            "Sheet 'Summary' has totals, not transactions. Pick 'Passbook Payment History'."
        )
    if is_paytm_passbook(resolved, df.columns):
        try:
            mapped = map_paytm_passbook(df)
        except ValueError as exc:
            raise ParseError(str(exc)) from exc
        return _normalize_transactions(mapped, dayfirst=True)
    return _normalize_transactions(df)


def parse_upload(content: bytes, filename: str, sheet_name: str | None = None) -> pd.DataFrame:
    name = filename.lower()
    if name.endswith(".csv"):
        return parse_csv(content)
    if name.endswith(".xlsx"):
        return parse_xlsx(content, sheet_name=sheet_name)
    raise ParseError("Please upload a .csv or .xlsx file.")
