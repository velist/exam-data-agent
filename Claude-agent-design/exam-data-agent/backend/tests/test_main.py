import os
import sys
import json

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from fastapi.testclient import TestClient
import services.chat as chat_service
import main as main_module


def test_chat_stream_route_exists_and_returns_sse(monkeypatch):
    """POST /api/chat/stream must be registered and return text/event-stream"""
    monkeypatch.setattr(chat_service, "_validate_input", lambda message: None)
    monkeypatch.setattr(chat_service, "_generate_sql_with_fix", lambda message, history: "SELECT 1")
    monkeypatch.setattr(chat_service, "_execute_query_with_retry", lambda message, history, sql: (sql, {"columns": ["x"], "rows": [["1"]]}))
    monkeypatch.setattr(chat_service, "_stream_summary_chunks", lambda message, table_data, history: iter(["ok"]))

    client = TestClient(main_module.app)
    response = client.post("/api/chat/stream", json={"message": "test", "history": []})

    assert response.status_code == 200
    assert "text/event-stream" in response.headers["content-type"]
    assert response.headers.get("cache-control") == "no-cache"
    assert response.headers.get("x-accel-buffering") == "no"

    events = []
    for line in response.text.strip().split("\n"):
        line = line.strip()
        if line.startswith("data: "):
            events.append(json.loads(line[6:]))

    types_list = [e["type"] for e in events]
    assert "status" in types_list
    assert "done" in types_list


def test_chat_route_still_works(monkeypatch):
    """Existing POST /api/chat must not break"""
    monkeypatch.setattr(chat_service, "_validate_input", lambda message: None)
    monkeypatch.setattr(chat_service, "_generate_sql_with_fix", lambda message, history: "SELECT 1")
    monkeypatch.setattr(chat_service, "_execute_query_with_retry", lambda message, history, sql: (sql, {"columns": ["x"], "rows": [["1"]]}))
    monkeypatch.setattr(chat_service, "_summarize_result", lambda message, table_data, history: "ok")

    client = TestClient(main_module.app)
    response = client.post("/api/chat", json={"message": "test", "history": []})

    assert response.status_code == 200
    data = response.json()
    assert "answer" in data
