# 对话导出按钮与报表 Markdown 实施计划 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 复现并修复“对话页未显示下载 XLSX 按钮”和“报表详情 Markdown 层级不明显/未正确体现”的问题，并用 Playwright 在真实页面确认结果。

**Architecture:** 先锁定两个问题的固定复现输入，再用单元测试把期望行为写死，最后只在诊断结果指向的文件做最小修改。对话导出按钮优先检查“是否真的返回了非空表格”；报表 Markdown 优先检查“流式内容是否已是 Markdown，再决定改样式还是改生成要求”。

**Tech Stack:** React 19 / TypeScript / Testing Library / Vitest / ReactMarkdown / FastAPI / Playwright MCP / SSE

---

## File Map

| 路径 | 动作 | 责任 |
|------|------|------|
| `frontend/src/components/ChatBubble.test.tsx` | Modify | 为 XLSX 按钮显示/隐藏规则补测试 |
| `frontend/src/pages/chatMessageUtils.test.ts` | Optional modify | 若需要锁定 table 事件保留行为，可在这里加回归测试 |
| `frontend/src/components/ChatBubble.tsx` | Modify only if tests prove needed | 导出按钮显示逻辑或样式最小修复 |
| `frontend/src/components/InsightText.test.tsx` | Create | 锁定 Markdown 标题、列表、加粗渲染结果 |
| `frontend/src/components/InsightText.tsx` | Modify only if tests prove needed | Markdown 容器或渲染配置修复 |
| `frontend/src/styles/report.css` | Modify only if tests/Playwright prove needed | Markdown 可视层级样式修复 |
| `backend/prompts/insight.txt` | Modify only if SSE 原文不是 Markdown | 强化输出结构要求 |
| `backend/services/insight.py` | Modify only if prompt 接线 needed | 保持最小改动，不改 SSE 协议 |

## Preconditions

- 本计划默认执行根目录是 `D:\文档\文档\公司\NLP\Claude-agent-design\exam-data-agent`。
- 固定导出按钮复现问题的基线输入：`3月各班次类型销量和销售额`。
- 固定 Markdown 验收结构：`### 数据概览`、`### 关键发现`、`### 产品建议`、列表项 `- **问题**：...`、加粗文本 `**具体数据和变化幅度**`。
- 标题层级只要求“有清晰 Markdown 标题结构”，不强制必须是 `##` 还是 `###`；只要最终页面能稳定呈现标题层级即可。
- 必须先做浏览器复现和网络观察，再决定是否改 `ChatBubble.tsx`、`report.css` 或 `backend/prompts/insight.txt`。
- 如果真实页面与单元测试冲突，优先相信 Playwright 观察结果，再补测试贴合实际问题。

---

### Task 1: 为导出按钮行为补前端测试

**Files:**
- Modify: `frontend/src/components/ChatBubble.test.tsx`
- Test: `frontend/src/components/ChatBubble.test.tsx`

- [ ] **Step 1: 写失败测试，锁定“有非空表格时显示下载按钮”**

在 `ChatBubble.test.tsx` 增加：

```tsx
it("shows download button when table has columns and rows", () => {
  render(
    <ChatBubble
      role="assistant"
      content=""
      table={{ columns: ["班次类型", "销量"], rows: [["课程", "12"]] }}
    />,
  );

  expect(screen.getByRole("button", { name: "下载 XLSX" })).toBeInTheDocument();
});
```

- [ ] **Step 2: 写失败测试，锁定“空表时不显示下载按钮”**

```tsx
it("does not show download button for empty table rows", () => {
  render(
    <ChatBubble
      role="assistant"
      content=""
      table={{ columns: ["班次类型", "销量"], rows: [] }}
    />,
  );

  expect(screen.queryByRole("button", { name: "下载 XLSX" })).not.toBeInTheDocument();
});
```

- [ ] **Step 3: 运行测试并确认现状**

Run: `cd frontend && npx vitest run src/components/ChatBubble.test.tsx`

Expected:
- 如果“有表格显示按钮”已通过，说明问题更可能出在运行时数据链路或页面样式
- 如果失败，再进入 Step 4 修复组件

- [ ] **Step 4: 仅在测试失败时做最小实现修复**

可接受的最小修复：
- 调整 `canDownloadTable` 条件
- 调整按钮 DOM/可访问名称
- 修复按钮容器在有图表/无图表时的布局隐藏问题

禁止：
- 为空表放宽按钮展示
- 重写 XLSX 生成逻辑

- [ ] **Step 5: 重新运行组件测试**

Run: `cd frontend && npx vitest run src/components/ChatBubble.test.tsx`

Expected: PASS。

- [ ] **Step 6: 提交按钮侧代码（如果有改动）**

```bash
git add frontend/src/components/ChatBubble.test.tsx frontend/src/components/ChatBubble.tsx
git commit -m "fix: keep chat xlsx button aligned with table state"
```

若只有测试新增且代码无需改动，提交信息改为：

```bash
git add frontend/src/components/ChatBubble.test.tsx
git commit -m "test: lock chat xlsx button visibility rules"
```

---

### Task 2: 用 Playwright 复现导出按钮问题并定位根因

**Files:**
- Verify only: `frontend/src/components/ChatBubble.tsx`
- Verify only: `frontend/src/pages/Chat.tsx`
- Verify only: `backend/services/chat_stream.py`
- Optional modify: `frontend/src/pages/chatMessageUtils.test.ts`

- [ ] **Step 1: 启动真实服务**

Run:

```bash
start.bat
```

Expected: 前端构建成功，后端监听 `http://localhost:8230`。

- [ ] **Step 2: 用 Playwright 打开聊天页并发送固定基线问题**

基线输入：`3月各班次类型销量和销售额`

检查点：
- 是否出现表格
- 是否出现“下载 XLSX”按钮
- assistant 消息是否仍在流式中

- [ ] **Step 3: 观察网络 / 页面状态，判断根因属于哪一类**

必须落到以下两类之一：
1. **接口返回了非空 `table`，但按钮没显示**
2. **接口没有返回非空 `table`**

记录至少这些证据：
- `table.columns`
- `table.rows.length`
- DOM 中是否存在按钮

- [ ] **Step 4: 如果根因是“接口没回非空 table”，先补最小保护测试**

可在 `frontend/src/pages/chatMessageUtils.test.ts` 或相关测试中补一条回归测试，确保收到 `table` 事件时 message 上的 `table` 不会被后续事件覆盖或清空。

示例：

```ts
it("keeps table after answer chunks and done", () => {
  let msg = createStreamingAssistantMessage();
  msg = applyStreamEvent(msg, { type: "table", columns: ["x"], rows: [["1"]] });
  msg = applyStreamEvent(msg, { type: "answer_chunk", text: "ok" });
  msg = applyStreamEvent(msg, { type: "done" });
  expect(msg.table).toEqual({ columns: ["x"], rows: [["1"]] });
});
```

- [ ] **Step 5: 如果根因是“接口没回非空 table”，继续排查并修后端链路**

按下面顺序收敛，不要停在“知道不是按钮问题”：
1. 检查 `backend/services/chat_stream.py` 是否发送了 `type: "table"` 事件
2. 检查 `backend/services/chat.py::_execute_query_with_retry()` 返回的 `table_data` 是否为空
3. 若 SQL 实际有结果但事件里没有表格，修流式事件编排或前端消息状态保留逻辑
4. 若 SQL 结果本身为空，但该基线问题按当前示例本应有数据，回到 NL2SQL / 查询执行链路定位，不修改按钮逻辑掩盖问题

此分支至少要补一个对应测试：
- 前端：`chatMessageUtils.test.ts`，锁定 `table` 不被后续事件丢失
- 若改后端：`backend/tests/test_chat_stream.py`，锁定流式响应在有结果时一定包含 `table` 事件

- [ ] **Step 6: 根据定位结果做最小修复并重跑相关测试**

Run（按实际改动选用）：
- `cd frontend && npx vitest run src/components/ChatBubble.test.tsx src/pages/chatMessageUtils.test.ts`
- 如果动到后端流式链路，再加：`cd backend && python -m pytest tests/test_chat_stream.py tests/test_main.py -q`

Expected: PASS。

---

### Task 3: 为 Markdown 渲染结果补组件测试

**Files:**
- Create: `frontend/src/components/InsightText.test.tsx`
- Test: `frontend/src/components/InsightText.test.tsx`

- [ ] **Step 1: 写失败测试，锁定 Markdown 标题/列表/加粗会被渲染成结构**

```tsx
import { render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import InsightText from "./InsightText";

vi.mock("../api", () => ({
  streamInsight: (_params: unknown, onChunk: (text: string) => void, onDone: () => void) => {
    onChunk("### 数据概览\n\n**具体数据和变化幅度**\n\n### 关键发现\n- **问题**：课程销量增长\n\n### 产品建议");
    onDone();
    return () => {};
  },
}));

describe("InsightText markdown", () => {
  it("renders headings, bold text and list items from markdown", async () => {
    render(<InsightText params={{ type: "monthly", date: "2026-03" }} />);

    expect(await screen.findByRole("heading", { name: "数据概览" })).toBeInTheDocument();
    expect(screen.getByText("具体数据和变化幅度").tagName.toLowerCase()).toBe("strong");
    expect(screen.getByRole("heading", { name: "关键发现" })).toBeInTheDocument();
    expect(screen.getByText("问题").tagName.toLowerCase()).toBe("strong");
  });
});
```

- [ ] **Step 2: 运行测试并确认现状**

Run: `cd frontend && npx vitest run src/components/InsightText.test.tsx`

Expected:
- 若失败，说明 `InsightText` 当前在测试环境下没有把 Markdown 结构正确渲染出来
- 若通过，则问题更可能是样式层或后端实际输出内容不稳定

- [ ] **Step 3: 仅在测试失败时修复组件层问题**

允许的最小改动：
- 调整 `InsightText.tsx` 中 `ReactMarkdown` 容器或加载结束逻辑
- 避免流式游标/空态覆盖已生成内容

禁止：
- 改成聊天页 Markdown
- 重写 SSE 逻辑

- [ ] **Step 4: 重新运行组件测试**

Run: `cd frontend && npx vitest run src/components/InsightText.test.tsx`

Expected: PASS。

- [ ] **Step 5: 提交 Markdown 组件层改动（如果有）**

```bash
git add frontend/src/components/InsightText.test.tsx frontend/src/components/InsightText.tsx
git commit -m "fix: preserve report markdown rendering structure"
```

如果只有新增测试，则改成 `test:` 前缀。

---

### Task 4: 用 Playwright 验证报表详情 Markdown 的真实渲染与样式

**Files:**
- Verify only: `frontend/src/components/InsightText.tsx`
- Modify only if needed: `frontend/src/styles/report.css`
- Modify only if needed: `backend/prompts/insight.txt`
- Modify only if needed: `backend/services/insight.py`

- [ ] **Step 1: 打开固定报表入口，观察洞察区域实际输出**

固定复现入口优先使用：`http://localhost:8230/report?type=monthly`，并在页面中选择 `2026-03` 月报（若该月无内容，再退回使用一个当前已有洞察内容的周报日期）。

优先检查：
- 是否出现 `### 数据概览 / ### 关键发现 / ### 产品建议` 结构
- 列表是否渲染成 `<ul>/<li>`
- 加粗是否渲染成 `<strong>`

- [ ] **Step 2: 如果 DOM 结构正确但视觉层级不明显，修 `report.css`**

允许的最小修复：
- 增强 `.report-insight__markdown h3`
- 增强 `.report-insight__markdown ul/li/strong`
- 修复容器 margin / padding / contrast 导致的“看起来像纯文本”问题

完成后运行：

```bash
cd frontend && npm test && npm run build
```

Expected: PASS。

- [ ] **Step 3: 如果 SSE 原文不是 Markdown，修 `backend/prompts/insight.txt`**

只增强提示词，不改 SSE 协议。目标是让模型稳定输出：
- `### 数据概览`
- `### 关键发现`
- `### 产品建议`
- `- **问题**：...`

如需在 `backend/services/insight.py` 做最小接线补充，只允许补说明，不允许改事件格式。

完成后运行：

```bash
cd backend && python -m pytest tests/test_main.py -q
```

Expected: PASS。

- [ ] **Step 4: 用 Playwright 复验真实页面**

通过浏览器确认：
- 标题可见
- 列表有项目符号或明确分组
- 加粗文本有层级差异
- 不影响“数据查询中 / 数据分析中 / 分析生成中”状态卡片

---

### Task 5: 最终验证与交接

**Files:**
- Verify only: `frontend/src/components/ChatBubble.tsx`
- Verify only: `frontend/src/components/InsightText.tsx`
- Verify only: `frontend/src/styles/report.css`
- Verify only: `backend/prompts/insight.txt`

- [ ] **Step 1: 跑前端相关测试集合**

Run:

```bash
cd frontend && npx vitest run \
  src/components/ChatBubble.test.tsx \
  src/components/InsightText.test.tsx \
  src/pages/chatMessageUtils.test.ts
```

Expected: PASS。

- [ ] **Step 2: 如果本轮改过后端，再跑后端相关测试**

Run:

```bash
cd backend && python -m pytest tests/test_chat_stream.py tests/test_main.py -q
```

Expected: PASS。

- [ ] **Step 3: 跑前端构建**

Run: `cd frontend && npm run build`

Expected: PASS。

- [ ] **Step 4: 用 Playwright 做最终人工验收**

验收结论必须同时满足：
- 基线问题 `3月各班次类型销量和销售额` 返回表格时，页面出现“下载 XLSX”按钮
- 点击按钮可以下载文件，且文件包含完整表头和至少一行数据
- 报表详情页中 `### 数据概览 / ### 关键发现 / ### 产品建议` 具有清晰层级
- 空表格回答仍不显示下载按钮

- [ ] **Step 5: 完成前使用 @superpowers:verification-before-completion**

目标：在宣称修复完成之前，再次确认浏览器复现、测试、构建都已有真实证据。
