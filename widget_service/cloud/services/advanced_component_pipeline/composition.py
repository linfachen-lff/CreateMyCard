"""15 个高级组件族的确定性选择、跨尺寸组合和预算校验。"""

from __future__ import annotations

import re
from collections import defaultdict

from models.generation import TaskSpec
from services.cardplan_template.registry import CardPlanRegistry

from .models import (
    AdvancedComponentAssignment,
    AdvancedComponentCapability,
    AdvancedCompositionPlan,
    ComponentRole,
    DataShape,
    Presentation,
)

_LIST_COMPONENTS = frozenset(
    {"ScheduleOverview", "TaskOverview", "CallOverview", "SettingsOverview"}
)
_METRIC_DOMAINS = frozenset(
    {"battery", "app-usage", "activity", "workout", "heart-rate", "sleep", "bluetooth"}
)
_AREA_ORDER = {"compact": 0, "standard": 1, "expanded": 2}


def build_advanced_composition_plan(
    task_spec: TaskSpec,
    data_shape: DataShape,
    registry: CardPlanRegistry,
) -> AdvancedCompositionPlan | None:
    """从 Query 与 Schema 选择领域组件；不读取 fixture、Golden 或运行时业务值。"""
    query_text = _normalize(task_spec.userQuery)
    schema_text = _normalize(
        " ".join(
            f"{field.path} {field.name} {field.description} {' '.join(field.roles)}"
            for field in data_shape.fields
        )
    )
    ranked: list[tuple[float, AdvancedComponentCapability]] = []
    for capability in registry.advanced_components.values():
        query_matches = _matched_terms(query_text, capability.detection_terms)
        schema_matches = _matched_terms(schema_text, capability.detection_terms)
        score = query_matches * 4.0 + schema_matches
        first_query_position = min(
            (
                query_text.find(_normalize(term))
                for term in capability.detection_terms
                if _normalize(term) in query_text
            ),
            default=-1,
        )
        if first_query_position >= 0 and query_text:
            # 同分时让用户更早陈述的主语义胜出，避免末尾 Action（例如“提醒”）
            # 把主要内容领域误判成通用辅助领域。
            score += 1.0 - first_query_position / max(1, len(query_text))
        if query_matches > 0 or schema_matches >= 2:
            ranked.append((score, capability))
    ranked.sort(key=lambda item: (-item[0], item[1].name))
    if not ranked:
        return None

    budget = registry.size_budgets[task_spec.size]
    action_count = min(len(task_spec.eventCandidates), budget.max_primary_actions)
    maximum = min(
        budget.max_advanced_components,
        2 if action_count else budget.recommended_advanced_components,
    )
    selected: list[tuple[float, AdvancedComponentCapability]] = [ranked[0]]
    dropped: list[str] = []
    for candidate in ranked[1:]:
        if len(selected) >= maximum:
            dropped.append(candidate[1].domain_id)
            continue
        if _domains_are_coherent(
            [item[1].domain_id for item in selected],
            candidate[1].domain_id,
            registry.domain_groups,
        ):
            selected.append(candidate)
        else:
            dropped.append(candidate[1].domain_id)

    signals = _data_signals(data_shape, schema_text, selected)
    if selected[0][1].domain_id == "weather" and "forecast" in signals:
        selected.append((selected[0][0] - 0.01, selected[0][1]))
        maximum = max(maximum, 2)
    if len(selected) > budget.max_advanced_components:
        selected = selected[: budget.max_advanced_components]

    assignments: list[AdvancedComponentAssignment] = []
    chart_used = False
    for index, (score, capability) in enumerate(selected):
        role = _role_for(index, len(selected))
        presentation = _presentation_for(task_spec.size, role)
        if _AREA_ORDER[presentation] < _AREA_ORDER[capability.min_area]:
            presentation = capability.min_area
        variant = _variant_for(capability, f"{query_text} {schema_text}")
        if capability.domain_id == "weather" and index > 0:
            variant = "forecast"
        max_items = capability.max_items_by_presentation.get(presentation)
        if max_items is not None:
            max_items = min(max_items, budget.max_list_items)
        uses_chart = capability.supports_primary_chart and capability.domain_id in _METRIC_DOMAINS
        uses_chart = uses_chart and not chart_used
        chart_used = chart_used or uses_chart
        assignments.append(
            AdvancedComponentAssignment(
                component_id=capability.name,
                domain_id=capability.domain_id,
                role=role,
                variant=variant,
                presentation=presentation,
                privacy_mode="masked" if capability.sensitive_fields else "full",
                max_items=max_items,
                uses_primary_chart=uses_chart,
                score=score,
                local_template_ids=capability.local_template_ids,
                visible_field_keys=fields_for_presentation(capability, presentation),
            )
        )

    adaptive_template_id = _select_adaptive_template(
        assignments,
        action_count=action_count,
        signals=signals,
    )
    plan = AdvancedCompositionPlan(
        registry_version=registry.advanced_registry_version,
        size=task_spec.size,
        primary_domain=assignments[0].domain_id,
        primary_goal=task_spec.userQuery,
        adaptive_template_id=adaptive_template_id,
        assignments=tuple(assignments),
        action_count=action_count,
        primary_chart_count=sum(item.uses_primary_chart for item in assignments),
        max_list_items=budget.max_list_items,
        information_levels=min(
            len(assignments) + int(bool(action_count)), budget.max_information_levels
        ),
        data_signals=tuple(sorted(signals)),
        local_template_ids=_unique_templates(
            assignments,
            size=task_spec.size,
            registry=registry,
        ),
        dropped_domain_ids=tuple(dict.fromkeys(dropped)),
    )
    validate_advanced_composition_plan(plan, registry)
    return plan


def validate_advanced_composition_plan(
    plan: AdvancedCompositionPlan,
    registry: CardPlanRegistry,
) -> None:
    budget = registry.size_budgets[plan.size]
    if not plan.assignments:
        raise ValueError("Advanced Component plan must not be empty")
    if len(plan.assignments) > budget.max_advanced_components:
        raise ValueError("Advanced Component budget exceeded")
    if plan.action_count > budget.max_primary_actions:
        raise ValueError("Advanced Component primary Action budget exceeded")
    if plan.primary_chart_count > budget.max_primary_charts:
        raise ValueError("Advanced Component primary chart budget exceeded")
    if plan.information_levels > budget.max_information_levels:
        raise ValueError("Advanced Component information hierarchy budget exceeded")
    hero_count = sum(item.role == "hero" for item in plan.assignments)
    if hero_count > 1:
        raise ValueError("Advanced Component plan cannot contain two heroes")
    domains: list[str] = []
    for assignment in plan.assignments:
        capability = registry.require_advanced_component(assignment.component_id)
        if assignment.domain_id != capability.domain_id:
            raise ValueError("Advanced Component domain mismatch")
        if plan.size not in capability.supported_card_sizes:
            raise ValueError(f"Advanced Component does not support size: {assignment.component_id}")
        if assignment.role not in capability.supported_roles:
            raise ValueError(f"Advanced Component does not support role: {assignment.component_id}")
        if assignment.variant not in capability.variants:
            raise ValueError(
                f"Advanced Component variant is not registered: {assignment.component_id}"
            )
        if _AREA_ORDER[assignment.presentation] < _AREA_ORDER[capability.min_area]:
            raise ValueError(f"Advanced Component area is too small: {assignment.component_id}")
        if capability.sensitive_fields and assignment.privacy_mode == "full":
            raise ValueError(
                f"Sensitive Advanced Component must be masked: {assignment.component_id}"
            )
        if assignment.max_items is not None and assignment.max_items > budget.max_list_items:
            raise ValueError(f"Advanced Component list budget exceeded: {assignment.component_id}")
        must_show = set(capability.field_priorities["mustShow"])
        if not must_show.issubset(assignment.visible_field_keys):
            raise ValueError(
                f"Advanced Component mustShow field was cropped: {assignment.component_id}"
            )
        domains.append(assignment.domain_id)
    if not _all_domains_are_coherent(domains, registry.domain_groups):
        raise ValueError("Advanced Component domains have no shared user goal")
    if plan.adaptive_template_id is None:
        return
    template = registry.require_adaptive_template(plan.adaptive_template_id)
    if plan.size not in template.supported_card_sizes:
        raise ValueError("Adaptive Template does not support target size")
    if len(plan.assignments) > template.max_components_by_size[plan.size]:
        raise ValueError("Adaptive Template component budget exceeded")
    if plan.action_count and not template.supports_primary_action:
        raise ValueError("Adaptive Template does not support a primary Action")
    missing_signals = set(template.required_data_signals) - set(plan.data_signals)
    if missing_signals:
        raise ValueError(f"Adaptive Template is missing data signals: {sorted(missing_signals)}")
    required_advanced = sum(slot.required and slot.kind == "advanced" for slot in template.slots)
    if len(plan.assignments) < required_advanced:
        raise ValueError("Adaptive Template required slots are not filled")


def _normalize(value: str) -> str:
    return re.sub(r"[\s_./:-]+", " ", value.casefold())


def _matched_terms(text: str, terms: tuple[str, ...]) -> int:
    return sum(_normalize(term) in text for term in terms)


def _variant_for(capability: AdvancedComponentCapability, text: str) -> str:
    scores = {
        variant: _matched_terms(text, terms) for variant, terms in capability.variant_terms.items()
    }
    matches = [(score, variant) for variant, score in scores.items() if score > 0]
    if not matches:
        return capability.default_variant
    return min(matches, key=lambda item: (-item[0], capability.variants.index(item[1])))[1]


def _groups_by_domain(groups: dict[str, tuple[str, ...]]) -> dict[str, set[str]]:
    result: dict[str, set[str]] = defaultdict(set)
    for group_id, domains in groups.items():
        for domain in domains:
            result[domain].add(group_id)
    return result


def _domains_are_coherent(
    selected: list[str],
    candidate: str,
    groups: dict[str, tuple[str, ...]],
) -> bool:
    by_domain = _groups_by_domain(groups)
    return all(
        domain == candidate or bool(by_domain[domain] & by_domain[candidate]) for domain in selected
    )


def _all_domains_are_coherent(
    domains: list[str],
    groups: dict[str, tuple[str, ...]],
) -> bool:
    unique = list(dict.fromkeys(domains))
    return all(
        _domains_are_coherent(unique[:index], domain, groups) for index, domain in enumerate(unique)
    )


def _role_for(index: int, count: int) -> ComponentRole:
    if index == 0:
        return "hero"
    return "support" if count <= 3 else "micro"


def _presentation_for(size: str, role: ComponentRole) -> Presentation:
    if role == "micro":
        return "compact"
    if size == "2x4":
        return "expanded" if role == "hero" else "standard"
    return "standard" if role == "hero" else "compact"


def fields_for_presentation(
    capability: AdvancedComponentCapability,
    presentation: Presentation,
) -> tuple[str, ...]:
    """按 expandedOnly → preferShow → mustShow 的裁剪规则投影可见字段。"""
    groups = capability.field_priorities
    visible = list(groups["mustShow"])
    if presentation in {"standard", "expanded"}:
        visible.extend(groups["preferShow"])
    if presentation == "expanded":
        visible.extend(groups["expandedOnly"])
    return tuple(visible)


def _data_signals(
    data_shape: DataShape,
    schema_text: str,
    selected: list[tuple[float, AdvancedComponentCapability]],
) -> set[str]:
    domains = {item[1].domain_id for item in selected}
    signals = set(domains)
    if data_shape.collection_count:
        signals.add("list")
    if data_shape.metric_count >= 2:
        signals.add("metrics")
    if domains & _METRIC_DOMAINS:
        signals.add("metrics")
    if "weather" in domains and any(
        term in schema_text for term in ("forecast", "daily", "high", "low", "预报", "最高", "最低")
    ):
        signals.add("forecast")
    return signals


def _select_adaptive_template(
    assignments: list[AdvancedComponentAssignment],
    *,
    action_count: int,
    signals: set[str],
) -> str | None:
    if (
        assignments[0].domain_id == "weather"
        and "forecast" in signals
        and len(assignments) >= 2
        and not action_count
    ):
        return "weather-forecast"
    if assignments[0].component_id in _LIST_COMPONENTS and action_count and "list" in signals:
        return "list-action"
    if len(assignments) >= 3 and "metrics" in signals and not action_count:
        return "metric-grid"
    if len(assignments) >= 3 and not action_count:
        return "hero-two-support"
    if len(assignments) == 2 and action_count:
        return "hero-support-action"
    if len(assignments) == 2:
        score_gap = abs(assignments[0].score - assignments[1].score)
        return "two-content" if score_gap <= 1.0 else "hero-support"
    if len(assignments) == 1 and action_count:
        return "hero-action"
    return None


def _unique_templates(
    assignments: list[AdvancedComponentAssignment],
    *,
    size: str,
    registry: CardPlanRegistry,
) -> tuple[str, ...]:
    # 2x2 跨领域组合中，每个语义区只下发一个职责清晰的候选，防止主领域的
    # 两个相似模板挤掉 support 区。support 优先使用 Registry 标注为 context/summary
    # 的模板；选择仅依赖受信的角色与语义标签，不读取 fixture 或业务名称。
    if size == "2x2" and len(assignments) > 1:
        selected: list[str] = []
        for assignment in assignments:
            candidates = assignment.local_template_ids
            if not candidates:
                continue
            selected_id = candidates[0]
            if assignment.role == "support":
                selected_id = next(
                    (
                        template_id
                        for template_id in candidates
                        if {"context", "summary"}
                        & {
                            tag.casefold()
                            for tag in registry.require_template(template_id).domain_tags
                        }
                    ),
                    selected_id,
                )
            selected.append(selected_id)
        return tuple(dict.fromkeys(selected))[:8]

    # 单领域时保留前两个专用候选，给模型适量 variant 选择空间。
    return tuple(
        dict.fromkeys(
            template_id
            for assignment in assignments
            for template_id in assignment.local_template_ids[:2]
        )
    )[:8]
