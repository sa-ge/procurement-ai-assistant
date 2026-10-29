"""FastAPI backend for the procurement assistant.

Run (from backend/):  uvicorn app.main:app --reload --port 8000
"""
import uuid

from fastapi import FastAPI, HTTPException
from fastapi.concurrency import run_in_threadpool
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from app.agent.graph import ask
from app.config import settings
from app.db import get_collection
from app.schema import FIELDS

app = FastAPI(title="Procurement Assistant API", version="1.0.0")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])

EXAMPLES = [
    "How many orders were created in March 2014?",
    "Which quarter had the highest spending?",
    "What are the 10 most frequently ordered items?",
    "Top 5 departments by total spending in fiscal year 2013-2014",
    "Show the monthly spending trend for 2014",
    "Which suppliers received the most money from the Department of Corrections?",
    "What share of spending goes to IT vs non-IT purchases?",
    "In the quarter with the highest spending, which department spent the most?",
    "كم عدد الطلبات في الربع الأول من 2015؟",
]


class ChatRequest(BaseModel):
    message: str = Field(min_length=1, max_length=2000)
    session_id: str | None = None


@app.get("/api/health")
def health():
    try:
        count = get_collection().estimated_document_count()
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(503, f"MongoDB unavailable: {exc}") from exc
    return {"status": "ok", "documents": count, "llm": f"{settings.llm_provider}:{settings.llm_model}"}


@app.get("/api/examples")
def examples():
    return EXAMPLES


@app.get("/api/schema")
def schema():
    return {"schema": FIELDS}


@app.post("/api/chat")
async def chat(req: ChatRequest):
    session_id = req.session_id or str(uuid.uuid4())
    try:
        result = await run_in_threadpool(ask, req.message, session_id)
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(502, f"Agent error: {type(exc).__name__}: {exc}") from exc
    return {"session_id": session_id, **result}
