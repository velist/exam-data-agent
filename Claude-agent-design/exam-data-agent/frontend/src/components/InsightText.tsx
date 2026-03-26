import { useEffect, useState } from "react";
import { Card, Spin, Typography } from "antd";
import { BulbOutlined } from "@ant-design/icons";
import { streamInsight } from "../api";

const { Paragraph } = Typography;

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
      <Paragraph style={{ whiteSpace: "pre-wrap" }}>
        {text}
        {loading && text && <span style={{ animation: "blink 1s step-end infinite" }}>|</span>}
      </Paragraph>
    </Card>
  );
}
