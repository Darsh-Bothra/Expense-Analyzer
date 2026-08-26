import os

from langchain_core.messages import AIMessage, HumanMessage, SystemMessage, ToolMessage

from app.db import append_chat_message, get_dataset_meta, list_chat_messages, load_transactions_df
from app.llm import get_chat_model, provider_api_key_present
from app.observability import estimate_cost, extract_usage
from app.schemas import FactsPayload, ToolCallTrace
from app.tools import make_tools

MAX_TOOL_ROUNDS = 3
HISTORY_TURNS = 10

SYSTEM_PROMPT = """You are an expense analyst for an Indian UPI statement.
Columns: date (YYYY-MM-DD), merchant, amount, type (Credit or Debit), category.
Categories: Food, Travel, Shopping, Bills, Entertainment, Others, Income.
Income = sum of Credit amounts. Expense = sum of Debit amounts. Net savings = Income − Expense.
Category % is debit in that category divided by total expense.

You MUST call tools to obtain numbers. Never invent merchants, amounts, or percentages.
If a tool returns an error, fix the arguments and retry.
If a tool returns empty results, say the statement has no matching rows.
Answer in clear INR (₹). Be concise. Use only figures from tool JSON."""


def template_chat_reply(facts: FactsPayload) -> str:
    return (
        "No LLM API key is configured, so this is a cached KPI summary rather than a live tool answer. "
        f"Income ₹{facts.income:,.0f}, expenses ₹{facts.expense:,.0f}, "
        f"net savings ₹{facts.savings:,.0f}, {facts.transaction_count} transactions. "
        f"Weekend share of expenses: {facts.weekend_pct_of_expense}%."
    )


def _history_messages(dataset_id: str) -> list:
    rows = list_chat_messages(dataset_id, limit=HISTORY_TURNS)
    out = []
    for row in rows:
        if row["role"] == "user":
            out.append(HumanMessage(content=row["content"]))
        elif row["role"] == "assistant":
            out.append(AIMessage(content=row["content"]))
    return out


def _content_text(message: AIMessage) -> str:
    content = message.content
    if isinstance(content, str):
        return content.strip()
    if isinstance(content, list):
        parts = []
        for block in content:
            if isinstance(block, str):
                parts.append(block)
            elif isinstance(block, dict) and block.get("type") == "text":
                parts.append(str(block.get("text", "")))
        return "".join(parts).strip()
    return str(content).strip() if content else ""


def _system_prompt(dataset_id: str) -> str:
    df = load_transactions_df(dataset_id)
    if df.empty:
        span = "This dataset has no rows."
    else:
        start = df["date"].min().strftime("%Y-%m-%d")
        end = df["date"].max().strftime("%Y-%m-%d")
        span = (
            f"This statement covers {start} to {end} ({len(df)} rows). "
            "When the user says this year/month without dates, use this span, not today's calendar."
        )
    return f"{SYSTEM_PROMPT}\n{span}"


def run_chat(dataset_id: str, user_message: str) -> tuple[str, list[ToolCallTrace], str, int, int, float]:
    meta = get_dataset_meta(dataset_id)
    if meta is None:
        raise KeyError(dataset_id)
    facts: FactsPayload = meta["facts"]

    append_chat_message(dataset_id, "user", user_message)

    if not provider_api_key_present():
        reply = template_chat_reply(facts)
        append_chat_message(dataset_id, "assistant", reply, tool_trace=[])
        return reply, [], "template", 0, 0, 0.0

    tools = make_tools(dataset_id)
    by_name = {t.name: t for t in tools}
    traces: list[ToolCallTrace] = []
    total_in = 0
    total_out = 0

    try:
        model = get_chat_model()
        bound = model.bind_tools(tools)
        messages: list = [
            SystemMessage(content=_system_prompt(dataset_id)),
            *_history_messages(dataset_id),
        ]
        # history already includes the user message we just stored
        if not messages or not isinstance(messages[-1], HumanMessage):
            messages.append(HumanMessage(content=user_message))

        ai: AIMessage | None = None
        for _ in range(MAX_TOOL_ROUNDS):
            ai = bound.invoke(messages)
            messages.append(ai)
            t_in, t_out = extract_usage(ai)
            total_in += t_in
            total_out += t_out
            calls = getattr(ai, "tool_calls", None) or []
            if not calls:
                break
            for call in calls:
                name = call.get("name") or ""
                args = call.get("args") or {}
                traces.append(ToolCallTrace(name=name, args=args if isinstance(args, dict) else {}))
                tool = by_name.get(name)
                if tool is None:
                    result = f'{{"error": "Unknown tool {name}"}}'
                else:
                    try:
                        result = tool.invoke(args if isinstance(args, dict) else {})
                    except Exception as exc:
                        result = f'{{"error": {str(exc)!r}}}'
                messages.append(
                    ToolMessage(
                        content=str(result),
                        tool_call_id=call.get("id") or name,
                    )
                )
        else:
            if ai is not None and (getattr(ai, "tool_calls", None) or []):
                ai = model.invoke(
                    [
                        *messages,
                        HumanMessage(
                            content="Stop calling tools. Answer the user using only the tool JSON already in this conversation."
                        ),
                    ]
                )
                messages.append(ai)
                t_in, t_out = extract_usage(ai)
                total_in += t_in
                total_out += t_out

        reply = _content_text(ai) if ai is not None else ""
        if not reply:
            reply = (
                "I looked up the statement with tools but could not form a text answer. "
                "Try asking again with a merchant, category, or date range."
            )
        dump = [t.model_dump() for t in traces]
        append_chat_message(dataset_id, "assistant", reply, tool_trace=dump)
        cost = estimate_cost(os.getenv("LLM_MODEL", "gpt-4o-mini"), total_in, total_out)
        return reply, traces, "llm", total_in, total_out, cost
    except Exception:
        reply = template_chat_reply(facts)
        append_chat_message(dataset_id, "assistant", reply, tool_trace=[])
        return reply, [], "template", 0, 0, 0.0
