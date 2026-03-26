# 考试宝典数据助手 实现计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 构建一个面向管理层的数据查询Web Agent，支持自然语言查数、固定周报/月报、AI洞察分析。

**Architecture:** FastAPI后端连接AnalyticDB MySQL，通过千问qwen-plus实现NL2SQL和AI洞察。React + Ant Design + ECharts前端，对话页轻量回答，报告页固定模板展示。SSE流式输出AI洞察文本。

**Tech Stack:** Python 3.11, FastAPI, SQLAlchemy, pymysql, openai SDK, sqlparse | React 18, TypeScript, Ant Design 5, ECharts | Docker Compose

**Spec:** `docs/superpowers/specs/2026-03-26-exam-data-agent-design.md`

**现有资源：**
- 数据库连接：`am-bp1s2h8891l2u1mnl167320o.ads.aliyuncs.com`，用户`chenzhi`
- 千问API Key：在`千问key.env`中
- 已有SQL模板：在`查询语句示例.txt`中（5类周报查询+销售查询）
- 密码等敏感信息：各`.env`文件中

---

## File Structure

```
exam-data-agent/
├── backend/
│   ├── main.py                  # FastAPI入口，路由注册，CORS
│   ├── config.py                # 配置管理（从.env加载所有密钥和连接信息）
│   ├── db.py                    # SQLAlchemy连接池，execute_query辅助函数
│   ├── sql_validator.py         # SQL安全校验（sqlparse解析，白名单检查）
│   ├── services/
│   │   ├── __init__.py
│   │   ├── chat.py              # NL2SQL对话服务（千问生成SQL→校验→执行→总结）
│   │   ├── report.py            # 固定报告服务（加载SQL模板，执行，结构化返回）
│   │   └── insight.py           # AI洞察生成（SSE流式输出）
│   ├── sql_templates/           # 预置SQL模板（参数化，从现有查询语句改写）
│   │   ├── weekly_user_growth.sql
│   │   ├── weekly_active.sql
│   │   ├── weekly_pay.sql
│   │   ├── weekly_retention.sql
│   │   └── weekly_behavior.sql
│   ├── prompts/
│   │   ├── nl2sql.txt           # NL2SQL的system prompt
│   │   └── insight.txt          # 洞察分析prompt
│   ├── tests/
│   │   ├── test_sql_validator.py
│   │   ├── test_report.py
│   │   └── test_chat.py
│   └── requirements.txt
├── frontend/
│   ├── src/
│   │   ├── api.ts               # 后端API调用封装
│   │   ├── App.tsx              # 路由配置
│   │   ├── pages/
│   │   │   ├── Chat.tsx         # 对话查询页
│   │   │   └── Report.tsx       # 固定报告页
│   │   ├── components/
│   │   │   ├── MetricCard.tsx   # 指标卡片
│   │   │   ├── TrendChart.tsx   # ECharts趋势图
│   │   │   ├── InsightText.tsx  # AI洞察打字机效果
│   │   │   └── ChatBubble.tsx   # 对话气泡（含表格渲染）
│   │   └── main.tsx
│   ├── index.html
│   ├── package.json
│   ├── tsconfig.json
│   └── vite.config.ts
├── .env                         # 统一密钥配置（git忽略）
├── .gitignore
├── docker-compose.yml
├── Dockerfile.backend
└── Dockerfile.frontend
```

---

## Task 1: 项目脚手架与配置

**Files:**
- Create: `exam-data-agent/.gitignore`
- Create: `exam-data-agent/.env`
- Create: `exam-data-agent/backend/requirements.txt`
- Create: `exam-data-agent/backend/config.py`

- [ ] **Step 1: 创建项目目录结构**

```bash
cd "D:/文档/文档/公司/NLP/Claude-agent-design"
mkdir -p exam-data-agent/backend/services
mkdir -p exam-data-agent/backend/sql_templates
mkdir -p exam-data-agent/backend/prompts
mkdir -p exam-data-agent/backend/tests
mkdir -p exam-data-agent/frontend/src/pages
mkdir -p exam-data-agent/frontend/src/components
```

- [ ] **Step 2: 创建.gitignore**

```gitignore
# exam-data-agent/.gitignore
.env
__pycache__/
*.pyc
node_modules/
dist/
.vite/
```

- [ ] **Step 3: 创建.env（从现有密钥文件整合）**

从项目根目录的各个密钥文件读取，整合到一个`.env`：
```env
# 数据库
DB_HOST=am-bp1s2h8891l2u1mnl167320o.ads.aliyuncs.com
DB_PORT=3306
DB_USER=chenzhi
DB_PASSWORD=25823291@Yingedu
DB_NAME=dws

# 千问API
QWEN_API_KEY=sk-fe955bdbb4434be799c823bca4484c9a
QWEN_BASE_URL=https://dashscope.aliyuncs.com/compatible-mode/v1
QWEN_MODEL=qwen-plus
```

- [ ] **Step 4: 创建requirements.txt**

```txt
# exam-data-agent/backend/requirements.txt
fastapi==0.115.0
uvicorn[standard]==0.30.0
sqlalchemy==2.0.35
pymysql==1.1.1
cryptography==43.0.0
openai==1.50.0
sqlparse==0.5.1
python-dotenv==1.0.1
sse-starlette==2.1.0
```

- [ ] **Step 5: 创建config.py**

```python
# exam-data-agent/backend/config.py
import os
from dotenv import load_dotenv

load_dotenv(os.path.join(os.path.dirname(__file__), '..', '.env'))

DB_HOST = os.getenv("DB_HOST")
DB_PORT = int(os.getenv("DB_PORT", "3306"))
DB_USER = os.getenv("DB_USER")
DB_PASSWORD = os.getenv("DB_PASSWORD")
DB_NAME = os.getenv("DB_NAME", "dws")

DATABASE_URL = f"mysql+pymysql://{DB_USER}:{DB_PASSWORD}@{DB_HOST}:{DB_PORT}/{DB_NAME}"

QWEN_API_KEY = os.getenv("QWEN_API_KEY")
QWEN_BASE_URL = os.getenv("QWEN_BASE_URL", "https://dashscope.aliyuncs.com/compatible-mode/v1")
QWEN_MODEL = os.getenv("QWEN_MODEL", "qwen-plus")

# 安全限制
SQL_TIMEOUT_SECONDS = 30
MAX_RESULT_ROWS = 1000
MAX_INPUT_LENGTH = 500
ALLOWED_TABLES = [
    "dws.dws_user_daily_quiz_stats_day",
    "dws.dws_active_user_report_week",
    "dws.dws_pay_user_report_week",
    "dws.dws_retention_user_report_week",
    "dws.dws_user_behavior_report_week",
    "bigdata.v_ws_salesflow_ex",
]
```

- [ ] **Step 6: Commit**

```bash
git add exam-data-agent/.gitignore exam-data-agent/backend/requirements.txt exam-data-agent/backend/config.py
git commit -m "feat: scaffold project structure and configuration"
```

> **注意**：不要把`.env`提交到git。

---

## Task 2: 数据库连接层

**Files:**
- Create: `exam-data-agent/backend/db.py`

- [ ] **Step 1: 创建db.py**

```python
# exam-data-agent/backend/db.py
from sqlalchemy import create_engine, text
from config import DATABASE_URL, SQL_TIMEOUT_SECONDS, MAX_RESULT_ROWS

engine = create_engine(
    DATABASE_URL,
    pool_size=5,
    max_overflow=10,
    pool_pre_ping=True,
    connect_args={"connect_timeout": 10},
)


def execute_query(sql: str, params: dict = None) -> dict:
    """执行SQL查询，返回 {"columns": [...], "rows": [...]}"""
    with engine.connect() as conn:
        conn.execute(text(f"SET SESSION max_execution_time={SQL_TIMEOUT_SECONDS * 1000}"))
        result = conn.execute(text(sql), params or {})
        columns = list(result.keys())
        rows = [list(row) for row in result.fetchmany(MAX_RESULT_ROWS)]
        # 将所有值转为字符串，方便JSON序列化
        rows = [[str(v) if v is not None else "" for v in row] for row in rows]
        return {"columns": columns, "rows": rows}
```

- [ ] **Step 2: 手动验证数据库连接**

```bash
cd exam-data-agent/backend
pip install -r requirements.txt
python -c "from db import engine; conn = engine.connect(); print('Connected!'); conn.close()"
```

Expected: 打印 `Connected!`

- [ ] **Step 3: Commit**

```bash
git add exam-data-agent/backend/db.py
git commit -m "feat: add database connection layer with connection pool"
```

---

## Task 3: SQL安全校验器

**Files:**
- Create: `exam-data-agent/backend/sql_validator.py`
- Create: `exam-data-agent/backend/tests/test_sql_validator.py`

- [ ] **Step 1: 编写测试**

```python
# exam-data-agent/backend/tests/test_sql_validator.py
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
from sql_validator import validate_sql


def test_valid_select():
    assert validate_sql("SELECT * FROM dws.dws_active_user_report_week") is True


def test_valid_select_with_where():
    sql = "SELECT start_dt, reg_users FROM dws.dws_active_user_report_week WHERE end_dt > '2026-01-01'"
    assert validate_sql(sql) is True


def test_reject_delete():
    assert validate_sql("DELETE FROM dws.dws_active_user_report_week") is False


def test_reject_drop():
    assert validate_sql("DROP TABLE dws.dws_active_user_report_week") is False


def test_reject_insert():
    assert validate_sql("INSERT INTO dws.dws_active_user_report_week VALUES (1,2,3)") is False


def test_reject_update():
    assert validate_sql("UPDATE dws.dws_active_user_report_week SET reg_users=0") is False


def test_reject_unknown_table():
    assert validate_sql("SELECT * FROM secret_table") is False


def test_reject_sleep():
    assert validate_sql("SELECT SLEEP(10)") is False


def test_reject_into_outfile():
    assert validate_sql("SELECT * FROM dws.dws_active_user_report_week INTO OUTFILE '/tmp/a'") is False


def test_reject_load_file():
    assert validate_sql("SELECT LOAD_FILE('/etc/passwd')") is False


def test_allow_bigdata_sales():
    assert validate_sql("SELECT sum(售价) FROM bigdata.v_ws_salesflow_ex WHERE 销售部门名称='APP直充'") is True


def test_reject_bigdata_other():
    assert validate_sql("SELECT * FROM bigdata.some_other_table") is False


def test_allow_subquery():
    sql = "SELECT * FROM (SELECT start_dt, reg_users FROM dws.dws_active_user_report_week) t"
    assert validate_sql(sql) is True


def test_reject_union_bad_table():
    sql = "SELECT * FROM dws.dws_active_user_report_week UNION SELECT * FROM secret_table"
    assert validate_sql(sql) is False
```

- [ ] **Step 2: 运行测试确认失败**

```bash
cd exam-data-agent/backend
python -m pytest tests/test_sql_validator.py -v
```

Expected: FAIL（sql_validator模块不存在）

- [ ] **Step 3: 实现sql_validator.py**

```python
# exam-data-agent/backend/sql_validator.py
import re
import sqlparse
from sqlparse.sql import IdentifierList, Identifier, Where, Parenthesis
from sqlparse.tokens import Keyword, DML
from config import ALLOWED_TABLES

DANGEROUS_FUNCTIONS = {"LOAD_FILE", "SLEEP", "BENCHMARK", "GET_LOCK", "RELEASE_LOCK"}
DANGEROUS_KEYWORDS = {"INTO OUTFILE", "INTO DUMPFILE"}


def _extract_table_names(parsed):
    """从解析后的SQL中提取所有表名"""
    tables = set()
    from_seen = False
    join_seen = False

    for token in parsed.tokens:
        if token.ttype is Keyword and token.normalized in ("FROM", "JOIN", "INNER JOIN", "LEFT JOIN", "RIGHT JOIN", "CROSS JOIN"):
            from_seen = True
            join_seen = "JOIN" in token.normalized
            continue

        if from_seen:
            if isinstance(token, IdentifierList):
                for identifier in token.get_identifiers():
                    name = identifier.get_real_name()
                    schema = identifier.get_parent_name()
                    if schema:
                        tables.add(f"{schema}.{name}")
                    elif name:
                        tables.add(name)
                from_seen = False
            elif isinstance(token, Identifier):
                name = token.get_real_name()
                schema = token.get_parent_name()
                if schema:
                    tables.add(f"{schema}.{name}")
                elif name:
                    tables.add(name)
                from_seen = False
            elif isinstance(token, Parenthesis):
                # 子查询
                inner_sql = token.value[1:-1].strip()
                inner_tables = _extract_tables_from_sql(inner_sql)
                tables.update(inner_tables)
                from_seen = False
            elif token.ttype is not sqlparse.tokens.Whitespace:
                from_seen = False

        # 递归处理子查询
        if isinstance(token, Parenthesis):
            inner_sql = token.value[1:-1].strip()
            inner_tables = _extract_tables_from_sql(inner_sql)
            tables.update(inner_tables)

    return tables


def _extract_tables_from_sql(sql: str) -> set:
    """解析SQL字符串，提取所有表名"""
    tables = set()
    for statement in sqlparse.parse(sql):
        tables.update(_extract_table_names(statement))
    return tables


def _check_dangerous_patterns(sql_upper: str) -> bool:
    """检查危险函数和关键字"""
    for func in DANGEROUS_FUNCTIONS:
        if re.search(rf'\b{func}\s*\(', sql_upper):
            return False
    for kw in DANGEROUS_KEYWORDS:
        if kw in sql_upper:
            return False
    return True


def _is_table_allowed(table_name: str) -> bool:
    """检查表名是否在白名单中"""
    # 精确匹配
    if table_name in ALLOWED_TABLES:
        return True
    # dws.* 通配
    if table_name.startswith("dws."):
        return True
    # 不带schema的表名，视为dws库
    if "." not in table_name:
        return True
    return False


def validate_sql(sql: str) -> bool:
    """校验SQL是否安全。返回True表示允许执行。"""
    sql = sql.strip().rstrip(";")
    sql_upper = sql.upper()

    # 1. 只允许SELECT
    parsed_list = sqlparse.parse(sql)
    if not parsed_list:
        return False
    for statement in parsed_list:
        if statement.get_type() != "SELECT":
            return False

    # 2. 检查危险函数/关键字
    if not _check_dangerous_patterns(sql_upper):
        return False

    # 3. 检查DML/DDL关键字
    for kw in ["INSERT", "UPDATE", "DELETE", "DROP", "ALTER", "CREATE", "TRUNCATE", "GRANT", "REVOKE"]:
        if re.search(rf'\b{kw}\b', sql_upper):
            return False

    # 4. 提取表名并校验白名单
    tables = _extract_tables_from_sql(sql)
    for table in tables:
        if not _is_table_allowed(table):
            return False

    return True
```

- [ ] **Step 4: 运行测试确认通过**

```bash
cd exam-data-agent/backend
python -m pytest tests/test_sql_validator.py -v
```

Expected: 全部PASS

- [ ] **Step 5: Commit**

```bash
git add exam-data-agent/backend/sql_validator.py exam-data-agent/backend/tests/test_sql_validator.py
git commit -m "feat: add SQL security validator with whitelist and dangerous pattern detection"
```

---

## Task 4: SQL模板文件（周报查询）

**Files:**
- Create: `exam-data-agent/backend/sql_templates/weekly_user_growth.sql`
- Create: `exam-data-agent/backend/sql_templates/weekly_active.sql`
- Create: `exam-data-agent/backend/sql_templates/weekly_pay.sql`
- Create: `exam-data-agent/backend/sql_templates/weekly_retention.sql`
- Create: `exam-data-agent/backend/sql_templates/weekly_behavior.sql`

基于 `查询语句示例.txt` 中的现有SQL，改写为参数化模板。每个模板接受 `:end_date` 参数（目标周的周五日期），查询最近N周数据用于趋势展示。

- [ ] **Step 1: 创建weekly_active.sql**

从 `查询语句示例.txt` 第157-187行改写。这个模板查询活跃用户周报表，返回最近8周数据（含环比和同比）。

```sql
-- weekly_active.sql
-- 参数: :end_date (目标周的周五日期，如 '2026-03-27')
-- 返回: 最近8周的注册用户、活跃用户、有效活跃用户及其环比同比
SELECT
    start_dt,
    end_dt,
    reg_users,
    LEAD(reg_users, 1) OVER (ORDER BY end_dt DESC) AS last_week_reg_users,
    reg_users_yoy,
    active_users,
    LEAD(active_users, 1) OVER (ORDER BY end_dt DESC) AS last_week_active_users,
    active_users_yoy,
    valid_active_users,
    LEAD(valid_active_users, 1) OVER (ORDER BY end_dt DESC) AS last_week_valid_active_users,
    valid_active_users_yoy
FROM (
    SELECT *
    FROM dws.dws_active_user_report_week
    WHERE end_dt <= :end_date
    ORDER BY end_dt DESC
    LIMIT 9
) t
ORDER BY end_dt DESC
LIMIT 8;
```

- [ ] **Step 2: 创建weekly_pay.sql**

从 `查询语句示例.txt` 第204-244行改写。

```sql
-- weekly_pay.sql
-- 参数: :end_date
-- 返回: 最近8周付费用户、转化率、复购率、ARPU
SELECT
    start_dt,
    end_dt,
    pay_users,
    LEAD(pay_users, 1) OVER (ORDER BY end_dt DESC) AS last_week_pay_users,
    pay_users_yoy,
    pay_conv_rate,
    LEAD(pay_conv_rate, 1) OVER (ORDER BY end_dt DESC) AS last_week_pay_conv_rate,
    pay_conv_rate_yoy,
    repurchase_rate,
    LEAD(repurchase_rate, 1) OVER (ORDER BY end_dt DESC) AS last_week_repurchase_rate,
    repurchase_rate_yoy,
    arpu,
    LEAD(arpu, 1) OVER (ORDER BY end_dt DESC) AS last_week_arpu,
    arpu_yoy
FROM (
    SELECT *
    FROM dws.dws_pay_user_report_week
    WHERE end_dt <= :end_date
    ORDER BY end_dt DESC
    LIMIT 9
) t
ORDER BY end_dt DESC
LIMIT 8;
```

- [ ] **Step 3: 创建weekly_retention.sql**

从 `查询语句示例.txt` 第256-293行改写。

```sql
-- weekly_retention.sql
-- 参数: :end_date
-- 返回: 最近8周次日留存率、周留存率
SELECT
    start_dt,
    end_dt,
    n1_ret_rate,
    LEAD(n1_ret_rate, 1) OVER (ORDER BY end_dt DESC) AS last_week_n1_ret_rate,
    n1_ret_rate_yoy,
    w_ret_rate,
    LEAD(w_ret_rate, 1) OVER (ORDER BY end_dt DESC) AS last_week_w_ret_rate,
    w_ret_rate_yoy
FROM (
    SELECT *
    FROM dws.dws_retention_user_report_week
    WHERE end_dt <= :end_date
    ORDER BY end_dt DESC
    LIMIT 9
) t
ORDER BY end_dt DESC
LIMIT 8;
```

- [ ] **Step 4: 创建weekly_behavior.sql**

从 `查询语句示例.txt` 第314-404行改写。

```sql
-- weekly_behavior.sql
-- 参数: :end_date
-- 返回: 最近8周答题/模考/课程参与率、播放进度、人均刷题量
SELECT
    start_dt,
    end_dt,
    quiz_part_rate,
    LAG(quiz_part_rate, 1) OVER (ORDER BY end_dt ASC) AS last_week_quiz_part_rate,
    quiz_part_rate_yoy,
    mock_part_rate,
    LAG(mock_part_rate, 1) OVER (ORDER BY end_dt ASC) AS last_week_mock_part_rate,
    mock_part_rate_yoy,
    course_part_rate,
    LAG(course_part_rate, 1) OVER (ORDER BY end_dt ASC) AS last_week_course_part_rate,
    course_part_rate_yoy,
    avg_play_progress,
    LAG(avg_play_progress, 1) OVER (ORDER BY end_dt ASC) AS last_week_avg_play_progress,
    avg_play_progress_yoy,
    quiz_rate,
    LAG(quiz_rate, 1) OVER (ORDER BY end_dt ASC) AS last_week_quiz_rate,
    quiz_rate_yoy
FROM (
    SELECT *
    FROM dws.dws_user_behavior_report_week
    WHERE end_dt <= :end_date
    ORDER BY end_dt DESC
    LIMIT 9
) sub
ORDER BY end_dt ASC;
```

- [ ] **Step 5: 创建weekly_user_growth.sql**

从 `查询语句示例.txt` 第8-130行改写（日维度统计表，用于日粒度注册/活跃/刷题趋势）。

```sql
-- weekly_user_growth.sql
-- 参数: :start_date, :end_date (目标周的周六和周五)
-- 返回: 目标周每天的注册、活跃、人均刷题，以及本周日均值
SELECT
    stat_date,
    daily_register_count,
    daily_active_count,
    daily_avg_exam,
    ROUND(
        SUM(daily_register_count) OVER (ORDER BY stat_date)
        / ROW_NUMBER() OVER (ORDER BY stat_date),
    0) AS week_avg_register,
    ROUND(
        SUM(daily_active_count) OVER (ORDER BY stat_date)
        / ROW_NUMBER() OVER (ORDER BY stat_date),
    0) AS week_avg_active,
    ROUND(
        AVG(daily_avg_exam) OVER (ORDER BY stat_date),
    2) AS week_avg_exam
FROM dws.dws_user_daily_quiz_stats_day
WHERE stat_date BETWEEN :start_date AND :end_date
ORDER BY stat_date;
```

- [ ] **Step 6: Commit**

```bash
git add exam-data-agent/backend/sql_templates/
git commit -m "feat: add parameterized SQL templates for 5 weekly report sections"
```

---

## Task 5: 固定报告服务

**Files:**
- Create: `exam-data-agent/backend/services/__init__.py`
- Create: `exam-data-agent/backend/services/report.py`
- Create: `exam-data-agent/backend/tests/test_report.py`

- [ ] **Step 1: 创建__init__.py**

```python
# exam-data-agent/backend/services/__init__.py
```
（空文件）

- [ ] **Step 2: 编写report.py核心计算函数的测试**

```python
# exam-data-agent/backend/tests/test_report.py
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
from services.report import calc_change_rate, parse_pct, get_week_range


def test_calc_change_rate_normal():
    assert calc_change_rate(110, 100) == "+10.00%"


def test_calc_change_rate_decrease():
    assert calc_change_rate(90, 100) == "-10.00%"


def test_calc_change_rate_zero_base():
    assert calc_change_rate(100, 0) == "N/A"


def test_calc_change_rate_none_base():
    assert calc_change_rate(100, None) == "N/A"


def test_parse_pct_with_percent():
    assert parse_pct("12.34%") == 12.34


def test_parse_pct_number():
    assert parse_pct("56.78") == 56.78


def test_parse_pct_none():
    assert parse_pct(None) is None


def test_get_week_range():
    # 2026-03-27 是周五
    start, end = get_week_range("2026-03-27")
    assert start == "2026-03-21"  # 周六
    assert end == "2026-03-27"    # 周五


def test_get_week_range_midweek():
    # 2026-03-25 是周三，应该返回所在周的周六和周五
    start, end = get_week_range("2026-03-25")
    assert start == "2026-03-21"
    assert end == "2026-03-27"
```

- [ ] **Step 3: 运行测试确认失败**

```bash
cd exam-data-agent/backend
python -m pytest tests/test_report.py -v
```

Expected: FAIL

- [ ] **Step 4: 实现report.py**

```python
# exam-data-agent/backend/services/report.py
import os
from datetime import datetime, timedelta
from db import execute_query

TEMPLATES_DIR = os.path.join(os.path.dirname(__file__), '..', 'sql_templates')


def parse_pct(value) -> float | None:
    """将 '12.34%' 或 12.34 解析为浮点数"""
    if value is None or value == "" or value == "None":
        return None
    s = str(value).replace("%", "").strip()
    try:
        return float(s)
    except ValueError:
        return None


def calc_change_rate(current, previous) -> str:
    """计算环比/同比百分比变化"""
    if previous is None or previous == 0 or previous == "" or previous == "None":
        return "N/A"
    try:
        current_f = float(str(current).replace("%", ""))
        previous_f = float(str(previous).replace("%", ""))
    except (ValueError, TypeError):
        return "N/A"
    if previous_f == 0:
        return "N/A"
    rate = (current_f - previous_f) / previous_f * 100
    sign = "+" if rate >= 0 else ""
    return f"{sign}{rate:.2f}%"


def get_week_range(date_str: str) -> tuple[str, str]:
    """根据任意日期，返回所在业务周的(周六, 周五)日期字符串。
    业务周定义：周六起始，周五结束。"""
    dt = datetime.strptime(date_str, "%Y-%m-%d")
    weekday = dt.weekday()  # Monday=0, Sunday=6
    # 计算到本周周六（起始）的偏移
    # 周六=5, 周日=6, 周一=0, ..., 周五=4
    # 周六起始意味着：如果是周六(5)，偏移0；周日(6)偏移-1；周一(0)偏移-2...周五(4)偏移-6
    days_since_saturday = (weekday - 5) % 7
    saturday = dt - timedelta(days=days_since_saturday)
    friday = saturday + timedelta(days=6)
    return saturday.strftime("%Y-%m-%d"), friday.strftime("%Y-%m-%d")


def _load_template(name: str) -> str:
    """加载SQL模板文件"""
    path = os.path.join(TEMPLATES_DIR, name)
    with open(path, "r", encoding="utf-8") as f:
        return f.read()


def _build_section(rows: list, columns: list, metrics_config: list[dict]) -> dict:
    """将查询结果构建为报告section结构。
    metrics_config: [{"key": "reg_users", "label": "注册用户", "col": "reg_users",
                      "last_col": "last_week_reg_users", "yoy_col": "reg_users_yoy"}]
    """
    if not rows:
        return {"metrics": {}, "trend": []}

    col_idx = {c: i for i, c in enumerate(columns)}
    latest = rows[0]  # 最新一周

    metrics = {}
    for mc in metrics_config:
        current_val = latest[col_idx[mc["col"]]]
        last_val = latest[col_idx[mc["last_col"]]] if mc.get("last_col") and mc["last_col"] in col_idx else None
        yoy_val = latest[col_idx[mc["yoy_col"]]] if mc.get("yoy_col") and mc["yoy_col"] in col_idx else None

        metrics[mc["key"]] = {
            "label": mc["label"],
            "value": current_val,
            "wow": calc_change_rate(current_val, last_val),
            "yoy": calc_change_rate(current_val, yoy_val),
        }

    # 趋势数据（按时间正序）
    trend = []
    start_idx = col_idx.get("start_dt", col_idx.get("stat_date"))
    end_idx = col_idx.get("end_dt")
    for row in reversed(rows):
        entry = {"start": row[start_idx] if start_idx is not None else ""}
        if end_idx is not None:
            entry["end"] = row[end_idx]
        for mc in metrics_config:
            entry[mc["key"]] = row[col_idx[mc["col"]]]
        trend.append(entry)

    return {"metrics": metrics, "trend": trend}


def get_weekly_report(date_str: str) -> dict:
    """获取周报数据。date_str为目标周内任意日期。"""
    start_date, end_date = get_week_range(date_str)

    result = {"period": {"start": start_date, "end": end_date}, "sections": {}}

    # 1. 活跃用户
    sql = _load_template("weekly_active.sql")
    # 去掉SQL注释行
    sql_lines = [l for l in sql.split("\n") if not l.strip().startswith("--")]
    sql_clean = "\n".join(sql_lines)
    data = execute_query(sql_clean, {"end_date": end_date})
    result["sections"]["active"] = _build_section(data["rows"], data["columns"], [
        {"key": "reg_users", "label": "注册用户", "col": "reg_users", "last_col": "last_week_reg_users", "yoy_col": "reg_users_yoy"},
        {"key": "active_users", "label": "活跃用户", "col": "active_users", "last_col": "last_week_active_users", "yoy_col": "active_users_yoy"},
        {"key": "valid_active_users", "label": "有效活跃用户", "col": "valid_active_users", "last_col": "last_week_valid_active_users", "yoy_col": "valid_active_users_yoy"},
    ])

    # 2. 付费
    sql = _load_template("weekly_pay.sql")
    sql_lines = [l for l in sql.split("\n") if not l.strip().startswith("--")]
    sql_clean = "\n".join(sql_lines)
    data = execute_query(sql_clean, {"end_date": end_date})
    result["sections"]["pay"] = _build_section(data["rows"], data["columns"], [
        {"key": "pay_users", "label": "付费用户", "col": "pay_users", "last_col": "last_week_pay_users", "yoy_col": "pay_users_yoy"},
        {"key": "pay_conv_rate", "label": "付费转化率", "col": "pay_conv_rate", "last_col": "last_week_pay_conv_rate", "yoy_col": "pay_conv_rate_yoy"},
        {"key": "repurchase_rate", "label": "复购率", "col": "repurchase_rate", "last_col": "last_week_repurchase_rate", "yoy_col": "repurchase_rate_yoy"},
        {"key": "arpu", "label": "ARPU", "col": "arpu", "last_col": "last_week_arpu", "yoy_col": "arpu_yoy"},
    ])

    # 3. 留存
    sql = _load_template("weekly_retention.sql")
    sql_lines = [l for l in sql.split("\n") if not l.strip().startswith("--")]
    sql_clean = "\n".join(sql_lines)
    data = execute_query(sql_clean, {"end_date": end_date})
    result["sections"]["retention"] = _build_section(data["rows"], data["columns"], [
        {"key": "n1_ret_rate", "label": "次日留存率", "col": "n1_ret_rate", "last_col": "last_week_n1_ret_rate", "yoy_col": "n1_ret_rate_yoy"},
        {"key": "w_ret_rate", "label": "周留存率", "col": "w_ret_rate", "last_col": "last_week_w_ret_rate", "yoy_col": "w_ret_rate_yoy"},
    ])

    # 4. 行为
    sql = _load_template("weekly_behavior.sql")
    sql_lines = [l for l in sql.split("\n") if not l.strip().startswith("--")]
    sql_clean = "\n".join(sql_lines)
    data = execute_query(sql_clean, {"end_date": end_date})
    # 行为表按end_dt ASC排序，最新在最后
    rows_reversed = list(reversed(data["rows"])) if data["rows"] else []
    result["sections"]["behavior"] = _build_section(rows_reversed, data["columns"], [
        {"key": "quiz_part_rate", "label": "答题参与率", "col": "quiz_part_rate", "last_col": "last_week_quiz_part_rate", "yoy_col": "quiz_part_rate_yoy"},
        {"key": "mock_part_rate", "label": "模考参与率", "col": "mock_part_rate", "last_col": "last_week_mock_part_rate", "yoy_col": "mock_part_rate_yoy"},
        {"key": "course_part_rate", "label": "课程参与率", "col": "course_part_rate", "last_col": "last_week_course_part_rate", "yoy_col": "course_part_rate_yoy"},
        {"key": "avg_play_progress", "label": "人均播放进度", "col": "avg_play_progress", "last_col": "last_week_avg_play_progress", "yoy_col": "avg_play_progress_yoy"},
        {"key": "quiz_rate", "label": "人均刷题量", "col": "quiz_rate", "last_col": "last_week_quiz_rate", "yoy_col": "quiz_rate_yoy"},
    ])

    # 5. 用户增长（日粒度）
    sql = _load_template("weekly_user_growth.sql")
    sql_lines = [l for l in sql.split("\n") if not l.strip().startswith("--")]
    sql_clean = "\n".join(sql_lines)
    data = execute_query(sql_clean, {"start_date": start_date, "end_date": end_date})
    result["sections"]["user_growth"] = {
        "columns": data["columns"],
        "rows": data["rows"],
    }

    return result


def get_monthly_report(month_str: str) -> dict:
    """获取月报。month_str格式为 '2026-03'。
    基于周报数据按月聚合，跨月归属规则：按周起始日期（周六）所在月份。"""
    year, month = map(int, month_str.split("-"))

    # 查询该月所有周的数据（start_dt在该月的周）
    # 使用active_user表获取周列表
    sql = """
    SELECT DISTINCT start_dt, end_dt
    FROM dws.dws_active_user_report_week
    WHERE SUBSTRING(start_dt, 1, 7) = :month
    ORDER BY start_dt
    """
    data = execute_query(sql, {"month": month_str})

    if not data["rows"]:
        return {"period": {"month": month_str}, "sections": {}, "weekly_reports": []}

    # 为该月每一周生成周报，然后汇总
    weekly_reports = []
    for row in data["rows"]:
        end_dt = row[1]  # end_dt
        wr = get_weekly_report(end_dt)
        weekly_reports.append(wr)

    # 汇总逻辑：取每周指标，计算月均值
    result = {
        "period": {"month": month_str, "weeks": len(weekly_reports)},
        "sections": {},
        "weekly_reports": weekly_reports,  # 含各周明细，供前端渲染趋势
    }

    return result
```

- [ ] **Step 5: 运行测试确认通过**

```bash
cd exam-data-agent/backend
python -m pytest tests/test_report.py -v
```

Expected: 全部PASS（纯计算函数测试不依赖数据库）

- [ ] **Step 6: Commit**

```bash
git add exam-data-agent/backend/services/
git add exam-data-agent/backend/tests/test_report.py
git commit -m "feat: add weekly/monthly report service with SQL template loading"
```

---

## Task 6: NL2SQL对话服务

**Files:**
- Create: `exam-data-agent/backend/prompts/nl2sql.txt`
- Create: `exam-data-agent/backend/services/chat.py`

- [ ] **Step 1: 创建NL2SQL Prompt模板**

```text
# exam-data-agent/backend/prompts/nl2sql.txt
你是考试宝典的数据查询助手。你的唯一任务是将用户的自然语言问题转换为一条MySQL SELECT查询语句。

## 规则
1. 只输出一条SQL语句，不要解释，不要添加任何其他文字
2. 只能使用SELECT语句，禁止INSERT/UPDATE/DELETE/DROP等
3. 只能查询以下表，不要使用其他表

## 可用表

### dws.dws_active_user_report_week（活跃用户周报）
- start_dt: 周开始日期（周六）
- end_dt: 周结束日期（周五）
- reg_users: 注册用户数
- active_users: 活跃用户数
- valid_active_users: 有效活跃用户数
- reg_users_yoy: 去年同期注册用户数
- active_users_yoy: 去年同期活跃用户数
- valid_active_users_yoy: 去年同期有效活跃用户数

### dws.dws_pay_user_report_week（付费用户周报）
- start_dt, end_dt: 周起止日期
- pay_users: 付费用户数
- pay_conv_rate: 付费转化率（带%号，如 '3.50%'）
- repurchase_rate: 复购率（带%号）
- arpu: 每用户平均收入
- pay_users_yoy, pay_conv_rate_yoy, repurchase_rate_yoy, arpu_yoy: 去年同期值

### dws.dws_retention_user_report_week（留存周报）
- start_dt, end_dt
- n1_ret_rate: 次日留存率（带%号）
- w_ret_rate: 周留存率（带%号）
- n1_ret_rate_yoy, w_ret_rate_yoy: 去年同期值

### dws.dws_user_behavior_report_week（用户行为周报）
- start_dt, end_dt
- quiz_part_rate: 答题参与率（带%号）
- mock_part_rate: 模考参与率（带%号）
- course_part_rate: 课程参与率（带%号）
- avg_play_progress: 人均播放进度（带%号）
- quiz_rate: 人均刷题量（纯数字）
- 各指标均有_yoy同比字段

### dws.dws_user_daily_quiz_stats_day（每日用户统计）
- stat_date: 日期
- daily_register_count: 当日新增注册用户
- daily_active_count: 当日活跃用户
- daily_avg_exam: 当日人均刷题量

### bigdata.v_ws_salesflow_ex（销售流水）
- 售价: 订单金额
- 销售日期: 日期字符串
- 销售部门名称: 如 'APP直充'

## 业务规则
- 业务周定义：周六为周起始，周五为周结束
- 当用户说"本周"，指包含今天的业务周
- 当用户说"上周"，指上一个完整的业务周
- 当用户说"最近"且未指定时间，默认最近一周
- 百分比字段存储时带%号，计算时需REPLACE去掉%再转数值
- 今天是{today}

## 示例
用户: 上周新注册用户多少
SQL: SELECT reg_users FROM dws.dws_active_user_report_week ORDER BY end_dt DESC LIMIT 1

用户: 3月份销售总额
SQL: SELECT SUM(售价) AS total_sales FROM bigdata.v_ws_salesflow_ex WHERE SUBSTRING(销售日期,1,7) = '2026-03' AND 销售部门名称 = 'APP直充'

用户: 最近4周活跃用户趋势
SQL: SELECT start_dt, end_dt, active_users FROM dws.dws_active_user_report_week ORDER BY end_dt DESC LIMIT 4
```

- [ ] **Step 2: 创建chat.py**

```python
# exam-data-agent/backend/services/chat.py
import os
from datetime import date
from openai import OpenAI
from config import QWEN_API_KEY, QWEN_BASE_URL, QWEN_MODEL, MAX_INPUT_LENGTH
from sql_validator import validate_sql
from db import execute_query

PROMPTS_DIR = os.path.join(os.path.dirname(__file__), '..', 'prompts')

client = OpenAI(api_key=QWEN_API_KEY, base_url=QWEN_BASE_URL)


def _load_prompt(name: str) -> str:
    path = os.path.join(PROMPTS_DIR, name)
    with open(path, "r", encoding="utf-8") as f:
        return f.read()


def _generate_sql(message: str, history: list[dict]) -> str:
    """调用千问将自然语言转为SQL"""
    system_prompt = _load_prompt("nl2sql.txt").replace("{today}", date.today().isoformat())

    messages = [{"role": "system", "content": system_prompt}]
    # 加入最近5轮对话上下文
    for h in history[-10:]:
        messages.append(h)
    messages.append({"role": "user", "content": message})

    response = client.chat.completions.create(
        model=QWEN_MODEL,
        messages=messages,
        temperature=0,
        max_tokens=1000,
    )
    sql = response.choices[0].message.content.strip()
    # 去掉可能的markdown代码块标记
    if sql.startswith("```"):
        lines = sql.split("\n")
        sql = "\n".join(lines[1:-1] if lines[-1].strip() == "```" else lines[1:])
    return sql.strip()


def _summarize_result(message: str, table_data: dict) -> str:
    """调用千问对查询结果生成一句话总结"""
    # 将表格数据格式化为文本
    if not table_data["rows"]:
        return "查询结果为空，没有找到匹配的数据。"

    header = " | ".join(table_data["columns"])
    rows_text = "\n".join([" | ".join(row) for row in table_data["rows"][:20]])
    data_text = f"{header}\n{rows_text}"

    response = client.chat.completions.create(
        model=QWEN_MODEL,
        messages=[
            {"role": "system", "content": "你是考试宝典的数据分析助手。用户问了一个数据问题，下面是查询结果。请用简洁的中文（1-2句话）回答用户的问题，直接给出关键数据。"},
            {"role": "user", "content": f"用户问题：{message}\n\n查询结果：\n{data_text}"},
        ],
        temperature=0.3,
        max_tokens=200,
    )
    return response.choices[0].message.content.strip()


def chat(message: str, history: list[dict] = None) -> dict:
    """对话查询主函数。
    返回: {"answer": str, "table": {"columns": [...], "rows": [...]}}
    或: {"error": True, "code": str, "message": str}
    """
    if history is None:
        history = []

    if len(message) > MAX_INPUT_LENGTH:
        return {"error": True, "code": "INVALID_INPUT", "message": f"输入过长，请控制在{MAX_INPUT_LENGTH}字以内"}

    # 1. 生成SQL
    try:
        sql = _generate_sql(message, history)
    except Exception as e:
        return {"error": True, "code": "LLM_ERROR", "message": f"AI服务暂时不可用，请稍后重试"}

    # 2. 校验SQL
    if not validate_sql(sql):
        # 尝试修正一次
        try:
            fix_messages = [
                {"role": "system", "content": "上一次生成的SQL不合规。请重新生成一条安全的SELECT查询。只使用dws库和bigdata.v_ws_salesflow_ex表。"},
                {"role": "user", "content": f"原始问题：{message}\n不合规SQL：{sql}\n请重新生成合规的SQL。"},
            ]
            response = client.chat.completions.create(model=QWEN_MODEL, messages=fix_messages, temperature=0, max_tokens=1000)
            sql = response.choices[0].message.content.strip()
            if sql.startswith("```"):
                lines = sql.split("\n")
                sql = "\n".join(lines[1:-1] if lines[-1].strip() == "```" else lines[1:])
            sql = sql.strip()
            if not validate_sql(sql):
                return {"error": True, "code": "SQL_FAILED", "message": "无法生成合规的查询语句，请换个方式描述您的问题"}
        except Exception:
            return {"error": True, "code": "SQL_FAILED", "message": "无法生成合规的查询语句，请换个方式描述您的问题"}

    # 3. 执行SQL
    try:
        table_data = execute_query(sql)
    except Exception as e:
        error_msg = str(e)
        if "max_execution_time" in error_msg.lower() or "timeout" in error_msg.lower():
            return {"error": True, "code": "SQL_TIMEOUT", "message": "查询超时，请尝试缩小查询范围或指定更具体的条件"}
        return {"error": True, "code": "SQL_FAILED", "message": "查询执行失败，请换个方式描述您的问题"}

    # 4. 生成总结
    try:
        answer = _summarize_result(message, table_data)
    except Exception:
        answer = "查询完成，请查看下方数据表格。"

    return {"answer": answer, "table": table_data}
```

- [ ] **Step 3: Commit**

```bash
git add exam-data-agent/backend/prompts/nl2sql.txt exam-data-agent/backend/services/chat.py
git commit -m "feat: add NL2SQL chat service with Qwen integration and auto-correction"
```

---

## Task 7: AI洞察服务（SSE流式）

**Files:**
- Create: `exam-data-agent/backend/prompts/insight.txt`
- Create: `exam-data-agent/backend/services/insight.py`

- [ ] **Step 1: 创建洞察分析Prompt**

```text
# exam-data-agent/backend/prompts/insight.txt
你是考试宝典的资深数据分析师，正在为管理层撰写数据周报/月报的洞察分析。

请基于以下报告数据，输出：
1. **关键发现**（3-5条）：每条都要包含具体数据和变化幅度，如"注册用户环比下降12%，已连续两周下滑"
2. **业务建议**（1-2条）：基于数据趋势给出可操作的建议

## 要求
- 语言简洁专业，适合管理层阅读
- 优先关注异常变化（大幅上升/下降、连续变化趋势）
- 给出的建议要具体可执行，不要空泛
- 用 Markdown 格式输出，使用 ### 标题区分"关键发现"和"业务建议"

## 报告数据
{report_data}
```

- [ ] **Step 2: 创建insight.py**

```python
# exam-data-agent/backend/services/insight.py
import os
import json
from openai import OpenAI
from config import QWEN_API_KEY, QWEN_BASE_URL, QWEN_MODEL
from services.report import get_weekly_report, get_monthly_report

PROMPTS_DIR = os.path.join(os.path.dirname(__file__), '..', 'prompts')

client = OpenAI(api_key=QWEN_API_KEY, base_url=QWEN_BASE_URL)


def _load_prompt(name: str) -> str:
    path = os.path.join(PROMPTS_DIR, name)
    with open(path, "r", encoding="utf-8") as f:
        return f.read()


def _format_report_for_prompt(report: dict) -> str:
    """将报告数据格式化为Prompt可读文本"""
    lines = []
    period = report.get("period", {})
    if "month" in period:
        lines.append(f"报告类型: 月报 ({period['month']})")
    else:
        lines.append(f"报告类型: 周报 ({period.get('start', '')} ~ {period.get('end', '')})")

    for section_key, section_data in report.get("sections", {}).items():
        if "metrics" not in section_data:
            continue
        lines.append(f"\n## {section_key}")
        for metric_key, metric in section_data["metrics"].items():
            label = metric.get("label", metric_key)
            value = metric.get("value", "N/A")
            wow = metric.get("wow", "N/A")
            yoy = metric.get("yoy", "N/A")
            lines.append(f"- {label}: {value} (环比: {wow}, 同比: {yoy})")

    return "\n".join(lines)


async def stream_insight(report_type: str, date_str: str):
    """SSE流式生成洞察分析。yield每个文本chunk。"""
    # 1. 获取报告数据
    if report_type == "weekly":
        report = get_weekly_report(date_str)
    elif report_type == "monthly":
        report = get_monthly_report(date_str)
    else:
        yield "data: 不支持的报告类型\n\n"
        return

    # 2. 格式化数据
    report_text = _format_report_for_prompt(report)
    prompt_template = _load_prompt("insight.txt")
    prompt = prompt_template.replace("{report_data}", report_text)

    # 3. 流式调用千问
    stream = client.chat.completions.create(
        model=QWEN_MODEL,
        messages=[
            {"role": "system", "content": prompt},
            {"role": "user", "content": "请分析以上数据，给出关键发现和业务建议。"},
        ],
        temperature=0.5,
        max_tokens=1000,
        stream=True,
    )

    for chunk in stream:
        if chunk.choices and chunk.choices[0].delta.content:
            text = chunk.choices[0].delta.content
            yield f"data: {json.dumps({'text': text}, ensure_ascii=False)}\n\n"

    yield "data: [DONE]\n\n"
```

- [ ] **Step 3: Commit**

```bash
git add exam-data-agent/backend/prompts/insight.txt exam-data-agent/backend/services/insight.py
git commit -m "feat: add AI insight service with SSE streaming output"
```

---

## Task 8: FastAPI主入口与路由

**Files:**
- Create: `exam-data-agent/backend/main.py`

- [ ] **Step 1: 创建main.py**

```python
# exam-data-agent/backend/main.py
from fastapi import FastAPI, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from services.chat import chat
from services.report import get_weekly_report, get_monthly_report
from services.insight import stream_insight

app = FastAPI(title="考试宝典数据助手")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


class ChatRequest(BaseModel):
    message: str
    history: list[dict] = []


@app.post("/api/chat")
def api_chat(req: ChatRequest):
    result = chat(req.message, req.history)
    return result


@app.get("/api/report/weekly")
def api_weekly_report(date: str = Query(..., description="目标周内任意日期，如2026-03-27")):
    return get_weekly_report(date)


@app.get("/api/report/monthly")
def api_monthly_report(month: str = Query(..., description="目标月份，如2026-03")):
    return get_monthly_report(month)


@app.get("/api/insight/stream")
async def api_insight_stream(
    type: str = Query(..., description="weekly或monthly"),
    date: str = Query(..., description="日期参数"),
):
    return StreamingResponse(
        stream_insight(type, date),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


@app.get("/api/health")
def health():
    return {"status": "ok"}
```

- [ ] **Step 2: 启动后端验证**

```bash
cd exam-data-agent/backend
pip install -r requirements.txt
python -m uvicorn main:app --reload --port 8000
```

在浏览器访问 `http://localhost:8000/api/health`，Expected: `{"status":"ok"}`

- [ ] **Step 3: Commit**

```bash
git add exam-data-agent/backend/main.py
git commit -m "feat: add FastAPI main entry with all API routes"
```

---

## Task 9: 前端项目初始化

**Files:**
- Create: `exam-data-agent/frontend/package.json`
- Create: `exam-data-agent/frontend/vite.config.ts`
- Create: `exam-data-agent/frontend/tsconfig.json`
- Create: `exam-data-agent/frontend/index.html`
- Create: `exam-data-agent/frontend/src/main.tsx`
- Create: `exam-data-agent/frontend/src/App.tsx`
- Create: `exam-data-agent/frontend/src/api.ts`

- [ ] **Step 1: 初始化React项目**

```bash
cd exam-data-agent/frontend
npm create vite@latest . -- --template react-ts
npm install antd @ant-design/icons echarts echarts-for-react react-router-dom
```

- [ ] **Step 2: 创建api.ts（后端API封装）**

```typescript
// exam-data-agent/frontend/src/api.ts
const BASE_URL = import.meta.env.VITE_API_URL || "http://localhost:8000";

export interface ChatResponse {
  answer?: string;
  table?: { columns: string[]; rows: string[][] };
  error?: boolean;
  code?: string;
  message?: string;
}

export interface ReportResponse {
  period: { start?: string; end?: string; month?: string };
  sections: Record<string, any>;
}

export async function sendChat(message: string, history: { role: string; content: string }[]): Promise<ChatResponse> {
  const res = await fetch(`${BASE_URL}/api/chat`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ message, history }),
  });
  return res.json();
}

export async function getWeeklyReport(date: string): Promise<ReportResponse> {
  const res = await fetch(`${BASE_URL}/api/report/weekly?date=${date}`);
  return res.json();
}

export async function getMonthlyReport(month: string): Promise<ReportResponse> {
  const res = await fetch(`${BASE_URL}/api/report/monthly?month=${month}`);
  return res.json();
}

export function streamInsight(type: string, date: string, onChunk: (text: string) => void, onDone: () => void) {
  const url = `${BASE_URL}/api/insight/stream?type=${type}&date=${date}`;
  const eventSource = new EventSource(url);

  eventSource.onmessage = (event) => {
    if (event.data === "[DONE]") {
      eventSource.close();
      onDone();
      return;
    }
    try {
      const data = JSON.parse(event.data);
      if (data.text) onChunk(data.text);
    } catch {
      // ignore parse errors
    }
  };

  eventSource.onerror = () => {
    eventSource.close();
    onDone();
  };

  return () => eventSource.close();
}
```

- [ ] **Step 3: 创建App.tsx（路由配置）**

```tsx
// exam-data-agent/frontend/src/App.tsx
import { BrowserRouter, Routes, Route } from "react-router-dom";
import Chat from "./pages/Chat";
import Report from "./pages/Report";

export default function App() {
  return (
    <BrowserRouter>
      <Routes>
        <Route path="/" element={<Chat />} />
        <Route path="/report" element={<Report />} />
      </Routes>
    </BrowserRouter>
  );
}
```

- [ ] **Step 4: Commit**

```bash
git add exam-data-agent/frontend/
git commit -m "feat: initialize React frontend with routing and API layer"
```

---

## Task 10: 前端组件——ChatBubble、MetricCard

**Files:**
- Create: `exam-data-agent/frontend/src/components/ChatBubble.tsx`
- Create: `exam-data-agent/frontend/src/components/MetricCard.tsx`

- [ ] **Step 1: 创建ChatBubble.tsx**

```tsx
// exam-data-agent/frontend/src/components/ChatBubble.tsx
import { Table, Typography } from "antd";

const { Text } = Typography;

interface Props {
  role: "user" | "assistant";
  content: string;
  table?: { columns: string[]; rows: string[][] };
}

export default function ChatBubble({ role, content, table }: Props) {
  const isUser = role === "user";

  return (
    <div style={{
      display: "flex",
      justifyContent: isUser ? "flex-end" : "flex-start",
      marginBottom: 16,
      padding: "0 16px",
    }}>
      <div style={{
        maxWidth: "80%",
        padding: "12px 16px",
        borderRadius: 12,
        backgroundColor: isUser ? "#1677ff" : "#f5f5f5",
        color: isUser ? "#fff" : "#333",
      }}>
        <Text style={{ color: isUser ? "#fff" : "#333", whiteSpace: "pre-wrap" }}>
          {content}
        </Text>
        {table && table.rows.length > 0 && (
          <Table
            style={{ marginTop: 12 }}
            size="small"
            pagination={false}
            scroll={{ x: "max-content" }}
            dataSource={table.rows.map((row, i) => {
              const obj: Record<string, string> = { key: String(i) };
              table.columns.forEach((col, j) => { obj[col] = row[j]; });
              return obj;
            })}
            columns={table.columns.map((col) => ({
              title: col,
              dataIndex: col,
              key: col,
            }))}
          />
        )}
      </div>
    </div>
  );
}
```

- [ ] **Step 2: 创建MetricCard.tsx**

```tsx
// exam-data-agent/frontend/src/components/MetricCard.tsx
import { Card, Statistic, Space, Typography, Row, Col } from "antd";
import { ArrowUpOutlined, ArrowDownOutlined } from "@ant-design/icons";

const { Text } = Typography;

interface MetricData {
  label: string;
  value: string;
  wow: string;
  yoy: string;
}

interface Props {
  data: MetricData;
}

function ChangeTag({ label, value }: { label: string; value: string }) {
  if (!value || value === "N/A") return <Text type="secondary">{label}: N/A</Text>;

  const numStr = value.replace("%", "").replace("+", "");
  const num = parseFloat(numStr);
  const isUp = num > 0;
  const color = isUp ? "#52c41a" : "#ff4d4f";
  const icon = isUp ? <ArrowUpOutlined /> : <ArrowDownOutlined />;

  return (
    <Text style={{ color, fontSize: 12 }}>
      {icon} {label} {value}
    </Text>
  );
}

export default function MetricCard({ data }: Props) {
  return (
    <Card size="small" style={{ minWidth: 200 }}>
      <Statistic title={data.label} value={data.value} />
      <Space direction="vertical" size={2} style={{ marginTop: 8 }}>
        <ChangeTag label="环比" value={data.wow} />
        <ChangeTag label="同比" value={data.yoy} />
      </Space>
    </Card>
  );
}
```

- [ ] **Step 3: Commit**

```bash
git add exam-data-agent/frontend/src/components/ChatBubble.tsx exam-data-agent/frontend/src/components/MetricCard.tsx
git commit -m "feat: add ChatBubble and MetricCard components"
```

---

## Task 11: 前端组件——TrendChart、InsightText

**Files:**
- Create: `exam-data-agent/frontend/src/components/TrendChart.tsx`
- Create: `exam-data-agent/frontend/src/components/InsightText.tsx`

- [ ] **Step 1: 创建TrendChart.tsx**

```tsx
// exam-data-agent/frontend/src/components/TrendChart.tsx
import ReactECharts from "echarts-for-react";

interface Props {
  title: string;
  xData: string[];        // 周起始日期
  series: {
    name: string;
    data: (number | string)[];
  }[];
}

export default function TrendChart({ title, xData, series }: Props) {
  const option = {
    title: { text: title, textStyle: { fontSize: 14 } },
    tooltip: { trigger: "axis" as const },
    legend: { bottom: 0 },
    grid: { left: "3%", right: "4%", bottom: "15%", containLabel: true },
    xAxis: {
      type: "category" as const,
      data: xData,
      axisLabel: { rotate: 30, fontSize: 10 },
    },
    yAxis: { type: "value" as const },
    series: series.map((s) => ({
      name: s.name,
      type: "line" as const,
      data: s.data.map((v) => {
        const n = parseFloat(String(v).replace("%", ""));
        return isNaN(n) ? 0 : n;
      }),
      smooth: true,
    })),
  };

  return <ReactECharts option={option} style={{ height: 300, width: "100%" }} />;
}
```

- [ ] **Step 2: 创建InsightText.tsx**

```tsx
// exam-data-agent/frontend/src/components/InsightText.tsx
import { useEffect, useState } from "react";
import { Card, Spin, Typography } from "antd";
import { BulbOutlined } from "@ant-design/icons";
import { streamInsight } from "../api";

const { Paragraph } = Typography;

interface Props {
  type: "weekly" | "monthly";
  date: string;
}

export default function InsightText({ type, date }: Props) {
  const [text, setText] = useState("");
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    setText("");
    setLoading(true);

    const cancel = streamInsight(type, date,
      (chunk) => setText((prev) => prev + chunk),
      () => setLoading(false),
    );

    return cancel;
  }, [type, date]);

  return (
    <Card
      title={<><BulbOutlined /> AI 分析洞察</>}
      style={{ marginTop: 24 }}
    >
      {loading && !text && <Spin tip="正在分析数据..." />}
      <Paragraph style={{ whiteSpace: "pre-wrap" }}>
        {text}
        {loading && text && <span className="cursor-blink">|</span>}
      </Paragraph>
    </Card>
  );
}
```

- [ ] **Step 3: Commit**

```bash
git add exam-data-agent/frontend/src/components/TrendChart.tsx exam-data-agent/frontend/src/components/InsightText.tsx
git commit -m "feat: add TrendChart and InsightText (typewriter effect) components"
```

---

## Task 12: 对话查询页

**Files:**
- Create: `exam-data-agent/frontend/src/pages/Chat.tsx`

- [ ] **Step 1: 创建Chat.tsx**

```tsx
// exam-data-agent/frontend/src/pages/Chat.tsx
import { useState, useRef, useEffect } from "react";
import { Layout, Input, Button, Space, Tag, Typography } from "antd";
import { SendOutlined, BarChartOutlined } from "@ant-design/icons";
import { useNavigate } from "react-router-dom";
import ChatBubble from "../components/ChatBubble";
import { sendChat, ChatResponse } from "../api";

const { Header, Content, Footer } = Layout;
const { Title } = Typography;

interface Message {
  role: "user" | "assistant";
  content: string;
  table?: { columns: string[]; rows: string[][] };
}

const SUGGESTIONS = [
  "本周注册用户情况",
  "付费转化率趋势",
  "上月销售总额",
  "活跃用户同比去年",
];

export default function Chat() {
  const [messages, setMessages] = useState<Message[]>([]);
  const [input, setInput] = useState("");
  const [loading, setLoading] = useState(false);
  const bottomRef = useRef<HTMLDivElement>(null);
  const navigate = useNavigate();

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages]);

  const handleSend = async (text?: string) => {
    const msg = text || input.trim();
    if (!msg) return;
    setInput("");

    const userMsg: Message = { role: "user", content: msg };
    setMessages((prev) => [...prev, userMsg]);
    setLoading(true);

    // 构建history
    const history = messages.slice(-10).map((m) => ({
      role: m.role,
      content: m.content,
    }));

    try {
      const res: ChatResponse = await sendChat(msg, history);
      const assistantMsg: Message = {
        role: "assistant",
        content: res.error ? (res.message || "查询失败") : (res.answer || ""),
        table: res.error ? undefined : res.table,
      };
      setMessages((prev) => [...prev, assistantMsg]);
    } catch {
      setMessages((prev) => [...prev, { role: "assistant", content: "网络错误，请稍后重试" }]);
    } finally {
      setLoading(false);
    }
  };

  return (
    <Layout style={{ height: "100vh" }}>
      <Header style={{
        background: "#fff",
        display: "flex",
        alignItems: "center",
        justifyContent: "space-between",
        padding: "0 24px",
        borderBottom: "1px solid #f0f0f0",
      }}>
        <Title level={4} style={{ margin: 0 }}>考试宝典数据助手</Title>
        <Space>
          <Button icon={<BarChartOutlined />} onClick={() => navigate("/report?type=weekly")}>
            周报
          </Button>
          <Button icon={<BarChartOutlined />} onClick={() => navigate("/report?type=monthly")}>
            月报
          </Button>
        </Space>
      </Header>

      <Content style={{ flex: 1, overflow: "auto", padding: "24px 0" }}>
        {messages.length === 0 && (
          <div style={{ textAlign: "center", padding: "60px 24px" }}>
            <Title level={3} type="secondary">你好，请问想查询什么数据？</Title>
            <Space wrap style={{ marginTop: 24 }}>
              {SUGGESTIONS.map((s) => (
                <Tag
                  key={s}
                  style={{ cursor: "pointer", padding: "4px 12px", fontSize: 14 }}
                  onClick={() => handleSend(s)}
                >
                  {s}
                </Tag>
              ))}
            </Space>
          </div>
        )}
        {messages.map((msg, i) => (
          <ChatBubble key={i} role={msg.role} content={msg.content} table={msg.table} />
        ))}
        <div ref={bottomRef} />
      </Content>

      <Footer style={{ padding: "12px 24px", background: "#fff", borderTop: "1px solid #f0f0f0" }}>
        <Space.Compact style={{ width: "100%" }}>
          <Input
            size="large"
            placeholder="输入数据查询问题..."
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onPressEnter={() => handleSend()}
            disabled={loading}
          />
          <Button
            size="large"
            type="primary"
            icon={<SendOutlined />}
            onClick={() => handleSend()}
            loading={loading}
          />
        </Space.Compact>
      </Footer>
    </Layout>
  );
}
```

- [ ] **Step 2: Commit**

```bash
git add exam-data-agent/frontend/src/pages/Chat.tsx
git commit -m "feat: add Chat page with conversation UI and suggestion bubbles"
```

---

## Task 13: 固定报告页

**Files:**
- Create: `exam-data-agent/frontend/src/pages/Report.tsx`

- [ ] **Step 1: 创建Report.tsx**

```tsx
// exam-data-agent/frontend/src/pages/Report.tsx
import { useState, useEffect } from "react";
import { useSearchParams, useNavigate } from "react-router-dom";
import { Layout, DatePicker, Segmented, Row, Col, Spin, Button, Typography, Divider } from "antd";
import { ArrowLeftOutlined } from "@ant-design/icons";
import dayjs from "dayjs";
import MetricCard from "../components/MetricCard";
import TrendChart from "../components/TrendChart";
import InsightText from "../components/InsightText";
import { getWeeklyReport, getMonthlyReport, ReportResponse } from "../api";

const { Header, Content } = Layout;
const { Title } = Typography;

export default function Report() {
  const [searchParams] = useSearchParams();
  const navigate = useNavigate();
  const [reportType, setReportType] = useState<"weekly" | "monthly">(
    (searchParams.get("type") as "weekly" | "monthly") || "weekly"
  );
  const [date, setDate] = useState(dayjs().format("YYYY-MM-DD"));
  const [month, setMonth] = useState(dayjs().format("YYYY-MM"));
  const [report, setReport] = useState<ReportResponse | null>(null);
  const [loading, setLoading] = useState(false);

  const currentDateParam = reportType === "weekly" ? date : month;

  useEffect(() => {
    setLoading(true);
    const fetchReport = reportType === "weekly"
      ? getWeeklyReport(date)
      : getMonthlyReport(month);

    fetchReport
      .then((data) => setReport(data))
      .catch(() => setReport(null))
      .finally(() => setLoading(false));
  }, [reportType, date, month]);

  const renderSection = (key: string, title: string) => {
    const section = report?.sections?.[key];
    if (!section || !section.metrics) return null;

    const metrics = Object.values(section.metrics) as any[];
    const trend = section.trend || [];
    const xData = trend.map((t: any) => t.start || t.end || "");

    return (
      <div key={key} style={{ marginBottom: 32 }}>
        <Title level={5}>{title}</Title>
        <Row gutter={[16, 16]}>
          {metrics.map((m: any) => (
            <Col key={m.label} xs={12} sm={8} md={6}>
              <MetricCard data={m} />
            </Col>
          ))}
        </Row>
        {trend.length > 0 && (
          <TrendChart
            title={`${title}趋势`}
            xData={xData}
            series={metrics.map((m: any) => ({
              name: m.label,
              data: trend.map((t: any) => t[Object.keys(section.metrics).find((k: string) => section.metrics[k].label === m.label) || ""] || 0),
            }))}
          />
        )}
        <Divider />
      </div>
    );
  };

  return (
    <Layout style={{ minHeight: "100vh" }}>
      <Header style={{
        background: "#fff",
        display: "flex",
        alignItems: "center",
        gap: 16,
        padding: "0 24px",
        borderBottom: "1px solid #f0f0f0",
        flexWrap: "wrap",
      }}>
        <Button icon={<ArrowLeftOutlined />} onClick={() => navigate("/")} type="text" />
        <Title level={4} style={{ margin: 0 }}>
          考试宝典{reportType === "weekly" ? "周" : "月"}报
        </Title>
        <Segmented
          value={reportType}
          options={[
            { label: "周报", value: "weekly" },
            { label: "月报", value: "monthly" },
          ]}
          onChange={(v) => setReportType(v as "weekly" | "monthly")}
        />
        {reportType === "weekly" ? (
          <DatePicker
            value={dayjs(date)}
            onChange={(d) => d && setDate(d.format("YYYY-MM-DD"))}
          />
        ) : (
          <DatePicker
            picker="month"
            value={dayjs(month, "YYYY-MM")}
            onChange={(d) => d && setMonth(d.format("YYYY-MM"))}
          />
        )}
      </Header>

      <Content style={{ padding: 24, maxWidth: 1200, margin: "0 auto", width: "100%" }}>
        {loading ? (
          <div style={{ textAlign: "center", padding: 80 }}>
            <Spin size="large" tip="加载报告数据中..." />
          </div>
        ) : report ? (
          <>
            {renderSection("active", "用户增长与活跃")}
            {renderSection("pay", "付费转化")}
            {renderSection("retention", "用户留存")}
            {renderSection("behavior", "用户行为")}
            <InsightText type={reportType} date={currentDateParam} />
          </>
        ) : (
          <div style={{ textAlign: "center", padding: 80 }}>
            <Title level={4} type="secondary">暂无报告数据</Title>
          </div>
        )}
      </Content>
    </Layout>
  );
}
```

- [ ] **Step 2: Commit**

```bash
git add exam-data-agent/frontend/src/pages/Report.tsx
git commit -m "feat: add Report page with metric cards, trend charts, and AI insights"
```

---

## Task 14: Docker部署配置

**Files:**
- Create: `exam-data-agent/Dockerfile.backend`
- Create: `exam-data-agent/Dockerfile.frontend`
- Create: `exam-data-agent/docker-compose.yml`

- [ ] **Step 1: 创建Dockerfile.backend**

```dockerfile
# exam-data-agent/Dockerfile.backend
FROM python:3.11-slim
WORKDIR /app
COPY backend/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY backend/ .
EXPOSE 8000
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
```

- [ ] **Step 2: 创建Dockerfile.frontend**

```dockerfile
# exam-data-agent/Dockerfile.frontend
FROM node:20-alpine AS build
WORKDIR /app
COPY frontend/package*.json ./
RUN npm ci
COPY frontend/ .
RUN npm run build

FROM nginx:alpine
COPY --from=build /app/dist /usr/share/nginx/html
COPY <<'EOF' /etc/nginx/conf.d/default.conf
server {
    listen 80;
    location / {
        root /usr/share/nginx/html;
        index index.html;
        try_files $uri $uri/ /index.html;
    }
    location /api/ {
        proxy_pass http://backend:8000;
        proxy_http_version 1.1;
        proxy_set_header Connection "";
        proxy_buffering off;
        proxy_cache off;
    }
}
EOF
EXPOSE 80
```

- [ ] **Step 3: 创建docker-compose.yml**

```yaml
# exam-data-agent/docker-compose.yml
version: "3.8"
services:
  backend:
    build:
      context: .
      dockerfile: Dockerfile.backend
    env_file: .env
    ports:
      - "8000:8000"
    restart: unless-stopped

  frontend:
    build:
      context: .
      dockerfile: Dockerfile.frontend
    ports:
      - "80:80"
    depends_on:
      - backend
    restart: unless-stopped
```

- [ ] **Step 4: Commit**

```bash
git add exam-data-agent/Dockerfile.backend exam-data-agent/Dockerfile.frontend exam-data-agent/docker-compose.yml
git commit -m "feat: add Docker deployment configuration"
```

---

## Task 15: 端到端验证

- [ ] **Step 1: 启动后端**

```bash
cd exam-data-agent/backend
pip install -r requirements.txt
python -m uvicorn main:app --reload --port 8000
```

- [ ] **Step 2: 验证后端API**

```bash
# 健康检查
curl http://localhost:8000/api/health

# 对话查询
curl -X POST http://localhost:8000/api/chat \
  -H "Content-Type: application/json" \
  -d '{"message":"上周注册用户多少","history":[]}'

# 周报
curl "http://localhost:8000/api/report/weekly?date=2026-03-27"
```

- [ ] **Step 3: 启动前端**

```bash
cd exam-data-agent/frontend
npm install
npm run dev
```

在浏览器访问 `http://localhost:5173`，验证：
1. 对话页加载正常，推荐气泡可点击
2. 输入"上周注册用户多少"，返回文字回答和数据表格
3. 点击"周报"按钮，跳转报告页
4. 报告页显示指标卡片、趋势图表
5. AI洞察区域流式输出文字

- [ ] **Step 4: 移动端验证**

使用浏览器DevTools切换到移动端视口（375x667），验证：
1. 对话页输入框在底部
2. 报告页卡片单列堆叠
3. 图表自适应宽度

- [ ] **Step 5: 运行全部测试**

```bash
cd exam-data-agent/backend
python -m pytest tests/ -v
```

Expected: 全部PASS

- [ ] **Step 6: 最终Commit**

```bash
cd "D:/文档/文档/公司/NLP/Claude-agent-design"
git add -A exam-data-agent/
git commit -m "feat: complete exam data agent MVP - chat, reports, AI insights"
```
