import { useMemo } from "react";
import ReactECharts from "echarts-for-react";

interface ChatChartProps {
  type: "line" | "bar";
  labels: string[];
  series: { name: string; data: number[] }[];
}

const palette = ["#00b4d8", "#66ffd1", "#0284c7", "#38bdf8", "#0f766e"];

export default function ChatChart({ type, labels, series }: ChatChartProps) {
  const option = useMemo(
    () => ({
      color: palette,
      tooltip: {
        trigger: "axis" as const,
        appendToBody: true,
        confine: false,
        backgroundColor: "rgba(15, 23, 42, 0.88)",
        borderWidth: 0,
        textStyle: { color: "#fff" },
        axisPointer: {
          type: "line" as const,
          lineStyle: { color: "rgba(148, 163, 184, 0.35)", width: 1 },
        },
      },
      legend: {
        show: series.length > 1,
        bottom: 0,
        icon: "circle",
        textStyle: { color: "#6e7e85", fontSize: 12 },
      },
      grid: {
        left: "3%",
        right: "4%",
        top: 24,
        bottom: series.length > 1 ? 36 : 18,
        containLabel: true,
      },
      xAxis: {
        type: "category" as const,
        data: labels,
        boundaryGap: type === "bar",
        axisLine: { lineStyle: { color: "#dbe7ea" } },
        axisTick: { show: false },
        axisLabel: {
          rotate: labels.length > 6 ? 30 : 0,
          fontSize: 10,
          color: "#94a3b8",
        },
      },
      yAxis: {
        type: "value" as const,
        splitLine: { lineStyle: { color: "#edf4f6" } },
        axisLabel: { color: "#94a3b8" },
      },
      series: series.map((item, index) => {
        if (type === "bar") {
          return {
            name: item.name,
            type: "bar" as const,
            data: item.data,
            barMaxWidth: 28,
            itemStyle: {
              borderRadius: [6, 6, 0, 0] as [number, number, number, number],
            },
          };
        }

        return {
          name: item.name,
          type: "line" as const,
          data: item.data,
          smooth: true,
          symbol: "circle",
          symbolSize: 8,
          showSymbol: true,
          lineStyle: { width: 3 },
          areaStyle: index === 0 ? { color: "rgba(0, 180, 216, 0.10)" } : undefined,
        };
      }),
    }),
    [labels, series, type],
  );

  if (labels.length === 0 || series.length === 0) {
    return null;
  }

  return (
    <div style={{ width: "100%", minWidth: 0 }}>
      <ReactECharts option={option} style={{ height: 240, width: "100%" }} />
    </div>
  );
}
