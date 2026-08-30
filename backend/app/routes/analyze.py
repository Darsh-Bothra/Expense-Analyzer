import os
import time
from collections import deque
from threading import Lock

from fastapi import APIRouter, File, Form, HTTPException, Request, UploadFile

from app.db import persist_dataset
from app.llm.insights import generate_insights
from app.observability import StepTimer, record_run
from app.pipeline.analytics import build_facts
from app.pipeline.categorize import add_categories
from app.pipeline.parser import ParseError, inspect_upload, parse_upload
from app.schemas import AnalyzeResponse, TransactionRow, WorkbookInspect

router = APIRouter()

MAX_FILE_BYTES = int(os.getenv("ANALYZE_MAX_FILE_BYTES", str(5 * 1024 * 1024)))  # 5 MB
MAX_ROWS = int(os.getenv("ANALYZE_MAX_ROWS", "100000"))
RATE_LIMIT_WINDOW_S = 60
RATE_LIMIT_MAX_REQUESTS = int(os.getenv("ANALYZE_RATE_LIMIT", "20"))


# --- Simple per-IP rate limiter for /analyze ---
_rate_lock = Lock()
_rate_buckets: dict[str, deque[float]] = {}


def _rate_limit_hit(client_ip: str) -> bool:
    now = time.monotonic()
    with _rate_lock:
        bucket = _rate_buckets.setdefault(client_ip, deque(maxlen=RATE_LIMIT_MAX_REQUESTS))
        cutoff = now - RATE_LIMIT_WINDOW_S
        while bucket and bucket[0] < cutoff:
            bucket.popleft()
        if len(bucket) >= RATE_LIMIT_MAX_REQUESTS:
            return True
        bucket.append(now)
        return False


@router.post("/inspect-workbook", response_model=WorkbookInspect)
async def inspect_workbook(file: UploadFile = File(...)):
    name = (file.filename or "").lower()
    if not name.endswith((".csv", ".xlsx")):
        raise HTTPException(status_code=400, detail="Please upload a .csv or .xlsx file.")
    content = await file.read()
    if len(content) > MAX_FILE_BYTES:
        raise HTTPException(
            status_code=413,
            detail=f"File too large. Limit is {MAX_FILE_BYTES} bytes.",
        )
    try:
        return inspect_upload(content, file.filename or name)
    except ParseError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/analyze", response_model=AnalyzeResponse)
async def analyze(
    request: Request,
    file: UploadFile = File(...),
    sheet: str | None = Form(None),
):
    client_ip = request.client.host if request.client else "unknown"
    if _rate_limit_hit(client_ip):
        raise HTTPException(
            status_code=429,
            detail=f"Rate limit exceeded. Max {RATE_LIMIT_MAX_REQUESTS} uploads per {RATE_LIMIT_WINDOW_S}s from one IP.",
        )
    timer = StepTimer()
    name = (file.filename or "").lower()
    if not name.endswith((".csv", ".xlsx")):
        raise HTTPException(status_code=400, detail="Please upload a .csv or .xlsx file.")
    with timer.step("read_file"):
        content = await file.read()
    if len(content) > MAX_FILE_BYTES:
        record_run(
            timer,
            endpoint="/analyze",
            filename=file.filename,
            row_count=None,
            insights_source=None,
            ok=False,
            error=f"File too large ({len(content)} bytes > {MAX_FILE_BYTES}).",
        )
        raise HTTPException(
            status_code=413,
            detail=f"File too large. Limit is {MAX_FILE_BYTES} bytes.",
        )
    try:
        with timer.step("parse"):
            df = parse_upload(content, file.filename or name, sheet_name=sheet or None)
    except ParseError as exc:
        record_run(
            timer,
            endpoint="/analyze",
            filename=file.filename,
            row_count=None,
            insights_source=None,
            ok=False,
            error=str(exc),
        )
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    if len(df) > MAX_ROWS:
        record_run(
            timer,
            endpoint="/analyze",
            filename=file.filename,
            row_count=len(df),
            insights_source=None,
            ok=False,
            error=f"Too many rows ({len(df)} > {MAX_ROWS}).",
        )
        raise HTTPException(
            status_code=413,
            detail=f"Too many rows. Limit is {MAX_ROWS}; got {len(df)}.",
        )

    with timer.step("categorize"):
        df = add_categories(df)
    with timer.step("analytics"):
        facts = build_facts(df)
    with timer.step("insights"):
        insights, source, tokens_in, tokens_out, cost = generate_insights(facts)
    with timer.step("serialize_rows"):
        rows = [
            TransactionRow(
                date=row.date.strftime("%Y-%m-%d"),
                merchant=row.merchant,
                amount=float(row.amount),
                type=row.type,
                category=row.category,
            )
            for row in df.itertuples()
        ]
        dataset_id = persist_dataset(file.filename, df, facts, insights, source)
    record_run(
        timer,
        endpoint="/analyze",
        filename=file.filename,
        row_count=len(rows),
        insights_source=source,
        ok=True,
        tokens_in=tokens_in,
        tokens_out=tokens_out,
        cost_usd=cost,
    )
    return AnalyzeResponse(
        rows=rows,
        facts=facts,
        insights=insights,
        insights_source=source,
        dataset_id=dataset_id,
    )
