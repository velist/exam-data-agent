import { useState, useRef, useEffect } from "react";
import { Layout, Input, Button, Space, Tag, Typography } from "antd";
import { SendOutlined, BarChartOutlined } from "@ant-design/icons";
import { useNavigate } from "react-router-dom";
import ChatBubble from "../components/ChatBubble";
import { sendChat, streamChat, StreamChatError } from "../api";
import {
  type ChatMessage,
  buildHistorySnapshot,
  createStreamingAssistantMessage,
  applyStreamEvent,
  markInterruptedMessage,
  generateMessageId,
} from "./chatMessageUtils";

const { Header, Content, Footer } = Layout;
const { Title } = Typography;

const SUGGESTIONS = [
  "本周注册用户情况",
  "付费转化率趋势",
  "上月销售总额",
  "活跃用户同比去年",
];

export default function Chat() {
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [input, setInput] = useState("");
  const [loading, setLoading] = useState(false);
  const bottomRef = useRef<HTMLDivElement>(null);
  const abortRef = useRef<AbortController | null>(null);
  const placeholderIdRef = useRef<string | null>(null);
  const navigate = useNavigate();

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages]);

  const handleSend = async (text?: string) => {
    const msg = text || input.trim();
    if (!msg) return;

    // 1. 取消旧流
    abortRef.current?.abort();
    const controller = new AbortController();
    abortRef.current = controller;

    // 2. 追加 user 消息，生成 history 快照（基于已完成消息）
    const userMessage: ChatMessage = {
      id: generateMessageId(),
      role: "user",
      content: msg,
    };
    const historySnapshot = buildHistorySnapshot(messages);

    // 3. 创建占位消息，用稳定 ID 定位
    const placeholder = createStreamingAssistantMessage();
    placeholderIdRef.current = placeholder.id;

    setMessages((prev) => [...prev, userMessage, placeholder]);
    setInput("");
    setLoading(true);

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
        // 取消：有内容则保留并标记中断，无内容则移除占位
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
        return;
      }

      if (error instanceof StreamChatError && error.beforeFirstEvent) {
        // 首帧前失败：降级到同步接口
        try {
          const res = await sendChat(msg, historySnapshot);
          updatePlaceholder(() => ({
            id: placeholderIdRef.current!,
            role: "assistant",
            content: res.error
              ? res.message || "查询失败"
              : res.answer || "",
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
        return;
      }

      // 首帧后失败：保留已有内容，标记中断
      updatePlaceholder((m) => markInterruptedMessage(m));
    } finally {
      if (abortRef.current === controller) {
        abortRef.current = null;
        placeholderIdRef.current = null;
        setLoading(false);
      }
    }
  };

  return (
    <Layout style={{ height: "100vh" }}>
      <Header
        style={{
          background: "#fff",
          display: "flex",
          alignItems: "center",
          justifyContent: "space-between",
          padding: "0 24px",
          borderBottom: "1px solid #f0f0f0",
        }}
      >
        <Title level={4} style={{ margin: 0 }}>
          考试宝典数据助手
        </Title>
        <Space>
          <Button
            icon={<BarChartOutlined />}
            onClick={() => navigate("/report?type=weekly")}
          >
            周报
          </Button>
          <Button
            icon={<BarChartOutlined />}
            onClick={() => navigate("/report?type=monthly")}
          >
            月报
          </Button>
        </Space>
      </Header>
      <Content style={{ flex: 1, overflow: "auto", padding: "24px 0" }}>
        {messages.length === 0 && (
          <div style={{ textAlign: "center", padding: "60px 24px" }}>
            <Title level={3} type="secondary">
              你好，请问想查询什么数据？
            </Title>
            <Space wrap style={{ marginTop: 24 }}>
              {SUGGESTIONS.map((s) => (
                <Tag
                  key={s}
                  style={{ cursor: "pointer", padding: "4px 12px", fontSize: 14 }}
                  onClick={() => handleSend(s)}
                >
                  {s}
                </Tag>
              ))}
            </Space>
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
      </Content>
      <Footer
        style={{
          padding: "12px 24px",
          background: "#fff",
          borderTop: "1px solid #f0f0f0",
        }}
      >
        <Space.Compact style={{ width: "100%" }}>
          <Input
            size="large"
            placeholder="输入数据查询问题..."
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onPressEnter={() => handleSend()}
            disabled={loading}
          />
          <Button
            size="large"
            type="primary"
            icon={<SendOutlined />}
            onClick={() => handleSend()}
            loading={loading}
          />
        </Space.Compact>
      </Footer>
    </Layout>
  );
}
