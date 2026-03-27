import { Table, Typography } from "antd";
import { useMemo, type ReactNode } from "react";
import SimpleChart from "./SimpleChart";

const { Text } = Typography;

interface Props {
  role: "user" | "assistant";
  content: string;
  table?: { columns: string[]; rows: string[][] };
  statusText?: string;
  error?: string;
}

/** Detect if a string is purely numeric (int / float / percentage) */
function isNumeric(v: string): boolean {
  return /^-?[\d,]+(\.\d+)?%?$/.test(v.trim());
}

/** Format cell value: highlight numbers, detect trend arrows */
function formatCellValue(val: string): ReactNode {
  if (!val) return val;
  const trimmed = val.trim();

  // trend indicators
  if (/^[↑▲]\s*/.test(trimmed))
    return <span className="trend-up">{trimmed.replace(/^[↑▲]\s*/, "")}</span>;
  if (/^[↓▼]\s*/.test(trimmed))
    return <span className="trend-down">{trimmed.replace(/^[↓▼]\s*/, "")}</span>;

  // numeric highlight
  if (isNumeric(trimmed))
    return <span className="num-highlight">{trimmed}</span>;

  return val;
}

/** Render insight text with inline number highlighting */
function renderInsightText(text: string): ReactNode {
  // Split text at number patterns (e.g., 988人, 14.5%, ¥1,200)
  const parts = text.split(/([\d,]+(?:\.\d+)?[%¥元人次个件天月周年万亿]?)/g);
  return parts.map((part, i) =>
    /^[\d,]+(?:\.\d+)?[%¥元人次个件天月周年万亿]?$/.test(part) && part.length > 0 ? (
      <span key={i} className="num-highlight">{part}</span>
    ) : (
      <span key={i}>{part}</span>
    ),
  );
}

/** Try to extract chart-friendly data from a table (label col + numeric col) */
function extractChartData(table: { columns: string[]; rows: string[][] }) {
  if (table.columns.length < 2 || table.rows.length < 2) return null;
  // Find first numeric column (skip label column)
  let labelIdx = 0;
  let valueIdx = -1;
  for (let j = 1; j < table.columns.length; j++) {
    const allNumeric = table.rows.every((row) => isNumeric(row[j] || "0"));
    if (allNumeric) { valueIdx = j; break; }
  }
  if (valueIdx === -1) return null;
  const labels = table.rows.map((r) => r[labelIdx] || "");
  const data = table.rows.map((r) => parseFloat((r[valueIdx] || "0").replace(/,/g, "")));
  // Determine chart type: time series → line, categories → bar
  const isTimeSeries = labels.some((l) => /\d{4}[-/]\d{2}/.test(l));
  return { labels, data, type: (isTimeSeries ? "line" : "bar") as "line" | "bar" };
}

export default function ChatBubble({ role, content, table, statusText, error }: Props) {
  const isUser = role === "user";

  const chartData = useMemo(() => {
    if (!table || table.rows.length === 0) return null;
    return extractChartData(table);
  }, [table]);

  return (
    <div className={`message ${isUser ? "user-msg" : "ai-msg"}`}>
      {/* 1. Status indicator */}
      {statusText && (
        <div className="msg-status">
          <div className="msg-status-spinner" />
          <span>{statusText}</span>
        </div>
      )}

      {/* 2. Table in data-visual-card */}
      {table &&
        (table.rows.length > 0 ? (
          <div className="data-visual-card">
            <Table
              size="small"
              pagination={false}
              scroll={{ x: "max-content" }}
              dataSource={table.rows.map((row, i) => {
                const obj: Record<string, string> = { key: String(i) };
                table.columns.forEach((col, j) => {
                  obj[col] = row[j];
                });
                return obj;
              })}
              columns={table.columns.map((col) => ({
                title: col,
                dataIndex: col,
                key: col,
                render: (val: string) => formatCellValue(val),
              }))}
            />
          </div>
        ) : (
          <Text type="secondary" style={{ display: "block", marginBottom: content ? 12 : 0 }}>
            查询完成，暂无匹配数据
          </Text>
        ))}

      {/* 2.5 Auto chart from table data */}
      {chartData && (
        <SimpleChart type={chartData.type} labels={chartData.labels} data={chartData.data} />
      )}

      {/* 3. Insight text with number highlighting */}
      {content && (
        <div className="insight-text">{renderInsightText(content)}</div>
      )}

      {/* 4. Error / interruption */}
      {error && (
        <div className="msg-error">{error}</div>
      )}
    </div>
  );
}
