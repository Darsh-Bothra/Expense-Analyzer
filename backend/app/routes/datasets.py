from fastapi import APIRouter, HTTPException

from app.llm.chat import run_chat
from app.db import (
    dataset_exists,
    get_dataset_meta,
    list_chat_messages,
    list_transaction_rows,
)
from app.observability import StepTimer, record_run
from app.schemas import (
    ChatMessageOut,
    ChatRequest,
    ChatResponse,
    DatasetResponse,
    ToolCallTrace,
)

router = APIRouter()


def _require_dataset(dataset_id: str) -> None:
    if not dataset_exists(dataset_id):
        raise HTTPException(status_code=404, detail="Dataset not found.")


@router.get("/datasets/{dataset_id}", response_model=DatasetResponse)
def get_dataset(dataset_id: str):
    meta = get_dataset_meta(dataset_id)
    if meta is None:
        raise HTTPException(status_code=404, detail="Dataset not found.")
    return DatasetResponse(
        dataset_id=meta["dataset_id"],
        filename=meta["filename"],
        created_at=meta["created_at"],
        rows=list_transaction_rows(dataset_id),
        facts=meta["facts"],
        insights=meta["insights"],
        insights_source=meta["insights_source"],
    )


@router.post("/datasets/{dataset_id}/chat", response_model=ChatResponse)
def chat(dataset_id: str, body: ChatRequest):
    _require_dataset(dataset_id)
    timer = StepTimer()
    try:
        reply, traces, source, tokens_in, tokens_out, cost = run_chat(dataset_id, body.message.strip())
    except KeyError:
        record_run(
            timer,
            endpoint="/chat",
            filename=None,
            row_count=None,
            insights_source=None,
            ok=False,
            error="Dataset not found.",
        )
        raise HTTPException(status_code=404, detail="Dataset not found.") from None
    record_run(
        timer,
        endpoint="/chat",
        filename=None,
        row_count=None,
        insights_source=source,
        ok=True,
        tokens_in=tokens_in,
        tokens_out=tokens_out,
        cost_usd=cost,
    )
    return ChatResponse(reply=reply, tool_calls=traces, source=source)


@router.get("/datasets/{dataset_id}/messages", response_model=list[ChatMessageOut])
def chat_history(dataset_id: str):
    _require_dataset(dataset_id)
    rows = list_chat_messages(dataset_id)
    out: list[ChatMessageOut] = []
    for row in rows:
        traces = None
        if row["tool_trace"]:
            traces = [ToolCallTrace.model_validate(t) for t in row["tool_trace"]]
        out.append(
            ChatMessageOut(
                role=row["role"],
                content=row["content"],
                tool_trace=traces,
                created_at=row["created_at"],
            )
        )
    return out
