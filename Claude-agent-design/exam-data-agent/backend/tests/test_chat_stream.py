import os
import sys
import json
import types

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
import services.chat_stream as chat_stream
import services.chat as chat_service


def _collect_events(gen):
    events = []
    for chunk in gen:
        text = chunk.decode() if isinstance(chunk, bytes) else chunk
        if not text.strip():
            continue
        assert text.startswith("data: "), f"Bad SSE frame: {text!r}"
        events.append(json.loads(text[len("data: "):].strip()))
    return events


def test_stream_chat_success_sequence(monkeypatch):
    monkeypatch.setattr(chat_stream, "try_route", lambda msg, hist: None)
    monkeypatch.setattr(chat_service, "_validate_input", lambda message: None)
    monkeypatch.setattr(chat_service, "_generate_sql_with_fix", lambda message, history: "SELECT 1")
    monkeypatch.setattr(chat_service, "_execute_query_with_retry", lambda message, history, sql: (sql, {"columns": ["指标", "数值"], "rows": [["注册用户", "1200"]]}))
    monkeypatch.setattr(chat_service, "_stream_summary_chunks", lambda message, table_data, history: iter(["上周注册用户1200人，", "环比增长10%。"]))

    events = _collect_events(chat_stream.stream_chat_events("上周注册用户多少", []))

    types_list = [e["type"] for e in events]
    assert types_list == ["status", "status", "status", "table", "status", "answer_chunk", "answer_chunk", "done"]
    assert events[0]["stage"] == "understanding"
    assert events[1]["stage"] == "generating_sql"
    assert events[2]["stage"] == "querying"
    assert events[3]["rows"] == [["注册用户", "1200"]]
    assert events[4]["stage"] == "summarizing"


def test_stream_chat_invalid_input_returns_error(monkeypatch):
    monkeypatch.setattr(chat_service, "_validate_input", lambda message: {"error": True, "code": "INVALID_INPUT", "message": "输入过长"})

    events = _collect_events(chat_stream.stream_chat_events("x" * 9999, []))

    assert len(events) == 1
    assert events[0]["type"] == "error"
    assert events[0]["code"] == "INVALID_INPUT"


def test_stream_chat_sql_failed_returns_error(monkeypatch):
    monkeypatch.setattr(chat_stream, "try_route", lambda msg, hist: None)
    monkeypatch.setattr(chat_service, "_validate_input", lambda message: None)
    monkeypatch.setattr(chat_service, "_generate_sql_with_fix", _raise_chat_error("SQL_FAILED", "无法生成合规的查询语句"))

    events = _collect_events(chat_stream.stream_chat_events("上周注册用户多少", []))

    error_events = [e for e in events if e["type"] == "error"]
    assert len(error_events) == 1
    assert error_events[0]["code"] == "SQL_FAILED"
    assert not any(e["type"] == "done" for e in events)


def test_stream_chat_sql_timeout_returns_error(monkeypatch):
    monkeypatch.setattr(chat_stream, "try_route", lambda msg, hist: None)
    monkeypatch.setattr(chat_service, "_validate_input", lambda message: None)
    monkeypatch.setattr(chat_service, "_generate_sql_with_fix", lambda message, history: "SELECT 1")
    monkeypatch.setattr(chat_service, "_execute_query_with_retry", _raise_chat_error("SQL_TIMEOUT", "查询超时"))

    events = _collect_events(chat_stream.stream_chat_events("上周注册用户多少", []))

    error_events = [e for e in events if e["type"] == "error"]
    assert len(error_events) == 1
    assert error_events[0]["code"] == "SQL_TIMEOUT"
    assert not any(e["type"] == "done" for e in events)


def test_stream_chat_zero_rows_still_sends_table(monkeypatch):
    monkeypatch.setattr(chat_stream, "try_route", lambda msg, hist: None)
    monkeypatch.setattr(chat_service, "_validate_input", lambda message: None)
    monkeypatch.setattr(chat_service, "_generate_sql_with_fix", lambda message, history: "SELECT 1")
    monkeypatch.setattr(chat_service, "_execute_query_with_retry", lambda message, history, sql: (sql, {"columns": ["注册用户"], "rows": []}))
    monkeypatch.setattr(chat_service, "_stream_summary_chunks", lambda message, table_data, history: iter(["查询结果为空。"]))

    events = _collect_events(chat_stream.stream_chat_events("上周注册用户多少", []))

    table_events = [e for e in events if e["type"] == "table"]
    assert len(table_events) == 1
    assert table_events[0]["rows"] == []
    assert any(e["type"] == "done" for e in events)


def test_stream_chat_summary_failure_sends_fallback_then_done(monkeypatch):
    monkeypatch.setattr(chat_stream, "try_route", lambda msg, hist: None)
    monkeypatch.setattr(chat_service, "_validate_input", lambda message: None)
    monkeypatch.setattr(chat_service, "_generate_sql_with_fix", lambda message, history: "SELECT 1")
    monkeypatch.setattr(chat_service, "_execute_query_with_retry", lambda message, history, sql: (sql, {"columns": ["注册用户"], "rows": [["1200"]]}))

    def failing_summary(message, table_data, history):
        raise RuntimeError("LLM exploded")

    monkeypatch.setattr(chat_service, "_stream_summary_chunks", failing_summary)

    events = _collect_events(chat_stream.stream_chat_events("上周注册用户多少", []))

    assert any(e["type"] == "table" for e in events)
    answer_chunks = [e for e in events if e["type"] == "answer_chunk"]
    assert len(answer_chunks) >= 1
    assert events[-1]["type"] == "done"
    assert not any(e["type"] == "error" for e in events)


def test_stream_chat_done_and_error_are_mutually_exclusive(monkeypatch):
    """done and error must never both appear in the same response"""
    monkeypatch.setattr(chat_stream, "try_route", lambda msg, hist: None)
    monkeypatch.setattr(chat_service, "_validate_input", lambda message: None)
    monkeypatch.setattr(chat_service, "_generate_sql_with_fix", lambda message, history: "SELECT 1")
    monkeypatch.setattr(chat_service, "_execute_query_with_retry", lambda message, history, sql: (sql, {"columns": ["x"], "rows": [["1"]]}))
    monkeypatch.setattr(chat_service, "_stream_summary_chunks", lambda message, table_data, history: iter(["ok"]))

    events = _collect_events(chat_stream.stream_chat_events("test", []))

    has_done = any(e["type"] == "done" for e in events)
    has_error = any(e["type"] == "error" for e in events)
    assert has_done != has_error or (not has_done and not has_error)


def test_stream_chat_follow_up_inherits_history(monkeypatch):
    captured = {}
    monkeypatch.setattr(chat_stream, "try_route", lambda msg, hist: None)
    monkeypatch.setattr(chat_service, "_validate_input", lambda message: None)

    def capture_sql(message, history):
        captured["history"] = history
        return "SELECT 1"

    monkeypatch.setattr(chat_service, "_generate_sql_with_fix", capture_sql)
    monkeypatch.setattr(chat_service, "_execute_query_with_retry", lambda message, history, sql: (sql, {"columns": ["x"], "rows": [["1"]]}))
    monkeypatch.setattr(chat_service, "_stream_summary_chunks", lambda message, table_data, history: iter(["ok"]))

    history = [
        {"role": "user", "content": "上周注册用户多少"},
        {"role": "assistant", "content": "上周注册用户1200人。"},
    ]
    events = _collect_events(chat_stream.stream_chat_events("环比呢", history))

    assert captured["history"] == history
    assert events[-1]["type"] == "done"


def _raise_chat_error(code, message):
    def raiser(*args, **kwargs):
        raise chat_service.ChatError(code, message)
    return raiser


# --- 快速路由命中测试 ---

def test_stream_chat_routed_skips_nl2sql(monkeypatch):
    """路由命中时跳过 NL2SQL 和 DB 查询，直接返回表格 + AI 总结"""
    fake_data = {"columns": ["月份", "销量", "销售额"], "rows": [["2026-03", "500", "12000"]]}
    monkeypatch.setattr(chat_stream, "try_route", lambda msg, hist: fake_data)
    monkeypatch.setattr(chat_service, "_validate_input", lambda message: None)
    monkeypatch.setattr(chat_service, "_stream_summary_chunks",
                        lambda message, table_data, history: iter(["3月销量500单。"]))

    events = _collect_events(chat_stream.stream_chat_events("3月销量", []))

    types_list = [e["type"] for e in events]
    # 不应出现 generating_sql 和 querying 阶段
    assert "status" in types_list
    assert events[-1]["type"] == "done"
    stages = [e.get("stage") for e in events if e["type"] == "status"]
    assert "generating_sql" not in stages
    assert "querying" not in stages
    assert "understanding" in stages
    assert "summarizing" in stages
    # 表格数据正确
    table_events = [e for e in events if e["type"] == "table"]
    assert len(table_events) == 1
    assert table_events[0]["rows"] == [["2026-03", "500", "12000"]]


def test_stream_chat_route_miss_falls_through_to_nl2sql(monkeypatch):
    """路由未命中时走正常 NL2SQL 流程"""
    monkeypatch.setattr(chat_stream, "try_route", lambda msg, hist: None)
    monkeypatch.setattr(chat_service, "_validate_input", lambda message: None)
    monkeypatch.setattr(chat_service, "_generate_sql_with_fix", lambda message, history: "SELECT 1")
    monkeypatch.setattr(chat_service, "_execute_query_with_retry",
                        lambda message, history, sql: (sql, {"columns": ["x"], "rows": [["1"]]}))
    monkeypatch.setattr(chat_service, "_stream_summary_chunks",
                        lambda message, table_data, history: iter(["ok"]))

    events = _collect_events(chat_stream.stream_chat_events("一个奇怪的问题", []))

    stages = [e.get("stage") for e in events if e["type"] == "status"]
    assert "generating_sql" in stages
    assert "querying" in stages
    assert events[-1]["type"] == "done"
