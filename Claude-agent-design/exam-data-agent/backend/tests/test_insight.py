import os
import sys
import json
import asyncio
import types

os.environ.setdefault("DB_HOST", "localhost")
os.environ.setdefault("DB_USER", "test")
os.environ.setdefault("DB_PASSWORD", "test")
os.environ.setdefault("DB_NAME", "dws")
os.environ.setdefault("QWEN_API_KEY", "test-key")

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
import services.insight as insight


async def _collect_chunks(gen):
    chunks = []
    async for chunk in gen:
        chunks.append(chunk)
    return chunks


def _collect_events(gen):
    events = []
    for chunk in asyncio.run(_collect_chunks(gen)):
        text = chunk.decode() if isinstance(chunk, bytes) else chunk
        if not text.strip():
            continue
        assert text.startswith("data: "), f"Bad SSE frame: {text!r}"
        payload = text[len("data: "):].strip()
        if payload == "[DONE]":
            events.append(payload)
            continue
        events.append(json.loads(payload))
    return events


def test_stream_insight_uses_four_section_structure_and_contextual_rules(monkeypatch):
    captured = {}
    report = {
        "period": {"start": "2026-03-29", "end": "2026-04-04"},
        "sections": {
            "pay": {
                "metrics": {
                    "pay_users": {
                        "label": "付费用户",
                        "value": "100",
                        "wow": "+10.00%",
                        "yoy": "N/A",
                    }
                }
            }
        },
    }

    monkeypatch.setattr(insight, "get_weekly_report", lambda date: report)

    def fake_create(**kwargs):
        captured.update(kwargs)
        return [
            types.SimpleNamespace(
                choices=[
                    types.SimpleNamespace(
                        delta=types.SimpleNamespace(content="本周付费用户增长明显。")
                    )
                ]
            )
        ]

    monkeypatch.setattr(insight.client.chat.completions, "create", fake_create)

    events = _collect_events(insight.stream_insight("weekly", date="2026-04-04"))

    system_prompt = captured["messages"][0]["content"]
    user_prompt = captured["messages"][1]["content"]
    assert "核心结论" in system_prompt
    assert "趋势/异常" in system_prompt
    assert "业务判断" in system_prompt
    assert "建议动作" in system_prompt
    assert "报告类型: 周报 (2026-03-29 ~ 2026-04-04)" in system_prompt
    assert "- 付费用户: 100 (环比: +10.00%, 同比: N/A)" in system_prompt
    assert "请严格使用“核心结论、趋势/异常、业务判断、建议动作”这四个标题" in user_prompt
    assert "不要输出“数据概览”“关键发现”“产品建议”等旧版标题" in user_prompt
    assert events[-1] == "[DONE]"


def test_stream_insight_user_prompt_enforces_natural_business_review_tone(monkeypatch):
    captured = {}

    monkeypatch.setattr(
        insight,
        "get_monthly_report",
        lambda date: {"period": {"month": "2026-03"}, "sections": {}},
    )
    monkeypatch.setattr(
        insight.client.chat.completions,
        "create",
        lambda **kwargs: captured.update(kwargs) or [
            types.SimpleNamespace(
                choices=[types.SimpleNamespace(delta=types.SimpleNamespace(content="完成"))]
            )
        ],
    )

    _collect_events(insight.stream_insight("monthly", date="2026-03"))

    user_prompt = captured["messages"][1]["content"]
    assert "业务判断与建议动作要像业务复盘，先说清现象，再做克制判断" in user_prompt
    assert "不要堆砌“链路”“承接”“迁移”“剪刀差”“放大”等生硬分析术语" in user_prompt
    assert "允许保留基于指标关系或模块表现的弱解释，但不要写得像研究报告或咨询分析" in user_prompt


def test_stream_insight_forbids_over_specific_business_guesses(monkeypatch):
    captured = {}

    monkeypatch.setattr(
        insight,
        "get_monthly_report",
        lambda date: {"period": {"month": "2026-03"}, "sections": {}},
    )
    monkeypatch.setattr(
        insight.client.chat.completions,
        "create",
        lambda **kwargs: captured.update(kwargs) or [
            types.SimpleNamespace(
                choices=[types.SimpleNamespace(delta=types.SimpleNamespace(content="完成"))]
            )
        ],
    )

    _collect_events(insight.stream_insight("monthly", date="2026-03"))

    system_prompt = captured["messages"][0]["content"]
    user_prompt = captured["messages"][1]["content"]
    assert "不要自行补出具体套餐名、活动名、价格档位、营销话术或页面入口" in system_prompt
    assert "建议动作给到方向即可，不要展开成过细的执行剧本" in system_prompt
    assert "不要脑补具体套餐名、活动名、价格档位、营销话术或页面入口" in user_prompt
    assert "建议动作给到业务方向即可，不要写成过细的执行细节" in user_prompt


def test_stream_insight_forbids_operational_jargon_and_action_scripts(monkeypatch):
    captured = {}

    monkeypatch.setattr(
        insight,
        "get_monthly_report",
        lambda date: {"period": {"month": "2026-03"}, "sections": {}},
    )
    monkeypatch.setattr(
        insight.client.chat.completions,
        "create",
        lambda **kwargs: captured.update(kwargs) or [
            types.SimpleNamespace(
                choices=[types.SimpleNamespace(delta=types.SimpleNamespace(content="完成"))]
            )
        ],
    )

    _collect_events(insight.stream_insight("monthly", date="2026-03"))

    system_prompt = captured["messages"][0]["content"]
    user_prompt = captured["messages"][1]["content"]
    assert "业务判断尽量只写数据现象、直接业务观察和谨慎判断，不要写成机制推演或包装过度的分析结论" in system_prompt
    assert "不要写低价入口、冷启动优化、知识点推荐、个性化复购提醒、挑战活动等超出数据证据的具体设想" in system_prompt
    assert "建议动作只写优先关注方向，不要展开到页面位、触发机制、推送策略或活动玩法" in system_prompt
    assert "业务判断尽量只写数据现象、直接业务观察和谨慎判断，不要写成机制推演或包装过度的分析结论" in user_prompt
    assert "不要写低价入口、冷启动优化、知识点推荐、个性化复购提醒、挑战活动等超出数据证据的具体设想" in user_prompt
    assert "建议动作只写优先关注方向，不要展开到页面位、触发机制、推送策略或活动玩法" in user_prompt


def test_stream_insight_forbids_residual_analysis_jargon(monkeypatch):
    captured = {}

    monkeypatch.setattr(
        insight,
        "get_monthly_report",
        lambda date: {"period": {"month": "2026-03"}, "sections": {}},
    )
    monkeypatch.setattr(
        insight.client.chat.completions,
        "create",
        lambda **kwargs: captured.update(kwargs) or [
            types.SimpleNamespace(
                choices=[types.SimpleNamespace(delta=types.SimpleNamespace(content="完成"))]
            )
        ],
    )

    _collect_events(insight.stream_insight("monthly", date="2026-03"))

    system_prompt = captured["messages"][0]["content"]
    user_prompt = captured["messages"][1]["content"]
    assert "不要使用‘价格带’‘自主安排节奏’‘学习闭环’‘轻量归因’这类偏分析包装的说法" in system_prompt
    assert "业务判断里的弱解释也要尽量落在用户表现或经营现象上，不要再延伸成抽象概念包装" in system_prompt
    assert "不要使用‘价格带’‘自主安排节奏’‘学习闭环’‘轻量归因’这类偏分析包装的说法" in user_prompt
    assert "业务判断里的弱解释也要尽量落在用户表现或经营现象上，不要再延伸成抽象概念包装" in user_prompt


def test_stream_insight_forbids_semi_specific_business_scripts(monkeypatch):
    captured = {}

    monkeypatch.setattr(
        insight,
        "get_monthly_report",
        lambda date: {"period": {"month": "2026-03"}, "sections": {}},
    )
    monkeypatch.setattr(
        insight.client.chat.completions,
        "create",
        lambda **kwargs: captured.update(kwargs) or [
            types.SimpleNamespace(
                choices=[types.SimpleNamespace(delta=types.SimpleNamespace(content="完成"))]
            )
        ],
    )

    _collect_events(insight.stream_insight("monthly", date="2026-03"))

    system_prompt = captured["messages"][0]["content"]
    user_prompt = captured["messages"][1]["content"]
    assert "不要把判断写成首购低价套餐、成交结构倾斜、入口优化、提醒机制、结果反馈体验、学习动线衔接等半具体化推测" in system_prompt
    assert "不要把数据变化解释成阶段性训练强度、应试训练偏好或系统学习取舍这类带业务设定的判断" in system_prompt
    assert "不要把判断写成首购低价套餐、成交结构倾斜、入口优化、提醒机制、结果反馈体验、学习动线衔接等半具体化推测" in user_prompt
    assert "不要把数据变化解释成阶段性训练强度、应试训练偏好或系统学习取舍这类带业务设定的判断" in user_prompt



def test_stream_insight_forbids_analysis_framework_and_segmentation(monkeypatch):
    captured = {}

    monkeypatch.setattr(
        insight,
        "get_monthly_report",
        lambda date: {"period": {"month": "2026-03"}, "sections": {}},
    )
    monkeypatch.setattr(
        insight.client.chat.completions,
        "create",
        lambda **kwargs: captured.update(kwargs) or [
            types.SimpleNamespace(
                choices=[types.SimpleNamespace(delta=types.SimpleNamespace(content="完成"))]
            )
        ],
    )

    _collect_events(insight.stream_insight("monthly", date="2026-03"))

    system_prompt = captured["messages"][0]["content"]
    user_prompt = captured["messages"][1]["content"]
    assert "不要写成功能接受度、生命周期作用、购买类型、成交品类、价格分布这类分析框架化表述" in system_prompt
    assert "不要写高强度用户、82题以上群体这类分群动作化表达" in system_prompt
    assert "不要写成功能接受度、生命周期作用、购买类型、成交品类、价格分布这类分析框架化表述" in user_prompt
    assert "不要写高强度用户、82题以上群体这类分群动作化表达" in user_prompt


def test_stream_insight_forbids_value_judgment_and_transition_jargon(monkeypatch):
    captured = {}

    monkeypatch.setattr(
        insight,
        "get_monthly_report",
        lambda date: {"period": {"month": "2026-03"}, "sections": {}},
    )
    monkeypatch.setattr(
        insight.client.chat.completions,
        "create",
        lambda **kwargs: captured.update(kwargs) or [
            types.SimpleNamespace(
                choices=[types.SimpleNamespace(delta=types.SimpleNamespace(content="完成"))]
            )
        ],
    )

    _collect_events(insight.stream_insight("monthly", date="2026-03"))

    system_prompt = captured["messages"][0]["content"]
    user_prompt = captured["messages"][1]["content"]
    assert "不要写成产品价值感知、实战类学习动作、即时反馈型练习、系统性课程学习这类抽象归类" in system_prompt
    assert "不要写成使用路径、行为迁移、带动作用、低价套餐占比、高单价服务这类分析链路或价格结构拆解" in system_prompt
    assert "不要写成产品价值感知、实战类学习动作、即时反馈型练习、系统性课程学习这类抽象归类" in user_prompt
    assert "不要写成使用路径、行为迁移、带动作用、低价套餐占比、高单价服务这类分析链路或价格结构拆解" in user_prompt

    captured = {}

    monkeypatch.setattr(
        insight,
        "get_monthly_report",
        lambda date: {"period": {"month": "2026-03"}, "sections": {}},
    )
    monkeypatch.setattr(
        insight.client.chat.completions,
        "create",
        lambda **kwargs: captured.update(kwargs) or [
            types.SimpleNamespace(
                choices=[types.SimpleNamespace(delta=types.SimpleNamespace(content="完成"))]
            )
        ],
    )

    _collect_events(insight.stream_insight("monthly", date="2026-03"))

    system_prompt = captured["messages"][0]["content"]
    user_prompt = captured["messages"][1]["content"]
    assert "无论证据高低，都不要把当前波动解释为冲刺期、练兵节点、报名期、查分期、备考节奏等考试阶段判断" in system_prompt
    assert "也不要使用“目标驱动型学习”“临近节点”“节奏切换”“冲刺验证”等阶段影射表述" in system_prompt
    assert "无论证据高低，都不要把数据波动写成考试阶段或备考时点变化" in user_prompt
    assert "不要输出“冲刺期”“练兵节点”“目标驱动型学习”“临近节点”等表述" in user_prompt


def test_stream_insight_forbids_price_structure_and_operational_packaging(monkeypatch):
    captured = {}

    monkeypatch.setattr(
        insight,
        "get_monthly_report",
        lambda date: {"period": {"month": "2026-03"}, "sections": {}},
    )
    monkeypatch.setattr(
        insight.client.chat.completions,
        "create",
        lambda **kwargs: captured.update(kwargs) or [
            types.SimpleNamespace(
                choices=[types.SimpleNamespace(delta=types.SimpleNamespace(content="完成"))]
            )
        ],
    )

    _collect_events(insight.stream_insight("monthly", date="2026-03"))

    system_prompt = captured["messages"][0]["content"]
    user_prompt = captured["messages"][1]["content"]
    assert "不要写成低价行为、高单价组合消费、价格敏感度、套餐选择分布这类价格结构或消费层次推测" in system_prompt
    assert "不要写成应试训练类轻量交互、轻量交互、触达效率、承接能力、学习路径这类分析包装或抽象表述" in system_prompt
    assert "不要写成低价行为、高单价组合消费、价格敏感度、套餐选择分布这类价格结构或消费层次推测" in user_prompt
    assert "不要写成应试训练类轻量交互、轻量交互、触达效率、承接能力、学习路径这类分析包装或抽象表述" in user_prompt



def test_stream_insight_forbids_purchase_tier_and_mechanism_backfill(monkeypatch):
    captured = {}

    monkeypatch.setattr(
        insight,
        "get_monthly_report",
        lambda date: {"period": {"month": "2026-03"}, "sections": {}},
    )
    monkeypatch.setattr(
        insight.client.chat.completions,
        "create",
        lambda **kwargs: captured.update(kwargs) or [
            types.SimpleNamespace(
                choices=[types.SimpleNamespace(delta=types.SimpleNamespace(content="完成"))]
            )
        ],
    )

    _collect_events(insight.stream_insight("monthly", date="2026-03"))

    system_prompt = captured["messages"][0]["content"]
    user_prompt = captured["messages"][1]["content"]
    assert "不要写成单次购买、入门级购买、低价入口产品这类购买层次或入口结构推测" in system_prompt
    assert "不要写成集中刷题行为、高刷题量用户、常规用户、提醒机制、特定活动带动这类动作化分群或机制归因" in system_prompt
    assert "不要写成单次购买、入门级购买、低价入口产品这类购买层次或入口结构推测" in user_prompt
    assert "不要写成集中刷题行为、高刷题量用户、常规用户、提醒机制、特定活动带动这类动作化分群或机制归因" in user_prompt



def test_stream_insight_forbids_subscription_variant_and_mechanism_speculation(monkeypatch):
    captured = {}

    monkeypatch.setattr(
        insight,
        "get_monthly_report",
        lambda date: {"period": {"month": "2026-03"}, "sections": {}},
    )
    monkeypatch.setattr(
        insight.client.chat.completions,
        "create",
        lambda **kwargs: captured.update(kwargs) or [
            types.SimpleNamespace(
                choices=[types.SimpleNamespace(delta=types.SimpleNamespace(content="完成"))]
            )
        ],
    )

    _collect_events(insight.stream_insight("monthly", date="2026-03"))

    system_prompt = captured["messages"][0]["content"]
    user_prompt = captured["messages"][1]["content"]
    assert "不要写成基础套餐、入门级产品、套餐结构分布这类订阅层级或产品结构推测" in system_prompt
    assert "不要写成应试型练习动作、付费动作这类行为归类或动作包装" in system_prompt
    assert "不要写成路径回溯、关联强度、行为关联分析这类分析链路术语" in system_prompt
    assert "不要写成播放体验、内容更新、入口可见性这类页面机制或产品功能推测" in system_prompt
    assert "不要写成基础套餐、入门级产品、套餐结构分布这类订阅层级或产品结构推测" in user_prompt
    assert "不要写成应试型练习动作、付费动作这类行为归类或动作包装" in user_prompt
    assert "不要写成路径回溯、关联强度、行为关联分析这类分析链路术语" in user_prompt
    assert "不要写成播放体验、内容更新、入口可见性这类页面机制或产品功能推测" in user_prompt


def test_stream_insight_forbids_behavioral_tilt_and_price_variant(monkeypatch):
    captured = {}

    monkeypatch.setattr(
        insight,
        "get_monthly_report",
        lambda date: {"period": {"month": "2026-03"}, "sections": {}},
    )
    monkeypatch.setattr(
        insight.client.chat.completions,
        "create",
        lambda **kwargs: captured.update(kwargs) or [
            types.SimpleNamespace(
                choices=[types.SimpleNamespace(delta=types.SimpleNamespace(content="完成"))]
            )
        ],
    )

    _collect_events(insight.stream_insight("monthly", date="2026-03"))

    system_prompt = captured["messages"][0]["content"]
    user_prompt = captured["messages"][1]["content"]
    assert "不要写成用户行为向某类功能倾斜、测评类功能倾斜这类行为倾向归类" in system_prompt
    assert "不要写成集中练习强度、练习集中度这类练习强度判断" in system_prompt
    assert "不要写成低价套餐购买增多、高单价服务使用减少这类价格结构拆解变体" in system_prompt
    assert "不要写成用户行为向某类功能倾斜、测评类功能倾斜这类行为倾向归类" in user_prompt
    assert "不要写成集中练习强度、练习集中度这类练习强度判断" in user_prompt
    assert "不要写成低价套餐购买增多、高单价服务使用减少这类价格结构拆解变体" in user_prompt


def test_stream_insight_preserves_status_order(monkeypatch):
    monkeypatch.setattr(
        insight,
        "get_monthly_report",
        lambda date: {"period": {"month": "2026-03"}, "sections": {}},
    )
    monkeypatch.setattr(
        insight.client.chat.completions,
        "create",
        lambda **kwargs: [
            types.SimpleNamespace(
                choices=[types.SimpleNamespace(delta=types.SimpleNamespace(content="完成"))]
            )
        ],
    )

    events = _collect_events(insight.stream_insight("monthly", date="2026-03"))

    status_stages = [
        event["stage"]
        for event in events
        if isinstance(event, dict) and event.get("type") == "status"
    ]
    assert status_stages == ["querying", "analyzing", "generating"]
    assert events[-1] == "[DONE]"
