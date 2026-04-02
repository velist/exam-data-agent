# 项目基础指南 — 考试宝典数据助手

基于自然语言查询的数据分析 Agent，支持对话查数、追问、周报/月报生成与 AI 洞察。

## 快速启动

```bash
# 一键启动（构建前端 + 启动服务）
start.bat

# 或手动
cd frontend && npm run build && cd ../backend && python -m uvicorn main:app --port 8000
```

访问 `http://localhost:8000`

## 环境要求

- Python 3.12+、Node.js 20+
- MySQL（阿里云 AnalyticDB）
- 阿里百炼千问 API

后端依赖：`cd backend && pip install -r requirements.txt`
前端依赖：`cd frontend && npm install`

配置文件 `backend/.env`：

```env
DB_HOST=<host>
DB_PORT=3306
DB_USER=<user>
DB_PASSWORD=<password>
DB_NAME=dws
QWEN_API_KEY=<key>
QWEN_BASE_URL=https://dashscope.aliyuncs.com/compatible-mode/v1
QWEN_MODEL=qwen-plus
```

## 架构

```
frontend/dist (React SPA)
     ↓ 静态文件挂载
FastAPI (port 8000)
 ├── POST /api/chat          同步聊天
 ├── POST /api/chat/stream   流式聊天 (SSE)
 ├── GET  /api/report/weekly  周报数据
 ├── GET  /api/report/monthly 月报数据
 ├── GET  /api/insight/stream 洞察流式生成
 └── GET  /*                  SPA fallback
```

前后端合并为单进程，FastAPI 同时 serve API 和前端静态文件。

## 核心功能

### 1. 对话查数

用户用自然语言提问，后端通过千问 LLM 生成 SQL，查库返回表格 + 文本总结。

**链路：** 用户输入 → 意图识别 → NL2SQL → SQL 校验/修复 → 执行 → 总结

**关键文件：**
- `backend/services/chat.py` — 聊天主链路，所有阶段函数的单一事实来源
- `backend/prompts/nl2sql.txt` — NL2SQL 系统提示词（含表结构、示例）
- `backend/sql_validator.py` — SQL 安全校验（白名单表 + 危险函数黑名单 + 递归子查询检查）

### 2. 追问口径继承

"环比呢""退款类呢""按周分别多少" 等追问会自动继承上轮的时间范围、统计对象和筛选条件。

**实现方式：**
- `_is_follow_up_question()` — 通过关键词 + 短句模式检测追问
- `_rewrite_follow_up_message()` — 把模糊追问改写为显式约束请求
- `_build_follow_up_scope_prompt()` — 注入系统提示，禁止 LLM 擅改口径

### 3. 流式聊天

SSE 事件流，前端先看到状态提示，再看到表格，最后逐步追加文本。

**事件顺序：**
```
status(understanding) → status(generating_sql) → status(querying)
→ table → status(summarizing) → answer_chunk × N → done
```

**关键设计：**
- `backend/services/chat_stream.py` — SSE 事件编排，复用 chat.py 共享函数
- `frontend/src/api.ts` 的 `streamChat()` — fetch + ReadableStream 解析 SSE
- `frontend/src/pages/chatMessageUtils.ts` — history 快照只保留已完成的 user+assistant 配对，不让 UI 中间态污染后端上下文
- 占位消息用稳定 ID 定位（非数组下标），防止并发提问串改
- 首帧前失败自动降级同步接口，首帧后失败保留已有内容

### 4. 周报/月报

固定模板报告，5 个板块：用户增长、活跃、付费转化、留存、行为。

**关键文件：**
- `backend/services/report.py` — 报告数据组装
- `backend/services/report_cache.py` — 启动时缓存全部 dws 表到内存
- `backend/services/insight.py` — 基于报告数据调 LLM 流式生成洞察

### 5. 组件样式系统

前端聊天气泡支持丰富的数据展示组件：

| 组件 | 说明 | 文件 |
|------|------|------|
| 数据表格 | Ant Design Table + 数字高亮 + 交替行 + 趋势指标 | `ChatBubble.tsx` |
| 对话图表 | 基于 ECharts 的多系列图表，支持 tooltip / legend / XLSX 下载 | `ChatChart.tsx` |
| 洞察文本 | 数字自动蓝色高亮，行高 1.8 可读排版 | `ChatBubble.tsx` |

样式参考：`考宝1.2-组件预览.html`，设计规范：`考宝1.2-设计规范.md`

## 数据缓存策略

### 查询结果缓存（1 年有效期）

后端查询结果按 SQL 哈希缓存为 JSON 文件，避免重复查库：

```
backend/data/query_cache/{sha256_16}.json
格式: { "ts": timestamp, "sql": "...", "result": { "columns": [...], "rows": [...] } }
```

**规则：**
- 含时间关键词（`本周`/`今天`/`CURDATE`等）的查询不缓存
- 有效期 1 年，过期自动清理
- 缓存文件：`backend/services/query_cache.py`

### 静态部署缓存同步

将缓存导出到前端静态目录，供 CF Pages 纯前端部署使用：

```bash
python scripts/export_cache.py
# → frontend/public/cache/*.json + index.json
```

前端在静态模式下（无后端）自动从 `/cache/` 读取预生成数据。

## 部署

### 本地开发

```bash
start.bat   # 构建前端 + 启动 FastAPI (localhost:8000)
```

### Cloudflare Pages（纯静态部署）

适用场景：不需要实时后端，数据通过缓存 JSON 预生成。

**步骤：**

1. 本地运行后端，执行常用查询积累缓存
2. 导出缓存：`python scripts/export_cache.py`
3. 推送到 GitHub
4. 在 CF Pages Dashboard 连接 GitHub 仓库
   - 构建命令：`cd frontend && npm install && npm run build`
   - 输出目录：`frontend/dist`
5. 自动部署，缓存 JSON 作为静态资源一并发布

**环境切换：**
- 开发模式（有后端）：直接访问 API，实时查库
- 静态模式（CF Pages）：从 `/cache/` 读取预生成 JSON，未缓存的查询提示"数据暂未收录"

**配置文件：** `wrangler.toml`

### Docker + VPS（完整功能部署）

如需实时查库功能，可通过 Docker 部署完整后端：

```bash
docker build -t kaobao-agent .
docker run -p 8230:8230 --env-file backend/.env kaobao-agent
```

## 数据库表

| 表 | 用途 | 关键字段 |
|----|------|----------|
| `dws.dws_user_daily_quiz_stats_day` | 日粒度用户数据 | stat_date, daily_register_count, daily_active_count |
| `dws.dws_active_user_report_week` | 周活跃 | reg_users, active_users, valid_active_users, *_yoy |
| `dws.dws_pay_user_report_week` | 周付费 | pay_users, pay_conv_rate, repurchase_rate, arpu |
| `dws.dws_retention_user_report_week` | 周留存 | n1_ret_rate, w_ret_rate |
| `dws.dws_user_behavior_report_week` | 周行为 | quiz_part_rate, mock_part_rate, course_part_rate |
| `dws.dws_v_salesflow_dateil` | 销售流水 | 售价, 销售日期, 销售部门名称 |
| `dws.dws_customer_service` | 客服进线 | question_type, question_theme, submit_time |

业务周定义：周六 ~ 周五。

## 测试

```bash
# 后端（26 个测试）
cd backend && python -m pytest tests/ -q

# 前端（19 个测试）
cd frontend && npm test
```

覆盖范围：follow-up 意图识别、SQL 修复重试、流式事件顺序、done/error 互斥、总结兜底、history 快照隔离、ChatBubble 渲染顺序、SSE 解析、中断检测。

## 项目结构

```
exam-data-agent/
├── start.bat                    # 一键启动
├── wrangler.toml                # CF Pages 部署配置
├── scripts/
│   └── export_cache.py          # 缓存导出到前端静态目录
├── backend/
│   ├── main.py                  # FastAPI 入口 + 静态文件挂载
│   ├── config.py                # 环境变量
│   ├── db.py                    # SQLAlchemy 连接池
│   ├── sql_validator.py         # SQL 安全校验
│   ├── services/
│   │   ├── chat.py              # 聊天主链路（共享阶段函数）
│   │   ├── chat_stream.py       # SSE 事件编排
│   │   ├── query_cache.py       # SQL 查询结果缓存（1年JSON）
│   │   ├── report.py            # 周报/月报组装
│   │   ├── report_cache.py      # 报告数据缓存
│   │   └── insight.py           # AI 洞察流式生成
│   ├── prompts/                 # LLM 提示词
│   ├── data/
│   │   ├── report_cache.json    # 报告磁盘缓存
│   │   └── query_cache/         # 查询结果缓存目录
│   └── tests/                   # pytest 测试
└── frontend/
    ├── src/
    │   ├── api.ts               # API 层（sendChat/streamChat/静态缓存）
    │   ├── pages/
    │   │   ├── Chat.tsx         # 聊天页（落地屏 + 聊天屏）
    │   │   ├── Report.tsx       # 报告页
    │   │   └── chatMessageUtils.ts  # 消息状态纯函数
    │   ├── components/
    │   │   ├── ChatBubble.tsx   # 聊天气泡（表格+图表+洞察）
    │   │   ├── ChatChart.tsx    # ECharts 对话图表（多系列/tooltip/legend/导出）
    │   │   ├── MetricCard.tsx   # KPI 卡片
    │   │   ├── TrendChart.tsx   # 趋势图
    │   │   └── InsightText.tsx  # AI 洞察
    │   └── styles/
    │       └── chat.css         # 聊天页完整样式
    ├── public/cache/            # 导出的静态缓存（CF Pages 用）
    └── dist/                    # 构建产物（被 FastAPI 挂载）
```
