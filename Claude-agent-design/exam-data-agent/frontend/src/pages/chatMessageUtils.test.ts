import { describe, expect, it } from "vitest";
import {
  applyStreamEvent,
  buildHistorySnapshot,
  createStreamingAssistantMessage,
  markInterruptedMessage,
  generateMessageId,
  type ChatMessage,
} from "./chatMessageUtils";

const completedAssistant: ChatMessage = {
  id: "a1",
  role: "assistant",
  content: "上周注册用户1200人。",
  statusText: "",
  isStreaming: false,
  table: { columns: ["注册用户"], rows: [["1200"]] },
};

describe("buildHistorySnapshot", () => {
  it("keeps only completed user+assistant pairs", () => {
    const snapshot = buildHistorySnapshot([
      { id: "u1", role: "user", content: "上周注册用户多少" },
      completedAssistant,
      { id: "u2", role: "user", content: "环比呢" },
      createStreamingAssistantMessage(), // still streaming
    ]);

    expect(snapshot).toEqual([
      { role: "user", content: "上周注册用户多少" },
      { role: "assistant", content: "上周注册用户1200人。" },
    ]);
  });

  it("excludes user messages without a completed assistant follow-up", () => {
    const snapshot = buildHistorySnapshot([
      { id: "u1", role: "user", content: "上周注册用户多少" },
    ]);
    expect(snapshot).toEqual([]);
  });

  it("excludes interrupted assistant messages from history", () => {
    const interrupted = markInterruptedMessage(
      applyStreamEvent(createStreamingAssistantMessage(), {
        type: "answer_chunk",
        text: "上周注册用户1200人，",
      }),
    );

    expect(interrupted.content).toContain("上周注册用户1200人");
    expect(
      buildHistorySnapshot([
        { id: "u1", role: "user", content: "上周注册用户多少" },
        interrupted,
      ]),
    ).toEqual([]);
  });

  it("excludes error assistant messages from history", () => {
    const errorMsg: ChatMessage = {
      id: "a1",
      role: "assistant",
      content: "",
      error: "查询失败",
      isStreaming: false,
    };
    expect(
      buildHistorySnapshot([
        { id: "u1", role: "user", content: "test" },
        errorMsg,
      ]),
    ).toEqual([]);
  });
});

describe("applyStreamEvent", () => {
  it("updates statusText on status event", () => {
    const msg = createStreamingAssistantMessage();
    const updated = applyStreamEvent(msg, {
      type: "status",
      stage: "querying",
      text: "正在查询数据...",
    });
    expect(updated.statusText).toBe("正在查询数据...");
    expect(updated.isStreaming).toBe(true);
  });

  it("sets table on table event", () => {
    const msg = createStreamingAssistantMessage();
    const updated = applyStreamEvent(msg, {
      type: "table",
      columns: ["x"],
      rows: [["1"]],
    });
    expect(updated.table).toEqual({ columns: ["x"], rows: [["1"]] });
  });

  it("appends text on answer_chunk", () => {
    let msg = createStreamingAssistantMessage();
    msg = applyStreamEvent(msg, { type: "answer_chunk", text: "A" });
    msg = applyStreamEvent(msg, { type: "answer_chunk", text: "B" });
    expect(msg.content).toBe("AB");
  });

  it("clears streaming state on done", () => {
    const msg = createStreamingAssistantMessage();
    const updated = applyStreamEvent(msg, { type: "done" });
    expect(updated.isStreaming).toBe(false);
    expect(updated.statusText).toBe("");
  });

  it("sets error on error event", () => {
    const msg = createStreamingAssistantMessage();
    const updated = applyStreamEvent(msg, {
      type: "error",
      code: "SQL_FAILED",
      message: "查询失败",
    });
    expect(updated.error).toBe("查询失败");
    expect(updated.isStreaming).toBe(false);
  });
});

describe("generateMessageId", () => {
  it("returns unique ids", () => {
    const a = generateMessageId();
    const b = generateMessageId();
    expect(a).not.toBe(b);
  });
});
