import { Table, Typography } from "antd";

const { Text } = Typography;

interface Props {
  role: "user" | "assistant";
  content: string;
  table?: { columns: string[]; rows: string[][] };
}

export default function ChatBubble({ role, content, table }: Props) {
  const isUser = role === "user";
  return (
    <div style={{ display: "flex", justifyContent: isUser ? "flex-end" : "flex-start", marginBottom: 16, padding: "0 16px" }}>
      <div style={{ maxWidth: "80%", padding: "12px 16px", borderRadius: 12, backgroundColor: isUser ? "#1677ff" : "#f5f5f5", color: isUser ? "#fff" : "#333" }}>
        <Text style={{ color: isUser ? "#fff" : "#333", whiteSpace: "pre-wrap" }}>{content}</Text>
        {table && table.rows.length > 0 && (
          <Table
            style={{ marginTop: 12 }}
            size="small"
            pagination={false}
            scroll={{ x: "max-content" }}
            dataSource={table.rows.map((row, i) => {
              const obj: Record<string, string> = { key: String(i) };
              table.columns.forEach((col, j) => { obj[col] = row[j]; });
              return obj;
            })}
            columns={table.columns.map((col) => ({ title: col, dataIndex: col, key: col }))}
          />
        )}
      </div>
    </div>
  );
}
