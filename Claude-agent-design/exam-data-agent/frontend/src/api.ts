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
