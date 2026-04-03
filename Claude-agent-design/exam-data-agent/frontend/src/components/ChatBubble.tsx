import { Table, Typography } from "antd";
import { useMemo, type ReactNode } from "react";
import * as XLSX from "xlsx";
import ChatChart from "./ChatChart";

const { Text } = Typography;

/** SQL column name → Chinese display name */
const COLUMN_LABEL: Record<string, string> = {
  start_dt: "开始日期",
  end_dt: "结束日期",
  order_date: "订单日期",
  pay_date: "付款日期",
  create_time: "创建时间",
  update_time: "更新时间",
  product_name: "产品名称",
  product_type: "产品类型",
  class_type: "班次类型",
  class_name: "班次名称",
  sale_amount: "销售金额",
  sale_count: "销量",
  total_amount: "总金额",
  refund_amount: "退款金额",
  user_count: "用户数",
  reg_count: "注册数",
  pay_count: "付费数",
  channel_name: "渠道名称",
  province: "省份",
  city: "城市",
};

function getColumnLabel(col: string): string {
  return COLUMN_LABEL[col] ?? col;
}

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

function parseNumericValue(v: string): number {
  return Number.parseFloat(v.trim().replace(/[,%]/g, ""));
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

/** Try to extract chart-friendly data from a table (label col + numeric cols) */
function extractChartData(table: { columns: string[]; rows: string[][] }) {
  if (table.columns.length < 2 || table.rows.length < 2) return null;

  const labelIdx = 0;
  const labels = table.rows.map((row) => row[labelIdx] || "");
  const series = table.columns
    .map((column, index) => {
      if (index === labelIdx) return null;

      const values = table.rows.map((row) => row[index] ?? "");
      const allNumeric = values.every((value) => isNumeric(value));
      if (!allNumeric) return null;

      return {
        name: column,
        data: values.map((value) => parseNumericValue(value)),
      };
    })
    .filter((item): item is { name: string; data: number[] } => item !== null);

  if (series.length === 0) return null;

  // Determine chart type: time series → line, categories → bar
  const isTimeSeries = labels.some((label) => /\d{4}[-/]\d{2}/.test(label));
  return {
    labels,
    series,
    type: (isTimeSeries ? "line" : "bar") as "line" | "bar",
  };
}

function formatExportFileName(date: Date): string {
  const pad = (value: number) => String(value).padStart(2, "0");
  return `典宝数据_${date.getFullYear()}-${pad(date.getMonth() + 1)}-${pad(date.getDate())}_${pad(date.getHours())}-${pad(date.getMinutes())}.xlsx`;
}

export default function ChatBubble({ role, content, table, statusText, error }: Props) {
  const isUser = role === "user";

  const chartData = useMemo(() => {
    if (!table || table.rows.length === 0) return null;
    return extractChartData(table);
  }, [table]);

  const canDownloadTable = Boolean(table && table.columns.length > 0 && table.rows.length > 0);

  const handleDownloadXlsx = () => {
    if (!table || table.columns.length === 0 || table.rows.length === 0) return;

    const worksheet = XLSX.utils.aoa_to_sheet([table.columns, ...table.rows]);
    const workbook = XLSX.utils.book_new();
    XLSX.utils.book_append_sheet(workbook, worksheet, "数据");
    XLSX.writeFile(workbook, formatExportFileName(new Date()));
  };

  return (
    <div className={`message ${isUser ? "user-msg" : "ai-msg"}`}>
      {/* 0. Role label */}
      <div className={`msg-role-label ${isUser ? "role-user" : "role-ai"}`}>
        {isUser ? "你" : "典宝"}
      </div>

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
                title: getColumnLabel(col),
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

      {/* 2.5 Download current table as XLSX */}
      {canDownloadTable && (
        <div
          style={{
            margin: chartData ? "12px 0" : "12px 0 0",
            display: "flex",
            justifyContent: "flex-end",
          }}
        >
          <button
            type="button"
            onClick={handleDownloadXlsx}
            style={{
              border: "1px solid #d9eaf0",
              borderRadius: 8,
              background: "#f7fdff",
              color: "#1677ff",
              padding: "6px 12px",
              fontSize: 13,
              cursor: "pointer",
            }}
          >
            下载 XLSX
          </button>
        </div>
      )}

      {/* 2.6 Auto chart from table data */}
      {chartData && (
        <ChatChart type={chartData.type} labels={chartData.labels} series={chartData.series} />
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
