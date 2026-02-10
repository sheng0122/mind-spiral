"""Mind Spiral API Server — FastAPI 薄包裝"""

from __future__ import annotations

import os
import time
from pathlib import Path

from fastapi import Depends, FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from engine.auth import Role, require_authenticated, require_owner, resolve_role
from engine.config import get_owner_dir, load_config
from engine.schemas_api import (
    APIResponse,
    AskRequest,
    ErrorDetail,
    ErrorResponse,
    GenerateRequest,
    IngestRequest,
    QueryRequest,
)

_start_time = time.time()
_config = load_config()

app = FastAPI(title="Mind Spiral API", version="0.1.0")

# CORS
_cors_origins = os.environ.get("MIND_SPIRAL_CORS_ORIGINS", "*").split(",")
app.add_middleware(
    CORSMiddleware,
    allow_origins=[o.strip() for o in _cors_origins],
    allow_methods=["*"],
    allow_headers=["*"],
)


# ─── Exception handler ───


@app.exception_handler(HTTPException)
async def http_exception_handler(request, exc):
    return JSONResponse(
        status_code=exc.status_code,
        content=ErrorResponse(
            error=ErrorDetail(code=str(exc.status_code), message=exc.detail),
        ).model_dump(),
    )


# ─── Helpers ───


def _check_owner_exists(owner_id: str):
    owner_dir = get_owner_dir(_config, owner_id)
    if not (owner_dir / "signals.jsonl").exists():
        raise HTTPException(status_code=404, detail=f"Owner '{owner_id}' not found")


# ─── Endpoints ───


@app.get("/health")
async def health():
    """健康檢查 — 不需認證。"""
    import chromadb

    uptime = time.time() - _start_time
    return APIResponse(
        data={
            "version": "0.1.0",
            "uptime_seconds": round(uptime, 1),
            "chromadb_version": chromadb.__version__,
        },
    ).model_dump()


@app.get("/stats")
async def stats(owner_id: str):
    """統計資訊 — 不需認證。"""
    from engine.signal_store import SignalStore
    from engine.conviction_detector import _load_convictions
    from engine.trace_extractor import _load_traces
    from engine.frame_clusterer import _load_frames
    from engine.identity_scanner import _load_identity

    _check_owner_exists(owner_id)
    owner_dir = get_owner_dir(_config, owner_id)
    store = SignalStore(_config, owner_id)

    signal_stats = store.stats()
    convictions = _load_convictions(owner_dir)
    traces = _load_traces(owner_dir)
    frames = _load_frames(owner_dir)
    identities = _load_identity(owner_dir)

    return APIResponse(
        data={
            "signals": signal_stats,
            "convictions_count": len(convictions),
            "traces_count": len(traces),
            "frames_count": len(frames),
            "identities_count": len(identities),
        },
    ).model_dump()


@app.post("/ask")
async def ask_endpoint(
    req: AskRequest,
    role: Role = Depends(resolve_role),
):
    """統一入口 — 自動判斷 query 或 generate。"""
    from engine.query_engine import ask

    _check_owner_exists(req.owner_id)
    result = ask(
        owner_id=req.owner_id,
        text=req.text,
        caller=req.caller_id,
        config=_config,
    )
    return APIResponse(data=result).model_dump()


@app.post("/query")
async def query_endpoint(
    req: QueryRequest,
    role: Role = Depends(resolve_role),
):
    """五層感知查詢。"""
    from engine.query_engine import query

    _check_owner_exists(req.owner_id)
    result = query(
        owner_id=req.owner_id,
        question=req.question,
        caller=req.caller_id,
        config=_config,
    )
    return APIResponse(data=result).model_dump()


@app.post("/generate")
async def generate_endpoint(
    req: GenerateRequest,
    role: Role = Depends(resolve_role),
):
    """Generation Mode — 產出內容。"""
    from engine.query_engine import generate

    _check_owner_exists(req.owner_id)
    result = generate(
        owner_id=req.owner_id,
        task=req.text,
        output_type=req.output_type,
        caller=req.caller_id,
        config=_config,
    )
    return APIResponse(data=result).model_dump()


@app.post("/ingest")
async def ingest_endpoint(
    req: IngestRequest,
    role: Role = Depends(require_owner),
):
    """寫入 signals — 限 owner。"""
    from engine.models import Signal, SignalContent, SignalSource, SignalLifecycle
    from engine.signal_store import SignalStore

    _check_owner_exists(req.owner_id)
    store = SignalStore(_config, req.owner_id)

    # 轉換 SignalInput → Signal
    signals = []
    for s in req.signals:
        signal = Signal(
            owner_id=req.owner_id,
            signal_id=s.signal_id,
            direction=s.direction,
            modality=s.modality,
            authority=s.authority,
            content=SignalContent(
                text=s.text,
                type=s.content_type,
                reasoning=s.reasoning,
                confidence=s.confidence,
                emotion=s.emotion,
            ),
            source=SignalSource(
                date=s.date,
                context=s.context,
                participants=s.participants,
                source_file=s.source_file,
            ),
            topics=s.topics,
            lifecycle=SignalLifecycle(active=True, created_at=s.date),
        )
        signals.append(signal)

    count = store.ingest(signals)
    return APIResponse(
        data={"ingested": count, "total_submitted": len(req.signals)},
    ).model_dump()
