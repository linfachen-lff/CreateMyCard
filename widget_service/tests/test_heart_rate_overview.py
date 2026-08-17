"""HeartRateOverview admission, Provider Template lowering, and placement tests."""

from __future__ import annotations

import json
from typing import Any

import pytest

from models.generation import TaskSpec
from overview_test_support import compile_health_scope, field
from services.advanced_component_pipeline.content_selectors import (
    extract_heart_rate_overview_facts,
    heart_rate_overview_is_eligible,
)
from services.advanced_component_pipeline.data_shape import extract_data_shape
from services.advanced_component_pipeline.scope_planner import build_advanced_scope_prompt
from services.cardplan_template.registry import get_cardplan_registry
from services.terse_dsl_nested2_converter import TerseDslNested2ConversionError


def _heart_task(
    *,
    size: str = "2x2",
    query: str = "显示运动平均心率",
    average: Any = 126,
    average_type: str = "integer",
    updated_at: Any = "今天 18:20",
) -> TaskSpec:
    provider = {"exerciseHeartRateAvg": field(average, average_type)}
    if updated_at is not None:
        provider["updatedAt"] = field(updated_at, "string")
    return TaskSpec(
        userQuery=query,
        size=size,
        eventCandidates=[],
        assetCandidates=[],
        dataModelSchema={"GetHealthAndSportSummary": provider},
    )


@pytest.mark.parametrize(
    ("average", "average_type", "eligible"),
    [
        (1, "integer", True),
        (126, "integer", True),
        (0, "integer", False),
        (-1, "integer", False),
        (88.5, "number", False),
        ("88", "string", False),
    ],
)
def test_heart_rate_requires_positive_integer_average(
    average: Any,
    average_type: str,
    eligible: bool,
):
    task = _heart_task(average=average, average_type=average_type)

    assert (extract_heart_rate_overview_facts(task.dataModelSchema) is not None) is eligible
    assert heart_rate_overview_is_eligible(
        task,
        {"GetHealthAndSportSummary"},
    ) is eligible


def test_heart_rate_update_time_is_optional_unless_explicitly_requested():
    no_metadata = _heart_task(updated_at=None)
    explicit = _heart_task(query="显示运动平均心率和更新时间", updated_at=None)

    assert heart_rate_overview_is_eligible(
        no_metadata,
        {"GetHealthAndSportSummary"},
    )
    assert not heart_rate_overview_is_eligible(
        explicit,
        {"GetHealthAndSportSummary"},
    )


def test_heart_rate_first_layer_exposes_average_through_provider_template():
    task = _heart_task()
    messages = build_advanced_scope_prompt(
        task,
        extract_data_shape(task),
        get_cardplan_registry(),
        available_capability_ids=("GetHealthAndSportSummary",),
    )
    payload = json.loads(messages[1]["content"])
    candidate = next(
        item
        for item in payload["advancedComponents"]
        if item["id"] == "HeartRateOverview"
    )
    capability = get_cardplan_registry().require_ux_business_component("HeartRateOverview")

    assert candidate["variants"] == ["average"]
    assert capability.implementation == "template"
    assert capability.local_template_ids == ("HeartRateOverview@1",)


@pytest.mark.parametrize(
    "query",
    [
        "显示当前心率",
        "显示实时心率",
        "显示静息心率",
        "显示心率异常风险",
        "显示心率区间和趋势",
        "显示心率波形",
        "显示最大心率和最低心率",
    ],
)
def test_heart_rate_rejects_unsupported_intents(query: str):
    assert not heart_rate_overview_is_eligible(
        _heart_task(query=query),
        {"GetHealthAndSportSummary"},
    )


@pytest.mark.parametrize("size", ["2x2", "2x4"])
def test_heart_rate_average_lowers_as_bound_metric_without_state_or_chart(size: str):
    task = _heart_task(size=size)
    source = (
        'SingleFocusLayout(Template("HeartRateOverview@1", "heroUpdated", {}));'
    )

    compiled, projection, _projected = compile_health_scope(
        task,
        ("HeartRateOverview",),
        {"GetHealthAndSportSummary"},
        source,
    )

    assert projection.contract.required_template_groups == (("HeartRateOverview@1",),)
    assert compiled.stats.template_used_ids == ("HeartRateOverview@1",)
    assert "Image(" not in compiled.effective_output
    assert "运动平均心率" in compiled.effective_output
    assert "当前心率" not in compiled.effective_output
    assert "静息心率" not in compiled.effective_output
    assert all(
        token not in compiled.effective_output
        for token in ("Progress", "Polyline", "正常", "异常", "风险")
    )
    assert '"fontColor":"#FFE84057"' in compiled.effective_output
    assert '"fontSize":10' in compiled.effective_output
    assert "${data.GetHealthAndSportSummary.exerciseHeartRateAvg}" in compiled.effective_output
    assert "${data.GetHealthAndSportSummary.updatedAt}" in compiled.effective_output


def test_heart_rate_icon_must_match_heart_semantics():
    task = _heart_task()
    task = task.model_copy(
        update={
            "assetCandidates": [
                {
                    "id": "asset.steps",
                    "src": "resources/base/media/steps.svg",
                    "description": "步数图标",
                    "sceneTags": ["steps", "activity"],
                }
            ]
        }
    )
    source = (
        'SingleFocusLayout(Template("HeartRateOverview@1", "heroUpdatedIcon", '
        '{"sourceIcon":"resources/base/media/steps.svg"}));'
    )

    with pytest.raises(TerseDslNested2ConversionError, match="do not match"):
        compile_health_scope(
            task,
            ("HeartRateOverview",),
            {"GetHealthAndSportSummary"},
            source,
        )


@pytest.mark.parametrize("variant", ["heroCurrent", "heroAttention"])
def test_heart_rate_disabled_variants_are_rejected_by_deterministic_validation(
    variant: str,
):
    source = f'SingleFocusLayout(Template("HeartRateOverview@1", "{variant}", {{}}));'

    with pytest.raises(TerseDslNested2ConversionError, match="variant"):
        compile_health_scope(
            _heart_task(),
            ("HeartRateOverview",),
            {"GetHealthAndSportSummary"},
            source,
        )


def test_heart_rate_is_fixed_support_in_activity_multi_business_layout():
    task = _heart_task(size="2x4", query="显示今日步数和运动平均心率")
    health = dict(task.dataModelSchema["GetHealthAndSportSummary"])
    health["dailySteps"] = field(4321, "integer")
    combined = task.model_copy(
        update={"dataModelSchema": {"GetHealthAndSportSummary": health}}
    )
    wrong_order = (
        'HeroSupportLayout(Template("HeartRateOverview@1", "heroUpdated", {}),'
        'ActivityOverview({"variant":"steps","role":"support"}));'
    )

    with pytest.raises(TerseDslNested2ConversionError, match="ActivityOverview must lead"):
        compile_health_scope(
            combined,
            ("ActivityOverview", "HeartRateOverview"),
            {"GetHealthAndSportSummary"},
            wrong_order,
        )


def test_heart_rate_is_valid_support_after_activity_overview():
    task = _heart_task(size="2x4", query="显示今日步数和运动平均心率")
    health = dict(task.dataModelSchema["GetHealthAndSportSummary"])
    health["dailySteps"] = field(4321, "integer")
    combined = task.model_copy(
        update={"dataModelSchema": {"GetHealthAndSportSummary": health}}
    )
    source = (
        'HeroSupportLayout(ActivityOverview({"variant":"steps","role":"hero"}),'
        'Template("HeartRateOverview@1", "supportUpdated", {}));'
    )

    compiled, projection, _projected = compile_health_scope(
        combined,
        ("ActivityOverview", "HeartRateOverview"),
        {"GetHealthAndSportSummary"},
        source,
    )

    assert projection.contract.required_business_component_ids == ("ActivityOverview",)
    assert projection.contract.required_template_groups == (("HeartRateOverview@1",),)
    assert compiled.stats.template_used_ids == ("HeartRateOverview@1",)
    assert (
        'Text("${data.GetHealthAndSportSummary.exerciseHeartRateAvg}", '
        '"compact-title", {"fontSize":20'
    ) in compiled.effective_output
