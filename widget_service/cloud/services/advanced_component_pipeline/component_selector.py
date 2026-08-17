"""高级组件的确定性选择器。"""

from __future__ import annotations

import math

from .component_registry import component_specs
from .models import CandidateScore, ComponentSelection, DataShape, SelectionConstraints, UIBrief


def structural_rejection_reasons(
    data_shape: DataShape,
    constraints: SelectionConstraints,
    spec,
) -> list[str]:
    """返回仅由 TaskSpec 决定的硬性不兼容原因，不掺入业务关键词。"""
    reasons: list[str] = []
    if constraints.size not in spec.supported_sizes:
        reasons.append("unsupported-size")
    return reasons


def structural_compatibility(
    data_shape: DataShape, constraints: SelectionConstraints, spec
) -> dict:
    """计算模板槽位覆盖率；不足只降分，不把模板从候选集中删除。"""
    role_coverage = {}
    for role, expected in spec.required_field_roles.items():
        actual = sum(role in field.roles for field in data_shape.fields)
        role_coverage[role] = min(1.0, actual / expected) if expected else 1.0
    dimensions = {
        "fields": min(1.0, len(data_shape.fields) / spec.min_fields) if spec.min_fields else 1.0,
        "assets": min(1.0, constraints.asset_count / spec.min_assets) if spec.min_assets else 1.0,
        "actions": min(1.0, constraints.action_count / spec.min_actions)
        if spec.min_actions
        else 1.0,
        "fieldRoles": sum(role_coverage.values()) / len(role_coverage) if role_coverage else 1.0,
    }
    return {
        "score": round(sum(dimensions.values()) / len(dimensions), 4),
        "dimensions": dimensions,
    }


def eligible_component_specs(
    data_shape: DataShape,
    constraints: SelectionConstraints,
):
    """在调用模型前过滤 TaskSpec 无法满足的模板。"""
    return tuple(
        spec
        for spec in component_specs()
        if not structural_rejection_reasons(data_shape, constraints, spec)
    )


def _signals(
    data_shape: DataShape,
    brief: UIBrief,
    constraints: SelectionConstraints,
) -> dict[str, float]:
    return {
        "metrics": min(1.0, data_shape.metric_count / 3.0),
        "duration": min(1.0, data_shape.duration_count / 2.0),
        "time-range": float(data_shape.time_range_count > 0),
        "percentage": min(1.0, float(data_shape.percentage_count)),
        "repeated-metrics": float(data_shape.repeated_metric_group_count > 0),
        "action": float(constraints.action_count > 0),
        "monitoring-intent": float(brief.scenario == "resource-monitoring"),
        "schedule-intent": float(brief.domain == "schedule"),
    }


def _overlap_score(actual: list[str], expected: list[str], weight: float) -> float:
    if not expected:
        return 0.0
    return weight * len(set(actual) & set(expected)) / len(set(expected))


def _semantic_score(brief: UIBrief, spec) -> float:
    score = 0.0
    if brief.domain in spec.domains:
        score += 6.0
    if brief.scenario in spec.scenarios:
        score += 7.0
    score += _overlap_score(brief.status_semantics, spec.status_semantics, 4.0)
    score += _overlap_score(brief.content_semantics, spec.content_semantics, 5.0)
    score += _overlap_score(brief.action_semantics, spec.action_semantics, 5.0)
    if brief.temporality in spec.temporalities:
        score += 2.0
    if brief.layout_archetype in spec.layout_archetypes:
        score += 6.0
    return score


def select_component(
    data_shape: DataShape,
    brief: UIBrief,
    constraints: SelectionConstraints,
) -> ComponentSelection | None:
    """选择得分达到阈值的组件；无法可靠选择时返回 ``None`` 以回退原链路。"""
    signals = _signals(data_shape, brief, constraints)
    candidates: list[CandidateScore] = []
    for spec in component_specs():
        score = 0.0
        matched: list[str] = []
        penalties: list[str] = []
        structural_rejections = structural_rejection_reasons(data_shape, constraints, spec)
        score -= 100.0 * len(structural_rejections)
        penalties.extend(structural_rejections)
        if spec.layout_archetypes and brief.layout_archetype not in spec.layout_archetypes:
            score -= 2.0
            penalties.append("layout-archetype-mismatch")
        semantic_score = _semantic_score(brief, spec)
        if semantic_score < spec.min_semantic_score:
            score -= spec.min_semantic_score - semantic_score
            penalties.append("semantic-profile-mismatch")
        score += semantic_score
        if semantic_score:
            matched.append(f"semantic={semantic_score:.2f}")
        compatibility = structural_compatibility(data_shape, constraints, spec)
        compatibility_score = compatibility["score"]
        score += compatibility_score * 8.0
        if compatibility_score < 1.0:
            penalties.append(f"partial-slot-coverage:{compatibility_score:.2f}")
        else:
            matched.append("slot-coverage=1.00")
        for signal, weight in spec.required_signals.items():
            value = signals.get(signal, 0.0)
            if value == 0.0:
                score -= abs(weight) * 1.5
                penalties.append(f"missing:{signal}")
            else:
                score += value * weight
                matched.append(f"{signal}={value:.2f}")
        for signal, weight in spec.preferred_signals.items():
            value = signals.get(signal, 0.0)
            if value:
                score += value * weight
                matched.append(f"{signal}={value:.2f}")
        candidates.append(
            CandidateScore(
                component_id=spec.component_id,
                score=round(score, 4),
                matched=matched,
                penalties=penalties,
            )
        )
    candidates.sort(key=lambda item: (-item.score, item.component_id))
    if not candidates or candidates[0].score < 1.0:
        return None
    margin = candidates[0].score - (candidates[1].score if len(candidates) > 1 else 0.0)
    confidence = 1.0 / (1.0 + math.exp(-margin / 2.5))
    return ComponentSelection(
        component_id=candidates[0].component_id,
        confidence=round(confidence, 4),
        candidates=candidates,
    )
