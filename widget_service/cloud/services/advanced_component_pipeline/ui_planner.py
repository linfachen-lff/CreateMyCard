"""高级组件的 UI 意图规划。

真实模型接入时，模型只能输出 :class:`UIBrief`；组件、布局和主题仍由服务端
确定。当前离线规划器用于模型不可用或结果不合格时的安全回退。
"""

from __future__ import annotations

import json
from collections.abc import Awaitable, Callable
from typing import Any

from pydantic import ValidationError

from models.generation import TaskSpec
from services.cardplan_template.prompt import selection_candidates
from services.cardplan_template.registry import CardPlanRegistry

from .component_selector import eligible_component_specs, structural_compatibility
from .models import AdvancedCompositionPlan, DataShape, SelectionConstraints, UIBrief


def _whole_card_candidates(task_spec: TaskSpec, data_shape: DataShape) -> list[dict[str, Any]]:
    constraints = SelectionConstraints(
        size=task_spec.size,
        action_count=len(task_spec.eventCandidates),
        asset_count=len(task_spec.assetCandidates),
    )
    return [
        {
            "layoutArchetype": spec.component_id,
            "visualStructure": spec.description,
            "requiredSlots": spec.slots,
            "requirements": {
                "minFields": spec.min_fields,
                "minAssets": spec.min_assets,
                "minActions": spec.min_actions,
                "requiredFieldRoles": spec.required_field_roles,
            },
            "taskSpecCompatibility": structural_compatibility(data_shape, constraints, spec),
        }
        for spec in eligible_component_specs(data_shape, constraints)
    ]


def build_ui_planner_prompt(
    task_spec: TaskSpec,
    data_shape: DataShape,
    registry: CardPlanRegistry | None = None,
    card_spec: dict[str, Any] | None = None,
) -> list[dict[str, str]]:
    """构造第一轮模型消息，仅开放版本化局部 Template 能力元数据。"""
    registry = registry or CardPlanRegistry()
    user_payload = {
        "userQuery": task_spec.userQuery,
        "size": task_spec.size,
        "dataShape": data_shape.model_dump(exclude={"fields"}),
        "fields": [field.model_dump() for field in data_shape.fields],
        "eventIds": [event.id for event in task_spec.eventCandidates if event.id],
        "eventCandidates": [
            event.model_dump(exclude_none=True) for event in task_spec.eventCandidates
        ],
        "wholeCardCandidates": _whole_card_candidates(task_spec, data_shape),
        "cardPlanCandidates": selection_candidates(task_spec, registry, card_spec),
    }
    output_schema = UIBrief.model_json_schema(by_alias=True)
    for field_name in ("advancedComponentIds", "adaptiveTemplateId", "primaryDomain"):
        output_schema["properties"].pop(field_name, None)
    return [
        {
            "role": "system",
            "content": (
                "你只负责输出抽象 UI 意图 JSON。themeId 和 localTemplateIds 只能从"
                "cardPlanCandidates 选择；themeSemantics/layoutSemantics 只能表达语义，"
                "domain、scenario、statusSemantics、contentSemantics、actionSemantics 必须"
                "根据用户目标、字段含义和事件能力，从 JSON Schema 的枚举中选择；"
                "这些字段描述业务语义，不能填写组件名或布局名。"
                "layoutArchetype 必须只根据需要呈现的数据槽位和视觉层级选择，"
                "不得根据具体 App、品牌、人群或业务名称选择。只能从 wholeCardCandidates"
                "中的 layoutArchetype 选择；如果列表为空则填写 auto。逐项对照 fields 与"
                "requiredSlots，优先覆盖用户明确要求的视觉结构（例如环形进度、双指标、"
                "倒计时、时间线），不要仅因为某个模板字段更少就选择它。"
                "选择规则：只有用户明确要求环形进度，或百分比是唯一核心指标时才选择"
                "status-ring-action；两个独立百分比且都需要环形展示时选择"
                "dual-ring-primary-action；两个独立时长需要并列展示时选择"
                "dual-duration-action；使用量、使用时长及状态摘要选择"
                "usage-summary-action；倒计时选择 hero-countdown；具有明确开始/结束时间的"
                "未来事项选择 upcoming-event-action，包含日期、地点和时间线详情时选择"
                "timeline-event-action；hero-metric-icon-action 只用于用户明确要求两个语义"
                "图片且候选中确实存在该模板；其他单一突出指标使用 hero-metric-action。"
                "不能输出颜色、圆角、组件树、布局源码、参数值或 DesignToken。"
                "局部 Template 是可选能力，不适合时输出空列表。选择 Theme 时优先保证它与"
                "所选局部 Template 的 compatibleThemeIds 一致。actionPlacement 只表达 Action "
                "属于整卡主操作(card)、某个内容摘要/图标控制(content)、无操作(none)，不确定"
                "时用 auto；只有 Action 是局部语义不可分割的一部分时才选择 content，且"
                "localTemplateIds 必须包含 actionPolicy=required 的 Template。actionPolicy=optional"
                "表示可把主操作提升到 card，不足以选择 content。选择局部 Template 时优先选择"
                "requiredParameters 能逐项"
                "覆盖独立 fields、素材和 Action 的 variant，不要把多个独立字段"
                "拼成一个字符串来"
                "迁就参数较少的 Template；同一组事实只能由一个最匹配的局部 Template 承担，"
                "不得同时选择 title/time/value 等主要参数明显重叠的 Template。"
                "不得借此输出具体组件。"
                "advancedComponentIds、"
                "adaptiveTemplateId 和 primaryDomain 是服务端确定性字段，必须省略，服务端会在"
                "解析后注入。\n" + json.dumps(output_schema, ensure_ascii=False)
            ),
        },
        {"role": "user", "content": json.dumps(user_payload, ensure_ascii=False)},
    ]


async def plan_ui_with_llm(
    task_spec: TaskSpec,
    data_shape: DataShape,
    generate_json: Callable[[list[dict[str, str]], str], Awaitable[dict[str, Any]]],
    composition_plan: AdvancedCompositionPlan | None = None,
    card_spec: dict[str, Any] | None = None,
) -> UIBrief:
    """第一轮模型只生成抽象 UIBrief；结构不合法时由调用方回退离线规划。"""
    raw = await generate_json(
        build_ui_planner_prompt(
            task_spec,
            data_shape,
            card_spec=card_spec,
        ),
        "advanced-ui-brief",
    )
    try:
        brief = UIBrief.model_validate(raw)
    except ValidationError as exc:
        raise ValueError(f"invalid UIBrief: {exc}") from exc
    registry = CardPlanRegistry()
    eligible_layouts = {
        item["layoutArchetype"] for item in _whole_card_candidates(task_spec, data_shape)
    }
    if brief.layout_archetype != "auto" and brief.layout_archetype not in eligible_layouts:
        raise ValueError("UIBrief selected a whole-card template outside eligible candidates")
    candidates = selection_candidates(task_spec, registry, card_spec)
    theme_ids = {item["id"] for item in candidates["themes"]}
    template_ids = {item["id"] for item in candidates["localTemplates"]}
    if brief.theme_id is not None and brief.theme_id not in theme_ids:
        raise ValueError("UIBrief selected a theme outside the trusted candidates")
    if any(item not in template_ids for item in brief.local_template_ids):
        raise ValueError("UIBrief selected a Template outside the trusted candidates")
    brief = apply_advanced_composition(brief, composition_plan)
    return normalize_action_placement(brief, data_shape, registry)


def normalize_action_placement(
    brief: UIBrief,
    data_shape: DataShape,
    registry: CardPlanRegistry | None = None,
) -> UIBrief:
    """Keep one primary bottom Action in card@1; reserve content for local controls."""
    if data_shape.action_count == 0 and brief.action_placement == "content":
        return brief.model_copy(update={"action_placement": "none"})
    if data_shape.action_count != 1 or brief.action_placement in {"card", "none"}:
        return brief
    registry = registry or CardPlanRegistry()
    definitions = [registry.require_template(item) for item in brief.local_template_ids]
    if any(item.action_policy == "required" for item in definitions):
        return brief
    return brief.model_copy(update={"action_placement": "card"})


def plan_ui_offline(
    task_spec: TaskSpec,
    data_shape: DataShape,
    composition_plan: AdvancedCompositionPlan | None = None,
) -> UIBrief:
    """根据数据语义给出可预测的保守意图，保证选择器无需模型也能安全运行。"""
    query = task_spec.userQuery.lower()
    scene_rules = [
        (
            ("内存不足", "内存清理", "一键清理"),
            dict(
                domain="device",
                scenario="memory-cleanup",
                layoutArchetype="dual-ring-primary-action",
                statusSemantics=["warning"],
                contentSemantics=["memory-usage", "storage-usage", "percentage"],
                actionSemantics=["clean-memory"],
                temporality="now",
                primary="内存占用和一键清理",
            ),
        ),
        (
            ("打车", "叫车", "出租车", "恶劣天气通勤"),
            dict(
                domain="weather",
                scenario="bad-weather-commute",
                layoutArchetype="hero-metric-icon-action",
                statusSemantics=["warning"],
                contentSemantics=["location", "temperature", "status"],
                actionSemantics=["hail-taxi"],
                temporality="now",
                primary="恶劣天气和打车建议",
            ),
        ),
        (
            ("亲人关怀", "家庭关怀", "电话关怀"),
            dict(
                domain="weather",
                scenario="family-care",
                layoutArchetype="hero-metric-action",
                contentSemantics=["location", "temperature", "status"],
                actionSemantics=["call-contact"],
                temporality="now",
                primary="亲人天气与关怀",
            ),
        ),
        (
            ("赛事", "马拉松", "距离比赛"),
            dict(
                domain="sports",
                scenario="race-countdown",
                layoutArchetype="hero-countdown",
                contentSemantics=["event-title", "countdown"],
                actionSemantics=["open-event"],
                temporality="upcoming",
                primary="赛事倒计时",
            ),
        ),
        (
            ("睡眠", "早睡", "深睡"),
            dict(
                domain="health",
                scenario="sleep-summary",
                layoutArchetype="dual-duration-action",
                statusSemantics=["sleep-quality"],
                contentSemantics=["duration", "status"],
                actionSemantics=["remind-sleep"],
                temporality="historical",
                primary="睡眠时长",
            ),
        ),
        (
            ("防沉迷", "使用时长", "管控时间", "屏幕时间"),
            dict(
                domain="digital-wellbeing",
                scenario="usage-control",
                layoutArchetype="usage-summary-action",
                contentSemantics=["app-usage", "duration"],
                actionSemantics=["manage-usage"],
                temporality="now",
                primary="应用使用时长",
            ),
        ),
        (
            ("低电量", "省电模式", "电量低"),
            dict(
                domain="device",
                scenario="low-power",
                layoutArchetype="status-ring-action",
                statusSemantics=["low-power", "warning"],
                contentSemantics=["battery-level", "percentage", "status"],
                actionSemantics=["enable-power-saving"],
                temporality="now",
                primary="低电量状态",
            ),
        ),
        (
            ("专注模式", "会议倒计时", "免打扰"),
            dict(
                domain="schedule",
                scenario="upcoming-event",
                layoutArchetype="upcoming-event-action",
                statusSemantics=["do-not-disturb"],
                contentSemantics=["event-title", "time-range"],
                actionSemantics=["open-dnd-settings", "enable-focus"],
                temporality="upcoming",
                primary="下一个会议",
            ),
        ),
        (
            ("当前会议", "加入会议", "会议号"),
            dict(
                domain="schedule",
                scenario="ongoing-event",
                layoutArchetype="timeline-event-action",
                statusSemantics=["active"],
                contentSemantics=["event-title", "time-range", "location-detail"],
                actionSemantics=["join-meeting"],
                temporality="now",
                primary="当前会议",
            ),
        ),
        (
            ("倒计时", "倒数日", "倒数"),
            dict(
                domain="general",
                scenario="countdown",
                layoutArchetype="hero-countdown",
                contentSemantics=["countdown"],
                actionSemantics=[],
                temporality="upcoming",
                primary="目标日期倒计时",
            ),
        ),
    ]
    for keywords, semantics in scene_rules:
        if any(keyword in query for keyword in keywords):
            primary = semantics.pop("primary")
            return UIBrief(
                purpose=primary,
                primaryInformation=[primary],
                informationHierarchy=["主信息", "补充信息", "主要操作"],
                attention="prominent",
                visualTone="场景清晰、信息层级明确",
                contentPriorities=[primary, "操作直接"],
                reason="用户需求与已注册高级场景明确匹配。",
                **semantics,
            )
    if data_shape.time_range_count:
        brief = UIBrief(
            purpose="schedule-management",
            domain="schedule",
            scenario="schedule-detail",
            layoutArchetype="upcoming-event-action",
            contentSemantics=["event-title", "time-range"],
            actionSemantics=["open-details"],
            primaryInformation=["近期事项", "开始和结束时间"],
            informationHierarchy=["事项", "时间", "主要操作"],
            temporality="upcoming",
            visualTone="warm-focused",
            contentPriorities=["时间清晰", "操作直接"],
            reason="数据包含同一事项的时间范围。",
        )
        return apply_advanced_composition(brief, composition_plan)
    is_monitoring = data_shape.percentage_count or data_shape.repeated_metric_group_count
    if is_monitoring or any(word in query for word in ("内存", "电量", "存储", "状态")):
        brief = UIBrief(
            purpose="resource-monitoring",
            domain="device",
            scenario="resource-monitoring",
            layoutArchetype="dual-ring-primary-action",
            statusSemantics=["warning"],
            contentSemantics=["metric", "percentage", "status"],
            actionSemantics=["primary-action"],
            primaryInformation=["核心占用", "关联指标"],
            informationHierarchy=["状态", "核心指标", "主要操作"],
            density="compact",
            attention="warning-capable",
            visualTone="technical-efficient",
            contentPriorities=["异常可识别", "指标可扫读"],
            reason="数据包含资源百分比或重复指标。",
        )
        return apply_advanced_composition(brief, composition_plan)
    brief = UIBrief(
        purpose="wellbeing-coaching",
        domain="health",
        scenario="status-summary",
        layoutArchetype="dual-duration-action",
        contentSemantics=["metric", "duration", "status"],
        actionSemantics=["open-details"],
        primaryInformation=["当前状态", "核心时长"],
        informationHierarchy=["状态", "时长", "主要操作"],
        temporality="historical" if data_shape.duration_count else "now",
        attention="prominent",
        visualTone="calm-night",
        contentPriorities=["状态先被感知", "时长快速理解"],
        reason="数据适合形成可行动的状态摘要。",
    )
    return apply_advanced_composition(brief, composition_plan)


def apply_advanced_composition(
    brief: UIBrief,
    composition_plan: AdvancedCompositionPlan | None,
) -> UIBrief:
    """把确定性组件计划注入 Brief，不允许模型覆盖计算字段。"""
    if composition_plan is None:
        return brief
    # 2x2 的确定性组合计划已经按领域、主次和空间预算选好局部模板。模型候选仍
    # 保留在原始 UIBrief 中供审计，但不再把额外的通用兜底模板并入有效候选，
    # 避免同一事实被两个 Template 重复消费。2x4 空间更充足，继续允许去重并集。
    if composition_plan.size == "2x2" and composition_plan.local_template_ids:
        templates = list(composition_plan.local_template_ids)
    else:
        templates = list(
            dict.fromkeys([*composition_plan.local_template_ids, *brief.local_template_ids])
        )[:12]
    return brief.model_copy(
        update={
            "advanced_component_ids": [
                assignment.component_id for assignment in composition_plan.assignments
            ],
            "adaptive_template_id": composition_plan.adaptive_template_id,
            "primary_domain": composition_plan.primary_domain,
            "local_template_ids": templates,
        }
    )
