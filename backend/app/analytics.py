import pandas as pd

from app.schemas import (
    CategoryStat,
    FactsPayload,
    MerchantStat,
    NamedAmount,
    NamedCount,
)

EXPENSE_CATEGORIES = [
    "Food",
    "Travel",
    "Shopping",
    "Bills",
    "Entertainment",
    "Others",
]


def _debits(df: pd.DataFrame) -> pd.DataFrame:
    return df[df["type"] == "Debit"]


def _credits(df: pd.DataFrame) -> pd.DataFrame:
    return df[df["type"] == "Credit"]


def build_facts(df: pd.DataFrame) -> FactsPayload:
    credits = _credits(df)
    debits = _debits(df)
    income = float(credits["amount"].sum()) if not credits.empty else 0.0
    expense = float(debits["amount"].sum()) if not debits.empty else 0.0
    savings = income - expense

    top_merchants: list[MerchantStat] = []
    most_frequent: NamedCount | None = None
    highest_spend: NamedAmount | None = None

    if not debits.empty:
        grouped = (
            debits.groupby("merchant", as_index=False)
            .agg(amount=("amount", "sum"), count=("amount", "size"))
            .sort_values(["amount", "count", "merchant"], ascending=[False, False, True])
        )
        # #region agent log
        try:
            import json as _json, time as _time
            _it = next(grouped.head(1).itertuples())
            _freq_preview = grouped.sort_values(["count", "amount", "merchant"], ascending=[False, False, True]).iloc[0]
            with open("/home/darsh/Desktop/assignment-npci/.cursor/debug-3cabff.log", "a") as _f:
                _f.write(_json.dumps({"sessionId":"3cabff","hypothesisId":"A","location":"analytics.py:grouped","message":"merchant groupby row access","data":{"grouped_cols":list(grouped.columns),"grouped_dtypes":{c:str(t) for c,t in grouped.dtypes.items()},"n_groups":int(len(grouped)),"itertuple_count_type":str(type(_it.count)),"itertuple_has_count_field":"count" in getattr(_it,"_fields",()),"freq_type":str(type(_freq_preview)),"freq_count_type":str(type(_freq_preview.count)),"freq_bracket_count":None if "count" not in _freq_preview.index else (None if callable(_freq_preview["count"]) else int(_freq_preview["count"])),"freq_index":[str(x) for x in _freq_preview.index],"debit_n":int(len(debits))},"timestamp":int(_time.time()*1000),"runId":"pre-fix"})+"\n")
        except Exception as _e:
            try:
                import json as _json, time as _time
                with open("/home/darsh/Desktop/assignment-npci/.cursor/debug-3cabff.log", "a") as _f:
                    _f.write(_json.dumps({"sessionId":"3cabff","hypothesisId":"C","location":"analytics.py:grouped-log-fail","message":"instrumentation failed","data":{"error":str(_e)},"timestamp":int(_time.time()*1000),"runId":"pre-fix"})+"\n")
            except Exception:
                pass
        # #endregion
        try:
            top_merchants = [
                MerchantStat(name=row.merchant, amount=float(row.amount), count=int(row.count))
                for row in grouped.head(5).itertuples()
            ]
        except Exception as _e:
            # #region agent log
            import json as _json, time as _time
            with open("/home/darsh/Desktop/assignment-npci/.cursor/debug-3cabff.log", "a") as _f:
                _f.write(_json.dumps({"sessionId":"3cabff","hypothesisId":"B","location":"analytics.py:top_merchants","message":"itertuples count access failed","data":{"error":str(_e),"error_type":type(_e).__name__},"timestamp":int(_time.time()*1000),"runId":"pre-fix"})+"\n")
            # #endregion
            raise
        freq = grouped.sort_values(["count", "amount", "merchant"], ascending=[False, False, True]).iloc[0]
        # Series.count is a method; the txn tally lives in freq["count"]
        try:
            most_frequent = NamedCount(name=str(freq["merchant"]), count=int(freq["count"]))
        except Exception as _e:
            # #region agent log
            import json as _json, time as _time
            with open("/home/darsh/Desktop/assignment-npci/.cursor/debug-3cabff.log", "a") as _f:
                _f.write(_json.dumps({"sessionId":"3cabff","hypothesisId":"A","location":"analytics.py:most_frequent","message":"freq.count int() failed","data":{"error":str(_e),"error_type":type(_e).__name__,"freq_count_repr":repr(freq.count),"bracket_ok":"count" in freq.index,"bracket_val":None if "count" not in freq.index else str(freq["count"]),"merchant":str(freq.merchant) if hasattr(freq,"merchant") else None},"timestamp":int(_time.time()*1000),"runId":"post-fix"})+"\n")
            # #endregion
            raise
        # #region agent log
        try:
            import json as _json, time as _time
            with open("/home/darsh/Desktop/assignment-npci/.cursor/debug-3cabff.log", "a") as _f:
                _f.write(_json.dumps({"sessionId":"3cabff","hypothesisId":"A","location":"analytics.py:most_frequent-ok","message":"most frequent merchant built","data":{"name":most_frequent.name,"count":most_frequent.count},"timestamp":int(_time.time()*1000),"runId":"post-fix"})+"\n")
        except Exception:
            pass
        # #endregion
        highest = grouped.iloc[0]
        highest_spend = NamedAmount(name=str(highest["merchant"]), amount=float(highest["amount"]))

    categories: list[CategoryStat] = []
    if "category" in df.columns and not debits.empty:
        cat = (
            debits[debits["category"] != "Income"]
            .groupby("category", as_index=False)
            .agg(amount=("amount", "sum"))
        )
        by_name = {row.category: float(row.amount) for row in cat.itertuples()}
        for name in EXPENSE_CATEGORIES:
            amount = by_name.get(name, 0.0)
            pct = (amount / expense * 100.0) if expense else 0.0
            if amount > 0 or name in by_name:
                categories.append(
                    CategoryStat(name=name, amount=amount, pct_of_expense=round(pct, 1))
                )
        categories = [c for c in categories if c.amount > 0]

    weekend_pct = 0.0
    if not debits.empty:
        weekend = debits[debits["date"].dt.dayofweek >= 5]["amount"].sum()
        weekend_pct = round(float(weekend) / expense * 100.0, 1) if expense else 0.0

    return FactsPayload(
        income=round(income, 2),
        expense=round(expense, 2),
        savings=round(savings, 2),
        transaction_count=int(len(df)),
        top_merchants=top_merchants,
        most_frequent_merchant=most_frequent,
        highest_spend_merchant=highest_spend,
        categories=categories,
        weekend_pct_of_expense=weekend_pct,
    )
