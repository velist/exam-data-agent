"""
阿里云 DashScope ASR WebSocket 代理
前端 → 本后端 WS → DashScope ASR WS

解决浏览器 WebSocket 无法设置 Authorization Header 的问题。
"""

import asyncio
import json
import logging
import uuid

import websockets

from config import QWEN_API_KEY

logger = logging.getLogger(__name__)

DASHSCOPE_WS_URL = "wss://dashscope.aliyuncs.com/api-ws/v1/inference/"
ASR_MODEL = "fun-asr-realtime"


async def proxy_asr(client_ws):
    """
    代理单次 ASR 会话：
    1. 连接 DashScope WebSocket（带 Authorization header）
    2. 发送 run-task 启动识别
    3. 双向转发：前端音频 → DashScope，DashScope 结果 → 前端
    """
    task_id = uuid.uuid4().hex

    headers = {"Authorization": f"bearer {QWEN_API_KEY}"}

    try:
        async with websockets.connect(
            DASHSCOPE_WS_URL,
            additional_headers=headers,
            max_size=10 * 1024 * 1024,
        ) as asr_ws:
            # 1. 发送 run-task
            run_task = {
                "header": {
                    "action": "run-task",
                    "task_id": task_id,
                    "streaming": "duplex",
                },
                "payload": {
                    "task_group": "audio",
                    "task": "asr",
                    "function": "recognition",
                    "model": ASR_MODEL,
                    "parameters": {
                        "format": "pcm",
                        "sample_rate": 16000,
                    },
                    "input": {},
                },
            }
            await asr_ws.send(json.dumps(run_task))
            logger.info(f"ASR 任务已启动: {task_id}")

            # 2. 等待 task-started
            started_msg = await asyncio.wait_for(asr_ws.recv(), timeout=10)
            started = json.loads(started_msg)
            if started.get("header", {}).get("event") != "task-started":
                error_msg = started.get("header", {}).get("error_message", "启动失败")
                await client_ws.send_json({"type": "error", "message": error_msg})
                return

            await client_ws.send_json({"type": "ready"})

            # 3. 双向转发
            async def forward_audio():
                """前端 → DashScope：二进制音频数据"""
                try:
                    while True:
                        msg = await client_ws.receive()
                        if msg["type"] == "websocket.disconnect":
                            break
                        if msg["type"] == "websocket.receive":
                            if "bytes" in msg and msg["bytes"]:
                                await asr_ws.send(msg["bytes"])
                            elif "text" in msg:
                                data = json.loads(msg["text"])
                                if data.get("action") == "stop":
                                    break
                except Exception as e:
                    logger.debug(f"音频转发结束: {e}")

                # 发送 finish-task
                finish = {
                    "header": {
                        "action": "finish-task",
                        "task_id": task_id,
                        "streaming": "duplex",
                    },
                    "payload": {"input": {}},
                }
                await asr_ws.send(json.dumps(finish))

            async def forward_results():
                """DashScope → 前端：识别结果"""
                try:
                    async for raw in asr_ws:
                        if isinstance(raw, bytes):
                            continue
                        msg = json.loads(raw)
                        event = msg.get("header", {}).get("event", "")

                        if event == "result-generated":
                            output = msg.get("payload", {}).get("output", {})
                            sentence = output.get("sentence", {})
                            text = sentence.get("text", "")
                            is_end = sentence.get("sentence_end", False)
                            if text:
                                await client_ws.send_json({
                                    "type": "result",
                                    "text": text,
                                    "is_end": is_end,
                                })
                        elif event == "task-finished":
                            await client_ws.send_json({"type": "done"})
                            break
                        elif event == "task-failed":
                            error_msg = msg.get("header", {}).get("error_message", "识别失败")
                            await client_ws.send_json({"type": "error", "message": error_msg})
                            break
                except Exception as e:
                    logger.debug(f"结果转发结束: {e}")

            # 并行运行音频转发和结果转发
            await asyncio.gather(forward_audio(), forward_results())

    except Exception as e:
        logger.error(f"ASR 代理错误: {e}")
        try:
            await client_ws.send_json({"type": "error", "message": str(e)})
        except Exception:
            pass
