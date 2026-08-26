from fastapi import APIRouter

from app.observability import snapshot

router = APIRouter()


@router.get("/observability")
def observability():
    """Per-step latency and LLM token/cost for recent /analyze and /chat calls (persisted in SQLite, last 50)."""
    return snapshot()
