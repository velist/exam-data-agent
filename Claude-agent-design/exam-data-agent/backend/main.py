import os
import uuid
from datetime import datetime
from pathlib import Path
from contextlib import asynccontextmanager
from fastapi import FastAPI, Query, WebSocket, WebSocketDisconnect, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse, FileResponse, Response
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

DIST_DIR = Path(__file__).resolve().parent.parent / "frontend" / "dist"
from services.chat import chat
from services.chat_stream import stream_chat_events
from services.report import get_weekly_report, get_monthly_report, get_range_report
from services.report_cache import init_cache
from services.dataset_cache import init_dataset_cache
from services.insight import stream_insight
from services.debug import get_logs, export_logs, clear_logs, cancel_query, cleanup_old_logs


def _client_ip(request: Request) -> str:
    """获取客户端真实 IP，优先从反向代理头获取"""
    forwarded = request.headers.get("X-Forwarded-For")
    if forwarded:
        return forwarded.split(",")[0].strip()
    real_ip = request.headers.get("X-Real-IP")
    if real_ip:
        return real_ip.strip()
    host = request.client.host if request.client else "unknown"
    return host


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_cache()
    init_dataset_cache()
    cleanup_old_logs()
    yield


app = FastAPI(title="考试宝典数据助手", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


class ChatRequest(BaseModel):
    message: str
    history: list[dict] = []


@app.post("/api/chat")
def api_chat(req: ChatRequest):
    return chat(req.message, req.history)


@app.post("/api/chat/stream")
def api_chat_stream(req: ChatRequest, request: Request):
    query_id = uuid.uuid4().hex[:12]
    ip = _client_ip(request)
    return StreamingResponse(
        stream_chat_events(req.message, req.history, query_id=query_id, client_ip=ip),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
            "X-Query-Id": query_id,
        },
    )


@app.get("/api/report/weekly")
def api_weekly_report(date: str = Query(..., description="目标周内任意日期，如2026-03-27")):
    return get_weekly_report(date)


@app.get("/api/report/monthly")
def api_monthly_report(month: str = Query(..., description="目标月份，如2026-03")):
    return get_monthly_report(month)


@app.get("/api/report/range")
def api_range_report(
    start: str = Query(..., description="开始日期，如2026-01-01"),
    end: str = Query(..., description="结束日期，如2026-03-31"),
):
    try:
        return get_range_report(start, end)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.get("/api/insight/stream")
async def api_insight_stream(
    type: str = Query(..., description="weekly、monthly或range"),
    date: str | None = Query(None, description="周报/月报日期参数"),
    start: str | None = Query(None, description="区间开始日期"),
    end: str | None = Query(None, description="区间结束日期"),
):
    return StreamingResponse(
        stream_insight(type, date=date, start=start, end=end),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


# --- 调试 API ---


@app.get("/api/debug/logs")
def api_debug_logs(request: Request, limit: int = Query(50, ge=1, le=200)):
    ip = _client_ip(request)
    return {"logs": get_logs(ip, limit)}


@app.get("/api/debug/logs/export")
def api_debug_logs_export(request: Request):
    """导出日志：服务器保存 + 返回下载"""
    ip = _client_ip(request)
    json_str, saved_path = export_logs(ip)
    filename = f"debug-logs-{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    return Response(
        content=json_str,
        media_type="application/json",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@app.delete("/api/debug/logs")
def api_debug_logs_clear(request: Request):
    ip = _client_ip(request)
    clear_logs(ip)
    return {"ok": True}


@app.post("/api/debug/cancel/{query_id}")
def api_debug_cancel(query_id: str):
    ok = cancel_query(query_id)
    return {"ok": ok, "query_id": query_id}


@app.get("/api/health")
def health():
    return {"status": "ok"}


@app.websocket("/api/asr")
async def api_asr(ws: WebSocket):
    await ws.accept()
    try:
        from services.asr_proxy import proxy_asr
        await proxy_asr(ws)
    except WebSocketDisconnect:
        pass


# --- 前端静态文件 (SPA) ---
if DIST_DIR.exists():
    app.mount("/assets", StaticFiles(directory=str(DIST_DIR / "assets")), name="static")

    @app.get("/")
    async def serve_index():
        return FileResponse(str(DIST_DIR / "index.html"))

    @app.get("/{full_path:path}")
    async def serve_spa(full_path: str):
        return FileResponse(str(DIST_DIR / "index.html"))
