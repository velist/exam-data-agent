# Insight Optimization Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 在不改查数主链路和前端协议的前提下，新增共享洞察上下文层，统一聊天洞察与报表洞察的分析骨架，并补强与分析强相关的意图建模。

**Architecture:** 先新增一个纯函数模块 `backend/services/insight_context.py`，把消息、history、表格结果、报表结果统一归纳为“查询意图 / 分析意图 / 指标域 / 证据等级 / 考季阶段”的结构化上下文。然后把这层接入 `backend/services/chat.py` 与 `backend/services/insight.py`，让聊天总结和报表洞察共享同一套生成约束；`chat_stream.py`、`dataset_router.py`、`report.py` 与前端流式消费保持兼容，仅通过测试回归确认不被影响。

**Tech Stack:** Python 3, FastAPI, OpenAI-compatible client, pytest, SSE streaming, React/Vite（仅用于本地手工回归）

---

## 文件结构与职责

- `backend/services/insight_context.py`（新建）
  - 纯函数模块
  - 负责构造聊天洞察与报表洞察共享的分析上下文
  - 输出查询意图、分析意图、业务域、证据等级、考季阶段、上下文文本
- `backend/services/chat.py:183-223,299-328`
  - 聊天总结链路
  - 接入共享上下文，并统一总结骨架
- `backend/services/insight.py:74-96`
  - 报表洞察链路
  - 在流式生成前注入共享上下文
- `backend/prompts/insight.txt:1-33`
  - 报表洞察提示词模板
  - 升级为与聊天总结一致的骨架与约束
- `backend/tests/test_insight_context.py`（新建）
  - 测共享上下文构造逻辑
- `backend/tests/test_insight.py`（新建）
  - 测报表洞察流式生成时的上下文注入与状态流
- `backend/tests/test_chat.py`
  - 测聊天总结 prompt 与低/中/高证据约束
- `backend/tests/test_main.py`
  - 测 `/api/insight/stream` 路由与 SSE 协议兼容
- `backend/tests/test_chat_stream.py`
  - 回归确认聊天 SSE 事件结构不变
- `backend/tests/test_dataset_router.py`
  - 回归确认快速路由逻辑不被意图增强带坏
- `docs/superpowers/specs/2026-04-08-insight-optimization-design.md`
  - 已批准的设计依据，执行中不得扩展到查数链路重构、规则引擎或上线部署

---

### Task 1: 新增共享洞察上下文模块

**Files:**
- Create: `backend/services/insight_context.py`
- Create: `backend/tests/test_insight_context.py`
- Reference: `backend/services/chat.py:40-167`
- Reference: `backend/services/report.py:112-209`
- Reference: `docs/superpowers/specs/2026-04-08-insight-optimization-design.md:100-175`

- [ ] **Step 1: 写失败测试，锁定共享上下文的最小行为**

在 `backend/tests/test_insight_context.py` 先写 6 个最小失败用例：

```python
from datetime import date
from services.insight_context import (
    build_chat_analysis_context,
    build_report_analysis_context,
    infer_exam_stage,
    infer_exam_type,
)


def test_build_chat_analysis_context_marks_low_evidence_for_single_value():
    context = build_chat_analysis_context(
        message="上月销售总额",
        history=[],
        table_data={"columns": ["sale_amount"], "rows": [["540000"]]},
        today=date(2026, 4, 8),
    )
    assert context["analysis_intent"] == "value_only"
    assert context["evidence_level"] == "low"
    assert context["business_domain"] == "sales"


def test_build_chat_analysis_context_marks_trend_focus_for_follow_up():
    context = build_chat_analysis_context(
        message="环比呢",
        history=[{"role": "user", "content": "上周注册用户多少"}],
        table_data={"columns": ["指标", "数值", "环比"], "rows": [["注册用户", "1200", "+10%"]]},
        today=date(2026, 4, 8),
    )
    assert context["query_intent"] == "follow_up_analysis"
    assert context["analysis_intent"] == "trend_focus"
    assert context["evidence_level"] == "high"


def test_infer_exam_type_detects_nurse_from_message_keywords():
    assert infer_exam_type("护考课程参与率怎么样", []) == "nurse"


def test_infer_exam_stage_returns_none_when_exam_type_unknown():
    assert infer_exam_stage(date(2026, 4, 8), None) is None


def test_build_chat_analysis_context_includes_exam_type_and_stage_when_detected():
    context = build_chat_analysis_context(
        message="护考付费转化率",
        history=[],
        table_data={"columns": ["pay_conv_rate", "环比"], "rows": [["12.5%", "+3.0%"]]},
        today=date(2026, 4, 8),
    )
    assert context["exam_type"] == "nurse"
    assert context["exam_stage"] == "冲刺提分期"


def test_build_report_analysis_context_marks_structured_report_as_medium_or_high():
    report = {
        "period": {"month": "2026-03"},
        "sections": {
            "pay": {
                "metrics": {
                    "pay_users": {"label": "付费用户", "value": "800", "wow": "+12.00%", "yoy": "N/A"}
                }
            }
        },
    }
    context = build_report_analysis_context("monthly", report, today=date(2026, 4, 8))
    assert context["business_domain"] == "payment"
    assert context["evidence_level"] in {"medium", "high"}
```

- [ ] **Step 2: 运行新测试，确认当前失败**

Run:

```bash
cd backend && python -m pytest tests/test_insight_context.py -v
```

Expected:
- FAIL，报 `ModuleNotFoundError: No module named 'services.insight_context'`
  或函数未定义 / 返回结构不匹配

- [ ] **Step 3: 写最小实现，先让共享上下文可用**

在 `backend/services/insight_context.py` 新建纯函数模块，最小先提供这些函数：

```python
from __future__ import annotations

from datetime import date
from typing import Any


def infer_exam_type(message: str, history: list[dict] | None = None, report: dict[str, Any] | None = None) -> str | None:
    ...


def infer_exam_stage(today: date, exam_type: str | None) -> str | None:
    if exam_type is None:
        return None
    month = today.month
    if exam_type == "nurse":
        if month in {3, 4}:
            return "冲刺提分期"
        if month in {11, 12}:
            return "报名启动期"
    if exam_type == "physician":
        if month in {6, 7, 8}:
            return "冲刺提分期"
        if month in {9, 10, 11}:
            return "查分转化期"
    return None


def build_chat_analysis_context(message: str, history: list[dict], table_data: dict[str, Any], today: date | None = None) -> dict[str, Any]:
    ...


def build_report_analysis_context(report_type: str, report: dict[str, Any], today: date | None = None) -> dict[str, Any]:
    ...
```

实现要求：
- 只做纯函数，不查库、不依赖 FastAPI
- `infer_exam_type()` 先做最小关键词推断，至少支持：`nurse`、`physician`、`pharmacist`、`health_title`；无法识别返回 `None`
- 聊天链路从 `message + history` 推断考试类型；报表链路可从 `report` 文本标签或缺省上下文推断，推不出就返回 `None`
- `query_intent` 至少支持：`new_query`、`follow_up_analysis`、`follow_up_filter`、`follow_up_grouping`、`detail_or_ranking`
- `analysis_intent` 至少支持：`value_only`、`trend_focus`、`anomaly_focus`、`action_focus`
- `business_domain` 至少支持：`user_growth`、`retention`、`learning_behavior`、`payment`、`sales`、`customer_service`
- `evidence_level` 只允许：`low`、`medium`、`high`
- 返回结果里显式包含 `exam_type` 与 `exam_stage`
- 额外返回 `context_text`，供 chat / insight 直接拼进 LLM 请求
- 无法识别考试类型时，`exam_stage` 返回 `None`，不猜测

- [ ] **Step 4: 扩充实现，让 context_text 足够稳定可复用**

`context_text` 输出格式固定为多行中文键值，便于测试与 prompt 复用，例如：

```text
查询意图：follow_up_analysis
分析意图：trend_focus
业务域：user_growth
考试类型：nurse
证据等级：high
考季阶段：冲刺提分期
口径继承：沿用上一轮时间范围与统计对象
```

要求：
- 缺失值统一输出“未识别”或“无”
- 不把原始 `history` 或整张表格重复展开到这里
- 不在这一步生成建议文案，只做上下文摘要

- [ ] **Step 5: 重新运行上下文模块测试，确认通过**

Run:

```bash
cd backend && python -m pytest tests/test_insight_context.py -v
```

Expected:
- PASS，6 个新用例全部通过

- [ ] **Step 6: 提交一个最小检查点**

```bash
git add backend/services/insight_context.py backend/tests/test_insight_context.py
git commit -m "feat: add shared insight context builder"
```

---

### Task 2: 让聊天总结接入共享上下文与统一骨架

**Files:**
- Modify: `backend/services/chat.py:183-223`
- Modify: `backend/services/chat.py:299-328`
- Modify: `backend/tests/test_chat.py`
- Test: `backend/tests/test_chat_stream.py`
- Test: `backend/tests/test_dataset_router.py`
- Reference: `docs/superpowers/specs/2026-04-08-insight-optimization-design.md:177-255`

- [ ] **Step 1: 先写失败测试，锁定聊天总结的新约束**

在 `backend/tests/test_chat.py` 新增至少 3 个失败用例：

```python
def test_summarize_result_injects_analysis_context(monkeypatch):
    captured = {}

    def fake_create(**kwargs):
        captured.update(kwargs)
        return types.SimpleNamespace(
            choices=[types.SimpleNamespace(message=types.SimpleNamespace(content="当前注册用户1200人。"))]
        )

    monkeypatch.setattr(chat_service.client.chat.completions, "create", fake_create)
    monkeypatch.setattr(
        chat_service,
        "build_chat_analysis_context",
        lambda message, history, table_data: {
            "context_text": "查询意图：follow_up_analysis\n分析意图：trend_focus\n业务域：user_growth\n证据等级：high\n考季阶段：未识别"
        },
    )

    chat_service._summarize_result(
        "环比呢",
        {"columns": ["指标", "数值", "环比"], "rows": [["注册用户", "1200", "+10%"]]},
        [{"role": "user", "content": "上周注册用户多少"}],
    )

    request_text = "\n".join(item["content"] for item in captured["messages"])
    assert "证据等级：high" in request_text
    assert "查询意图：follow_up_analysis" in request_text


def test_summarize_result_low_evidence_prompt_forbids_action_suggestion(monkeypatch):
    captured = {}
    ...
    assert "低证据时只报核心数据" in captured["messages"][0]["content"]


def test_stream_summary_chunks_reuses_same_summary_message_builder(monkeypatch):
    ...
    assert captured_sync_messages == captured_stream_messages
```

- [ ] **Step 2: 运行聊天总结相关测试，确认当前失败**

Run:

```bash
cd backend && python -m pytest tests/test_chat.py -v
```

Expected:
- FAIL，原因应为 `build_chat_analysis_context` 未接入
- 或 sync / stream 两条链路尚未复用同一套 summary message builder

- [ ] **Step 3: 先抽一个共享的 summary message 组装函数**

在 `backend/services/chat.py` 中新增一个仅服务总结阶段的 helper，例如：

```python
def _build_summary_messages(message: str, table_data: dict, history: list[dict] | None = None) -> list[dict]:
    history = history or []
    context = build_chat_analysis_context(message, history, table_data)
    header = " | ".join(table_data["columns"])
    rows_text = "\n".join([" | ".join(row) for row in table_data["rows"][:20]])
    history_text = "\n".join([f"{item['role']}: {item['content']}" for item in history[-6:]]) or "无"
    return [
        {"role": "system", "content": CHAT_SUMMARY_SYSTEM_PROMPT},
        {
            "role": "user",
            "content": f"分析上下文：\n{context['context_text']}\n\n最近对话上下文：\n{history_text}\n\n当前问题：{message}\n\n查询结果：\n{header}\n{rows_text}",
        },
    ]
```

要求：
- `_summarize_result()` 与 `_stream_summary_chunks()` 统一改用它
- 只重构“总结消息组装”这一小块，不动 SQL 生成与查询逻辑

- [ ] **Step 4: 更新聊天总结系统提示词，显式落地证据约束**

把 `CHAT_SUMMARY_SYSTEM_PROMPT` 调整为统一骨架，至少加上这些规则：

```python
CHAT_SUMMARY_SYSTEM_PROMPT = (
    "你是考试宝典的高级数据分析师。请严格按以下顺序输出：核心结论、趋势/异常、业务判断、建议动作。\n"
    "规则：\n"
    "- 低证据时只报核心数据，不输出泛化建议\n"
    "- 只有存在同比/环比/多期趋势时，才写趋势或异常\n"
    "- 建议动作必须绑定当前指标域与考试宝典已有模块\n"
    "- 无法识别考季阶段时，不要自行猜测\n"
    "- 总共不超过 3-4 句话，每句话都要有信息量"
)
```

不要做的事：
- 不引入第二套聊天 prompt 文件
- 不新增复杂模板引擎
- 不改 `chat()` 返回结构

- [ ] **Step 5: 运行聊天总结与追问回归测试，确认通过**

Run:

```bash
cd backend && python -m pytest tests/test_chat.py tests/test_chat_stream.py tests/test_dataset_router.py -v
```

Expected:
- PASS
- `test_chat_stream.py` 里 SSE 事件顺序不变
- `test_dataset_router.py` 里快速路由行为不变

- [ ] **Step 6: 提交聊天链路检查点**

```bash
git add backend/services/chat.py backend/tests/test_chat.py
git commit -m "feat: unify chat insight summary context"
```

---

### Task 3: 让报表洞察接入共享上下文并补齐接口测试

**Files:**
- Modify: `backend/services/insight.py:74-96`
- Modify: `backend/prompts/insight.txt:1-33`
- Create: `backend/tests/test_insight.py`
- Modify: `backend/tests/test_main.py`
- Reference: `docs/superpowers/specs/2026-04-08-insight-optimization-design.md:124-255`

- [ ] **Step 1: 先写失败测试，锁定报表洞察的上下文注入**

新建 `backend/tests/test_insight.py`，先写两个失败用例：

```python
import asyncio
import json
import os
import sys
import types

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
import services.insight as insight_service


def _collect_async_events(gen):
    async def _consume():
        items = []
        async for chunk in gen:
            text = chunk.decode() if isinstance(chunk, bytes) else chunk
            if text.startswith("data: ") and "[DONE]" not in text:
                items.append(json.loads(text[len("data: "):].strip()))
        return items
    return asyncio.run(_consume())


def test_stream_insight_injects_report_analysis_context(monkeypatch):
    captured = {}

    monkeypatch.setattr(
        insight_service,
        "get_monthly_report",
        lambda month: {
            "period": {"month": month},
            "sections": {"pay": {"metrics": {"pay_users": {"label": "付费用户", "value": "800", "wow": "+12.00%", "yoy": "N/A"}}}},
        },
    )
    monkeypatch.setattr(insight_service, "_load_prompt", lambda _: "分析上下文\n{analysis_context}\n\n报告数据\n{report_data}")
    monkeypatch.setattr(
        insight_service,
        "build_report_analysis_context",
        lambda report_type, report: {"context_text": "业务域：payment\n证据等级：high\n考季阶段：冲刺提分期"},
    )

    def fake_create(**kwargs):
        captured.update(kwargs)
        chunk = types.SimpleNamespace(choices=[types.SimpleNamespace(delta=types.SimpleNamespace(content="ok"))])
        return [chunk]

    monkeypatch.setattr(insight_service.client.chat.completions, "create", fake_create)

    events = _collect_async_events(insight_service.stream_insight("monthly", date="2026-03"))
    request_text = "\n".join(item["content"] for item in captured["messages"])
    assert "业务域：payment" in request_text
    assert any(event.get("type") == "status" for event in events)


def test_stream_insight_keeps_status_sequence(monkeypatch):
    ...
    assert [event["stage"] for event in status_events] == ["querying", "analyzing", "generating"]
```

- [ ] **Step 2: 给 `/api/insight/stream` 补一个失败的接口测试**

在 `backend/tests/test_main.py` 增加一个用例，要求与 `/api/chat/stream` 一样锁住 SSE 协议：

```python
def test_insight_stream_route_exists_and_returns_sse(monkeypatch):
    async def fake_stream(*args, **kwargs):
        yield 'data: {"type":"status","stage":"querying","text":"数据查询中"}\n\n'
        yield 'data: [DONE]\n\n'

    monkeypatch.setattr(main_module, "stream_insight", fake_stream)

    client = TestClient(main_module.app)
    response = client.get("/api/insight/stream?type=monthly&date=2026-03")

    assert response.status_code == 200
    assert "text/event-stream" in response.headers["content-type"]
    assert response.headers.get("cache-control") == "no-cache"
```

- [ ] **Step 3: 运行报表洞察相关测试，确认当前失败**

Run:

```bash
cd backend && python -m pytest tests/test_insight.py tests/test_main.py -v
```

Expected:
- FAIL，原因是 `build_report_analysis_context` 尚未接入
- 或 prompt 还没有 `{analysis_context}` 占位符
- 或 `/api/insight/stream` 尚无锁定测试

- [ ] **Step 4: 写最小实现，把共享上下文注入报表洞察链路**

修改 `backend/services/insight.py`：

```python
report_text = _format_report_for_prompt(report, report_type)
analysis_context = build_report_analysis_context(report_type, report)
prompt_template = _load_prompt("insight.txt")
prompt = (
    prompt_template
    .replace("{analysis_context}", analysis_context["context_text"])
    .replace("{report_data}", report_text)
)
```

要求：
- 只在 `stream_insight()` 注入上下文
- 保持现有状态事件顺序：`querying -> analyzing -> generating`
- 保持最终 `[DONE]` 结束帧不变

- [ ] **Step 5: 升级 `backend/prompts/insight.txt`，统一输出骨架**

把 prompt 改成显式包含共享上下文占位符，并与聊天总结对齐：

```text
你是「考试宝典」的高级数据分析师。

## 分析上下文
{analysis_context}

## 输出要求
请严格按以下顺序输出：
1. 核心结论
2. 趋势 / 异常（仅在存在同比 / 环比 / 多期对比证据时输出）
3. 业务判断
4. 建议动作（仅在证据充分时输出）

规则：
- 低证据时只报核心数据，不输出泛化建议
- 建议动作必须绑定考试宝典已有模块
- 无法识别考季阶段时，不要自行猜测
- 使用 Markdown 输出

## 报告数据
{report_data}
```

不要做的事：
- 不单独引入新的 prompt 文件族
- 不把医考行业动态展开成大段硬编码文案
- 不在 prompt 里塞整份 history

- [ ] **Step 6: 重新运行报表洞察与 API 测试，确认通过**

Run:

```bash
cd backend && python -m pytest tests/test_insight.py tests/test_main.py -v
```

Expected:
- PASS
- `/api/insight/stream` 仍返回 SSE
- `stream_insight()` 状态流仍是 `querying -> analyzing -> generating`

- [ ] **Step 7: 提交报表洞察检查点**

```bash
git add backend/services/insight.py backend/prompts/insight.txt backend/tests/test_insight.py backend/tests/test_main.py
git commit -m "feat: align report insight with shared analysis context"
```

---

### Task 4: 跑完整回归并做本地手工验证

**Files:**
- Verify: `backend/tests/test_insight_context.py`
- Verify: `backend/tests/test_insight.py`
- Verify: `backend/tests/test_chat.py`
- Verify: `backend/tests/test_chat_stream.py`
- Verify: `backend/tests/test_dataset_router.py`
- Verify: `backend/tests/test_main.py`
- Verify: `backend/tests/test_report.py`
- Verify: `frontend/src/api.test.ts`
- Verify: `frontend/src/pages/chatMessageUtils.test.ts`
- Verify: `frontend/src/components/ChatBubble.test.tsx`

- [ ] **Step 1: 运行完整后端目标测试集**

Run:

```bash
cd backend && python -m pytest tests/test_insight_context.py tests/test_insight.py tests/test_chat.py tests/test_chat_stream.py tests/test_dataset_router.py tests/test_main.py tests/test_report.py -v
```

Expected:
- PASS
- 无 SSE 协议回归
- 无追问口径回归
- 无报表工具函数回归

- [ ] **Step 2: 运行前端回归测试，确认接口消费未受影响**

Run:

```bash
npm --prefix frontend test
```

Expected:
- PASS
- 允许保留当前已有的 jsdom pseudo-element 提示，但不能新增失败

- [ ] **Step 3: 启动本地后端与前端，做手工冒烟**

后端：

```bash
python -m uvicorn main:app --app-dir backend --reload --port 8230
```

前端：

```bash
npm --prefix frontend run dev -- --host 0.0.0.0
```

手工验证清单：
- 聊天页普通查数：例如“上月销售总额”
- 聊天页追问：例如“环比呢”“退款类呢”“按周分别多少”
- 报表页月报 / 周报 / 区间洞察
- 表格 / 图表先展示，AI 洞察继续异步生成
- 单值查询不会硬写泛化建议
- 有环比/同比时能输出趋势或异常判断

- [ ] **Step 4: 记录结果并在失败时先收敛根因，再补最小修复**

记录至少包括：
- 哪些自动化测试通过
- 哪个手工场景验证通过
- 是否出现错误建议、乱猜考季、SSE 卡住、前端消费异常

若失败，先定位属于哪一层：
- 上下文构造错误
- chat 总结 prompt 约束错误
- report 洞察 prompt 注入错误
- SSE / 接口兼容问题

不要在这个阶段扩展新需求。

- [ ] **Step 5: 提交最终实现检查点**

```bash
git add backend/services/insight_context.py backend/services/chat.py backend/services/insight.py backend/prompts/insight.txt backend/tests/test_insight_context.py backend/tests/test_insight.py backend/tests/test_chat.py backend/tests/test_main.py
git commit -m "feat: improve insight analysis context and intent modeling"
```

---

## 验证清单

- [ ] 共享上下文模块已创建，并同时服务 chat / report
- [ ] 聊天总结与报表洞察使用统一分析骨架
- [ ] 低证据只报核心数据，不编造趋势或泛化建议
- [ ] 高证据场景可输出趋势 / 异常 / 动作建议
- [ ] 无法识别考试类型或考季阶段时，不会自行猜测
- [ ] 追问口径继承逻辑保持可用
- [ ] `/api/chat/stream` SSE 事件结构不变
- [ ] `/api/insight/stream` SSE 事件结构已被测试锁定
- [ ] 快速路由与报表聚合未被本次优化带坏
- [ ] 前端异步展示体验保持不变

---

## 范围守卫

执行时不要做以下事情：

- 不重写 `dataset_router.py` 主路由
- 不重构 `report.py` 聚合逻辑
- 不引入数据库表、知识库、复杂规则引擎
- 不新增第二套聊天/报表协议
- 不顺手做 UI 改版
- 不部署上线
- 不修改与本次目标无关的前端组件

---

## 失败处理

如果实现后出现“洞察更聪明但链路不稳定”，按这个顺序排查：

1. 先看 `backend/tests/test_chat_stream.py` 和 `backend/tests/test_main.py` 是否回归，确认不是 SSE / 路由协议被破坏
2. 再看 `backend/tests/test_insight_context.py`，确认意图标签、证据等级、考季阶段是否被错误判定
3. 再看 `backend/tests/test_chat.py` / `backend/tests/test_insight.py`，确认 prompt 注入位置和约束文本是否生效
4. 如果只有文案质量不理想，优先微调 `context_text` 与 prompt 规则，不要回头重做查数链路
5. 如果手工验证发现某类问题无法稳定分类，先回退为更保守的 `value_only` / `low evidence` 输出，而不是扩展新规则系统
