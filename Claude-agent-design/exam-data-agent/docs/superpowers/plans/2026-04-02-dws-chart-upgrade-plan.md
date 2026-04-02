# dws 数据源精简 + 对话页图表升级 + mini 区域隐藏 实施计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 将数据源精简为仅 dws 库（含新销售表），将对话页 Canvas 图表升级为 ECharts 交互式图表并添加 XLSX 下载，隐藏对话模式下的 mini 球形区域。

**Architecture:** 后端移除 bigdata 白名单和提示词引用，新增 dws 销售表；前端新建 ChatChart 组件替换 SimpleChart，使用 SheetJS 实现客户端 XLSX 导出，条件渲染 mini 球形区域。

**Tech Stack:** Python/FastAPI, React 19, TypeScript, ECharts 6, echarts-for-react, xlsx (SheetJS), Ant Design 6

**Spec:** `docs/superpowers/specs/2026-04-02-dws-only-and-chart-upgrade-design.md`

---

## File Structure

### 后端修改
| 文件 | 操作 | 职责 |
|------|------|------|
| `backend/config.py:23-34` | 修改 | 移除 bigdata 表，新增 dws 销售表 |
| `backend/prompts/nl2sql.txt` | 修改 | 移除 bigdata 描述/示例，添加新销售表描述，添加引导规则 |
| `backend/services/chat.py:248-251` | 修改 | 修复提示词移除 bigdata 引用 |
| `backend/tests/test_sql_validator.py:40-44` | 修改 | bigdata 测试改为拦截断言，新增 dws 销售表通过断言 |

### 前端新增
| 文件 | 操作 | 职责 |
|------|------|------|
| `frontend/src/components/ChatChart.tsx` | 新建 | ECharts 交互式图表（折线+柱状），用于对话气泡 |

### 前端修改
| 文件 | 操作 | 职责 |
|------|------|------|
| `frontend/src/components/ChatBubble.tsx` | 修改 | 替换 SimpleChart 为 ChatChart，升级 extractChartData 为多系列，添加下载按钮 |
| `frontend/src/pages/Chat.tsx:307-314` | 修改 | 条件渲染 vh-section-mini |
| `frontend/src/styles/chat.css` | 修改 | 可能的布局间距调整 |

### 前端删除
| 文件 | 操作 | 职责 |
|------|------|------|
| `frontend/src/components/SimpleChart.tsx` | 删除 | 被 ChatChart 替代，仅 ChatBubble 引用 |

### 依赖
| 包 | 操作 |
|----|------|
| `xlsx` | npm install（前端新增依赖） |

---

## Task 1: 移除 bigdata 白名单 + 新增 dws 销售表

**Files:**
- Modify: `backend/config.py:23-34`
- Modify: `backend/tests/test_sql_validator.py:40-44`

- [ ] **Step 1: 更新 test_sql_validator.py — 将 bigdata 测试改为拦截断言，新增 dws 销售表测试**

```python
# 替换第 40-44 行
def test_reject_bigdata_sales():
    """bigdata 表已移除，应被拦截"""
    assert validate_sql("SELECT sum(售价) FROM bigdata.v_ws_salesflow_ex WHERE 销售部门名称='APP直充'") is False

def test_reject_bigdata_other():
    assert validate_sql("SELECT * FROM bigdata.some_table") is False

def test_allow_dws_salesflow():
    """新增的 dws 销售流水表应通过"""
    assert validate_sql("SELECT * FROM dws.dws_v_salesflow_dateil WHERE 销售日期 >= '2026-01-01'") is True
```

- [ ] **Step 2: 运行测试验证失败（bigdata 测试应失败因为白名单还没改）**

Run: `cd backend && python -m pytest tests/test_sql_validator.py::test_reject_bigdata_sales tests/test_sql_validator.py::test_allow_dws_salesflow -v`
Expected: `test_reject_bigdata_sales` FAIL（当前 bigdata 还在白名单中）

- [ ] **Step 3: 修改 config.py 白名单**

将 `backend/config.py` 第 23-34 行替换为：

```python
ALLOWED_TABLES = [
    "dws.dws_user_daily_quiz_stats_day",
    "dws.dws_active_user_report_week",
    "dws.dws_pay_user_report_week",
    "dws.dws_retention_user_report_week",
    "dws.dws_user_behavior_report_week",
    "dws.dws_customer_service",
    "dws.dws_v_salesflow_dateil",
]
```

- [ ] **Step 4: 运行全部 validator 测试**

Run: `cd backend && python -m pytest tests/test_sql_validator.py -v`
Expected: 全部 PASS

- [ ] **Step 5: Commit**

```bash
git add backend/config.py backend/tests/test_sql_validator.py
git commit -m "feat: 移除 bigdata 白名单，新增 dws_v_salesflow_dateil"
```

---

## Task 2: 清理 chat.py 修复提示词

**Files:**
- Modify: `backend/services/chat.py:248-251`

- [ ] **Step 1: 修改 SQL 修复提示词**

将 `backend/services/chat.py` 第 248-251 行替换为：

```python
    fix_messages = _build_llm_messages(
        message,
        history,
        "上一次生成的SQL不合规。请重新生成一条安全的SELECT查询。只使用dws库中的表。只输出SQL，不要解释。",
    )
```

- [ ] **Step 2: 运行全部后端测试**

Run: `cd backend && python -m pytest tests/ -v`
Expected: 全部 PASS

- [ ] **Step 3: Commit**

```bash
git add backend/services/chat.py
git commit -m "fix: SQL 修复提示词移除 bigdata 表名硬编码"
```

---

## Task 3: 清理 NL2SQL 提示词

**Files:**
- Modify: `backend/prompts/nl2sql.txt`

- [ ] **Step 1: 查询 dws.dws_v_salesflow_dateil 表结构**

连接数据库查表结构（需要 .env 配置）：

```bash
cd backend && python -c "
from db import engine
from sqlalchemy import text
with engine.connect() as conn:
    rows = conn.execute(text('DESCRIBE dws.dws_v_salesflow_dateil')).fetchall()
    for r in rows:
        print(r)
"
```

记录字段名和类型，用于下一步编写表结构描述。

- [ ] **Step 2: 修改 nl2sql.txt 意图分类**

在提示词的意图分类区域（约第 7-15 行）：
- 移除"销售收入"指向 bigdata 的映射，改为指向 `dws.dws_v_salesflow_dateil`
- 移除"业绩统计"指向 bigdata 的映射，改为指向 `dws.dws_v_salesflow_dateil` + `dws_pay_user_report_week`
- 移除"用户画像"指向 bigdata 的映射（用户画像降级到 dws 活跃/注册表）
- 移除"用户行为埋点"指向 bigdata 的映射（直接删除）

- [ ] **Step 3: 删除 bigdata 表结构描述**

删除以下区块（约第 90-142 行之间的 bigdata 相关内容）：
- `bigdata.v_ws_salesflow_ex` 结构描述
- `bigdata.v_ksb_users_ex` 结构描述（含渠道判断正则）
- `bigdata.v_ws_vnsalesrank` 结构描述
- `bigdata.v_ksb_userclick` 结构描述

- [ ] **Step 4: 添加新 dws 销售表结构描述**

在 dws 表描述区域末尾，根据 Step 1 查到的字段，添加：

```
### dws.dws_v_salesflow_dateil（销售流水明细 — 清洗后视图）
- [根据实际字段填写]
```

- [ ] **Step 5: 删除 bigdata SQL 示例**

删除所有引用 bigdata 表的 SQL 示例（约第 161、203、206、209、212、215、218、221、224 行）。

- [ ] **Step 6: 添加新销售表 SQL 示例**

根据新表字段，添加 2-3 个使用 `dws.dws_v_salesflow_dateil` 的示例查询。

- [ ] **Step 7: 添加引导规则**

在提示词末尾（示例之后）添加：

```
## 数据范围限制
当前系统仅支持 dws 库中的数据表。如果用户的问题涉及以下不支持的领域，请用现有数据表尽量回答，无法回答时输出：
-- NO_DATA_AVAILABLE
该数据暂不在系统支持范围内，目前可查询的数据包括：用户增长、活跃、付费转化、留存、学习行为、客服进线和销售流水。

不支持的领域：
- 用户画像（省份、渠道、职称等维度）
- 页面点击埋点（按钮点击、页面访问等）
```

- [ ] **Step 8: 运行全部后端测试**

Run: `cd backend && python -m pytest tests/ -v`
Expected: 全部 PASS

- [ ] **Step 9: Commit**

```bash
git add backend/prompts/nl2sql.txt
git commit -m "feat: NL2SQL 提示词迁移至纯 dws 数据源，新增销售流水表"
```

---

## Task 4: 安装 xlsx 依赖

**Files:**
- Modify: `frontend/package.json`

- [ ] **Step 1: 安装 xlsx**

Run: `cd frontend && npm install xlsx`

- [ ] **Step 2: 验证安装成功**

Run: `cd frontend && node -e "const XLSX = require('xlsx'); console.log('xlsx version:', XLSX.version)"`
Expected: 输出 xlsx 版本号

- [ ] **Step 3: Commit**

```bash
git add frontend/package.json frontend/package-lock.json
git commit -m "chore: 添加 xlsx (SheetJS) 依赖"
```

---

## Task 5: 创建 ChatChart 组件

**Files:**
- Create: `frontend/src/components/ChatChart.tsx`

- [ ] **Step 1: 创建 ChatChart.tsx**

```tsx
import ReactECharts from "echarts-for-react";

const COLORS = ["#00b4d8", "#66ffd1", "#0284c7", "#38bdf8", "#0f766e"];

interface ChatChartProps {
  type: "line" | "bar";
  labels: string[];
  series: { name: string; data: number[] }[];
}

export default function ChatChart({ type, labels, series }: ChatChartProps) {
  const option = {
    color: COLORS,
    tooltip: {
      trigger: "axis" as const,
      backgroundColor: "rgba(15, 23, 42, 0.88)",
      borderColor: "rgba(0, 180, 216, 0.3)",
      borderWidth: 1,
      textStyle: { color: "#e2e8f0", fontSize: 13 },
      appendToBody: true,
    },
    legend: {
      show: series.length > 1,
      bottom: 0,
      textStyle: { color: "#94a3b8", fontSize: 12 },
      icon: "circle",
      itemWidth: 8,
      itemHeight: 8,
    },
    grid: {
      left: "3%",
      right: "4%",
      top: 16,
      bottom: series.length > 1 ? "18%" : "8%",
      containLabel: true,
    },
    xAxis: {
      type: "category" as const,
      data: labels,
      axisLabel: { color: "#64748b", fontSize: 11, rotate: labels.length > 6 ? 30 : 0 },
      axisLine: { lineStyle: { color: "rgba(255,255,255,0.08)" } },
      boundaryGap: type === "bar",
    },
    yAxis: {
      type: "value" as const,
      splitLine: { lineStyle: { color: "rgba(255,255,255,0.06)" } },
      axisLabel: { color: "#64748b", fontSize: 11 },
    },
    series: series.map((s, i) => ({
      name: s.name,
      type,
      data: s.data,
      smooth: type === "line",
      symbol: "circle",
      symbolSize: 8,
      lineStyle: type === "line" ? { width: 3 } : undefined,
      itemStyle: type === "bar" ? { borderRadius: [4, 4, 0, 0] } : undefined,
      areaStyle:
        type === "line" && i === 0
          ? {
              color: {
                type: "linear",
                x: 0, y: 0, x2: 0, y2: 1,
                colorStops: [
                  { offset: 0, color: "rgba(0, 180, 216, 0.2)" },
                  { offset: 1, color: "rgba(0, 180, 216, 0)" },
                ],
              },
            }
          : undefined,
    })),
  };

  return (
    <ReactECharts
      option={option}
      style={{ height: 240, width: "100%" }}
      opts={{ renderer: "canvas" }}
    />
  );
}
```

- [ ] **Step 2: 验证 TypeScript 编译**

Run: `cd frontend && npx tsc --noEmit src/components/ChatChart.tsx 2>&1 | head -20`
Expected: 无错误或仅有可忽略的 isolatedModules 警告

- [ ] **Step 3: Commit**

```bash
git add frontend/src/components/ChatChart.tsx
git commit -m "feat: 新建 ChatChart 组件 — ECharts 交互式图表（折线+柱状）"
```

---

## Task 6: 改造 ChatBubble — 替换图表 + 添加下载

**Files:**
- Modify: `frontend/src/components/ChatBubble.tsx:3,52-67,72-75,117-119`

- [ ] **Step 1: 替换 import**

将第 3 行：
```tsx
import SimpleChart from "./SimpleChart";
```
替换为：
```tsx
import ChatChart from "./ChatChart";
import * as XLSX from "xlsx";
```

- [ ] **Step 2: 升级 extractChartData 函数为多系列**

将第 52-67 行的 `extractChartData` 替换为：

```tsx
function extractChartData(table: { columns: string[]; rows: string[][] }) {
  if (table.columns.length < 2 || table.rows.length < 2) return null;
  const series: { name: string; data: number[] }[] = [];
  for (let j = 1; j < table.columns.length; j++) {
    const allNumeric = table.rows.every((row) => isNumeric(row[j] || "0"));
    if (allNumeric) {
      series.push({
        name: table.columns[j],
        data: table.rows.map((r) => parseFloat((r[j] || "0").replace(/,/g, "").replace(/%/g, ""))),
      });
    }
  }
  if (series.length === 0) return null;
  const labels = table.rows.map((r) => r[0] || "");
  const isTimeSeries = labels.some((l) => /\d{4}[-/]\d{2}/.test(l));
  return { labels, series, type: (isTimeSeries ? "line" : "bar") as "line" | "bar" };
}
```

- [ ] **Step 3: 添加 XLSX 下载函数**

在 `extractChartData` 函数之后添加：

```tsx
function downloadXlsx(table: { columns: string[]; rows: string[][] }) {
  const wsData = [table.columns, ...table.rows];
  const ws = XLSX.utils.aoa_to_sheet(wsData);
  const wb = XLSX.utils.book_new();
  XLSX.utils.book_append_sheet(wb, ws, "数据");
  const now = new Date();
  const ts = `${now.getFullYear()}-${String(now.getMonth() + 1).padStart(2, "0")}-${String(now.getDate()).padStart(2, "0")}_${String(now.getHours()).padStart(2, "0")}-${String(now.getMinutes()).padStart(2, "0")}`;
  XLSX.writeFile(wb, `典宝数据_${ts}.xlsx`);
}
```

- [ ] **Step 4: 替换渲染区域 — 下载按钮 + ChatChart**

将第 117-119 行的 SimpleChart 渲染替换为：

```tsx
      {table && table.rows.length > 0 && (
        <div style={{ display: "flex", justifyContent: "flex-end", padding: "4px 0" }}>
          <button
            onClick={() => downloadXlsx(table)}
            style={{
              display: "inline-flex", alignItems: "center", gap: 6,
              padding: "5px 12px", background: "rgba(0,180,216,0.12)",
              color: "#00b4d8", border: "1px solid rgba(0,180,216,0.25)",
              borderRadius: 8, fontSize: 12, cursor: "pointer",
            }}
          >
            <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
              <path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4" />
              <polyline points="7 10 12 15 17 10" />
              <line x1="12" y1="15" x2="12" y2="3" />
            </svg>
            下载 XLSX
          </button>
        </div>
      )}
      {chartData && (
        <ChatChart type={chartData.type} labels={chartData.labels} series={chartData.series} />
      )}
```

- [ ] **Step 5: 验证 TypeScript 编译**

Run: `cd frontend && npx tsc --noEmit 2>&1 | head -30`
Expected: 无 ChatBubble 相关错误

- [ ] **Step 6: Commit**

```bash
git add frontend/src/components/ChatBubble.tsx
git commit -m "feat: 对话气泡图表升级为 ECharts + 多系列 + XLSX 下载"
```

---

## Task 7: 删除 SimpleChart

**Files:**
- Delete: `frontend/src/components/SimpleChart.tsx`

- [ ] **Step 1: 删除 SimpleChart.tsx**

```bash
rm frontend/src/components/SimpleChart.tsx
```

- [ ] **Step 2: 验证无编译错误**

Run: `cd frontend && npx tsc --noEmit 2>&1 | head -20`
Expected: 无 SimpleChart 相关错误

- [ ] **Step 3: Commit**

```bash
git add -u frontend/src/components/SimpleChart.tsx
git commit -m "chore: 删除 SimpleChart（已被 ChatChart 替代）"
```

---

## Task 8: 对话模式下隐藏 mini 球形区域

**Files:**
- Modify: `frontend/src/pages/Chat.tsx:307-314`

- [ ] **Step 1: 添加条件渲染**

将 `Chat.tsx` 第 307-314 行：

```tsx
        <section className="vh-section-mini">
          <div className="mini-sphere-wrap">
            <div ref={sphereRef}>
              <SmartSphere />
            </div>
            <div className="state-text">{STATE_TEXT_MAP[appState]}</div>
          </div>
        </section>
```

替换为：

```tsx
        {screen === "landing" && (
          <section className="vh-section-mini">
            <div className="mini-sphere-wrap">
              <div ref={sphereRef}>
                <SmartSphere />
              </div>
              <div className="state-text">{STATE_TEXT_MAP[appState]}</div>
            </div>
          </section>
        )}
```

- [ ] **Step 2: 验证 TypeScript 编译**

Run: `cd frontend && npx tsc --noEmit 2>&1 | head -20`
Expected: 无错误

- [ ] **Step 3: Commit**

```bash
git add frontend/src/pages/Chat.tsx
git commit -m "fix: 对话模式下隐藏 mini 球形区域，避免遮挡内容"
```

---

## Task 9: 构建验证 + 全量测试

**Files:** 无新增修改

- [ ] **Step 1: 运行全部后端测试**

Run: `cd backend && python -m pytest tests/ -v`
Expected: 全部 PASS

- [ ] **Step 2: 运行全部前端测试**

Run: `cd frontend && npm test`
Expected: 全部 PASS

- [ ] **Step 3: 前端生产构建**

Run: `cd frontend && npm run build`
Expected: 构建成功，无错误

- [ ] **Step 4: 如有测试失败，修复后提交**

```bash
git add -A
git commit -m "fix: 修复测试/构建问题"
```
