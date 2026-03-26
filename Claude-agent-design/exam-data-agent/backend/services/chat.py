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


def _clean_sql_response(sql: str) -> str:
    """清理千问返回的SQL（去掉markdown标记等）"""
    sql = sql.strip()
    if sql.startswith("```"):
        lines = sql.split("\n")
        sql = "\n".join(lines[1:-1] if lines[-1].strip() == "```" else lines[1:])
    return sql.strip().rstrip(";")


def _generate_sql(message: str, history: list[dict]) -> str:
    """调用千问将自然语言转为SQL"""
    system_prompt = _load_prompt("nl2sql.txt").replace("{today}", date.today().isoformat())

    messages = [{"role": "system", "content": system_prompt}]
    for h in history[-10:]:
        messages.append(h)
    messages.append({"role": "user", "content": message})

    response = client.chat.completions.create(
        model=QWEN_MODEL,
        messages=messages,
        temperature=0,
        max_tokens=1000,
    )
    return _clean_sql_response(response.choices[0].message.content)


def _summarize_result(message: str, table_data: dict) -> str:
    """调用千问对查询结果生成一句话总结"""
    if not table_data["rows"]:
        return "查询结果为空，没有找到匹配的数据。"

    header = " | ".join(table_data["columns"])
    rows_text = "\n".join([" | ".join(row) for row in table_data["rows"][:20]])
    data_text = f"{header}\n{rows_text}"

    response = client.chat.completions.create(
        model=QWEN_MODEL,
        messages=[
            {"role": "system", "content": "你是考试宝典的数据分析助手。用户问了一个数据问题，下面是查询结果。请用简洁的中文（1-2句话）回答用户的问题，直接给出关键数据和简短解读。如果有环比或同比数据，指出变化趋势。"},
            {"role": "user", "content": f"用户问题：{message}\n\n查询结果：\n{data_text}"},
        ],
        temperature=0.3,
        max_tokens=200,
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
    except Exception:
        return {"error": True, "code": "LLM_ERROR", "message": "AI服务暂时不可用，请稍后重试"}

    # 2. 校验SQL
    if not validate_sql(sql):
        try:
            fix_messages = [
                {"role": "system", "content": "上一次生成的SQL不合规。请重新生成一条安全的SELECT查询。只使用dws库和bigdata.v_ws_salesflow_ex表。只输出SQL，不要解释。"},
                {"role": "user", "content": f"原始问题：{message}\n不合规SQL：{sql}\n请重新生成合规的SQL。"},
            ]
            response = client.chat.completions.create(model=QWEN_MODEL, messages=fix_messages, temperature=0, max_tokens=1000)
            sql = _clean_sql_response(response.choices[0].message.content)
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
