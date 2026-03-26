import { useState, useRef, useEffect } from "react";
import { Layout, Input, Button, Space, Tag, Typography } from "antd";
import { SendOutlined, BarChartOutlined } from "@ant-design/icons";
import { useNavigate } from "react-router-dom";
import ChatBubble from "../components/ChatBubble";
import { sendChat, ChatResponse } from "../api";
const { Header, Content, Footer } = Layout;
const { Title } = Typography;
interface Message { role: "user" | "assistant"; content: string; table?: { columns: string[]; rows: string[][] }; }
const SUGGESTIONS = ["本周注册用户情况", "付费转化率趋势", "上月销售总额", "活跃用户同比去年"];
export default function Chat() {
  const [messages, setMessages] = useState<Message[]>([]);
  const [input, setInput] = useState("");
  const [loading, setLoading] = useState(false);
  const bottomRef = useRef<HTMLDivElement>(null);
  const navigate = useNavigate();
  useEffect(() => { bottomRef.current?.scrollIntoView({ behavior: "smooth" }); }, [messages]);
  const handleSend = async (text?: string) => {
    const msg = text || input.trim();
    if (!msg) return;
    setInput("");
    setMessages((prev) => [...prev, { role: "user", content: msg }]);
    setLoading(true);
    const history = messages.slice(-10).map((m) => ({ role: m.role, content: m.content }));
    try {
      const res: ChatResponse = await sendChat(msg, history);
      setMessages((prev) => [...prev, { role: "assistant", content: res.error ? (res.message || "查询失败") : (res.answer || ""), table: res.error ? undefined : res.table }]);
    } catch { setMessages((prev) => [...prev, { role: "assistant", content: "网络错误，请稍后重试" }]); }
    finally { setLoading(false); }
  };
  return (
    <Layout style={{ height: "100vh" }}>
      <Header style={{ background: "#fff", display: "flex", alignItems: "center", justifyContent: "space-between", padding: "0 24px", borderBottom: "1px solid #f0f0f0" }}>
        <Title level={4} style={{ margin: 0 }}>考试宝典数据助手</Title>
        <Space><Button icon={<BarChartOutlined />} onClick={() => navigate("/report?type=weekly")}>周报</Button><Button icon={<BarChartOutlined />} onClick={() => navigate("/report?type=monthly")}>月报</Button></Space>
      </Header>
      <Content style={{ flex: 1, overflow: "auto", padding: "24px 0" }}>
        {messages.length === 0 && (<div style={{ textAlign: "center", padding: "60px 24px" }}><Title level={3} type="secondary">你好，请问想查询什么数据？</Title><Space wrap style={{ marginTop: 24 }}>{SUGGESTIONS.map((s) => (<Tag key={s} style={{ cursor: "pointer", padding: "4px 12px", fontSize: 14 }} onClick={() => handleSend(s)}>{s}</Tag>))}</Space></div>)}
        {messages.map((msg, i) => (<ChatBubble key={i} role={msg.role} content={msg.content} table={msg.table} />))}
        <div ref={bottomRef} />
      </Content>
      <Footer style={{ padding: "12px 24px", background: "#fff", borderTop: "1px solid #f0f0f0" }}>
        <Space.Compact style={{ width: "100%" }}>
          <Input size="large" placeholder="输入数据查询问题..." value={input} onChange={(e) => setInput(e.target.value)} onPressEnter={() => handleSend()} disabled={loading} />
          <Button size="large" type="primary" icon={<SendOutlined />} onClick={() => handleSend()} loading={loading} />
        </Space.Compact>
      </Footer>
    </Layout>
  );
}
