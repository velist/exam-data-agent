const BASE_URL = import.meta.env.VITE_API_URL || "";

export interface ChatResponse {
  answer?: string;
  table?: { columns: string[]; rows: string[][] };
  error?: boolean;
  code?: string;
  message?: string;
}

export interface ReportResponse {
  period: { start?: string; end?: string; month?: string };
  sections: Record<string, any>;
}

export async function sendChat(message: string, history: { role: string; content: string }[]): Promise<ChatResponse> {
  const res = await fetch(`${BASE_URL}/api/chat`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ message, history }),
  });
  return res.json();
}

export async function getWeeklyReport(date: string): Promise<ReportResponse> {
  const res = await fetch(`${BASE_URL}/api/report/weekly?date=${date}`);
  return res.json();
}

export async function getMonthlyReport(month: string): Promise<ReportResponse> {
  const res = await fetch(`${BASE_URL}/api/report/monthly?month=${month}`);
  return res.json();
}

// --- 聊天流式 API ---

export type HistoryMessage = { role: "user" | "assistant"; content: string };

export type ChatStreamEvent =
  | { type: "status"; stage: "understanding" | "generating_sql" | "querying" | "summarizing"; text: string }
  | { type: "table"; columns: string[]; rows: string[][] }
  | { type: "answer_chunk"; text: string }
  | { type: "done" }
  | { type: "error"; code: string; message: string };

export class StreamChatError extends Error {
  code: string;
  beforeFirstEvent: boolean;
  isAbort: boolean;

  constructor(message: string, options: { code: string; beforeFirstEvent: boolean; isAbort?: boolean }) {
    super(message);
    this.code = options.code;
    this.beforeFirstEvent = options.beforeFirstEvent;
    this.isAbort = Boolean(options.isAbort);
  }
}

export async function streamChat(
  message: string,
  history: HistoryMessage[],
  handlers: { onEvent: (event: ChatStreamEvent) => void },
  options?: { signal?: AbortSignal },
): Promise<void> {
  let res: Response;
  try {
    res = await fetch(`${BASE_URL}/api/chat/stream`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ message, history }),
      signal: options?.signal,
    });
  } catch (error) {
    if (options?.signal?.aborted) {
      throw new StreamChatError("用户取消", { code: "STREAM_ABORTED", beforeFirstEvent: true, isAbort: true });
    }
    throw new StreamChatError("流式请求初始化失败", { code: "STREAM_INIT_FAILED", beforeFirstEvent: true });
  }

  if (!res.ok || !res.body) {
    throw new StreamChatError("流式请求初始化失败", { code: "STREAM_INIT_FAILED", beforeFirstEvent: true });
  }

  const reader = res.body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";
  let receivedFirstEvent = false;
  let receivedTerminal = false;

  try {
    while (true) {
      const { done, value } = await reader.read();
      if (done) break;
      buffer += decoder.decode(value, { stream: true });
      const frames = buffer.split("\n\n");
      buffer = frames.pop() ?? "";
      for (const frame of frames) {
        const line = frame
          .split("\n")
          .map((item) => item.trim())
          .find((item) => item.startsWith("data: "));
        if (!line) continue;
        const event = JSON.parse(line.slice(6)) as ChatStreamEvent;
        receivedFirstEvent = true;
        if (event.type === "done" || event.type === "error") {
          receivedTerminal = true;
        }
        handlers.onEvent(event);
      }
    }
  } catch (error) {
    if (options?.signal?.aborted) {
      throw new StreamChatError("用户取消", { code: "STREAM_ABORTED", beforeFirstEvent: !receivedFirstEvent, isAbort: true });
    }
    throw new StreamChatError("流式读取失败", { code: "STREAM_READ_FAILED", beforeFirstEvent: !receivedFirstEvent });
  }

  if (receivedFirstEvent && !receivedTerminal) {
    throw new StreamChatError("流式中断：未收到终态事件", { code: "STREAM_INTERRUPTED", beforeFirstEvent: false });
  }
}

// --- 报告洞察流式 API ---

export function streamInsight(type: string, date: string, onChunk: (text: string) => void, onDone: () => void) {
  const url = `${BASE_URL}/api/insight/stream?type=${type}&date=${date}`;
  const eventSource = new EventSource(url);

  eventSource.onmessage = (event) => {
    if (event.data === "[DONE]") {
      eventSource.close();
      onDone();
      return;
    }
    try {
      const data = JSON.parse(event.data);
      if (data.text) onChunk(data.text);
    } catch {}
  };

  eventSource.onerror = () => {
    eventSource.close();
    onDone();
  };

  return () => eventSource.close();
}
