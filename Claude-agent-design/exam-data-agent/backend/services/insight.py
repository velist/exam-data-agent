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


def _build_insight_user_prompt() -> str:
    rules = [
        "请严格使用“核心结论、趋势/异常、业务判断、建议动作”这四个标题，不要改写成“数据概览、关键发现、产品建议”等其他标题。",
        "不要输出“数据概览”“关键发现”“产品建议”等旧版标题。",
        "若某部分证据不足，可直接省略该部分，不要写“无法判断”“暂无明显异常”“无需动作”等占位句。",
        "业务判断与建议动作要像业务复盘，先说清现象，再做克制判断。",
        "业务判断尽量只写数据现象、直接业务观察和谨慎判断，不要写成机制推演或包装过度的分析结论。",
        "不要堆砌“链路”“承接”“迁移”“剪刀差”“放大”等生硬分析术语。",
        "不要使用‘价格带’‘自主安排节奏’‘学习闭环’‘轻量归因’这类偏分析包装的说法。",
        "不要把判断写成首购低价套餐、成交结构倾斜、入口优化、提醒机制、结果反馈体验、学习动线衔接等半具体化推测。",
        "不要写成功能接受度、生命周期作用、购买类型、成交品类、价格分布这类分析框架化表述。",
        "不要写成产品价值感知、实战类学习动作、即时反馈型练习、系统性课程学习这类抽象归类。",
        "不要写成使用路径、行为迁移、带动作用、低价套餐占比、高单价服务这类分析链路或价格结构拆解。",
        "不要写成低价行为、高单价组合消费、价格敏感度、套餐选择分布这类价格结构或消费层次推测。",
        "不要写成应试训练类轻量交互、轻量交互、触达效率、承接能力、学习路径这类分析包装或抽象表述。",
        "不要写成单次购买、入门级购买、低价入口产品这类购买层次或入口结构推测。",
        "不要写成集中刷题行为、高刷题量用户、常规用户、提醒机制、特定活动带动这类动作化分群或机制归因。",
        "不要写成基础套餐、入门级产品、套餐结构分布这类订阅层级或产品结构推测。",
        "不要写成应试型练习动作、付费动作这类行为归类或动作包装。",
        "不要写成路径回溯、关联强度、行为关联分析这类分析链路术语。",
        "不要写成播放体验、内容更新、入口可见性这类页面机制或产品功能推测。",
        "不要写成用户行为向某类功能倾斜、测评类功能倾斜这类行为倾向归类。",
        "不要写成集中练习强度、练习集中度这类练习强度判断。",
        "不要写成低价套餐购买增多、高单价服务使用减少这类价格结构拆解变体。",
        "允许保留基于指标关系或模块表现的弱解释，但不要写得像研究报告或咨询分析。",
        "业务判断里的弱解释也要尽量落在用户表现或经营现象上，不要再延伸成抽象概念包装。",
        "不要把数据变化解释成阶段性训练强度、应试训练偏好或系统学习取舍这类带业务设定的判断。",
        "不要写高强度用户、82题以上群体这类分群动作化表达。",
        "不要脑补具体套餐名、活动名、价格档位、营销话术或页面入口。",
        "不要写低价入口、冷启动优化、知识点推荐、个性化复购提醒、挑战活动等超出数据证据的具体设想。",
        "建议动作给到业务方向即可，不要写成过细的执行细节。",
        "建议动作只写优先关注方向，不要展开到页面位、触发机制、推送策略或活动玩法。",
        "无论证据高低，都不要把数据波动写成考试阶段或备考时点变化。",
        "不要输出“冲刺期”“练兵节点”“目标驱动型学习”“临近节点”等表述。",
        "也不要输出“节奏切换”“冲刺验证”等表述。",
    ]
    return "\n".join(rules)


async def stream_insight(report_type: str, date: str | None = None, start: str | None = None, end: str | None = None):
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
    user_prompt = _build_insight_user_prompt()

    yield f"data: {json.dumps({'type': 'status', 'stage': 'generating', 'text': '分析生成中'}, ensure_ascii=False)}\n\n"
    await asyncio.sleep(0)

    stream = client.chat.completions.create(
        model=QWEN_MODEL,
        messages=[
            {"role": "system", "content": prompt},
            {"role": "user", "content": user_prompt},
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
