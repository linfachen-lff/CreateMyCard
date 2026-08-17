# -*- coding: utf-8 -*-
# ruff: noqa: E402
"""DateOverview provider gate, TerseDSL lowering, and composition tests."""

import json
import sys
from pathlib import Path
from typing import Any

import pytest

PROJECT_ROOT = Path(__file__).resolve().parents[1]
CLOUD_ROOT = PROJECT_ROOT / "cloud"
if str(CLOUD_ROOT) not in sys.path:
    sys.path.insert(0, str(CLOUD_ROOT))

from models.generation import EventAction, TaskSpec
from overview_test_support import (
    prepare_provider_scope_projection,
    provider_direct_shadow_projection,
)
from services.advanced_component_pipeline.content_selectors import (
    apply_content_selectors,
    date_overview_is_eligible,
    extract_date_overview_facts,
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


def _field(value: Any, data_type: str = "string") -> dict[str, Any]:
    return {"type": data_type, "sampleValue": value}


def _date_task(
    *,
    size: str = "2x2",
    query: str = "产品评审会议是几号星期几",
    start_date: Any = "2026-07-15",
    updated_at: Any = "2026-07-01 09:00",
    include_start_date: bool = True,
    include_updated_at: bool = True,
    start_date_type: str = "string",
    with_action: bool = False,
) -> TaskSpec:
    event = {
        "title": _field("产品评审"),
        "dtStart": _field("09:30"),
        "dtEnd": _field("10:30"),
        "eventLocation": _field("A区会议室"),
    }
    if include_start_date:
        event["startDate"] = _field(start_date, start_date_type)
    calendar: dict[str, Any] = {"events": [event]}
    if include_updated_at:
        calendar["updatedAt"] = _field(updated_at)
    actions = []
    if with_action:
        actions.append(
            EventAction(
                id="event.joinMeeting",
                displayLabel="加入会议",
                call="clickToIntent",
                args={},
            )
        )
    return TaskSpec(
        userQuery=query,
        size=size,
        eventCandidates=actions,
        dataModelSchema={"GetCalendarEvents": calendar},
        assetCandidates=[],
    )


@pytest.mark.parametrize(
    ("start_date", "updated_at", "expected_date", "expected_weekday"),
    [
        ("2026-07-15", None, "15日", "星期三"),
        ("2026/07/15", None, "15日", "星期三"),
        ("07-15", "2026-07-01 09:00", "15日", "星期三"),
    ],
)
def test_date_selector_accepts_only_supported_calendar_date_formats(
    start_date: str,
    updated_at: str | None,
    expected_date: str,
    expected_weekday: str,
):
    task_spec = _date_task(
        start_date=start_date,
        updated_at=updated_at,
        include_updated_at=updated_at is not None,
    )

    selected = apply_content_selectors(task_spec, {"GetCalendarEvents"})
    facts = extract_date_overview_facts(selected.dataModelSchema)

    assert facts is not None
    assert facts.date == expected_date
    assert facts.weekday == expected_weekday
    assert date_overview_is_eligible(task_spec, {"GetCalendarEvents"})


@pytest.mark.parametrize(
    "task_spec",
    [
        _date_task(include_start_date=False),
        _date_task(start_date=""),
        _date_task(start_date=715, start_date_type="integer"),
        _date_task(start_date="2026-02-30"),
        _date_task(start_date="2026.07.15"),
        _date_task(start_date="7-15"),
        _date_task(start_date="07-15", include_updated_at=False),
        _date_task(start_date="07-15", updated_at="20xx-07-01 09:00"),
        _date_task(start_date="07-15", updated_at="2026-02-30 09:00"),
    ],
)
def test_date_selector_rejects_missing_wrong_type_or_invalid_dates(task_spec: TaskSpec):
    selected = apply_content_selectors(task_spec, {"GetCalendarEvents"})

    assert extract_date_overview_facts(selected.dataModelSchema) is None
    assert not date_overview_is_eligible(task_spec, {"GetCalendarEvents"})
    selectors = selected.dataModelSchema.get("data", {}).get("_advancedSelectors", {})
    assert "date" not in selectors


def test_date_gate_does_not_accept_unrelated_date_weekday_fields():
    task_spec = TaskSpec(
        userQuery="产品评审会议的日期和星期",
        size="2x2",
        dataModelSchema={
            "GetCalendarEvents": {"events": [{"title": _field("产品评审")}]},
            "unrelated": {
                "date": _field("15日"),
                "weekday": _field("星期三"),
            },
        },
        assetCandidates=[],
    )

    assert extract_date_overview_facts(task_spec.dataModelSchema) is None
    assert not date_overview_is_eligible(task_spec, {"GetCalendarEvents"})


@pytest.mark.parametrize(
    "query",
    [
        "今天几号",
        "今天星期几",
        "显示当前日期",
        "产品评审会议是明天吗",
        "产品评审会议是哪个月份",
        "产品评审会议是哪一年",
        "产品评审会议的农历日期",
        "产品评审会议距离现在还有几天",
    ],
)
def test_date_scope_gate_rejects_system_and_unsupported_date_intents(query: str):
    task_spec = _date_task(query=query)

    assert not date_overview_is_eligible(task_spec, {"GetCalendarEvents"})
    with pytest.raises(ValueError, match="no provider-backed"):
        build_advanced_scope_prompt(
            task_spec,
            extract_data_shape(task_spec),
            get_cardplan_registry(),
            available_capability_ids=("GetCalendarEvents",),
        )


def test_first_layer_prompt_explains_date_admission_and_exposes_no_json_template():
    task_spec = _date_task()
    messages = build_advanced_scope_prompt(
        task_spec,
        extract_data_shape(task_spec),
        get_cardplan_registry(),
        available_capability_ids=("GetCalendarEvents",),
    )
    payload = json.loads(messages[1]["content"])
    date_candidate = next(
        item for item in payload["advancedComponents"] if item["id"] == "DateOverview"
    )
    registry_date = get_cardplan_registry().require_ux_business_component("DateOverview")

    assert set(date_candidate["variants"]) == {"compactDate", "dateHero"}
    assert "events[].startDate" in date_candidate["description"]
    assert "系统当前日期" in date_candidate["description"]
    assert "2x2" in date_candidate["description"]
    assert registry_date.implementation == "template"
    assert registry_date.local_template_ids == ("DateOverview@1",)


@pytest.mark.asyncio
async def test_forced_first_layer_date_selection_is_rejected_by_deterministic_gate():
    task_spec = _date_task(query="今天星期几")

    async def generate_json(_messages, _phase):
        return {
            "scopeVersion": "advanced-scope-brief/1",
            "themeId": "meeting-paper-neutral",
            "advancedComponentIds": ["DateOverview"],
        }

    with pytest.raises(ValueError, match="no provider-backed"):
        await plan_advanced_scope_with_llm(
            task_spec,
            extract_data_shape(task_spec),
            generate_json,
            get_cardplan_registry(),
            available_capability_ids=("GetCalendarEvents",),
        )


@pytest.mark.asyncio
async def test_2x2_scope_normalization_drops_schedule_only_date_but_keeps_explicit_date():
    registry = get_cardplan_registry()

    async def generate_json(_messages, _phase):
        return {
            "scopeVersion": "advanced-scope-brief/1",
            "themeId": "meeting-paper-neutral",
            "advancedComponentIds": ["ScheduleOverview", "DateOverview"],
        }

    schedule_only = _date_task(query="显示下一场会议")
    normalized = await plan_advanced_scope_with_llm(
        schedule_only,
        extract_data_shape(schedule_only),
        generate_json,
        registry,
        available_capability_ids=("GetCalendarEvents",),
    )
    explicit_date = _date_task(query="显示下一场会议的日期和星期")
    retained = await plan_advanced_scope_with_llm(
        explicit_date,
        extract_data_shape(explicit_date),
        generate_json,
        registry,
        available_capability_ids=("GetCalendarEvents",),
    )

    assert normalized.advanced_component_ids == ("ScheduleOverview",)
    assert retained.advanced_component_ids == ("ScheduleOverview", "DateOverview")


def _compile_date(
    size: str,
    source: str,
    *,
    multi_business: bool = False,
    with_action: bool = False,
):
    query = "显示产品评审会议的日期、星期和日程"
    if with_action:
        query += "，并加入会议"
    task_spec = _date_task(
        size=size,
        query=query,
        with_action=with_action,
    )
    capability_ids = {"GetCalendarEvents"}
    component_ids = (
        ("DateOverview", "ScheduleOverview")
        if multi_business
        else ("DateOverview",)
    )
    scope = AdvancedScopeBrief(
        themeId="meeting-paper-neutral",
        advancedComponentIds=component_ids,
    )
    projected, card_spec, registry = prepare_provider_scope_projection(
        task_spec,
        capability_ids,
        component_ids,
    )
    projection = build_ux_mixed_prompt(
        task_spec=projected,
        card_spec=card_spec,
        scope=scope,
        registry=registry,
    )
    projection = provider_direct_shadow_projection(projection, source, component_ids)
    return compile_ux_layout_card(
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


@pytest.mark.parametrize("size", ["2x2", "2x4"])
def test_single_business_date_hero_is_direct_terse_with_30_and_14_fp(size: str):
    source = (
        'SingleFocusLayout({"contentAlign":"centerStart"},'
        'DateOverview({"variant":"dateHero","role":"hero"}));'
    )

    compiled = _compile_date(size, source)

    assert "DateOverview" not in compiled.effective_output
    assert "Template" not in compiled.effective_output
    assert 'Text("15日", "title", {"fontSize":30,"fontWeight":800' in compiled.effective_output
    assert 'Text("星期三", "body", {"fontSize":14,"fontWeight":500' in (
        compiled.effective_output
    )
    assert compiled.effective_output.count("15日") == 1
    assert compiled.effective_output.count("星期三") == 1


@pytest.mark.parametrize("with_action", [False, True])
def test_2x2_date_schedule_uses_compact_14_12_and_schedule_owned_action(
    with_action: bool,
):
    layout = "HeroSupportActionLayout" if with_action else "HeroSupportLayout"
    action = ',PillAction({"actionId":"event.joinMeeting"})' if with_action else ""
    source = (
        f"{layout}("
        'DateOverview({"variant":"compactDate","role":"support"}),'
        'ScheduleOverview({"variant":"meetingCompact","role":"support"})'
        f"{action});"
    )

    compiled = _compile_date(
        "2x2",
        source,
        multi_business=True,
        with_action=with_action,
    )

    assert 'Text("15日", "compact-title", {"fontSize":14,"fontWeight":700' in (
        compiled.effective_output
    )
    assert 'Text("星期三", "subtitle", {"fontSize":12,"fontWeight":500' in (
        compiled.effective_output
    )
    assert compiled.effective_output.index('Text("15日"') < compiled.effective_output.index(
        'Text("产品评审"'
    )
    assert "DateOverview" not in compiled.effective_output
    if with_action:
        assert compiled.effective_output.count("加入会议") == 1
        assert "PillAction" not in compiled.effective_output


def test_2x4_date_schedule_uses_left_date_hero_right_schedule_and_bottom_action():
    source = (
        'HeroSupportActionLayout({"heroRatio":"balanced"},'
        'DateOverview({"variant":"dateHero","role":"hero"}),'
        'ScheduleOverview({"variant":"meetingExpanded","role":"support"}),'
        'PillAction({"actionId":"event.joinMeeting"}));'
    )

    compiled = _compile_date("2x4", source, multi_business=True, with_action=True)

    assert 'Text("15日", "title", {"fontSize":30,"fontWeight":800' in compiled.effective_output
    assert 'Text("星期三", "body", {"fontSize":14,"fontWeight":500' in (
        compiled.effective_output
    )
    assert compiled.effective_output.index('Text("15日"') < compiled.effective_output.index(
        'Text("产品评审"'
    )
    assert compiled.effective_output.count("加入会议") == 1
    assert '"justifyContent":"spaceBetween"' in compiled.effective_output


def test_single_date_rejects_action_and_multi_business_rejects_wrong_variant_role():
    single_with_action = (
        'SingleFocusLayout(DateOverview({"variant":"dateHero","role":"hero"}),'
        'PillAction({"actionId":"event.joinMeeting"}));'
    )
    wrong_multi = (
        'HeroSupportLayout(DateOverview({"variant":"dateHero","role":"hero"}),'
        'ScheduleOverview({"variant":"meetingExpanded","role":"hero"}));'
    )

    with pytest.raises(TerseDslNested2ConversionError, match="cannot consume an Action"):
        _compile_date("2x2", single_with_action, with_action=True)
    with pytest.raises(TerseDslNested2ConversionError, match="variant and role"):
        _compile_date("2x2", wrong_multi, multi_business=True)
