# 考试宝典数据助手 — 设计文档

## 1. 项目概述

### 1.1 产品定位
面向考试宝典管理层的数据查询Agent，通过自然语言交互查询业务数据，支持固定周报/月报生成及AI洞察分析。

### 1.2 目标用户
- **管理层**：不写SQL，需要简洁直观的数据结论和可视化图表

### 1.3 核心能力
1. **自然语言查数**：输入"上周新注册用户数"等自然语言，AI自动翻译为SQL执行并返回结果
2. **固定报告**：一键生成周报/月报，固定模板页面，自动填充数据和图表
3. **AI洞察**：千问模型自动生成数据解读和业务建议（流式文本输出）

### 1.4 技术约束
- 模型：阿里百炼千问（qwen-plus），通过OpenAI兼容接口调用
- 数据库：阿里云AnalyticDB MySQL
- 数据范围：已梳理的dws数据库为主 + 部分bigdata表
- 部署：内网，无需登录鉴权

---

## 2. 系统架构

```
┌──────────────────────────────────────────────────┐
│                 前端 (React)                       │
│    Ant Design 5 + ECharts + 响应式布局             │
│  ┌───────────┐  ┌──────────────────────────────┐  │
│  │  对话查询   │  │  报告页（独立页面，固定模板）  │  │
│  │  轻量回答   │  │  数据卡片+图表+AI文本洞察     │  │
│  └───────────┘  └──────────────────────────────┘  │
└─────────────────────┬────────────────────────────┘
                      │ HTTP API + SSE
┌─────────────────────┴────────────────────────────┐
│                后端 (FastAPI)                       │
│  ┌───────────┐ ┌───────────┐ ┌────────────────┐   │
│  │  对话服务   │ │  报告服务   │ │  洞察生成服务   │   │
│  │  NL→SQL   │ │  固定模板   │ │  千问AI分析    │   │
│  └─────┬─────┘ └─────┬─────┘ └──────┬─────────┘   │
│        └─────────────┴──────────────┘              │
│                      │                             │
│        ┌─────────────┴──────────────┐              │
│        │   数据库连接层 (SQLAlchemy)   │              │
│        └─────────────┬──────────────┘              │
└──────────────────────┴───────────────────────────┘
                       │
             ┌─────────┴──────────┐
             │  AnalyticDB MySQL  │
             │  dws.* / bigdata.* │
             └────────────────────┘
```

---

## 3. 前端设计

### 3.1 页面结构

#### 页面1：对话查询页（首页）
- **顶部**：Logo"考试宝典数据助手" + 快捷入口（"查看周报""查看月报"按钮，点击跳转报告页）
- **主体**：聊天对话界面
  - 用户输入自然语言问题
  - AI回复：**仅文字+数据表格**，保持轻量
  - 支持连续对话（保留最近5轮上下文）
- **底部**：输入框 + 发送按钮 + 常用问题推荐气泡
- **移动端**：全屏对话布局，底部固定输入框

#### 常用问题推荐
- "本周注册用户情况"
- "付费转化率趋势"
- "上月销售总额"
- "活跃用户同比去年"

#### 页面2：报告页（独立页面，固定模板）
- **顶部**：报告标题 + 日期范围选择器 + 周报/月报切换
- **主体**：五大板块，每个板块包含：
  - 核心指标卡片（数字 + 环比/同比箭头标识，涨绿跌红）
  - 趋势图表（ECharts，近8周/近6月折线图，数据填入自动渲染）
- **五大板块**：
  1. **用户增长**：新增注册用户、日均注册、环比、同比
  2. **用户活跃**：活跃用户数、有效活跃用户、环比、同比
  3. **付费转化**：付费用户数、付费转化率、复购率、ARPU
  4. **用户留存**：次日留存率、周留存率
  5. **用户行为**：答题参与率、模考参与率、课程参与率、人均播放进度、人均刷题量
- **底部**：AI分析建议区
  - 纯文本输出，流式打字机效果（逐字显示，带加载感）
  - 内容：3-5个关键发现 + 1-2条业务建议
- **移动端**：卡片单列堆叠，图表自适应宽度

### 3.2 技术栈
- React 18 + TypeScript
- Ant Design 5（UI组件库）
- ECharts（图表）
- 响应式：Ant Design Grid + CSS媒体查询

---

## 4. 后端设计

### 4.1 NL2SQL 对话服务

**流程：**
1. 用户输入自然语言问题
2. 构建Prompt：System Prompt（表元数据+字段说明+示例SQL）+ 用户问题 + 最近5轮上下文
3. 千问模型生成SQL
4. **安全校验**：
   - 只允许SELECT语句
   - 表名白名单：`dws.*` + `bigdata.v_ws_salesflow_ex`
   - 禁止子查询中的DDL/DML
5. 执行SQL，30秒超时
6. 将结果传给千问，生成一句话总结
7. 返回前端：数据表格 + 总结文字

**错误处理：**
- SQL执行失败 → 千问自动修正一次 → 仍失败则返回友好提示
- 超时 → 提示用户缩小查询范围

**表元数据（注入Prompt）：**

| 表名 | 用途 | 关键字段 |
|------|------|----------|
| `dws.dws_user_daily_quiz_stats_day` | 每日用户刷题统计 | stat_date, daily_register_count, daily_active_count, daily_avg_exam |
| `dws.dws_active_user_report_week` | 活跃用户周报 | start_dt, end_dt, reg_users, active_users, valid_active_users, *_yoy |
| `dws.dws_pay_user_report_week` | 付费用户周报 | start_dt, end_dt, pay_users, pay_conv_rate, repurchase_rate, arpu, *_yoy |
| `dws.dws_retention_user_report_week` | 留存周报 | start_dt, end_dt, n1_ret_rate, w_ret_rate, *_yoy |
| `dws.dws_user_behavior_report_week` | 行为周报 | start_dt, end_dt, quiz_part_rate, mock_part_rate, course_part_rate, avg_play_progress, quiz_rate, *_yoy |
| `bigdata.v_ws_salesflow_ex` | 销售流水 | 售价, 销售日期, 销售部门名称 |

> **注意**：表的完整字段列表需要在实现阶段从数据库中动态获取（`SHOW COLUMNS`），上表仅列出已知的关键字段。

### 4.2 固定报告服务

**周报：**
- 5个预置SQL模板（对应5张dws周报表），来源于现有的查询语句示例
- 传入目标周的起止日期参数
- 返回结构化JSON：
```json
{
  "period": {"start": "2026-03-21", "end": "2026-03-27"},
  "sections": {
    "user_growth": {
      "metrics": {
        "reg_users": {"value": 1234, "wow": "+5.2%", "yoy": "+12.3%"},
        "daily_avg_reg": {"value": 176, "wow": "+3.1%", "yoy": "+8.7%"}
      },
      "trend": [{"week": "W1", "value": 150}, ...]
    },
    ...
  }
}
```

**月报：**
- 基于周报数据按月聚合
- 计算月度总量/均值 + 月环比 + 月同比
- 返回格式同周报

**周定义：** 周六为周起始，周五为周结束（与现有业务逻辑一致）

### 4.3 AI洞察服务

- 将报告结构化数据传给千问
- Prompt要求输出：
  - 3-5个关键发现（附具体数据，如"注册用户环比下降12%，已连续两周下滑"）
  - 1-2条业务建议
- **流式输出**（Server-Sent Events），前端逐字显示
- 使用 `qwen-plus` 模型

### 4.4 安全机制
- SQL白名单：仅允许SELECT
- 表白名单：`dws.*` + `bigdata.v_ws_salesflow_ex`（后续可扩展）
- 查询超时：30秒
- 单次返回行数限制：1000行
- 输入长度限制：500字符

---

## 5. 项目结构

```
exam-data-agent/
├── backend/
│   ├── main.py                  # FastAPI入口，路由注册
│   ├── config.py                # 配置管理（从.env加载）
│   ├── db.py                    # 数据库连接池（SQLAlchemy）
│   ├── services/
│   │   ├── chat.py              # NL2SQL对话服务
│   │   ├── report.py            # 固定报告服务（周报/月报）
│   │   └── insight.py           # AI洞察生成（SSE流式）
│   ├── sql_templates/           # 预置SQL模板
│   │   ├── weekly_active.sql    # 活跃用户周报
│   │   ├── weekly_pay.sql       # 付费用户周报
│   │   ├── weekly_retention.sql # 留存周报
│   │   ├── weekly_behavior.sql  # 行为周报
│   │   └── weekly_user.sql      # 用户增长周报（日维度汇总）
│   ├── prompts/                 # 千问Prompt模板
│   │   ├── nl2sql.txt           # NL转SQL的system prompt
│   │   └── insight.txt          # 洞察分析prompt
│   └── requirements.txt
├── frontend/
│   ├── src/
│   │   ├── pages/
│   │   │   ├── Chat.tsx         # 对话查询页
│   │   │   └── Report.tsx       # 固定报告页
│   │   ├── components/
│   │   │   ├── MetricCard.tsx   # 指标卡片（数字+环比同比箭头）
│   │   │   ├── TrendChart.tsx   # 趋势图表（ECharts封装）
│   │   │   ├── InsightText.tsx  # AI洞察文本（打字机效果）
│   │   │   └── ChatBubble.tsx   # 对话气泡
│   │   └── App.tsx
│   └── package.json
├── .env                         # 密钥配置（git忽略）
└── docker-compose.yml           # 一键部署
```

---

## 6. API接口设计

### 6.1 对话查询
```
POST /api/chat
Body: { "message": "上周新注册用户多少", "history": [...] }
Response: { "answer": "上周新注册用户1,234人，环比增长5.2%", "table": [...] }
```

### 6.2 获取周报数据
```
GET /api/report/weekly?date=2026-03-27
Response: { "period": {...}, "sections": {...} }
```

### 6.3 获取月报数据
```
GET /api/report/monthly?month=2026-03
Response: { "period": {...}, "sections": {...} }
```

### 6.4 AI洞察（SSE流式）
```
GET /api/insight/stream?type=weekly&date=2026-03-27
Response: SSE stream，逐字输出分析文本
```

---

## 7. 技术栈总结

| 层级 | 技术选型 |
|------|---------|
| 前端框架 | React 18 + TypeScript |
| UI组件库 | Ant Design 5 |
| 图表 | ECharts |
| 后端框架 | Python 3.11 + FastAPI |
| 数据库驱动 | SQLAlchemy + pymysql |
| LLM | 千问 qwen-plus（阿里百炼OpenAI兼容接口） |
| 部署 | Docker Compose（nginx + uvicorn） |

---

## 8. 未来扩展（不在MVP范围内）
- 更多bigdata表的接入
- 用户登录与权限管理
- 报告定时推送（钉钉/邮件）
- 自定义报告模板
- 数据导出（Excel/PDF）
