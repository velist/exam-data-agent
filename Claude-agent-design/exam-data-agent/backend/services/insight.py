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
    """SSE流式生成洞察分析"""
    if report_type == "weekly":
        report = get_weekly_report(date_str)
    elif report_type == "monthly":
        report = get_monthly_report(date_str)
    else:
        yield f"data: {json.dumps({'text': '不支持的报告类型'}, ensure_ascii=False)}\n\n"
        return

    report_text = _format_report_for_prompt(report)
    prompt_template = _load_prompt("insight.txt")
    prompt = prompt_template.replace("{report_data}", report_text)

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
