"""SleepOverview admission, direct lowering, layout, and safety tests."""

from __future__ import annotations

import json
import re
from typing import Any

import pytest

from models.generation import EventAction, TaskSpec
from overview_test_support import (
    field,
    prepare_provider_scope_projection,
    provider_direct_shadow_projection,
)
from services.advanced_component_pipeline import content_selectors, scope_planner
from services.advanced_component_pipeline.content_selectors import (
    approved_sleep_action_ids,
    extract_sleep_overview_facts,
    project_content_component_facts,
    sleep_overview_is_eligible,
    sleep_overview_variants,
)
from services.advanced_component_pipeline.data_shape import extract_data_shape
from services.advanced_component_pipeline.models import AdvancedScopeBrief
from services.advanced_component_pipeline.scope_planner import (
    build_advanced_scope_prompt,
    plan_advanced_scope_with_llm,
)
from services.advanced_component_pipeline.ux_mixed_prompt import build_ux_mixed_prompt
from services.cardplan_template.compiler import compile_ux_layout_card
from services.cardplan_template.registry import get_cardplan_registry
from services.protocol_registry import TERSE_DSL_NESTED2_PROFILE_ID, A2UIProtocolRegistry
from services.terse_dsl_nested2_converter import TerseDslNested2ConversionError

_MISSING = object()


def _sleep_action(action_id: str = "event.open.clock.alarm") -> EventAction:
    return EventAction(
        id=action_id,
        displayLabel="设置早睡提醒",
        call="clickToIntent",
        args={"intentName": "Clock"},
    )


def _sleep_assets() -> list[dict[str, Any]]:
    return [
        {
            "id": "asset.sleep.moon",
            "src": "resources/base/media/moon.svg",
            "description": "睡眠月亮图标",
            "sceneTags": ["sleep", "moon"],
        },
        {
            "id": "asset.alarm",
            "src": "resources/base/media/alarm.svg",
            "description": "睡眠闹钟提醒图标",
            "sceneTags": ["sleep", "alarm"],
        },
        {
            "id": "asset.weather",
            "src": "resources/base/media/weather.svg",
            "description": "天气图标",
            "sceneTags": ["weather"],
        },
    ]


def _sleep_task(
    *,
    size: str = "2x2",
    query: str = "显示昨晚睡眠总时长",
    duration: Any = "7小时5分钟",
    duration_type: str = "string",
    status: Any = _MISSING,
    status_type: str = "string",
    fall_asleep: Any = _MISSING,
    wakeup: Any = _MISSING,
    actions: list[EventAction] | None = None,
    assets: list[dict[str, Any]] | None = None,
) -> TaskSpec:
    provider: dict[str, Any] = {
        "nightSleepDurationText": field(duration, duration_type),
    }
    if status is not _MISSING:
        provider["sleepStatus"] = field(status, status_type)
    if fall_asleep is not _MISSING:
        provider["fallAsleepTimeText"] = field(fall_asleep, "string")
    if wakeup is not _MISSING:
        provider["wakeupTimeText"] = field(wakeup, "string")
    return TaskSpec(
        userQuery=query,
        size=size,
        eventCandidates=actions or [],
        assetCandidates=assets or [],
        dataModelSchema={"GetHealthAndSportSummary": provider},
    )


def _compile_sleep(
    task_spec: TaskSpec,
    source: str,
    *,
    component_ids: tuple[str, ...] = ("SleepOverview",),
    theme_id: str = "sleep-night-violet",
):
    capability_ids = {"GetHealthAndSportSummary"}
    projected, card_spec, registry = prepare_provider_scope_projection(
        task_spec,
        capability_ids,
        component_ids,
    )
    scope = AdvancedScopeBrief(
        themeId=theme_id,
        advancedComponentIds=component_ids,
    )
    projection = build_ux_mixed_prompt(
        task_spec=projected,
        card_spec=card_spec,
        scope=scope,
        registry=registry,
    )
    projection = provider_direct_shadow_projection(projection, source, component_ids)
    compiled = compile_ux_layout_card(
        source,
        task_spec=projected,
        card_spec=(card_spec if projection.contract.required_template_groups else None),
        enable_data_bindings=bool(projection.contract.required_template_groups),
        contract=projection.contract,
        protocol_profile=A2UIProtocolRegistry.read_design_protocol_profile(
            TERSE_DSL_NESTED2_PROFILE_ID
        ),
        registry=registry,
    )
    return compiled, projection, projected


@pytest.mark.parametrize(
    ("duration", "expected"),
    [
        ("0分钟", ("0", "分钟", None, None)),
        ("7小时5分钟", ("7", "小时", "5", "分钟")),
        ("1小时75分钟", ("2", "小时", "15", "分钟")),
    ],
)
def test_sleep_duration_is_losslessly_parsed_and_normalized(
    duration: str,
    expected: tuple[str, str, str | None, str | None],
):
    task = _sleep_task(duration=duration)

    facts = extract_sleep_overview_facts(task.dataModelSchema)

    assert facts is not None
    assert (
        facts.duration.primary_value,
        facts.duration.primary_unit,
        facts.duration.secondary_value,
        facts.duration.secondary_unit,
    ) == expected
    assert sleep_overview_variants(task, {"GetHealthAndSportSummary"}) == ("duration",)


@pytest.mark.parametrize(
    "duration",
    ["", "7小时5分钟20秒", "7.5小时", "约7小时", "seven hours", 425],
)
def test_sleep_rejects_missing_or_lossy_duration(duration: Any):
    duration_type = "integer" if isinstance(duration, int) else "string"
    task = _sleep_task(duration=duration, duration_type=duration_type)

    assert extract_sleep_overview_facts(task.dataModelSchema) is None
    assert not sleep_overview_is_eligible(task, {"GetHealthAndSportSummary"})


@pytest.mark.parametrize(
    "query",
    [
        "显示睡眠得分",
        "显示深睡浅睡和 REM",
        "显示午睡时长",
        "显示睡眠目标完成率",
        "显示睡眠趋势和历史",
        "给出睡眠建议",
        "显示睡眠阶段图",
    ],
)
def test_sleep_batch_admission_downgrades_requests_outside_projection(
    query: str,
    monkeypatch,
):
    monkeypatch.setattr(
        content_selectors,
        "advanced_component_data_admission_is_relaxed",
        lambda: True,
    )
    task = _sleep_task(query=query, status="良好")

    assert sleep_overview_variants(
        task,
        {"GetHealthAndSportSummary"},
    ) == ("duration",)


def test_sleep_extended_projection_request_remains_strict_outside_batch(monkeypatch):
    monkeypatch.setattr(
        content_selectors,
        "advanced_component_data_admission_is_relaxed",
        lambda: False,
    )
    task = _sleep_task(query="显示深睡和 REM", status="良好")

    assert not sleep_overview_is_eligible(task, {"GetHealthAndSportSummary"})


def test_sleep_status_and_insufficient_downgrade_without_explicit_trusted_facts(
    monkeypatch,
):
    monkeypatch.setattr(
        content_selectors,
        "advanced_component_data_admission_is_relaxed",
        lambda: True,
    )
    no_status = _sleep_task(query="显示睡眠状态")
    good = _sleep_task(query="显示是否睡眠不足", status="良好")
    insufficient = _sleep_task(query="显示是否睡眠不足", status="睡眠不足")

    assert sleep_overview_variants(
        no_status,
        {"GetHealthAndSportSummary"},
    ) == ("duration",)
    assert sleep_overview_variants(
        good,
        {"GetHealthAndSportSummary"},
    ) == ("duration",)
    assert sleep_overview_variants(
        insufficient,
        {"GetHealthAndSportSummary"},
    ) == ("duration", "insufficient")


def test_short_duration_never_infers_insufficient():
    task = _sleep_task(duration="2小时", status="良好")

    facts = extract_sleep_overview_facts(task.dataModelSchema)

    assert facts is not None and not facts.explicitly_insufficient
    assert sleep_overview_variants(task, {"GetHealthAndSportSummary"}) == ("duration",)


@pytest.mark.parametrize(
    ("size", "fall_asleep", "wakeup", "expected_variants"),
    [
        ("2x4", "23:15", "06:20", ("duration", "schedule")),
        ("2x2", "23:15", "06:20", ("duration",)),
        ("2x4", "23:15", _MISSING, ("duration",)),
        ("2x4", "25:15", "06:20", ("duration",)),
        ("2x4", "23:15", "6:20", ("duration",)),
    ],
)
def test_sleep_schedule_downgrades_when_times_or_size_are_unavailable(
    size: str,
    fall_asleep: Any,
    wakeup: Any,
    expected_variants: tuple[str, ...],
    monkeypatch,
):
    monkeypatch.setattr(
        content_selectors,
        "advanced_component_data_admission_is_relaxed",
        lambda: True,
    )
    task = _sleep_task(
        size=size,
        query="显示入睡时间和醒来时间",
        fall_asleep=fall_asleep,
        wakeup=wakeup,
    )

    assert sleep_overview_variants(
        task,
        {"GetHealthAndSportSummary"},
    ) == expected_variants


def test_sleep_uses_one_provider_record_and_requires_real_capability():
    task = _sleep_task()
    split = task.model_copy(
        update={
            "dataModelSchema": {
                "GetHealthAndSportSummary": {
                    "nightSleepDurationText": field("", "string")
                },
                "unrelated": {"nightSleepDurationText": field("7小时", "string")},
            }
        }
    )

    assert not sleep_overview_is_eligible(task, set())
    assert not sleep_overview_is_eligible(split, {"GetHealthAndSportSummary"})


def test_projection_contains_only_sleep_render_facts_and_server_segments():
    task = _sleep_task(
        size="2x4",
        query="显示睡眠状态、入睡和醒来时间",
        status="良好",
        fall_asleep="23:15",
        wakeup="06:20",
    )
    task = task.model_copy(
        update={
            "dataModelSchema": {
                "GetHealthAndSportSummary": {
                    **task.dataModelSchema["GetHealthAndSportSummary"],
                    "sleepScore": field(86, "integer"),
                    "deepSleepDurationText": field("2小时", "string"),
                    "totalNapDurationText": field("30分钟", "string"),
                }
            }
        }
    )

    projected = project_content_component_facts(
        task,
        {"GetHealthAndSportSummary"},
        ("SleepOverview",),
    )
    sleep = projected.dataModelSchema["data"]["SleepOverview"]

    assert set(sleep) == {
        "nightSleepDurationText",
        "sleepDurationPrimaryValueText",
        "sleepDurationPrimaryUnitText",
        "sleepDurationSecondaryValueText",
        "sleepDurationSecondaryUnitText",
        "sleepStatus",
        "fallAsleepTimeText",
        "wakeupTimeText",
    }
    assert not {"sleepScore", "deepSleepDurationText", "totalNapDurationText"} & set(sleep)


def test_first_layer_exposes_query_backed_direct_variants_without_template(monkeypatch):
    monkeypatch.setattr(
        scope_planner,
        "advanced_component_data_admission_is_bypassed",
        lambda: False,
    )
    monkeypatch.setattr(
        content_selectors,
        "advanced_component_data_admission_is_relaxed",
        lambda: False,
    )
    task = _sleep_task(status="睡眠不足")
    messages = build_advanced_scope_prompt(
        task,
        extract_data_shape(task),
        get_cardplan_registry(),
        available_capability_ids=("GetHealthAndSportSummary",),
    )
    payload = json.loads(messages[1]["content"])
    candidate = next(
        item for item in payload["advancedComponents"] if item["id"] == "SleepOverview"
    )
    capability = get_cardplan_registry().require_ux_business_component("SleepOverview")

    assert candidate["variants"] == ["duration", "insufficient"]
    assert candidate["themeIds"] == ["sleep-night-violet"]
    assert capability.implementation == "template"
    assert capability.local_template_ids == ("SleepOverview@1",)
    assert "ux-sleep" not in json.dumps(candidate, ensure_ascii=False)


@pytest.mark.asyncio
async def test_extended_sleep_request_can_select_duration_in_batch_mode(monkeypatch):
    monkeypatch.setattr(
        scope_planner,
        "advanced_component_data_admission_is_bypassed",
        lambda: False,
    )
    monkeypatch.setattr(
        content_selectors,
        "advanced_component_data_admission_is_relaxed",
        lambda: True,
    )
    task = _sleep_task(query="显示深睡和 REM")

    async def generate_json(_messages, _phase):
        return {
            "scopeVersion": "advanced-scope-brief/1",
            "themeId": "sleep-night-violet",
            "advancedComponentIds": ["SleepOverview"],
        }

    scope = await plan_advanced_scope_with_llm(
        task,
        extract_data_shape(task),
        generate_json,
        get_cardplan_registry(),
        available_capability_ids=("GetHealthAndSportSummary",),
    )

    assert scope.advanced_component_ids == ("SleepOverview",)


@pytest.mark.parametrize("size", ["2x2", "2x4"])
def test_sleep_direct_constructor_lowers_to_standard_a2ui(size: str):
    task = _sleep_task(
        size=size,
        status="良好",
        fall_asleep="23:15",
        wakeup="06:20",
    )
    source = 'SingleFocusLayout(SleepOverview({"variant":"duration","role":"hero"}));'

    compiled, projection, _projected = _compile_sleep(task, source)
    output = compiled.effective_output

    assert projection.contract.required_template_groups == ()
    assert compiled.stats.template_used_ids == ()
    assert "SleepOverview" not in output
    assert "Template" not in output
    assert all(token not in output for token in ("Progress", "Ring", "stage", "阶段"))
    assert 'Text("睡眠", "compact-title", {"fontSize":12' in output
    assert all(f'"fontSize":{value}' in output for value in (30, 12))
    assert re.search(
        r'Row\("between", \{"width":"matchParent","itemMargin":2.*?'
        r'Row\("between", \{"itemMargin":0.*?Text\("7".*?Text\("小时".*?'
        r'Row\("between", \{"itemMargin":0.*?Text\("5".*?Text\("分钟"',
        output,
    )
    assert '"padding":12' in output
    assert '"borderRadius":20' in output
    assert '"#FFAC49F5"' in output
    assert '"#FFC386F0"' in output
    assert "SleepOverview" not in compiled.a2ui
    assert "Progress" not in compiled.a2ui
    if size == "2x4":
        assert all(item in output for item in ('"borderRadius":8', 'Text("入睡"', '23:15'))


def test_sleep_source_icon_is_optional_trusted_and_hidden_in_multi_business():
    task = _sleep_task(assets=_sleep_assets())
    valid = (
        'SingleFocusLayout(SleepOverview({"variant":"duration","role":"hero",'
        '"sourceIcon":"resources/base/media/moon.svg"}));'
    )
    compiled, _projection, _projected = _compile_sleep(task, valid)
    assert "resources/base/media/moon.svg" in compiled.effective_output

    invalid = valid.replace("moon.svg", "weather.svg")
    with pytest.raises(TerseDslNested2ConversionError, match="does not match"):
        _compile_sleep(task, invalid)

    health = dict(task.dataModelSchema["GetHealthAndSportSummary"])
    health["dailySteps"] = field(0, "integer")
    combined = task.model_copy(
        update={
            "size": "2x2",
            "userQuery": "显示今日步数和睡眠",
            "dataModelSchema": {"GetHealthAndSportSummary": health},
        }
    )
    source = (
        'HeroSupportLayout(ActivityOverview({"variant":"steps","role":"hero"}),'
        'SleepOverview({"variant":"duration","role":"support",'
        '"sourceIcon":"resources/base/media/moon.svg"}));'
    )
    compiled, _projection, _projected = _compile_sleep(
        combined,
        source,
        component_ids=("ActivityOverview", "SleepOverview"),
        theme_id="meeting-paper-neutral",
    )
    assert "resources/base/media/moon.svg" not in compiled.effective_output


@pytest.mark.parametrize(
    "source",
    [
        'SingleFocusLayout(SleepOverview({"variant":"stages","role":"hero"}));',
        'SingleFocusLayout(SleepOverview({"variant":"duration","role":"peer"}));',
        'SingleFocusLayout(SleepOverview({"variant":"duration","role":"hero",'
        '"sleepStatus":"良好"}));',
    ],
)
def test_sleep_rejects_disabled_variants_roles_and_business_parameters(source: str):
    with pytest.raises(TerseDslNested2ConversionError):
        _compile_sleep(_sleep_task(), source)


def test_sleep_action_requires_query_approval_and_semantic_icon():
    no_action = _sleep_task(query="显示昨晚睡眠总时长")
    requested = _sleep_task(
        query="显示昨晚睡眠总时长并设置早睡提醒",
        actions=[_sleep_action()],
        assets=_sleep_assets(),
    )
    wrong_event = requested.model_copy(
        update={"eventCandidates": [_sleep_action("event.open.health.sport")]}
    )

    assert approved_sleep_action_ids(no_action) == ()
    assert approved_sleep_action_ids(requested) == ("event.open.clock.alarm",)
    assert approved_sleep_action_ids(wrong_event) == ()

    source = (
        'HeroActionLayout(SleepOverview({"variant":"duration","role":"hero"}),'
        'PillAction({"actionId":"event.open.clock.alarm",'
        '"icon":"resources/base/media/alarm.svg"}));'
    )
    compiled, projection, _projected = _compile_sleep(requested, source)
    output = compiled.effective_output
    assert projection.contract.content_action_ids == ("event.open.clock.alarm",)
    assert compiled.stats.action_used_ids == ("event.open.clock.alarm",)
    assert all(item in output for item in ('"height":36', '"fontSize":14', '"width":20'))
    assert '"itemMargin":8' in output

    with pytest.raises(TerseDslNested2ConversionError):
        _compile_sleep(no_action, source)
    with pytest.raises(TerseDslNested2ConversionError, match="sleep reminder semantics"):
        _compile_sleep(requested, source.replace("alarm.svg", "weather.svg"))


def test_sleep_multi_business_layouts_preserve_hero_support_relation():
    task = _sleep_task(
        size="2x4",
        query="显示睡眠和今日步数",
        fall_asleep="23:15",
        wakeup="06:20",
    )
    health = dict(task.dataModelSchema["GetHealthAndSportSummary"])
    health["dailySteps"] = field(0, "integer")
    combined = task.model_copy(
        update={"dataModelSchema": {"GetHealthAndSportSummary": health}}
    )
    source = (
        'SequentialSummaryLayout(SleepOverview({"variant":"duration","role":"hero"}),'
        'ActivityOverview({"variant":"steps","role":"support"}));'
    )

    compiled, _projection, _projected = _compile_sleep(
        combined,
        source,
        component_ids=("SleepOverview", "ActivityOverview"),
        theme_id="meeting-paper-neutral",
    )

    assert "SleepOverview" not in compiled.effective_output
    assert "ActivityOverview" not in compiled.effective_output
    assert "今日步数" in compiled.effective_output
    assert "Progress" not in compiled.effective_output
    assert '"backgroundColor":"#24FFFFFF"' in compiled.effective_output


def test_sleep_2x2_multi_business_rejects_peer_pair_and_sleep_first():
    task = _sleep_task(size="2x2", query="显示睡眠和今日步数")
    health = dict(task.dataModelSchema["GetHealthAndSportSummary"])
    health["dailySteps"] = field(1, "integer")
    combined = task.model_copy(
        update={"dataModelSchema": {"GetHealthAndSportSummary": health}}
    )
    source = (
        'PeerPairLayout(SleepOverview({"variant":"duration","role":"hero"}),'
        'ActivityOverview({"variant":"steps","role":"support"}));'
    )

    with pytest.raises(TerseDslNested2ConversionError):
        _compile_sleep(
            combined,
            source,
            component_ids=("SleepOverview", "ActivityOverview"),
            theme_id="meeting-paper-neutral",
        )
