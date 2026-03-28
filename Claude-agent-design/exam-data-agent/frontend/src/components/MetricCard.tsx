import { Card } from "antd";
import { ArrowUpOutlined, ArrowDownOutlined } from "@ant-design/icons";

interface MetricData {
  label: string;
  value: string;
  wow: string;
  yoy: string;
}

function ChangeTag({ label, value }: { label: string; value: string }) {
  if (!value || value === "N/A") {
    return <span className="metric-card__change metric-card__change--neutral">{label}：N/A</span>;
  }

  const num = parseFloat(value.replace("%", "").replace("+", ""));
  const stateClass = num > 0 ? "metric-card__change--up" : num < 0 ? "metric-card__change--down" : "metric-card__change--neutral";
  const icon = num > 0 ? <ArrowUpOutlined /> : num < 0 ? <ArrowDownOutlined /> : null;

  return (
    <span className={`metric-card__change ${stateClass}`}>
      {icon && <span className="metric-card__change-icon">{icon}</span>}
      <span className="metric-card__change-label">{label}</span>
      <span className="metric-card__change-value">{value}</span>
    </span>
  );
}

export default function MetricCard({ data }: { data: MetricData }) {
  return (
    <Card className="metric-card" size="small" styles={{ body: { padding: 20, height: "100%" } }}>
      <div className="metric-card__label">{data.label}</div>
      <div className="metric-card__value">{data.value}</div>
      <div className="metric-card__changes">
        <ChangeTag label="环比" value={data.wow} />
        <ChangeTag label="同比" value={data.yoy} />
      </div>
    </Card>
  );
}
