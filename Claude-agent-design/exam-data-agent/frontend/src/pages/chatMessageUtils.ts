import type { ChatStreamEvent, HistoryMessage } from "../api";

export type ChatMessage = {
  id: string;
  role: "user" | "assistant";
  content: string;
  table?: { columns: string[]; rows: string[][] };
  statusText?: string;
  isStreaming?: boolean;
  error?: string;
  isInterrupted?: boolean;
};

let _nextId = 1;
export function generateMessageId(): string {
  return `msg-${Date.now()}-${_nextId++}`;
}

/**
 * 只保留已完成轮次的 {role, content} 对。
 * 规则：user 消息只有在其后紧跟一条"已完成"的 assistant 消息时才进入快照。
 */
export function buildHistorySnapshot(messages: ChatMessage[]): HistoryMessage[] {
  const result: HistoryMessage[] = [];
  for (let i = 0; i < messages.length; i++) {
    const msg = messages[i];
    if (msg.role === "user") {
      const next = messages[i + 1];
      if (
        next &&
        next.role === "assistant" &&
        !next.isStreaming &&
        !next.error &&
        !next.isInterrupted &&
        next.content.trim()
      ) {
        result.push({ role: "user", content: msg.content });
        result.push({ role: "assistant", content: next.content });
        i++; // skip the paired assistant
      }
    }
  }
  return result;
}

export function createStreamingAssistantMessage(): ChatMessage {
  return {
    id: generateMessageId(),
    role: "assistant",
    content: "",
    statusText: "正在理解问题...",
    isStreaming: true,
  };
}

export function applyStreamEvent(message: ChatMessage, event: ChatStreamEvent): ChatMessage {
  switch (event.type) {
    case "status":
      return { ...message, statusText: event.text, isStreaming: true };
    case "table":
      return { ...message, table: { columns: event.columns, rows: event.rows } };
    case "answer_chunk":
      return { ...message, content: `${message.content}${event.text}` };
    case "done":
      return { ...message, isStreaming: false, statusText: "" };
    case "error":
      return { ...message, isStreaming: false, statusText: "", error: event.message };
  }
}

export function markInterruptedMessage(message: ChatMessage): ChatMessage {
  return {
    ...message,
    isStreaming: false,
    statusText: "",
    isInterrupted: true,
    error: message.error ?? "回答中断，请重试补充分析",
  };
}
