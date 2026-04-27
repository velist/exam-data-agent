import json
import time
import logging
import uuid
from services import chat as chat_service
from services.chat import ChatError
from services.dataset_router import try_route
from services.debug import add_log, create_cancel_token, remove_cancel_token

logger = logging.getLogger("chat_stream")


def _sse(event: dict) -> str:
    return f"data: {json.dumps(event, ensure_ascii=False)}\n\n"


def stream_chat_events(message: str, history: list[dict], query_id: str | None = None, client_ip: str = "unknown"):
    """把聊天主链路拆成 SSE 事件流。只做事件编排，不复制业务逻辑。"""
    if query_id is None:
        query_id = uuid.uuid4().hex[:12]

    cancel_event = create_cancel_token(query_id)
    t_start = time.time()
    log_entry = {"query_id": query_id, "message": message, "history_len": len(history), "routed": False}

    def _add_log(entry: dict):
        add_log(entry, client_ip)

    def _check_cancel():
        if cancel_event.is_set():
            raise CancelQueryError(query_id)

    try:
        _check_cancel()

        validation_error = chat_service._validate_input(message)
        if validation_error:
            log_entry["error"] = validation_error["message"]
            _add_log(log_entry)
            yield _sse({"type": "error", "code": validation_error["code"], "message": validation_error["message"]})
            return

        yield _sse({"type": "status", "stage": "understanding", "text": "正在理解问题..."})

        _check_cancel()

        # 尝试快速路由：命中预生成数据集则跳过 NL2SQL + DB
        routed_data = try_route(message, history)

        if routed_data is not None:
            logger.info("快速路由命中，跳过 NL2SQL")
            log_entry["routed"] = True
            table_data = routed_data
        else:
            # 未命中，走原有 NL2SQL 链路
            try:
                _check_cancel()
                yield _sse({"type": "status", "stage": "generating_sql", "text": "正在生成查询语句..."})
                sql = chat_service._generate_sql_with_fix(message, history)
                log_entry["sql"] = sql
            except CancelQueryError:
                raise
            except ChatError as e:
                log_entry["error"] = str(e)
                _add_log(log_entry)
                yield _sse({"type": "error", "code": e.code, "message": str(e)})
                return
            except Exception:
                logger.exception("SQL generation failed")
                log_entry["error"] = "AI服务不可用"
                _add_log(log_entry)
                yield _sse({"type": "error", "code": "LLM_ERROR", "message": "AI服务暂时不可用，请稍后重试"})
                return

            try:
                _check_cancel()
                yield _sse({"type": "status", "stage": "querying", "text": "正在查询数据..."})
                final_sql, table_data = chat_service._execute_query_with_retry(message, history, sql)
                log_entry["sql"] = final_sql
            except CancelQueryError:
                raise
            except ChatError as e:
                log_entry["error"] = str(e)
                _add_log(log_entry)
                yield _sse({"type": "error", "code": e.code, "message": str(e)})
                return
            except Exception:
                logger.exception("Query execution failed")
                log_entry["error"] = "查询执行失败"
                _add_log(log_entry)
                yield _sse({"type": "error", "code": "SQL_FAILED", "message": "查询执行失败，请换个方式描述您的问题"})
                return

        _check_cancel()

        row_count = len(table_data.get("rows", [])) if table_data else 0
        log_entry["row_count"] = row_count
        yield _sse({"type": "table", "columns": table_data["columns"], "rows": table_data["rows"]})

        _check_cancel()
        yield _sse({"type": "status", "stage": "summarizing", "text": "正在生成分析结论..."})

        try:
            for text in chat_service._stream_summary_chunks(message, table_data, history):
                if cancel_event.is_set():
                    break
                if text:
                    yield _sse({"type": "answer_chunk", "text": text})
        except Exception:
            logger.exception("Summary generation failed, using fallback")
            yield _sse({"type": "answer_chunk", "text": "查询完成，请查看下方数据表格。"})

        if cancel_event.is_set():
            log_entry["cancelled"] = True
            _add_log(log_entry)
            yield _sse({"type": "error", "code": "CANCELLED", "message": "查询已被取消"})
            return

        elapsed = round(time.time() - t_start, 2)
        log_entry["elapsed"] = elapsed
        log_entry["status"] = "ok"
        _add_log(log_entry)

        yield _sse({"type": "done"})

    except CancelQueryError:
        elapsed = round(time.time() - t_start, 2)
        log_entry["cancelled"] = True
        log_entry["elapsed"] = elapsed
        _add_log(log_entry)
        yield _sse({"type": "error", "code": "CANCELLED", "message": "查询已被取消"})
    finally:
        remove_cancel_token(query_id)


class CancelQueryError(Exception):
    """查询被取消时抛出"""
    def __init__(self, query_id: str):
        self.query_id = query_id
        super().__init__(f"Query {query_id} was cancelled")
