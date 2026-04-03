import json
import logging
from services import chat as chat_service
from services.chat import ChatError
from services.dataset_router import try_route

logger = logging.getLogger("chat_stream")


def _sse(event: dict) -> str:
    return f"data: {json.dumps(event, ensure_ascii=False)}\n\n"


def stream_chat_events(message: str, history: list[dict]):
    """把聊天主链路拆成 SSE 事件流。只做事件编排，不复制业务逻辑。"""
    validation_error = chat_service._validate_input(message)
    if validation_error:
        yield _sse({"type": "error", "code": validation_error["code"], "message": validation_error["message"]})
        return

    yield _sse({"type": "status", "stage": "understanding", "text": "正在理解问题..."})

    # 尝试快速路由：命中预生成数据集则跳过 NL2SQL + DB
    routed_data = try_route(message, history)

    if routed_data is not None:
        logger.info("快速路由命中，跳过 NL2SQL")
        table_data = routed_data
    else:
        # 未命中，走原有 NL2SQL 链路
        try:
            yield _sse({"type": "status", "stage": "generating_sql", "text": "正在生成查询语句..."})
            sql = chat_service._generate_sql_with_fix(message, history)
        except ChatError as e:
            yield _sse({"type": "error", "code": e.code, "message": str(e)})
            return
        except Exception:
            logger.exception("SQL generation failed")
            yield _sse({"type": "error", "code": "LLM_ERROR", "message": "AI服务暂时不可用，请稍后重试"})
            return

        try:
            yield _sse({"type": "status", "stage": "querying", "text": "正在查询数据..."})
            final_sql, table_data = chat_service._execute_query_with_retry(message, history, sql)
        except ChatError as e:
            yield _sse({"type": "error", "code": e.code, "message": str(e)})
            return
        except Exception:
            logger.exception("Query execution failed")
            yield _sse({"type": "error", "code": "SQL_FAILED", "message": "查询执行失败，请换个方式描述您的问题"})
            return

    yield _sse({"type": "table", "columns": table_data["columns"], "rows": table_data["rows"]})

    yield _sse({"type": "status", "stage": "summarizing", "text": "正在生成分析结论..."})

    try:
        for text in chat_service._stream_summary_chunks(message, table_data, history):
            if text:
                yield _sse({"type": "answer_chunk", "text": text})
    except Exception:
        logger.exception("Summary generation failed, using fallback")
        yield _sse({"type": "answer_chunk", "text": "查询完成，请查看下方数据表格。"})

    yield _sse({"type": "done"})
