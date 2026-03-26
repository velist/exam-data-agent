import { Card, Statistic, Space, Typography } from "antd";
import { ArrowUpOutlined, ArrowDownOutlined } from "@ant-design/icons";

const { Text } = Typography;

interface MetricData {
  label: string;
  value: string;
  wow: string;
  yoy: string;
}

function ChangeTag({ label, value }: { label: string; value: string }) {
  if (!value || value === "N/A") return <Text type="secondary" style={{ fontSize: 12 }}>{label}: N/A</Text>;
  const num = parseFloat(value.replace("%", "").replace("+", ""));
  const isUp = num > 0;
  const color = isUp ? "#52c41a" : "#ff4d4f";
  const icon = isUp ? <ArrowUpOutlined /> : <ArrowDownOutlined />;
  return <Text style={{ color, fontSize: 12 }}>{icon} {label} {value}</Text>;
}

export default function MetricCard({ data }: { data: MetricData }) {
  return (
    <Card size="small" style={{ minWidth: 200 }}>
      <Statistic title={data.label} value={data.value} />
      <Space direction="vertical" size={2} style={{ marginTop: 8 }}>
        <ChangeTag label="环比" value={data.wow} />
        <ChangeTag label="同比" value={data.yoy} />
      </Space>
    </Card>
  );
}
