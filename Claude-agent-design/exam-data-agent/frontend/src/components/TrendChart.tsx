import { Card } from "antd";
import ReactECharts from "echarts-for-react";

interface Props {
  title: string;
  xData: string[];
  series: { name: string; data: (number | string)[] }[];
}

const palette = ["#00b4d8", "#66ffd1", "#0284c7", "#38bdf8", "#0f766e"];

export default function TrendChart({ title, xData, series }: Props) {
  const option = {
    color: palette,
    tooltip: {
      trigger: "axis" as const,
      appendToBody: true,
      confine: false,
      backgroundColor: "rgba(15, 23, 42, 0.88)",
      borderWidth: 0,
      textStyle: { color: "#fff" },
    },
    legend: {
      bottom: 0,
      icon: "circle",
      textStyle: { color: "#6e7e85", fontSize: 12 },
    },
    grid: { left: "3%", right: "4%", top: 48, bottom: "18%", containLabel: true },
    xAxis: {
      type: "category" as const,
      data: xData,
      boundaryGap: false,
      axisLine: { lineStyle: { color: "#dbe7ea" } },
      axisTick: { show: false },
      axisLabel: { rotate: 30, fontSize: 10, color: "#94a3b8" },
    },
    yAxis: {
      type: "value" as const,
      splitLine: { lineStyle: { color: "#edf4f6" } },
      axisLabel: { color: "#94a3b8" },
    },
    series: series.map((s, idx) => ({
      name: s.name,
      type: "line" as const,
      data: s.data.map((v) => {
        const n = parseFloat(String(v).replace("%", ""));
        return Number.isNaN(n) ? 0 : n;
      }),
      smooth: true,
      symbol: "circle",
      symbolSize: 8,
      lineStyle: { width: 3 },
      areaStyle: idx === 0 ? { color: "rgba(0, 180, 216, 0.10)" } : undefined,
    })),
  };

  return (
    <Card
      className="report-trend-chart"
      size="small"
      title={<span className="report-trend-chart__title">{title}</span>}
      styles={{
        header: { borderBottom: "none", minHeight: 52 },
        body: { paddingTop: 0 },
      }}
    >
      <ReactECharts className="report-trend-chart__canvas" option={option} style={{ height: 300, width: "100%" }} />
    </Card>
  );
}
