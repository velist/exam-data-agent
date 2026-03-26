# 钉钉自然语言数据查询机器人 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 在本机运行一个基于钉钉 Stream Mode 的群聊机器人，支持自然语言查单库全表、按需触发分析看板 JSON、并通过阿里百炼/千问输出摘要与建议。

**Architecture:** 使用 Python 3.12 构建单进程后端，分为钉钉接入、元数据扫描、LLM 规划、SQL 安全校验、查询执行、结果格式化、看板发布七个模块。机器人走 Stream Mode 接收群里 @ 消息；LLM 通过阿里百炼 OpenAI 兼容接口调用；SQL 仅允许单条 SELECT，并通过解析器与规则双重校验；长周期分析问题额外生成固定 JSON 并发布到网站模板可读的位置。

**Tech Stack:** Python 3.12, dingtalk-stream, OpenAI Python SDK, SQLAlchemy, PyMySQL, Pydantic Settings, sqlglot, pandas + xlrd, FastAPI (health/debug only), pytest, respx/httpx

---

## File Structure and Responsibilities

- `pyproject.toml` — 项目元数据、依赖、pytest 配置。
- `.gitignore` — 忽略虚拟环境、缓存、日志、生成的 dashboard JSON、真实秘钥。
- `.env.example` — 规范化环境变量模板，作为未来替代散落文本文件的目标格式。
- `README.md` — 本地启动、配置映射、手工验证步骤。
- `app/config.py` — 统一读取 `.env` 与现有“中文标签/纯文本”秘钥文件，输出 `Settings`。
- `app/logging_config.py` — 结构化日志初始化。
- `app/models/message.py` — 统一群消息对象与路由结果对象。
- `app/bot/handlers.py` — 钉钉消息解析、AT 检查、回复调用。
- `app/bot/stream_client.py` — Stream 客户端启动与回调注册。
- `app/llm/schemas.py` — LLM 输出 JSON Schema（意图、SQL 候选、摘要、建议）。
- `app/llm/prompts.py` — 规划 SQL、总结回答、看板建议提示词模板。
- `app/llm/client.py` — 阿里百炼 OpenAI 兼容客户端封装。
- `app/db/engine.py` — 数据库连接与连接池。
- `app/db/introspection.py` — 扫描库表字段元数据并落盘缓存。
- `app/db/query_runner.py` — 执行安全 SQL、限制返回规模、统一错误处理。
- `app/metadata/aliases.py` — 从 `表映射.xls` 读取中文别名并与真实元数据合并。
- `app/security/sql_guard.py` — SQL 解析、只读校验、敏感库拦截、LIMIT 注入。
- `app/security/masking.py` — 手机号/姓名/证件号等部分脱敏。
- `app/security/rate_limit.py` — 轻量用户/群级限流。
- `app/workflow/router.py` — 即时问答流 vs 分析看板流路由。
- `app/workflow/query_workflow.py` — NL -> LLM -> SQL guard -> DB -> 摘要/表格。
- `app/workflow/dashboard_workflow.py` — 分析问题 -> 查询 -> dashboard payload -> 发布 -> 摘要。
- `app/formatting/reply_builder.py` — 群回复文本/表格截断/看板链接格式化。
- `app/dashboard/payloads.py` — 看板 JSON 结构与序列化。
- `app/dashboard/publisher.py` — JSON 落盘和/或 HTTP 推送网站。
- `app/audit/logger.py` — 审计记录（问题、耗时、行数、是否触发看板）。
- `app/main.py` — 应用装配、依赖注入、启动入口。
- `scripts/run_bot.py` — 启动机器人。
- `scripts/refresh_metadata.py` — 手工刷新元数据缓存。
- `scripts/smoke_query.py` — 在不接钉钉时，用命令行问题走全链路。
- `tests/...` — 单测、契约测试、工作流测试、E2E 伪集成测试。
- `data/metadata/` — 落盘的 schema cache。
- `data/dashboards/` — 生成的 JSON 数据。
- `data/logs/` — 本地运行日志。

## Implementation Notes

- 当前目录不是 git 仓库，因此第一步先 `git init`，后续所有任务都保留 commit step。
- 现有秘钥文件不是标准 `.env`：`机器人配置.env` 含中文/英文标签文本和一个 webhook URL，其他文件有纯文本值。实现时必须兼容这些旧格式，同时引导未来切到标准 `.env`。
- `表映射.xls` 是旧式 `.xls`，读取时需要 `xlrd`；不能只依赖 `openpyxl`。
- 钉钉官方开发者百科的 Python 机器人 Stream 示例使用 `dingtalk-stream` 与 `ChatbotHandler`。
- 阿里百炼官方 OpenAI 兼容文档给出了 `https://dashscope.aliyuncs.com/compatible-mode/v1` 的 Python SDK 调用方式。

---

### Task 0: 初始化仓库与最小可运行骨架

**Files:**
- Create: `.gitignore`
- Create: `pyproject.toml`
- Create: `README.md`
- Create: `app/__init__.py`
- Create: `app/main.py`
- Create: `tests/test_smoke.py`
- Create: `data/.gitkeep`
- Create: `scripts/.gitkeep`
- Test: `tests/test_smoke.py`

- [ ] **Step 1: 写一个失败的最小烟雾测试**

```python
# tests/test_smoke.py
import importlib


def test_app_package_importable():
    module = importlib.import_module("app.main")
    assert hasattr(module, "create_app")
```

- [ ] **Step 2: 运行测试，确认当前失败**

Run: `pytest tests/test_smoke.py -v`  
Expected: FAIL with `ModuleNotFoundError: No module named 'app'`

- [ ] **Step 3: 创建项目骨架与依赖声明**

```toml
# pyproject.toml
[build-system]
requires = ["setuptools>=69", "wheel"]
build-backend = "setuptools.build_meta"

[project]
name = "dingtalk-data-query-bot"
version = "0.1.0"
description = "DingTalk natural-language data query bot with dashboard workflow"
readme = "README.md"
requires-python = ">=3.12"
dependencies = [
  "dingtalk-stream>=0.22",
  "openai>=1.75.0",
  "sqlalchemy>=2.0",
  "pymysql>=1.1",
  "pydantic>=2.7",
  "pydantic-settings>=2.2",
  "sqlglot>=25.0",
  "pandas>=2.2",
  "xlrd>=2.0",
  "fastapi>=0.115",
  "httpx>=0.28",
]

[project.optional-dependencies]
dev = [
  "pytest>=8.3",
  "pytest-asyncio>=0.26",
  "respx>=0.21",
  "ruff>=0.11",
]

[tool.pytest.ini_options]
testpaths = ["tests"]
pythonpath = ["."]
```

```python
# app/main.py
from dataclasses import dataclass


@dataclass
class Application:
    name: str = "dingtalk-data-query-bot"


def create_app() -> Application:
    return Application()
```

- [ ] **Step 4: 创建忽略文件与基础文档**

```gitignore
# .gitignore
.venv/
__pycache__/
.pytest_cache/
.ruff_cache/
*.pyc
.env
.env.*
data/logs/
data/dashboards/
data/metadata/
!.gitkeep
```

```markdown
# README.md

## Quick start
1. `python -m venv .venv`
2. `./.venv/Scripts/Activate.ps1`
3. `python -m pip install -e .[dev]`
4. `pytest -q`
```

- [ ] **Step 5: 安装依赖并验证测试通过**

Run:
1. `python -m venv .venv`
2. `./.venv/Scripts/Activate.ps1`
3. `python -m pip install -e .[dev]`
4. `pytest tests/test_smoke.py -v`

Expected: PASS

- [ ] **Step 6: 初始化 git 并提交骨架**

```bash
git init
git add .
git commit -m "chore: bootstrap dingtalk data bot project"
```

---

### Task 1: 配置加载与旧格式秘钥兼容

**Files:**
- Create: `.env.example`
- Create: `app/config.py`
- Create: `tests/test_config.py`
- Modify: `README.md`
- Test: `tests/test_config.py`

- [ ] **Step 1: 先写失败测试，覆盖旧格式文件解析和标准 env 回退**

```python
# tests/test_config.py
from pathlib import Path

from app.config import Settings, load_settings


def test_load_settings_from_legacy_files(tmp_path: Path):
    (tmp_path / "机器人配置.env").write_text(
        "appid：ding-app-id\nClient ID：client_id_value\nClient Secret：client_secret_value\nwebhook:https://oapi.dingtalk.com/robot/send?access_token=abc\n",
        encoding="utf-8",
    )
    (tmp_path / "千问key.env").write_text("sk-demo-key\n", encoding="utf-8")
    (tmp_path / "数据库链接.txt").write_text("db.example.com\n", encoding="utf-8")
    (tmp_path / "数据库账号.txt").write_text("reporter\n", encoding="utf-8")
    (tmp_path / "数据库密码.env").write_text("password@123\n", encoding="utf-8")

    settings = load_settings(base_dir=tmp_path)

    assert isinstance(settings, Settings)
    assert settings.dingtalk_client_id == "client_id_value"
    assert settings.dingtalk_client_secret == "client_secret_value"
    assert settings.qwen_api_key.get_secret_value() == "sk-demo-key"
    assert settings.db_host == "db.example.com"
    assert settings.db_user == "reporter"
```

- [ ] **Step 2: 运行测试，确认失败**

Run: `pytest tests/test_config.py -v`  
Expected: FAIL with `ModuleNotFoundError` or missing `load_settings`

- [ ] **Step 3: 实现 Settings 与 legacy file parser**

```python
# app/config.py
from __future__ import annotations

import re
from pathlib import Path

from pydantic import SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


LABEL_PATTERNS = {
    "dingtalk_appid": re.compile(r"^appid[：: ]+(.+)$", re.I),
    "dingtalk_client_id": re.compile(r"^client\s*id[：: ]+(.+)$", re.I),
    "dingtalk_client_secret": re.compile(r"^client\s*secret[：: ]+(.+)$", re.I),
}


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    dingtalk_client_id: str
    dingtalk_client_secret: str
    dingtalk_robot_code: str | None = None
    dingtalk_webhook: str | None = None
    qwen_api_key: SecretStr
    qwen_base_url: str = "https://dashscope.aliyuncs.com/compatible-mode/v1"
    qwen_model: str = "qwen-plus-latest"
    db_host: str
    db_port: int = 3306
    db_name: str = "bigdata"
    db_user: str
    db_password: SecretStr
    metadata_cache_path: str = "data/metadata/schema_cache.json"
    dashboard_output_dir: str = "data/dashboards"
    dashboard_public_base_url: str = "https://example.com/dashboards"
    dashboard_threshold_days: int = 7
    query_row_limit: int = 50
    query_timeout_seconds: int = 15


def load_settings(base_dir: Path | None = None) -> Settings:
    base_dir = base_dir or Path.cwd()
    legacy = _load_legacy_values(base_dir)
    return Settings(**legacy)
```

- [ ] **Step 4: 定义标准 `.env.example` 和 README 中的映射说明**

```dotenv
# .env.example
DINGTALK_CLIENT_ID=
DINGTALK_CLIENT_SECRET=
DINGTALK_ROBOT_CODE=
DINGTALK_WEBHOOK=
QWEN_API_KEY=
QWEN_BASE_URL=https://dashscope.aliyuncs.com/compatible-mode/v1
QWEN_MODEL=qwen-plus-latest
DB_HOST=
DB_PORT=3306
DB_NAME=bigdata
DB_USER=
DB_PASSWORD=
DASHBOARD_PUBLIC_BASE_URL=https://example.com/dashboards
DASHBOARD_OUTPUT_DIR=data/dashboards
```

- [ ] **Step 5: 跑测试确认 parser 和 settings 都通过**

Run: `pytest tests/test_config.py -v`  
Expected: PASS

- [ ] **Step 6: 提交配置模块**

```bash
git add .env.example README.md app/config.py tests/test_config.py
git commit -m "feat: add config loader for legacy secrets"
```

---

### Task 2: 钉钉 Stream 接入与统一消息对象

**Files:**
- Create: `app/models/message.py`
- Create: `app/bot/handlers.py`
- Create: `app/bot/stream_client.py`
- Create: `scripts/run_bot.py`
- Create: `tests/bot/test_handlers.py`
- Modify: `app/main.py`
- Test: `tests/bot/test_handlers.py`

- [ ] **Step 1: 写失败测试，先锁定消息解析和 ACK 行为**

```python
# tests/bot/test_handlers.py
import types

from app.bot.handlers import DingtalkMessageHandler


class DummyIncoming:
    sender_staff_id = "staff-1"
    conversation_id = "cid-1"
    chatbot_corp_id = "corp-1"
    text = types.SimpleNamespace(content="@机器人 最近有多少新用户？")


def test_handler_normalizes_message_and_calls_processor():
    class Processor:
        async def handle(self, message):
            return "最近新增用户 42 人"

    handler = DingtalkMessageHandler(processor=Processor())
    message = handler._normalize(DummyIncoming())

    assert message.text == "最近有多少新用户？"
    assert message.sender_id == "staff-1"
```

- [ ] **Step 2: 运行测试，确认失败**

Run: `pytest tests/bot/test_handlers.py -v`  
Expected: FAIL with missing handler classes

- [ ] **Step 3: 实现统一消息模型与处理器适配**

```python
# app/models/message.py
from dataclasses import dataclass, field
from datetime import datetime


@dataclass
class NormalizedMessage:
    sender_id: str
    conversation_id: str
    conversation_type: str
    text: str
    raw_text: str
    received_at: datetime = field(default_factory=datetime.utcnow)
```

```python
# app/bot/handlers.py
from __future__ import annotations

import re

import dingtalk_stream
from dingtalk_stream import AckMessage

from app.models.message import NormalizedMessage


AT_PREFIX = re.compile(r"^@\S+\s*")


class DingtalkMessageHandler(dingtalk_stream.ChatbotHandler):
    def __init__(self, processor):
        super().__init__()
        self.processor = processor

    def _normalize(self, incoming) -> NormalizedMessage:
        raw_text = incoming.text.content.strip()
        text = AT_PREFIX.sub("", raw_text, count=1).strip()
        return NormalizedMessage(
            sender_id=getattr(incoming, "sender_staff_id", ""),
            conversation_id=incoming.conversation_id,
            conversation_type=getattr(incoming, "conversation_type", "group"),
            text=text,
            raw_text=raw_text,
        )

    async def process(self, callback: dingtalk_stream.CallbackMessage):
        incoming = dingtalk_stream.ChatbotMessage.from_dict(callback.data)
        message = self._normalize(incoming)
        reply = await self.processor.handle(message)
        self.reply_text(reply, incoming)
        return AckMessage.STATUS_OK, "OK"
```

- [ ] **Step 4: 封装 Stream client 与脚本入口**

```python
# app/bot/stream_client.py
import dingtalk_stream

from app.bot.handlers import DingtalkMessageHandler


def build_stream_client(settings, processor):
    credential = dingtalk_stream.Credential(
        settings.dingtalk_client_id,
        settings.dingtalk_client_secret,
    )
    client = dingtalk_stream.DingTalkStreamClient(credential)
    client.register_callback_handler(
        dingtalk_stream.chatbot.ChatbotMessage.TOPIC,
        DingtalkMessageHandler(processor=processor),
    )
    return client
```

- [ ] **Step 5: 跑单测并做一次 dry-run 导入验证**

Run:
1. `pytest tests/bot/test_handlers.py -v`
2. `python -c "from app.bot.stream_client import build_stream_client; print('ok')"`

Expected: tests PASS, import prints `ok`

- [ ] **Step 6: 提交 Stream 接入骨架**

```bash
git add app/models/message.py app/bot/handlers.py app/bot/stream_client.py scripts/run_bot.py tests/bot/test_handlers.py app/main.py
git commit -m "feat: add dingtalk stream ingress skeleton"
```

---

### Task 3: 数据库连接、元数据扫描、Excel 中文别名合并

**Files:**
- Create: `app/db/engine.py`
- Create: `app/db/introspection.py`
- Create: `app/metadata/aliases.py`
- Create: `tests/db/test_introspection.py`
- Create: `tests/metadata/test_aliases.py`
- Create: `scripts/refresh_metadata.py`
- Test: `tests/db/test_introspection.py`
- Test: `tests/metadata/test_aliases.py`

- [ ] **Step 1: 写失败测试，先锁定元数据缓存结构**

```python
# tests/db/test_introspection.py
from app.db.introspection import build_schema_cache


def test_build_schema_cache_returns_table_column_mapping():
    rows = [
        {"table_schema": "bigdata", "table_name": "users", "column_name": "id", "data_type": "bigint"},
        {"table_schema": "bigdata", "table_name": "users", "column_name": "phone", "data_type": "varchar"},
    ]

    cache = build_schema_cache(rows)

    assert cache["bigdata.users"]["columns"]["id"] == "bigint"
    assert cache["bigdata.users"]["columns"]["phone"] == "varchar"
```

- [ ] **Step 2: 再写失败测试，锁定 Excel 别名合并结果**

```python
# tests/metadata/test_aliases.py
import pandas as pd

from app.metadata.aliases import merge_alias_rows


def test_merge_alias_rows_attaches_cn_aliases():
    schema_cache = {"bigdata.v_ksb_users_ex": {"columns": {"用户id": "bigint"}}}
    df = pd.DataFrame([
        {"数据库名": "bigdata", "表英文名": "v_ksb_users_ex", "表中文名": "用户信息表", "字段英文名": "用户id", "字段中文名": "用户编号"}
    ])

    merged = merge_alias_rows(schema_cache, df)

    assert merged["bigdata.v_ksb_users_ex"]["table_alias"] == "用户信息表"
```

- [ ] **Step 3: 运行测试确认失败**

Run: `pytest tests/db/test_introspection.py tests/metadata/test_aliases.py -v`  
Expected: FAIL with missing modules/functions

- [ ] **Step 4: 实现数据库 engine 与 introspection**

```python
# app/db/engine.py
from sqlalchemy import create_engine


def build_engine(settings):
    password = settings.db_password.get_secret_value()
    url = f"mysql+pymysql://{settings.db_user}:{password}@{settings.db_host}:{settings.db_port}/{settings.db_name}?charset=utf8mb4"
    return create_engine(url, pool_pre_ping=True, pool_recycle=1800)
```

```python
# app/db/introspection.py
from collections import defaultdict


INTROSPECTION_SQL = """
SELECT table_schema, table_name, column_name, data_type
FROM information_schema.columns
WHERE table_schema = :schema
ORDER BY table_name, ordinal_position
"""


def build_schema_cache(rows):
    cache = defaultdict(lambda: {"columns": {}, "table_alias": None, "column_aliases": {}})
    for row in rows:
        key = f"{row['table_schema']}.{row['table_name']}"
        cache[key]["schema"] = row["table_schema"]
        cache[key]["table"] = row["table_name"]
        cache[key]["columns"][row["column_name"]] = row["data_type"]
    return dict(cache)
```

- [ ] **Step 5: 实现 `.xls` 中文别名加载与缓存落盘**

```python
# app/metadata/aliases.py
from pathlib import Path

import pandas as pd



def load_alias_sheet(path: Path) -> pd.DataFrame:
    return pd.read_excel(path, sheet_name=0)



def merge_alias_rows(schema_cache: dict, df: pd.DataFrame) -> dict:
    for _, row in df.fillna("").iterrows():
        key = f"{row['数据库名']}.{row['表英文名']}"
        if key not in schema_cache:
            continue
        if row.get("表中文名"):
            schema_cache[key]["table_alias"] = row["表中文名"]
        if row.get("字段英文名") and row.get("字段中文名"):
            schema_cache[key]["column_aliases"][row["字段英文名"]] = row["字段中文名"]
    return schema_cache
```

- [ ] **Step 6: 跑测试并生成一次本地 schema cache**

Run:
1. `pytest tests/db/test_introspection.py tests/metadata/test_aliases.py -v`
2. `python scripts/refresh_metadata.py`

Expected:
- tests PASS
- `data/metadata/schema_cache.json` created

- [ ] **Step 7: 提交元数据模块**

```bash
git add app/db/engine.py app/db/introspection.py app/metadata/aliases.py scripts/refresh_metadata.py tests/db/test_introspection.py tests/metadata/test_aliases.py
git commit -m "feat: add schema introspection and alias merging"
```

---

### Task 4: 百炼/千问客户端与结构化 LLM 契约

**Files:**
- Create: `app/llm/schemas.py`
- Create: `app/llm/prompts.py`
- Create: `app/llm/client.py`
- Create: `tests/llm/test_client.py`
- Test: `tests/llm/test_client.py`

- [ ] **Step 1: 写失败测试，固定查询规划 JSON 解析契约**

```python
# tests/llm/test_client.py
from app.llm.schemas import QueryPlan


def test_query_plan_parses_required_fields():
    payload = {
        "question_type": "metric",
        "candidate_tables": ["bigdata.v_ksb_users_ex"],
        "candidate_sql": "SELECT COUNT(*) AS total FROM v_ksb_users_ex",
        "requires_dashboard": False,
        "clarification_needed": False,
    }

    plan = QueryPlan.model_validate(payload)

    assert plan.question_type == "metric"
    assert plan.requires_dashboard is False
```

- [ ] **Step 2: 运行测试，确认失败**

Run: `pytest tests/llm/test_client.py -v`  
Expected: FAIL with missing schema/client module

- [ ] **Step 3: 定义 Pydantic 契约和 prompt 模板**

```python
# app/llm/schemas.py
from pydantic import BaseModel, Field


class QueryPlan(BaseModel):
    question_type: str
    candidate_tables: list[str] = Field(default_factory=list)
    candidate_fields: list[str] = Field(default_factory=list)
    candidate_sql: str
    time_range: dict = Field(default_factory=dict)
    dimensions: list[str] = Field(default_factory=list)
    metrics: list[str] = Field(default_factory=list)
    requires_dashboard: bool = False
    clarification_needed: bool = False
    clarification_question: str | None = None


class AnswerSummary(BaseModel):
    answer: str
    follow_up: str | None = None
    suggestions: list[str] = Field(default_factory=list)
```

```python
# app/llm/client.py
from openai import OpenAI

from app.llm.schemas import QueryPlan


class QwenClient:
    def __init__(self, settings):
        self.client = OpenAI(
            api_key=settings.qwen_api_key.get_secret_value(),
            base_url=settings.qwen_base_url,
        )
        self.model = settings.qwen_model

    def build_query_plan(self, messages: list[dict]) -> QueryPlan:
        completion = self.client.chat.completions.create(
            model=self.model,
            response_format={"type": "json_object"},
            messages=messages,
            temperature=0,
        )
        content = completion.choices[0].message.content
        return QueryPlan.model_validate_json(content)
```

- [ ] **Step 4: 用 mock 测试客户端解析逻辑**

```python
# tests/llm/test_client.py (additional)
from types import SimpleNamespace

from app.llm.client import QwenClient


def test_build_query_plan_parses_model_json():
    fake_response = SimpleNamespace(
        choices=[SimpleNamespace(message=SimpleNamespace(content='{"question_type":"metric","candidate_sql":"SELECT 1","requires_dashboard":false,"clarification_needed":false}'))]
    )

    client = QwenClient.__new__(QwenClient)
    client.model = "qwen-plus-latest"
    client.client = SimpleNamespace(chat=SimpleNamespace(completions=SimpleNamespace(create=lambda **_: fake_response)))

    plan = client.build_query_plan([{"role": "user", "content": "最近有多少新用户"}])
    assert plan.candidate_sql == "SELECT 1"
```

- [ ] **Step 5: 跑测试确认契约稳定**

Run: `pytest tests/llm/test_client.py -v`  
Expected: PASS

- [ ] **Step 6: 提交 LLM 契约层**

```bash
git add app/llm/schemas.py app/llm/prompts.py app/llm/client.py tests/llm/test_client.py
git commit -m "feat: add qwen client and structured llm contracts"
```

---

### Task 5: SQL 安全校验与安全查询执行器

**Files:**
- Create: `app/security/sql_guard.py`
- Create: `app/db/query_runner.py`
- Create: `tests/security/test_sql_guard.py`
- Create: `tests/db/test_query_runner.py`
- Test: `tests/security/test_sql_guard.py`
- Test: `tests/db/test_query_runner.py`

- [ ] **Step 1: 先写失败测试，锁定只允许单条 SELECT**

```python
# tests/security/test_sql_guard.py
import pytest

from app.security.sql_guard import ensure_safe_select


@pytest.mark.parametrize(
    "sql",
    [
        "UPDATE users SET name='x'",
        "SELECT * FROM users; DELETE FROM users",
        "SELECT * FROM information_schema.columns",
        "SELECT * FROM users -- comment",
    ],
)
def test_unsafe_sql_is_rejected(sql):
    with pytest.raises(ValueError):
        ensure_safe_select(sql, max_rows=50)
```

- [ ] **Step 2: 再写失败测试，锁定自动补 LIMIT**

```python
from app.security.sql_guard import ensure_safe_select


def test_limit_is_added_when_missing():
    safe_sql = ensure_safe_select("SELECT id, name FROM users", max_rows=20)
    assert "LIMIT 20" in safe_sql.upper()
```

- [ ] **Step 3: 运行测试，确认失败**

Run: `pytest tests/security/test_sql_guard.py -v`  
Expected: FAIL with missing guard implementation

- [ ] **Step 4: 用 sqlglot 实现解析和规则校验**

```python
# app/security/sql_guard.py
import re

import sqlglot
from sqlglot import exp

FORBIDDEN_SCHEMAS = {"information_schema", "mysql", "performance_schema", "sys"}
COMMENT_PATTERN = re.compile(r"(--|/\*|#)")



def ensure_safe_select(sql: str, max_rows: int) -> str:
    sql = sql.strip()
    if COMMENT_PATTERN.search(sql):
        raise ValueError("SQL comments are not allowed")
    if ";" in sql.rstrip(";"):
        raise ValueError("Multiple statements are not allowed")

    tree = sqlglot.parse_one(sql, read="mysql")
    if not isinstance(tree, (exp.Select, exp.Union, exp.Subquery)):
        raise ValueError("Only SELECT queries are allowed")

    for table in tree.find_all(exp.Table):
        if table.db and table.db.lower() in FORBIDDEN_SCHEMAS:
            raise ValueError("System schemas are blocked")

    if not tree.args.get("limit"):
        tree = tree.limit(max_rows)
    return tree.sql(dialect="mysql")
```

- [ ] **Step 5: 实现 query runner，统一返回列表记录和列名**

```python
# app/db/query_runner.py
from sqlalchemy import text

from app.security.sql_guard import ensure_safe_select



def run_safe_query(engine, sql: str, *, max_rows: int, timeout_seconds: int) -> tuple[list[str], list[dict]]:
    safe_sql = ensure_safe_select(sql, max_rows=max_rows)
    with engine.connect() as conn:
        result = conn.execute(text(safe_sql))
        rows = [dict(row._mapping) for row in result.fetchmany(max_rows)]
        columns = list(rows[0].keys()) if rows else list(result.keys())
    return columns, rows
```

- [ ] **Step 6: 补一个 runner 单测并跑通全部安全测试**

```python
# tests/db/test_query_runner.py
from types import SimpleNamespace

from app.db.query_runner import run_safe_query


def test_run_safe_query_returns_columns_and_rows():
    class FakeResult:
        def fetchmany(self, _):
            return [SimpleNamespace(_mapping={"total": 3})]
        def keys(self):
            return ["total"]

    class FakeConn:
        def __enter__(self): return self
        def __exit__(self, *args): return False
        def execute(self, _): return FakeResult()

    class FakeEngine:
        def connect(self): return FakeConn()

    columns, rows = run_safe_query(FakeEngine(), "SELECT COUNT(*) AS total FROM users", max_rows=50, timeout_seconds=15)
    assert columns == ["total"]
    assert rows == [{"total": 3}]
```

Run: `pytest tests/security/test_sql_guard.py tests/db/test_query_runner.py -v`  
Expected: PASS

- [ ] **Step 7: 提交安全查询层**

```bash
git add app/security/sql_guard.py app/db/query_runner.py tests/security/test_sql_guard.py tests/db/test_query_runner.py
git commit -m "feat: add sql guard and safe query runner"
```

---

### Task 6: 即时问答流（路由、执行、脱敏、回复格式）

**Files:**
- Create: `app/security/masking.py`
- Create: `app/security/rate_limit.py`
- Create: `app/workflow/router.py`
- Create: `app/workflow/query_workflow.py`
- Create: `app/formatting/reply_builder.py`
- Create: `tests/workflow/test_router.py`
- Create: `tests/workflow/test_query_workflow.py`
- Create: `tests/formatting/test_reply_builder.py`
- Test: `tests/workflow/test_router.py`
- Test: `tests/workflow/test_query_workflow.py`
- Test: `tests/formatting/test_reply_builder.py`

- [ ] **Step 1: 写失败测试，先锁定何时走 dashboard**

```python
# tests/workflow/test_router.py
from app.workflow.router import choose_workflow


def test_choose_dashboard_for_comparison_question():
    route = choose_workflow("上周同比去年销售怎么样？", dashboard_threshold_days=7)
    assert route == "dashboard"



def test_choose_query_for_simple_metric_question():
    route = choose_workflow("最近有多少新用户？", dashboard_threshold_days=7)
    assert route == "query"
```

- [ ] **Step 2: 再写失败测试，锁定手机号脱敏与表格格式**

```python
# tests/formatting/test_reply_builder.py
from app.formatting.reply_builder import format_table_reply



def test_table_reply_masks_phone_numbers():
    text = format_table_reply(
        answer="查到 1 条记录",
        columns=["姓名", "手机号"],
        rows=[{"姓名": "张三", "手机号": "13812341234"}],
    )
    assert "138****1234" in text
```

- [ ] **Step 3: 运行测试，确认失败**

Run: `pytest tests/workflow/test_router.py tests/formatting/test_reply_builder.py -v`  
Expected: FAIL with missing modules

- [ ] **Step 4: 实现路由、脱敏和回复格式化**

```python
# app/workflow/router.py
ANALYSIS_KEYWORDS = ("同比", "环比", "趋势", "原因", "建议", "退款", "投诉")



def choose_workflow(question: str, dashboard_threshold_days: int) -> str:
    if any(word in question for word in ANALYSIS_KEYWORDS):
        return "dashboard"
    return "query"
```

```python
# app/security/masking.py
import re

PHONE_RE = re.compile(r"(?<!\d)(1\d{2})(\d{4})(\d{4})(?!\d)")



def mask_value(value):
    if isinstance(value, str):
        value = PHONE_RE.sub(r"\1****\3", value)
        if len(value) == 3:
            return value[0] + "*" + value[-1]
    return value
```

```python
# app/formatting/reply_builder.py
from app.security.masking import mask_value



def format_table_reply(answer: str, columns: list[str], rows: list[dict]) -> str:
    lines = [answer]
    if not rows:
        return answer + "\n（未查到数据）"
    header = " | ".join(columns)
    lines.append(header)
    lines.append("-|-".join(["---"] * len(columns)))
    for row in rows[:10]:
        lines.append(" | ".join(str(mask_value(row.get(col, ""))) for col in columns))
    return "\n".join(lines)
```

- [ ] **Step 5: 写并实现 query workflow 集成测试**

```python
# tests/workflow/test_query_workflow.py
from types import SimpleNamespace

from app.workflow.query_workflow import QueryWorkflow



def test_query_workflow_returns_formatted_answer():
    llm = SimpleNamespace(build_query_plan=lambda *_: SimpleNamespace(candidate_sql="SELECT 42 AS total", clarification_needed=False))
    runner = SimpleNamespace(run=lambda sql: (["total"], [{"total": 42}]))
    summarizer = SimpleNamespace(summarize=lambda **_: "最近新增用户 42 人")

    workflow = QueryWorkflow(llm=llm, query_runner=runner, summarizer=summarizer)
    reply = workflow.answer("最近有多少新用户？")

    assert "42" in reply
```

- [ ] **Step 6: 跑测试并修到全绿**

Run: `pytest tests/workflow/test_router.py tests/workflow/test_query_workflow.py tests/formatting/test_reply_builder.py -v`  
Expected: PASS

- [ ] **Step 7: 提交即时问答流**

```bash
git add app/security/masking.py app/security/rate_limit.py app/workflow/router.py app/workflow/query_workflow.py app/formatting/reply_builder.py tests/workflow/test_router.py tests/workflow/test_query_workflow.py tests/formatting/test_reply_builder.py
git commit -m "feat: add immediate query workflow"
```

---

### Task 7: 分析看板流与网站发布适配

**Files:**
- Create: `app/dashboard/payloads.py`
- Create: `app/dashboard/publisher.py`
- Create: `app/workflow/dashboard_workflow.py`
- Create: `tests/dashboard/test_payloads.py`
- Create: `tests/dashboard/test_publisher.py`
- Create: `templates/dashboard_payload.example.json`
- Test: `tests/dashboard/test_payloads.py`
- Test: `tests/dashboard/test_publisher.py`

- [ ] **Step 1: 写失败测试，先锁定 JSON payload 结构**

```python
# tests/dashboard/test_payloads.py
from app.dashboard.payloads import DashboardPayload



def test_dashboard_payload_serializes_required_sections():
    payload = DashboardPayload(
        title="上周销售同比分析",
        time_range={"label": "上周 vs 去年同期"},
        summary_metrics=[{"label": "销售额", "value": 12345}],
        trend_series=[],
        comparison_metrics=[],
        top_items=[],
        reason_breakdown=[],
        ai_summary="销售同比上升 12%",
        ai_suggestions=["继续关注退款原因"],
    )
    data = payload.model_dump()
    assert data["title"] == "上周销售同比分析"
```

- [ ] **Step 2: 再写失败测试，锁定本地发布生成 URL**

```python
# tests/dashboard/test_publisher.py
from pathlib import Path

from app.dashboard.publisher import LocalDashboardPublisher



def test_local_publisher_writes_json_and_returns_public_url(tmp_path: Path):
    publisher = LocalDashboardPublisher(output_dir=tmp_path, public_base_url="https://site.example/dashboards")
    url = publisher.publish("sales-weekly", {"title": "demo"})
    assert url == "https://site.example/dashboards/sales-weekly.json"
    assert (tmp_path / "sales-weekly.json").exists()
```

- [ ] **Step 3: 运行测试，确认失败**

Run: `pytest tests/dashboard/test_payloads.py tests/dashboard/test_publisher.py -v`  
Expected: FAIL with missing payload/publisher implementation

- [ ] **Step 4: 实现 payload 模型与本地发布器**

```python
# app/dashboard/payloads.py
from pydantic import BaseModel, Field


class DashboardPayload(BaseModel):
    title: str
    generated_at: str | None = None
    time_range: dict
    summary_metrics: list[dict] = Field(default_factory=list)
    trend_series: list[dict] = Field(default_factory=list)
    comparison_metrics: list[dict] = Field(default_factory=list)
    top_items: list[dict] = Field(default_factory=list)
    reason_breakdown: list[dict] = Field(default_factory=list)
    ai_summary: str
    ai_suggestions: list[str] = Field(default_factory=list)
```

```python
# app/dashboard/publisher.py
import json
from pathlib import Path


class LocalDashboardPublisher:
    def __init__(self, output_dir: Path, public_base_url: str):
        self.output_dir = output_dir
        self.public_base_url = public_base_url.rstrip("/")
        self.output_dir.mkdir(parents=True, exist_ok=True)

    def publish(self, slug: str, payload: dict) -> str:
        path = self.output_dir / f"{slug}.json"
        path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
        return f"{self.public_base_url}/{slug}.json"
```

- [ ] **Step 5: 实现 dashboard workflow，把查询结果 + AI 建议串起来**

```python
# app/workflow/dashboard_workflow.py
from datetime import datetime

from app.dashboard.payloads import DashboardPayload


class DashboardWorkflow:
    def __init__(self, llm, query_runner, publisher):
        self.llm = llm
        self.query_runner = query_runner
        self.publisher = publisher

    def answer(self, question: str) -> tuple[str, str]:
        plan = self.llm.build_query_plan([{"role": "user", "content": question}])
        columns, rows = self.query_runner.run(plan.candidate_sql)
        summary = self.llm.build_summary(question=question, columns=columns, rows=rows)
        payload = DashboardPayload(
            title=question,
            generated_at=datetime.utcnow().isoformat(),
            time_range=plan.time_range,
            summary_metrics=rows[:6],
            ai_summary=summary.answer,
            ai_suggestions=summary.suggestions,
        )
        slug = "dashboard-" + datetime.utcnow().strftime("%Y%m%d%H%M%S")
        url = self.publisher.publish(slug, payload.model_dump())
        return summary.answer, url
```

- [ ] **Step 6: 跑测试并确认看板流全绿**

Run: `pytest tests/dashboard/test_payloads.py tests/dashboard/test_publisher.py -v`  
Expected: PASS

- [ ] **Step 7: 提交看板流**

```bash
git add app/dashboard/payloads.py app/dashboard/publisher.py app/workflow/dashboard_workflow.py tests/dashboard/test_payloads.py tests/dashboard/test_publisher.py templates/dashboard_payload.example.json
git commit -m "feat: add dashboard workflow and publisher"
```

---

### Task 8: 应用装配、审计日志、限流与命令行脚本

**Files:**
- Create: `app/audit/logger.py`
- Create: `app/logging_config.py`
- Modify: `app/main.py`
- Modify: `scripts/run_bot.py`
- Create: `scripts/smoke_query.py`
- Create: `tests/audit/test_logger.py`
- Create: `tests/security/test_rate_limit.py`
- Test: `tests/audit/test_logger.py`
- Test: `tests/security/test_rate_limit.py`

- [ ] **Step 1: 写失败测试，先锁定审计日志不会写出敏感明文**

```python
# tests/audit/test_logger.py
from app.audit.logger import redact_payload



def test_redact_payload_masks_sensitive_text():
    payload = {"question": "查手机号 13812341234", "rows": [{"手机号": "13812341234"}]}
    redacted = redact_payload(payload)
    assert "138****1234" in str(redacted)
    assert "13812341234" not in str(redacted)
```

- [ ] **Step 2: 运行测试，确认失败**

Run: `pytest tests/audit/test_logger.py tests/security/test_rate_limit.py -v`  
Expected: FAIL with missing logger/rate-limit implementations

- [ ] **Step 3: 实现审计日志与轻量限流**

```python
# app/security/rate_limit.py
from collections import defaultdict, deque
from time import time


class SlidingWindowRateLimiter:
    def __init__(self, max_requests: int, window_seconds: int):
        self.max_requests = max_requests
        self.window_seconds = window_seconds
        self.events = defaultdict(deque)

    def allow(self, key: str) -> bool:
        now = time()
        dq = self.events[key]
        while dq and now - dq[0] > self.window_seconds:
            dq.popleft()
        if len(dq) >= self.max_requests:
            return False
        dq.append(now)
        return True
```

```python
# app/audit/logger.py
from app.security.masking import mask_value



def redact_payload(payload: dict) -> dict:
    def _walk(value):
        if isinstance(value, dict):
            return {k: _walk(v) for k, v in value.items()}
        if isinstance(value, list):
            return [_walk(v) for v in value]
        return mask_value(value)
    return _walk(payload)
```

- [ ] **Step 4: 在 `app/main.py` 装配 settings、LLM、DB、workflow 和 processor**

```python
# app/main.py
from app.config import load_settings
from app.db.engine import build_engine
from app.llm.client import QwenClient
from app.workflow.router import choose_workflow



def create_app():
    settings = load_settings()
    engine = build_engine(settings)
    llm = QwenClient(settings)
    return {
        "settings": settings,
        "engine": engine,
        "llm": llm,
        "router": choose_workflow,
    }
```

- [ ] **Step 5: 跑测试并验证 CLI 脚本可执行**

Run:
1. `pytest tests/audit/test_logger.py tests/security/test_rate_limit.py -v`
2. `python scripts/smoke_query.py --question "最近有多少新用户？" --dry-run`

Expected:
- tests PASS
- dry run prints a route / generated plan preview without contacting DingTalk

- [ ] **Step 6: 提交装配与硬化**

```bash
git add app/audit/logger.py app/logging_config.py app/main.py scripts/run_bot.py scripts/smoke_query.py tests/audit/test_logger.py tests/security/test_rate_limit.py
git commit -m "feat: wire application assembly and safeguards"
```

---

### Task 9: 端到端伪集成测试与真实环境验收

**Files:**
- Create: `tests/e2e/test_bot_pipeline.py`
- Modify: `README.md`
- Modify: `.env.example`
- Test: `tests/e2e/test_bot_pipeline.py`

- [ ] **Step 1: 写失败的 E2E 测试，覆盖“即时问答”和“dashboard 链接”两条路径**

```python
# tests/e2e/test_bot_pipeline.py
from app.workflow.router import choose_workflow



def test_router_selects_query_path_for_simple_question():
    assert choose_workflow("最近有多少新用户？", dashboard_threshold_days=7) == "query"



def test_router_selects_dashboard_path_for_analysis_question():
    assert choose_workflow("上周同比去年销售怎么样？", dashboard_threshold_days=7) == "dashboard"
```

- [ ] **Step 2: 运行完整测试套件，先看到失败点**

Run: `pytest -q`  
Expected: FAIL only if there are remaining integration gaps; fix them before proceeding.

- [ ] **Step 3: 修补所有失败并跑完整测试套件到全绿**

Run: `pytest -q`  
Expected: all tests PASS

- [ ] **Step 4: 做真实环境 smoke 验证（手工）**

Run:
1. `python scripts/refresh_metadata.py`
2. `python scripts/smoke_query.py --question "最近有多少新用户？"`
3. `python scripts/smoke_query.py --question "上周同比去年销售怎么样？"`
4. `python scripts/run_bot.py`

Expected:
- metadata cache refreshed
- 第一条返回文本摘要 + 表格
- 第二条返回摘要 + dashboard JSON URL
- 机器人在钉钉群中被 @ 后能回消息

- [ ] **Step 5: 更新 README 的实际启动说明和故障排查**

```markdown
## Manual verification
- 如果 Stream 连不上，先检查企业应用是否启用了 Stream Mode、Client ID/Secret 是否正确。
- 如果 metadata 刷新失败，先执行最小 SQL 验证数据库连通性。
- 如果 dashboard URL 可写但网站不显示，先检查网站模板读取的 JSON 路径是否一致。
```

- [ ] **Step 6: 提交 MVP 完成状态**

```bash
git add README.md .env.example tests/e2e/test_bot_pipeline.py
git commit -m "feat: finish mvp verification flow"
```

---

## Manual Acceptance Checklist

- [ ] 能从现有 `机器人配置.env`、`千问key.env`、`数据库链接.txt`、`数据库账号.txt`、`数据库密码.env` 读取配置
- [ ] Stream Mode 可以在本机连上钉钉
- [ ] 能扫描 `bigdata` 库元数据并缓存到本地
- [ ] 能回答“最近有多少新用户？”
- [ ] 能回答“最近投诉的人多不多？”
- [ ] 能对“上周同比去年销售怎么样？”返回摘要 + 看板链接
- [ ] 返回中手机号等敏感字段部分脱敏
- [ ] 不显示实际 SQL
- [ ] 非 SELECT / 多语句 / 系统库访问都会被拦截
- [ ] 审计日志中不保留敏感明文结果

## References for Implementation

- 钉钉 Stream 概述（开发者百科）：https://opensource.dingtalk.com/developerpedia/docs/learn/stream/overview/
- 钉钉 Python 机器人 Stream 教程：https://opensource.dingtalk.com/developerpedia/docs/explore/tutorials/stream/bot/python/build-bot/
- 钉钉 Stream 协议补充：https://opensource.dingtalk.com/developerpedia/docs/learn/stream/protocol/
- 阿里百炼 OpenAI 兼容 Chat：https://help.aliyun.com/zh/model-studio/compatibility-of-openai-with-dashscope

