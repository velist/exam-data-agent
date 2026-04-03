# 聊天界面线性布局改造实施计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 将聊天界面从左右气泡布局改为统一左对齐线性布局，用角色标签区分发言者。

**Architecture:** 仅修改 ChatBubble 组件（添加角色标签）和 chat.css（去除气泡样式、统一左对齐），不改动 Chat.tsx 的消息流逻辑和 SSE 链路。

**Tech Stack:** React, TypeScript, CSS

**Spec:** `docs/superpowers/specs/2026-04-03-chat-linear-layout-design.md`

---

### Task 1: ChatBubble 添加角色标签

**Files:**
- Modify: `frontend/src/components/ChatBubble.tsx:112-113`
- Test: `frontend/src/components/ChatBubble.test.tsx`

- [ ] **Step 1: 在 ChatBubble.test.tsx 添加角色标签测试**

在文件末尾 `describe` 块内追加两个测试：

```tsx
it("renders role label '典宝' for assistant messages", () => {
  render(<ChatBubble role="assistant" content="测试回复" />);
  expect(screen.getByText("典宝")).toBeInTheDocument();
});

it("renders role label '你' for user messages", () => {
  render(<ChatBubble role="user" content="测试提问" />);
  expect(screen.getByText("你")).toBeInTheDocument();
});
```

- [ ] **Step 2: 运行测试确认失败**

Run: `cd frontend && npx vitest run src/components/ChatBubble.test.tsx`
Expected: 2 FAIL — 找不到 "典宝" 和 "你" 文本

- [ ] **Step 3: 在 ChatBubble.tsx 添加角色标签**

在 `return` 语句中，`{/* 1. Status indicator */}` 注释之前，添加角色标签：

```tsx
{/* 0. Role label */}
<div className={`msg-role-label ${isUser ? "role-user" : "role-ai"}`}>
  {isUser ? "你" : "典宝"}
</div>
```

即在 `<div className={`message ${isUser ? "user-msg" : "ai-msg"}`}>` 之后、`{statusText && (` 之前插入。

- [ ] **Step 4: 运行测试确认通过**

Run: `cd frontend && npx vitest run src/components/ChatBubble.test.tsx`
Expected: 6 tests PASS

- [ ] **Step 5: 提交**

```bash
git add frontend/src/components/ChatBubble.tsx frontend/src/components/ChatBubble.test.tsx
git commit -m "feat(chat): add role labels to ChatBubble"
```

---

### Task 2: 重写消息样式为线性布局

**Files:**
- Modify: `frontend/src/styles/chat.css:398-441`（.message / .user-msg / .ai-msg）
- Modify: `frontend/src/styles/chat.css:810-901`（PC 端媒体查询中 .message）
- Modify: `frontend/src/styles/chat.css:906-999`（移动端媒体查询中 .message）

- [ ] **Step 1: 重写 .message 基础样式**

将 `chat.css` 中 `.message` 块（约第 399-409 行）替换为：

```css
.message {
  max-width: 100%;
  padding: 12px 0;
  border-bottom: 1px solid rgba(0,0,0,0.06);
  font-size: 15px;
  line-height: 1.5;
  animation: slideUp 0.3s ease;
  position: relative;
  z-index: 1;
  word-break: break-word;
}
```

去除了：`border-radius: 16px`（圆角气泡）

- [ ] **Step 2: 重写 .ai-msg 样式**

将 `.ai-msg` 块（约第 415-424 行）替换为：

```css
.ai-msg {
  align-self: flex-start;
  color: #333;
}
```

去除了：`background`、`backdrop-filter`、`border-bottom-left-radius`、`box-shadow`、`border`

- [ ] **Step 3: 保持 .ai-msg.guide-message**

`.ai-msg.guide-message` 保持不变（仅宽度设置）：

```css
.ai-msg.guide-message {
  width: 100%;
  max-width: 100%;
  padding: 12px 0;
}
```

- [ ] **Step 4: 重写 .user-msg 样式**

将 `.user-msg` 块（约第 431-439 行）替换为：

```css
.user-msg {
  align-self: flex-start;
  color: #555;
}
```

去除了：蓝色背景、白色文字、`align-self: flex-end`、阴影、边框

- [ ] **Step 5: 添加 .msg-role-label 样式**

在 `.user-msg` 之后添加：

```css
/* ---- Role Label ---- */
.msg-role-label {
  font-size: 13px;
  font-weight: 600;
  margin-bottom: 4px;
}
.msg-role-label.role-user {
  color: #888;
}
.msg-role-label.role-ai {
  color: #0077B6;
}
```

- [ ] **Step 6: 调整 PC 端媒体查询**

在 `@media (min-width: 768px)` 中，将 `.message` 的 `max-width: 75%` 改为：

```css
.message {
  max-width: 100%;
  font-size: 16px;
}
```

- [ ] **Step 7: 调整移动端媒体查询**

在 `@media (max-width: 767px)` 中，将 `.message` 的 `max-width: 92%` 改为：

```css
.message { max-width: 100%; }
```

- [ ] **Step 8: 运行全部前端测试确认无破坏**

Run: `cd frontend && npx vitest run`
Expected: 全部 PASS（28 tests）

- [ ] **Step 9: 提交**

```bash
git add frontend/src/styles/chat.css
git commit -m "style(chat): replace bubble layout with linear left-aligned layout"
```

---

### Task 3: 浏览器视觉验证

- [ ] **Step 1: 启动前端开发服务器**

Run: `cd frontend && npm run dev`

- [ ] **Step 2: 打开浏览器验证**

确认以下视觉效果：
1. 所有消息左对齐，无气泡包裹
2. 用户消息前有灰色 "你" 标签，文字为深灰
3. AI 消息前有蓝色 "典宝" 标签，文字为正常色
4. 消息之间有细分隔线
5. 表格/图表仍在 `data-visual-card` 卡片内正常展示
6. 引导卡片样式正常
7. XLSX 下载按钮正常
8. 移动端和 PC 端均正常

- [ ] **Step 3: 截图留证后提交（如有微调）**

```bash
git add -A && git commit -m "style(chat): fine-tune linear layout after visual review"
```
