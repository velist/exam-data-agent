# 月报默认月份与缓存重建 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 让月报在每月 1-14 日默认展示上月，并在实际服务环境中清理/重建三层缓存，确保重建结果只来自当前 `dws` 逻辑。

**Architecture:** 将“月报默认月份”提取为一个可单测的纯函数，再由 `Report.tsx` 消费，避免把日期规则散落在页面内部。缓存部分不改架构，只在目标运行环境执行一次明确的清理 → 预热 → 导出 → 校验流程，并把运行期产物排除在提交之外。

**Tech Stack:** React 19 / TypeScript / Dayjs / Vitest / FastAPI / Python / JSON cache files / curl

---

## File Map

| 路径 | 动作 | 责任 |
|------|------|------|
| `frontend/src/pages/reportDateUtils.ts` | Create | 纯函数：根据当前日期计算月报默认月份 |
| `frontend/src/pages/reportDateUtils.test.ts` | Create | 默认月份规则单元测试（1-14 日、15 日、跨年） |
| `frontend/src/pages/Report.test.tsx` | Create | 页面级集成测试，锁定 `/report?type=monthly` 首次加载时实际请求的月份 |
| `frontend/src/pages/Report.tsx:65-68` | Modify | 用 helper 替换 `month` 的“固定当前月”初始化 |
| `backend/services/report_cache.py` | Verify only | 确认报表缓存预热表仍全部来自 `dws` |
| `backend/services/query_cache.py` | Verify only | 确认查询缓存写入路径与重建后校验方式 |
| `scripts/export_cache.py` | Verify only | 用于把 `query_cache` 导出到 `frontend/public/cache/` |

## Preconditions

- 本计划默认执行根目录是 `D:\文档\文档\公司\NLP\Claude-agent-design\exam-data-agent`；下面的 `cd frontend`、`cd backend`、`python scripts/export_cache.py` 都以此为前提。
- 在**实际需要清理缓存的环境**执行 Task 3；不要只在无关的本地副本里重建。
- Task 3 必须在**隔离实例、无并发外部流量的端口，或明确维护窗口**执行；否则 `query_cache` 与静态导出校验会被其他请求污染，导致非确定性结果。
- 当前后端读取的是仓库根目录 `.env`（见 `backend/config.py`），不是 `backend/.env`。
- 不要提交 `backend/data/query_cache/`、`frontend/public/cache/`、`backend/data/report_cache.json` 这类运行期产物。
- 如果 Task 3 的运行结果与 spec 明显不一致，先回到 `@superpowers:systematic-debugging`，不要边猜边改。

---

### Task 1: 提取月报默认月份纯函数

**Files:**
- Create: `frontend/src/pages/reportDateUtils.ts`
- Test: `frontend/src/pages/reportDateUtils.test.ts`

- [ ] **Step 1: 写失败的纯函数测试**

```ts
import { describe, expect, it } from "vitest";
import dayjs from "dayjs";
import { getDefaultMonthlyReportMonth } from "./reportDateUtils";

describe("getDefaultMonthlyReportMonth", () => {
  it("returns previous month before the 15th", () => {
    expect(getDefaultMonthlyReportMonth(dayjs("2026-04-02"))).toBe("2026-03");
  });

  it("returns current month on the 15th", () => {
    expect(getDefaultMonthlyReportMonth(dayjs("2026-04-15"))).toBe("2026-04");
  });

  it("handles January rollover", () => {
    expect(getDefaultMonthlyReportMonth(dayjs("2026-01-01"))).toBe("2025-12");
  });
});
```

- [ ] **Step 2: 运行测试并确认失败**

Run: `cd frontend && npx vitest run src/pages/reportDateUtils.test.ts`

Expected: FAIL，提示 `Cannot find module './reportDateUtils'` 或 `getDefaultMonthlyReportMonth is not defined`。

- [ ] **Step 3: 写最小实现**

```ts
import dayjs, { type Dayjs } from "dayjs";

export function getDefaultMonthlyReportMonth(now: Dayjs = dayjs()): string {
  const target = now.date() < 15 ? now.subtract(1, "month") : now;
  return target.format("YYYY-MM");
}
```

- [ ] **Step 4: 重新运行测试并确认通过**

Run: `cd frontend && npx vitest run src/pages/reportDateUtils.test.ts`

Expected: PASS，3 个用例全部通过。

- [ ] **Step 5: 提交 helper 与测试**

```bash
git add frontend/src/pages/reportDateUtils.ts frontend/src/pages/reportDateUtils.test.ts
git commit -m "fix: extract monthly report default month rule"
```

---

### Task 2: 把默认月份规则接入 Report 页面

**Files:**
- Create: `frontend/src/pages/Report.test.tsx`
- Modify: `frontend/src/pages/Report.tsx:65-68`
- Test: `frontend/src/pages/Report.test.tsx`

- [ ] **Step 1: 写页面级失败测试，锁定月报入口默认请求月份**

```tsx
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { render, waitFor } from "@testing-library/react";
import Report from "./Report";
import * as api from "../api";

vi.mock("../components/InsightText", () => ({
  default: () => <div data-testid="insight-text" />,
}));

vi.mock("../api", async () => {
  const actual = await vi.importActual<typeof import("../api")>("../api");
  return {
    ...actual,
    getWeeklyReport: vi.fn(),
    getMonthlyReport: vi.fn(),
    getRangeReport: vi.fn(),
  };
});

const sampleReport = { period: { month: "2026-03", weeks: 4 }, sections: {} };

describe("Report monthly defaults", () => {
  beforeEach(() => {
    vi.useFakeTimers();
    vi.setSystemTime(new Date("2026-04-02T10:00:00Z"));
    vi.mocked(api.getMonthlyReport).mockResolvedValue(sampleReport as never);
    vi.mocked(api.getWeeklyReport).mockResolvedValue({ period: {}, sections: {} } as never);
    vi.mocked(api.getRangeReport).mockResolvedValue({ period: {}, sections: {} } as never);
  });

  afterEach(() => {
    vi.useRealTimers();
    vi.clearAllMocks();
  });

  it("loads previous month before mid-month", async () => {
    render(
      <MemoryRouter initialEntries={["/report?type=monthly"]}>
        <Routes>
          <Route path="/report" element={<Report />} />
        </Routes>
      </MemoryRouter>,
    );

    await waitFor(() => {
      expect(api.getMonthlyReport).toHaveBeenCalledWith("2026-03");
    });
  });
});
```

- [ ] **Step 2: 运行测试并确认失败**

Run: `cd frontend && npx vitest run src/pages/Report.test.tsx`

Expected: FAIL，断言显示当前调用参数仍是 `2026-04`。

- [ ] **Step 3: 用 helper 替换 Report 页面初始月**

在 `frontend/src/pages/Report.tsx`：
- 引入 `getDefaultMonthlyReportMonth`
- 把 `const [month, setMonth] = useState(dayjs().format("YYYY-MM"));` 改成 helper 结果
- 保持周报、区间报表、手动切换月份逻辑不变

最小目标代码：

```tsx
import { getDefaultMonthlyReportMonth } from "./reportDateUtils";

const [month, setMonth] = useState(getDefaultMonthlyReportMonth());
```

- [ ] **Step 4: 运行页面级与 helper 测试**

Run: `cd frontend && npx vitest run src/pages/reportDateUtils.test.ts src/pages/Report.test.tsx`

Expected: PASS。

- [ ] **Step 5: 运行完整前端测试和构建**

Run: `cd frontend && npm test && npm run build`

Expected: 全量前端测试通过，构建成功。

- [ ] **Step 6: 提交页面改动**

```bash
git add frontend/src/pages/Report.tsx frontend/src/pages/Report.test.tsx
git commit -m "fix: default monthly report to previous month before mid-month"
```

---

### Task 3: 在目标环境清理并重建三层缓存

**Files:**
- Verify only: `backend/services/report_cache.py`
- Verify only: `backend/services/query_cache.py`
- Verify only: `scripts/export_cache.py`

- [ ] **Step 1: 先确认报表缓存预热 SQL 仍全部来自 dws**

Run:

```bash
python - <<'PY'
import re
from pathlib import Path
text = Path("backend/services/report_cache.py").read_text(encoding="utf-8")
queries = re.findall(r'"(SELECT \* FROM [^"]+)"', text)
assert queries, "No preload queries found"
for sql in queries:
    assert "FROM dws." in sql, sql
print("OK: report cache preload queries are dws-only")
PY
```

Expected: 输出 `OK: report cache preload queries are dws-only`。

- [ ] **Step 2: 清理旧缓存**

Run:

```bash
rm -f backend/data/report_cache.json
rm -rf backend/data/query_cache
rm -rf frontend/public/cache
```

Expected: 三层旧缓存被移除；目录不存在也不算失败。

- [ ] **Step 3: 启动后端服务，让报表缓存重新预热**

在**单独终端**或后台任务中运行，避免阻塞后续预热命令。

Run:

```bash
cd backend && python -m uvicorn main:app --host 127.0.0.1 --port 8230
```

Expected: 服务启动成功；日志中出现 `report_cache` 读取/刷新信息；当前终端保持占用，后续 Step 3-7 在另一个终端执行。

- [ ] **Step 4: 预热最小报表缓存集合并校验 HTTP 200**

Run:

```bash
python - <<'PY'
import urllib.request
urls = [
    "http://127.0.0.1:8230/api/report/weekly?date=2026-03-27",
    "http://127.0.0.1:8230/api/report/monthly?month=2026-03",
    "http://127.0.0.1:8230/api/report/range?start=2026-03-01&end=2026-03-31",
]
for url in urls:
    with urllib.request.urlopen(url) as resp:
        print(resp.status, url)
PY
```

Expected: 三行输出都以 `200` 开头，且 `backend/data/report_cache.json` 重新出现。

- [ ] **Step 5: 预热最小查询缓存集合并校验缓存样本内容**

Run:

```bash
python - <<'PY'
import json, urllib.request
from pathlib import Path
req = urllib.request.Request(
    "http://127.0.0.1:8230/api/chat",
    data=json.dumps({"message": "3月各班次类型销量和销售额", "history": []}).encode("utf-8"),
    headers={"Content-Type": "application/json"},
)
with urllib.request.urlopen(req) as resp:
    print(resp.status)
cache_files = sorted(Path("backend/data/query_cache").glob("*.json"), key=lambda p: p.stat().st_mtime, reverse=True)
assert cache_files, "No query cache files created"
latest = json.loads(cache_files[0].read_text(encoding="utf-8"))
print(latest["sql"])
assert "dws.dws_v_salesflow_dateil" in latest["sql"], latest["sql"]
PY
```

Expected: 先输出 `200`，再输出一条包含 `dws.dws_v_salesflow_dateil` 的 SQL；这说明基线问题确实生成了预期查询缓存样本。

- [ ] **Step 6: 导出静态缓存**

Run: `python scripts/export_cache.py`

Expected: 输出 `已导出 N 个缓存文件到 frontend/public/cache`，并生成 `frontend/public/cache/index.json`。

- [ ] **Step 7: 校验缓存中不再含有 bigdata 痕迹**

Run:

```bash
python - <<'PY'
from pathlib import Path
paths = [Path("backend/data/report_cache.json")]
paths += list(Path("backend/data/query_cache").glob("*.json"))
paths += list(Path("frontend/public/cache").glob("*.json"))
violations = [str(path) for path in paths if path.exists() and "bigdata." in path.read_text(encoding="utf-8")]
if violations:
    raise SystemExit(f"Unexpected bigdata references: {violations}")
print("OK: no bigdata references")
PY
```

Expected: 输出 `OK: no bigdata references`。

- [ ] **Step 8: 停掉本地后端（如果是本地重建）并检查工作区**

Run: `git status --short`

Expected: 运行期缓存产物很可能仍会出现在工作区，尤其是已跟踪的 `backend/data/report_cache.json`；实现者必须明确**不要 stage/commit** `backend/data/query_cache/`、`frontend/public/cache/`、`backend/data/report_cache.json` 这类运行期文件。

如果需要在提交前把工作区恢复到“只剩代码变更”，先执行清理/还原，再重新检查：

```bash
rm -rf backend/data/query_cache frontend/public/cache
# 对已跟踪文件，按当前分支状态恢复
 git checkout -- backend/data/report_cache.json
 git status --short
```

---

### Task 4: 最终验证与交接

**Files:**
- Verify only: `frontend/src/pages/Report.tsx`
- Verify only: `frontend/src/pages/reportDateUtils.ts`
- Verify only: `backend/data/report_cache.json`
- Verify only: `frontend/public/cache/index.json`

- [ ] **Step 1: 回归默认月份逻辑**

Run: `cd frontend && npx vitest run src/pages/reportDateUtils.test.ts src/pages/Report.test.tsx`

Expected: PASS；覆盖 1-14 日、15 日、跨年以及 `/report?type=monthly` 页面接线。

- [ ] **Step 2: 回归现有后端报表测试**

Run: `cd backend && python -m pytest tests/test_report.py tests/test_main.py -q`

Expected: PASS；报表路由与 FastAPI 入口不回退。

- [ ] **Step 3: 记录缓存重建结果**

检查项：
- `backend/data/report_cache.json` 已重建
- `backend/data/query_cache/` 有新的查询缓存样本
- `frontend/public/cache/index.json` 已生成
- 校验脚本确认无 `bigdata.`
- `frontend/public/cache/index.json` 中的 key/数量与 `backend/data/query_cache/` 导出的样本相符

建议校验：

```bash
python - <<'PY'
import json
from pathlib import Path
query_keys = sorted(p.stem for p in Path("backend/data/query_cache").glob("*.json"))
index = json.loads(Path("frontend/public/cache/index.json").read_text(encoding="utf-8"))
index_keys = sorted(item["key"] for item in index)
print(len(query_keys), len(index_keys))
assert query_keys == index_keys, "cache export index does not match query_cache files"
PY
```

- [ ] **Step 4: 完成前使用 @superpowers:verification-before-completion**

目标：再次确认测试、构建、缓存校验结果都已真实执行，不靠口头判断。
