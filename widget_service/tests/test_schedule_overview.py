"""ScheduleOverview admission, trusted lowering, and resource-boundary tests."""

from __future__ import annotations

import json
from typing import Any

import pytest

from models.generation import EventAction, TaskSpec
from overview_test_support import (
    prepare_provider_scope_projection,
    provider_direct_shadow_projection,
)
from services.advanced_component_pipeline.content_selectors import (
    approved_schedule_action_ids,
    extract_schedule_overview_facts,
    schedule_overview_is_eligible,
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


def _field(value: Any, data_type: str = "string") -> dict[str, Any]:
    return {"type": data_type, "sampleValue": value}


def _join_action() -> EventAction:
    return EventAction(
        id="event.enter.meeting",
        displayLabel="加入会议",
        call="clickToIntent",
        args={"intentName": "ViewCalendarEvent"},
    )


def _focus_action() -> EventAction:
    return EventAction(
        id="event.enable.focus",
        displayLabel="开启专注",
        call="clickToIntent",
        args={"intentName": "DoNotDisturb"},
    )


def _schedule_assets() -> list[dict[str, Any]]:
    return [
        {
            "id": "asset.calendar",
            "src": "resources/base/media/calendar.svg",
            "description": "日历来源图标",
            "sceneTags": ["calendar", "schedule"],
        },
        {
            "id": "asset.time",
            "src": "resources/base/media/time.svg",
            "description": "会议时间图标",
            "sceneTags": ["time"],
        },
        {
            "id": "asset.location",
            "src": "resources/base/media/location.svg",
            "description": "会议地点图标",
            "sceneTags": ["location"],
        },
        {
            "id": "asset.meeting-action",
            "src": "resources/base/media/meeting-action.svg",
            "description": "加入会议操作图标",
            "sceneTags": ["meeting"],
        },
        {
            "id": "asset.focus-action",
            "src": "resources/base/media/focus-action.svg",
            "description": "开启专注操作图标",
            "sceneTags": ["focus"],
        },
        {
            "id": "asset.weather",
            "src": "resources/base/media/weather.svg",
            "description": "天气图标",
            "sceneTags": ["weather"],
        },
    ]


def _schedule_task(
    *,
    size: str = "2x2",
    query: str = "显示下一场会议",
    title: Any = "产品评审",
    start: Any = "09:30",
    end: Any = "10:30",
    location: Any = "A区会议室",
    title_type: str = "string",
    start_type: str = "string",
    event_count: Any = 1,
    events: list[dict[str, Any]] | None = None,
    actions: list[EventAction] | None = None,
    assets: list[dict[str, Any]] | None = None,
) -> TaskSpec:
    if events is None:
        event: dict[str, Any] = {
            "startDate": _field("2026-08-11"),
        }
        if title is not _MISSING:
            event["title"] = _field(title, title_type)
        if start is not _MISSING:
            event["dtStart"] = _field(start, start_type)
        if end is not _MISSING:
            event["dtEnd"] = _field(end)
        if location is not _MISSING:
            event["eventLocation"] = _field(location)
        events = [event]
    provider: dict[str, Any] = {
        "eventCount": _field(event_count, "integer"),
        "events": events,
        "updatedAt": _field("2026-08-11 08:00"),
    }
    return TaskSpec(
        userQuery=query,
        size=size,
        eventCandidates=actions or [],
        dataModelSchema={"GetCalendarEvents": provider},
        assetCandidates=assets or [],
    )


def _compile_schedule(
    task_spec: TaskSpec,
    source: str,
    component_ids: tuple[str, ...] = ("ScheduleOverview",),
):
    capability_ids = {"GetCalendarEvents"}
    projected, card_spec, registry = prepare_provider_scope_projection(
        task_spec,
        capability_ids,
        component_ids,
    )
    scope = AdvancedScopeBrief(
        themeId="meeting-paper-neutral",
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
        contract=projection.contract,
        protocol_profile=A2UIProtocolRegistry.read_design_protocol_profile(
            TERSE_DSL_NESTED2_PROFILE_ID
        ),
        registry=registry,
        card_spec=card_spec if projection.contract.required_template_groups else None,
        enable_data_bindings=bool(projection.contract.required_template_groups),
    )
    return compiled, projection


@pytest.mark.parametrize(
    ("size", "source", "font_sizes"),
    [
        (
            "2x2",
            'SingleFocusLayout(ScheduleOverview({"variant":"nextEvent","role":"hero"}));',
            (20, 14, 10),
        ),
        (
            "2x4",
            'SingleFocusLayout(ScheduleOverview('
            '{"variant":"meetingExpanded","role":"hero"}));',
            (20, 14, 10),
        ),
    ],
)
def test_single_business_direct_schedule_lowers_to_standard_terse_and_a2ui(
    size: str,
    source: str,
    font_sizes: tuple[int, int, int],
):
    compiled, _projection = _compile_schedule(_schedule_task(size=size), source)

    assert "ScheduleOverview" not in compiled.effective_output
    assert "Template" not in compiled.effective_output
    assert 'Text("产品评审", "title", {"width":"100%","fontSize":20' in (
        compiled.effective_output
    )
    assert all(f'"fontSize":{size}' in compiled.effective_output for size in font_sizes)
    assert "ScheduleOverview" not in compiled.a2ui
    assert "Template" not in compiled.a2ui
    rows = [json.loads(line) for line in compiled.a2ui.splitlines()]
    assert [next(key for key in row if key != "version") for row in rows] == [
        "createSurface",
        "updateComponents",
        "updateDataModel",
    ]


@pytest.mark.parametrize(
    ("size", "variant"),
    [("2x2", "meetingCompact"), ("2x4", "meetingExpanded")],
)
def test_schedule_action_is_layout_owned_14fp_36vp_with_20vp_candidate_icon(
    size: str,
    variant: str,
):
    task_spec = _schedule_task(
        size=size,
        query="显示下一场会议并加入会议",
        actions=[_join_action()],
        assets=_schedule_assets(),
    )
    source = (
        'HeroActionLayout(ScheduleOverview({"variant":"'
        + variant
        + '","role":"hero"}),PillAction({"actionId":"event.enter.meeting",'
        '"icon":"resources/base/media/meeting-action.svg"}));'
    )

    compiled, _projection = _compile_schedule(task_spec, source)

    assert "PillAction" not in compiled.effective_output
    assert 'Text("加入会议", "compact-action", {"fontColor"' in compiled.effective_output
    assert '"fontSize":14,"fontWeight":500' in compiled.effective_output
    assert '"height":36' in compiled.effective_output
    assert 'Image("resources/base/media/meeting-action.svg", "icon", {"width":20,"height":20' in (
        compiled.effective_output
    )
    assert compiled.effective_output.index('Text("产品评审"') < compiled.effective_output.index(
        'Text("加入会议"'
    )


@pytest.mark.parametrize(
    ("size", "date_variant", "schedule_variant", "date_role", "schedule_fonts"),
    [
        ("2x2", "compactDate", "meetingCompact", "support", (14, 12, 10)),
        ("2x4", "dateHero", "meetingExpanded", "hero", (16, 14, 10)),
    ],
)
def test_date_schedule_composition_uses_size_specific_support_type_scale(
    size: str,
    date_variant: str,
    schedule_variant: str,
    date_role: str,
    schedule_fonts: tuple[int, int, int],
):
    task_spec = _schedule_task(
        size=size,
        query="显示下一场会议的日期、星期和日程，并加入会议",
        actions=[_join_action()],
    )
    config = '({"heroRatio":"balanced"},' if size == "2x4" else "("
    source = (
        "HeroSupportActionLayout"
        + config
        + f'DateOverview({{"variant":"{date_variant}","role":"{date_role}"}}),'
        + f'ScheduleOverview({{"variant":"{schedule_variant}","role":"support"}}),'
        + 'PillAction({"actionId":"event.enter.meeting"}));'
    )

    compiled, _projection = _compile_schedule(
        task_spec,
        source,
        ("DateOverview", "ScheduleOverview"),
    )

    assert compiled.effective_output.index('Text("11日"') < compiled.effective_output.index(
        'Text("产品评审"'
    )
    schedule_tail = compiled.effective_output.split('Text("产品评审"', 1)[1]
    assert all(f'"fontSize":{font_size}' in schedule_tail for font_size in schedule_fonts)
    assert compiled.effective_output.count("加入会议") == 1


def test_schedule_rail_is_hollow_and_divider_stays_inside_business_body():
    compiled, _projection = _compile_schedule(
        _schedule_task(),
        'SingleFocusLayout(ScheduleOverview({"variant":"nextEvent","role":"hero"}));',
    )

    output = compiled.effective_output
    assert '"width":8,"height":8,"borderRadius":4,"borderWidth":2' in output
    assert 'Divider({"width":1,"height":42,"strokeWidth":1,' in output
    assert output.index('Text("下一个日程"') < output.index('"borderWidth":2')
    assert output.index('"borderWidth":2') < output.index('Text("A区会议室"')


def test_schedule_icons_are_optional_and_semantically_checked_against_task_assets():
    no_icons, _projection = _compile_schedule(
        _schedule_task(assets=[]),
        'SingleFocusLayout(ScheduleOverview({"variant":"nextEvent","role":"hero"}));',
    )
    assert "resources/base/media/" not in no_icons.effective_output

    source = (
        'SingleFocusLayout(ScheduleOverview({"variant":"nextEvent","role":"hero",'
        '"sourceIcon":"resources/base/media/calendar.svg",'
        '"timeIcon":"resources/base/media/time.svg",'
        '"locationIcon":"resources/base/media/location.svg"}));'
    )
    compiled, _projection = _compile_schedule(
        _schedule_task(assets=_schedule_assets()),
        source,
    )
    assert 'Image("resources/base/media/calendar.svg", "icon", {"width":12,"height":12' in (
        compiled.effective_output
    )
    assert '"fillColor":"#FFFF3B30"' in compiled.effective_output
    assert "resources/base/media/time.svg" in compiled.effective_output
    assert "resources/base/media/location.svg" in compiled.effective_output

    mismatched = source.replace("calendar.svg", "weather.svg")
    with pytest.raises(TerseDslNested2ConversionError, match="does not match"):
        _compile_schedule(_schedule_task(assets=_schedule_assets()), mismatched)

    reused_optional, _projection = _compile_schedule(
        _schedule_task(assets=[_schedule_assets()[0]]),
        'SingleFocusLayout(ScheduleOverview({"variant":"nextEvent","role":"hero",'
        '"sourceIcon":"resources/base/media/calendar.svg",'
        '"timeIcon":"resources/base/media/calendar.svg",'
        '"locationIcon":"resources/base/media/calendar.svg"}));',
    )
    assert reused_optional.effective_output.count("resources/base/media/calendar.svg") == 1


def test_explicit_icon_request_requires_a_semantically_matching_task_asset():
    missing = _schedule_task(query="显示下一场会议和日历来源图标")
    mismatched = _schedule_task(
        query="显示下一场会议和日历来源图标",
        assets=[_schedule_assets()[-1]],
    )
    matching = _schedule_task(
        query="显示下一场会议和日历来源图标",
        assets=[_schedule_assets()[0]],
    )

    assert not schedule_overview_is_eligible(missing, {"GetCalendarEvents"})
    assert not schedule_overview_is_eligible(mismatched, {"GetCalendarEvents"})
    assert schedule_overview_is_eligible(matching, {"GetCalendarEvents"})

    action_icon_missing = _schedule_task(
        query="显示下一场会议，加入会议并显示动作图标",
        actions=[_join_action()],
    )
    assert not schedule_overview_is_eligible(action_icon_missing, {"GetCalendarEvents"})


def test_schedule_action_requires_requested_matching_event_and_matching_asset():
    requested = _schedule_task(
        query="显示下一场会议并加入会议",
        actions=[_join_action()],
        assets=_schedule_assets(),
    )
    assert approved_schedule_action_ids(requested) == ("event.enter.meeting",)

    mismatched_icon = (
        'HeroActionLayout(ScheduleOverview({"variant":"meetingCompact","role":"hero"}),'
        'PillAction({"actionId":"event.enter.meeting",'
        '"icon":"resources/base/media/weather.svg"}));'
    )
    with pytest.raises(TerseDslNested2ConversionError, match="does not match"):
        _compile_schedule(requested, mismatched_icon)

    missing_candidate = _schedule_task(query="显示下一场会议并加入会议")
    assert not schedule_overview_is_eligible(missing_candidate, {"GetCalendarEvents"})


def test_focus_context_requires_an_approved_focus_event_and_2x2_rejects_two_actions():
    focus = _schedule_task(
        query="显示下一场会议并开启专注",
        actions=[_focus_action()],
    )
    compiled, _projection = _compile_schedule(
        focus,
        'HeroActionLayout(ScheduleOverview({"variant":"focusContext","role":"hero"}),'
        'PillAction({"actionId":"event.enable.focus"}));',
    )
    assert "开启专注" in compiled.effective_output

    both = _schedule_task(
        query="显示下一场会议，加入会议并开启专注",
        actions=[_join_action(), _focus_action()],
    )
    assert not schedule_overview_is_eligible(both, {"GetCalendarEvents"})


@pytest.mark.parametrize(
    ("end", "location", "expected_time", "expected_location"),
    [
        (_MISSING, _MISSING, "09:30", None),
        ("", "", "09:30", None),
        ("全天", "A区会议室", "09:30 - 全天", "A区会议室"),
    ],
)
def test_schedule_facts_accept_optional_end_location_and_short_all_day_text(
    end: Any,
    location: Any,
    expected_time: str,
    expected_location: str | None,
):
    facts = extract_schedule_overview_facts(
        _schedule_task(end=end, location=location).dataModelSchema
    )

    assert facts is not None
    assert facts.title == "产品评审"
    assert facts.time_text == expected_time
    assert facts.location == expected_location


@pytest.mark.parametrize(
    "task_spec",
    [
        _schedule_task(title=_MISSING),
        _schedule_task(start=_MISSING),
        _schedule_task(title=""),
        _schedule_task(start=""),
        _schedule_task(title=7, title_type="integer"),
        _schedule_task(start=930, start_type="integer"),
        _schedule_task(
            events=[
                {"title": _field("第一项缺时间")},
                {"title": _field("第二项"), "dtStart": _field("10:00")},
            ]
        ),
        _schedule_task(
            events=[
                {"dtStart": _field("09:30")},
                {"title": _field("第二项"), "dtStart": _field("10:00")},
            ]
        ),
    ],
)
def test_schedule_facts_reject_missing_empty_wrong_type_and_cross_event_mix(
    task_spec: TaskSpec,
):
    assert extract_schedule_overview_facts(task_spec.dataModelSchema) is None
    assert not schedule_overview_is_eligible(task_spec, {"GetCalendarEvents"})


def test_location_request_rejects_missing_location_and_expanded_downgrades_without_placeholder():
    explicit = _schedule_task(
        query="显示下一场会议地点",
        location=_MISSING,
    )
    assert not schedule_overview_is_eligible(explicit, {"GetCalendarEvents"})

    ordinary = _schedule_task(location=_MISSING)
    assert schedule_overview_is_eligible(ordinary, {"GetCalendarEvents"})
    compiled, _projection = _compile_schedule(
        ordinary,
        'SingleFocusLayout(ScheduleOverview('
        '{"variant":"meetingExpanded","role":"hero"}));',
    )
    assert "地点未知" not in compiled.effective_output
    assert "eventLocation" not in compiled.effective_output


@pytest.mark.parametrize(
    "query",
    [
        "显示今日全部议程列表",
        "会议是否正在进行",
        "会议还有几分钟开始",
        "显示会议号和备注",
        "显示会议邀请人和是否可加入",
        "今天几号星期几",
        "产品评审会议是几号星期几",
        "显示待办任务",
        "打开备忘录",
    ],
)
def test_schedule_admission_rejects_unsupported_intents(query: str):
    assert not schedule_overview_is_eligible(
        _schedule_task(query=query),
        {"GetCalendarEvents"},
    )


@pytest.mark.parametrize(
    "task_spec",
    [
        _schedule_task(event_count=0),
        _schedule_task(events=[]),
    ],
)
def test_schedule_rejects_explicit_empty_preview(task_spec: TaskSpec):
    assert extract_schedule_overview_facts(task_spec.dataModelSchema) is None
    assert not schedule_overview_is_eligible(task_spec, {"GetCalendarEvents"})


@pytest.mark.asyncio
async def test_forced_first_layer_schedule_selection_is_rejected_by_server_gate():
    task_spec = _schedule_task(query="深圳天气和今日全部议程")
    task_spec = task_spec.model_copy(
        update={
            "dataModelSchema": {
                **task_spec.dataModelSchema,
                "ViewWeather": {
                    "districtName": _field("深圳"),
                    "temperatureText": _field("30°"),
                    "condition": _field("晴"),
                    "airQuality": _field("空气优"),
                    "temperatureRangeText": _field("26° / 32°"),
                },
            }
        }
    )

    async def generate_json(_messages, _phase):
        return {
            "scopeVersion": "advanced-scope-brief/1",
            "themeId": "meeting-paper-neutral",
            "advancedComponentIds": ["ScheduleOverview"],
        }

    with pytest.raises(ValueError, match="outside trusted candidates"):
        await plan_advanced_scope_with_llm(
            task_spec,
            extract_data_shape(task_spec),
            generate_json,
            get_cardplan_registry(),
            available_capability_ids=("GetCalendarEvents", "ViewWeather"),
        )


def test_first_layer_prompt_and_registry_expose_direct_schedule_without_json_template():
    task_spec = _schedule_task()
    messages = build_advanced_scope_prompt(
        task_spec,
        extract_data_shape(task_spec),
        get_cardplan_registry(),
        available_capability_ids=("GetCalendarEvents",),
    )
    payload = json.loads(messages[1]["content"])
    schedule = next(
        item for item in payload["advancedComponents"] if item["id"] == "ScheduleOverview"
    )
    assert "同一可信首项" in schedule["description"]
    assert "分钟倒计时" in messages[0]["content"]

    registry = get_cardplan_registry()
    capability = registry.require_ux_business_component("ScheduleOverview")
    assert capability.implementation == "template"
    assert capability.local_template_ids == ("ScheduleOverview@1",)
    assert "ux-schedule-overview@2" not in registry.templates
