import { useState, useRef, useEffect, useCallback } from "react";
import ChatBubble from "../components/ChatBubble";
import { streamChat, StreamChatError, BASE_URL } from "../api";
import {
  type ChatMessage,
  buildHistorySnapshot,
  createStreamingAssistantMessage,
  applyStreamEvent,
  markInterruptedMessage,
  generateMessageId,
} from "./chatMessageUtils";
import "../styles/chat.css";
import "../styles/test.css";

interface LogEntry {
  query_id: string;
  timestamp: string;
  message: string;
  sql?: string;
  row_count?: number;
  elapsed?: number;
  status?: string;
  error?: string;
  cancelled?: boolean;
  routed?: boolean;
  history_len?: number;
}

export default function Test() {
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [input, setInput] = useState("");
  const [loading, setLoading] = useState(false);
  const [queryId, setQueryId] = useState<string | null>(null);
  const [logs, setLogs] = useState<LogEntry[]>([]);
  const [logExpanded, setLogExpanded] = useState<Record<string, boolean>>({});

  const bottomRef = useRef<HTMLDivElement>(null);
  const abortRef = useRef<AbortController | null>(null);
  const placeholderIdRef = useRef<string | null>(null);

  // Fetch logs periodically
  const fetchLogs = useCallback(async () => {
    try {
      const res = await fetch(`${BASE_URL}/api/debug/logs?limit=100`);
      if (res.ok) {
        const data = await res.json();
        setLogs(data.logs || []);
      }
    } catch {}
  }, []);

  useEffect(() => {
    fetchLogs();
    const interval = setInterval(fetchLogs, 2000);
    return () => clearInterval(interval);
  }, [fetchLogs]);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages]);

  const handleCancel = async () => {
    // Frontend abort
    if (abortRef.current) {
      abortRef.current.abort();
    }
    // Backend cancel
    if (queryId) {
      try {
        await fetch(`${BASE_URL}/api/debug/cancel/${queryId}`, { method: "POST" });
      } catch {}
    }
  };

  const handleExportLogs = async () => {
    try {
      const res = await fetch(`${BASE_URL}/api/debug/logs/export`);
      if (!res.ok) return;
      const blob = await res.blob();
      const url = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      // 从 Content-Disposition 取文件名，或使用默认名
      const disposition = res.headers.get("Content-Disposition") || "";
      const match = disposition.match(/filename="?([^";\n]+)"?/);
      a.download = match ? match[1] : `debug-logs-${new Date().toISOString().slice(0, 10)}.json`;
      a.click();
      URL.revokeObjectURL(url);
    } catch {}
  };

  const handleClearLogs = async () => {
    try {
      await fetch(`${BASE_URL}/api/debug/logs`, { method: "DELETE" });
      setLogs([]);
      setLogExpanded({});
    } catch {}
  };

  const handleSend = async (text?: string) => {
    const msg = text || input.trim();
    if (!msg || loading) return;

    abortRef.current?.abort();
    const controller = new AbortController();
    abortRef.current = controller;

    const userMessage: ChatMessage = {
      id: generateMessageId(),
      role: "user",
      content: msg,
    };
    const historySnapshot = buildHistorySnapshot(messages);
    const placeholder = createStreamingAssistantMessage();
    placeholderIdRef.current = placeholder.id;

    setMessages((prev) => [...prev, userMessage, placeholder]);
    setInput("");
    setLoading(true);

    // Extract query_id from response headers isn't possible with fetch,
    // so we use a temp id from the placeholder
    setQueryId(placeholder.id);

    const updatePlaceholder = (updater: (msg: ChatMessage) => ChatMessage) => {
      const targetId = placeholderIdRef.current;
      setMessages((prev) =>
        prev.map((m) => (m.id === targetId ? updater(m) : m)),
      );
    };

    try {
      await streamChat(
        msg,
        historySnapshot,
        {
          onEvent: (event) => {
            updatePlaceholder((m) => applyStreamEvent(m, event));
          },
        },
        { signal: controller.signal },
      );
    } catch (error) {
      if (error instanceof StreamChatError && error.isAbort) {
        const targetId = placeholderIdRef.current;
        setMessages((prev) => {
          const target = prev.find((m) => m.id === targetId);
          if (target && (target.content || target.table)) {
            return prev.map((m) =>
              m.id === targetId ? markInterruptedMessage(m) : m,
            );
          }
          return prev.filter((m) => m.id !== targetId);
        });
        setQueryId(null);
        setLoading(false);
        return;
      }
      updatePlaceholder((m) => markInterruptedMessage(m));
    } finally {
      if (abortRef.current === controller) {
        abortRef.current = null;
        placeholderIdRef.current = null;
        setQueryId(null);
        setLoading(false);
      }
    }
  };

  const toggleLogExpand = (id: string) => {
    setLogExpanded((prev) => ({ ...prev, [id]: !prev[id] }));
  };

  const formatTime = (ts: string) => {
    try {
      const d = new Date(ts);
      return d.toLocaleTimeString("zh-CN", { hour: "2-digit", minute: "2-digit", second: "2-digit" });
    } catch {
      return ts;
    }
  };

  return (
    <div className="test-page">
      {/* Top bar */}
      <header className="test-header">
        <div className="test-header-left">
          <span className="test-title">调试面板</span>
          {queryId && <span className="test-query-id">Query: {queryId}</span>}
        </div>
        <div className="test-header-right">
          {loading && (
            <button className="test-btn test-btn-danger" onClick={handleCancel}>
              中断查询
            </button>
          )}
          <button className="test-btn" onClick={handleExportLogs}>
            导出日志
          </button>
          <button className="test-btn" onClick={handleClearLogs}>
            清空日志
          </button>
        </div>
      </header>

      <div className="test-main">
        {/* Left: Chat area */}
        <div className="test-chat">
          <div className="chat-area" style={{ flex: 1 }}>
            {messages.length === 0 && (
              <div className="message ai-msg guide-message">
                调试模式：输入查询以测试链路，可中断、可查看日志、可导出。
              </div>
            )}
            {messages.map((msg) => (
              <ChatBubble
                key={msg.id}
                role={msg.role}
                content={msg.content}
                table={msg.table}
                statusText={msg.statusText}
                error={msg.error}
              />
            ))}
            <div ref={bottomRef} />
          </div>

          <div className="input-bar">
            <div className="input-wrap">
              <input
                type="text"
                placeholder="输入调试查询..."
                value={input}
                onChange={(e) => setInput(e.target.value)}
                onKeyDown={(e) => { if (e.key === "Enter") handleSend(); }}
                disabled={loading}
              />
            </div>
            <button
              className="send-btn"
              onClick={() => handleSend()}
              disabled={loading}
            >
              <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                <line x1="22" y1="2" x2="11" y2="13" />
                <polygon points="22 2 15 22 11 13 2 9 22 2" />
              </svg>
            </button>
          </div>
        </div>

        {/* Right: Log panel */}
        <div className="test-log-panel">
          <div className="test-log-header">
            查询日志 ({logs.length})
          </div>
          <div className="test-log-list">
            {logs.length === 0 && (
              <div className="test-log-empty">暂无日志，发起查询后自动记录</div>
            )}
            {[...logs].reverse().map((entry) => {
              const id = entry.query_id || entry.timestamp;
              const expanded = logExpanded[id];
              return (
                <div
                  key={id}
                  className={`test-log-entry ${entry.cancelled ? "cancelled" : ""} ${entry.error ? "error" : ""}`}
                  onClick={() => toggleLogExpand(id)}
                >
                  <div className="test-log-entry-head">
                    <span className={`test-log-status ${entry.error ? "err" : entry.cancelled ? "cancel" : "ok"}`}>
                      {entry.cancelled ? "已取消" : entry.error ? "失败" : "OK"}
                    </span>
                    <span className="test-log-msg">{entry.message}</span>
                    <span className="test-log-meta">
                      {entry.routed && <span className="tag">路由</span>}
                      {entry.row_count !== undefined && <span>{entry.row_count}行</span>}
                      {entry.elapsed !== undefined && <span>{entry.elapsed}s</span>}
                      <span>{formatTime(entry.timestamp)}</span>
                    </span>
                  </div>
                  {expanded && (
                    <div className="test-log-entry-detail">
                      {entry.sql && (
                        <div className="test-log-field">
                          <label>SQL</label>
                          <pre>{entry.sql}</pre>
                        </div>
                      )}
                      {entry.error && (
                        <div className="test-log-field">
                          <label>错误</label>
                          <pre className="err">{entry.error}</pre>
                        </div>
                      )}
                      <div className="test-log-field-meta">
                        <span>Query ID: {entry.query_id}</span>
                        {entry.history_len !== undefined && <span>History: {entry.history_len}</span>}
                      </div>
                    </div>
                  )}
                </div>
              );
            })}
          </div>
        </div>
      </div>
    </div>
  );
}
