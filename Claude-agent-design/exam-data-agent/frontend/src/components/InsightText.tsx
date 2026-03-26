import { useEffect, useState } from "react";
import { Card, Spin } from "antd";
import { BulbOutlined } from "@ant-design/icons";
import ReactMarkdown from "react-markdown";
import { streamInsight } from "../api";

interface Props {
  type: "weekly" | "monthly";
  date: string;
}

export default function InsightText({ type, date }: Props) {
  const [text, setText] = useState("");
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    setText("");
    setLoading(true);
    const cancel = streamInsight(type, date,
      (chunk) => setText((prev) => prev + chunk),
      () => setLoading(false),
    );
    return cancel;
  }, [type, date]);

  return (
    <Card title={<><BulbOutlined /> AI 分析洞察</>} style={{ marginTop: 24 }}>
      {loading && !text && <Spin tip="正在分析数据..." />}
      <div className="insight-markdown">
        <ReactMarkdown>{text}</ReactMarkdown>
        {loading && text && <span style={{ animation: "blink 1s step-end infinite" }}>|</span>}
      </div>
      <style>{`
        .insight-markdown h3 { font-size: 16px; font-weight: 600; margin: 16px 0 8px; }
        .insight-markdown ul { padding-left: 20px; }
        .insight-markdown li { margin-bottom: 6px; line-height: 1.8; }
        .insight-markdown strong { color: #1677ff; }
      `}</style>
    </Card>
  );
}
