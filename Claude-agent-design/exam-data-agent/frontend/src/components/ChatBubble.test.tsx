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
    // Numbers get formatted, so match the formatted version
    const contentIdx = text.indexOf("1,200");
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

  it("renders role label '典宝' for assistant messages", () => {
    render(<ChatBubble role="assistant" content="测试回复" />);
    expect(screen.getByText("典宝")).toBeInTheDocument();
  });

  it("renders role label '你' for user messages", () => {
    render(<ChatBubble role="user" content="测试提问" />);
    expect(screen.getByText("你")).toBeInTheDocument();
  });

  it("formats table numbers with thousand separators and 2 decimal places", () => {
    render(
      <ChatBubble
        role="assistant"
        content=""
        table={{
          columns: ["指标", "数值", "增长率"],
          rows: [
            ["用户数", "1234567.5", "15.41%"],
            ["金额", "98765432.1", "+123.456%"],
          ],
        }}
      />,
    );

    expect(screen.getByText("1,234,567.50")).toBeInTheDocument();
    expect(screen.getByText("98,765,432.10")).toBeInTheDocument();
    expect(screen.getByText("15.41%")).toBeInTheDocument();
    expect(screen.getByText("+123.46%")).toBeInTheDocument();
  });

  it("formats integer table numbers without decimal places", () => {
    render(
      <ChatBubble
        role="assistant"
        content=""
        table={{
          columns: ["指标", "销量", "用户数"],
          rows: [
            ["班次A", "1200", "530"],
            ["班次B", "98765", "4321"],
          ],
        }}
      />,
    );

    expect(screen.getByText("1,200")).toBeInTheDocument();
    expect(screen.getByText("530")).toBeInTheDocument();
    expect(screen.getByText("98,765")).toBeInTheDocument();
    expect(screen.getByText("4,321")).toBeInTheDocument();
  });

  it("does not format date-like values", () => {
    render(
      <ChatBubble
        role="assistant"
        content=""
        table={{
          columns: ["月份", "数据"],
          rows: [
            ["2024-01", "100"],
            ["2024-03", "200"],
            ["2024-12", "300"],
          ],
        }}
      />,
    );

    expect(screen.getByText("2024-01")).toBeInTheDocument();
    expect(screen.getByText("2024-03")).toBeInTheDocument();
    expect(screen.getByText("2024-12")).toBeInTheDocument();
  });

  it("formats insight text numbers: integers without decimals, floats with 2 decimals", () => {
    const { container } = render(
      <ChatBubble role="assistant" content="销量1200件，ARPU 45.67元，同比增长12.3%。" />,
    );

    const highlightedNums = container.querySelectorAll(".num-highlight");
    expect(highlightedNums.length).toBe(3);
    expect(highlightedNums[0].textContent).toBe("1,200件");
    expect(highlightedNums[1].textContent).toBe("45.67元");
    expect(highlightedNums[2].textContent).toBe("12.30%");
  });

  it("does not format date-like numbers in insight text", () => {
    const { container } = render(
      <ChatBubble role="assistant" content="2024-01月销量为5000件。" />,
    );

    const highlightedNums = container.querySelectorAll(".num-highlight");
    expect(highlightedNums.length).toBe(1);
    expect(highlightedNums[0].textContent).toBe("5,000件");
    // "2024-01" should NOT be highlighted/formatted
    const textContent = container.textContent || "";
    expect(textContent).toContain("2024-01");
    // Should NOT contain the formatted version
    expect(textContent).not.toContain("2,024");
  });

  it("formats insight text numbers with thousand separators and 2 decimal places", () => {
    const { container } = render(
      <ChatBubble role="assistant" content="上周活跃用户988765.5人，环比增长12.3%。" />,
    );

    const highlightedNums = container.querySelectorAll(".num-highlight");
    expect(highlightedNums.length).toBe(2);
    expect(highlightedNums[0].textContent).toBe("988,765.50人");
    expect(highlightedNums[1].textContent).toBe("12.30%");
  });

  it("does not format Chinese date patterns like 2026年3月 in insight text", () => {
    const { container } = render(
      <ChatBubble
        role="assistant"
        content="上月（2026年3月）销售总额为266.32万元，共17948笔订单。"
      />,
    );

    const textContent = container.textContent || "";
    // Year and month must NOT be formatted
    expect(textContent).toContain("2026年3月");
    expect(textContent).not.toContain("2,026");
    expect(textContent).not.toContain("2,026.00");
    // Real data numbers should still be formatted
    const highlightedNums = container.querySelectorAll(".num-highlight");
    const texts = Array.from(highlightedNums).map((el) => el.textContent);
    expect(texts).toContain("266.32万");
    expect(texts).toContain("17,948");
  });
});
