import os
from pathlib import Path
from contextlib import asynccontextmanager
from fastapi import FastAPI, Query, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse, FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

DIST_DIR = Path(__file__).resolve().parent.parent / "frontend" / "dist"
from services.chat import chat
from services.chat_stream import stream_chat_events
from services.report import get_weekly_report, get_monthly_report
from services.report_cache import init_cache
from services.insight import stream_insight


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_cache()
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
def api_chat_stream(req: ChatRequest):
    return StreamingResponse(
        stream_chat_events(req.message, req.history),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


@app.get("/api/report/weekly")
def api_weekly_report(date: str = Query(..., description="目标周内任意日期，如2026-03-27")):
    return get_weekly_report(date)


@app.get("/api/report/monthly")
def api_monthly_report(month: str = Query(..., description="目标月份，如2026-03")):
    return get_monthly_report(month)


@app.get("/api/insight/stream")
async def api_insight_stream(
    type: str = Query(..., description="weekly或monthly"),
    date: str = Query(..., description="日期参数"),
):
    return StreamingResponse(
        stream_insight(type, date),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


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
        """SPA fallback: 非 /api 路径全部返回 index.html"""
        return FileResponse(str(DIST_DIR / "index.html"))
