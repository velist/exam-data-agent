import os
import re
import logging
from datetime import date
from openai import OpenAI
from config import QWEN_API_KEY, QWEN_BASE_URL, QWEN_MODEL, MAX_INPUT_LENGTH
from sql_validator import validate_sql
from db import execute_query

logger = logging.getLogger("chat")
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(name)s] %(message)s")

PROMPTS_DIR = os.path.join(os.path.dirname(__file__), '..', 'prompts')

client = OpenAI(api_key=QWEN_API_KEY, base_url=QWEN_BASE_URL)


def _load_prompt(name: str) -> str:
    path = os.path.join(PROMPTS_DIR, name)
    with open(path, "r", encoding="utf-8") as f:
        return f.read()


def _clean_sql_response(sql: str) -> str:
    """清理千问返回的SQL（去掉markdown标记等）"""
    sql = sql.strip()
    if sql.startswith("```"):
        lines = sql.split("\n")
        sql = "\n".join(lines[1:-1] if lines[-1].strip() == "```" else lines[1:])
    return sql.strip().rstrip(";")


def _get_last_history_content(history: list[dict], role: str) -> str:
    for item in reversed(history):
        if item.get("role") == role and item.get("content"):
            return item["content"]
    return ""


def _is_explicit_new_scope(message: str) -> bool:
    patterns = (
        r"^(今天|昨天|本周|上周|本月|上月|今年|去年)",
        r"^最近\d*天",
        r"^近\d+(天|周|月|年)",
        r"^这个月",
        r"^上个月",
        r"^\d+月",
        r"^\d{4}-\d{2}",
    )
    return any(re.search(pattern, message) for pattern in patterns)



def _is_follow_up_question(message: str, history: list[dict]) -> bool:
    if not history:
        return False

    normalized = message.strip()
    if not normalized:
        return False

    if _is_explicit_new_scope(normalized):
        return False

    explicit_markers = (
        "环比",
        "同比",
        "趋势",
        "和上周比",
        "和去年比",
        "比一下",
        "只看",
        "其中",
        "退款类",
        "投诉类",
        "某系列",
        "某科目",
        "这个指标",
        "那个指标",
        "它",
    )
    if any(marker in normalized for marker in explicit_markers):
        return True

    if _is_dimension_follow_up(normalized):
        return True

    return len(normalized) <= 12 and normalized.endswith("呢")



def _normalize_follow_up_analysis_label(message: str) -> str:
    if "环比" in message:
        return "环比"
    if "同比" in message:
        return "同比"
    if "趋势" in message:
        return "趋势"
    return message.strip().rstrip("呢吗？?")



def _is_dimension_follow_up(message: str) -> bool:
    return bool(re.match(r"^按(周|月|天|系列|科目)(分别)?(多少|看|看一下|拆开|拆分|统计)?$", message.strip()))



def _rewrite_follow_up_message(message: str, history: list[dict]) -> str:
    if not _is_follow_up_question(message, history):
        return message

    last_user_message = _get_last_history_content(history, "user")
    if not last_user_message:
        return message

    if any(keyword in message for keyword in ("环比", "同比", "趋势", "比一下", "比呢")):
        analysis_label = _normalize_follow_up_analysis_label(message)
        return (
            f"基于上一轮用户问题“{last_user_message}”，当前仅补充“{analysis_label}”这一分析要求。"
            "请保持上一轮的统计对象、时间范围、筛选条件、分组维度不变，"
            "不要改成最新一期、本周、最近几周等新口径，只输出SQL。"
        )

    if _is_dimension_follow_up(message):
        return (
            f"基于上一轮用户问题“{last_user_message}”，当前改为按“{message}”对应的维度重新分组或拆分。"
            "请保持上一轮的统计主题、时间范围和筛选条件不变，只改变分组维度，只输出SQL。"
        )

    return (
        f"基于上一轮用户问题“{last_user_message}”，当前仅在上一轮结果基础上追加与“{message}”对应的筛选条件。"
        "请保留上一轮的时间范围、统计主题和分组维度，不要切换主题或改成趋势查询，只输出SQL。"
    )



def _build_follow_up_scope_prompt(message: str, history: list[dict]) -> str:
    if not _is_follow_up_question(message, history):
        return ""

    last_user_message = _get_last_history_content(history, "user")
    if not last_user_message:
        return ""

    last_assistant_message = _get_last_history_content(history, "assistant") or "无"
    return (
        "当前问题是对上一轮查询结果的追问，请严格沿用上轮口径。\n"
        f"上一轮用户问题：{last_user_message}\n"
        f"上一轮助手回答：{last_assistant_message}\n"
        "你必须继承上一轮已经确定的统计对象、时间范围、筛选条件、分组维度。\n"
        "如果当前追问只是在补充分析方式（如环比/同比/趋势），请在同一统计对象和同一时间口径上补充分析，不要改写成最新一期、本周、最近几周等新的时间口径。\n"
        "如果当前追问是在上一轮结果上缩小范围（如退款类、投诉类、某系列、某科目），只新增对应筛选条件，不要改成趋势查询或切换主题。\n"
        "如果当前追问是在上一轮结果上改分组维度（如按周、按系列、按科目），应保留统计主题、时间范围和筛选条件，只改变分组维度。\n"
        "只有当用户明确提出新的时间、对象、维度时，才允许改变查询口径。"
    )


def _build_llm_messages(message: str, history: list[dict], system_prompt: str | None = None) -> list[dict]:
    resolved_system_prompt = system_prompt or _load_prompt("nl2sql.txt").replace("{today}", date.today().isoformat())
    messages = [{"role": "system", "content": resolved_system_prompt}]
    follow_up_scope_prompt = _build_follow_up_scope_prompt(message, history)
    if follow_up_scope_prompt:
        messages.append({"role": "system", "content": follow_up_scope_prompt})
    for h in history[-10:]:
        messages.append(h)
    messages.append({"role": "user", "content": _rewrite_follow_up_message(message, history)})
    return messages


def _generate_sql(message: str, history: list[dict]) -> str:
    """调用千问将自然语言转为SQL"""
    messages = _build_llm_messages(message, history)

    response = client.chat.completions.create(
        model=QWEN_MODEL,
        messages=messages,
        temperature=0,
        max_tokens=2500,  # 增加到 2500 以支持复杂的多指标同比查询
    )
    return _clean_sql_response(response.choices[0].message.content)


def _summarize_result(message: str, table_data: dict, history: list[dict] | None = None) -> str:
    """调用千问对查询结果生成简短总结和洞察"""
    if not table_data["rows"]:
        return "查询结果为空，没有找到匹配的数据。"

    history = history or []
    header = " | ".join(table_data["columns"])
    rows_text = "\n".join([" | ".join(row) for row in table_data["rows"][:20]])
    data_text = f"{header}\n{rows_text}"
    history_text = "\n".join([f"{item['role']}: {item['content']}" for item in history[-6:]]) or "无"

    response = client.chat.completions.create(
        model=QWEN_MODEL,
        messages=[
            {"role": "system", "content": "你是考试宝典的数据分析助手。用户问了一个数据问题，下面是查询结果。请用简洁的中文（2-3句话）回答用户的问题：先给出核心数据，再补一句趋势判断或简短洞察。若有环比、同比、趋势字段，优先点出变化。如果结果里没有环比、同比、趋势或可比较字段，不要推断趋势、原因或业务影响，只做保守表述。不要空话。"},
            {"role": "user", "content": f"最近对话上下文：\n{history_text}\n\n当前问题：{message}\n\n查询结果：\n{data_text}\n\n请输出：核心结论 + 简短洞察。"},
        ],
        temperature=0.3,
        max_tokens=220,
    )
    return response.choices[0].message.content.strip()


def chat(message: str, history: list[dict] = None) -> dict:
    """对话查询主函数。"""
    if history is None:
        history = []

    if len(message) > MAX_INPUT_LENGTH:
        return {"error": True, "code": "INVALID_INPUT", "message": f"输入过长，请控制在{MAX_INPUT_LENGTH}字以内"}

    # 1. 生成SQL
    try:
        sql = _generate_sql(message, history)
        logger.info(f"用户问题: {message}")
        logger.info(f"生成SQL: {sql}")
    except Exception as e:
        logger.error(f"LLM调用失败: {e}")
        return {"error": True, "code": "LLM_ERROR", "message": "AI服务暂时不可用，请稍后重试"}

    # 2. 校验SQL
    if not validate_sql(sql):
        logger.warning(f"SQL校验失败: {sql}")
        try:
            fix_messages = _build_llm_messages(
                message,
                history,
                "上一次生成的SQL不合规。请重新生成一条安全的SELECT查询。只使用dws库和bigdata.v_ws_salesflow_ex表。只输出SQL，不要解释。",
            )
            fix_messages.append({"role": "system", "content": f"不合规SQL：{sql}"})
            response = client.chat.completions.create(model=QWEN_MODEL, messages=fix_messages, temperature=0, max_tokens=2500)
            sql = _clean_sql_response(response.choices[0].message.content)
            if not validate_sql(sql):
                return {"error": True, "code": "SQL_FAILED", "message": "无法生成合规的查询语句，请换个方式描述您的问题"}
        except Exception:
            return {"error": True, "code": "SQL_FAILED", "message": "无法生成合规的查询语句，请换个方式描述您的问题"}

    # 3. 执行SQL
    try:
        table_data = execute_query(sql)
        logger.info(f"查询结果: {len(table_data['rows'])}行, 列: {table_data['columns']}")
    except Exception as e:
        error_msg = str(e)
        if "max_execution_time" in error_msg.lower() or "timeout" in error_msg.lower():
            return {"error": True, "code": "SQL_TIMEOUT", "message": "查询超时，请尝试缩小查询范围或指定更具体的条件"}
        return {"error": True, "code": "SQL_FAILED", "message": "查询执行失败，请换个方式描述您的问题"}

    # 3.5 空结果智能重试：如果查周报表返回空，尝试用日表重新查询
    if not table_data["rows"] and "_report_week" in sql:
        logger.info("周报表返回空，尝试用日表重新查询")
        try:
            retry_messages = _build_llm_messages(message, history)
            retry_messages.append(
                {"role": "system", "content": "周报表没有数据（可能本周/本期还未结束），请改用日表 dws.dws_user_daily_quiz_stats_day 按日期范围查询。只输出SQL。"}
            )
            response = client.chat.completions.create(model=QWEN_MODEL, messages=retry_messages, temperature=0, max_tokens=2500)
            retry_sql = _clean_sql_response(response.choices[0].message.content)
            logger.info(f"重试SQL: {retry_sql}")
            if validate_sql(retry_sql):
                retry_data = execute_query(retry_sql)
                if retry_data["rows"]:
                    table_data = retry_data
                    sql = retry_sql
                    logger.info(f"重试成功: {len(table_data['rows'])}行")
        except Exception as e:
            logger.warning(f"重试失败: {e}")

    # 4. 生成总结
    try:
        answer = _summarize_result(message, table_data, history)
    except Exception:
        answer = "查询完成，请查看下方数据表格。"

    return {"answer": answer, "table": table_data}
