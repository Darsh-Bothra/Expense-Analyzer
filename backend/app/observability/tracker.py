"""Step timings and LLM token/cost tracking, persisted in SQLite."""

from __future__ import annotations

import os
import time
from contextlib import contextmanager
from datetime import datetime, timezone

from app.db import insert_run, list_recent_runs

MAX_RUNS = 50
STEP_ORDER = (
    "read_file",
    "parse_csv",
    "categorize",
    "analytics",
    "insights",
    "serialize_rows",
)

# Per-1M-token USD pricing (input, output). Best-effort; unknown models cost 0.
_PRICING_PER_M = {
    "gpt-4o-mini": (0.15, 0.60),
    "gpt-4o": (2.50, 10.00),
    "gpt-4.1-mini": (0.40, 1.60),
    "gpt-4.1": (2.00, 8.00),
    "gpt-5-mini": (0.25, 2.00),
    "llama-3.1-8b-instant": (0.05, 0.08),
    "llama-3.3-70b-versatile": (0.59, 0.79),
    "gemini-2.0-flash": (0.10, 0.40),
    "gemini-1.5-flash": (0.075, 0.30),
    "claude-3-5-haiku-latest": (0.80, 4.00),
    "claude-3-5-sonnet-latest": (3.00, 15.00),
}


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


class StepTimer:
    def __init__(self) -> None:
        self.steps_ms: dict[str, float] = {}
        self._wall_start = time.perf_counter()

    @contextmanager
    def step(self, name: str):
        start = time.perf_counter()
        try:
            yield
        finally:
            self.steps_ms[name] = round((time.perf_counter() - start) * 1000, 2)

    def wall_total_ms(self) -> float:
        return round((time.perf_counter() - self._wall_start) * 1000, 2)

    def slowest_step(self) -> str | None:
        if not self.steps_ms:
            return None
        return max(self.steps_ms, key=self.steps_ms.get)


def estimate_cost(model: str, tokens_in: int, tokens_out: int) -> float:
    key = (model or "").strip().lower()
    rates = _PRICING_PER_M.get(key)
    if rates is None:
        # try matching by family prefix
        for name, r in _PRICING_PER_M.items():
            if key.startswith(name) or name.startswith(key):
                rates = r
                break
    if rates is None:
        return 0.0
    in_cost = (tokens_in / 1_000_000.0) * rates[0]
    out_cost = (tokens_out / 1_000_000.0) * rates[1]
    return round(in_cost + out_cost, 6)


def extract_usage(ai_message) -> tuple[int, int]:
    """Best-effort extraction of (input_tokens, output_tokens) from a LangChain AIMessage."""
    usage = getattr(ai_message, "usage_metadata", None)
    if isinstance(usage, dict):
        return int(usage.get("input_tokens", 0)), int(usage.get("output_tokens", 0))
    resp_meta = getattr(ai_message, "response_metadata", None)
    if isinstance(resp_meta, dict):
        token_usage = (
            resp_meta.get("token_usage")
            or resp_meta.get("usage")
            or {}
        )
        if isinstance(token_usage, dict):
            return int(
                token_usage.get("prompt_tokens")
                or token_usage.get("input_tokens")
                or 0
            ), int(
                token_usage.get("completion_tokens")
                or token_usage.get("output_tokens")
                or 0
            )
    return 0, 0


def record_run(
    timer: StepTimer | None,
    *,
    endpoint: str,
    filename: str | None = None,
    row_count: int | None = None,
    insights_source: str | None = None,
    ok: bool,
    error: str | None = None,
    tokens_in: int | None = None,
    tokens_out: int | None = None,
    cost_usd: float | None = None,
) -> dict:
    steps_ms = dict(timer.steps_ms) if timer is not None else {}
    total_ms = timer.wall_total_ms() if timer is not None else 0.0
    slowest = timer.slowest_step() if timer is not None else None
    entry = {
        "at": _now_iso(),
        "endpoint": endpoint,
        "filename": filename,
        "row_count": row_count,
        "insights_source": insights_source,
        "ok": ok,
        "error": error,
        "steps_ms": steps_ms,
        "total_ms": total_ms,
        "slowest_step": slowest,
        "tokens_in": tokens_in,
        "tokens_out": tokens_out,
        "cost_usd": cost_usd,
    }
    try:
        insert_run(entry)
    except Exception:
        # Observability must never break the request.
        pass
    return entry


def snapshot() -> dict:
    recent = list_recent_runs(MAX_RUNS)

    avgs: dict[str, float] = {}
    maxes: dict[str, float] = {}
    totals_in = 0
    totals_out = 0
    total_cost = 0.0
    if recent:
        keys = set()
        for run in recent:
            keys.update(run["steps_ms"].keys())
            keys.add("total")
            if run.get("tokens_in"):
                totals_in += run["tokens_in"]
            if run.get("tokens_out"):
                totals_out += run["tokens_out"]
            if run.get("cost_usd"):
                total_cost += run["cost_usd"]
        for key in list(STEP_ORDER) + ["total"]:
            if key not in keys and key != "total":
                continue
            values = (
                [run["total_ms"] for run in recent]
                if key == "total"
                else [run["steps_ms"][key] for run in recent if key in run["steps_ms"]]
            )
            if not values:
                continue
            avgs[key] = round(sum(values) / len(values), 2)
            maxes[key] = round(max(values), 2)

    step_avgs = {k: v for k, v in avgs.items() if k != "total"}
    bottleneck = None
    if step_avgs:
        name = max(step_avgs, key=step_avgs.get)
        bottleneck = {"step": name, "avg_ms": step_avgs[name], "max_ms": maxes.get(name)}

    return {
        "request_count": len(recent),
        "bottleneck": bottleneck,
        "avg_ms": avgs,
        "max_ms": maxes,
        "tokens_in": totals_in,
        "tokens_out": totals_out,
        "cost_usd": round(total_cost, 6),
        "recent": recent,
    }
