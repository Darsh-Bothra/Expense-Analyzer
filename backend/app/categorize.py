CATEGORY_MAP = {
    "swiggy": "Food",
    "zomato": "Food",
    "dominos": "Food",
    "domino's": "Food",
    "mcdonalds": "Food",
    "mcdonald's": "Food",
    "starbucks": "Food",
    "uber eats": "Food",
    "uber": "Travel",
    "ola": "Travel",
    "rapido": "Travel",
    "irctc": "Travel",
    "amazon": "Shopping",
    "flipkart": "Shopping",
    "myntra": "Shopping",
    "ajio": "Shopping",
    "electricity": "Bills",
    "airtel": "Bills",
    "jio": "Bills",
    "bescom": "Bills",
    "bsnl": "Bills",
    "netflix": "Entertainment",
    "bookmyshow": "Entertainment",
    "spotify": "Entertainment",
    "hotstar": "Entertainment",
    "prime": "Entertainment",
}

INCOME_MERCHANTS = {"salary", "refund", "cashback"}


def categorize_merchant(name: str) -> str:
    key = name.strip().lower()
    if key in INCOME_MERCHANTS:
        return "Income"
    return CATEGORY_MAP.get(key, "Others")


def add_categories(df):
    out = df.copy()
    out["category"] = out["merchant"].map(categorize_merchant)
    return out
