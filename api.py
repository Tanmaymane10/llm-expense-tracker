"""
HTTP API for the expense tracker. Clients (the Streamlit dashboard, a Telegram bot, curl) all
talk to this one service, which owns the model calls, the guardrails and the database.

    uvicorn api:app --reload        # interactive docs at http://localhost:8000/docs

Authentication: send the header  X-API-Key: <API_TOKEN>  (set API_TOKEN in .env).
"""
import hmac
import json
import logging
import os
import time
import uuid
from contextlib import asynccontextmanager
from datetime import date
from typing import Annotated, Literal

import pandas as pd
from fastapi import Depends, FastAPI, Header, HTTPException, Query, Request
from pydantic import BaseModel, Field

import analytics as an
import core

logging.basicConfig(level=os.environ.get("LOG_LEVEL", "INFO"), format="%(message)s")
log = logging.getLogger("expense_api")


@asynccontextmanager
async def lifespan(_app: FastAPI):
    core.init_db()
    yield


app = FastAPI(title="Expense Tracker API", version="1.0.0", lifespan=lifespan)


# ------------------------------------------------------------------ plumbing
@app.middleware("http")
async def access_log(request: Request, call_next):
    """One structured log line per request. Message bodies are never logged (they are private)."""
    request_id = uuid.uuid4().hex[:12]
    started = time.perf_counter()
    response = await call_next(request)
    response.headers["X-Request-ID"] = request_id
    log.info(json.dumps({
        "request_id": request_id, "method": request.method, "path": request.url.path,
        "status": response.status_code,
        "ms": round((time.perf_counter() - started) * 1000),
    }))
    return response


def require_api_key(x_api_key: Annotated[str | None, Header()] = None):
    expected = os.environ.get("API_TOKEN")
    if not expected:  # fail closed: never run an open API by accident
        raise HTTPException(503, "Server is missing the API_TOKEN setting.")
    if not x_api_key or not hmac.compare_digest(x_api_key, expected):
        raise HTTPException(401, "Invalid or missing API key.")


def _records(df: pd.DataFrame) -> list:
    """DataFrame -> JSON-safe list of dicts (handles numpy types, NaN and dates)."""
    return json.loads(df.to_json(orient="records", date_format="iso"))


protected = [Depends(require_api_key)]


# ------------------------------------------------------------------ models
class Message(BaseModel):
    role: Literal["user", "assistant"]
    content: str = Field(max_length=2000)


class ChatRequest(BaseModel):
    message: str = Field(min_length=1, max_length=2000)
    history: list[Message] = Field(default_factory=list, max_length=20)
    session_id: str = Field(default="default", max_length=64)  # used for the rate limit


class ChatResponse(BaseModel):
    reply: str


# ------------------------------------------------------------------ endpoints
@app.get("/health")
def health():
    """Liveness/readiness check: confirms the database is reachable. No auth, no secrets."""
    try:
        with core.get_conn() as conn:
            conn.execute("SELECT 1")
    except Exception as exc:
        raise HTTPException(503, "Database unavailable.") from exc
    return {"status": "ok", "model": core.MODEL}


@app.post("/chat", response_model=ChatResponse, dependencies=protected)
def chat(req: ChatRequest):
    try:
        reply = core.chat_turn([m.model_dump() for m in req.history], req.message,
                               req.session_id)
    except Exception as exc:  # model/network failure: don't leak internals to the client
        log.exception("chat failed")
        raise HTTPException(502, "The AI service is unavailable. Please try again.") from exc
    return ChatResponse(reply=reply)


@app.get("/expenses", dependencies=protected)
def list_expenses(limit: Annotated[int, Query(ge=1, le=500)] = 50,
                  start: date | None = None, end: date | None = None):
    df = an.load_expenses()
    if df.empty:
        return []
    if start:
        df = df[df["date"] >= pd.Timestamp(start)]
    if end:
        df = df[df["date"] <= pd.Timestamp(end)]
    out = df.sort_values("spent_at", ascending=False).head(limit)[
        ["id", "spent_at", "item", "amount_inr", "category"]].copy()
    out["spent_at"] = out["spent_at"].dt.strftime("%Y-%m-%d %H:%M")
    return _records(out)


@app.get("/analytics/summary", dependencies=protected)
def analytics_summary(start: date | None = None, end: date | None = None):
    today = date.today()
    start, end = start or today.replace(day=1), end or today
    if start > end:
        raise HTTPException(422, "start must not be after end.")
    empty = {"start": start.isoformat(), "end": end.isoformat(), "total": 0.0,
             "transactions": 0, "avg_per_day": 0.0, "top_category": "-",
             "top_category_amount": 0.0, "by_category": [], "monthly": []}
    df_all = an.load_expenses()
    if df_all.empty:
        return empty
    df = an.filter_range(df_all, start, end)
    if df.empty:
        return empty
    return {
        "start": start.isoformat(), "end": end.isoformat(),
        **an.kpis(df, start, end),
        "by_category": _records(an.category_table(df)),
        "monthly": _records(an.monthly_trend(df_all).reset_index()),
    }


@app.get("/llm/usage", dependencies=protected)
def llm_usage(days: Annotated[int, Query(ge=1, le=365)] = 7, include_eval: bool = False):
    """Model-call observability: volume, latency percentiles, tokens and error rate."""
    df = an.load_llm_calls(include_eval)
    if not df.empty:
        df = df[df["ts"] >= pd.Timestamp.now() - pd.Timedelta(days=days)]
    return {"days": days, **an.llm_summary(df), "daily": _records(an.llm_daily(df).reset_index())}