import { render, screen } from "@testing-library/react";
import { describe, it, expect } from "vitest";
import ChatBubble from "./ChatBubble";

describe("ChatBubble", () => {
  it("renders assistant sections in status -> table -> content -> error order", () => {
    const { container } = render(
      <ChatBubble
        role="assistant"
        content="上周注册用户1200人。"
        statusText="正在生成分析结论..."
        table={{ columns: ["指标", "数值"], rows: [["注册用户", "1200"]] }}
        error="回答中断，请重试补充分析"
      />,
    );

    const text = container.textContent || "";
    const statusIdx = text.indexOf("正在生成分析结论...");
    const tableIdx = text.indexOf("注册用户");
    const contentIdx = text.indexOf("上周注册用户1200人。");
    const errorIdx = text.indexOf("回答中断，请重试补充分析");

    expect(statusIdx).toBeLessThan(tableIdx);
    expect(tableIdx).toBeLessThan(contentIdx);
    expect(contentIdx).toBeLessThan(errorIdx);
  });

  it("shows explicit empty state instead of empty table", () => {
    render(
      <ChatBubble
        role="assistant"
        content=""
        table={{ columns: ["指标", "数值"], rows: [] }}
      />,
    );

    expect(screen.getByText("查询完成，暂无匹配数据")).toBeInTheDocument();
  });

  it("renders error message when present", () => {
    render(
      <ChatBubble role="assistant" content="" error="查询失败" />,
    );

    expect(screen.getByText("查询失败")).toBeInTheDocument();
  });

  it("renders user bubble without status/error sections", () => {
    const { container } = render(
      <ChatBubble role="user" content="上周注册用户多少" />,
    );

    expect(container.textContent).toContain("上周注册用户多少");
  });
});
