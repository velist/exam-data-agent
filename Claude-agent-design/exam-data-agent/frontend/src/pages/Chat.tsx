import { useState, useRef, useEffect, useCallback } from "react";
import { useNavigate } from "react-router-dom";
import ChatBubble from "../components/ChatBubble";
import { streamChat, sendChat, StreamChatError } from "../api";
import { useASR } from "../hooks/useASR";
import {
  type ChatMessage,
  buildHistorySnapshot,
  createStreamingAssistantMessage,
  applyStreamEvent,
  markInterruptedMessage,
  generateMessageId,
} from "./chatMessageUtils";
import "../styles/chat.css";

type AppState = "idle" | "thinking" | "speaking";

const SUGGESTIONS = [
  "本周注册用户情况",
  "付费转化率趋势",
  "上月销售总额",
  "活跃用户同比去年",
];

const STATE_TEXT_MAP: Record<AppState, string> = {
  idle: "我已准备好",
  thinking: "正在思考……",
  speaking: "正在回复……",
};

/* ---------- SVG Icons ---------- */
const SendIcon = () => (
  <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
    <line x1="22" y1="2" x2="11" y2="13" />
    <polygon points="22 2 15 22 11 13 2 9 22 2" />
  </svg>
);

const ChartIcon = () => (
  <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
    <line x1="18" y1="20" x2="18" y2="10" /><line x1="12" y1="20" x2="12" y2="4" /><line x1="6" y1="20" x2="6" y2="14" />
  </svg>
);

/* ---------- Float tag data ---------- */
const FLOAT_TAGS = [
  { label: "新用户注册数", icon: "user", style: { top: "18%", left: "8%", animationDelay: "0s" } },
  { label: "销售额查询", icon: "dollar", style: { top: "12%", right: "8%", animationDelay: "1.5s" } },
  { label: "销售额环比", icon: "trend", style: { top: "42%", right: "5%", animationDelay: "0.8s" } },
  { label: "用户答题情况", icon: "chat", style: { bottom: "28%", left: "8%", animationDelay: "2.2s" } },
  { label: "广告点击数", icon: "bar", style: { bottom: "22%", right: "10%", animationDelay: "3s" } },
];

const TAG_ICONS: Record<string, React.ReactNode> = {
  user: <svg className="tag-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.9" strokeLinecap="round" strokeLinejoin="round"><path d="M12 12a4 4 0 1 0 0-8a4 4 0 0 0 0 8Z" /><path d="M4 20a8 8 0 0 1 16 0" /></svg>,
  dollar: <svg className="tag-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.9" strokeLinecap="round" strokeLinejoin="round"><path d="M12 3v18" /><path d="M16.5 7.5c0-1.9-2-3.5-4.5-3.5S7.5 5.2 7.5 7c0 5 9 2 9 8c0 2-2 4-4.5 4S7.5 17.5 7.5 15.5" /></svg>,
  trend: <svg className="tag-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.9" strokeLinecap="round" strokeLinejoin="round"><path d="M4 19h16" /><path d="M6 15l4-4l3 2l5-6" /></svg>,
  chat: <svg className="tag-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.9" strokeLinecap="round" strokeLinejoin="round"><path d="M8 6h8" /><path d="M8 10h8" /><path d="M8 14h5" /><path d="M6 3h12a2 2 0 0 1 2 2v14l-4-3H6a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2Z" /></svg>,
  bar: <svg className="tag-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.9" strokeLinecap="round" strokeLinejoin="round"><path d="M4 19h16" /><path d="M7 15V9" /><path d="M12 15V6" /><path d="M17 15v-3" /></svg>,
};

/* ---------- Smart Sphere Component ---------- */
function SmartSphere({ id }: { id?: string }) {
  return (
    <div className="smart-sphere" id={id}>
      <div className="sphere-eyes">
        <div className="sphere-eye" />
        <div className="sphere-eye" />
      </div>
    </div>
  );
}

/* ========== Main Chat Page ========== */
export default function Chat() {
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [input, setInput] = useState("");
  const [loading, setLoading] = useState(false);
  const [screen, setScreen] = useState<"landing" | "chat">("landing");
  const [appState, setAppState] = useState<AppState>("idle");

  const bottomRef = useRef<HTMLDivElement>(null);
  const abortRef = useRef<AbortController | null>(null);
  const placeholderIdRef = useRef<string | null>(null);
  const inputRef = useRef<HTMLInputElement>(null);
  const sphereRef = useRef<HTMLDivElement>(null);

  const navigate = useNavigate();

  // ASR voice input
  const asrTextRef = useRef("");
  const asr = useASR({
    onResult: (text, isFinal) => {
      asrTextRef.current = text;
      setInput(text);
      if (isFinal) {
        asrTextRef.current = "";
      }
    },
    onDone: () => {
      const finalText = asrTextRef.current || input;
      if (finalText.trim()) {
        handleSend(finalText.trim());
      }
      asrTextRef.current = "";
    },
    onError: (msg) => {
      console.warn("ASR error:", msg);
    },
  });

  const toggleVoice = useCallback(() => {
    if (asr.state === "recording") {
      asr.stop();
    } else if (asr.state === "idle") {
      if (screen === "landing") openChat();
      asr.start();
    }
  }, [asr, screen]);

  // Auto-scroll on new messages
  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages]);

  // Sphere idle animation (blink / jump)
  useEffect(() => {
    const interval = setInterval(() => {
      if (appState !== "idle" || !sphereRef.current) return;
      const sphere = sphereRef.current;
      if (Math.random() < 0.5) {
        const eyes = sphere.querySelector(".sphere-eyes");
        if (eyes) {
          eyes.classList.add("eye-blink");
          setTimeout(() => eyes.classList.remove("eye-blink"), 600);
        }
      } else {
        sphere.classList.add("sphere-jump");
        setTimeout(() => sphere.classList.remove("sphere-jump"), 800);
      }
    }, 5000);
    return () => clearInterval(interval);
  }, [appState]);

  const openChat = useCallback(() => {
    setScreen("chat");
    setTimeout(() => inputRef.current?.focus(), 600);
  }, []);

  const handleSend = async (text?: string) => {
    const msg = text || input.trim();
    if (!msg) return;

    // Switch to chat if on landing
    if (screen === "landing") openChat();

    // Cancel previous stream
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
    setAppState("thinking");

    const updatePlaceholder = (updater: (msg: ChatMessage) => ChatMessage) => {
      const targetId = placeholderIdRef.current;
      setMessages((prev) =>
        prev.map((m) => (m.id === targetId ? updater(m) : m)),
      );
    };

    try {
      let firstEvent = true;
      await streamChat(
        msg,
        historySnapshot,
        {
          onEvent: (event) => {
            if (firstEvent) {
              setAppState("speaking");
              firstEvent = false;
            }
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
        setAppState("idle");
        return;
      }

      if (error instanceof StreamChatError && error.beforeFirstEvent) {
        try {
          const res = await sendChat(msg, historySnapshot);
          updatePlaceholder(() => ({
            id: placeholderIdRef.current!,
            role: "assistant",
            content: res.error ? res.message || "查询失败" : res.answer || "",
            table: res.error ? undefined : res.table,
            isStreaming: false,
            statusText: "",
            error: res.error ? res.message || "查询失败" : undefined,
          }));
        } catch {
          updatePlaceholder((m) => ({
            ...m,
            isStreaming: false,
            statusText: "",
            error: "网络错误，请稍后重试",
          }));
        }
        setAppState("idle");
        return;
      }

      updatePlaceholder((m) => markInterruptedMessage(m));
    } finally {
      if (abortRef.current === controller) {
        abortRef.current = null;
        placeholderIdRef.current = null;
        setLoading(false);
        setAppState("idle");
      }
    }
  };

  return (
    <div className={`app-container state-${appState}`}>
      {/* Fluid gradient background */}
      <div className="fluid-bg" style={{ height: screen === "chat" ? "35%" : "100%" }}>
        <div className="blob blob-1" />
        <div className="blob blob-2" />
        <div className="blob blob-3" />
      </div>

      {/* ====== Landing Screen ====== */}
      <div className={`landing-screen ${screen === "chat" ? "exit" : ""}`}>
        <div className="landing-header">
          <h1>Hello</h1>
          <h2>我是典宝，有什么可以帮你的？</h2>
          <p>我是你的业务数据助理，懂数据、会查询。内部经营指标、用户行为分析、营收报表查询，交给我就好。</p>
        </div>

        <div className="core-container">
          {FLOAT_TAGS.map((tag) => (
            <div key={tag.label} className="float-tag" style={tag.style}>
              {TAG_ICONS[tag.icon]}
              {tag.label}
            </div>
          ))}
          <SmartSphere id="main-sphere" />
        </div>

        <div className="landing-footer">
          <div className="guide-input" onClick={openChat}>
            <span style={{ position: "relative", zIndex: 1 }}>跟我聊聊您的分析需求...</span>
            <svg style={{ position: "relative", zIndex: 1 }} width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
              <path d="M12 1a3 3 0 0 0-3 3v8a3 3 0 0 0 6 0V4a3 3 0 0 0-3-3z" />
              <path d="M19 10v2a7 7 0 0 1-14 0v-2" />
            </svg>
          </div>
        </div>
      </div>

      {/* ====== Chat Screen ====== */}
      <div className={`chat-screen ${screen === "chat" ? "enter" : ""}`}>
        {/* Header */}
        <header className="chat-header">
          <div className="header-title" onClick={() => setScreen("landing")}>
            <span className="status-dot" />
            典宝 AI 助手
          </div>
          <div className="header-actions">
            <button className="header-btn" onClick={() => navigate("/report?type=weekly")}>
              <ChartIcon /> 周报
            </button>
            <button className="header-btn" onClick={() => navigate("/report?type=monthly")}>
              <ChartIcon /> 月报
            </button>
          </div>
        </header>

        {/* Mini sphere section */}
        <section className="vh-section-mini">
          <div className="mini-sphere-wrap">
            <div ref={sphereRef}>
              <SmartSphere />
            </div>
            <div className="state-text">{STATE_TEXT_MAP[appState]}</div>
          </div>
        </section>

        {/* Chat area */}
        <div className="chat-area">
          {/* Welcome guide cards when no messages */}
          {messages.length === 0 && (
            <div className="message ai-msg guide-message">
              您好！我是您的企业数据助理典宝。您可以直接对我说话，或者点击下方为您准备的快捷入口。
              <div className="guide-cards-container">
                {SUGGESTIONS.map((s) => (
                  <div key={s} className="guide-card" onClick={() => handleSend(s)}>
                    <span className="card-text">{s}</span>
                    <span className="card-arrow">❯</span>
                  </div>
                ))}
              </div>
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

        {/* Input bar */}
        <div className="input-bar">
          <div className="input-wrap">
            <input
              ref={inputRef}
              type="text"
              placeholder={asr.state === "recording" ? "正在听..." : "输入问题..."}
              value={input}
              onChange={(e) => setInput(e.target.value)}
              onKeyDown={(e) => { if (e.key === "Enter") handleSend(); }}
              disabled={loading || asr.state === "recording"}
            />
          </div>
          <button
            className={`mic-btn ${asr.state === "recording" ? "recording" : ""} ${asr.state === "connecting" ? "connecting" : ""}`}
            onClick={toggleVoice}
            disabled={loading || asr.state === "connecting"}
            title={asr.state === "recording" ? "停止录音" : "语音输入"}
          >
            {asr.state === "recording" ? (
              <svg width="20" height="20" viewBox="0 0 24 24" fill="currentColor"><rect x="6" y="6" width="12" height="12" rx="2" /></svg>
            ) : (
              <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                <path d="M12 1a3 3 0 0 0-3 3v8a3 3 0 0 0 6 0V4a3 3 0 0 0-3-3z" />
                <path d="M19 10v2a7 7 0 0 1-14 0v-2" />
                <line x1="12" y1="19" x2="12" y2="23" />
              </svg>
            )}
          </button>
          <button className="send-btn" onClick={() => handleSend()} disabled={loading || asr.state === "recording"}>
            <SendIcon />
          </button>
        </div>
      </div>
    </div>
  );
}
