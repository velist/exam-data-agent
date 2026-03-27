from contextlib import asynccontextmanager
from fastapi import FastAPI, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
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
