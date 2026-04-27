import { Table, Typography } from "antd";
import { useMemo, type ReactNode } from "react";
import * as XLSX from "xlsx";
import ChatChart from "./ChatChart";

const { Text } = Typography;

/** SQL column name → Chinese display name */
const COLUMN_LABEL: Record<string, string> = {
  // 日期时间
  start_dt: "开始日期",
  end_dt: "结束日期",
  stat_date: "统计日期",
  order_date: "订单日期",
  pay_date: "付款日期",
  create_time: "创建时间",
  update_time: "更新时间",
  // 产品
  product_name: "产品名称",
  product_type: "产品类型",
  series_name: "系列名称",
  class_type: "班次类型",
  class_name: "班次名称",
  // 销售
  sale_amount: "销售金额",
  sale_count: "销量",
  total_amount: "总金额",
  refund_amount: "退款金额",
  channel_name: "渠道名称",
  channel_type: "渠道类型",
  // 用户基础
  user_count: "用户数",
  reg_count: "注册数",
  reg_users: "注册用户",
  active_users: "活跃用户",
  valid_active_users: "有效活跃用户",
  daily_register_count: "日注册数",
  daily_active_count: "日活跃数",
  // 付费
  pay_count: "付费数",
  pay_users: "付费用户",
  pay_conv_rate: "付费转化率",
  repurchase_rate: "复购率",
  arpu: "ARPU",
  // 留存
  n1_ret_rate: "次日留存率",
  w_ret_rate: "周留存率",
  // 行为
  quiz_part_rate: "答题参与率",
  mock_part_rate: "模考参与率",
  course_part_rate: "课程参与率",
  avg_play_progress: "人均播放进度",
  quiz_rate: "人均刷题量",
  daily_avg_exam: "人均刷题数",
  // 地理
  province: "省份",
  city: "城市",
  // 客服
  theme: "问题主题",
  ticket_count: "工单数",
  avg_response_time: "平均响应时间",
};

export function getColumnLabel(col: string): string {
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

/** Detect if a string looks like a date (YYYY-MM, YYYY/MM, YYYY-MM-DD, etc.) */
function isDateLike(v: string): boolean {
  return /^\d{4}[-/]\d{1,2}([-/]\d{1,2})?$/.test(v.trim());
}

function parseNumericValue(v: string): number {
  return Number.parseFloat(v.trim().replace(/[,%]/g, ""));
}

/** Format an integer with thousand separators, no decimal places */
function formatInteger(n: number): string {
  return n.toLocaleString("en-US", { minimumFractionDigits: 0, maximumFractionDigits: 0 });
}

/** Format a float with thousand separators and 2 decimal places */
function formatFloat(n: number): string {
  return n.toLocaleString("en-US", { minimumFractionDigits: 2, maximumFractionDigits: 2 });
}

/** Decide whether to format as float (2 decimals) or integer (no decimals) */
function shouldFormatAsFloat(raw: string, num: number): boolean {
  // If the raw string has a decimal point, check if the value is actually a whole number
  if (raw.includes(".")) {
    // Values like "1805.0" or "5563.00" from DB should be treated as integers
    return num !== Math.floor(num);
  }
  return false;
}

/** Format a raw cell value: apply number formatting */
function formatCellDisplay(val: string): string {
  if (!val) return val;
  const trimmed = val.trim();

  // Skip date-like values
  if (isDateLike(trimmed)) return val;

  // Percentage: format number part, keep % and leading sign
  const pctMatch = trimmed.match(/^([+-]?)([\d,]+(?:\.\d+)?)%$/);
  if (pctMatch) {
    const sign = pctMatch[1];
    const numStr = pctMatch[2];
    const num = Number.parseFloat(numStr.replace(/,/g, ""));
    if (!Number.isNaN(num)) {
      const fmt = shouldFormatAsFloat(numStr, num) ? formatFloat(num) : formatInteger(num);
      return `${sign}${fmt}%`;
    }
  }

  // Plain number
  if (isNumeric(trimmed)) {
    const num = Number.parseFloat(trimmed.replace(/,/g, ""));
    if (!Number.isNaN(num)) {
      return shouldFormatAsFloat(trimmed, num) ? formatFloat(num) : formatInteger(num);
    }
  }

  return val;
}

/** Detect cell value type for CSS styling */
function getCellDisplayClass(val: string): string {
  if (!val) return "";
  const trimmed = val.trim();
  if (/^[↑▲]\s*/.test(trimmed)) return "trend-up";
  if (/^[↓▼]\s*/.test(trimmed)) return "trend-down";
  if (isNumeric(trimmed)) return "num-highlight";
  return "";
}

/** Format cell value: highlight numbers, detect trend arrows */
function formatCellValue(val: string): ReactNode {
  if (!val) return val;
  const display = formatCellDisplay(val);
  const cls = getCellDisplayClass(val);
  if (cls) return <span className={cls}>{display}</span>;
  return display || val;
}

/** Render insight text with inline number highlighting and formatting */
function renderInsightText(text: string): ReactNode {
  // Protect dates like "2024-01", "2024/03-15", "2026年3月", "2026年" by pre-replacing with non-numeric tokens
  const dateTokens: string[] = [];
  const tagChars = "abcdefghijklmnopqrst";
  let protectedText = text.replace(/(\d{4}[-/]\d{1,2}([-/]\d{1,2})?)/g, (_full, dateStr) => {
    const tag = `@DT${tagChars[dateTokens.length]}@`;
    dateTokens.push(dateStr);
    return tag;
  });
  // Also protect Chinese date patterns: "2026年3月", "2026年"
  protectedText = protectedText.replace(/(\d{4}年(?:\d{1,2}月)?)/g, (_full, dateStr) => {
    const tag = `@DT${tagChars[dateTokens.length]}@`;
    dateTokens.push(dateStr);
    return tag;
  });

  // Split at number patterns
  const parts = protectedText.split(/([\d,]+(?:\.\d+)?[%¥元人次个件天月周年万亿]?)/g);

  const elements: ReactNode[] = [];
  let tokenCounter = 0;

  // Build a map for fast token→index lookup
  const tokenMap = new Map<string, string>();
  dateTokens.forEach((d, i) => tokenMap.set(`@DT${tagChars[i]}@`, d));

  parts.forEach((part) => {
    // If this part contains a date token, restore all dates in it
    if (/@DT[a-t]@/.test(part)) {
      const restored = part.replace(/@DT([a-t])@/g, (_m, ch) => {
        const idx = tagChars.indexOf(ch);
        return dateTokens[idx] ?? "";
      });
      elements.push(<span key={`r-${tokenCounter++}`}>{restored}</span>);
      return;
    }

    if (!/^\d/.test(part)) {
      elements.push(<span key={`t-${tokenCounter++}`}>{part}</span>);
      return;
    }

    const match = part.match(/^([\d,]+(?:\.\d+)?)([%¥元人次个件天月周年万亿]?)$/);
    if (!match) {
      elements.push(<span key={`x-${tokenCounter++}`}>{part}</span>);
      return;
    }

    const numStr = match[1];
    const unit = match[2];
    const num = Number.parseFloat(numStr.replace(/,/g, ""));
    if (Number.isNaN(num)) {
      elements.push(<span key={`n-${tokenCounter++}`}>{part}</span>);
      return;
    }

    const formatted = shouldFormatAsFloat(numStr, num) ? formatFloat(num) : formatInteger(num);
    elements.push(
      <span key={`h-${tokenCounter++}`} className="num-highlight">
        {formatted}
        {unit}
      </span>,
    );
  });

  return elements;
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

    const exportColumns = table.columns.map((col) => getColumnLabel(col));
    const worksheet = XLSX.utils.aoa_to_sheet([exportColumns, ...table.rows]);
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
