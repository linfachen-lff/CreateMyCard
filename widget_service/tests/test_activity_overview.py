"""ActivityOverview admission, direct lowering, and composition tests."""

from __future__ import annotations

import json
from typing import Any

import pytest

from config.config import get_settings
from models.generation import TaskSpec
from overview_test_support import compile_health_scope, field
from services.advanced_component_pipeline.content_selectors import (
    activity_overview_is_eligible,
    activity_overview_variants,
    advanced_component_batch_data_admission,
    extract_activity_overview_facts,
)
from services.advanced_component_pipeline.data_shape import extract_data_shape
from services.advanced_component_pipeline.models import AdvancedScopeBrief
from services.advanced_component_pipeline.scope_planner import (
    build_advanced_scope_prompt,
    validate_advanced_scope,
)
from services.cardplan_template.registry import get_cardplan_registry
from services.terse_dsl_nested2_converter import TerseDslNested2ConversionError


@pytest.fixture(autouse=True)
def _strict_data_admission_by_default(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr(
        get_settings(),
        "enable_advanced_component_data_admission_bypass_for_batch",
        False,
    )


def _activity_task(
    *,
    size: str = "2x2",
    query: str = "显示今日活动概览",
    steps: Any = 6321,
    steps_type: str = "integer",
    calories: Any = "320 千卡",
    distance: Any = "4.2 公里",
) -> TaskSpec:
    provider = {"dailySteps": field(steps, steps_type)}
    if calories is not None:
        provider["dailyTotalCaloriesText"] = field(calories, "string")
    if distance is not None:
        provider["dailyDistanceText"] = field(distance, "string")
    return TaskSpec(
        userQuery=query,
        size=size,
        eventCandidates=[],
        assetCandidates=[],
        dataModelSchema={"GetHealthAndSportSummary": provider},
    )


@pytest.mark.parametrize("steps", [0, 6321])
def test_activity_steps_accepts_nonnegative_integer_including_zero(steps: int):
    task = _activity_task(query="显示今日步数", steps=steps, calories=None, distance=None)

    facts = extract_activity_overview_facts(task.dataModelSchema)

    assert facts is not None and facts.daily_steps == steps
    assert activity_overview_is_eligible(task, {"GetHealthAndSportSummary"})
    assert activity_overview_variants(task, {"GetHealthAndSportSummary"}) == ("steps",)


@pytest.mark.parametrize(
    ("steps", "steps_type"),
    [(-1, "integer"), (1.5, "number"), ("12", "string"), (True, "boolean")],
)
def test_activity_rejects_negative_or_wrong_typed_steps(steps: Any, steps_type: str):
    task = _activity_task(query="显示今日步数", steps=steps, steps_type=steps_type)

    assert extract_activity_overview_facts(task.dataModelSchema) is None
    assert not activity_overview_is_eligible(task, {"GetHealthAndSportSummary"})


def test_activity_summary_requires_all_three_fields_but_steps_can_downgrade():
    incomplete = _activity_task(distance=None)
    steps_only = _activity_task(query="显示今日步数", distance=None)

    assert not activity_overview_is_eligible(
        incomplete,
        {"GetHealthAndSportSummary"},
    )
    assert activity_overview_variants(
        steps_only,
        {"GetHealthAndSportSummary"},
    ) == ("steps",)


def test_activity_first_layer_exposes_only_query_backed_direct_variants():
    task = _activity_task(query="显示今日步数", calories=None, distance=None)
    with advanced_component_batch_data_admission(True):
        messages = build_advanced_scope_prompt(
            task,
            extract_data_shape(task),
            get_cardplan_registry(),
            available_capability_ids=("GetHealthAndSportSummary",),
        )
    payload = json.loads(messages[1]["content"])
    candidate = next(
        item for item in payload["advancedComponents"] if item["id"] == "ActivityOverview"
    )
    capability = get_cardplan_registry().require_ux_business_component("ActivityOverview")

    assert candidate["variants"] == ["steps"]
    assert capability.implementation == "template"
    assert capability.local_template_ids == ("ActivityOverview@1",)


@pytest.mark.parametrize(
    "query",
    [
        "显示目标步数和达成率",
        "显示活动 Ring 和进度条",
        "显示活动分钟和站立小时",
        "显示活动趋势",
        "仅显示热量",
    ],
)
def test_activity_rejects_unsupported_intents(query: str):
    assert not activity_overview_is_eligible(
        _activity_task(query=query),
        {"GetHealthAndSportSummary"},
    )


def test_batch_mode_temporarily_bypasses_data_admission_but_keeps_renderable_facts(
    monkeypatch: pytest.MonkeyPatch,
):
    settings = get_settings()
    monkeypatch.setattr(settings, "enable_widget_batch_recording", True)
    monkeypatch.setattr(
        settings,
        "enable_advanced_component_data_admission_bypass_for_batch",
        True,
    )
    task = _activity_task(query="显示目标步数和达成率")

    with advanced_component_batch_data_admission(True):
        messages = build_advanced_scope_prompt(
            task,
            extract_data_shape(task),
            get_cardplan_registry(),
            available_capability_ids=("GetHealthAndSportSummary",),
        )
    payload = json.loads(messages[1]["content"])
    candidate = next(
        item for item in payload["advancedComponents"] if item["id"] == "ActivityOverview"
    )
    with advanced_component_batch_data_admission(True):
        compiled, _projection, _projected = compile_health_scope(
            task,
            ("ActivityOverview",),
            {"GetHealthAndSportSummary"},
            'SingleFocusLayout(ActivityOverview({"variant":"steps","role":"hero"}));',
        )

    assert payload["temporaryDataAdmissionBypass"] is True
    assert candidate["variants"] == ["steps", "dailySummary"]
    assert "今日活动" in compiled.effective_output


@pytest.mark.parametrize("size", ["2x2", "2x4"])
@pytest.mark.parametrize("variant", ["steps", "dailySummary"])
def test_activity_direct_constructor_lowers_without_template_or_progress(
    size: str,
    variant: str,
):
    query = "显示今日步数" if variant == "steps" else "显示今日活动概览"
    task = _activity_task(size=size, query=query, steps=0)
    source = f'SingleFocusLayout(ActivityOverview({{"variant":"{variant}","role":"hero"}}));'

    compiled, projection, projected = compile_health_scope(
        task,
        ("ActivityOverview",),
        {"GetHealthAndSportSummary"},
        source,
    )

    assert projection.contract.required_template_groups == ()
    assert compiled.stats.template_used_ids == ()
    assert "ActivityOverview" not in compiled.effective_output
    assert "Progress" not in compiled.effective_output
    assert "Image(" not in compiled.effective_output
    assert "今日活动" in compiled.effective_output
    assert projected.dataModelSchema["data"]["ActivityOverview"]["dailySteps"][
        "sampleValue"
    ] == 0


def test_activity_icon_is_optional_and_must_match_task_asset_semantics():
    task = _activity_task(query="显示今日步数")
    task = task.model_copy(
        update={
            "assetCandidates": [
                {
                    "id": "asset.weather",
                    "src": "resources/base/media/weather.svg",
                    "description": "天气图标",
                    "sceneTags": ["weather"],
                }
            ]
        }
    )
    source = (
        'SingleFocusLayout(ActivityOverview({"variant":"steps","role":"hero",'
        '"stepsIcon":"resources/base/media/weather.svg"}));'
    )

    with pytest.raises(TerseDslNested2ConversionError, match="does not match"):
        compile_health_scope(
            task,
            ("ActivityOverview",),
            {"GetHealthAndSportSummary"},
            source,
        )


@pytest.mark.parametrize("variant", ["calories", "exercise"])
def test_activity_disabled_variants_are_rejected(variant: str):
    source = (
        f'SingleFocusLayout(ActivityOverview({{"variant":"{variant}","role":"hero"}}));'
    )
    with pytest.raises(TerseDslNested2ConversionError, match="variant"):
        compile_health_scope(
            _activity_task(),
            ("ActivityOverview",),
            {"GetHealthAndSportSummary"},
            source,
        )


def test_activity_heart_composition_requires_trusted_companion_and_fixed_roles():
    task = _activity_task(size="2x4", query="显示今日活动和运动平均心率")
    health = dict(task.dataModelSchema["GetHealthAndSportSummary"])
    health["exerciseHeartRateAvg"] = field(128, "integer")
    combined = task.model_copy(
        update={"dataModelSchema": {"GetHealthAndSportSummary": health}}
    )
    source = (
        'HeroSupportLayout(ActivityOverview({"variant":"dailySummary","role":"hero"}),'
        'Template("HeartRateOverview@1", "support", {}));'
    )

    compiled, _projection, _projected = compile_health_scope(
        combined,
        ("ActivityOverview", "HeartRateOverview"),
        {"GetHealthAndSportSummary"},
        source,
    )

    assert "运动平均心率" in compiled.effective_output
    assert "Progress" not in compiled.effective_output
    assert compiled.stats.template_used_ids == ("HeartRateOverview@1",)

    scope = AdvancedScopeBrief(
        themeId="meeting-paper-neutral",
        advancedComponentIds=("ActivityOverview", "HeartRateOverview"),
    )
    with pytest.raises(
        ValueError,
        match="outside trusted candidates|untrusted SleepOverview",
    ):
        validate_advanced_scope(
            scope,
            task,
            extract_data_shape(task),
            get_cardplan_registry(),
            ("GetHealthAndSportSummary",),
        )


def test_activity_sleep_composition_rejects_missing_trusted_sleep_duration():
    task = _activity_task(query="显示今日活动和睡眠")
    scope = AdvancedScopeBrief(
        themeId="meeting-paper-neutral",
        advancedComponentIds=("ActivityOverview", "SleepOverview"),
    )

    with pytest.raises(ValueError, match="outside trusted candidates"):
        validate_advanced_scope(
            scope,
            task,
            extract_data_shape(task),
            get_cardplan_registry(),
            ("GetHealthAndSportSummary",),
        )


@pytest.mark.parametrize("size", ["2x2", "2x4"])
def test_activity_sleep_composition_uses_direct_sleep_support(size: str):
    task = _activity_task(size=size, query="显示今日活动和睡眠")
    health = dict(task.dataModelSchema["GetHealthAndSportSummary"])
    health.update(
        {
            "sleepStatus": field("睡眠充足", "string"),
            "nightSleepDurationText": field("7小时45分钟", "string"),
            "fallAsleepTimeText": field("23:10", "string"),
            "wakeupTimeText": field("06:55", "string"),
        }
    )
    combined = task.model_copy(
        update={"dataModelSchema": {"GetHealthAndSportSummary": health}}
    )
    source = (
        'HeroSupportLayout(ActivityOverview({"variant":"dailySummary","role":"hero"}),'
        'SleepOverview({"variant":"duration","role":"support"}));'
    )

    compiled, projection, _projected = compile_health_scope(
        combined,
        ("ActivityOverview", "SleepOverview"),
        {"GetHealthAndSportSummary"},
        source,
    )

    assert projection.contract.required_template_groups == ()
    assert compiled.stats.template_used_ids == ()
    assert "ActivityOverview" not in compiled.effective_output
    assert "SleepOverview" not in compiled.effective_output
    assert "7" in compiled.effective_output
    assert "45" in compiled.effective_output
