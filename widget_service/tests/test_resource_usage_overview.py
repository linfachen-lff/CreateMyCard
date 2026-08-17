"""ResourceUsageOverview admission, direct lowering, and layout tests."""

from __future__ import annotations

import json
import math
from typing import Any

import pytest

from models.generation import EventAction, TaskSpec
from overview_test_support import (
    prepare_provider_scope_projection,
    provider_direct_shadow_projection,
)
from services.advanced_component_pipeline.content_selectors import (
    approved_memory_cleanup_action_ids,
    extract_resource_usage_overview_facts,
    project_content_component_facts,
    resource_usage_overview_is_eligible,
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


def _field(value: Any, data_type: str) -> dict[str, Any]:
    return {"type": data_type, "sampleValue": value}


def _cleanup_action() -> EventAction:
    return EventAction(
        id="event.clean.memory",
        displayLabel="一键清理",
        call="clickToApi",
        args={"operation": "cleanMemory"},
    )


def _resource_assets() -> list[dict[str, Any]]:
    return [
        {
            "id": "asset.memory",
            "src": "resources/base/media/memory.svg",
            "description": "系统内存资源图标",
            "sceneTags": ["memory", "resource"],
        },
        {
            "id": "asset.clean-memory",
            "src": "resources/base/media/clean-memory.svg",
            "description": "一键清理内存动作图标",
            "sceneTags": ["clean", "memory"],
        },
        {
            "id": "asset.battery",
            "src": "resources/base/media/battery.svg",
            "description": "手机电量图标",
            "sceneTags": ["battery", "power", "phone"],
        },
        {
            "id": "asset.weather",
            "src": "resources/base/media/weather.svg",
            "description": "天气图标",
            "sceneTags": ["weather"],
        },
    ]


def _resource_task(
    *,
    size: str = "2x2",
    query: str = "显示系统内存占用",
    usage_percent: Any = 43.75,
    usage_type: str = "number",
    available_mem_text: Any = "4.50 GB",
    available_type: str = "string",
    total_mem_text: Any = "8.00 GB",
    total_type: str = "string",
    free_mem_text: Any = "1.20 GB",
    include_usage: bool = True,
    include_available: bool = True,
    include_total: bool = True,
    actions: list[EventAction] | None = None,
    assets: list[dict[str, Any]] | None = None,
) -> TaskSpec:
    provider: dict[str, Any] = {
        "freeMemText": _field(free_mem_text, "string"),
    }
    if include_usage:
        provider["usagePercent"] = _field(usage_percent, usage_type)
    if include_available:
        provider["availableMemText"] = _field(available_mem_text, available_type)
    if include_total:
        provider["totalMemText"] = _field(total_mem_text, total_type)
    return TaskSpec(
        userQuery=query,
        size=size,
        eventCandidates=actions or [],
        dataModelSchema={"GetSystemMemInfo": provider},
        assetCandidates=assets or [],
    )


def _compile_resource(task_spec: TaskSpec, source: str):
    capability_ids = {"GetSystemMemInfo"}
    component_ids = ("ResourceUsageOverview",)
    projected, card_spec, registry = prepare_provider_scope_projection(
        task_spec,
        capability_ids,
        component_ids,
    )
    scope = AdvancedScopeBrief(
        themeId="device-clean-blue-teal",
        advancedComponentIds=("ResourceUsageOverview",),
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


def _resource_battery_task(*, size: str, with_action: bool) -> TaskSpec:
    task_spec = _resource_task(
        size=size,
        query=("显示内存占用、手机电量并一键清理" if with_action else "显示内存占用和手机电量"),
        actions=[_cleanup_action()] if with_action else [],
        assets=_resource_assets(),
    )
    schema = dict(task_spec.dataModelSchema)
    schema["GetPhoneBatteryInfo"] = {
        "batterySOC": _field(68, "number"),
        "batterySOCText": _field("68%", "string"),
        "batteryCapacityLevelDesc": _field("电量充足", "string"),
        "chargingStatusDesc": _field("未充电", "string"),
    }
    return task_spec.model_copy(update={"dataModelSchema": schema})


def _compile_resource_battery(task_spec: TaskSpec, source: str):
    capability_ids = {"GetPhoneBatteryInfo", "GetSystemMemInfo"}
    component_ids = ("ResourceUsageOverview", "BatteryOverview")
    projected, card_spec, registry = prepare_provider_scope_projection(
        task_spec,
        capability_ids,
        component_ids,
    )
    scope = AdvancedScopeBrief(
        themeId="meeting-paper-neutral",
        advancedComponentIds=component_ids,
    )
    business_title = "内存与电量"
    projection = build_ux_mixed_prompt(
        task_spec=projected,
        card_spec={**card_spec, "title": business_title},
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
        business_title=business_title,
    )
    return compiled, projection


@pytest.mark.parametrize("usage_percent", [0, 100])
def test_resource_usage_gate_accepts_zero_and_one_hundred(usage_percent: int):
    task_spec = _resource_task(usage_percent=usage_percent)

    facts = extract_resource_usage_overview_facts(task_spec.dataModelSchema)
    projected = project_content_component_facts(
        task_spec,
        {"GetSystemMemInfo"},
        ("ResourceUsageOverview",),
    )

    assert facts is not None
    assert facts.usage_percent == usage_percent
    assert resource_usage_overview_is_eligible(task_spec, {"GetSystemMemInfo"})
    resource = projected.dataModelSchema["data"]["ResourceUsageOverview"]
    assert set(resource) == {"usagePercent", "availableMemText", "totalMemText"}
    assert "freeMemText" not in json.dumps(projected.dataModelSchema)


@pytest.mark.parametrize(
    "task_spec",
    [
        _resource_task(include_usage=False),
        _resource_task(include_available=False),
        _resource_task(include_total=False),
        _resource_task(usage_percent=-0.01),
        _resource_task(usage_percent=100.01),
        _resource_task(usage_percent=math.nan),
        _resource_task(usage_percent=math.inf),
        _resource_task(usage_percent="43", usage_type="string"),
        _resource_task(usage_percent=True, usage_type="boolean"),
        _resource_task(available_mem_text=4.5, available_type="number"),
        _resource_task(total_mem_text=" "),
    ],
)
def test_resource_usage_gate_rejects_missing_out_of_range_and_wrong_types(
    task_spec: TaskSpec,
):
    assert extract_resource_usage_overview_facts(task_spec.dataModelSchema) is None
    assert not resource_usage_overview_is_eligible(task_spec, {"GetSystemMemInfo"})


@pytest.mark.parametrize(
    "query",
    [
        "显示存储占用",
        "显示磁盘空间",
        "清理应用缓存",
        "显示进程明细",
        "显示 CPU 和 GPU 占用",
        "显示 swap 使用量",
        "显示内存趋势",
        "显示内存历史曲线",
        "只显示 freeMemText",
        "只显示完全空闲内存",
    ],
)
def test_resource_usage_scope_rejects_unsupported_intents(query: str):
    task_spec = _resource_task(query=query)

    assert not resource_usage_overview_is_eligible(task_spec, {"GetSystemMemInfo"})
    with pytest.raises(ValueError, match="no provider-backed"):
        build_advanced_scope_prompt(
            task_spec,
            extract_data_shape(task_spec),
            get_cardplan_registry(),
            available_capability_ids=("GetSystemMemInfo",),
        )


def test_resource_usage_does_not_aggregate_unrelated_fields():
    task_spec = TaskSpec(
        userQuery="显示内存占用",
        size="2x2",
        dataModelSchema={
            "GetSystemMemInfo": {
                "usagePercent": _field(50, "number"),
                "availableMemText": _field("4 GB", "string"),
            },
            "unrelated": {"totalMemText": _field("8 GB", "string")},
        },
        assetCandidates=[],
    )

    assert extract_resource_usage_overview_facts(task_spec.dataModelSchema) is None


def test_first_layer_exposes_only_direct_memory_variant_without_template_dependency():
    task_spec = _resource_task()
    messages = build_advanced_scope_prompt(
        task_spec,
        extract_data_shape(task_spec),
        get_cardplan_registry(),
        available_capability_ids=("GetSystemMemInfo",),
    )
    payload = json.loads(messages[1]["content"])
    candidate = next(
        item for item in payload["advancedComponents"] if item["id"] == "ResourceUsageOverview"
    )
    capability = get_cardplan_registry().require_ux_business_component("ResourceUsageOverview")

    assert candidate["variants"] == ["memory"]
    assert capability.roles == ("hero", "peer")
    assert "storage 未启用" in candidate["description"]
    assert capability.implementation == "template"
    assert capability.local_template_ids == ("ResourceUsageOverview@1",)
    assert "ux-resource-usage-overview" not in json.dumps(candidate, ensure_ascii=False)


@pytest.mark.asyncio
async def test_forced_invalid_resource_selection_is_rejected_after_first_layer():
    task_spec = _resource_task(usage_percent=101)

    async def generate_json(_messages, _phase):
        return {
            "scopeVersion": "advanced-scope-brief/1",
            "themeId": "device-clean-blue-teal",
            "advancedComponentIds": ["ResourceUsageOverview"],
        }

    with pytest.raises(ValueError, match="no provider-backed"):
        await plan_advanced_scope_with_llm(
            task_spec,
            extract_data_shape(task_spec),
            generate_json,
            get_cardplan_registry(),
            available_capability_ids=("GetSystemMemInfo",),
        )


def test_memory_cleanup_action_requires_query_and_registered_event_candidate():
    event = _cleanup_action()

    assert (
        approved_memory_cleanup_action_ids(_resource_task(query="显示内存占用", actions=[event]))
        == ()
    )
    assert approved_memory_cleanup_action_ids(_resource_task(query="显示内存占用并一键清理")) == ()
    assert approved_memory_cleanup_action_ids(
        _resource_task(query="显示内存占用并一键清理", actions=[event])
    ) == ("event.clean.memory",)


@pytest.mark.parametrize("size", ["2x2", "2x4"])
@pytest.mark.parametrize("usage_percent", [0, 100])
def test_single_resource_direct_constructor_lowers_to_standard_a2ui(
    size: str,
    usage_percent: int,
):
    task_spec = _resource_task(size=size, usage_percent=usage_percent)
    compiled, projection = _compile_resource(
        task_spec,
        'SingleFocusLayout(ResourceUsageOverview({"variant":"memory","role":"hero"}));',
    )

    assert projection.requested_template_ids == ()
    assert projection.contract.required_template_groups == ()
    assert "ResourceUsageOverview" not in compiled.effective_output
    assert "Template" not in compiled.effective_output
    assert f'"value":{usage_percent}' in compiled.effective_output
    assert '"width":52' in compiled.effective_output
    assert '"strokeWidth":6' in compiled.effective_output
    assert '"borderRadius":20' in compiled.effective_output
    assert '"padding":12' in compiled.effective_output
    assert all(f'"fontSize":{font_size}' in compiled.effective_output for font_size in (10, 12, 14))
    assert "内存不足" not in compiled.effective_output
    assert "正常" not in compiled.effective_output
    assert "告警" not in compiled.effective_output
    assert "freeMemText" not in compiled.effective_output
    assert "ResourceUsageOverview" not in compiled.a2ui
    assert "Template" not in compiled.a2ui


@pytest.mark.parametrize("size", ["2x2", "2x4"])
def test_resource_title_is_top_level_and_ring_text_uses_rounded_integer(size: str):
    compiled, _projection = _compile_resource(
        _resource_task(size=size, usage_percent=43.75),
        'SingleFocusLayout(ResourceUsageOverview({"variant":"memory","role":"hero"}));',
    )
    output = compiled.effective_output

    title_index = output.index('Text("内存占用", "compact-title", {"fontSize":12')
    content_index = output.index('Row("between"', title_index)
    assert title_index < content_index
    assert output.count('Text("内存占用"') == 1
    assert 'Text("44", "body", {"fontSize":14' in output
    assert 'Text("43.75", "body"' not in output
    assert '"value":43.75' in output


def test_resource_percentage_text_rounds_half_up_without_changing_chart_value():
    compiled, _projection = _compile_resource(
        _resource_task(usage_percent=42.5),
        'SingleFocusLayout(ResourceUsageOverview({"variant":"memory","role":"hero"}));',
    )

    assert 'Text("43", "body", {"fontSize":14' in compiled.effective_output
    assert '"value":42.5' in compiled.effective_output


def test_resource_percentage_without_icon_is_fixed_inside_ring():
    compiled, _projection = _compile_resource(
        _resource_task(usage_percent=43.75),
        'SingleFocusLayout(ResourceUsageOverview({"variant":"memory","role":"hero"}));',
    )
    output = compiled.effective_output
    stack_index = output.index('Stack("overlay", {"width":52,"height":52')
    progress_index = output.index('"type":"ring"', stack_index)
    percent_row_index = output.index(
        'Row("between", {"itemMargin":1,"justifyContent":"center",'
        '"alignItems":"bottom","constraintSize":{"minWidth":0,"minHeight":0},'
        '"width":52}',
        progress_index,
    )

    assert stack_index < progress_index < percent_row_index
    assert percent_row_index < output.index('Text("44"', percent_row_index)
    update = json.loads(compiled.a2ui.splitlines()[1])["updateComponents"]
    components = update["components"]
    progress = next(
        item
        for item in components
        if item["component"] == "Progress" and item.get("value") == 43.75
    )
    ring_stack = next(
        item
        for item in components
        if item["component"] == "Stack" and progress["id"] in item.get("children", [])
    )
    percent_row = next(
        item
        for item in components
        if item["component"] == "Row" and item["id"] in ring_stack["children"]
    )

    assert percent_row["styles"]["width"] == 52
    assert percent_row["styles"]["justifyContent"] == "center"


def test_resource_peer_without_icon_keeps_percentage_inside_compact_ring():
    task_spec = _resource_battery_task(size="2x2", with_action=False)
    source = (
        'PeerPairLayout(ResourceUsageOverview({"variant":"memory","role":"peer",'
        '"showTitle":false}),BatteryOverview({"variant":"normal","role":"peer",'
        '"showTitle":false}));'
    )
    compiled, _projection = _compile_resource_battery(task_spec, source)
    output = compiled.effective_output
    stack_index = output.index('Stack("overlay", {"width":44,"height":44')
    next_stack_index = output.index('Stack("overlay"', stack_index + 1)
    percent_index = output.index('Text("44"', stack_index)

    assert percent_index < next_stack_index
    assert '"justifyContent":"center"' in output[stack_index:percent_index]
    assert '"width":44' in output[stack_index:percent_index]


@pytest.mark.parametrize("size", ["2x2", "2x4"])
def test_resource_action_uses_36vp_pill_and_candidate_icon(size: str):
    task_spec = _resource_task(
        size=size,
        query="显示内存占用并一键清理",
        actions=[_cleanup_action()],
        assets=_resource_assets(),
    )
    source = (
        'HeroActionLayout(ResourceUsageOverview({"variant":"memory","role":"hero",'
        '"icon":"resources/base/media/memory.svg"}),'
        'PillAction({"actionId":"event.clean.memory",'
        '"icon":"resources/base/media/clean-memory.svg"}));'
    )
    compiled, _projection = _compile_resource(task_spec, source)

    assert '"height":36' in compiled.effective_output
    assert '"fontSize":14' in compiled.effective_output
    assert '"width":24' in compiled.effective_output
    assert '"width":20' in compiled.effective_output
    assert "resources/base/media/memory.svg" in compiled.effective_output
    assert "resources/base/media/clean-memory.svg" in compiled.effective_output
    assert "event.clean.memory" not in compiled.effective_output
    assert "clickToApi" in compiled.effective_output


def test_resource_icons_are_optional_and_unrelated_approved_icon_is_dropped():
    no_asset_task = _resource_task(
        query="显示内存占用并一键清理",
        actions=[_cleanup_action()],
    )
    compiled, _projection = _compile_resource(
        no_asset_task,
        'HeroActionLayout(ResourceUsageOverview({"variant":"memory","role":"hero"}),'
        'PillAction({"actionId":"event.clean.memory"}));',
    )
    assert 'Text("%"' in compiled.effective_output
    assert "Image(" not in compiled.effective_output

    task_spec = _resource_task(assets=_resource_assets())
    compiled, _projection = _compile_resource(
        task_spec,
        'SingleFocusLayout(ResourceUsageOverview({"variant":"memory","role":"hero",'
        '"icon":"resources/base/media/weather.svg"}));',
    )
    assert "resources/base/media/weather.svg" not in compiled.effective_output


def test_resource_unrelated_business_icon_is_dropped_but_cleanup_action_icon_remains():
    task_spec = _resource_task(
        query="显示内存占用并一键清理",
        actions=[_cleanup_action()],
        assets=_resource_assets(),
    )
    compiled, _projection = _compile_resource(
        task_spec,
        'HeroActionLayout(ResourceUsageOverview({"variant":"memory","role":"hero",'
        '"icon":"resources/base/media/weather.svg"}),'
        'PillAction({"actionId":"event.clean.memory",'
        '"icon":"resources/base/media/clean-memory.svg"}));',
    )

    assert "resources/base/media/weather.svg" not in compiled.effective_output
    assert "resources/base/media/clean-memory.svg" in compiled.effective_output


def test_single_resource_false_show_title_is_normalized_to_required_title():
    compiled, _projection = _compile_resource(
        _resource_task(),
        'SingleFocusLayout(ResourceUsageOverview({"variant":"memory","role":"hero",'
        '"showTitle":false}));',
    )

    assert compiled.effective_output.count('Text("内存占用"') == 1


@pytest.mark.parametrize(
    ("size", "with_action", "expected"),
    [
        ("2x2", False, ("PeerPairLayout",)),
        ("2x2", True, ("PeerPairLayout",)),
        ("2x4", False, ("HeroSupportLayout",)),
        ("2x4", True, ("HeroSupportActionLayout", "HeroSupportLayout")),
    ],
)
def test_resource_battery_scope_has_only_approved_multi_business_layouts(
    size: str,
    with_action: bool,
    expected: tuple[str, ...],
):
    task_spec = _resource_task(
        size=size,
        query=("显示内存占用、手机电量并一键清理" if with_action else "显示内存占用和手机电量"),
        actions=[_cleanup_action()] if with_action else [],
    )
    scope = AdvancedScopeBrief(
        themeId="meeting-paper-neutral",
        advancedComponentIds=("ResourceUsageOverview", "BatteryOverview"),
    )

    assert resolve_scope_layout_ids(scope, task_spec, get_cardplan_registry()) == expected


def test_resource_battery_prompt_exposes_titleless_peer_contract_to_llm():
    task_spec = _resource_battery_task(size="2x2", with_action=False)
    _compiled, projection = _compile_resource_battery(
        task_spec,
        'PeerPairLayout(ResourceUsageOverview({"variant":"memory","role":"peer",'
        '"showTitle":false}),BatteryOverview({"variant":"normal","role":"peer",'
        '"showTitle":false}));',
    )
    prompt = "\n".join(message["content"] for message in projection.messages)

    assert '"showTitle?":false' in prompt
    assert 'syntax=Template("ResourceUsageOverview@1","memory|memoryPeer",params)' in prompt
    assert '; syntax=Template("BatteryOverview@1",variant,params)' in prompt
    assert "高级组件之外写独立总标题" in prompt


@pytest.mark.parametrize("with_action", [False, True])
def test_resource_battery_2x2_lowers_to_two_equal_compact_rings(with_action: bool):
    task_spec = _resource_battery_task(size="2x2", with_action=with_action)
    action = (
        ',PillAction({"actionId":"event.clean.memory",'
        '"icon":"resources/base/media/clean-memory.svg"})'
        if with_action
        else ""
    )
    source = (
        'PeerPairLayout({"orientation":"rows"},ResourceUsageOverview('
        '{"variant":"memory","role":"peer",'
        '"icon":"resources/base/media/memory.svg","showTitle":false}),'
        'BatteryOverview({"variant":"normal","role":"peer",'
        '"batteryIcon":"resources/base/media/battery.svg","showTitle":false})'
        + action
        + ");"
    )
    compiled, projection = _compile_resource_battery(task_spec, source)

    assert projection.requested_template_ids == ()
    assert set(projection.contract.required_business_component_ids) == {
        "BatteryOverview",
        "ResourceUsageOverview",
    }
    assert compiled.effective_output.count('"type":"ring"') == 2
    assert compiled.effective_output.count('"width":44') >= 2
    assert compiled.effective_output.count('"strokeWidth":6') == 2
    assert '"layoutWeight":50' in compiled.effective_output
    assert compiled.effective_output.count('"fontSize":10') >= 4
    assert compiled.effective_output.count('"textAlign":"center"') >= 5
    assert compiled.effective_output.count('Text("内存与电量"') == 1
    assert 'Text("内存占用"' not in compiled.effective_output
    assert 'Text("设备电量"' not in compiled.effective_output
    assert compiled.effective_output.index('Text("内存与电量"') < (
        compiled.effective_output.index('"type":"ring"')
    )
    assert compiled.effective_output.count('Text("44"') == 1
    assert compiled.effective_output.count('Text("68%"') == 1
    assert "titleIcon" not in compiled.effective_output
    assert "ResourceUsageOverview" not in compiled.effective_output
    assert "BatteryOverview" not in compiled.effective_output
    assert ("clickToApi" in compiled.effective_output) is with_action


@pytest.mark.parametrize(
    "source",
    [
        'PeerPairLayout(ResourceUsageOverview({"variant":"memory","role":"peer"}),'
        'BatteryOverview({"variant":"normal","role":"peer","showTitle":false}));',
        'PeerPairLayout(ResourceUsageOverview({"variant":"memory","role":"peer",'
        '"showTitle":false}),BatteryOverview({"variant":"normal","role":"peer"}));',
    ],
)
def test_resource_battery_2x2_requires_both_internal_titles_hidden(source: str):
    with pytest.raises(TerseDslNested2ConversionError, match="showTitle=false"):
        _compile_resource_battery(
            _resource_battery_task(size="2x2", with_action=False),
            source,
        )


def test_resource_rejects_non_boolean_title_control():
    with pytest.raises(TerseDslNested2ConversionError, match="showTitle must be a Boolean"):
        _compile_resource(
            _resource_task(),
            'SingleFocusLayout(ResourceUsageOverview({"variant":"memory",'
            '"role":"hero","showTitle":0}));',
        )


@pytest.mark.parametrize("with_action", [False, True])
def test_resource_battery_2x4_lowers_memory_hero_and_battery_support(with_action: bool):
    task_spec = _resource_battery_task(size="2x4", with_action=with_action)
    layout = "HeroSupportActionLayout" if with_action else "HeroSupportLayout"
    action = (
        ',PillAction({"actionId":"event.clean.memory",'
        '"icon":"resources/base/media/clean-memory.svg"})'
        if with_action
        else ""
    )
    source = (
        layout + '(ResourceUsageOverview({"variant":"memory","role":"hero",'
        '"icon":"resources/base/media/memory.svg"}),'
        'BatteryOverview({"variant":"normal","role":"support",'
        '"batteryIcon":"resources/base/media/battery.svg"})' + action + ");"
    )
    compiled, _projection = _compile_resource_battery(task_spec, source)

    memory_index = compiled.effective_output.index("内存占用")
    battery_index = compiled.effective_output.index("设备电量")
    assert memory_index < battery_index
    assert '"layoutWeight":56' in compiled.effective_output
    assert '"layoutWeight":44' in compiled.effective_output
    assert compiled.effective_output.count('"type":"ring"') == 2
    assert '"width":52' in compiled.effective_output
    assert '"width":44' in compiled.effective_output
    assert "titleIcon" not in compiled.effective_output
    assert ("clickToApi" in compiled.effective_output) is with_action


@pytest.mark.parametrize(
    "source",
    [
        'SingleFocusLayout(ResourceUsageOverview({"variant":"storage","role":"hero"}));',
        'SingleFocusLayout(ResourceUsageOverview({"variant":"memory","role":"support"}));',
        'HeroSupportLayout(ResourceUsageOverview({"variant":"memory","role":"hero"}),'
        'Text("4.50 GB", "body"));',
    ],
)
def test_resource_direct_syntax_rejects_storage_role_and_layout_mismatch(source: str):
    with pytest.raises(TerseDslNested2ConversionError):
        _compile_resource(_resource_task(), source)
