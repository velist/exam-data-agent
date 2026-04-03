# 聊天界面线性布局改造设计

> 日期：2026-04-03
> 状态：已批准

## 目标

将聊天界面从左右气泡对话布局改为线性左对齐布局：
- 用户发言：纯文本，无气泡包裹
- 系统回复：富文本（数字高亮），无气泡包裹
- 通过角色标签（"你" / "典宝"）区分发言者

## 方案

**方案 A（最小改动）**：仅修改 `ChatBubble.tsx` 和 `chat.css`，不改动 `Chat.tsx` 消息流逻辑。

选择理由：改动集中，不影响 SSE 流式链路、表格/图表/XLSX 导出等核心功能，对测试影响最小。

## 改动范围

### ChatBubble.tsx

在消息内容最前面添加角色标签：

```tsx
<div className="msg-role-label">{isUser ? "你" : "典宝"}</div>
```

- 用户消息标签：灰色
- AI 消息标签：主题色（#0077B6）

### chat.css

#### .message（通用消息样式）

- 移除：`max-width: 85%`、圆角、背景色、阴影、边框
- 改为：`max-width: 100%`、`padding: 8px 0`、底部分隔线 `border-bottom: 1px solid rgba(0,0,0,0.06)`

#### .user-msg

- 移除：蓝色背景、`align-self: flex-end`、白色文字、阴影
- 改为：`align-self: flex-start`、文字颜色 `#555`

#### .ai-msg

- 移除：半透明白色背景、阴影、边框
- 改为：`align-self: flex-start`、无背景

#### 新增 .msg-role-label

- `font-size: 13px`、`font-weight: 600`、`margin-bottom: 4px`
- 用户标签色：`#888`
- AI 标签色：`#0077B6`

#### .guide-message

- 去气泡背景，保持 `width: 100%`

#### 响应式调整

- PC 端 `@media (min-width: 768px)` 中 `.message` 的 `max-width` 改为 100%（或合理宽度如 `max-width: 85%` 用于可读性）
- 移动端 `.message` 的 `max-width` 改为 100%

## 不改动的部分

| 模块 | 说明 |
|------|------|
| Chat.tsx | 消息流逻辑、SSE 处理、状态管理 |
| chatMessageUtils.ts | 纯函数，流式消息状态 |
| data-visual-card | 数据展示卡片保持现有样式 |
| guide-card | 引导卡片保持现有样式 |
| 表格/图表/XLSX 导出 | ChatBubble 内逻辑不变 |

## 对测试的影响

- `ChatBubble.test.tsx`：可能需要小幅调整（如新增角色标签的存在性断言），核心功能测试不变
- 其余测试文件无需改动
