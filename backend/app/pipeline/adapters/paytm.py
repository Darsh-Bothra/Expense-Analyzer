import pandas as pd

PAYTM_PASSBOOK_SHEET = "Passbook Payment History"
PAYTM_SUMMARY_SHEET = "Summary"

# Longest prefixes first so "Money received from" wins over "Received from".
_MERCHANT_PREFIXES = (
    "automatic payment for ",
    "money received from ",
    "money sent to ",
    "received from ",
    "paid to ",
)


def looks_like_paytm_headers(columns: list[str] | pd.Index) -> bool:
    lowered = {str(c).strip().lower() for c in columns}
    return "transaction details" in lowered and "amount" in lowered


def is_paytm_passbook(sheet_name: str, columns: list[str] | pd.Index) -> bool:
    if str(sheet_name).strip().lower() == PAYTM_PASSBOOK_SHEET.lower():
        return True
    return looks_like_paytm_headers(columns)


def is_paytm_summary(sheet_name: str) -> bool:
    return str(sheet_name).strip().lower() == PAYTM_SUMMARY_SHEET.lower()


def _parse_signed_amount(value) -> float:
    if value is None or (isinstance(value, float) and pd.isna(value)):
        return float("nan")
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        return float(value)
    text = (
        str(value)
        .strip()
        .replace(",", "")
        .replace("₹", "")
        .replace("rs.", "")
        .replace("rs", "")
        .replace(" ", "")
    )
    if not text or text.lower() in {"nan", "none"}:
        return float("nan")
    try:
        return float(text)
    except ValueError:
        return float("nan")


def _merchant_from_details(value) -> str:
    text = "" if value is None or (isinstance(value, float) and pd.isna(value)) else str(value).strip()
    lowered = text.lower()
    for prefix in _MERCHANT_PREFIXES:
        if lowered.startswith(prefix):
            return text[len(prefix) :].strip()
    return text


def map_paytm_passbook(df: pd.DataFrame) -> pd.DataFrame:
    renamed = df.copy()
    renamed.columns = [str(c).strip().lower() for c in renamed.columns]
    if "transaction details" not in renamed.columns or "amount" not in renamed.columns or "date" not in renamed.columns:
        raise ValueError("Paytm passbook is missing Date, Transaction Details, or Amount")

    signed = renamed["amount"].map(_parse_signed_amount)
    out = pd.DataFrame(
        {
            "date": renamed["date"],
            "merchant": renamed["transaction details"].map(_merchant_from_details),
            "amount": signed.abs(),
            "type": signed.map(lambda n: "Debit" if n < 0 else ("Credit" if n > 0 else "")),
        }
    )
    return out
