import os
import sys
import types

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
import services.chat as chat_service


def test_summarize_result_includes_history_and_insight_guidance(monkeypatch):
    captured = {}

    def fake_create(**kwargs):
        captured.update(kwargs)
        return types.SimpleNamespace(
            choices=[
                types.SimpleNamespace(
                    message=types.SimpleNamespace(content="环比增长10%，拉新有所回暖。")
                )
            ]
        )

    monkeypatch.setattr(chat_service.client.chat.completions, "create", fake_create)

    history = [
        {"role": "user", "content": "上周注册用户多少"},
        {"role": "assistant", "content": "上周注册用户1200人。"},
    ]
    table_data = {
        "columns": ["指标", "数值", "环比"],
        "rows": [["注册用户", "1200", "+10%"]],
    }

    answer = chat_service._summarize_result("环比呢", table_data, history)

    assert answer == "环比增长10%，拉新有所回暖。"
    assert "业务洞察" in captured["messages"][0]["content"]
    assert "最近对话上下文" in captured["messages"][1]["content"]
    assert "上周注册用户多少" in captured["messages"][1]["content"]


def test_chat_passes_history_to_summary(monkeypatch):
    history = [
        {"role": "user", "content": "上周注册用户多少"},
        {"role": "assistant", "content": "上周注册用户1200人。"},
    ]

    monkeypatch.setattr(chat_service, "_generate_sql", lambda message, history: "SELECT 1")
    monkeypatch.setattr(chat_service, "validate_sql", lambda sql: True)
    monkeypatch.setattr(
        chat_service,
        "execute_query",
        lambda sql: {"columns": ["注册用户"], "rows": [["1200"]]},
    )

    def fake_summarize(message, table_data, summary_history):
        assert summary_history == history
        return "上周注册用户1200人，环比增长10%，拉新回暖。"

    monkeypatch.setattr(chat_service, "_summarize_result", fake_summarize)

    result = chat_service.chat("环比呢", history)

    assert result["answer"] == "上周注册用户1200人，环比增长10%，拉新回暖。"
    assert result["table"] == {"columns": ["注册用户"], "rows": [["1200"]]}


def test_summarize_result_forbids_making_up_trends_without_comparison_data(monkeypatch):
    captured = {}

    def fake_create(**kwargs):
        captured.update(kwargs)
        return types.SimpleNamespace(
            choices=[
                types.SimpleNamespace(
                    message=types.SimpleNamespace(content="当前注册用户1200人。")
                )
            ]
        )

    monkeypatch.setattr(chat_service.client.chat.completions, "create", fake_create)

    table_data = {
        "columns": ["注册用户"],
        "rows": [["1200"]],
    }

    answer = chat_service._summarize_result("注册用户多少", table_data, [])

    assert answer == "当前注册用户1200人。"
    assert "不要编造趋势" in captured["messages"][0]["content"]


def test_generate_sql_adds_follow_up_scope_for_ratio_question(monkeypatch):
    captured = {}

    def fake_create(**kwargs):
        captured.update(kwargs)
        return types.SimpleNamespace(
            choices=[types.SimpleNamespace(message=types.SimpleNamespace(content="SELECT 1"))]
        )

    monkeypatch.setattr(chat_service, "_load_prompt", lambda _: "基础提示")
    monkeypatch.setattr(chat_service.client.chat.completions, "create", fake_create)

    history = [
        {"role": "user", "content": "上周注册用户多少"},
        {"role": "assistant", "content": "上周注册用户1200人。"},
    ]

    chat_service._generate_sql("环比呢", history)

    contents = "\n".join(message["content"] for message in captured["messages"])
    assert "上一轮用户问题：上周注册用户多少" in contents
    assert "必须继承上一轮已经确定的统计对象、时间范围、筛选条件、分组维度" in contents
    assert "如果当前追问只是在补充分析方式（如环比/同比/趋势）" in contents
    assert "不要改写成最新一期、本周、最近几周" in contents


def test_generate_sql_adds_follow_up_scope_for_customer_service_filter(monkeypatch):
    captured = {}

    def fake_create(**kwargs):
        captured.update(kwargs)
        return types.SimpleNamespace(
            choices=[types.SimpleNamespace(message=types.SimpleNamespace(content="SELECT 1"))]
        )

    monkeypatch.setattr(chat_service, "_load_prompt", lambda _: "基础提示")
    monkeypatch.setattr(chat_service.client.chat.completions, "create", fake_create)

    history = [
        {"role": "user", "content": "最近用户反馈怎么样"},
        {"role": "assistant", "content": "最近7天退款类和使用指导类问题较多。"},
    ]

    chat_service._generate_sql("退款类呢", history)

    contents = "\n".join(message["content"] for message in captured["messages"])
    assert "上一轮用户问题：最近用户反馈怎么样" in contents
    assert "必须继承上一轮已经确定的统计对象、时间范围、筛选条件、分组维度" in contents
    assert "如果当前追问是在上一轮结果上缩小范围（如退款类、投诉类、某系列、某科目）" in contents
    assert "只新增对应筛选条件，不要改成趋势查询或切换主题" in contents


def test_is_follow_up_question_supports_short_comparison_without_ne():
    history = [{"role": "user", "content": "上周注册用户多少"}]

    assert chat_service._is_follow_up_question("和上周比一下", history) is True



def test_is_follow_up_question_supports_short_filter_without_ne():
    history = [{"role": "user", "content": "最近用户反馈怎么样"}]

    assert chat_service._is_follow_up_question("退款类有多少", history) is True



def test_is_follow_up_question_ignores_new_explicit_scope():
    history = [{"role": "user", "content": "上周注册用户多少"}]

    assert chat_service._is_follow_up_question("这个月销售额多少", history) is False



def test_is_follow_up_question_ignores_short_new_metric_question():
    history = [{"role": "user", "content": "上周注册用户多少"}]

    assert chat_service._is_follow_up_question("DAU多少", history) is False



def test_is_follow_up_question_ignores_independent_group_query():
    history = [{"role": "user", "content": "上周注册用户多少"}]

    assert chat_service._is_follow_up_question("按周活跃用户多少", history) is False



def test_generate_sql_rewrites_ratio_follow_up_into_explicit_scoped_request(monkeypatch):
    captured = {}

    def fake_create(**kwargs):
        captured.update(kwargs)
        return types.SimpleNamespace(
            choices=[types.SimpleNamespace(message=types.SimpleNamespace(content="SELECT 1"))]
        )

    monkeypatch.setattr(chat_service.client.chat.completions, "create", fake_create)

    history = [
        {"role": "user", "content": "上周注册用户多少"},
        {"role": "assistant", "content": "上周注册用户1200人。"},
    ]

    chat_service._generate_sql("环比呢", history)

    rewritten = captured["messages"][-1]["content"]
    assert "基于上一轮用户问题“上周注册用户多少”" in rewritten
    assert "当前仅补充“环比”这一分析要求" in rewritten
    assert "不要改成最新一期、本周、最近几周等新口径" in rewritten



def test_generate_sql_rewrites_filter_follow_up_into_explicit_scoped_request(monkeypatch):
    captured = {}

    def fake_create(**kwargs):
        captured.update(kwargs)
        return types.SimpleNamespace(
            choices=[types.SimpleNamespace(message=types.SimpleNamespace(content="SELECT 1"))]
        )

    monkeypatch.setattr(chat_service.client.chat.completions, "create", fake_create)

    history = [
        {"role": "user", "content": "最近用户反馈怎么样"},
        {"role": "assistant", "content": "最近7天退款类和使用指导类问题较多。"},
    ]

    chat_service._generate_sql("退款类有多少", history)

    rewritten = captured["messages"][-1]["content"]
    assert "基于上一轮用户问题“最近用户反馈怎么样”" in rewritten
    assert "仅在上一轮结果基础上追加与“退款类有多少”对应的筛选条件" in rewritten
    assert "不要切换主题或改成趋势查询" in rewritten



def test_generate_sql_rewrites_dimension_follow_up_into_scoped_grouping_request(monkeypatch):
    captured = {}

    def fake_create(**kwargs):
        captured.update(kwargs)
        return types.SimpleNamespace(
            choices=[types.SimpleNamespace(message=types.SimpleNamespace(content="SELECT 1"))]
        )

    monkeypatch.setattr(chat_service.client.chat.completions, "create", fake_create)

    history = [
        {"role": "user", "content": "3月销售总额"},
        {"role": "assistant", "content": "3月销售总额54万元。"},
    ]

    chat_service._generate_sql("按周分别多少", history)

    rewritten = captured["messages"][-1]["content"]
    assert "基于上一轮用户问题“3月销售总额”" in rewritten
    assert "改为按“按周分别多少”对应的维度重新分组或拆分" in rewritten
    assert "保持上一轮的统计主题、时间范围和筛选条件不变" in rewritten



def test_nl2sql_prompt_removes_conflicting_follow_up_examples():
    prompt = chat_service._load_prompt("nl2sql.txt")

    assert "用户: 那环比呢？（上文查的是活跃用户）" not in prompt
    assert "用户: 和上周比呢（上文查的是销售额3月）" not in prompt
    assert "用户: 那环比呢？（上文查的是上周注册用户多少）" in prompt
    assert "用户: 退款类呢？（上文查的是最近用户反馈怎么样）" in prompt
    assert "用户: 按周分别多少（上文查的是3月销售）" in prompt
    assert "如果当前追问是在上一轮结果上改分组维度（如按周、按系列、按科目）" in prompt



def test_chat_preserves_follow_up_scope_in_sql_fix_retry(monkeypatch):
    captured = {}

    history = [
        {"role": "user", "content": "上周注册用户多少"},
        {"role": "assistant", "content": "上周注册用户1200人。"},
    ]

    monkeypatch.setattr(chat_service, "_generate_sql", lambda message, history: "SELECT bad_sql")
    monkeypatch.setattr(chat_service, "execute_query", lambda sql: {"columns": ["注册用户"], "rows": [["1200"]]})
    monkeypatch.setattr(chat_service, "_summarize_result", lambda message, table_data, history: "上周注册用户1200人。")

    def fake_validate(sql):
        return sql != "SELECT bad_sql"

    def fake_create(**kwargs):
        captured.update(kwargs)
        return types.SimpleNamespace(
            choices=[types.SimpleNamespace(message=types.SimpleNamespace(content="SELECT 1"))]
        )

    monkeypatch.setattr(chat_service, "validate_sql", fake_validate)
    monkeypatch.setattr(chat_service.client.chat.completions, "create", fake_create)

    result = chat_service.chat("环比呢", history)

    assert result["answer"] == "上周注册用户1200人。"
    contents = "\n".join(message["content"] for message in captured["messages"])
    assert "上一轮用户问题：上周注册用户多少" in contents
    assert "基于上一轮用户问题“上周注册用户多少”" in contents



def test_chat_preserves_follow_up_scope_in_weekly_retry(monkeypatch):
    captured = {}

    history = [
        {"role": "user", "content": "上周注册用户多少"},
        {"role": "assistant", "content": "上周注册用户1200人。"},
    ]

    monkeypatch.setattr(chat_service, "_generate_sql", lambda message, history: "SELECT * FROM dws.dws_active_user_report_week")
    monkeypatch.setattr(chat_service, "validate_sql", lambda sql: True)

    execute_calls = {"count": 0}

    def fake_execute(sql):
        execute_calls["count"] += 1
        if execute_calls["count"] == 1:
            return {"columns": ["注册用户"], "rows": []}
        return {"columns": ["注册用户"], "rows": [["1200"]]}

    monkeypatch.setattr(chat_service, "execute_query", fake_execute)
    monkeypatch.setattr(chat_service, "_summarize_result", lambda message, table_data, history: "上周注册用户1200人。")

    # Mock cache to avoid interference from prior tests
    import services.query_cache as qc
    monkeypatch.setattr(qc, "get_cached_result", lambda sql: None)
    monkeypatch.setattr(qc, "set_cached_result", lambda sql, data: None)

    def fake_create(**kwargs):
        captured.update(kwargs)
        return types.SimpleNamespace(
            choices=[types.SimpleNamespace(message=types.SimpleNamespace(content="SELECT 1"))]
        )

    monkeypatch.setattr(chat_service.client.chat.completions, "create", fake_create)

    result = chat_service.chat("环比呢", history)

    assert result["answer"] == "上周注册用户1200人。"
    contents = "\n".join(message["content"] for message in captured["messages"])
    assert "上一轮用户问题：上周注册用户多少" in contents
    assert "基于上一轮用户问题“上周注册用户多少”" in contents
