export const BASE_URL = import.meta.env.VITE_API_URL || "";

const LOCAL_HOSTNAMES = new Set(["localhost", "127.0.0.1", "::1"]);

/**
 * 静态模式：当没有配置后端 API 地址时（如 CF Pages 部署），
 * 从 /cache/ 目录读取预生成的 JSON 缓存。
 */
const IS_STATIC =
  typeof window !== "undefined" &&
  !import.meta.env.VITE_API_URL &&
  !LOCAL_HOSTNAMES.has(window.location.hostname);

/** 尝试从静态缓存获取查询结果（用于 CF Pages 纯前端部署） */
async function tryStaticCache(sql: string): Promise<{ columns: string[]; rows: string[][] } | null> {
  if (!IS_STATIC) return null;
  try {
    // hash SQL to match cache filename
    const normalized = sql.replace(/\s+/g, " ").trim().toUpperCase();
    const encoder = new TextEncoder();
    const hashBuffer = await crypto.subtle.digest("SHA-256", encoder.encode(normalized));
    const hashArray = Array.from(new Uint8Array(hashBuffer));
    const key = hashArray.map((b) => b.toString(16).padStart(2, "0")).join("").slice(0, 16);

    const res = await fetch(`/cache/${key}.json`);
    if (!res.ok) return null;
    const data = await res.json();
    return data.result || null;
  } catch {
    return null;
  }
}

export { IS_STATIC, tryStaticCache };

export interface ChatResponse {
  answer?: string;
  table?: { columns: string[]; rows: string[][] };
  error?: boolean;
  code?: string;
  message?: string;
}

export interface ReportResponse {
  period: { start?: string; end?: string; month?: string; weeks?: number };
  sections: Record<string, any>;
}

export interface InsightParams {
  type: "weekly" | "monthly" | "range";
  date?: string;
  start?: string;
  end?: string;
}

export async function sendChat(message: string, history: { role: string; content: string }[]): Promise<ChatResponse> {
  if (IS_STATIC) {
    return {
      error: true,
      code: "STATIC_MODE",
      message: "当前为静态部署模式，实时对话需要后端服务支持。请查看周报/月报获取数据分析。",
    };
  }
  const res = await fetch(`${BASE_URL}/api/chat`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ message, history }),
  });
  return res.json();
}

async function parseReportResponse(res: Response): Promise<ReportResponse> {
  const data = await res.json();
  if (!res.ok) {
    throw new Error(data?.detail || "报表加载失败");
  }
  return data;
}

export async function getWeeklyReport(date: string): Promise<ReportResponse> {
  const res = await fetch(`${BASE_URL}/api/report/weekly?date=${date}`);
  return parseReportResponse(res);
}

export async function getMonthlyReport(month: string): Promise<ReportResponse> {
  const res = await fetch(`${BASE_URL}/api/report/monthly?month=${month}`);
  return parseReportResponse(res);
}

export async function getRangeReport(start: string, end: string): Promise<ReportResponse> {
  const res = await fetch(`${BASE_URL}/api/report/range?start=${start}&end=${end}`);
  return parseReportResponse(res);
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
  // 静态模式下没有后端 API，直接返回提示
  if (IS_STATIC) {
    handlers.onEvent({
      type: "error",
      code: "STATIC_MODE",
      message: "当前为静态部署模式，实时对话需要后端服务支持。请查看周报/月报获取数据分析。",
    });
    return;
  }

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

export type InsightStatusEvent = {
  stage?: "querying" | "analyzing" | "generating";
  text: string;
};

export function streamInsight(
  params: InsightParams,
  onChunk: (text: string) => void,
  onDone: () => void,
  onError?: (msg: string) => void,
  onStatus?: (status: InsightStatusEvent) => void,
) {
  if (IS_STATIC) {
    onError?.("当前为静态部署模式，洞察分析需要后端服务支持。");
    onDone();
    return () => {};
  }

  const search = new URLSearchParams({ type: params.type });
  if (params.type === "range") {
    if (params.start) search.set("start", params.start);
    if (params.end) search.set("end", params.end);
  } else if (params.date) {
    search.set("date", params.date);
  }

  const url = `${BASE_URL}/api/insight/stream?${search.toString()}`;
  const eventSource = new EventSource(url);

  eventSource.onmessage = (event) => {
    if (event.data === "[DONE]") {
      eventSource.close();
      onDone();
      return;
    }
    try {
      const data = JSON.parse(event.data);
      if (data.type === "status" && data.text) {
        onStatus?.({ stage: data.stage, text: data.text });
      }
      if (data.text && data.type !== "status") {
        onChunk(data.text);
      }
    } catch {}
  };

  eventSource.onerror = () => {
    eventSource.close();
    onError?.("洞察分析加载失败，请稍后重试。");
    onDone();
  };

  return () => eventSource.close();
}
