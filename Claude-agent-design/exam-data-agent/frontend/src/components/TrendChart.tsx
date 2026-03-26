import ReactECharts from "echarts-for-react";

interface Props {
  title: string;
  xData: string[];
  series: { name: string; data: (number | string)[] }[];
}

export default function TrendChart({ title, xData, series }: Props) {
  const option = {
    title: { text: title, textStyle: { fontSize: 14 } },
    tooltip: { trigger: "axis" as const },
    legend: { bottom: 0 },
    grid: { left: "3%", right: "4%", bottom: "15%", containLabel: true },
    xAxis: { type: "category" as const, data: xData, axisLabel: { rotate: 30, fontSize: 10 } },
    yAxis: { type: "value" as const },
    series: series.map((s) => ({
      name: s.name,
      type: "line" as const,
      data: s.data.map((v) => { const n = parseFloat(String(v).replace("%", "")); return isNaN(n) ? 0 : n; }),
      smooth: true,
    })),
  };
  return <ReactECharts option={option} style={{ height: 300, width: "100%" }} />;
}
