"""AppUsageOverview admission, direct lowering, and safety tests."""

from __future__ import annotations

import json
import re
from typing import Any

import pytest

from config.config import get_settings
from models.generation import EventAction, TaskSpec
from overview_test_support import (
    prepare_provider_scope_projection,
    provider_direct_shadow_projection,
)
from services.advanced_component_pipeline.content_selectors import (
    advanced_component_batch_data_admission,
    app_usage_overview_is_eligible,
    approved_app_usage_action_ids,
    extract_app_usage_overview_facts,
    parse_duration_text,
    project_content_component_facts,
)
from services.advanced_component_pipeline.data_shape import extract_data_shape
from services.advanced_component_pipeline.models import AdvancedScopeBrief
from services.advanced_component_pipeline.scope_planner import (
    build_advanced_scope_prompt,
    plan_advanced_scope_with_llm,
    resolve_scope_layout_ids,
)
from services.advanced_component_pipeline.ux_mixed_prompt import build_ux_mixed_prompt
from services.cardplan_template.compiler import compile_ux_layout_card
from services.cardplan_template.registry import get_cardplan_registry
from services.protocol_registry import TERSE_DSL_NESTED2_PROFILE_ID, A2UIProtocolRegistry
from services.terse_dsl_nested2_converter import TerseDslNested2ConversionError

_MISSING = object()


def _field(value: Any, data_type: str = "string") -> dict[str, Any]:
    return {"type": data_type, "sampleValue": value}


def _parent_control_action() -> EventAction:
    return EventAction(
        id="event.open.settings.parentControl",
        displayLabel="家长控制设置",
        call="clickToIntent",
        args={"intentName": "ParentalControlSettings"},
    )


def _unrelated_action() -> EventAction:
    return EventAction(
        id="event.open.app.detail",
        displayLabel="打开应用详情",
        call="clickToIntent",
        args={"intentName": "AppDetail"},
    )


def _app_assets() -> list[dict[str, Any]]:
    return [
        {
            "id": "asset.app.douyin",
            "src": "resources/base/media/douyin.svg",
            "description": "抖音应用图标",
            "sceneTags": ["app"],
        },
        {
            "id": "asset.parent-control",
            "src": "resources/base/media/parent-control.svg",
            "description": "使用时间管控设置图标",
            "sceneTags": ["timer", "settings", "parental-control"],
        },
        {
            "id": "asset.weather",
            "src": "resources/base/media/weather.svg",
            "description": "天气图标",
            "sceneTags": ["weather"],
        },
    ]


def _app_usage_task(
    *,
    size: str = "2x2",
    query: str = "显示抖音今天的使用时长",
    app_name: Any = "抖音",
    duration_text: Any = "1小时21分钟",
    updated_at: Any = "2026-08-11 21:30",
    app_name_type: str = "string",
    duration_type: str = "string",
    updated_type: str = "string",
    actions: list[EventAction] | None = None,
    assets: list[dict[str, Any]] | None = None,
) -> TaskSpec:
    app_usage: dict[str, Any] = {}
    if app_name is not _MISSING:
        app_usage["appName"] = _field(app_name, app_name_type)
    if duration_text is not _MISSING:
        app_usage["durationText"] = _field(duration_text, duration_type)
    provider: dict[str, Any] = {"appUsage": app_usage}
    if updated_at is not _MISSING:
        provider["updatedAt"] = _field(updated_at, updated_type)
    return TaskSpec(
        userQuery=query,
        size=size,
        eventCandidates=actions or [],
        dataModelSchema={"GetAppUsageDuration": provider},
        assetCandidates=assets or [],
    )


def _compile_app_usage(task_spec: TaskSpec, source: str):
    capability_ids = {"GetAppUsageDuration"}
    component_ids = ("AppUsageOverview",)
    projected, card_spec, registry = prepare_provider_scope_projection(
        task_spec,
        capability_ids,
        component_ids,
    )
    scope = AdvancedScopeBrief(
        themeId="digital-wellbeing-neutral-dark",
        advancedComponentIds=("AppUsageOverview",),
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
    return compiled, projection


@pytest.mark.parametrize(
    ("duration_text", "expected"),
    [
        ("2小时", ("2", "小时", None, None)),
        ("25分钟", ("25", "分钟", None, None)),
        ("1 小时 21 分钟", ("1", "小时", "21", "分钟")),
        ("0分钟", ("0", "分钟", None, None)),
    ],
)
def test_duration_parser_accepts_lossless_hour_minute_forms(
    duration_text: str,
    expected: tuple[str, str, str | None, str | None],
):
    segments = parse_duration_text(duration_text)

    assert segments is not None
    assert (
        segments.primary_value,
        segments.primary_unit,
        segments.secondary_value,
        segments.secondary_unit,
    ) == expected
    assert app_usage_overview_is_eligible(
        _app_usage_task(duration_text=duration_text),
        {"GetAppUsageDuration"},
    )


@pytest.mark.parametrize(
    "duration_text",
    ["25秒", "25 秒", "1分钟21秒", "1 分钟 21 秒", "1.5小时", "约1小时"],
)
def test_seconds_and_other_unsupported_duration_forms_are_rejected(duration_text: str):
    task_spec = _app_usage_task(duration_text=duration_text)

    assert parse_duration_text(duration_text) is None
    assert extract_app_usage_overview_facts(task_spec.dataModelSchema) is None
    assert not app_usage_overview_is_eligible(task_spec, {"GetAppUsageDuration"})


@pytest.mark.parametrize(
    "task_spec",
    [
        _app_usage_task(app_name=_MISSING),
        _app_usage_task(duration_text=_MISSING),
        _app_usage_task(updated_at=_MISSING),
        _app_usage_task(app_name=""),
        _app_usage_task(app_name=" "),
        _app_usage_task(duration_text=""),
        _app_usage_task(updated_at=""),
        _app_usage_task(app_name=7, app_name_type="integer"),
        _app_usage_task(duration_text=21, duration_type="integer"),
        _app_usage_task(updated_at=2130, updated_type="integer"),
    ],
)
def test_app_usage_rejects_missing_empty_and_wrong_type_facts(task_spec: TaskSpec):
    assert extract_app_usage_overview_facts(task_spec.dataModelSchema) is None
    assert not app_usage_overview_is_eligible(task_spec, {"GetAppUsageDuration"})


def test_app_usage_requires_one_coherent_provider_tree_and_capability():
    task_spec = _app_usage_task(updated_at=_MISSING)
    task_spec = task_spec.model_copy(
        update={
            "dataModelSchema": {
                **task_spec.dataModelSchema,
                "unrelated": {"updatedAt": _field("2026-08-11 21:30")},
            }
        }
    )

    assert extract_app_usage_overview_facts(task_spec.dataModelSchema) is None
    assert not app_usage_overview_is_eligible(task_spec, {"GetAppUsageDuration"})
    assert not app_usage_overview_is_eligible(_app_usage_task(), set())


@pytest.mark.parametrize(
    "query",
    [
        "显示今天总屏幕时间",
        "显示抖音和微信今天的使用时长",
        "显示今天抖音和微信使用时长",
        "显示今天应用排行",
        "显示抖音今天每日限额",
        "显示抖音今天是否超限",
        "显示抖音今天剩余可用时长",
        "显示抖音今天使用比例和进度",
        "显示抖音今天相对历史的使用趋势",
        "显示抖音今天分类汇总",
        "显示抖音的使用时长",
        "显示今天的使用时长",
    ],
)
def test_scope_rejects_unsupported_or_ambiguous_app_usage_intents(query: str):
    task_spec = _app_usage_task(query=query)

    assert not app_usage_overview_is_eligible(task_spec, {"GetAppUsageDuration"})
    with pytest.raises(ValueError, match="no provider-backed"):
        build_advanced_scope_prompt(
            task_spec,
            extract_data_shape(task_spec),
            get_cardplan_registry(),
            available_capability_ids=("GetAppUsageDuration",),
        )


def test_batch_bypass_temporarily_relaxes_first_layer_app_usage_admission(
    monkeypatch: pytest.MonkeyPatch,
):
    settings = get_settings()
    monkeypatch.setattr(settings, "enable_widget_batch_recording", True)
    monkeypatch.setattr(
        settings,
        "enable_advanced_component_data_admission_bypass_for_batch",
        True,
    )
    task_spec = _app_usage_task(query="显示今天总屏幕时间")

    with advanced_component_batch_data_admission(True):
        messages = build_advanced_scope_prompt(
            task_spec,
            extract_data_shape(task_spec),
            get_cardplan_registry(),
            available_capability_ids=("GetAppUsageDuration",),
        )
    payload = json.loads(messages[1]["content"])

    assert "AppUsageOverview" in {
        item["id"] for item in payload["advancedComponents"]
    }
    assert "临时批跑模式" in messages[0]["content"]


def test_batch_bypass_keeps_trusted_projection_gate(
    monkeypatch: pytest.MonkeyPatch,
):
    settings = get_settings()
    monkeypatch.setattr(settings, "enable_widget_batch_recording", True)
    monkeypatch.setattr(
        settings,
        "enable_advanced_component_data_admission_bypass_for_batch",
        True,
    )
    task_spec = _app_usage_task(duration_text=_MISSING)

    with advanced_component_batch_data_admission(True):
        messages = build_advanced_scope_prompt(
            task_spec,
            extract_data_shape(task_spec),
            get_cardplan_registry(),
            available_capability_ids=("GetAppUsageDuration",),
        )
    payload = json.loads(messages[1]["content"])
    assert "AppUsageOverview" in {
        item["id"] for item in payload["advancedComponents"]
    }
    with pytest.raises(ValueError, match="no renderable provider facts"):
        project_content_component_facts(
            task_spec,
            {"GetAppUsageDuration"},
            ("AppUsageOverview",),
        )


def test_projection_contains_only_original_facts_and_deterministic_segments():
    projected = project_content_component_facts(
        _app_usage_task(),
        {"GetAppUsageDuration"},
        ("AppUsageOverview",),
    )
    app_usage = projected.dataModelSchema["data"]["AppUsageOverview"]

    assert set(app_usage) == {
        "appName",
        "durationText",
        "updatedAt",
        "durationPrimaryValueText",
        "durationPrimaryUnitText",
        "durationSecondaryValueText",
        "durationSecondaryUnitText",
    }
    assert app_usage["durationText"]["sampleValue"] == "1小时21分钟"
    assert app_usage["durationPrimaryValueText"]["sampleValue"] == "1"
    assert app_usage["durationSecondaryValueText"]["sampleValue"] == "21"


def test_first_layer_exposes_only_single_app_direct_constructor_without_template():
    task_spec = _app_usage_task()
    messages = build_advanced_scope_prompt(
        task_spec,
        extract_data_shape(task_spec),
        get_cardplan_registry(),
        available_capability_ids=("GetAppUsageDuration",),
    )
    payload = json.loads(messages[1]["content"])
    candidate = next(
        item for item in payload["advancedComponents"]
        if item["id"] == "AppUsageOverview"
    )
    capability = get_cardplan_registry().require_ux_business_component(
        "AppUsageOverview"
    )

    assert candidate["variants"] == ["singleApp"]
    assert capability.implementation == "template"
    assert capability.local_template_ids == ("AppUsageOverview@1",)
    assert capability.variants == ("singleApp", "dailyLimit", "overLimit", "topApps")
    assert "当前只启用 singleApp" in candidate["description"]
    assert "ux-app-usage-overview" not in json.dumps(candidate, ensure_ascii=False)


@pytest.mark.asyncio
async def test_forced_invalid_app_usage_selection_is_rejected_after_first_layer():
    task_spec = _app_usage_task(duration_text="1分钟21秒")

    async def generate_json(_messages, _phase):
        return {
            "scopeVersion": "advanced-scope-brief/1",
            "themeId": "digital-wellbeing-neutral-dark",
            "advancedComponentIds": ["AppUsageOverview"],
        }

    with pytest.raises(ValueError, match="no provider-backed"):
        await plan_advanced_scope_with_llm(
            task_spec,
            extract_data_shape(task_spec),
            generate_json,
            get_cardplan_registry(),
            available_capability_ids=("GetAppUsageDuration",),
        )


@pytest.mark.parametrize("size", ["2x2", "2x4"])
def test_single_app_direct_constructor_lowers_to_standard_a2ui(size: str):
    compiled, projection = _compile_app_usage(
        _app_usage_task(size=size),
        'SingleFocusLayout(AppUsageOverview({"variant":"singleApp","role":"hero"}));',
    )
    output = compiled.effective_output

    assert projection.requested_template_ids == ()
    assert projection.contract.required_template_groups == ()
    assert "AppUsageOverview" not in output
    assert "Template" not in output
    assert "Progress" not in output
    assert 'Text("抖音", "compact-title", {"fontSize":12' in output
    assert 'Text("2026-08-11 21:30", "subtitle", {"fontSize":10' in output
    assert all(f'"fontSize":{font_size}' in output for font_size in (30, 12, 10))
    assert re.search(
        r'Row\("between".*?Text\("1".*?Text\("小时".*?Text\("21".*?Text\("分钟"',
        output,
    )
    assert '"padding":12' in output
    assert '"borderRadius":20' in output
    assert "AppUsageOverview" not in compiled.a2ui
    assert "Template" not in compiled.a2ui
    assert "Progress" not in compiled.a2ui


@pytest.mark.parametrize("size", ["2x2", "2x4"])
def test_parent_control_action_uses_approved_36vp_pill_and_candidate_icons(size: str):
    task_spec = _app_usage_task(
        size=size,
        query="显示抖音今天的使用时长并管控时间",
        actions=[_parent_control_action()],
        assets=_app_assets(),
    )
    source = (
        'HeroActionLayout(AppUsageOverview({"variant":"singleApp","role":"hero",'
        '"appIcon":"resources/base/media/douyin.svg"}),'
        'PillAction({"actionId":"event.open.settings.parentControl",'
        '"icon":"resources/base/media/parent-control.svg"}));'
    )
    compiled, projection = _compile_app_usage(task_spec, source)
    output = compiled.effective_output

    assert projection.contract.content_action_ids == (
        "event.open.settings.parentControl",
    )
    assert 'Text("管控时间", "compact-action"' in output
    assert '"height":36' in output
    assert '"fontSize":14' in output
    assert 'Image("resources/base/media/douyin.svg", "icon", {"width":20,"height":20' in output
    assert (
        'Image("resources/base/media/parent-control.svg", "icon", {"width":20,"height":20'
        in output
    )


def test_parent_control_action_requires_query_event_and_exact_id():
    approved = _parent_control_action()

    assert approved_app_usage_action_ids(_app_usage_task(actions=[approved])) == ()
    assert approved_app_usage_action_ids(
        _app_usage_task(query="显示抖音今天使用时长并管控时间")
    ) == ()
    assert approved_app_usage_action_ids(
        _app_usage_task(
            query="显示抖音今天使用时长并管控时间",
            actions=[_unrelated_action()],
        )
    ) == ()
    assert approved_app_usage_action_ids(
        _app_usage_task(
            query="显示抖音今天使用时长并管控时间",
            actions=[approved],
        )
    ) == ("event.open.settings.parentControl",)


def test_app_and_action_icons_are_optional_and_semantically_checked():
    no_icons, _projection = _compile_app_usage(
        _app_usage_task(
            query="显示抖音今天使用时长并管控时间",
            actions=[_parent_control_action()],
        ),
        'HeroActionLayout(AppUsageOverview({"variant":"singleApp","role":"hero"}),'
        'PillAction({"actionId":"event.open.settings.parentControl"}));',
    )
    assert "Image(" not in no_icons.effective_output

    task_spec = _app_usage_task(
        query="显示抖音今天使用时长并管控时间",
        actions=[_parent_control_action()],
        assets=_app_assets(),
    )
    with pytest.raises(TerseDslNested2ConversionError, match="app semantics"):
        _compile_app_usage(
            task_spec,
            'HeroActionLayout(AppUsageOverview({"variant":"singleApp","role":"hero",'
            '"appIcon":"resources/base/media/weather.svg"}),'
            'PillAction({"actionId":"event.open.settings.parentControl"}));',
        )
    with pytest.raises(TerseDslNested2ConversionError, match="control intent"):
        _compile_app_usage(
            task_spec,
            'HeroActionLayout(AppUsageOverview({"variant":"singleApp","role":"hero"}),'
            'IconAction({"actionId":"event.open.settings.parentControl",'
            '"icon":"resources/base/media/parent-control.svg"}));',
        )
    with pytest.raises(TerseDslNested2ConversionError, match="does not match"):
        _compile_app_usage(
            task_spec,
            'HeroActionLayout(AppUsageOverview({"variant":"singleApp","role":"hero"}),'
            'PillAction({"actionId":"event.open.settings.parentControl",'
            '"icon":"resources/base/media/weather.svg"}));',
        )


def test_layout_selection_uses_action_only_when_semantically_closed():
    registry = get_cardplan_registry()
    scope = AdvancedScopeBrief(
        themeId="digital-wellbeing-neutral-dark",
        advancedComponentIds=("AppUsageOverview",),
    )
    no_action = resolve_scope_layout_ids(scope, _app_usage_task(), registry)
    unrelated = resolve_scope_layout_ids(
        scope,
        _app_usage_task(actions=[_unrelated_action()]),
        registry,
    )
    approved = resolve_scope_layout_ids(
        scope,
        _app_usage_task(
            query="显示抖音今天使用时长并管控时间",
            actions=[_parent_control_action()],
        ),
        registry,
    )

    assert no_action == ("SingleFocusLayout",)
    assert unrelated == ("SingleFocusLayout",)
    assert "HeroActionLayout" in approved


@pytest.mark.parametrize(
    "source",
    [
        'SingleFocusLayout(AppUsageOverview({"variant":"dailyLimit","role":"hero"}));',
        'SingleFocusLayout(AppUsageOverview({"variant":"singleApp","role":"support"}));',
        'HeroSupportLayout(AppUsageOverview({"variant":"singleApp","role":"hero"}),'
        'Text("状态需可信能力", "body"));',
    ],
)
def test_direct_syntax_rejects_disabled_variants_roles_and_placeholders(source: str):
    with pytest.raises(TerseDslNested2ConversionError):
        _compile_app_usage(_app_usage_task(), source)


@pytest.mark.asyncio
async def test_missing_trusted_system_mode_cannot_be_selected_or_combined():
    task_spec = _app_usage_task()
    messages = build_advanced_scope_prompt(
        task_spec,
        extract_data_shape(task_spec),
        get_cardplan_registry(),
        available_capability_ids=("GetAppUsageDuration",),
    )
    payload = json.loads(messages[1]["content"])
    assert "SystemModeOverview" not in {
        item["id"] for item in payload["advancedComponents"]
    }

    async def generate_json(_messages, _phase):
        return {
            "scopeVersion": "advanced-scope-brief/1",
            "themeId": "digital-wellbeing-neutral-dark",
            "advancedComponentIds": ["AppUsageOverview", "SystemModeOverview"],
        }

    with pytest.raises(ValueError, match="outside trusted candidates"):
        await plan_advanced_scope_with_llm(
            task_spec,
            extract_data_shape(task_spec),
            generate_json,
            get_cardplan_registry(),
            available_capability_ids=("GetAppUsageDuration",),
        )
