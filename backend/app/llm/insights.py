import os

from langchain_core.messages import HumanMessage, SystemMessage

from app.llm.client import get_chat_model, provider_api_key_present
from app.observability import estimate_cost, extract_usage
from app.prompts.insights import INSIGHTS_SYSTEM_PROMPT
from app.schemas import FactsPayload, InsightSummary


def _inr(value: float) -> str:
    return f"₹{value:,.0f}"


def template_insights(facts: FactsPayload) -> InsightSummary:
    highlights: list[str] = [
        f"Income {_inr(facts.income)}, expenses {_inr(facts.expense)}, net savings {_inr(facts.savings)}.",
    ]
    if facts.categories:
        top_cat = max(facts.categories, key=lambda c: c.amount)
        highlights.append(
            f"You spent {top_cat.pct_of_expense}% of expenses on {top_cat.name} ({_inr(top_cat.amount)})."
        )
    if facts.highest_spend_merchant:
        highlights.append(
            f"{facts.highest_spend_merchant.name} was your highest-spend merchant at {_inr(facts.highest_spend_merchant.amount)}."
        )
    if facts.most_frequent_merchant:
        highlights.append(
            f"{facts.most_frequent_merchant.name} was your most frequently used merchant ({facts.most_frequent_merchant.count} debit transactions)."
        )
    highlights.append(f"{facts.weekend_pct_of_expense}% of debit spend occurred on weekends.")
    highlights = highlights[:5]

    watchouts: list[str] = []
    cats = {c.name: c for c in facts.categories}
    if "Food" in cats and "Shopping" in cats and cats["Food"].amount > cats["Shopping"].amount * 1.25:
        watchouts.append("Food spend is significantly higher than Shopping.")
    elif "Food" in cats and "Shopping" not in cats and cats["Food"].pct_of_expense >= 30:
        watchouts.append("Food is a large share of expenses compared with other categories.")
    if facts.weekend_pct_of_expense >= 50:
        watchouts.append("Most spending occurred during weekends.")

    top_name = facts.categories[0].name if facts.categories else "spending"
    if facts.categories:
        top_name = max(facts.categories, key=lambda c: c.amount).name
    headline = f"{top_name} was a major part of this period's spending."
    return InsightSummary(headline=headline, highlights=highlights, watchouts=watchouts[:2])


def _numbers_in_facts(facts: FactsPayload) -> set[str]:
    tokens: set[str] = set()
    for value in (facts.income, facts.expense, facts.savings, facts.weekend_pct_of_expense):
        tokens.add(f"{value:.0f}")
        tokens.add(f"{value:.1f}")
    tokens.add(str(facts.transaction_count))
    for m in facts.top_merchants:
        tokens.add(f"{m.amount:.0f}")
        tokens.add(str(m.count))
        tokens.add(m.name.lower())
    if facts.most_frequent_merchant:
        tokens.add(facts.most_frequent_merchant.name.lower())
        tokens.add(str(facts.most_frequent_merchant.count))
    if facts.highest_spend_merchant:
        tokens.add(facts.highest_spend_merchant.name.lower())
        tokens.add(f"{facts.highest_spend_merchant.amount:.0f}")
    for c in facts.categories:
        tokens.add(c.name.lower())
        tokens.add(f"{c.amount:.0f}")
        tokens.add(f"{c.pct_of_expense:.1f}")
        tokens.add(f"{c.pct_of_expense:.0f}")
    return tokens


def _ground_highlights(facts: FactsPayload, insights: InsightSummary) -> InsightSummary:
    tokens = _numbers_in_facts(facts)
    kept = []
    for bullet in insights.highlights:
        lowered = bullet.lower()
        if any(tok in lowered for tok in tokens if tok):
            kept.append(bullet)
    if not kept:
        return template_insights(facts)
    return InsightSummary(
        headline=insights.headline,
        highlights=kept[:5],
        watchouts=insights.watchouts[:2],
    )


def generate_insights(facts: FactsPayload) -> tuple[InsightSummary, str, int, int, float]:
    fallback = template_insights(facts)
    # #region agent log
    try:
        import json as _json, time as _time, os as _os
        with open("/home/darsh/Desktop/assignment-npci/.cursor/debug-3cabff.log", "a") as _f:
            _f.write(_json.dumps({"sessionId":"3cabff","hypothesisId":"E","location":"insights.py:generate_insights","message":"insights entry","data":{"key_present":provider_api_key_present(),"provider":_os.getenv("LLM_PROVIDER","openai")},"timestamp":int(_time.time()*1000),"runId":"post-fix"})+"\n")
    except Exception:
        pass
    # #endregion
    if not provider_api_key_present():
        return fallback, "template", 0, 0, 0.0

    try:
        model = get_chat_model().with_structured_output(InsightSummary)
        result = model.invoke(
            [
                SystemMessage(content=INSIGHTS_SYSTEM_PROMPT),
                HumanMessage(content=f"Facts JSON:\n{facts.model_dump_json()}"),
            ]
        )
        if not isinstance(result, InsightSummary):
            result = InsightSummary.model_validate(result)
        # with_structured_output may wrap usage on the underlying raw response;
        # try to pull it from the model's last raw output if available.
        tokens_in, tokens_out = 0, 0
        raw = getattr(result, "raw", None)
        if raw is not None:
            tokens_in, tokens_out = extract_usage(raw)
        model_name = os.getenv("LLM_MODEL", "gpt-4o-mini")
        cost = estimate_cost(model_name, tokens_in, tokens_out)
        return _ground_highlights(facts, result), "llm", tokens_in, tokens_out, cost
    except Exception:
        return fallback, "template", 0, 0, 0.0
