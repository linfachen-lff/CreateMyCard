from __future__ import annotations

import json
import shutil
from copy import deepcopy
from pathlib import Path
from typing import Literal

import pytest

from models.generation import TaskSpec
from overview_test_support import prepare_provider_scope_projection
from services.advanced_component_pipeline.models import (
    UX_DIRECT_BUSINESS_COMPONENT_IDS,
    AdvancedScopeBrief,
)
from services.advanced_component_pipeline.ux_mixed_prompt import build_ux_mixed_prompt
from services.cardplan_template.compiler import compile_ux_layout_card
from services.cardplan_template.models import HybridBodyContract, HybridLimits
from services.cardplan_template.prompt import selection_candidates
from services.cardplan_template.provider_bundle import (
    compile_card_template,
    load_provider_bundle,
    load_provider_templates,
)
from services.cardplan_template.registry import CardPlanRegistry
from services.compact_dsl_a2ui_converter import (
    convert_a2ui_to_compact_dsl,
    convert_compact_dsl_to_a2ui,
)
from services.protocol_registry import TERSE_DSL_NESTED2_PROFILE_ID, A2UIProtocolRegistry
from services.terse_dsl_nested2_converter import TerseDslNested2ConversionError

SERVICE_ROOT = Path(__file__).resolve().parents[1]
WEATHER_BUNDLE = SERVICE_ROOT / "cloud/data/cardplan_template/source/providers/weather-cli"
HEALTH_BUNDLE = SERVICE_ROOT / "cloud/data/cardplan_template/source/providers/health-sport-cli"
PROVIDERS_ROOT = SERVICE_ROOT / "cloud/data/cardplan_template/source/providers"
FORMAL_CAPABILITY_SCHEMA = (
    SERVICE_ROOT / "cloud/data/capabilities/app-11.7.5.205_rom-6.0/data_capabilities.json"
)
WEATHER_TEMPLATE_ID = "WeatherOverview@1"
HEART_RATE_TEMPLATE_ID = "HeartRateOverview@1"


def _field(value: object, data_type: str) -> dict[str, object]:
    return {"type": data_type, "sampleValue": value}


def _task_schema_from_json_schema(schema: dict[str, object]) -> object:
    data_type = schema.get("type")
    if data_type == "object":
        properties = schema.get("properties", {})
        assert isinstance(properties, dict)
        return {
            key: _task_schema_from_json_schema(value)
            for key, value in properties.items()
            if isinstance(value, dict)
        }
    if data_type == "array":
        items = schema.get("items")
        assert isinstance(items, dict)
        return [_task_schema_from_json_schema(items)]
    defaults: dict[object, object] = {
        "string": "示例",
        "integer": 1,
        "number": 1.0,
        "boolean": True,
        "null": None,
    }
    return _field(schema.get("sampleValue", defaults[data_type]), str(data_type))


def _provider_output_schemas() -> dict[str, dict[str, object]]:
    payload = json.loads(FORMAL_CAPABILITY_SCHEMA.read_text(encoding="utf-8"))
    schemas = {item["id"]: item["outputSchema"] for item in payload}
    local_path = PROVIDERS_ROOT / "system-memory-cli/schemas/get-system-mem-info.schema.json"
    schemas["GetSystemMemInfo"] = json.loads(local_path.read_text(encoding="utf-8"))
    return schemas


def _weather_task_spec(size: Literal["2x2", "2x4"] = "2x2") -> TaskSpec:
    return TaskSpec(
        userQuery="查看青浦天气",
        size=size,
        dataModelSchema={
            "data": {
                "weatherPoc": {
                    "location": {"districtName": _field("青浦区", "string")},
                    "current": {
                        "temperatureText": _field("29°C", "string"),
                        "condition": _field("多云", "string"),
                        "airQuality": _field("良", "string"),
                    },
                    "daily": [{"temperatureRangeText": _field("25° / 32°", "string")}],
                }
            }
        },
    )


def _weather_contract() -> HybridBodyContract:
    weather_icon = "resources/base/media/weather.svg"
    return HybridBodyContract(
        theme_profile_id="family-weather-care-blue",
        allowed_components=(
            "Text",
            "Image",
            "Divider",
            "Progress",
            "Button",
            "Checkbox",
            "Row",
            "Column",
            "List",
            "Stack",
            "SingleFocusLayout",
        ),
        allowed_design_tokens=("title", "compact-title", "body", "subtitle"),
        allowed_layout_tokens=("compact", "between"),
        allowed_template_ids=(WEATHER_TEMPLATE_ID,),
        allowed_asset_sources=(weather_icon,),
        asset_semantic_tags_by_source={weather_icon: ("weather", "condition", "rain")},
        trusted_literals=(),
        trusted_numbers=(),
        required_literals=(),
        protected_literals=(),
        allowed_layout_component_ids=("SingleFocusLayout",),
        limits=HybridLimits(
            max_raw_components=8,
            max_expanded_components=48,
            max_nesting_depth=10,
            vertical_budget_vp=136,
        ),
    )


def _weather_card_spec(write_result_to: str = "/data/weatherPoc") -> dict[str, object]:
    return {
        "title": "青浦天气",
        "description": "查看当前天气",
        "suggestSize": "2x2",
        "dataBindings": [
            {
                "capabilityId": "ViewWeather",
                "arguments": {},
                "writeResultTo": write_result_to,
            }
        ],
    }


def _compile_weather_poc(
    *,
    variant: str = "hero",
    size: Literal["2x2", "2x4"] = "2x2",
    write_result_to: str = "/data/weatherPoc",
    params: dict[str, object] | None = None,
):
    card_spec = _weather_card_spec(write_result_to)
    card_spec["suggestSize"] = size
    return compile_ux_layout_card(
        f'SingleFocusLayout(Template("{WEATHER_TEMPLATE_ID}", "{variant}", '
        f"{json.dumps(params or {})}));",
        task_spec=_weather_task_spec(size),
        contract=_weather_contract(),
        protocol_profile=A2UIProtocolRegistry.read_design_protocol_profile(
            TERSE_DSL_NESTED2_PROFILE_ID
        ),
        registry=CardPlanRegistry(),
        card_spec=card_spec,
        enable_data_bindings=True,
    )


def _compile_weather_python(size: Literal["2x2", "2x4"]):
    icon = "resources/base/media/weather.svg"
    contract = _weather_contract().model_copy(
        update={
            "allowed_components": (*_weather_contract().allowed_components, "WeatherOverview"),
            "allowed_template_ids": (),
            "allowed_business_component_ids": ("WeatherOverview",),
            "required_business_component_ids": ("WeatherOverview",),
        }
    )
    return compile_ux_layout_card(
        'SingleFocusLayout(WeatherOverview({"variant":"current","role":"hero",'
        f'"conditionIcon":"{icon}"}}));',
        task_spec=_weather_task_spec(size),
        contract=contract,
        protocol_profile=A2UIProtocolRegistry.read_design_protocol_profile(
            TERSE_DSL_NESTED2_PROFILE_ID
        ),
        registry=CardPlanRegistry(),
        enable_data_bindings=True,
    )


def _heart_rate_task_spec(
    size: Literal["2x2", "2x4"] = "2x2",
    *,
    updated_at: bool = True,
) -> TaskSpec:
    health = {"exerciseHeartRateAvg": _field(126, "integer")}
    if updated_at:
        health["updatedAt"] = _field("今天 18:20", "string")
    return TaskSpec(
        userQuery="显示运动平均心率",
        size=size,
        dataModelSchema={"data": {"healthPoc": health}},
        assetCandidates=[
            {
                "id": "asset.heart",
                "src": "resources/base/media/heart.svg",
                "description": "心率图标",
                "sceneTags": ["heart", "heart-rate", "pulse"],
            }
        ],
    )


def _heart_rate_card_spec() -> dict[str, object]:
    return {
        "title": "运动平均心率",
        "description": "显示运动平均心率",
        "suggestSize": "2x2",
        "dataBindings": [
            {
                "capabilityId": "GetHealthAndSportSummary",
                "arguments": {},
                "writeResultTo": "/data/healthPoc",
            }
        ],
    }


def _heart_rate_contract(*, provider_template: bool) -> HybridBodyContract:
    heart_icon = "resources/base/media/heart.svg"
    allowed_components = (
        "Text",
        "Image",
        "Divider",
        "Progress",
        "Button",
        "Checkbox",
        "Row",
        "Column",
        "List",
        "Stack",
        "SingleFocusLayout",
    )
    return HybridBodyContract(
        theme_profile_id="meeting-paper-neutral",
        allowed_components=(
            allowed_components if provider_template else (*allowed_components, "HeartRateOverview")
        ),
        allowed_design_tokens=("title", "compact-title", "body", "subtitle"),
        allowed_layout_tokens=("compact", "between"),
        allowed_template_ids=(HEART_RATE_TEMPLATE_ID,) if provider_template else (),
        required_template_groups=(((HEART_RATE_TEMPLATE_ID,),) if provider_template else ()),
        allowed_asset_sources=(heart_icon,),
        asset_semantic_tags_by_source={
            heart_icon: ("heart", "heart-rate", "pulse"),
        },
        trusted_literals=(),
        trusted_numbers=(),
        required_literals=(),
        protected_literals=(),
        allowed_layout_component_ids=("SingleFocusLayout",),
        allowed_business_component_ids=() if provider_template else ("HeartRateOverview",),
        required_business_component_ids=() if provider_template else ("HeartRateOverview",),
        limits=HybridLimits(
            max_raw_components=8,
            max_expanded_components=48,
            max_nesting_depth=10,
            vertical_budget_vp=136,
        ),
    )


def _compile_heart_rate_provider(size: Literal["2x2", "2x4"]):
    card_spec = _heart_rate_card_spec()
    card_spec["suggestSize"] = size
    return compile_ux_layout_card(
        'SingleFocusLayout(Template("HeartRateOverview@1", "heroUpdatedIcon", '
        '{"sourceIcon":"resources/base/media/heart.svg"}));',
        task_spec=_heart_rate_task_spec(size),
        contract=_heart_rate_contract(provider_template=True),
        protocol_profile=A2UIProtocolRegistry.read_design_protocol_profile(
            TERSE_DSL_NESTED2_PROFILE_ID
        ),
        registry=CardPlanRegistry(),
        card_spec=card_spec,
        enable_data_bindings=True,
    )


def _compile_heart_rate_python(size: Literal["2x2", "2x4"]):
    return compile_ux_layout_card(
        'SingleFocusLayout(HeartRateOverview({"variant":"average","role":"hero",'
        '"sourceIcon":"resources/base/media/heart.svg"}));',
        task_spec=_heart_rate_task_spec(size),
        contract=_heart_rate_contract(provider_template=False),
        protocol_profile=A2UIProtocolRegistry.read_design_protocol_profile(
            TERSE_DSL_NESTED2_PROFILE_ID
        ),
        registry=CardPlanRegistry(),
        enable_data_bindings=True,
    )


def test_weather_provider_bundle_loads_and_compiles_all_variants():
    bundle = load_provider_bundle(WEATHER_BUNDLE)
    manifest = json.loads((WEATHER_BUNDLE / "provider.json").read_text(encoding="utf-8"))

    assert bundle.manifest.provider_id == "com.huawei.weather.cli"
    assert set(manifest["capabilities"][0]) == {
        "capabilityId",
        "dataSchema",
        "templates",
    }
    assert bundle.templates[0].wire_id == WEATHER_TEMPLATE_ID
    assert [variant.size for variant in bundle.templates[0].variants] == [
        "compact",
        "compactIcon",
        "hero",
        "heroIcon",
    ]
    assert bundle.templates[0].source_format == "cardtpl/1"


def test_all_direct_business_components_have_provider_templates():
    definitions = load_provider_templates(PROVIDERS_ROOT)
    wire_ids = {definition.wire_id for definition in definitions}

    assert {f"{component_id}@1" for component_id in UX_DIRECT_BUSINESS_COMPONENT_IDS}.issubset(
        wire_ids
    )
    assert "WorkoutCountdown@1" in wire_ids


def test_provider_template_migration_routes_are_explicit():
    registry = CardPlanRegistry()
    migrated_component_ids = {
        "DateOverview",
        "ScheduleOverview",
        "BatteryOverview",
        "ResourceUsageOverview",
        "AppUsageOverview",
        "ActivityOverview",
        "WorkoutOverview",
        "SleepOverview",
        "BluetoothDeviceOverview",
    }

    for component_id in migrated_component_ids:
        capability = registry.require_ux_business_component(component_id)
        assert capability.implementation == "template"
        assert capability.local_template_ids

    for component_id, template_ids in {
        "WeatherOverview": ("WeatherOverview@1",),
        "HeartRateOverview": ("HeartRateOverview@1",),
    }.items():
        capability = registry.require_ux_business_component(component_id)
        assert capability.implementation == "template"
        assert capability.local_template_ids == template_ids


@pytest.mark.parametrize(
    ("component_id", "template_id", "variant", "capability_id", "theme_id"),
    [
        (
            "DateOverview",
            "DateOverview@1",
            "dateHero",
            "GetCalendarEvents",
            "meeting-paper-neutral",
        ),
        (
            "ScheduleOverview",
            "ScheduleOverview@1",
            "nextEvent",
            "GetCalendarEvents",
            "meeting-paper-neutral",
        ),
        (
            "BatteryOverview",
            "BatteryOverview@1",
            "normal",
            "GetPhoneBatteryInfo",
            "system-low-power-blue",
        ),
        (
            "ResourceUsageOverview",
            "ResourceUsageOverview@1",
            "memory",
            "GetSystemMemInfo",
            "device-clean-blue-teal",
        ),
        (
            "AppUsageOverview",
            "AppUsageOverview@1",
            "singleApp",
            "GetAppUsageDuration",
            "digital-wellbeing-neutral-dark",
        ),
        (
            "ActivityOverview",
            "ActivityOverview@1",
            "dailySummary",
            "GetHealthAndSportSummary",
            "race-sunrise-action",
        ),
        (
            "WorkoutOverview",
            "WorkoutOverview@1",
            "latest",
            "GetHealthAndSportSummary",
            "race-sunrise-action",
        ),
        (
            "WorkoutOverview",
            "WorkoutCountdown@1",
            "countdown",
            "GetCountdownDays",
            "race-sunrise-action",
        ),
        (
            "SleepOverview",
            "SleepOverview@1",
            "duration",
            "GetHealthAndSportSummary",
            "sleep-night-violet",
        ),
        (
            "BluetoothDeviceOverview",
            "BluetoothDeviceOverview@1",
            "earbudsFull",
            "GetEarphoneInfo",
            "audio-product-neutral-violet",
        ),
    ],
)
def test_provider_backed_ux_component_default_path_reaches_final_a2ui(
    component_id: str,
    template_id: str,
    variant: str,
    capability_id: str,
    theme_id: str,
):
    registry = CardPlanRegistry()
    output_schema = _provider_output_schemas()[capability_id]
    task_spec = TaskSpec(
        userQuery=registry.require_template(template_id).description,
        size="2x2",
        dataModelSchema={
            capability_id: _task_schema_from_json_schema(output_schema),
        },
    )
    projected, card_spec, registry = prepare_provider_scope_projection(
        task_spec,
        {capability_id},
        (component_id,),
        force_template=True,
    )
    projection = build_ux_mixed_prompt(
        task_spec=projected,
        card_spec=card_spec,
        scope=AdvancedScopeBrief(
            themeId=theme_id,
            advancedComponentIds=(component_id,),
        ),
        registry=registry,
    )
    compilation = compile_ux_layout_card(
        f'SingleFocusLayout(Template("{template_id}", "{variant}", {{}}));',
        task_spec=projected,
        contract=projection.contract,
        protocol_profile=A2UIProtocolRegistry.read_design_protocol_profile(
            TERSE_DSL_NESTED2_PROFILE_ID
        ),
        registry=registry,
        card_spec=card_spec,
        enable_data_bindings=True,
    )

    assert projection.contract.required_template_groups == ((template_id,),)
    assert compilation.stats.template_used_ids == (template_id,)
    assert "${data." in compilation.effective_output
    assert "Template" not in compilation.a2ui
    assert "_advancedComponent" not in compilation.a2ui


def test_provider_template_preserves_repeated_structural_text() -> None:
    component_id = "BluetoothDeviceOverview"
    capability_id = "GetEarphoneInfo"
    template_id = "BluetoothDeviceOverview@1"
    registry = CardPlanRegistry()
    task_spec = TaskSpec(
        userQuery="查看蓝牙耳机电量",
        size="2x2",
        dataModelSchema={
            capability_id: _task_schema_from_json_schema(_provider_output_schemas()[capability_id])
        },
    )
    projected, card_spec, registry = prepare_provider_scope_projection(
        task_spec,
        {capability_id},
        (component_id,),
        force_template=True,
    )
    projection = build_ux_mixed_prompt(
        task_spec=projected,
        card_spec=card_spec,
        scope=AdvancedScopeBrief(
            themeId="audio-product-neutral-violet",
            advancedComponentIds=(component_id,),
        ),
        registry=registry,
    )

    compilation = compile_ux_layout_card(
        f'SingleFocusLayout(Template("{template_id}", "earbudsFull", {{}}));',
        task_spec=projected,
        contract=projection.contract,
        protocol_profile=A2UIProtocolRegistry.read_design_protocol_profile(
            TERSE_DSL_NESTED2_PROFILE_ID
        ),
        registry=registry,
        card_spec=card_spec,
        enable_data_bindings=True,
    )
    messages = [json.loads(line) for line in compilation.a2ui.splitlines()]
    contents = [
        component.get("content")
        for component in messages[1]["updateComponents"]["components"]
        if component["component"] == "Text"
    ]

    assert sum(isinstance(content, str) and "+ '%'" in content for content in contents) == 2


def test_all_provider_capabilities_use_the_minimal_three_field_contract():
    manifests = sorted(PROVIDERS_ROOT.glob("*/provider.json"))

    assert manifests
    for manifest_path in manifests:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        for capability in manifest["capabilities"]:
            assert set(capability) == {"capabilityId", "dataSchema", "templates"}
            assert set(capability["dataSchema"]) == {"path", "version"}


def test_all_provider_template_variants_expand_to_final_a2ui():
    output_schemas = _provider_output_schemas()
    definitions = load_provider_templates(PROVIDERS_ROOT)

    for definition in definitions:
        capability_id = definition.capability_id
        assert capability_id is not None
        task_data = _task_schema_from_json_schema(output_schemas[capability_id])
        card_spec = {
            "title": definition.description,
            "description": definition.description,
            "suggestSize": "2x2",
            "dataBindings": [
                {
                    "capabilityId": capability_id,
                    "arguments": {},
                    "writeResultTo": "/data/providerPoc",
                }
            ],
        }
        for variant in definition.variants:
            size = variant.supported_card_sizes[0]
            card_spec["suggestSize"] = size
            variant_task_data = deepcopy(task_data)
            if definition.wire_id == "BatteryOverview@1":
                if variant.size.startswith("charging"):
                    variant_task_data["chargingStatusDesc"]["sampleValue"] = "正在充电"
                elif variant.size.startswith("low"):
                    variant_task_data["batterySOC"]["sampleValue"] = 10
                    variant_task_data["batterySOCText"]["sampleValue"] = "10%"
                    variant_task_data["batteryCapacityLevelDesc"]["sampleValue"] = "电量较低"
            if definition.wire_id == "BluetoothDeviceOverview@1":
                variant_task_data["isConnected"]["sampleValue"] = not variant.size.startswith(
                    "disconnected"
                )
            params = {
                name: "resources/base/media/weather.svg"
                for name in variant.parameters_schema.get("required", ())
                if name in definition.asset_parameter_semantic_tags
            }
            for name in variant.parameters_schema.get("required", ()):
                if name in params:
                    continue
                parameter_type = variant.parameters_schema["properties"][name]["type"]
                params[name] = {
                    "string": "示例",
                    "integer": 1,
                    "number": 1.0,
                    "boolean": True,
                }[parameter_type]
            allowed_assets = tuple(
                dict.fromkeys(
                    value
                    for name, value in params.items()
                    if name in definition.asset_parameter_semantic_tags
                )
            )
            asset_tags = {
                source: definition.asset_parameter_semantic_tags[name]
                for name, source in params.items()
                if name in definition.asset_parameter_semantic_tags
            }
            task_spec = TaskSpec(
                userQuery=definition.description,
                size=size,
                dataModelSchema={"data": {"providerPoc": variant_task_data}},
            )
            contract = HybridBodyContract(
                theme_profile_id=definition.compatible_theme_profile_ids[0],
                allowed_components=(
                    "Text",
                    "Image",
                    "Divider",
                    "Progress",
                    "Button",
                    "Checkbox",
                    "Row",
                    "Column",
                    "List",
                    "Stack",
                    "SingleFocusLayout",
                ),
                allowed_design_tokens=("title", "compact-title", "body", "subtitle"),
                allowed_layout_tokens=("compact", "between"),
                allowed_template_ids=(definition.wire_id,),
                allowed_asset_sources=allowed_assets,
                asset_semantic_tags_by_source=asset_tags,
                trusted_literals=tuple(
                    value
                    for name, value in params.items()
                    if isinstance(value, str)
                    and name not in definition.asset_parameter_semantic_tags
                ),
                trusted_numbers=tuple(
                    value
                    for value in params.values()
                    if isinstance(value, (int, float)) and not isinstance(value, bool)
                ),
                required_literals=(),
                protected_literals=(),
                allowed_layout_component_ids=("SingleFocusLayout",),
                limits=HybridLimits(
                    max_raw_components=8,
                    max_expanded_components=64,
                    max_nesting_depth=12,
                    vertical_budget_vp=160,
                ),
            )
            compilation = compile_ux_layout_card(
                f'SingleFocusLayout(Template("{definition.wire_id}", '
                f'"{variant.size}", {json.dumps(params)}));',
                task_spec=task_spec,
                contract=contract,
                protocol_profile=A2UIProtocolRegistry.read_design_protocol_profile(
                    TERSE_DSL_NESTED2_PROFILE_ID
                ),
                registry=CardPlanRegistry(),
                card_spec=card_spec,
                enable_data_bindings=True,
            )

            assert compilation.stats.template_used_ids == (definition.wire_id,)
            assert "Template(" not in compilation.effective_output
            assert "Template" not in compilation.a2ui
            compact_archive = convert_a2ui_to_compact_dsl(
                compilation.a2ui,
                size=size,
            )
            round_tripped_a2ui = convert_compact_dsl_to_a2ui(
                compact_archive,
                size=size,
                protocol_profile=A2UIProtocolRegistry.read_design_protocol_profile(
                    "design-compact-dsl"
                ),
            )
            assert [json.loads(line) for line in round_tripped_a2ui.splitlines()] == [
                json.loads(line) for line in compilation.a2ui.splitlines()
            ]


def test_weather_provider_uses_upstream_data_schema_even_when_local_file_is_invalid(
    tmp_path: Path,
):
    copied = tmp_path / "weather-cli"
    shutil.copytree(WEATHER_BUNDLE, copied)
    local_schema = copied / "schemas/view-weather.output.schema.json"
    local_schema.write_text("{}", encoding="utf-8")

    bundle = load_provider_bundle(copied)

    assert bundle.templates[0].wire_id == WEATHER_TEMPLATE_ID


def test_provider_data_schema_falls_back_to_bundle_local_path(tmp_path: Path):
    copied = tmp_path / "weather-cli"
    shutil.copytree(WEATHER_BUNDLE, copied)
    manifest_path = copied / "provider.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest["capabilities"][0]["dataSchema"] = {
        "path": "schemas/view-weather.output.schema.json",
        "version": "weather-local/1",
    }
    manifest_path.write_text(json.dumps(manifest, ensure_ascii=False), encoding="utf-8")

    bundle = load_provider_bundle(copied)

    assert bundle.templates[0].wire_id == WEATHER_TEMPLATE_ID


def test_provider_upstream_data_schema_version_must_match_path(tmp_path: Path):
    copied = tmp_path / "weather-cli"
    shutil.copytree(WEATHER_BUNDLE, copied)
    manifest_path = copied / "provider.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest["capabilities"][0]["dataSchema"]["version"] = "unknown-version"
    manifest_path.write_text(json.dumps(manifest, ensure_ascii=False), encoding="utf-8")

    with pytest.raises(ValueError, match="version does not match"):
        load_provider_bundle(copied)


def test_provider_template_candidates_require_matching_card_and_task_bindings():
    registry = CardPlanRegistry()
    task_spec = _weather_task_spec()
    admitted = selection_candidates(task_spec, registry, _weather_card_spec())
    admitted_ids = {item["id"] for item in admitted["localTemplates"]}
    assert WEATHER_TEMPLATE_ID in admitted_ids

    missing_card_binding = selection_candidates(task_spec, registry)
    missing_card_binding_ids = {item["id"] for item in missing_card_binding["localTemplates"]}
    assert WEATHER_TEMPLATE_ID not in missing_card_binding_ids

    incomplete_task_spec = task_spec.model_copy(
        update={
            "dataModelSchema": {
                "data": {"weatherPoc": {"location": {"districtName": _field("青浦区", "string")}}}
            }
        }
    )
    incomplete = selection_candidates(
        incomplete_task_spec,
        registry,
        _weather_card_spec(),
    )
    incomplete_ids = {item["id"] for item in incomplete["localTemplates"]}
    assert WEATHER_TEMPLATE_ID not in incomplete_ids


def test_heart_rate_provider_variant_admission_is_binding_specific():
    expected_variants = {
        False: {"hero", "heroIcon", "support", "supportIcon"},
        True: {
            "heroUpdated",
            "heroUpdatedIcon",
            "supportUpdated",
            "supportUpdatedIcon",
        },
    }
    for has_updated_at, expected in expected_variants.items():
        candidates = selection_candidates(
            _heart_rate_task_spec(updated_at=has_updated_at),
            CardPlanRegistry(),
            _heart_rate_card_spec(),
        )
        heart_rate = next(
            item for item in candidates["localTemplates"] if item["id"] == HEART_RATE_TEMPLATE_ID
        )

        assert {item["size"] for item in heart_rate["variants"]} == expected


def test_heart_rate_variant_without_optional_binding_still_compiles():
    task_spec = _heart_rate_task_spec(updated_at=False)
    card_spec = _heart_rate_card_spec()
    compilation = compile_ux_layout_card(
        'SingleFocusLayout(Template("HeartRateOverview@1", "hero", {}));',
        task_spec=task_spec,
        contract=_heart_rate_contract(provider_template=True),
        protocol_profile=A2UIProtocolRegistry.read_design_protocol_profile(
            TERSE_DSL_NESTED2_PROFILE_ID
        ),
        registry=CardPlanRegistry(),
        card_spec=card_spec,
        enable_data_bindings=True,
    )

    assert compilation.stats.template_used_ids == (HEART_RATE_TEMPLATE_ID,)
    with pytest.raises(
        TerseDslNested2ConversionError,
        match="binding is not declared by TaskSpec",
    ):
        compile_ux_layout_card(
            'SingleFocusLayout(Template("HeartRateOverview@1", "heroUpdated", {}));',
            task_spec=task_spec,
            contract=_heart_rate_contract(provider_template=True),
            protocol_profile=A2UIProtocolRegistry.read_design_protocol_profile(
                TERSE_DSL_NESTED2_PROFILE_ID
            ),
            registry=CardPlanRegistry(),
            card_spec=card_spec,
            enable_data_bindings=True,
        )


@pytest.mark.parametrize(("variant", "size"), [("hero", "2x2"), ("compact", "2x4")])
def test_weather_provider_template_expands_bindings_to_final_a2ui(
    variant: str,
    size: Literal["2x2", "2x4"],
):
    compilation = _compile_weather_poc(variant=variant, size=size)

    assert compilation.stats.template_used_ids == (WEATHER_TEMPLATE_ID,)
    assert "Template(" not in compilation.effective_output
    assert "Template" not in compilation.a2ui
    binding_paths = {
        f"/data/weatherPoc/{suffix}"
        for suffix in (
            "location/districtName",
            "current/temperatureText",
            "current/condition",
            "current/airQuality",
            "daily/0/temperatureRangeText",
        )
    }

    messages = [json.loads(line) for line in compilation.a2ui.splitlines()]
    assert len(messages) == 3
    assert messages[-1]["updateDataModel"]["surfaceId"] == "surface_card"
    text_contents = {
        component["content"]
        for component in messages[1]["updateComponents"]["components"]
        if component["component"] == "Text"
    }
    direct_binding_paths = binding_paths - {
        "/data/weatherPoc/current/condition",
        "/data/weatherPoc/current/airQuality",
    }
    assert {f"{{{{ ${{{path}}} }}}}" for path in direct_binding_paths}.issubset(text_contents)
    assert (
        "{{ ${/data/weatherPoc/current/condition} + '｜' + "
        "${/data/weatherPoc/current/airQuality} }}"
    ) in text_contents
    assert not any(content == "｜" for content in text_contents)


@pytest.mark.parametrize("size", ["2x2", "2x4"])
def test_weather_provider_template_meets_python_shadow_gate(
    size: Literal["2x2", "2x4"],
):
    icon = "resources/base/media/weather.svg"
    provider = _compile_weather_poc(
        variant="heroIcon",
        size=size,
        params={"conditionIcon": icon},
    )
    python = _compile_weather_python(size)

    expected_paths = {
        "/data/weatherPoc/location/districtName",
        "/data/weatherPoc/current/temperatureText",
        "/data/weatherPoc/current/condition",
        "/data/weatherPoc/current/airQuality",
        "/data/weatherPoc/daily/0/temperatureRangeText",
    }
    direct_provider_paths = expected_paths - {
        "/data/weatherPoc/current/condition",
        "/data/weatherPoc/current/airQuality",
    }
    expected_direct_provider_contents = {f"{{{{ ${{{path}}} }}}}" for path in direct_provider_paths}
    expected_python_contents = {
        f"{{{{ ${{{path}}} }}}}"
        for path in expected_paths - {"/data/weatherPoc/current/temperatureText"}
    }
    provider_condition_expression = (
        "{{ ${/data/weatherPoc/current/condition} + '｜' + "
        "${/data/weatherPoc/current/airQuality} }}"
    )
    compilation_contents: list[set[object]] = []
    for compilation in (provider, python):
        messages = [json.loads(line) for line in compilation.a2ui.splitlines()]
        components = messages[1]["updateComponents"]["components"]
        contents = {
            component.get("content") for component in components if component["component"] == "Text"
        }
        compilation_contents.append(contents)
        assert any(component["component"] == "Image" for component in components)
        assert not any(component["component"] in {"Template", "Button"} for component in components)
        assert '"fontSize":38' in compilation.effective_output
        assert icon in compilation.effective_output

    assert expected_direct_provider_contents.issubset(compilation_contents[0])
    assert provider_condition_expression in compilation_contents[0]
    assert expected_python_contents.issubset(compilation_contents[1])
    temperature_binding = "{{ ${/data/weatherPoc/current/temperatureText} }}"
    assert temperature_binding not in compilation_contents[1]
    assert "29°" in compilation_contents[1]
    assert provider.stats.template_used_ids == (WEATHER_TEMPLATE_ID,)


@pytest.mark.parametrize("size", ["2x2", "2x4"])
def test_heart_rate_provider_template_meets_python_shadow_gate(
    size: Literal["2x2", "2x4"],
):
    provider = _compile_heart_rate_provider(size)
    python = _compile_heart_rate_python(size)

    structures: list[list[dict[str, object]]] = []
    contents: list[set[object]] = []
    for compilation in (provider, python):
        messages = [json.loads(line) for line in compilation.a2ui.splitlines()]
        components = messages[1]["updateComponents"]["components"]
        structures.append(
            [
                {key: value for key, value in component.items() if key != "content"}
                for component in components
            ]
        )
        contents.append(
            {
                component.get("content")
                for component in components
                if component["component"] == "Text"
            }
        )

    assert structures[0] == structures[1]
    assert "{{ ${/data/healthPoc/exerciseHeartRateAvg} }}" in contents[0]
    assert "126" in contents[1]
    assert provider.stats.template_used_ids == (HEART_RATE_TEMPLATE_ID,)
    assert python.stats.template_used_ids == ()


def test_provider_template_rejects_binding_root_not_declared_by_task_spec():
    with pytest.raises(
        TerseDslNested2ConversionError,
        match="binding is not declared by TaskSpec",
    ):
        _compile_weather_poc(write_result_to="/data/unrelated")


def test_provider_bundle_rejects_tampered_template_digest(tmp_path: Path):
    copied = tmp_path / "weather-cli"
    shutil.copytree(WEATHER_BUNDLE, copied)
    template = copied / "templates/weather-overview.cardtpl"
    template.write_text(template.read_text(encoding="utf-8") + "\n", encoding="utf-8")

    with pytest.raises(ValueError, match="digest mismatch"):
        load_provider_bundle(copied)


def test_cardtpl_rejects_undeclared_bind_reference():
    source = (WEATHER_BUNDLE / "templates/weather-overview.cardtpl").read_text(encoding="utf-8")
    source = source.replace('Bind("city")', 'Bind("undeclared")', 1)
    output_schema = json.loads(
        (WEATHER_BUNDLE / "schemas/view-weather.output.schema.json").read_text(encoding="utf-8")
    )

    with pytest.raises(ValueError, match="unknown Provider Template bindings"):
        compile_card_template(
            source,
            provider_id="com.huawei.weather.cli",
            expected_wire_id=WEATHER_TEMPLATE_ID,
            expected_capability_id="ViewWeather",
            output_schema=output_schema,
            bundle_digest="sha256:" + "0" * 64,
        )


def test_cardtpl_rejects_arbitrary_function_calls():
    source = (WEATHER_BUNDLE / "templates/weather-overview.cardtpl").read_text(encoding="utf-8")
    source = source.replace('Bind("city")', 'eval("city")', 1)
    output_schema = json.loads(
        (WEATHER_BUNDLE / "schemas/view-weather.output.schema.json").read_text(encoding="utf-8")
    )

    with pytest.raises(ValueError, match="unsupported Provider Template component: eval"):
        compile_card_template(
            source,
            provider_id="com.huawei.weather.cli",
            expected_wire_id=WEATHER_TEMPLATE_ID,
            expected_capability_id="ViewWeather",
            output_schema=output_schema,
            bundle_digest="sha256:" + "0" * 64,
        )


def test_cardtpl_rejects_property_access_in_template_string():
    source = (WEATHER_BUNDLE / "templates/weather-overview.cardtpl").read_text(encoding="utf-8")
    source = source.replace("${condition}", "${condition.value}", 1)
    output_schema = json.loads(
        (WEATHER_BUNDLE / "schemas/view-weather.output.schema.json").read_text(encoding="utf-8")
    )

    with pytest.raises(ValueError, match="invalid placeholder"):
        compile_card_template(
            source,
            provider_id="com.huawei.weather.cli",
            expected_wire_id=WEATHER_TEMPLATE_ID,
            expected_capability_id="ViewWeather",
            output_schema=output_schema,
            bundle_digest="sha256:" + "0" * 64,
        )


def test_cardtpl_optional_binding_must_be_guarded_and_is_recorded() -> None:
    source = """#Template("OptionalBinding@1", {
      capability: "ReadOptional",
      description: "optional binding",
      domainTags: ["test"],
      compatibleThemeProfileIds: ["meeting-paper-neutral"],
      allowedParentComponents: ["Column"],
      bindings: { value: { path: "/value", type: "string" } },
      params: {},
      limits: { maxNodes: 8, maxDepth: 4 }
    })
    #Variant("hero", { sizes: ["2x2"], roles: ["hero"], requires: [] })
    Column("compact",
      IfBind("value", Text(Bind("value"), "body")),
      IfMissingBind("value", Text("暂无", "body"))
    )
    #EndVariant
    #EndTemplate"""
    output_schema = {
        "type": "object",
        "properties": {"value": {"type": "string"}},
    }

    definition = compile_card_template(
        source,
        provider_id="com.huawei.test.cli",
        expected_wire_id="OptionalBinding@1",
        expected_capability_id="ReadOptional",
        output_schema=output_schema,
        bundle_digest="sha256:" + "0" * 64,
    )

    assert definition.variants[0].required_bindings == ()
    assert definition.variants[0].optional_bindings == ("value",)

    unguarded = source.replace(
        'IfBind("value", Text(Bind("value"), "body"))',
        'Text(Bind("value"), "body")',
    )
    with pytest.raises(ValueError, match="optional Bind must be nested"):
        compile_card_template(
            unguarded,
            provider_id="com.huawei.test.cli",
            expected_wire_id="OptionalBinding@1",
            expected_capability_id="ReadOptional",
            output_schema=output_schema,
            bundle_digest="sha256:" + "0" * 64,
        )

    unknown = source.replace('IfBind("value"', 'IfBind("unknown"', 1)
    with pytest.raises(ValueError, match="unknown Provider Template conditional binding"):
        compile_card_template(
            unknown,
            provider_id="com.huawei.test.cli",
            expected_wire_id="OptionalBinding@1",
            expected_capability_id="ReadOptional",
            output_schema=output_schema,
            bundle_digest="sha256:" + "0" * 64,
        )
