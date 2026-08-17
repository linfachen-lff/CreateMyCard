"""WorkoutOverview admission, direct lowering, action, and composition tests."""

from __future__ import annotations

import json
from typing import Any

import pytest

from models.generation import TaskSpec
from overview_test_support import compile_health_scope, field, sport_action
from services.advanced_component_pipeline.content_selectors import (
    approved_workout_action_ids,
    extract_workout_countdown_facts,
    extract_workout_latest_facts,
    workout_overview_is_eligible,
    workout_overview_variants,
)
from services.advanced_component_pipeline.data_shape import extract_data_shape
from services.advanced_component_pipeline.scope_planner import build_advanced_scope_prompt
from services.cardplan_template.registry import get_cardplan_registry
from services.terse_dsl_nested2_converter import TerseDslNested2ConversionError


def _latest_task(
    *,
    size: str = "2x2",
    query: str = "显示最近运动",
    exercise_type: Any = "户外跑步",
    duration: Any = "42 分钟",
    calories: Any = "368 千卡",
) -> TaskSpec:
    return TaskSpec(
        userQuery=query,
        size=size,
        eventCandidates=[],
        assetCandidates=[],
        dataModelSchema={
            "GetHealthAndSportSummary": {
                "exerciseTypeName": field(exercise_type, "string"),
                "exerciseDurationText": field(duration, "string"),
                "exerciseCalorieText": field(calories, "string"),
            }
        },
    )


def _countdown_task(
    *,
    size: str = "2x2",
    query: str = "显示运动倒计时",
    days: Any = 3,
    days_type: str = "integer",
) -> TaskSpec:
    return TaskSpec(
        userQuery=query,
        size=size,
        eventCandidates=[],
        assetCandidates=[],
        dataModelSchema={"GetCountdownDays": {"countdownDays": field(days, days_type)}},
    )


def test_workout_latest_requires_complete_nonempty_triple():
    valid = _latest_task()

    assert extract_workout_latest_facts(valid.dataModelSchema) is not None
    assert workout_overview_variants(valid, {"GetHealthAndSportSummary"}) == ("latest",)

    for invalid in (
        _latest_task(exercise_type="暂无运动"),
        _latest_task(exercise_type=""),
        _latest_task(duration=""),
        _latest_task(calories=12),
    ):
        assert extract_workout_latest_facts(invalid.dataModelSchema) is None
        assert not workout_overview_is_eligible(
            invalid,
            {"GetHealthAndSportSummary"},
        )


def test_workout_first_layer_exposes_only_query_backed_direct_variant():
    task = _countdown_task(days=0)
    messages = build_advanced_scope_prompt(
        task,
        extract_data_shape(task),
        get_cardplan_registry(),
        available_capability_ids=("GetCountdownDays",),
    )
    payload = json.loads(messages[1]["content"])
    candidate = next(
        item for item in payload["advancedComponents"] if item["id"] == "WorkoutOverview"
    )
    capability = get_cardplan_registry().require_ux_business_component("WorkoutOverview")

    assert candidate["variants"] == ["countdown"]
    assert capability.implementation == "template"
    assert capability.local_template_ids == (
        "WorkoutOverview@1",
        "WorkoutCountdown@1",
    )


@pytest.mark.parametrize(
    ("days", "days_type", "eligible"),
    [
        (0, "integer", True),
        (8, "integer", True),
        (-1, "integer", False),
        (1.5, "number", False),
        ("3", "string", False),
    ],
)
def test_workout_countdown_integer_boundaries(
    days: Any,
    days_type: str,
    eligible: bool,
):
    task = _countdown_task(days=days, days_type=days_type)

    assert (extract_workout_countdown_facts(task.dataModelSchema) is not None) is eligible
    assert workout_overview_is_eligible(task, {"GetCountdownDays"}) is eligible


@pytest.mark.parametrize(
    "query",
    [
        "显示实时运动状态",
        "显示训练计划",
        "显示单次运动距离和配速轨迹",
        "显示心率区间",
        "显示赛事名称和完成率",
        "显示总里程",
    ],
)
def test_workout_rejects_unsupported_intents(query: str):
    assert not workout_overview_is_eligible(
        _latest_task(query=query),
        {"GetHealthAndSportSummary"},
    )


@pytest.mark.parametrize("size", ["2x2", "2x4"])
@pytest.mark.parametrize("variant", ["latest", "countdown"])
def test_workout_direct_constructor_lowers_enabled_variants_without_progress(
    size: str,
    variant: str,
):
    task = _latest_task(size=size) if variant == "latest" else _countdown_task(size=size, days=0)
    capability = "GetHealthAndSportSummary" if variant == "latest" else "GetCountdownDays"
    source = f'SingleFocusLayout(WorkoutOverview({{"variant":"{variant}","role":"hero"}}));'

    compiled, projection, _projected = compile_health_scope(
        task,
        ("WorkoutOverview",),
        {capability},
        source,
    )

    assert projection.contract.required_template_groups == ()
    assert compiled.stats.template_used_ids == ()
    assert "WorkoutOverview" not in compiled.effective_output
    assert "Progress" not in compiled.effective_output
    assert "Image(" not in compiled.effective_output
    if variant == "countdown":
        assert "运动倒计时" in compiled.effective_output
        assert "赛事" not in compiled.effective_output
        assert "训练计划" not in compiled.effective_output
        assert '"fontColor":"#FFFF7A45"' not in compiled.effective_output
        assert 'Text("天", "subtitle", {"fontSize":12' in compiled.effective_output
        assert '"alignItems":"bottom"' in compiled.effective_output
        assert '"alignItems":"end"' not in compiled.effective_output


def test_workout_icon_must_come_from_semantically_matching_task_asset():
    task = _latest_task()
    task = task.model_copy(
        update={
            "assetCandidates": [
                {
                    "id": "asset.heart",
                    "src": "resources/base/media/heart.svg",
                    "description": "心率图标",
                    "sceneTags": ["heart", "pulse"],
                }
            ]
        }
    )
    source = (
        'SingleFocusLayout(WorkoutOverview({"variant":"latest","role":"hero",'
        '"sourceIcon":"resources/base/media/heart.svg"}));'
    )

    with pytest.raises(TerseDslNested2ConversionError, match="does not match"):
        compile_health_scope(
            task,
            ("WorkoutOverview",),
            {"GetHealthAndSportSummary"},
            source,
        )


def test_workout_matching_icon_uses_registered_business_icon_size():
    task = _latest_task().model_copy(
        update={
            "assetCandidates": [
                {
                    "id": "asset.run",
                    "src": "resources/base/media/run.svg",
                    "description": "跑步运动图标",
                    "sceneTags": ["sport", "run", "workout"],
                }
            ]
        }
    )
    compiled, _projection, _projected = compile_health_scope(
        task,
        ("WorkoutOverview",),
        {"GetHealthAndSportSummary"},
        'SingleFocusLayout(WorkoutOverview({"variant":"latest","role":"hero",'
        '"sourceIcon":"resources/base/media/run.svg"}));',
    )
    assert '"width":20,"height":20' in compiled.effective_output


@pytest.mark.parametrize("variant", ["planned", "ongoing"])
def test_workout_disabled_variants_are_rejected(variant: str):
    source = (
        f'SingleFocusLayout(WorkoutOverview({{"variant":"{variant}","role":"hero"}}));'
    )
    with pytest.raises(TerseDslNested2ConversionError, match="variant"):
        compile_health_scope(
            _latest_task(),
            ("WorkoutOverview",),
            {"GetHealthAndSportSummary"},
            source,
        )


def test_workout_action_requires_query_closure_and_formal_event_id():
    no_action = _latest_task(query="显示最近运动")
    requested = _latest_task(query="显示最近运动并打开运动")
    requested = requested.model_copy(update={"eventCandidates": [sport_action()]})
    wrong = requested.model_copy(
        update={"eventCandidates": [sport_action("event.open.health.home")]}
    )

    assert approved_workout_action_ids(no_action) == ()
    assert approved_workout_action_ids(requested) == ("event.open.health.sport",)
    assert approved_workout_action_ids(wrong) == ()

    source = (
        'HeroActionLayout(WorkoutOverview({"variant":"latest","role":"hero"}),'
        'PillAction({"actionId":"event.open.health.sport"}));'
    )
    compiled, projection, _projected = compile_health_scope(
        requested,
        ("WorkoutOverview",),
        {"GetHealthAndSportSummary"},
        source,
    )
    assert projection.contract.content_action_ids == ("event.open.health.sport",)
    assert compiled.stats.action_used_ids == ("event.open.health.sport",)

    with pytest.raises(TerseDslNested2ConversionError):
        compile_health_scope(
            no_action,
            ("WorkoutOverview",),
            {"GetHealthAndSportSummary"},
            source,
        )


@pytest.mark.parametrize("size", ["2x2", "2x4"])
@pytest.mark.parametrize("with_action", [False, True])
def test_workout_activity_composition_requires_both_trusted_projections(
    size: str,
    with_action: bool,
):
    query = "显示最近运动和今日步数并打开运动" if with_action else "显示最近运动和今日步数"
    task = _latest_task(size=size, query=query)
    if with_action:
        task = task.model_copy(update={"eventCandidates": [sport_action()]})
    schema = dict(task.dataModelSchema)
    health = dict(schema["GetHealthAndSportSummary"])
    health["dailySteps"] = field(0, "integer")
    combined = task.model_copy(
        update={"dataModelSchema": {"GetHealthAndSportSummary": health}}
    )
    layout = "HeroSupportActionLayout" if with_action else "HeroSupportLayout"
    action = ',PillAction({"actionId":"event.open.health.sport"})' if with_action else ""
    source = (
        f'{layout}(WorkoutOverview({{"variant":"latest","role":"hero"}}),'
        f'ActivityOverview({{"variant":"steps","role":"support"}}){action});'
    )

    compiled, _projection, _projected = compile_health_scope(
        combined,
        ("WorkoutOverview", "ActivityOverview"),
        {"GetHealthAndSportSummary"},
        source,
    )

    assert "最近锻炼" in compiled.effective_output
    assert "今日步数" in compiled.effective_output
    assert "Progress" not in compiled.effective_output
    assert compiled.stats.action_used_ids == (
        ("event.open.health.sport",) if with_action else ()
    )
