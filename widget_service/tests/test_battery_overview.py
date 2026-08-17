"""BatteryOverview admission, projection, lowering, asset, and action tests."""

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
    apply_content_selectors,
    approved_battery_power_action_ids,
    battery_overview_is_eligible,
    extract_battery_overview_facts,
    project_content_component_facts,
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


def _power_action() -> EventAction:
    return EventAction(
        id="event.setPowerSavingMode",
        displayLabel="省电模式",
        call="clickToIntent",
        args={"intentName": "PowerSavingMode"},
    )


def _battery_assets() -> list[dict[str, Any]]:
    return [
        {
            "id": "asset.phone-battery",
            "src": "resources/base/media/phone-battery.svg",
            "description": "手机电池内容图标",
            "sceneTags": ["battery", "phone"],
        },
        {
            "id": "asset.power-saving",
            "src": "resources/base/media/power-saving.svg",
            "description": "开启省电模式的叶子图标",
            "sceneTags": ["power-saving", "leaf"],
        },
        {
            "id": "asset.weather",
            "src": "resources/base/media/weather.svg",
            "description": "天气图标",
            "sceneTags": ["weather"],
        },
    ]


def _battery_task(
    *,
    size: str = "2x2",
    query: str = "显示手机电量和充电状态",
    soc: Any = 68,
    soc_text: Any = "68%",
    capacity: Any = "电量正常",
    charging: Any = "未充电",
    actions: list[EventAction] | None = None,
    assets: list[dict[str, Any]] | None = None,
    extra_fields: dict[str, Any] | None = None,
) -> TaskSpec:
    provider: dict[str, Any] = {}
    if soc is not _MISSING:
        provider["batterySOC"] = _field(soc, "number")
    if soc_text is not _MISSING:
        provider["batterySOCText"] = _field(soc_text)
    if capacity is not _MISSING:
        provider["batteryCapacityLevelDesc"] = _field(capacity)
    if charging is not _MISSING:
        provider["chargingStatusDesc"] = _field(charging)
    provider.update(extra_fields or {})
    return TaskSpec(
        userQuery=query,
        size=size,
        eventCandidates=actions or [],
        dataModelSchema={"GetPhoneBatteryInfo": provider},
        assetCandidates=assets or [],
    )


def _compile_battery(task_spec: TaskSpec, source: str):
    capability_ids = {"GetPhoneBatteryInfo"}
    projected, card_spec, registry = prepare_provider_scope_projection(
        task_spec,
        capability_ids,
        ("BatteryOverview",),
    )
    projection = build_ux_mixed_prompt(
        task_spec=projected,
        card_spec=card_spec,
        scope=AdvancedScopeBrief(
            themeId="system-low-power-blue",
            advancedComponentIds=("BatteryOverview",),
        ),
        registry=registry,
    )
    projection = provider_direct_shadow_projection(
        projection,
        source,
        ("BatteryOverview",),
    )
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
    return compiled, projection, projected


@pytest.mark.parametrize(
    ("size", "soc", "soc_text", "capacity", "charging", "variant"),
    [
        ("2x2", 68, "68%", "电量正常", "未充电", "normal"),
        ("2x2", 80, "80%", "电量正常", "正在充电", "charging"),
        ("2x2", 18, "18%", "电量较低", "未充电", "low"),
        ("2x4", 68, "68%", "电量正常", "未充电", "normal"),
    ],
)
def test_single_battery_direct_constructor_lowers_to_standard_a2ui(
    size: str,
    soc: int,
    soc_text: str,
    capacity: str,
    charging: str,
    variant: str,
):
    task = _battery_task(
        size=size,
        soc=soc,
        soc_text=soc_text,
        capacity=capacity,
        charging=charging,
        assets=_battery_assets(),
    )
    source = (
        'SingleFocusLayout(BatteryOverview({"variant":"'
        + variant
        + '","role":"hero","batteryIcon":'
        '"resources/base/media/phone-battery.svg"}));'
    )

    compiled, projection, _projected = _compile_battery(task, source)

    assert projection.contract.required_template_groups == ()
    assert compiled.stats.template_used_ids == ()
    assert "BatteryOverview" not in compiled.effective_output
    assert "Template" not in compiled.effective_output
    assert "BatteryOverview" not in compiled.a2ui
    assert '"borderRadius":20,"padding":12' in compiled.effective_output
    assert '"color":"#FFF9A01E"' in compiled.effective_output
    assert '"backgroundColor":"#1A000000"' in compiled.effective_output
    assert '"width":52,"height":52,"strokeWidth":6' in compiled.effective_output
    assert '"width":24,"height":24' in compiled.effective_output
    assert '"fillColor":"#99000000"' in compiled.effective_output
    expected_font_sizes = (12, 14, 10) if size == "2x4" else (12,)
    assert all(
        f'"fontSize":{font_size}' in compiled.effective_output for font_size in expected_font_sizes
    )
    if size == "2x4":
        assert 'Row("between"' in compiled.effective_output
        assert compiled.effective_output.index('Text("设备电量"') < (
            compiled.effective_output.index('"type":"ring"')
        )


def test_zero_percent_is_valid_and_text_only_soc_is_derived():
    zero = _battery_task(soc=0, soc_text="0%", capacity="电量耗尽")
    assert battery_overview_is_eligible(zero, {"GetPhoneBatteryInfo"})
    compiled, _projection, _projected = _compile_battery(
        zero,
        'SingleFocusLayout(BatteryOverview({"variant":"low","role":"hero"}));',
    )
    assert '"value":0,"total":100' in compiled.effective_output

    text_only = _battery_task(soc=_MISSING, soc_text="42%")
    facts = extract_battery_overview_facts(text_only.dataModelSchema)
    assert facts is not None
    assert facts.level_percent == 42


def test_2x2_battery_uses_compact_description_and_bottom_left_ring():
    task = _battery_task(
        query="显示手机电量并开启省电模式",
        charging="充电中",
        actions=[_power_action()],
        assets=_battery_assets(),
    )
    compiled, _projection, _projected = _compile_battery(
        task,
        'HeroActionLayout(BatteryOverview({"variant":"charging","role":"hero",'
        '"batteryIcon":"resources/base/media/phone-battery.svg"}),'
        'IconAction({"actionId":"event.setPowerSavingMode",'
        '"icon":"resources/base/media/power-saving.svg"}));',
    )
    output = compiled.effective_output

    assert 'Text("电量 68%，电量正常，充电中", "body",' in output
    description = output.split('Text("电量 68%，电量正常，充电中"', 1)[1]
    assert '"fontSize":12' in description
    assert '"maxLines":2' in description
    assert '"alignContent":"bottomStart"' in output
    assert '"alignContent":"bottomEnd"' in output
    assert output.index('"alignContent":"bottomStart"') < output.index('"alignContent":"bottomEnd"')
    assert 'Text("68%", "compact-title"' not in output
    assert 'Text("充电中", "subtitle"' not in output
    assert '"padding":{"right":38,"bottom":38}' not in output


@pytest.mark.parametrize(
    "task_spec",
    [
        _battery_task(soc=42, soc_text="41%"),
        _battery_task(soc=101, soc_text="42%"),
        _battery_task(soc="42", soc_text="42%"),
        _battery_task(soc=-1, soc_text="-1%"),
        _battery_task(soc=101, soc_text="101%"),
        _battery_task(soc_text="unknown"),
        _battery_task(soc_text=_MISSING),
        _battery_task(capacity=_MISSING),
        _battery_task(capacity=""),
        _battery_task(charging=_MISSING),
        _battery_task(charging=""),
    ],
)
def test_battery_rejects_inconsistent_out_of_range_or_incomplete_facts(
    task_spec: TaskSpec,
):
    assert extract_battery_overview_facts(task_spec.dataModelSchema) is None
    assert not battery_overview_is_eligible(task_spec, {"GetPhoneBatteryInfo"})


@pytest.mark.parametrize(
    "query",
    [
        "显示电池健康度",
        "显示电池温度",
        "显示电池电压和电流",
        "显示充电器类型",
        "显示剩余续航",
        "显示预计充满时间",
        "显示耳机电量",
    ],
)
def test_battery_admission_rejects_unsupported_or_external_only_requests(query: str):
    task = _battery_task(query=query)
    assert not battery_overview_is_eligible(task, {"GetPhoneBatteryInfo"})


def test_phone_plus_external_battery_request_keeps_phone_battery_eligible():
    task = _battery_task(query="show phone and earphone battery")
    assert battery_overview_is_eligible(task, {"GetPhoneBatteryInfo"})


def test_battery_projection_retains_only_four_trusted_fields():
    task = _battery_task(
        extra_fields={
            "batteryHealth": _field("良好"),
            "temperature": _field("31°C"),
            "voltage": _field("4.1V"),
            "remainingRuntime": _field("8小时"),
        }
    )
    projected = project_content_component_facts(
        apply_content_selectors(task, {"GetPhoneBatteryInfo"}),
        {"GetPhoneBatteryInfo"},
        ("BatteryOverview",),
    )
    fields = projected.dataModelSchema["data"]["BatteryOverview"]
    assert set(fields) == {
        "batterySOC",
        "batterySOCText",
        "batteryCapacityLevelDesc",
        "chargingStatusDesc",
    }
    assert "batteryHealth" not in json.dumps(projected.dataModelSchema, ensure_ascii=False)


def test_first_layer_and_registry_use_direct_battery_not_old_json_template():
    task = _battery_task()
    messages = build_advanced_scope_prompt(
        task,
        extract_data_shape(task),
        get_cardplan_registry(),
        available_capability_ids=("GetPhoneBatteryInfo",),
    )
    payload = json.loads(messages[1]["content"])
    battery = next(
        item for item in payload["advancedComponents"] if item["id"] == "BatteryOverview"
    )
    assert battery["variants"] == ["normal", "charging", "low"]
    assert "0 到 100" in messages[0]["content"]

    registry = get_cardplan_registry()
    capability = registry.require_ux_business_component("BatteryOverview")
    assert capability.implementation == "template"
    assert capability.local_template_ids == ("BatteryOverview@1",)
    assert "ux-battery-overview@2" in registry.templates


@pytest.mark.asyncio
async def test_forced_first_layer_battery_selection_is_rejected_for_forbidden_request():
    task = _battery_task(query="显示电池温度")

    async def generate_json(_messages, _phase):
        return {
            "scopeVersion": "advanced-scope-brief/1",
            "themeId": "system-low-power-blue",
            "advancedComponentIds": ["BatteryOverview"],
        }

    with pytest.raises(
        ValueError,
        match="no provider-backed UX Business Component candidate|outside trusted candidates",
    ):
        await plan_advanced_scope_with_llm(
            task,
            extract_data_shape(task),
            generate_json,
            get_cardplan_registry(),
            available_capability_ids=("GetPhoneBatteryInfo",),
        )


def test_battery_icon_is_optional_and_semantically_validated():
    compiled, _projection, _projected = _compile_battery(
        _battery_task(),
        'SingleFocusLayout(BatteryOverview({"variant":"normal","role":"hero"}));',
    )
    assert "Image(" not in compiled.effective_output

    bad_source = (
        'SingleFocusLayout(BatteryOverview({"variant":"normal","role":"hero",'
        '"batteryIcon":"resources/base/media/weather.svg"}));'
    )
    with pytest.raises(TerseDslNested2ConversionError, match="does not match"):
        _compile_battery(_battery_task(assets=_battery_assets()), bad_source)

    with pytest.raises(TerseDslNested2ConversionError, match="trusted battery state"):
        _compile_battery(
            _battery_task(soc=18, soc_text="18%", capacity="电量较低"),
            'SingleFocusLayout(BatteryOverview({"variant":"normal","role":"hero"}));',
        )


def test_power_saving_action_requires_query_event_and_size_specific_control():
    task_2x2 = _battery_task(
        query="显示低电量并开启省电模式",
        soc=18,
        soc_text="18%",
        capacity="电量较低",
        actions=[_power_action()],
        assets=_battery_assets(),
    )
    assert approved_battery_power_action_ids(task_2x2) == ("event.setPowerSavingMode",)
    compiled, _projection, _projected = _compile_battery(
        task_2x2,
        'HeroActionLayout(BatteryOverview({"variant":"low","role":"hero"}),'
        'IconAction({"actionId":"event.setPowerSavingMode",'
        '"icon":"resources/base/media/power-saving.svg"}));',
    )
    assert '"width":30,"height":30' in compiled.effective_output
    assert '"width":16,"height":16' in compiled.effective_output
    assert '"backgroundColor":"#FFF9A01E"' in compiled.effective_output
    assert '"fillColor":"#FFFFFFFF"' in compiled.effective_output

    task_2x4 = task_2x2.model_copy(update={"size": "2x4"})
    wide, _projection, _projected = _compile_battery(
        task_2x4,
        'HeroActionLayout(BatteryOverview({"variant":"low","role":"hero"}),'
        'PillAction({"actionId":"event.setPowerSavingMode"}));',
    )
    assert '"height":36' in wide.effective_output
    assert '"fontSize":14' in wide.effective_output

    missing_event = _battery_task(query="显示低电量并开启省电模式", assets=_battery_assets())
    _compiled, projection, _projected = _compile_battery(
        missing_event,
        'SingleFocusLayout(BatteryOverview({"variant":"normal","role":"hero"}));',
    )
    assert projection.contract.content_action_ids == ()
    with pytest.raises(
        TerseDslNested2ConversionError,
        match="approved Layout Component|not approved",
    ):
        _compile_battery(
            missing_event,
            'HeroActionLayout(BatteryOverview({"variant":"normal","role":"hero"}),'
            'IconAction({"actionId":"event.setPowerSavingMode",'
            '"icon":"resources/base/media/power-saving.svg"}));',
        )

    missing_icon = _battery_task(
        query="显示低电量并开启省电模式",
        actions=[_power_action()],
    )
    assert approved_battery_power_action_ids(missing_icon) == ()

    wrong_icon = (
        'HeroActionLayout(BatteryOverview({"variant":"low","role":"hero"}),'
        'IconAction({"actionId":"event.setPowerSavingMode",'
        '"icon":"resources/base/media/weather.svg"}));'
    )
    repaired, _projection, _projected = _compile_battery(task_2x2, wrong_icon)
    assert "power-saving.svg" in repaired.effective_output
    assert "weather.svg" not in repaired.effective_output


def test_power_saving_action_normalizes_to_the_only_matching_approved_icon():
    task = _battery_task(
        query="显示电量并开启省电模式",
        actions=[_power_action()],
        assets=[
            {
                "id": "asset.bolt",
                "src": "resources/base/media/bolt_fill.svg",
                "description": "充电闪电图标",
                "sceneTags": ["battery", "power"],
            },
            {
                "id": "asset.battery-leaf",
                "src": "resources/base/media/battery_leaf_fill.svg",
                "description": "电池与绿叶组合图标，适用场景：节能模式",
                "sceneTags": ["battery", "power"],
            },
        ],
    )
    compiled, _projection, _projected = _compile_battery(
        task,
        'HeroActionLayout(BatteryOverview({"variant":"normal","role":"hero"}),'
        'IconAction({"actionId":"event.setPowerSavingMode",'
        '"icon":"resources/base/media/bolt_fill.svg"}));',
    )
    assert "battery_leaf_fill.svg" in compiled.effective_output
    assert "bolt_fill.svg" not in compiled.effective_output


def test_battery_2x2_rejects_pill_action_and_nested_or_wrong_role():
    task = _battery_task(
        query="显示低电量并开启省电模式",
        actions=[_power_action()],
        assets=_battery_assets(),
    )
    with pytest.raises(TerseDslNested2ConversionError, match="only accepts an IconAction"):
        _compile_battery(
            task,
            'HeroActionLayout(BatteryOverview({"variant":"low","role":"hero"}),'
            'PillAction({"actionId":"event.setPowerSavingMode"}));',
        )
    with pytest.raises(TerseDslNested2ConversionError, match="direct layout child"):
        _compile_battery(
            _battery_task(),
            'SingleFocusLayout(Column("compact",BatteryOverview('
            '{"variant":"normal","role":"hero"})));',
        )
    with pytest.raises(TerseDslNested2ConversionError, match="requires a hero"):
        _compile_battery(
            _battery_task(),
            'SingleFocusLayout(BatteryOverview({"variant":"normal","role":"peer"}));',
        )


@pytest.mark.parametrize("size", ["2x2", "2x4"])
def test_phone_and_earphone_compose_as_peer_businesses(size: str):
    task = _battery_task(
        size=size,
        query="同时显示手机和耳机电量",
    ).model_copy(
        update={
            "dataModelSchema": {
                **_battery_task().dataModelSchema,
                "GetEarphoneInfo": {
                    "isConnected": _field(True, "boolean"),
                    "earphoneName": _field("FreeBuds Pro"),
                    "leftBatteryLevel": _field(76, "number"),
                    "rightBatteryLevel": _field(72, "number"),
                    "batteryLevel": _field(64, "number"),
                },
            }
        }
    )
    capability_ids = {"GetPhoneBatteryInfo", "GetEarphoneInfo"}
    component_ids = ("BatteryOverview", "BluetoothDeviceOverview")
    projected, card_spec, registry = prepare_provider_scope_projection(
        task,
        capability_ids,
        component_ids,
    )
    scope = AdvancedScopeBrief(
        themeId="audio-product-neutral-violet",
        advancedComponentIds=("BatteryOverview", "BluetoothDeviceOverview"),
    )
    projection = build_ux_mixed_prompt(
        task_spec=projected,
        card_spec=card_spec,
        scope=scope,
        registry=registry,
    )
    layout = "PeerPairLayout" if size == "2x2" else "HeroSupportLayout"
    source = (
        layout + '(BatteryOverview({"variant":"normal","role":"hero"}),'
        'BluetoothDeviceOverview({"variant":"earbuds","role":"support"}));'
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
    )

    assert projection.contract.required_template_groups == ()
    assert compiled.stats.template_used_ids == ()
    assert "BatteryOverview" not in compiled.a2ui
    assert "BluetoothDeviceOverview" not in compiled.a2ui
    assert compiled.effective_output.count('"type":"ring"') == 3
    assert '"width":56,"height":56' in compiled.effective_output
    assert compiled.effective_output.count('Text("设备电量"') == 1
    if size == "2x4":
        assert "充电盒 64%" in compiled.effective_output


def test_provider_template_rejects_battery_variant_from_wrong_trusted_state() -> None:
    with pytest.raises(TerseDslNested2ConversionError, match="trusted state"):
        _compile_battery(
            _battery_task(),
            'SingleFocusLayout(Template("BatteryOverview@1","low",{}));',
        )
