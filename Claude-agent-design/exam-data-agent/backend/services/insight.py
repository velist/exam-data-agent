import os
import json
import asyncio
from openai import OpenAI
from config import QWEN_API_KEY, QWEN_BASE_URL, QWEN_MODEL
from services.report import get_weekly_report, get_monthly_report, get_range_report

PROMPTS_DIR = os.path.join(os.path.dirname(__file__), '..', 'prompts')

client = OpenAI(api_key=QWEN_API_KEY, base_url=QWEN_BASE_URL)


def _load_prompt(name: str) -> str:
    path = os.path.join(PROMPTS_DIR, name)
    with open(path, "r", encoding="utf-8") as f:
        return f.read()


def _format_report_for_prompt(report: dict, report_type: str) -> str:
    lines = []
    period = report.get("period", {})
    if report_type == "monthly":
        lines.append(f"报告类型: 月报 ({period.get('month', '')})")
    elif report_type == "range":
        lines.append(f"报告类型: 区间报表 ({period.get('start', '')} ~ {period.get('end', '')})")
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


async def stream_insight(report_type: str, date: str | None = None, start: str | None = None, end: str | None = None):
    """SSE流式生成洞察分析"""
    yield f"data: {json.dumps({'type': 'status', 'stage': 'querying', 'text': '数据查询中'}, ensure_ascii=False)}\n\n"
    await asyncio.sleep(0)

    if report_type == "weekly":
        if not date:
            yield f"data: {json.dumps({'text': '缺少周报日期参数'}, ensure_ascii=False)}\n\n"
            return
        report = get_weekly_report(date)
    elif report_type == "monthly":
        if not date:
            yield f"data: {json.dumps({'text': '缺少月报月份参数'}, ensure_ascii=False)}\n\n"
            return
        report = get_monthly_report(date)
    elif report_type == "range":
        if not start or not end:
            yield f"data: {json.dumps({'text': '缺少区间开始或结束参数'}, ensure_ascii=False)}\n\n"
            return
        try:
            report = get_range_report(start, end)
        except ValueError as exc:
            yield f"data: {json.dumps({'text': str(exc)}, ensure_ascii=False)}\n\n"
            return
    else:
        yield f"data: {json.dumps({'text': '不支持的报告类型'}, ensure_ascii=False)}\n\n"
        return

    yield f"data: {json.dumps({'type': 'status', 'stage': 'analyzing', 'text': '数据分析中'}, ensure_ascii=False)}\n\n"
    await asyncio.sleep(0)

    report_text = _format_report_for_prompt(report, report_type)
    prompt_template = _load_prompt("insight.txt")
    prompt = prompt_template.replace("{report_data}", report_text)

    yield f"data: {json.dumps({'type': 'status', 'stage': 'generating', 'text': '分析生成中'}, ensure_ascii=False)}\n\n"
    await asyncio.sleep(0)

    stream = client.chat.completions.create(
        model=QWEN_MODEL,
        messages=[
            {"role": "system", "content": prompt},
            {"role": "user", "content": "请基于以上报告数据，输出数据概览、关键发现和产品建议。重点关注异常变化指标。"},
        ],
        temperature=0.5,
        max_tokens=1500,
        stream=True,
    )

    for chunk in stream:
        if chunk.choices and chunk.choices[0].delta.content:
            text = chunk.choices[0].delta.content
            yield f"data: {json.dumps({'text': text}, ensure_ascii=False)}\n\n"
            await asyncio.sleep(0)

    yield "data: [DONE]\n\n"
