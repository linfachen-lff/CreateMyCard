"""BluetoothDeviceOverview admission, lowering, layout, and action tests."""

from __future__ import annotations

import json
from typing import Any

import pytest

from config.config import get_settings
from models.generation import EventAction, TaskSpec
from overview_test_support import (
    prepare_provider_scope_projection,
    provider_direct_shadow_projection,
)
from services.advanced_component_pipeline import content_selectors
from services.advanced_component_pipeline.content_selectors import (
    advanced_component_batch_data_admission,
    approved_bluetooth_music_action_ids,
    bluetooth_device_overview_is_eligible,
    bluetooth_device_overview_variants,
    extract_bluetooth_device_overview_facts,
)
from services.advanced_component_pipeline.data_shape import extract_data_shape
from services.advanced_component_pipeline.models import AdvancedScopeBrief
from services.advanced_component_pipeline.scope_planner import (
    build_advanced_scope_prompt,
    resolve_scope_layout_ids,
    validate_advanced_scope,
)
from services.advanced_component_pipeline.ux_mixed_prompt import build_ux_mixed_prompt
from services.cardplan_template.compiler import compile_ux_layout_card
from services.cardplan_template.registry import get_cardplan_registry
from services.protocol_registry import TERSE_DSL_NESTED2_PROFILE_ID, A2UIProtocolRegistry
from services.terse_dsl_nested2_converter import TerseDslNested2ConversionError

_MISSING = object()


@pytest.fixture(autouse=True)
def _strict_data_admission_by_default(monkeypatch: pytest.MonkeyPatch):
    settings = get_settings()
    monkeypatch.setattr(settings, "enable_widget_batch_recording", False)
    monkeypatch.setattr(
        settings,
        "enable_advanced_component_data_admission_bypass_for_batch",
        False,
    )


def _field(value: Any, data_type: str) -> dict[str, Any]:
    return {"type": data_type, "sampleValue": value}


def _music_action(action_id: str) -> EventAction:
    return EventAction(
        id=action_id,
        displayLabel=("每日推荐" if action_id.endswith("daily") else "心动歌单"),
        call="clickToIntent",
        args={"intentName": action_id},
    )


def _assets() -> list[dict[str, Any]]:
    return [
        {
            "src": "resources/base/media/earphone-source.svg",
            "description": "蓝牙耳机来源图标",
            "sceneTags": ["earphone", "audio", "product"],
        },
        {
            "src": "resources/base/media/left-ear.svg",
            "description": "左耳机图标",
            "sceneTags": ["earphone", "audio"],
        },
        {
            "src": "resources/base/media/right-ear.svg",
            "description": "右耳机图标",
            "sceneTags": ["earphone", "audio"],
        },
        {
            "src": "resources/base/media/phone.svg",
            "description": "手机设备电量图标",
            "sceneTags": ["phone-device", "battery"],
        },
        {
            "src": "resources/base/media/music.svg",
            "description": "每日推荐音乐图标",
            "sceneTags": ["music", "audio"],
        },
        {
            "src": "resources/base/media/favorite.svg",
            "description": "心动歌单爱心图标",
            "sceneTags": ["favorite", "heart"],
        },
        {
            "src": "resources/base/media/weather.svg",
            "description": "天气图标",
            "sceneTags": ["weather"],
        },
    ]


def _bluetooth_task(
    *,
    size: str = "2x2",
    query: str = "显示蓝牙耳机双耳电量",
    connected: Any = True,
    name: Any = "FreeBuds Pro",
    left: Any = 76,
    right: Any = 72,
    case: Any = 64,
    actions: list[EventAction] | None = None,
    include_phone: bool = False,
) -> TaskSpec:
    provider: dict[str, Any] = {
        "isConnected": _field(connected, "boolean"),
        "earphoneName": _field(name, "string"),
        "updatedAt": _field("2026-08-12 09:30", "string"),
    }
    for field_name, value in (
        ("leftBatteryLevel", left),
        ("rightBatteryLevel", right),
        ("batteryLevel", case),
    ):
        if value is not _MISSING:
            provider[field_name] = _field(value, "number")
    schema: dict[str, Any] = {"GetEarphoneInfo": provider}
    if include_phone:
        schema["GetPhoneBatteryInfo"] = {
            "batterySOC": _field(58, "number"),
            "batterySOCText": _field("58%", "string"),
            "batteryCapacityLevelDesc": _field("电量正常", "string"),
            "chargingStatusDesc": _field("未充电", "string"),
        }
    return TaskSpec(
        userQuery=query,
        size=size,
        eventCandidates=actions or [],
        dataModelSchema=schema,
        assetCandidates=_assets(),
    )


def _compile(
    task_spec: TaskSpec,
    source: str,
    component_ids: tuple[str, ...] = ("BluetoothDeviceOverview",),
):
    capability_ids = {"GetEarphoneInfo"}
    if "BatteryOverview" in component_ids:
        capability_ids.add("GetPhoneBatteryInfo")
    projected, card_spec, registry = prepare_provider_scope_projection(
        task_spec,
        capability_ids,
        component_ids,
    )
    card_spec.update(
        {
            "title": "设备电量",
            "description": "设备连接与电量概览",
        }
    )
    projection = build_ux_mixed_prompt(
        task_spec=projected,
        card_spec=card_spec,
        scope=AdvancedScopeBrief(
            themeId="audio-product-neutral-violet",
            advancedComponentIds=component_ids,
        ),
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


def _overview_call(role: str = "hero") -> str:
    return (
        'BluetoothDeviceOverview({"variant":"earbuds","role":"'
        + role
        + '","sourceIcon":"resources/base/media/earphone-source.svg",'
        '"leftEarIcon":"resources/base/media/left-ear.svg",'
        '"rightEarIcon":"resources/base/media/right-ear.svg"})'
    )


def test_schema_extraction_keeps_only_name_connection_and_three_batteries():
    facts = extract_bluetooth_device_overview_facts(_bluetooth_task().dataModelSchema)

    assert facts is not None
    assert facts.is_connected is True
    assert facts.earphone_name == "FreeBuds Pro"
    assert (
        facts.left_battery_level,
        facts.right_battery_level,
        facts.case_battery_level,
    ) == (76, 72, 64)
    assert "updated_at" not in facts.__dataclass_fields__


@pytest.mark.parametrize(
    ("query", "left", "right", "case"),
    [
        ("显示蓝牙耳机左耳电量", _MISSING, 72, 64),
        ("显示蓝牙耳机右耳电量", 76, _MISSING, 64),
        ("显示蓝牙耳机双耳电量", 76, _MISSING, 64),
        ("显示蓝牙耳机充电盒电量", 76, 72, _MISSING),
    ],
)
def test_explicitly_requested_part_must_exist(
    query: str,
    left: Any,
    right: Any,
    case: Any,
):
    task = _bluetooth_task(query=query, left=left, right=right, case=case)

    assert not bluetooth_device_overview_is_eligible(task, {"GetEarphoneInfo"})


@pytest.mark.parametrize(
    "query",
    [
        "显示天气",
        "显示今日日程",
        "显示睡眠",
        "显示应用使用时长",
        "显示蓝牙音箱电量",
        "显示蓝牙手表连接状态",
        "用蓝牙耳机播放暂停和下一首",
        "显示蓝牙耳机当前曲目和播放进度",
    ],
)
def test_unrelated_non_earphone_and_fake_transport_requests_are_rejected(query: str):
    task = _bluetooth_task(query=query)

    assert bluetooth_device_overview_variants(task, {"GetEarphoneInfo"}) == ()


@pytest.mark.parametrize("battery", [0, 100])
def test_zero_and_full_battery_are_valid(battery: int):
    task = _bluetooth_task(
        query="显示蓝牙耳机电量",
        left=battery,
        right=_MISSING,
        case=_MISSING,
    )

    assert bluetooth_device_overview_variants(task, {"GetEarphoneInfo"}) == ("earbuds",)


@pytest.mark.parametrize("battery", [-1, 101, True, "76", float("nan")])
def test_out_of_range_or_wrong_typed_only_battery_is_rejected(battery: Any):
    task = _bluetooth_task(left=battery, right=_MISSING, case=_MISSING)

    assert extract_bluetooth_device_overview_facts(task.dataModelSchema) is None


def test_first_layer_exposes_only_earbuds_and_revalidates_selection():
    task = _bluetooth_task()
    messages = build_advanced_scope_prompt(
        task,
        extract_data_shape(task),
        get_cardplan_registry(),
        available_capability_ids=("GetEarphoneInfo",),
    )
    payload = json.loads(messages[1]["content"])
    candidate = next(
        item for item in payload["advancedComponents"] if item["id"] == "BluetoothDeviceOverview"
    )

    assert candidate["variants"] == ["earbuds"]
    assert "非耳机设备请求不得选择" in messages[0]["content"]
    capability = get_cardplan_registry().require_ux_business_component("BluetoothDeviceOverview")
    assert capability.implementation == "template"
    assert capability.local_template_ids == ("BluetoothDeviceOverview@1",)

    invalid = _bluetooth_task(query="显示天气")
    with pytest.raises(ValueError, match="outside trusted candidates"):
        validate_advanced_scope(
            AdvancedScopeBrief(
                themeId="audio-product-neutral-violet",
                advancedComponentIds=("BluetoothDeviceOverview",),
            ),
            invalid,
            extract_data_shape(invalid),
            get_cardplan_registry(),
            ("GetEarphoneInfo",),
        )


def test_empty_data_bypass_is_batch_only_and_does_not_make_body_compilable(
    monkeypatch: pytest.MonkeyPatch,
):
    settings = get_settings()
    empty = _bluetooth_task().model_copy(update={"dataModelSchema": {"GetEarphoneInfo": {}}})
    with pytest.raises(ValueError, match="no provider-backed"):
        build_advanced_scope_prompt(
            empty,
            extract_data_shape(empty),
            get_cardplan_registry(),
            available_capability_ids=("GetEarphoneInfo",),
        )

    monkeypatch.setattr(settings, "enable_widget_batch_recording", True)
    monkeypatch.setattr(
        settings,
        "enable_advanced_component_data_admission_bypass_for_batch",
        True,
    )
    monkeypatch.setattr(
        content_selectors,
        "get_settings",
        lambda: settings,
    )
    with advanced_component_batch_data_admission(True):
        messages = build_advanced_scope_prompt(
            empty,
            extract_data_shape(empty),
            get_cardplan_registry(),
            available_capability_ids=("GetEarphoneInfo",),
        )
    payload = json.loads(messages[1]["content"])
    assert payload["temporaryDataAdmissionBypass"] is True
    assert any(item["id"] == "BluetoothDeviceOverview" for item in payload["advancedComponents"])

    with advanced_component_batch_data_admission(True):
        with pytest.raises(
            ValueError,
            match="no renderable provider facts|no compatible trusted earphone facts",
        ):
            _compile(empty, f"SingleFocusLayout({_overview_call()});")


def test_single_2x2_direct_layout_has_external_percent_and_no_fake_labels():
    compiled, projection, _projected = _compile(
        _bluetooth_task(),
        f"SingleFocusLayout({_overview_call()});",
    )
    output = compiled.effective_output

    assert projection.contract.required_template_groups == ()
    assert compiled.stats.template_used_ids == ()
    assert "BluetoothDeviceOverview" not in output
    assert "Template" not in output
    assert 'Text("FreeBuds Pro"' in output
    assert '"fontSize":12' in output
    assert '"width":20,"height":20' in output
    assert output.count('"type":"ring"') == 2
    assert output.count('"width":40,"height":40') >= 4
    assert output.count('"layoutWeight":1') >= 2
    assert output.count('"width":18,"height":18') == 2
    assert 'Text("76%"' in output and 'Text("72%"' in output
    assert "左耳" not in output and "右耳" not in output
    assert "充电盒" not in output
    assert "PillAction" not in output and "onClick" not in output


def test_disconnected_single_device_shows_status_without_stale_battery_rings():
    task = _bluetooth_task(connected=False)
    compiled, _projection, _projected = _compile(
        task,
        f"SingleFocusLayout({_overview_call()});",
    )

    assert "FreeBuds Pro" in compiled.effective_output
    assert "未连接" in compiled.effective_output
    assert '"type":"ring"' not in compiled.effective_output
    assert "76%" not in compiled.effective_output


def test_single_2x4_conditionally_renders_missing_ear_case_and_two_real_actions():
    task = _bluetooth_task(
        size="2x4",
        query="显示蓝牙耳机电量，并打开每日推荐和心动歌单",
        right=_MISSING,
        actions=[
            _music_action("event.open.music.daily"),
            _music_action("event.open.music.favorite"),
        ],
    )
    source = (
        'ActionMatrixLayout({"primaryActionIndex":0},'
        + _overview_call()
        + ',ActionTile({"actionId":"event.open.music.daily",'
        '"icon":"resources/base/media/music.svg"}),'
        'ActionTile({"actionId":"event.open.music.favorite",'
        '"icon":"resources/base/media/favorite.svg"}));'
    )
    compiled, projection, _projected = _compile(task, source)
    output = compiled.effective_output

    assert projection.contract.content_action_ids == (
        "event.open.music.daily",
        "event.open.music.favorite",
    )
    assert projection.contract.allowed_layout_component_ids == ("ActionMatrixLayout",)
    assert output.count('"type":"ring"') == 1
    assert 'Text("76%"' in output and 'Text("72%"' not in output
    assert 'Text("充电盒 64%"' in output
    assert output.count('"call":"clickToIntent"') == 2
    assert "播放" not in output and "暂停" not in output and "下一首" not in output


def test_music_entry_is_hidden_without_real_event_and_unapproved_action_fails():
    task = _bluetooth_task(query="显示蓝牙耳机并一键播放每日推荐")
    compiled, projection, _projected = _compile(
        task,
        f"SingleFocusLayout({_overview_call()});",
    )

    assert approved_bluetooth_music_action_ids(task) == ()
    assert projection.contract.content_action_ids == ()
    assert "onClick" not in compiled.effective_output
    with pytest.raises(
        TerseDslNested2ConversionError,
        match="approved Layout|not approved",
    ):
        _compile(
            task,
            "HeroActionLayout("
            + _overview_call()
            + ',PillAction({"actionId":"event.open.music.daily",'
            '"icon":"resources/base/media/music.svg"}));',
        )


def test_2x2_real_music_entry_uses_pill_and_semantic_icon():
    task = _bluetooth_task(
        query="显示蓝牙耳机电量",
        actions=[_music_action("event.open.music.daily")],
    )
    source = (
        "HeroActionLayout(" + _overview_call() + ',PillAction({"actionId":"event.open.music.daily",'
        '"icon":"resources/base/media/music.svg"}));'
    )
    compiled, projection, _projected = _compile(task, source)

    assert projection.contract.allowed_layout_component_ids == ("HeroActionLayout",)
    assert "每日推荐" in compiled.effective_output
    assert '"call":"clickToIntent"' in compiled.effective_output

    with pytest.raises(TerseDslNested2ConversionError, match="does not match"):
        _compile(
            task,
            "HeroActionLayout("
            + _overview_call()
            + ',PillAction({"actionId":"event.open.music.daily",'
            '"icon":"resources/base/media/weather.svg"}));',
        )


@pytest.mark.parametrize(
    ("size", "layout", "ear_ring_size"),
    [
        ("2x2", "PeerPairLayout", 32),
        ("2x4", "HeroSupportLayout", 40),
    ],
)
def test_phone_and_earphone_layout_has_one_title_and_clear_ring_hierarchy(
    size: str,
    layout: str,
    ear_ring_size: int,
):
    task = _bluetooth_task(
        size=size,
        query="显示手机和蓝牙耳机设备电量",
        include_phone=True,
        actions=[_music_action("event.open.music.daily")],
    )
    source = (
        layout + '(BatteryOverview({"variant":"normal","role":"hero",'
        '"batteryIcon":"resources/base/media/phone.svg"}),' + _overview_call("support") + ");"
    )
    compiled, projection, _projected = _compile(
        task,
        source,
        ("BatteryOverview", "BluetoothDeviceOverview"),
    )
    output = compiled.effective_output

    assert projection.contract.content_action_ids == ()
    assert output.count('Text("设备电量"') == 1
    assert '"width":56,"height":56' in output
    assert output.count('"type":"ring"') == 3
    assert output.count(f'"width":{ear_ring_size},"height":{ear_ring_size}') >= 4
    assert "onClick" not in output
    if size == "2x4":
        assert "充电盒 64%" in output


def test_phone_and_earphone_reject_actions_wrong_order_and_unrelated_third_business():
    task = _bluetooth_task(
        query="显示手机和蓝牙耳机设备电量",
        include_phone=True,
    )
    scope = AdvancedScopeBrief(
        themeId="audio-product-neutral-violet",
        advancedComponentIds=("BatteryOverview", "BluetoothDeviceOverview"),
    )
    assert resolve_scope_layout_ids(scope, task, get_cardplan_registry()) == ("PeerPairLayout",)

    with pytest.raises(TerseDslNested2ConversionError, match="hero first"):
        _compile(
            task,
            "PeerPairLayout("
            + _overview_call("support")
            + ',BatteryOverview({"variant":"normal","role":"hero"}));',
            ("BatteryOverview", "BluetoothDeviceOverview"),
        )

    unsupported = AdvancedScopeBrief(
        themeId="meeting-paper-neutral",
        advancedComponentIds=(
            "WeatherOverview",
            "BatteryOverview",
            "BluetoothDeviceOverview",
        ),
    )
    assert resolve_scope_layout_ids(unsupported, task, get_cardplan_registry()) == ()


def test_business_icon_source_must_be_model_selected_and_semantically_legal():
    task = _bluetooth_task()

    with pytest.raises(TerseDslNested2ConversionError, match="does not match"):
        _compile(
            task,
            "SingleFocusLayout(BluetoothDeviceOverview("
            '{"variant":"earbuds","role":"hero",'
            '"leftEarIcon":"resources/base/media/weather.svg"}));',
        )
    with pytest.raises(
        TerseDslNested2ConversionError,
        match="not an approved TaskSpec asset",
    ):
        _compile(
            task,
            "SingleFocusLayout(BluetoothDeviceOverview("
            '{"variant":"earbuds","role":"hero",'
            '"leftEarIcon":"resources/base/media/hard-coded.svg"}));',
        )


def test_provider_template_rejects_wrong_connection_and_data_shape_variants():
    with pytest.raises(TerseDslNested2ConversionError, match="connection state"):
        _compile(
            _bluetooth_task(),
            'SingleFocusLayout(Template("BluetoothDeviceOverview@1","disconnected",{}));',
        )

    with pytest.raises(TerseDslNested2ConversionError, match="trusted data shape"):
        _compile(
            _bluetooth_task(),
            'SingleFocusLayout(Template("BluetoothDeviceOverview@1","earbudPair",{}));',
        )
