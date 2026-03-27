import { Table, Typography, Spin } from "antd";
import { LoadingOutlined } from "@ant-design/icons";

const { Text } = Typography;

interface Props {
  role: "user" | "assistant";
  content: string;
  table?: { columns: string[]; rows: string[][] };
  statusText?: string;
  error?: string;
}

export default function ChatBubble({ role, content, table, statusText, error }: Props) {
  const isUser = role === "user";
  return (
    <div
      style={{
        display: "flex",
        justifyContent: isUser ? "flex-end" : "flex-start",
        marginBottom: 16,
        padding: "0 16px",
      }}
    >
      <div
        style={{
          maxWidth: "80%",
          padding: "12px 16px",
          borderRadius: 12,
          backgroundColor: isUser ? "#1677ff" : "#f5f5f5",
          color: isUser ? "#fff" : "#333",
        }}
      >
        {/* 1. 状态区 */}
        {statusText && (
          <div style={{ marginBottom: 8 }}>
            <Spin indicator={<LoadingOutlined style={{ fontSize: 14 }} />} size="small" />
            <Text type="secondary" style={{ marginLeft: 8 }}>
              {statusText}
            </Text>
          </div>
        )}

        {/* 2. 表格区 */}
        {table &&
          (table.rows.length > 0 ? (
            <Table
              style={{ marginBottom: content ? 12 : 0 }}
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
              }))}
            />
          ) : (
            <Text type="secondary" style={{ display: "block", marginBottom: content ? 12 : 0 }}>
              查询完成，暂无匹配数据
            </Text>
          ))}

        {/* 3. 文本区 */}
        {content && (
          <Text style={{ color: isUser ? "#fff" : "#333", whiteSpace: "pre-wrap" }}>
            {content}
          </Text>
        )}

        {/* 4. 错误/中断提示区 */}
        {error && (
          <div style={{ marginTop: content || table ? 8 : 0 }}>
            <Text type="danger">{error}</Text>
          </div>
        )}
      </div>
    </div>
  );
}
