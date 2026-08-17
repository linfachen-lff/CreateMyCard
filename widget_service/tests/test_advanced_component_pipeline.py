# -*- coding: utf-8 -*-
# ruff: noqa: E402
"""高级组件两轮模型、回退和模板编译测试。"""

import json
import sys
from copy import deepcopy
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest

PROJECT_ROOT = Path(__file__).resolve().parents[1]
CLOUD_ROOT = PROJECT_ROOT / "cloud"
if str(CLOUD_ROOT) not in sys.path:
    sys.path.insert(0, str(CLOUD_ROOT))

import services.advanced_component_pipeline.pipeline as advanced_pipeline_module
from api.schemas import GenerateWidgetCardRequest
from config.config import get_settings
from core.errors import GenerationStatus
from custom.a2ui_model_client import A2UIModelClient
from models.artifact import ArtifactMeta, WidgetArtifact
from models.generation import CandidateDataBinding, EventAction, TaskSpec
from models.service import ArtifactSaveResult
from overview_test_support import (
    prepare_provider_scope_projection,
    provider_direct_shadow_projection,
)
from services.advanced_component_pipeline import AdvancedComponentPipeline
from services.advanced_component_pipeline.compiler import (
    build_standard_a2ui,
    build_terse_nested2,
)
from services.advanced_component_pipeline.component_registry import component_plugins, get_component
from services.advanced_component_pipeline.component_selector import select_component
from services.advanced_component_pipeline.components.status_ring_action.plugin import (
    Invocation as LowPowerInvocation,
)
from services.advanced_component_pipeline.content_selectors import (
    apply_content_selectors,
    project_content_component_facts,
)
from services.advanced_component_pipeline.data_shape import extract_data_shape
from services.advanced_component_pipeline.models import (
    ActionRef,
    AdvancedPipelineOutput,
    AdvancedScopeBrief,
    BindingRef,
    SelectionConstraints,
    UIBrief,
)
from services.advanced_component_pipeline.scope_planner import (
    TemplateRouteNotApplicable,
    build_advanced_scope_prompt,
    plan_advanced_scope_with_llm,
    plan_template_route_with_llm,
    resolve_scope_layout_ids,
    scope_template_ids,
)
from services.advanced_component_pipeline.ui_planner import build_ui_planner_prompt
from services.advanced_component_pipeline.ux_mixed_framer import (
    frame_ux_layout_children,
    frame_ux_layout_root_children,
)
from services.advanced_component_pipeline.ux_mixed_prompt import build_ux_mixed_prompt
from services.artifact_store import ArtifactStore
from services.cardplan_template.compiler import compile_ux_layout_card
from services.cardplan_template.parser import parse_hybrid_card, parse_ux_layout_card
from services.cardplan_template.registry import get_cardplan_registry
from services.generation_pipeline import (
    DslProcessorKind,
    GenerationRoutePolicy,
)
from services.protocol_registry import TERSE_DSL_NESTED2_PROFILE_ID, A2UIProtocolRegistry
from services.source_artifact_repository import SourceArtifactLoadResult
from services.terse_dsl_nested2_converter import (
    TerseDslNested2ConversionError,
    convert_terse_dsl_nested2_to_a2ui,
)
from services.validator import ArtifactValidator
from services.widget_generation_service import WidgetGenerationService


def _metric_task_spec(with_action: bool = True) -> TaskSpec:
    events = [EventAction(id="event.enable.power", call="clickToApi", args={})]
    return TaskSpec(
        userQuery="设备电量低于20%，开启省电模式",
        size="2x2",
        eventCandidates=events if with_action else [],
        dataModelSchema={
            "data": {
                "battery": {
                    "status": {
                        "type": "string",
                        "description": "低电量状态和省电建议",
                        "sampleValue": "电量低于20%，开启省电模式",
                    },
                    "batteryPercent": {
                        "type": "integer",
                        "description": "电池电量百分比",
                        "sampleValue": 18,
                    },
                }
            }
        },
        assetCandidates=[
            {
                "id": "asset.electricity",
                "src": "resources/base/media/battery.svg",
                "description": "电池图标",
            },
            {
                "id": "asset.save_power",
                "src": "resources/base/media/power.svg",
                "description": "省电图标",
            },
        ],
    )


def test_component_plugins_are_discovered_from_component_directories():
    plugins = component_plugins()

    assert {plugin.component_id for plugin in plugins} == {
        "dual-duration-action",
        "dual-ring-primary-action",
        "hero-countdown",
        "status-ring-action",
        "timeline-event-action",
        "upcoming-event-action",
        "usage-summary-action",
        "hero-metric-action",
        "hero-metric-icon-action",
    }
    assert all(plugin.invocation_model for plugin in plugins)
    assert all(callable(plugin.build_rows) for plugin in plugins)
    assert all(callable(plugin.map_offline) for plugin in plugins)
    assert all(callable(plugin.validate) for plugin in plugins)


def _seven_scene_task_spec() -> TaskSpec:
    def field(data_type, sample, description):
        return {"type": data_type, "description": description, "sampleValue": sample}

    return TaskSpec(
        userQuery="生成场景卡片",
        size="2x2",
        eventCandidates=[EventAction(id="event.scene.action", call="clickToApi", args={})],
        dataModelSchema={
            "data": {
                "scene": {
                    "prefectureName": field("string", "深圳", "城市名称"),
                    "temperatureText": field("string", "38°", "当前温度"),
                    "condition": field("string", "晴", "天气状态"),
                    "temperatureRangeText": field("string", "26°/16°", "最高最低温度范围"),
                    "eventTitle": field("string", "UI需求评审会", "赛事或会议标题"),
                    "remainingDays": field("integer", 32, "赛事剩余天数"),
                    "sleepHours": field("integer", 5, "睡眠小时数"),
                    "sleepMinutes": field("integer", 45, "睡眠分钟数"),
                    "appName": field("string", "抖音使用时长", "应用名称"),
                    "durationText": field("string", "3小时45分钟", "应用使用时长"),
                    "status": field("string", "电量低于20%，开启省电模式", "电池状态"),
                    "batteryPercent": field("integer", 18, "电池电量百分比"),
                    "startTime": field("string", "14:00", "会议开始时间"),
                    "endTime": field("string", "15:30", "会议结束时间"),
                    "date": field("string", "27日", "日期"),
                    "weekday": field("string", "星期一", "星期"),
                    "location": field("string", "深圳市龙岗区", "会议地点"),
                    "memoryUsedPercent": field("integer", 87, "内存占用百分比"),
                    "storageUsedPercent": field("integer", 72, "设备存储占用百分比"),
                }
            }
        },
        assetCandidates=[
            {
                "id": "asset.location",
                "src": "resources/base/media/location.svg",
                "description": "定位天气图标",
            },
            {
                "id": "asset.run",
                "src": "resources/base/media/run.svg",
                "description": "运动跑步图标",
            },
            {
                "id": "asset.alarm",
                "src": "resources/base/media/alarm.svg",
                "description": "闹钟图标",
            },
            {
                "id": "asset.tiktok",
                "src": "resources/base/media/tiktok.png",
                "description": "应用图标",
            },
            {
                "id": "asset.timing",
                "src": "resources/base/media/timing.svg",
                "description": "计时图标",
            },
            {
                "id": "asset.electricity",
                "src": "resources/base/media/battery.svg",
                "description": "电池图标",
            },
            {
                "id": "asset.save_power",
                "src": "resources/base/media/power.svg",
                "description": "省电图标",
            },
            {
                "id": "asset.meeting",
                "src": "resources/base/media/meeting.svg",
                "description": "会议图标",
            },
            {
                "id": "asset.memory",
                "src": "resources/base/media/memory.svg",
                "description": "内存图标",
            },
            {
                "id": "asset.storage",
                "src": "resources/base/media/storage.svg",
                "description": "设备存储图标",
            },
            {
                "id": "asset.rain",
                "src": "resources/base/media/rain.svg",
                "description": "降雨天气图标",
            },
            {
                "id": "asset.taxi",
                "src": "resources/base/media/taxi.svg",
                "description": "打车图标",
            },
        ],
    )


@pytest.mark.parametrize(
    (
        "purpose",
        "component_id",
        "layout",
        "domain",
        "scenario",
        "content",
        "action",
        "status",
        "temporality",
    ),
    [
        (
            "亲人关怀",
            "hero-metric-action",
            "hero-metric-action",
            "weather",
            "family-care",
            ["location", "temperature"],
            ["call-contact"],
            [],
            "now",
        ),
        (
            "赛事陪伴",
            "hero-countdown",
            "hero-countdown",
            "sports",
            "race-countdown",
            ["countdown"],
            ["open-event"],
            [],
            "upcoming",
        ),
        (
            "睡眠监测",
            "dual-duration-action",
            "dual-duration-action",
            "health",
            "sleep-summary",
            ["duration"],
            ["remind-sleep"],
            ["sleep-quality"],
            "historical",
        ),
        (
            "防沉迷",
            "usage-summary-action",
            "usage-summary-action",
            "digital-wellbeing",
            "usage-control",
            ["app-usage", "duration"],
            ["manage-usage"],
            [],
            "now",
        ),
        (
            "设备电量",
            "status-ring-action",
            "status-ring-action",
            "device",
            "low-power",
            ["battery-level", "percentage"],
            ["enable-power-saving"],
            ["low-power"],
            "now",
        ),
        (
            "专注模式",
            "upcoming-event-action",
            "upcoming-event-action",
            "schedule",
            "upcoming-event",
            ["event-title", "time-range"],
            ["enable-focus"],
            ["do-not-disturb"],
            "upcoming",
        ),
        (
            "当前会议",
            "timeline-event-action",
            "timeline-event-action",
            "schedule",
            "ongoing-event",
            ["event-title", "time-range"],
            ["join-meeting"],
            ["active"],
            "now",
        ),
        (
            "内存不足",
            "dual-ring-primary-action",
            "dual-ring-primary-action",
            "device",
            "memory-cleanup",
            ["memory-usage", "storage-usage", "percentage"],
            ["clean-memory"],
            ["warning"],
            "now",
        ),
        (
            "雨天打车回家",
            "hero-metric-icon-action",
            "hero-metric-icon-action",
            "weather",
            "bad-weather-commute",
            ["location", "temperature", "status"],
            ["hail-taxi"],
            ["warning"],
            "now",
        ),
    ],
)
def test_visual_scene_plugins_select_and_compile(
    purpose, component_id, layout, domain, scenario, content, action, status, temporality
):
    task_spec = _seven_scene_task_spec()
    data_shape = extract_data_shape(task_spec)
    brief = UIBrief(
        purpose=purpose,
        domain=domain,
        scenario=scenario,
        layoutArchetype=layout,
        contentSemantics=content,
        actionSemantics=action,
        statusSemantics=status,
        temporality=temporality,
        primaryInformation=[purpose],
        informationHierarchy=["主信息", "操作"],
        visualTone=purpose,
        contentPriorities=[purpose],
        reason="测试场景选择",
    )
    selection = select_component(
        data_shape,
        brief,
        SelectionConstraints(
            size="2x2",
            action_count=1,
            asset_count=len(task_spec.assetCandidates),
        ),
    )
    assert selection is not None
    assert selection.component_id == component_id

    plugin = get_component(component_id)
    invocation = plugin.map_offline(task_spec, data_shape)
    plugin.validate(invocation, task_spec)
    terse = build_terse_nested2(component_id, invocation, task_spec, "night-violet")
    a2ui = build_standard_a2ui(component_id, invocation, task_spec, "night-violet")
    converted_a2ui = convert_terse_dsl_nested2_to_a2ui(
        terse,
        size="2x2",
        protocol_profile={"version": "v0.9", "sizes": {"2x2": {"width": 160, "height": 160}}},
    )

    assert terse.startswith('Column("card"')
    assert len(a2ui.splitlines()) == 3
    assert len(converted_a2ui.splitlines()) == 3
    assert '"root":"root"' in a2ui
    artifact = WidgetArtifact(
        genui=a2ui,
        cardSpec={"title": purpose, "description": purpose, "suggestSize": "2x2"},
        taskSpec=task_spec.model_dump(mode="json"),
        effectiveCapabilities={"asset": task_spec.assetCandidates},
        meta=ArtifactMeta(
            protocolProfileId="a2ui-form-rom6.0-v1",
            capabilityRegistryVersion="app-11.7.5.205_rom-6.0",
            createdAt=1,
        ),
    )
    errors = ArtifactValidator().validate(
        artifact,
        {"id": "a2ui-form-rom6.0-v1"},
    )
    assert [error for error in errors if not error.startswith("EFFECTIVE_")] == []


def test_schedule_dnd_ui_brief_selects_upcoming_event_layout():
    task_spec = _seven_scene_task_spec()
    brief = UIBrief(
        purpose="以紧凑卡片形式展示未来日程概览，提示用户当前处于免打扰状态，并允许一键进入设置。",
        domain="schedule",
        scenario="upcoming-event",
        layoutArchetype="upcoming-event-action",
        statusSemantics=["do-not-disturb"],
        contentSemantics=["event-title", "time-range", "event-count"],
        actionSemantics=["open-dnd-settings"],
        primaryInformation=["今日及近期日程数量", "近期日程的时间与标题", "免打扰开启状态"],
        informationHierarchy=["免打扰状态", "近期日程", "设置入口"],
        density="compact",
        temporality="upcoming",
        interaction="one-primary-action",
        attention="normal",
        visualTone="简洁、高效，强调日程时间性与免打扰的静默感",
        contentPriorities=["免打扰状态", "日程时间准确性", "日程标题", "进入设置"],
        reason="2x2 卡片突出未来日程和免打扰设置。",
    )

    selection = select_component(
        extract_data_shape(task_spec),
        brief,
        SelectionConstraints(
            size="2x2",
            action_count=1,
            asset_count=len(task_spec.assetCandidates),
        ),
    )

    assert selection is not None
    assert selection.component_id == "upcoming-event-action"
    assert selection.confidence >= 0.75


def test_structural_weather_hero_selection_does_not_require_business_name_or_asset():
    task_spec = TaskSpec(
        userQuery="生成一张状态概览卡片",
        size="2x2",
        eventCandidates=[EventAction(id="event.open", call="clickToApi", args={})],
        dataModelSchema={
            "data": {
                "summary": {
                    "city": {"type": "string", "description": "地点", "sampleValue": "深圳"},
                    "temperatureText": {
                        "type": "string",
                        "description": "当前温度",
                        "sampleValue": "28°",
                    },
                    "condition": {
                        "type": "string",
                        "description": "当前状态",
                        "sampleValue": "晴",
                    },
                    "rangeText": {
                        "type": "string",
                        "description": "范围摘要",
                        "sampleValue": "26°/18°",
                    },
                }
            }
        },
        assetCandidates=[],
    )
    brief = UIBrief(
        purpose="突出一个主指标，并在底部展示摘要和快捷操作",
        domain="general",
        scenario="general",
        layoutArchetype="hero-metric-action",
        primaryInformation=["地点", "主指标", "状态"],
        informationHierarchy=["地点", "主指标", "摘要和操作"],
        visualTone="清晰简洁",
        contentPriorities=["主指标"],
        reason="使用单个大指标布局。",
    )

    selection = select_component(
        extract_data_shape(task_spec),
        brief,
        SelectionConstraints(size="2x2", action_count=1, asset_count=0),
    )

    assert selection is not None
    assert selection.component_id == "hero-metric-action"
    planner_payload = json.loads(
        build_ui_planner_prompt(task_spec, extract_data_shape(task_spec))[1]["content"]
    )
    candidates = {item["layoutArchetype"]: item for item in planner_payload["wholeCardCandidates"]}
    assert candidates["hero-metric-action"]["taskSpecCompatibility"]["score"] == 1.0
    assert candidates["hero-metric-icon-action"]["taskSpecCompatibility"]["score"] < 1.0
    plugin = get_component(selection.component_id)
    invocation = plugin.map_offline(task_spec, extract_data_shape(task_spec))
    assert invocation.location_icon is None
    plugin.validate(invocation, task_spec)
    assert "Image(" not in build_terse_nested2(
        selection.component_id, invocation, task_spec, "system-teal"
    )


def test_sleep_semantics_override_an_incorrect_llm_layout_archetype():
    task_spec = _seven_scene_task_spec()
    brief = UIBrief(
        purpose="展示睡眠状态和两个睡眠时长",
        domain="health",
        scenario="sleep-summary",
        layoutArchetype="status-ring-action",
        statusSemantics=["sleep-quality"],
        contentSemantics=["duration", "status", "metric"],
        actionSemantics=["remind-sleep", "open-details"],
        primaryInformation=["睡眠状态", "夜间时长", "深睡时长"],
        informationHierarchy=["睡眠状态", "两个时长", "操作"],
        temporality="historical",
        visualTone="平静",
        contentPriorities=["两个睡眠时长"],
        reason="两个时长需要并列展示。",
    )

    selection = select_component(
        extract_data_shape(task_spec),
        brief,
        SelectionConstraints(
            size="2x2",
            action_count=1,
            asset_count=len(task_spec.assetCandidates),
        ),
    )

    assert selection is not None
    assert selection.component_id == "dual-duration-action"
    assert selection.confidence >= 0.9


def test_countdown_template_supports_one_field_without_action():
    task_spec = TaskSpec(
        userQuery="做个运动会倒数日卡片",
        size="2x2",
        eventCandidates=[],
        dataModelSchema={
            "data": {
                "countdown": {
                    "countdownDays": {
                        "type": "integer",
                        "description": "距离目标日期的剩余天数",
                        "sampleValue": 35,
                    }
                }
            }
        },
        assetCandidates=[],
    )
    data_shape = extract_data_shape(task_spec)
    brief = UIBrief(
        purpose="运动会倒数日",
        domain="sports",
        scenario="race-countdown",
        layoutArchetype="hero-countdown",
        contentSemantics=["countdown"],
        actionSemantics=[],
        primaryInformation=["剩余天数"],
        informationHierarchy=["标题", "倒计时"],
        temporality="upcoming",
        interaction="none",
        visualTone="活力运动感",
        contentPriorities=["倒计时"],
        reason="突出剩余天数。",
    )

    selection = select_component(
        data_shape,
        brief,
        SelectionConstraints(size="2x2", action_count=0, asset_count=0),
    )

    assert selection is not None
    assert selection.component_id == "hero-countdown"
    plugin = get_component(selection.component_id)
    invocation = plugin.map_offline(task_spec, data_shape)
    assert invocation.action is None
    terse = build_terse_nested2(
        selection.component_id,
        invocation,
        task_spec,
        "race-orange",
    )
    assert "Button(" not in terse
    assert '"path":"/data/countdown/countdownDays"' in terse


class OfflineModelClient:
    async def generate_json(self, _prompt, *, phase):
        raise RuntimeError(f"offline: {phase}")

    async def generate(self, *_args, **_kwargs):
        return (
            'Template("card@1", {}, Column("section", '
            'Text("设备电量低于20", "body"), '
            'Progress({"value":18,"total":100}), '
            'Text("电量低于20%，开启省电模式", "body")));'
        )


class StructuredModelClient:
    def __init__(self):
        self.phases = []
        self.prompts = {}

    async def generate_json(self, prompt, *, phase):
        self.phases.append(phase)
        self.prompts[phase] = prompt
        if phase == "advanced-ui-brief":
            return {
                "purpose": "低电量状态和省电操作",
                "domain": "device",
                "scenario": "low-power",
                "layoutArchetype": "status-ring-action",
                "statusSemantics": ["low-power", "warning"],
                "contentSemantics": ["battery-level", "percentage", "status"],
                "actionSemantics": ["enable-power-saving"],
                "primaryInformation": ["设备电量"],
                "informationHierarchy": ["指标", "操作"],
                "density": "compact",
                "temporality": "now",
                "interaction": "one-primary-action",
                "attention": "warning-capable",
                "visualTone": "technical-efficient",
                "contentPriorities": ["低电量状态优先"],
                "reason": "突出电量状态和省电入口。",
            }
        return {
            "status_text": {"path": "/data/battery/status"},
            "percentage": {"path": "/data/battery/batteryPercent"},
            "battery_icon": "asset.electricity",
            "action_icon": "asset.save_power",
            "action": {"event_id": "event.enable.power", "label": "开启省电"},
        }


@pytest.mark.asyncio
async def test_pipeline_uses_two_structured_model_calls_and_builds_template():
    model_client = StructuredModelClient()
    task_spec = _metric_task_spec()
    output = await AdvancedComponentPipeline().generate(task_spec, model_client)

    assert output is not None
    assert output.component_id == "status-ring-action"
    assert output.planner_mode == "llm"
    assert output.mapper_mode == "llm"
    assert model_client.phases == ["advanced-ui-brief", "advanced-argument-map"]
    planner_payload = json.loads(model_client.prompts["advanced-ui-brief"][1]["content"])
    assert planner_payload["eventCandidates"] == [
        event.model_dump(exclude_none=True) for event in task_spec.eventCandidates
    ]
    argument_payload = json.loads(model_client.prompts["advanced-argument-map"][1]["content"])
    assert argument_payload["assetCandidates"] == task_spec.assetCandidates
    assert output.source_dsl.startswith('Column("card"')
    assert "\ndata = " in output.source_dsl
    assert '"onClick":[{"call":"clickToApi","args":{}}]' in output.source_dsl


@pytest.mark.asyncio
async def test_pipeline_uses_offline_fallback_when_structured_model_fails():
    output = await AdvancedComponentPipeline().generate(
        _metric_task_spec(),
        OfflineModelClient(),
    )

    assert output is not None
    assert output.planner_mode == "offline"
    assert output.mapper_mode == "offline"


@pytest.mark.asyncio
async def test_pipeline_can_disable_offline_fallback_for_strict_evaluation():
    with pytest.raises(RuntimeError, match="offline: advanced-ui-brief"):
        await AdvancedComponentPipeline().generate(
            _metric_task_spec(),
            OfflineModelClient(),
            allow_offline_fallback=False,
        )


@pytest.mark.asyncio
async def test_pipeline_output_format_switch_can_emit_standard_a2ui(monkeypatch):
    monkeypatch.setattr(
        advanced_pipeline_module,
        "get_settings",
        lambda: SimpleNamespace(advanced_component_output_format="a2ui"),
    )

    output = await AdvancedComponentPipeline().generate(
        _metric_task_spec(),
        OfflineModelClient(),
    )

    assert output is not None
    assert output.source_format == "a2ui"
    assert len(output.source_dsl.splitlines()) == 3
    assert '"createSurface"' in output.source_dsl


@pytest.mark.asyncio
async def test_pipeline_uses_selected_template_even_when_confidence_is_low(monkeypatch):
    original_select_component = advanced_pipeline_module.select_component

    def select_with_low_confidence(*args, **kwargs):
        selection = original_select_component(*args, **kwargs)
        assert selection is not None
        return selection.model_copy(update={"confidence": 0.5})

    monkeypatch.setattr(
        advanced_pipeline_module,
        "select_component",
        select_with_low_confidence,
    )
    output = await AdvancedComponentPipeline().generate(
        _metric_task_spec(),
        OfflineModelClient(),
    )

    assert output is not None
    assert output.route == "whole-card-template"
    assert output.component_id == "status-ring-action"
    assert output.whole_card_confidence == 0.5
    assert output.fallback_used is False
    assert "Template" not in output.compiled_a2ui


@pytest.mark.asyncio
async def test_server_switch_disables_whole_card_template(monkeypatch):
    monkeypatch.setattr(get_settings(), "enable_advanced_whole_card_template", False)

    output = await AdvancedComponentPipeline().generate(
        _metric_task_spec(),
        OfflineModelClient(),
    )

    assert output is not None
    assert output.route == "hybrid-template"
    assert output.confidence_bypassed is True
    assert output.fallback_used is False


_WEATHER_TERSE_BODY = (
    'SingleFocusLayout(Template("WeatherOverview@1","heroIcon",'
    '{"conditionIcon":"resources/base/media/weather.svg"}));'
)


class UxMixedModelClient:
    def __init__(self, body: str | None = None):
        self.phases: list[str] = []
        self.prompts: dict[str, list[dict[str, str]]] = {}
        self.body = body or _WEATHER_TERSE_BODY

    async def generate_json(self, prompt, *, phase):
        self.phases.append(phase)
        self.prompts[phase] = prompt
        return {
            "scopeVersion": "advanced-scope-brief/1",
            "themeId": "family-weather-care-blue",
            "advancedComponentIds": ["WeatherOverview"],
        }

    async def generate(self, messages, _profile, **kwargs):
        phase = kwargs.get("phase", "")
        self.phases.append(phase)
        self.prompts[phase] = messages
        return self.body


class RetryingUxMixedModelClient(UxMixedModelClient):
    def __init__(self, bodies: list[str]):
        super().__init__(bodies[-1])
        self.bodies = list(bodies)

    async def generate(self, messages, _profile, **kwargs):
        phase = kwargs.get("phase", "")
        self.phases.append(phase)
        self.prompts[phase] = messages
        return self.bodies.pop(0)


def _weather_scope_task() -> TaskSpec:
    return TaskSpec(
        userQuery="天气",
        size="2x2",
        eventCandidates=[],
        assetCandidates=[
            {
                "src": "resources/base/media/weather.svg",
                "description": "天气状态图标",
                "sceneTags": ["condition", "weather"],
            }
        ],
        dataModelSchema={
            "data": {
                "ViewWeather": {
                    "location": {"districtName": _sample_field("深圳")},
                    "current": {
                        "temperatureText": _sample_field("38°"),
                        "condition": _sample_field("晴"),
                        "airQuality": _sample_field("空气优"),
                    },
                    "daily": [
                        {"temperatureRangeText": _sample_field("26° / 16°")}
                    ],
                }
            }
        },
    )


def _weather_card_spec(size: str = "2x2") -> dict[str, Any]:
    return {
        "title": "天气",
        "description": "天气状态",
        "suggestSize": size,
        "dataBindings": [
            {
                "capabilityId": "ViewWeather",
                "arguments": {},
                "writeResultTo": "/data/ViewWeather",
            }
        ],
    }


def _weather_scope_task_with_values(
    *,
    city: str,
    temperature: str,
    condition: str,
    air_quality: str,
    temperature_range: str,
    asset_candidates: list[dict[str, Any]] | None = None,
) -> TaskSpec:
    task_spec = _weather_scope_task()
    data_model_schema = deepcopy(task_spec.dataModelSchema)
    weather = data_model_schema["data"]["ViewWeather"]
    weather["location"]["districtName"] = _sample_field(city)
    weather["current"]["temperatureText"] = _sample_field(temperature)
    weather["current"]["condition"] = _sample_field(condition)
    weather["current"]["airQuality"] = _sample_field(air_quality)
    weather["daily"][0]["temperatureRangeText"] = _sample_field(temperature_range)
    updates: dict[str, Any] = {"dataModelSchema": data_model_schema}
    if asset_candidates is not None:
        updates["assetCandidates"] = asset_candidates
    return task_spec.model_copy(update=updates)


def _projected_weather_template_task() -> tuple[TaskSpec, dict[str, Any]]:
    selected = apply_content_selectors(_weather_scope_task(), {"ViewWeather"})
    projected = project_content_component_facts(
        selected,
        {"ViewWeather"},
        ("WeatherOverview",),
    )
    projected_schema = deepcopy(projected.dataModelSchema)
    projected_schema["data"]["ViewWeather"] = deepcopy(
        selected.dataModelSchema["data"]["ViewWeather"]
    )
    return (
        projected.model_copy(update={"dataModelSchema": projected_schema}),
        _weather_card_spec(),
    )


def test_new_scope_prompt_only_exposes_theme_and_advanced_component_output():
    task_spec = _weather_scope_task()
    prompt = build_advanced_scope_prompt(
        task_spec,
        extract_data_shape(task_spec),
        get_cardplan_registry(),
    )
    user_payload = json.loads(prompt[1]["content"])
    output_schema = json.loads(prompt[0]["content"].split("\n", 1)[1])

    assert set(output_schema["properties"]) == {
        "scopeVersion",
        "themeId",
        "advancedComponentIds",
    }
    assert "cardPlanCandidates" not in user_payload
    assert "localTemplates" not in user_payload
    assert "layoutComponents" not in user_payload
    assert len(user_payload["advancedComponents"]) <= 8


def _weather_coverage_binding(*fields: str) -> CandidateDataBinding:
    return CandidateDataBinding(
        capabilityId="ViewWeather",
        writeResultTo="/data/ViewWeather",
        candidateOutputFields=list(fields),
    )


@pytest.mark.asyncio
async def test_template_route_first_layer_accepts_only_full_weather_coverage():
    task_spec = _weather_scope_task()
    coverage_binding = _weather_coverage_binding(
        "/location/districtName",
        "/current/temperatureText",
        "/current/condition",
        "/current/airQuality",
        "/daily/0/temperatureRangeText",
    )

    async def generate_json(prompt, phase):
        assert phase == "template-route-decision"
        user_payload = json.loads(prompt[1]["content"])
        weather = next(
            item
            for item in user_payload["advancedComponents"]
            if item["id"] == "WeatherOverview"
        )
        assert user_payload["requiredOutputFieldsByCapability"]["ViewWeather"]
        assert "/current/condition" in weather["templateCoverageByCapability"]["ViewWeather"]
        return {
            "routeVersion": "template-route-decision/1",
            "templateUsable": True,
            "themeId": "family-weather-care-blue",
            "advancedComponentIds": ["WeatherOverview"],
        }

    scope = await plan_template_route_with_llm(
        task_spec,
        extract_data_shape(task_spec),
        generate_json,
        get_cardplan_registry(),
        (coverage_binding,),
        ("ViewWeather",),
        _weather_card_spec(),
    )

    assert scope.advanced_component_ids == ("WeatherOverview",)


@pytest.mark.asyncio
async def test_template_route_rejects_when_one_requested_field_is_not_covered():
    task_spec = _weather_scope_task()
    coverage_binding = _weather_coverage_binding(
        "/current/condition",
        "/current/humidity",
    )

    async def generate_json(_prompt, _phase):
        return {
            "routeVersion": "template-route-decision/1",
            "templateUsable": True,
            "themeId": "family-weather-care-blue",
            "advancedComponentIds": ["WeatherOverview"],
        }

    with pytest.raises(TemplateRouteNotApplicable, match="do not cover every"):
        await plan_template_route_with_llm(
            task_spec,
            extract_data_shape(task_spec),
            generate_json,
            get_cardplan_registry(),
            (coverage_binding,),
            ("ViewWeather",),
            _weather_card_spec(),
        )


@pytest.mark.asyncio
async def test_template_route_respects_first_layer_rejection():
    task_spec = _weather_scope_task()

    async def generate_json(_prompt, _phase):
        return {
            "routeVersion": "template-route-decision/1",
            "templateUsable": False,
            "themeId": None,
            "advancedComponentIds": [],
        }

    with pytest.raises(TemplateRouteNotApplicable, match="LLM rejected"):
        await plan_template_route_with_llm(
            task_spec,
            extract_data_shape(task_spec),
            generate_json,
            get_cardplan_registry(),
            (_weather_coverage_binding("/current/condition"),),
            ("ViewWeather",),
            _weather_card_spec(),
        )


def test_scope_prompt_does_not_pad_positive_matches_with_zero_score_components():
    prompt = build_advanced_scope_prompt(
        _weather_scope_task(),
        extract_data_shape(_weather_scope_task()),
        get_cardplan_registry(),
    )
    candidates = {item["id"] for item in json.loads(prompt[1]["content"])["advancedComponents"]}

    assert "WeatherOverview" in candidates
    assert "MemoPreview" not in candidates


def test_scope_candidates_do_not_promote_action_words_over_calendar_data():
    task_spec = TaskSpec(
        userQuery="展示下一日程并进入专注模式",
        size="2x2",
        eventCandidates=[EventAction(id="event.open.settings.dnd", call="clickToApi", args={})],
        dataModelSchema={
            "GetCalendarEvents": {
                "events": [
                    {
                        "title": _sample_field("UI需求评审会"),
                        "dtStart": _sample_field("14:00"),
                        "dtEnd": _sample_field("15:30"),
                    }
                ]
            }
        },
        assetCandidates=[],
    )
    prompt = build_advanced_scope_prompt(
        task_spec,
        extract_data_shape(task_spec),
        get_cardplan_registry(),
    )
    candidates = {item["id"] for item in json.loads(prompt[1]["content"])["advancedComponents"]}

    assert "ScheduleOverview" in candidates
    assert "SystemModeOverview" not in candidates


def test_scope_candidates_match_memory_as_device_resource_not_memo_substring():
    task_spec = TaskSpec(
        userQuery="展示内存占用并支持一键清理",
        size="2x2",
        eventCandidates=[EventAction(id="event.clean.memory", call="clickToApi", args={})],
        dataModelSchema={
            "GetSystemMemInfo": {
                "usagePercent": {"type": "number", "sampleValue": 72},
                "availableMemText": {"type": "string", "sampleValue": "3.6 GB 可用"},
                "totalMemText": {"type": "string", "sampleValue": "共 12 GB"},
            }
        },
        assetCandidates=[],
    )
    prompt = build_advanced_scope_prompt(
        task_spec,
        extract_data_shape(task_spec),
        get_cardplan_registry(),
    )
    component_candidates = json.loads(prompt[1]["content"])["advancedComponents"]
    candidates = {item["id"] for item in component_candidates}

    assert "ResourceUsageOverview" in candidates
    resource = next(item for item in component_candidates if item["id"] == "ResourceUsageOverview")
    assert resource["variants"] == ["memory"]
    assert "BatteryOverview" not in candidates
    assert "MemoPreview" not in candidates


def test_scope_provider_gate_hides_components_without_effective_data_capability():
    task_spec = TaskSpec(
        userQuery="展示待办并打开设置",
        size="2x2",
        eventCandidates=[EventAction(id="event.open.settings", call="clickToApi", args={})],
        dataModelSchema={"data": {"label": "待办"}},
        assetCandidates=[],
    )

    with pytest.raises(ValueError, match="no provider-backed"):
        build_advanced_scope_prompt(
            task_spec,
            extract_data_shape(task_spec),
            get_cardplan_registry(),
            available_capability_ids=(),
        )


@pytest.mark.parametrize(
    ("capability_id", "query", "component_id", "variants"),
    [
        (
            "GetAppUsageDuration",
            "展示抖音今天的使用时长",
            "AppUsageOverview",
            ["singleApp"],
        ),
        (
            "GetHealthAndSportSummary",
            "展示运动平均心率",
            "HeartRateOverview",
            ["average"],
        ),
    ],
)
def test_scope_exposes_only_provider_backed_component_variants(
    capability_id: str,
    query: str,
    component_id: str,
    variants: list[str],
) -> None:
    schema: dict[str, object] = {capability_id: {}}
    if capability_id == "GetAppUsageDuration":
        schema = {
            capability_id: {
                "appUsage": {
                    "appName": _sample_field("抖音"),
                    "durationText": _sample_field("25分钟"),
                },
                "updatedAt": _sample_field("今日 21:30"),
            }
        }
    elif component_id == "HeartRateOverview":
        schema = {
            capability_id: {
                "exerciseHeartRateAvg": {
                    "type": "integer",
                    "description": "可信运动平均心率",
                    "sampleValue": 128,
                }
            }
        }
    task_spec = TaskSpec(
        userQuery=query,
        size="2x2",
        dataModelSchema=schema,
        assetCandidates=[],
    )

    prompt = build_advanced_scope_prompt(
        task_spec,
        extract_data_shape(task_spec),
        get_cardplan_registry(),
        available_capability_ids=(capability_id,),
    )
    candidates = json.loads(prompt[1]["content"])["advancedComponents"]
    selected = next(item for item in candidates if item["id"] == component_id)

    assert selected["variants"] == variants


def test_explicit_provider_id_does_not_override_app_usage_fact_and_intent_gate():
    task_spec = TaskSpec(
        userQuery="展示待办和设置，但只有应用时长能力可用",
        size="2x2",
        dataModelSchema={"data": {"task": "待办", "setting": "设置"}},
        assetCandidates=[],
    )

    with pytest.raises(ValueError, match="no provider-backed"):
        build_advanced_scope_prompt(
            task_spec,
            extract_data_shape(task_spec),
            get_cardplan_registry(),
            available_capability_ids=("GetAppUsageDuration",),
        )


def test_2x2_scope_prompt_does_not_advertise_atomic_context_as_second_component():
    task_spec = _weather_scope_task()
    prompt = build_advanced_scope_prompt(
        task_spec,
        extract_data_shape(task_spec),
        get_cardplan_registry(),
        available_capability_ids=("ViewWeather",),
    )
    candidates = json.loads(prompt[1]["content"])["advancedComponents"]
    weather = next(item for item in candidates if item["id"] == "WeatherOverview")

    assert "LocationOverview" not in weather["compatibleWith"]


@pytest.mark.asyncio
async def test_2x2_scope_normalizes_weather_location_to_atomic_weather_owner():
    task_spec = _weather_scope_task()

    async def generate_json(_messages, _phase):
        return {
            "scopeVersion": "advanced-scope-brief/1",
            "themeId": "family-weather-care-blue",
            "advancedComponentIds": ["WeatherOverview", "LocationOverview"],
        }

    scope = await plan_advanced_scope_with_llm(
        task_spec,
        extract_data_shape(task_spec),
        generate_json,
        get_cardplan_registry(),
        available_capability_ids=("ViewWeather",),
    )

    assert scope.advanced_component_ids == ("WeatherOverview",)


def test_calendar_selector_derives_only_trusted_date_weekday_and_time_aliases():
    task_spec = TaskSpec(
        userQuery="下一场会议",
        size="2x2",
        dataModelSchema={
            "data": {
                "GetCalendarEvents": {
                    "events": [
                        {
                            "title": _sample_field("产品评审"),
                            "dtStart": _sample_field("09:30"),
                            "dtEnd": _sample_field("10:30"),
                            "eventLocation": _sample_field("A区会议室"),
                            "startDate": _sample_field("07-15"),
                        }
                    ],
                    "updatedAt": _sample_field("2026-07-15 09:00"),
                }
            }
        },
        assetCandidates=[],
    )

    selected = apply_content_selectors(task_spec, {"GetCalendarEvents"})
    derived = selected.dataModelSchema["data"]["_advancedSelectors"]

    assert derived["schedule"]["title"]["sampleValue"] == "产品评审"
    assert derived["schedule"]["timeText"]["sampleValue"] == "09:30 - 10:30"
    assert derived["schedule"]["location"]["sampleValue"] == "A区会议室"
    assert derived["date"]["date"]["sampleValue"] == "15日"
    assert derived["date"]["weekday"]["sampleValue"] == "星期三"
    assert "_advancedSelectors" not in task_spec.dataModelSchema["data"]


def test_weather_selector_requires_complete_current_weather_facts():
    complete = TaskSpec(
        userQuery="天气",
        size="2x2",
        dataModelSchema={
            "data": {
                "location": {
                    "districtName": _sample_field("龙岗区"),
                    "prefectureName": _sample_field("深圳市"),
                },
                "current": {
                    "temperatureText": _sample_field("38℃"),
                    "condition": _sample_field("晴"),
                    "airQuality": _sample_field("优"),
                },
                "daily": [{"temperatureRangeText": _sample_field("26℃ / 16℃")}],
                "updatedAt": _sample_field("2026-07-15 09:30"),
            }
        },
        assetCandidates=[],
    )

    selected = apply_content_selectors(complete, {"ViewWeather"})
    derived = selected.dataModelSchema["data"]["_advancedSelectors"]

    assert derived["weather"]["city"]["sampleValue"] == "龙岗区"
    assert derived["weather"]["temperature"]["sampleValue"] == "38℃"
    assert derived["weather"]["temperatureRange"]["sampleValue"] == "26℃ / 16℃"
    assert derived["location"]["label"]["sampleValue"] == "天气位置"

    incomplete = complete.model_copy(
        update={"dataModelSchema": {"data": {"current": {"condition": _sample_field("晴")}}}}
    )
    unchanged = apply_content_selectors(incomplete, {"ViewWeather"})
    assert unchanged is incomplete


@pytest.mark.parametrize(
    "missing_field",
    ["city", "temperatureText", "condition", "airQuality", "temperatureRangeText"],
)
def test_scope_hides_weather_when_any_required_fact_is_missing(missing_field: str):
    fields = {
        "districtName": _sample_field("深圳"),
        "temperatureText": _sample_field("38°"),
        "condition": _sample_field("晴"),
        "airQuality": _sample_field("空气优"),
        "temperatureRangeText": _sample_field("26° / 16°"),
    }
    if missing_field == "city":
        fields.pop("districtName")
    else:
        fields.pop(missing_field)
    task_spec = _weather_scope_task().model_copy(
        update={"dataModelSchema": {"ViewWeather": fields}}
    )

    assert "WeatherOverview" not in _scope_candidate_ids(
        task_spec,
        ("ViewWeather",),
    )


def test_scope_accepts_prefecture_as_weather_city_fallback():
    task_spec = _weather_scope_task().model_copy(
        update={
            "dataModelSchema": {
                "ViewWeather": {
                    "prefectureName": _sample_field("深圳市"),
                    "temperatureText": _sample_field("38°"),
                    "condition": _sample_field("晴"),
                    "airQuality": _sample_field("空气优"),
                    "temperatureRangeText": _sample_field("26° / 16°"),
                }
            }
        }
    )

    prompt = build_advanced_scope_prompt(
        task_spec,
        extract_data_shape(task_spec),
        get_cardplan_registry(),
        available_capability_ids=("ViewWeather",),
    )

    assert "WeatherOverview" in {
        item["id"] for item in json.loads(prompt[1]["content"])["advancedComponents"]
    }


@pytest.mark.parametrize(
    ("field_name", "invalid_field"),
    [
        ("temperatureText", {"type": "number", "sampleValue": 38}),
        ("condition", {"type": "string", "sampleValue": "  "}),
    ],
)
def test_scope_hides_weather_for_wrong_types_or_empty_strings(
    field_name: str,
    invalid_field: dict[str, object],
):
    schema = deepcopy(_weather_scope_task().dataModelSchema["data"]["ViewWeather"])
    schema["current"][field_name] = invalid_field
    task_spec = _weather_scope_task().model_copy(
        update={"dataModelSchema": {"data": {"ViewWeather": schema}}}
    )

    assert "WeatherOverview" not in _scope_candidate_ids(
        task_spec,
        ("ViewWeather",),
    )


def test_scope_hides_weather_when_only_unsupported_weather_fields_exist():
    task_spec = _weather_scope_task().model_copy(
        update={
            "dataModelSchema": {
                "ViewWeather": {
                    "pressure": _sample_field("1008 hPa"),
                    "visibility": _sample_field("10 km"),
                    "aqi": {"type": "integer", "sampleValue": 42},
                }
            }
        }
    )

    assert "WeatherOverview" not in _scope_candidate_ids(
        task_spec,
        ("ViewWeather",),
    )


@pytest.mark.parametrize(
    "query",
    [
        "逐小时天气预报",
        "日出日落",
        "当前气压",
        "天气能见度",
        "显示 AQI 数值",
        "展示体感温度、湿度、风力、紫外线、预警和降雨概率",
    ],
)
def test_scope_hides_weather_for_unsupported_user_requests(query: str):
    task_spec = _weather_scope_task().model_copy(update={"userQuery": query})

    assert "WeatherOverview" not in _scope_candidate_ids(
        task_spec,
        ("ViewWeather",),
    )


def test_weather_field_coverage_exposes_requested_renderable_visible_gap():
    query = "展示上海天气、体感温度、湿度、空气质量、风力、紫外线、预警和降雨概率"

    coverage = advanced_pipeline_module.weather_field_coverage(
        query,
        _weather_scope_task(),
        "",
    )

    assert set(coverage["requested"]) == {
        "city",
        "temperature",
        "condition",
        "airQuality",
        "temperatureRange",
        "feelsLike",
        "humidity",
        "wind",
        "uvIndex",
        "alert",
        "rainProbability",
    }
    assert coverage["renderableCount"] == 5
    assert coverage["visibleCount"] == 0


def _scope_candidate_ids(
    task_spec: TaskSpec,
    capability_ids: tuple[str, ...],
) -> set[str]:
    try:
        prompt = build_advanced_scope_prompt(
            task_spec,
            extract_data_shape(task_spec),
            get_cardplan_registry(),
            available_capability_ids=capability_ids,
        )
    except ValueError as exc:
        if str(exc) == "no provider-backed UX Business Component candidate":
            return set()
        raise
    return {
        item["id"] for item in json.loads(prompt[1]["content"])["advancedComponents"]
    }


@pytest.mark.asyncio
async def test_scope_rejects_forced_weather_model_output_when_five_facts_are_incomplete():
    task_spec = TaskSpec(
        userQuery="天气和手机电量",
        size="2x2",
        dataModelSchema={
            "ViewWeather": {"condition": _sample_field("晴")},
            "GetPhoneBatteryInfo": {
                "batterySOCText": _sample_field("68%"),
                "batteryCapacityLevelDesc": _sample_field("电量正常"),
            },
        },
        assetCandidates=[],
    )

    async def generate_json(_messages, _phase):
        return {
            "scopeVersion": "advanced-scope-brief/1",
            "themeId": "family-weather-care-blue",
            "advancedComponentIds": ["WeatherOverview"],
        }

    with pytest.raises(ValueError, match="outside trusted candidates"):
        await plan_advanced_scope_with_llm(
            task_spec,
            extract_data_shape(task_spec),
            generate_json,
            get_cardplan_registry(),
            available_capability_ids=("ViewWeather", "GetPhoneBatteryInfo"),
        )


@pytest.mark.asyncio
async def test_cross_domain_weather_scope_preserves_primary_scene_theme():
    task_spec = apply_content_selectors(
        _weather_schedule_task("2x4", with_action=False),
        {"ViewWeather", "GetCalendarEvents"},
    )

    async def generate_json(_messages, _phase):
        return {
            "scopeVersion": "advanced-scope-brief/1",
            "themeId": "family-weather-care-blue",
            "advancedComponentIds": ["WeatherOverview", "ScheduleOverview"],
        }

    scope = await plan_advanced_scope_with_llm(
        task_spec,
        extract_data_shape(task_spec),
        generate_json,
        get_cardplan_registry(),
        available_capability_ids=("ViewWeather", "GetCalendarEvents"),
    )

    assert scope.advanced_component_ids == ("WeatherOverview", "ScheduleOverview")
    assert scope.theme_id == "family-weather-care-blue"


def test_weather_multi_business_layout_candidates_exclude_forecast_layout():
    registry = get_cardplan_registry()
    scope = AdvancedScopeBrief(
        themeId="meeting-paper-neutral",
        advancedComponentIds=("WeatherOverview", "ScheduleOverview"),
    )
    layouts_2x2 = resolve_scope_layout_ids(
        scope,
        _weather_schedule_task("2x2", with_action=False),
        registry,
    )
    layouts_2x4 = resolve_scope_layout_ids(
        scope,
        _weather_schedule_task("2x4", with_action=False),
        registry,
    )

    assert layouts_2x2 == ("HeroSupportLayout",)
    assert "HeroSupportLayout" in layouts_2x4
    assert "WeatherNowForecastLayout" not in layouts_2x2
    assert "WeatherNowForecastLayout" not in layouts_2x4


def test_weather_single_business_layout_candidates_exclude_forecast_layout():
    registry = get_cardplan_registry()
    for size in ("2x2", "2x4"):
        task_spec = _weather_scope_task().model_copy(update={"size": size})
        scope = AdvancedScopeBrief(
            themeId="family-weather-care-blue",
            advancedComponentIds=("WeatherOverview",),
        )

        layouts = resolve_scope_layout_ids(scope, task_spec, registry)

        assert "SingleFocusLayout" in layouts
        assert "WeatherNowForecastLayout" not in layouts


def test_selectors_expose_weather_and_migrated_calendar_templates():
    weather = TaskSpec(
        userQuery="天气",
        size="2x2",
        dataModelSchema={
            "ViewWeather": {
                "districtName": _sample_field("龙岗区"),
                "temperatureText": _sample_field("38℃"),
                "condition": _sample_field("晴"),
                "airQuality": _sample_field("优"),
                "temperatureRangeText": _sample_field("26℃ / 16℃"),
                "updatedAt": _sample_field("2026-07-15 09:30"),
            }
        },
        assetCandidates=[
            {
                "src": "resources/base/media/weather.svg",
                "description": "天气状态图标",
                "sceneTags": ["condition", "weather"],
            }
        ],
    )
    selected = apply_content_selectors(weather, {"ViewWeather"})
    templates = scope_template_ids(
        AdvancedScopeBrief(
            themeId="family-weather-care-blue",
            advancedComponentIds=("WeatherOverview",),
        ),
        get_cardplan_registry(),
        selected,
    )

    assert templates == ("WeatherOverview@1",)

    calendar = TaskSpec(
        userQuery="下一场会议",
        size="2x2",
        dataModelSchema={
            "GetCalendarEvents": {
                "events": [
                    {
                        "title": _sample_field("产品评审"),
                        "dtStart": _sample_field("09:30"),
                        "dtEnd": _sample_field("10:30"),
                        "eventLocation": _sample_field("A区会议室"),
                        "startDate": _sample_field("07-15"),
                    }
                ],
                "updatedAt": _sample_field("2026-07-15 09:00"),
            }
        },
        assetCandidates=[],
    )
    selected_calendar = apply_content_selectors(calendar, {"GetCalendarEvents"})
    calendar_templates = scope_template_ids(
        AdvancedScopeBrief(
            themeId="meeting-paper-neutral",
            advancedComponentIds=("DateOverview", "ScheduleOverview"),
        ),
        get_cardplan_registry(),
        selected_calendar,
    )

    assert calendar_templates == ("DateOverview@1", "ScheduleOverview@1")


def test_second_layer_projection_keeps_only_selected_component_display_facts():
    task_spec = TaskSpec(
        userQuery="深圳天气",
        size="2x2",
        dataModelSchema={
            "data": {
                "weather": {
                    "location": {"districtName": _sample_field("深圳")},
                    "current": {
                        "temperatureText": _sample_field("38°"),
                        "condition": _sample_field("晴"),
                        "airQuality": _sample_field("空气优"),
                    },
                    "daily": [{"temperatureRangeText": _sample_field("26° / 16°")}],
                    "updatedAt": _sample_field("2026-08-11 10:00"),
                    "transportMetadata": _sample_field("不得进入卡片"),
                },
                "calendar": {"events": [{"title": _sample_field("另一个领域")}]},
            }
        },
        assetCandidates=[],
    )

    selected = apply_content_selectors(task_spec, {"ViewWeather", "GetCalendarEvents"})
    projected = project_content_component_facts(
        selected,
        {"ViewWeather", "GetCalendarEvents"},
        ("WeatherOverview",),
    )

    assert set(projected.dataModelSchema["data"]) == {"WeatherOverview"}
    assert set(projected.dataModelSchema["data"]["WeatherOverview"]) == {
        "city",
        "temperature",
        "condition",
        "airQuality",
        "temperatureRange",
    }
    assert "updatedAt" not in json.dumps(projected.dataModelSchema, ensure_ascii=False)
    assert "不得进入卡片" not in json.dumps(projected.dataModelSchema, ensure_ascii=False)


def test_battery_projection_derives_trusted_number_from_percentage_text():
    task_spec = TaskSpec(
        userQuery="手机电量",
        size="2x2",
        dataModelSchema={
            "GetPhoneBatteryInfo": {
                "batterySOCText": _sample_field("68%"),
                "batteryCapacityLevelDesc": _sample_field("电量正常"),
                "chargingStatusDesc": _sample_field("充电中"),
            }
        },
        assetCandidates=[
            {
                "src": "resources/base/media/battery.svg",
                "description": "手机电池图标",
                "sceneTags": ["battery", "power"],
            }
        ],
    )

    projected = project_content_component_facts(
        task_spec,
        {"GetPhoneBatteryInfo"},
        ("BatteryOverview",),
    )

    assert projected.dataModelSchema["data"]["BatteryOverview"]["batterySOC"] == {
        "type": "integer",
        "description": "可信手机本机电量百分比数值",
        "sampleValue": 68,
    }
    provider_projected, card_spec, registry = prepare_provider_scope_projection(
        task_spec,
        {"GetPhoneBatteryInfo"},
        ("BatteryOverview",),
    )
    projection = build_ux_mixed_prompt(
        task_spec=provider_projected,
        card_spec=card_spec,
        scope=AdvancedScopeBrief(
            themeId="system-low-power-blue",
            advancedComponentIds=("BatteryOverview",),
        ),
        registry=registry,
    )

    assert 68 in projection.contract.trusted_numbers
    assert projection.contract.required_template_groups == (("BatteryOverview@1",),)


def test_ux_layout_parser_unwraps_single_object_config_array():
    parsed = parse_ux_layout_card(
        'SingleFocusLayout([{"contentAlign":"centerStart"}], Text("天气", "body"));'
    )

    assert parsed.values == ({"contentAlign": "centerStart"},)


def test_workout_projection_uses_only_provider_backed_countdown_variant_fields():
    task_spec = TaskSpec(
        userQuery="赛事倒计时",
        size="2x2",
        dataModelSchema={
            "GetCountdownDays": {
                "countdownDays": {"type": "integer", "sampleValue": 32}
            },
            "GetHealthAndSportSummary": {
                "exerciseTypeName": _sample_field("户外跑步"),
                "exerciseDurationText": _sample_field("40分"),
                "exerciseCalorieText": _sample_field("298 千卡"),
            },
        },
        assetCandidates=[],
    )

    projected = project_content_component_facts(
        task_spec,
        {"GetCountdownDays"},
        ("WorkoutOverview",),
    )

    assert projected.dataModelSchema == {
        "data": {
            "WorkoutOverview": {
                "countdownDays": {
                    "type": "integer",
                    "description": "可信非负剩余天数，0 天为有效值",
                    "sampleValue": 32,
                }
            }
        }
    }


@pytest.mark.parametrize(
    ("duration", "expected"),
    [
        ("3小时45分钟", ("3", "小时", "45", "分钟")),
        ("45分钟", ("45", "分钟", "", "")),
        ("3h 05m", ("3", "小时", "05", "分钟")),
    ],
)
def test_app_usage_projection_derives_trusted_dual_value_segments(
    duration: str,
    expected: tuple[str, str, str, str],
) -> None:
    task_spec = TaskSpec(
        userQuery="应用时长",
        size="2x2",
        dataModelSchema={
            "data": {
                "AppUsageOverview": {
                    "appName": _sample_field("抖音"),
                    "durationText": _sample_field(duration),
                    "updatedAt": _sample_field("今日"),
                }
            }
        },
        assetCandidates=[],
    )

    projected = project_content_component_facts(
        task_spec,
        {"GetAppUsageDuration"},
        ("AppUsageOverview",),
    )
    usage = projected.dataModelSchema["data"]["AppUsageOverview"]

    actual = (
        usage["durationPrimaryValueText"]["sampleValue"],
        usage["durationPrimaryUnitText"]["sampleValue"],
        usage.get("durationSecondaryValueText", {}).get("sampleValue", ""),
        usage.get("durationSecondaryUnitText", {}).get("sampleValue", ""),
    )
    assert actual == expected


def test_sleep_projection_reuses_trusted_dual_value_segments() -> None:
    task_spec = TaskSpec(
        userQuery="睡眠",
        size="2x2",
        dataModelSchema={
            "GetHealthAndSportSummary": {
                "sleepStatus": _sample_field("睡眠不足"),
                "nightSleepDurationText": _sample_field("5小时45分钟"),
                "fallAsleepTimeText": _sample_field("23:15"),
                "wakeupTimeText": _sample_field("05:00"),
            }
        },
        assetCandidates=[],
    )

    projected = project_content_component_facts(
        task_spec,
        {"GetHealthAndSportSummary"},
        ("SleepOverview",),
    )
    sleep = projected.dataModelSchema["data"]["SleepOverview"]

    assert tuple(
        sleep[name]["sampleValue"]
        for name in (
            "sleepDurationPrimaryValueText",
            "sleepDurationPrimaryUnitText",
            "sleepDurationSecondaryValueText",
            "sleepDurationSecondaryUnitText",
        )
    ) == ("5", "小时", "45", "分钟")


def _sample_field(value: str) -> dict[str, str]:
    return {
        "type": "string",
        "description": "可信能力字段",
        "sampleValue": value,
    }


@pytest.mark.asyncio
async def test_scope_planner_normalizes_empty_model_selection_without_retry():
    task_spec = _weather_scope_task()
    calls = 0

    async def generate_json(_messages, _phase):
        nonlocal calls
        calls += 1
        return {
            "scopeVersion": "advanced-scope-brief/1",
            "themeId": "family-weather-care-blue",
            "advancedComponentIds": [],
        }

    scope = await plan_advanced_scope_with_llm(
        task_spec,
        extract_data_shape(task_spec),
        generate_json,
        get_cardplan_registry(),
    )

    assert calls == 1
    assert scope.advanced_component_ids == ("WeatherOverview",)


def test_schedule_migration_exposes_provider_template_dependency():
    task_spec = TaskSpec(
        userQuery="加入当前会议",
        size="2x2",
        eventCandidates=[EventAction(id="event.enter.meeting", call="clickToApi", args={})],
        dataModelSchema={
            "data": {
                "event": {
                    "title": "UI需求评审会",
                    "time": "14:00 - 15:30",
                    "location": "深圳市龙岗区五和大道华为园区",
                }
            }
        },
        assetCandidates=[
            {
                "src": "resources/base/media/ux_golden_asset_time_beige.svg",
                "description": "时间图标",
            },
            {
                "src": "resources/base/media/ux_golden_asset_icon_id.svg",
                "description": "位置图标",
            },
        ],
    )
    registry = get_cardplan_registry()
    selected = scope_template_ids(
        AdvancedScopeBrief(
            themeId="meeting-paper-neutral",
            advancedComponentIds=("ScheduleOverview",),
        ),
        registry,
        task_spec,
    )

    assert selected == ("ScheduleOverview@1",)


@pytest.mark.asyncio
async def test_scope_planner_trims_only_when_selected_components_have_no_common_layout():
    task_spec = TaskSpec(
        userQuery="展示会议日期和地点",
        size="2x2",
        eventCandidates=[EventAction(id="event.enter.meeting", call="clickToApi", args={})],
        dataModelSchema={
            "GetCalendarEvents": {
                "events": [
                    {
                        "title": _sample_field("UI需求评审会"),
                        "dtStart": _sample_field("09:30"),
                        "eventLocation": _sample_field("A区会议室"),
                        "startDate": _sample_field("08-27"),
                    }
                ],
                "updatedAt": _sample_field("2026-08-11 09:00"),
            },
            "ViewWeather": {
                "districtName": _sample_field("深圳"),
                "temperatureText": _sample_field("38°"),
                "condition": _sample_field("晴"),
                "airQuality": _sample_field("空气优"),
                "temperatureRangeText": _sample_field("26° / 16°"),
                "updatedAt": _sample_field("2026-08-11 09:00"),
            },
        },
        assetCandidates=[],
    )
    task_spec = apply_content_selectors(task_spec, {"GetCalendarEvents", "ViewWeather"})

    async def generate_json(_messages, _phase):
        return {
            "scopeVersion": "advanced-scope-brief/1",
            "themeId": "meeting-paper-neutral",
            "advancedComponentIds": [
                "ScheduleOverview",
                "DateOverview",
                "LocationOverview",
            ],
        }

    scope = await plan_advanced_scope_with_llm(
        task_spec,
        extract_data_shape(task_spec),
        generate_json,
        get_cardplan_registry(),
    )

    assert scope.advanced_component_ids == ("ScheduleOverview", "DateOverview")


@pytest.mark.asyncio
async def test_new_mixed_entry_uses_new_phases_and_lowers_layout_to_standard_a2ui():
    model_client = UxMixedModelClient()

    output = await AdvancedComponentPipeline().generate_mixed(
        _weather_scope_task(),
        model_client,
        _weather_card_spec(),
    )

    assert model_client.phases == ["advanced-component-scope", "advanced-mixed-body"]
    mixed_user_prompt = model_client.prompts["advanced-mixed-body"][1]["content"]
    assert '"深圳"' in mixed_user_prompt
    assert '"resources/base/media/weather.svg"' in mixed_user_prompt
    assert '"resources/base/media/sun_max.svg"' in mixed_user_prompt
    assert 'requiredLocalTemplateGroups=[["WeatherOverview@1"]]' in mixed_user_prompt
    assert "directBusinessComponents=[]" in mixed_user_prompt
    assert output.ui_brief == AdvancedScopeBrief(
        themeId="family-weather-care-blue",
        advancedComponentIds=("WeatherOverview",),
    )
    assert output.route == "hybrid-template"
    assert output.confidence_bypassed is True
    assert output.whole_card_candidates == []
    assert "SingleFocusLayout" in output.raw_output
    assert "Layout" not in output.effective_output
    assert "Template" not in output.compiled_a2ui
    assert "Layout" not in output.compiled_a2ui
    assert '"borderRadius":20' in output.effective_output
    assert '"padding":12' in output.effective_output


@pytest.mark.asyncio
@pytest.mark.parametrize("size", ["2x2", "2x4"])
async def test_weather_provider_expansion_preserves_single_business_hierarchy(size: str):
    task_spec = _weather_scope_task().model_copy(update={"size": size})
    output = await AdvancedComponentPipeline().generate_mixed(
        task_spec,
        UxMixedModelClient(),
        _weather_card_spec(size),
    )
    effective = output.effective_output

    assert "WeatherOverview" not in effective
    assert "Template" not in effective
    assert effective.index(
        'Text("${data.ViewWeather.location.districtName}"'
    ) < effective.index(
        'Image("resources/base/media/weather.svg"'
    )
    assert '"fontSize":38' in effective
    assert effective.count('"fontSize":14') >= 1
    assert (
        "{{ ${/data/ViewWeather/current/condition} + '｜' + "
        "${/data/ViewWeather/current/airQuality} }}"
    ) in effective
    assert '"fontSize":12' in effective
    if size == "2x4":
        assert (
            '"height":"matchParent","itemMargin":4,"justifyContent":"spaceBetween"'
            in effective
        )
    for path in (
        "${data.ViewWeather.location.districtName}",
        "${data.ViewWeather.current.temperatureText}",
        "${data.ViewWeather.daily.0.temperatureRangeText}",
    ):
        assert effective.count(path) == 1

    messages = [json.loads(line) for line in output.compiled_a2ui.splitlines()]
    components = messages[1]["updateComponents"]["components"]
    data_model = messages[2]["updateDataModel"]["value"]
    assert data_model["data"]["ViewWeather"]["current"]["temperatureText"] == "38°"
    assert "_advancedSelectors" not in data_model["data"]
    text_by_content = {
        component.get("content"): component
        for component in components
        if component.get("component") == "Text"
    }
    expected_bindings = {
        "{{ ${/data/ViewWeather/location/districtName} }}",
        "{{ ${/data/ViewWeather/current/temperatureText} }}",
        "{{ ${/data/ViewWeather/daily/0/temperatureRangeText} }}",
        (
            "{{ ${/data/ViewWeather/current/condition} + '｜' + "
            "${/data/ViewWeather/current/airQuality} }}"
        ),
    }
    assert expected_bindings.issubset(text_by_content)
    city_id = text_by_content["{{ ${/data/ViewWeather/location/districtName} }}"]["id"]
    condition_icon = next(
        component for component in components if component.get("component") == "Image"
    )
    if size == "2x2":
        title_row = next(
            component
            for component in components
            if component.get("component") == "Row"
            and component.get("children") == [city_id, condition_icon["id"]]
        )
        assert title_row["styles"]["width"] == "matchParent"
        assert title_row["styles"]["justifyContent"] == "spaceBetween"
        assert title_row["styles"]["alignItems"] == "top"
        assert condition_icon["styles"]["width"] == 20
        weather_column = next(
            component
            for component in components
            if component.get("component") == "Column"
            and title_row["id"] in component.get("children", [])
        )
        assert weather_column["styles"]["justifyContent"] == "spaceBetween"
    else:
        title_row = next(
            component
            for component in components
            if component.get("component") == "Row"
            and component.get("children") == [city_id, condition_icon["id"]]
        )
        assert title_row["styles"]["width"] == "matchParent"
        assert title_row["styles"]["justifyContent"] == "spaceBetween"
        assert title_row["styles"]["alignItems"] == "top"
    for component in components:
        if component.get("component") not in {"Row", "Column", "Stack"}:
            continue
        styles = component.get("styles", {})
        assert styles.get("width") != "100%"
        assert styles.get("height") != "100%"
    coverage = output.invocation["weatherFieldCoverage"]
    assert coverage["renderable"] == [
        "city",
        "temperature",
        "condition",
        "airQuality",
        "temperatureRange",
    ]
    assert coverage["visible"] == coverage["renderable"]
    assert coverage["visibleCount"] == 5


@pytest.mark.asyncio
async def test_weather_provider_template_uses_condition_icon_selected_by_second_step():
    task_spec = _weather_scope_task().model_copy(update={"assetCandidates": []})
    body = (
        'SingleFocusLayout(Template("WeatherOverview@1","heroIcon",'
        '{"conditionIcon":"resources/base/media/sun_max.svg"}));'
    )
    card_spec = _weather_card_spec("2x2")

    output = await AdvancedComponentPipeline().generate_mixed(
        task_spec,
        UxMixedModelClient(body),
        card_spec,
    )

    assert 'Image("resources/base/media/sun_max.svg"' in output.effective_output
    assert '"fillColor":"#FFFFC300"' in output.effective_output
    assert output.trusted_internal_asset_sources == (
        "resources/base/media/sun_max.svg",
    )
    assert output.effective_output.index(
        'Text("${data.ViewWeather.location.districtName}"'
    ) < output.effective_output.index('Image("resources/base/media/sun_max.svg"')

    artifact = WidgetGenerationService()._build_artifact(
        output.compiled_a2ui,
        card_spec,
        task_spec.model_dump(mode="json"),
        [],
        [],
        [],
        [],
        "a2ui-form-rom6.0-v1",
        "v0.9",
        "app-11.7.5.205_rom-6.0",
        trusted_internal_asset_sources=output.trusted_internal_asset_sources,
    )
    errors = ArtifactValidator().validate(
        artifact,
        {"id": "a2ui-form-rom6.0-v1"},
    )
    assert not any("EFFECTIVE_ASSET_NOT_ALLOWED" in error for error in errors)
    assert artifact.effectiveCapabilities["asset"] == [
        "resources/base/media/sun_max.svg"
    ]
    assert artifact.generationPlan.candidateAssetIds == []


@pytest.mark.asyncio
async def test_weather_non_sunny_condition_does_not_tint_multicolor_icon():
    task_spec = _weather_scope_task_with_values(
        city="深圳",
        temperature="26°",
        condition="多云",
        air_quality="空气优",
        temperature_range="31° / 24°",
    )
    body = (
        'SingleFocusLayout(Template("WeatherOverview@1","heroIcon",'
        '{"conditionIcon":"resources/base/media/weather.svg"}));'
    )

    output = await AdvancedComponentPipeline().generate_mixed(
        task_spec,
        UxMixedModelClient(body),
        _weather_card_spec(),
    )

    assert 'Image("resources/base/media/weather.svg"' in output.effective_output
    assert '"fillColor"' not in output.effective_output


@pytest.mark.asyncio
async def test_weather_sun_semantic_icon_stays_yellow_for_cloudy_condition():
    task_spec = _weather_scope_task_with_values(
        city="深圳",
        temperature="26°",
        condition="多云",
        air_quality="空气优",
        temperature_range="31° / 24°",
    )
    body = (
        'SingleFocusLayout(Template("WeatherOverview@1","heroIcon",'
        '{"conditionIcon":"resources/base/media/sun_max.svg"}));'
    )

    output = await AdvancedComponentPipeline().generate_mixed(
        task_spec,
        UxMixedModelClient(body),
        _weather_card_spec(),
    )

    assert 'Image("resources/base/media/sun_max.svg", "icon", {' in output.effective_output
    assert '"fillColor":"#FFFFC300"' in output.effective_output


@pytest.mark.asyncio
async def test_weather_multicolor_cloud_artwork_is_not_monochrome_tinted():
    task_spec = _weather_scope_task_with_values(
        city="上海",
        temperature="26°",
        condition="多云",
        air_quality="空气优",
        temperature_range="31° / 24°",
        asset_candidates=[
            {
                "src": "resources/base/media/icon_weather1.svg",
                "description": "多云渐变天气图标",
                "sceneTags": ["weather", "cloud"],
            }
        ],
    )
    body = (
        'SingleFocusLayout(Template("WeatherOverview@1","heroIcon",'
        '{"conditionIcon":"resources/base/media/icon_weather1.svg"}));'
    )

    output = await AdvancedComponentPipeline().generate_mixed(
        task_spec,
        UxMixedModelClient(body),
        _weather_card_spec(),
    )

    assert 'Image("resources/base/media/icon_weather1.svg", "icon", {' in output.effective_output
    assert '"fillColor"' not in output.effective_output


@pytest.mark.asyncio
async def test_weather_rain_icon_is_white_on_strong_background():
    task_spec = _weather_scope_task_with_values(
        city="深圳",
        temperature="26°",
        condition="小雨",
        air_quality="空气优",
        temperature_range="31° / 24°",
        asset_candidates=[
            {
                "src": "resources/base/media/drop.svg",
                "description": "雨滴图标",
                "sceneTags": ["weather", "water"],
            }
        ],
    )
    body = (
        'SingleFocusLayout(Template("WeatherOverview@1","heroIcon",'
        '{"conditionIcon":"resources/base/media/drop.svg"}));'
    )

    output = await AdvancedComponentPipeline().generate_mixed(
        task_spec,
        UxMixedModelClient(body),
        _weather_card_spec(),
    )

    assert 'Image("resources/base/media/drop.svg", "icon", {' in output.effective_output
    assert '"fillColor":"#FFFFFFFF"' in output.effective_output


@pytest.mark.asyncio
async def test_weather_batch_evidence_keeps_projected_task_and_precompile_dsl(monkeypatch):
    monkeypatch.setattr(get_settings(), "enable_widget_batch_recording", True)

    output = await AdvancedComponentPipeline().generate_mixed(
        _weather_scope_task(),
        UxMixedModelClient(),
        _weather_card_spec(),
    )

    evidence = output.invocation["batchEvidence"]
    projected = evidence["projectedTaskSpec"]["dataModelSchema"]["data"]
    assert set(projected["WeatherOverview"]) == {
        "city",
        "temperature",
        "condition",
        "airQuality",
        "temperatureRange",
    }
    assert set(projected["ViewWeather"]) == {"location", "current", "daily"}
    assert evidence["precompileDsl"].startswith("SingleFocusLayout(")
    assert 'Template("WeatherOverview@1"' in evidence["precompileDsl"]


@pytest.mark.asyncio
async def test_weather_details_action_lowers_to_whole_card_click():
    task_spec = _weather_scope_task().model_copy(
        update={
            "eventCandidates": [
                EventAction(
                    id="event.open.weather",
                    displayLabel="天气详情",
                    call="clickToIntent",
                    args={},
                )
            ],
            "assetCandidates": [
                *_weather_scope_task().assetCandidates,
                {
                    "src": "resources/base/media/open.svg",
                    "description": "打开天气详情图标",
                },
            ],
        }
    )
    body = (
        'SingleFocusLayout(Template("WeatherOverview@1","heroIcon",'
        '{"conditionIcon":"resources/base/media/weather.svg"}),'
        'IconAction({"actionId":"event.open.weather",'
        '"icon":"resources/base/media/open.svg"}));'
    )
    output = await AdvancedComponentPipeline().generate_mixed(
        task_spec,
        UxMixedModelClient(body),
        _weather_card_spec(),
    )

    assert '"onClick":[{"call":"clickToIntent","args":{}}]' in output.effective_output
    assert "天气详情" not in output.effective_output
    assert "resources/base/media/open.svg" not in output.effective_output
    assert '"alignContent":"bottomEnd"' not in output.effective_output
    for path in (
        "${data.ViewWeather.location.districtName}",
        "${data.ViewWeather.current.temperatureText}",
        "${data.ViewWeather.daily.0.temperatureRangeText}",
    ):
        assert output.effective_output.count(path) == 1
    assert (
        "{{ ${/data/ViewWeather/current/condition} + '｜' + "
        "${/data/ViewWeather/current/airQuality} }}"
    ) in output.effective_output
    assert '"width":20,"height":20' in output.effective_output
    messages = [json.loads(line) for line in output.compiled_a2ui.splitlines()]
    components = messages[1]["updateComponents"]["components"]
    root = next(component for component in components if component["id"] == "root")
    assert root["onClick"] == [{"call": "clickToIntent", "args": {}}]
    assert not any(component.get("content") == "天气详情" for component in components)
    assert all(
        component.get("styles", {}).get("fontColor") == "#FFFFFFFF"
        for component in components
        if component.get("component") == "Text"
    )


@pytest.mark.asyncio
async def test_weather_2x2_normalizes_wrapped_config_and_empty_icon_action():
    task_spec = _weather_scope_task().model_copy(
        update={
            "eventCandidates": [
                EventAction(
                    id="event.open.weather",
                    displayLabel="天气详情",
                    call="clickToIntent",
                    args={},
                )
            ]
        }
    )
    body = (
        'SingleFocusLayout([{"contentAlign":"centerStart"}],'
        'Template("WeatherOverview@1","heroIcon",'
        '{"conditionIcon":"resources/base/media/weather.svg"}),'
        'IconAction({"actionId":"event.open.weather","icon":""}));'
    )

    output = await AdvancedComponentPipeline().generate_mixed(
        task_spec,
        UxMixedModelClient(body),
        _weather_card_spec(),
    )

    assert '"onClick":[{"call":"clickToIntent","args":{}}]' in output.effective_output
    assert "天气详情" not in output.effective_output
    assert "IconAction" not in output.effective_output


def test_audio_stack_theme_maps_alignment_to_column_axis():
    capability_ids = {"GetEarphoneInfo"}
    task_spec = TaskSpec(
        userQuery="蓝牙耳机电量",
        size="2x2",
        dataModelSchema={
            "GetEarphoneInfo": {
                "isConnected": {"type": "boolean", "sampleValue": True},
                "earphoneName": _sample_field("FreeBuds Pro 3"),
                "leftBatteryLevel": {"type": "number", "sampleValue": 76},
                "rightBatteryLevel": {"type": "number", "sampleValue": 74},
                "batteryLevel": {"type": "number", "sampleValue": 80},
            }
        },
        assetCandidates=[],
    )
    component_ids = ("BluetoothDeviceOverview",)
    projected, card_spec, registry = prepare_provider_scope_projection(
        task_spec,
        capability_ids,
        component_ids,
    )
    projection = build_ux_mixed_prompt(
        task_spec=projected,
        card_spec=card_spec,
        scope=AdvancedScopeBrief(
            themeId="audio-product-neutral-violet",
            advancedComponentIds=("BluetoothDeviceOverview",),
        ),
        registry=registry,
    )
    source = (
        'SingleFocusLayout(BluetoothDeviceOverview('
        '{"variant":"earbuds","role":"hero"}));'
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

    assert (
        '"height":20,"itemMargin":4,"justifyContent":"spaceBetween",'
        '"alignItems":"top"'
    ) in compiled.effective_output
    assert "topStart" not in compiled.effective_output


def _weather_schedule_task(size: str, *, with_action: bool) -> TaskSpec:
    events = (
        [
            EventAction(
                id="event.viewCalendarEvent",
                displayLabel="查看日程",
                call="clickToIntent",
                args={},
            )
        ]
        if with_action
        else []
    )
    return TaskSpec(
        userQuery="天气和下一项日程",
        size=size,
        eventCandidates=events,
        dataModelSchema={
            "ViewWeather": dict(
                _weather_scope_task().dataModelSchema["data"]["ViewWeather"]
            ),
            "GetCalendarEvents": {
                "events": [
                    {
                        "title": _sample_field("产品评审"),
                        "dtStart": _sample_field("09:30"),
                        "dtEnd": _sample_field("10:30"),
                        "eventLocation": _sample_field("A3 会议室"),
                    }
                ]
            },
        },
        assetCandidates=[
            *_weather_scope_task().assetCandidates,
            {
                "src": "resources/base/media/calendar.svg",
                "description": "日程操作图标",
            },
        ],
    )


def _compile_weather_schedule(
    size: str,
    source: str,
    *,
    with_action: bool,
):
    capability_ids = {"ViewWeather", "GetCalendarEvents"}
    task_spec = _weather_schedule_task(size, with_action=with_action)
    scope = AdvancedScopeBrief(
        themeId="meeting-paper-neutral",
        advancedComponentIds=("WeatherOverview", "ScheduleOverview"),
    )
    projected, card_spec, registry = prepare_provider_scope_projection(
        task_spec,
        capability_ids,
        scope.advanced_component_ids,
        force_template=True,
    )
    projection = build_ux_mixed_prompt(
        task_spec=projected,
        card_spec=card_spec,
        scope=scope,
        registry=registry,
    )
    return compile_ux_layout_card(
        source,
        task_spec=projected,
        contract=projection.contract,
        protocol_profile=A2UIProtocolRegistry.read_design_protocol_profile(
            TERSE_DSL_NESTED2_PROFILE_ID
        ),
        registry=registry,
        card_spec=card_spec,
        enable_data_bindings=True,
    )


@pytest.mark.parametrize("with_action", [False, True])
def test_weather_2x2_multi_business_keeps_weather_as_primary(with_action: bool):
    if with_action:
        source = (
            'HeroSupportActionLayout({"heroRatio":"wide"},'
            'Template("WeatherOverview@1","compactIcon",'
            '{"conditionIcon":"resources/base/media/weather.svg"}),'
            'Template("ScheduleOverview@1","meetingCompact",{}),'
            'IconAction({"actionId":"event.viewCalendarEvent",'
            '"icon":"resources/base/media/calendar.svg"}));'
        )
    else:
        source = (
            'HeroSupportLayout({"ratio":"heroWide","direction":"vertical"},'
            'Template("WeatherOverview@1","compactIcon",'
            '{"conditionIcon":"resources/base/media/weather.svg"}),'
            'Template("ScheduleOverview@1","meetingCompact",{}));'
        )

    compiled = _compile_weather_schedule("2x2", source, with_action=with_action)

    assert "WeatherOverview(" not in compiled.effective_output
    assert compiled.effective_output.index(
        'Text("${data.ViewWeather.location.districtName}"'
    ) < compiled.effective_output.index('Image("resources/base/media/weather.svg"')
    assert compiled.effective_output.count("${data.GetCalendarEvents.events.0.title}") == 1
    assert "${data.ScheduleOverview.timeText}" in compiled.effective_output
    if with_action:
        assert '"alignContent":"bottomEnd"' in compiled.effective_output


@pytest.mark.parametrize(
    "source",
    [
        (
            'HeroSupportLayout({"ratio":"heroWide","direction":"horizontal"},'
            'Template("WeatherOverview@1","heroIcon",'
            '{"conditionIcon":"resources/base/media/weather.svg"}),'
            'Template("ScheduleOverview@1","meetingExpanded",{}));'
        ),
        (
            'HeroSupportLayout({"ratio":"heroWide","direction":"horizontal"},'
            'Template("ScheduleOverview@1","nextEventLocation",{}),'
            'Template("WeatherOverview@1","compactIcon",'
            '{"conditionIcon":"resources/base/media/weather.svg"}));'
        ),
    ],
)
def test_weather_2x4_multi_business_supports_primary_and_support_roles(source: str):
    compiled = _compile_weather_schedule("2x4", source, with_action=False)

    assert "WeatherOverview(" not in compiled.effective_output
    for path in (
        "${data.ViewWeather.location.districtName}",
        "${data.ViewWeather.current.temperatureText}",
        "${data.ViewWeather.daily.0.temperatureRangeText}",
    ):
        assert compiled.effective_output.count(path) == 1
    assert (
        "{{ ${/data/ViewWeather/current/condition} + '｜' + "
        "${/data/ViewWeather/current/airQuality} }}"
    ) in compiled.effective_output


def test_weather_2x4_hero_support_action_keeps_action_in_its_own_region():
    source = (
        'HeroSupportActionLayout({"heroRatio":"wide"},'
        'Template("WeatherOverview@1","heroIcon",'
        '{"conditionIcon":"resources/base/media/weather.svg"}),'
        'Template("ScheduleOverview@1","meetingExpanded",{}),'
        'PillAction({"actionId":"event.viewCalendarEvent",'
        '"icon":"resources/base/media/calendar.svg"}));'
    )

    compiled = _compile_weather_schedule("2x4", source, with_action=True)

    assert '"justifyContent":"spaceBetween"' in compiled.effective_output
    assert "查看日程" in compiled.effective_output
    assert compiled.effective_output.count("${data.GetCalendarEvents.events.0.title}") == 1


def test_weather_and_phone_battery_use_hero_support_action_roles():
    capability_ids = {"ViewWeather", "GetPhoneBatteryInfo"}
    weather = _weather_scope_task()
    task_spec = TaskSpec(
        userQuery="显示天气、手机电量并一键导航回家",
        size="2x2",
        eventCandidates=[
            EventAction(
                id="event.startNavigate",
                displayLabel="开始导航",
                call="clickToIntent",
                args={"intentName": "StartNavigate"},
            )
        ],
        dataModelSchema={
            "ViewWeather": dict(weather.dataModelSchema["data"]["ViewWeather"]),
            "GetPhoneBatteryInfo": {
                "batterySOC": {"type": "number", "sampleValue": 68},
                "batterySOCText": _sample_field("68%"),
                "batteryCapacityLevelDesc": _sample_field("正常电量"),
                "chargingStatusDesc": _sample_field("充电中"),
            },
        },
        assetCandidates=[
            *weather.assetCandidates,
            {
                "src": "resources/base/media/navigation.svg",
                "description": "一键导航回家图标",
                "sceneTags": ["location", "navigation"],
            },
        ],
    )
    scope = AdvancedScopeBrief(
        themeId="family-weather-care-blue",
        advancedComponentIds=("WeatherOverview", "BatteryOverview"),
    )
    projected, card_spec, registry = prepare_provider_scope_projection(
        task_spec,
        capability_ids,
        scope.advanced_component_ids,
        force_template=True,
    )
    projection = build_ux_mixed_prompt(
        task_spec=projected,
        card_spec=card_spec,
        scope=scope,
        registry=registry,
    )
    compiled = compile_ux_layout_card(
        'HeroSupportActionLayout(Template("WeatherOverview@1","compactIcon",'
        '{"conditionIcon":"resources/base/media/weather.svg"}),'
        'Template("BatteryOverview@1","chargingWeather",{}),'
        'IconAction({"actionId":"event.startNavigate",'
        '"icon":"resources/base/media/navigation.svg"}));',
        task_spec=projected,
        contract=projection.contract,
        protocol_profile=A2UIProtocolRegistry.read_design_protocol_profile(
            TERSE_DSL_NESTED2_PROFILE_ID
        ),
        registry=registry,
        card_spec=card_spec,
        enable_data_bindings=True,
    )

    assert "WeatherOverview(" not in compiled.effective_output
    assert "BatteryOverview(" not in compiled.effective_output
    assert "${data.GetPhoneBatteryInfo.batterySOCText}" in compiled.effective_output
    assert compiled.stats.action_used_ids == ("event.startNavigate",)
    assert '"fontSize":30' in compiled.effective_output
    assert '"height":36' in compiled.effective_output
    assert '"type":"ring"' not in compiled.effective_output


def test_weather_phone_and_earphone_three_business_scope_is_rejected():
    capability_ids = {"ViewWeather", "GetPhoneBatteryInfo", "GetEarphoneInfo"}
    task_spec = TaskSpec(
        userQuery="天气、手机电量和耳机电量",
        size="2x4",
        dataModelSchema={
            "ViewWeather": dict(
                _weather_scope_task().dataModelSchema["data"]["ViewWeather"]
            ),
            "GetPhoneBatteryInfo": {
                "batterySOC": {"type": "number", "sampleValue": 68},
                "batterySOCText": _sample_field("68%"),
                "batteryCapacityLevelDesc": _sample_field("电量正常"),
                "chargingStatusDesc": _sample_field("充电中"),
            },
            "GetEarphoneInfo": {
                "isConnected": {"type": "boolean", "sampleValue": True},
                "earphoneName": _sample_field("FreeBuds Pro 3"),
                "leftBatteryLevel": {"type": "number", "sampleValue": 76},
                "rightBatteryLevel": {"type": "number", "sampleValue": 74},
                "batteryLevel": {"type": "number", "sampleValue": 80},
            },
        },
        assetCandidates=[
            *_weather_scope_task().assetCandidates,
            {
                "src": "resources/base/media/battery.svg",
                "description": "手机电池图标",
                "sceneTags": ["battery", "power"],
            },
        ],
    )
    selected = apply_content_selectors(task_spec, capability_ids)
    scope = AdvancedScopeBrief(
        themeId="meeting-paper-neutral",
        advancedComponentIds=(
            "WeatherOverview",
            "BatteryOverview",
            "BluetoothDeviceOverview",
        ),
    )
    projected = project_content_component_facts(
        selected,
        capability_ids,
        scope.advanced_component_ids,
    )
    with pytest.raises(ValueError, match="no compatible UX layout"):
        build_ux_mixed_prompt(
            task_spec=projected,
            card_spec={
                "suggestSize": "2x4",
                "dataBindings": [
                    {"capabilityId": capability_id}
                    for capability_id in capability_ids
                ],
            },
            scope=scope,
            registry=get_cardplan_registry(),
        )


def test_ux_mixed_contract_rejects_standard_components_replacing_selected_business_component():
    projected, card_spec = _projected_weather_template_task()
    scope = AdvancedScopeBrief(
        themeId="family-weather-care-blue",
        advancedComponentIds=("WeatherOverview",),
    )
    projection = build_ux_mixed_prompt(
        task_spec=projected,
        card_spec=card_spec,
        scope=scope,
        registry=get_cardplan_registry(),
    )

    with pytest.raises(
        TerseDslNested2ConversionError,
        match="requires one trusted Template",
    ):
        compile_ux_layout_card(
            'SingleFocusLayout(Text("晴", "body"));',
            task_spec=projected,
            contract=projection.contract,
            protocol_profile=A2UIProtocolRegistry.read_design_protocol_profile(
                TERSE_DSL_NESTED2_PROFILE_ID
            ),
            registry=get_cardplan_registry(),
            card_spec=card_spec,
        )


def test_ux_mixed_contract_rejects_unknown_weather_variant():
    projected, card_spec = _projected_weather_template_task()
    scope = AdvancedScopeBrief(
        themeId="family-weather-care-blue",
        advancedComponentIds=("WeatherOverview",),
    )
    projection = build_ux_mixed_prompt(
        task_spec=projected,
        card_spec=card_spec,
        scope=scope,
        registry=get_cardplan_registry(),
    )
    source = _WEATHER_TERSE_BODY.replace('"heroIcon"', '"forecastItem"')

    with pytest.raises(
        TerseDslNested2ConversionError,
        match="Template variant does not match",
    ):
        compile_ux_layout_card(
            source,
            task_spec=projected,
            contract=projection.contract,
            protocol_profile=A2UIProtocolRegistry.read_design_protocol_profile(
                TERSE_DSL_NESTED2_PROFILE_ID
            ),
            registry=get_cardplan_registry(),
            card_spec=card_spec,
        )


@pytest.mark.parametrize(
    ("source", "message"),
    [
        (
            'SingleFocusLayout(Template("WeatherOverview@1","heroIcon",{}));',
            "Template params are invalid",
        ),
        (
            'SingleFocusLayout(Template("WeatherOverview@1","heroIcon",'
            '{"conditionIcon":"resources/base/media/not-approved.svg"}));',
            "Template asset is not approved",
        ),
    ],
)
def test_weather_overview_requires_approved_second_step_icon(source: str, message: str):
    projected, card_spec = _projected_weather_template_task()
    scope = AdvancedScopeBrief(
        themeId="family-weather-care-blue",
        advancedComponentIds=("WeatherOverview",),
    )
    projection = build_ux_mixed_prompt(
        task_spec=projected,
        card_spec=card_spec,
        scope=scope,
        registry=get_cardplan_registry(),
    )

    with pytest.raises(TerseDslNested2ConversionError, match=message):
        compile_ux_layout_card(
            source,
            task_spec=projected,
            contract=projection.contract,
            protocol_profile=A2UIProtocolRegistry.read_design_protocol_profile(
                TERSE_DSL_NESTED2_PROFILE_ID
            ),
            registry=get_cardplan_registry(),
            card_spec=card_spec,
        )


def test_ux_mixed_contract_uses_battery_template_and_approved_action():
    task_spec = TaskSpec(
        userQuery="展示低电状态并开启省电模式",
        size="2x2",
        eventCandidates=[
            EventAction(
                id="event.setPowerSavingMode",
                displayLabel="省电模式",
                call="clickToIntent",
                args={},
            )
        ],
        dataModelSchema={
            "GetPhoneBatteryInfo": {
                "batterySOC": {"type": "number", "sampleValue": 18},
                "batterySOCText": {"type": "string", "sampleValue": "18%"},
                "batteryCapacityLevelDesc": {
                    "type": "string",
                    "sampleValue": "手机电量低于20%，建议开启省电模式",
                },
                "chargingStatusDesc": {"type": "string", "sampleValue": "未充电"},
            }
        },
        assetCandidates=[
            {
                "src": "resources/base/media/battery.svg",
                "description": "充电/闪电图标，适用场景：低电模式",
            },
            {
                "src": "resources/base/media/save-power.svg",
                "description": "省电模式图标",
            },
        ],
    )
    projected, card_spec, registry = prepare_provider_scope_projection(
        task_spec,
        {"GetPhoneBatteryInfo"},
        ("BatteryOverview",),
        force_template=True,
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
    source = (
        'HeroActionLayout({"actionPlacement":"bottom"}, '
        'Template("BatteryOverview@1","low",{}),'
        'IconAction({"actionId":"event.setPowerSavingMode",'
        '"icon":"resources/base/media/save-power.svg"}));'
    )

    compiled = compile_ux_layout_card(
        source,
        task_spec=projected,
        contract=projection.contract,
        protocol_profile=A2UIProtocolRegistry.read_design_protocol_profile(
            TERSE_DSL_NESTED2_PROFILE_ID
        ),
        registry=registry,
        card_spec=card_spec,
        enable_data_bindings=True,
    )

    assert compiled.stats.template_used_ids == ("BatteryOverview@1",)
    assert "BatteryOverview(" not in compiled.effective_output
    assert "Template" not in compiled.a2ui


def test_ux_mixed_prompt_counts_action_outside_business_children():
    task_spec = _metric_task_spec().model_copy(
        update={
            "userQuery": "显示手机电量",
            "dataModelSchema": {
                "GetPhoneBatteryInfo": {
                    "batterySOC": {"type": "number", "sampleValue": 18},
                    "batterySOCText": {"type": "string", "sampleValue": "18%"},
                    "batteryCapacityLevelDesc": {
                        "type": "string",
                        "sampleValue": "电量较低",
                    },
                    "chargingStatusDesc": {"type": "string", "sampleValue": "未充电"},
                }
            },
        }
    )
    scope = AdvancedScopeBrief(
        themeId="device-clean-blue-teal",
        advancedComponentIds=("BatteryOverview",),
    )
    projected, card_spec, registry = prepare_provider_scope_projection(
        task_spec,
        {"GetPhoneBatteryInfo"},
        scope.advanced_component_ids,
    )
    projection = build_ux_mixed_prompt(
        task_spec=projected,
        card_spec=card_spec,
        scope=scope,
        registry=registry,
    )
    system_prompt = projection.messages[0]["content"]

    assert "businessChildren=" in system_prompt
    assert "Action 必须是连续末尾直接 children" in system_prompt
    assert "configSchema=" in system_prompt
    assert "禁止放进 Column/Row/Stack/List/Template" in system_prompt


def test_action_matrix_layout_requires_two_approved_controls_in_scope_and_prompt():
    registry = get_cardplan_registry()
    scope = AdvancedScopeBrief(
        themeId="meeting-paper-neutral",
        advancedComponentIds=("SettingsOverview",),
    )
    one_action = _metric_task_spec()
    two_actions = one_action.model_copy(
        update={
            "eventCandidates": [
                EventAction(id="event.first", call="clickToApi", args={}),
                EventAction(id="event.second", call="clickToApi", args={}),
            ]
        }
    )

    assert "ActionMatrixLayout" not in resolve_scope_layout_ids(scope, one_action, registry)
    assert "ActionMatrixLayout" in resolve_scope_layout_ids(scope, two_actions, registry)

    projection = build_ux_mixed_prompt(
        task_spec=two_actions,
        card_spec={"suggestSize": "2x2"},
        scope=scope,
        registry=registry,
    )

    assert projection.contract.content_action_ids == ("event.first", "event.second")
    assert "actions=2..2" in projection.messages[0]["content"]


def test_ux_mixed_prompt_exposes_weather_as_provider_template():
    task_spec, card_spec = _projected_weather_template_task()
    task_spec = task_spec.model_copy(
        update={
            "userQuery": "展示雨天天气并支持打车",
            "eventCandidates": [
                EventAction(id="event.startNavigate", call="clickToApi", args={})
            ],
            "assetCandidates": [
                *task_spec.assetCandidates,
                {
                    "src": "resources/base/media/car.svg",
                    "description": "汽车打车图标",
                },
            ],
        }
    )
    projection = build_ux_mixed_prompt(
        task_spec=task_spec,
        card_spec=card_spec,
        scope=AdvancedScopeBrief(
            themeId="rainy-commute-gray-blue",
            advancedComponentIds=("WeatherOverview",),
        ),
        registry=get_cardplan_registry(),
    )
    system_prompt = projection.messages[0]["content"]

    assert 'Template("WeatherOverview@1","heroIcon|compactIcon",' in system_prompt
    assert '"conditionIcon":"<trustedAssetSources item>"})' in system_prompt
    assert "不得输出旧 `WeatherOverview(...)` 构造器" in system_prompt


def test_ux_mixed_prompt_exposes_heart_rate_as_provider_template():
    task_spec = TaskSpec(
        userQuery="展示运动平均心率和更新时间",
        size="2x2",
        dataModelSchema={
            "data": {
                "healthPoc": {
                    "exerciseHeartRateAvg": {
                        "type": "integer",
                        "description": "可信运动平均心率",
                        "sampleValue": 128,
                    },
                    "updatedAt": _sample_field("今天 18:20"),
                }
            }
        },
        assetCandidates=[
            {
                "src": "resources/base/media/heart.svg",
                "description": "心率图标",
                "sceneTags": ["heart", "heart-rate", "pulse"],
            }
        ],
    )
    card_spec = {
        "suggestSize": "2x2",
        "dataBindings": [
            {
                "capabilityId": "GetHealthAndSportSummary",
                "writeResultTo": "/data/healthPoc",
            }
        ],
    }
    projection = build_ux_mixed_prompt(
        task_spec=task_spec,
        card_spec=card_spec,
        scope=AdvancedScopeBrief(
            themeId="meeting-paper-neutral",
            advancedComponentIds=("HeartRateOverview",),
        ),
        registry=get_cardplan_registry(),
    )
    system_prompt = projection.messages[0]["content"]

    assert 'Template("HeartRateOverview@1","hero|heroUpdated|' in system_prompt
    assert '"sourceIcon":"<trustedAssetSources item>"' in system_prompt
    assert "不得输出旧 HeartRateOverview(...) 构造器" in system_prompt
    assert "Template('HeartRateOverview@1', 'heroUpdated', params)" in system_prompt
    assert "Template('HeartRateOverview@1', 'hero', params)" not in system_prompt


@pytest.mark.asyncio
async def test_new_mixed_entry_rejects_standard_container_as_content_root():
    model_client = UxMixedModelClient('Column("section", Text("晴", "body"));')

    with pytest.raises(ValueError, match="root must be one Layout Component"):
        await AdvancedComponentPipeline().generate_mixed(
            _weather_scope_task(),
            model_client,
            _weather_card_spec(),
        )


@pytest.mark.asyncio
async def test_new_mixed_entry_retries_only_second_layer_after_contract_rejection():
    model_client = RetryingUxMixedModelClient(
        [
            'SingleFocusLayout(Text("模型新增标签", "body"));',
            _WEATHER_TERSE_BODY,
        ]
    )

    output = await AdvancedComponentPipeline().generate_mixed(
        _weather_scope_task(),
        model_client,
        _weather_card_spec(),
    )

    assert model_client.phases == [
        "advanced-component-scope",
        "advanced-mixed-body",
        "advanced-mixed-body-repair",
    ]
    retry_prompt = model_client.prompts["advanced-mixed-body-repair"]
    assert retry_prompt[-2]["role"] == "assistant"
    assert "模型新增标签" in retry_prompt[-2]["content"]
    assert "trustedStringLiterals" in retry_prompt[-1]["content"]
    assert output.invocation["validationRepairCount"] == 1
    assert output.fallback_used is False
    assert "WeatherOverview" in output.raw_output


@pytest.mark.asyncio
async def test_new_mixed_entry_repairs_unknown_weather_variant_without_scope_retry():
    model_client = RetryingUxMixedModelClient(
        [
            _WEATHER_TERSE_BODY.replace('"heroIcon"', '"forecastItem"'),
            _WEATHER_TERSE_BODY,
        ]
    )

    output = await AdvancedComponentPipeline().generate_mixed(
        _weather_scope_task(),
        model_client,
        _weather_card_spec(),
    )

    assert model_client.phases == [
        "advanced-component-scope",
        "advanced-mixed-body",
        "advanced-mixed-body-repair",
    ]
    assert (
        "WeatherOverview Template variant does not match"
        in model_client.prompts["advanced-mixed-body-repair"][-1]["content"]
    )
    assert output.invocation["validationRepairCount"] == 1


@pytest.mark.asyncio
async def test_new_mixed_entry_uses_second_repair_without_repeating_scope(monkeypatch):
    monkeypatch.setattr(get_settings(), "ux_mixed_validation_max_retry_attempts", 2)
    model_client = RetryingUxMixedModelClient(
        [
            'SingleFocusLayout(Text("模型新增标签", "body"));',
            'SingleFocusLayout(Column("section"));',
            _WEATHER_TERSE_BODY,
        ]
    )

    output = await AdvancedComponentPipeline().generate_mixed(
        _weather_scope_task(),
        model_client,
        _weather_card_spec(),
    )

    assert model_client.phases == [
        "advanced-component-scope",
        "advanced-mixed-body",
        "advanced-mixed-body-repair",
        "advanced-mixed-body-repair",
    ]
    assert output.invocation["validationRepairCount"] == 2
    assert output.fallback_used is False
    assert "WeatherOverview" in output.raw_output


@pytest.mark.asyncio
async def test_new_mixed_entry_keeps_weather_template_as_direct_layout_child():
    model_client = UxMixedModelClient()

    output = await AdvancedComponentPipeline().generate_mixed(
        _weather_scope_task(),
        model_client,
        _weather_card_spec(),
    )

    assert output.compiled_a2ui
    assert "SingleFocusLayout" in output.raw_output
    assert 'Template("WeatherOverview@1"' in output.raw_output
    assert "SingleFocusLayout" not in output.compiled_a2ui
    assert "WeatherOverview" not in output.effective_output


def test_ux_mixed_framer_repairs_only_trailing_typed_delimiters():
    source = 'Template("card@1", {"title":"天气"}, SingleFocusLayout(Text("晴", "body"));'

    framed, repaired = frame_ux_layout_children(
        source,
        size="2x2",
        registry=get_cardplan_registry(),
    )

    assert repaired is True
    assert framed.endswith(")));")
    assert parse_hybrid_card(framed).name == "card@1"


def test_ux_mixed_root_framer_keeps_weather_template_in_single_focus_layout():
    source = (
        'SingleFocusLayout(Template("WeatherOverview@1","compactIcon",'
        '{"conditionIcon":"resources/base/media/drop_1.svg"}),'
        'Column("compact",Text("多云","body"),Text("26℃","title")),'
        'PillAction({"actionId":"event.startNavigate",'
        '"icon":"resources/base/media/location_north_up_right_fill.svg"}));'
    )

    framed, repaired = frame_ux_layout_root_children(
        source,
        size="2x2",
        registry=get_cardplan_registry(),
        allowed_layout_ids=("SingleFocusLayout",),
    )
    root = parse_ux_layout_card(framed)

    assert repaired is True
    assert root.name == "SingleFocusLayout"
    assert [child.name for child in root.children] == ["WeatherOverview@1", "PillAction"]


def test_ux_mixed_root_framer_selects_only_allowed_layout_from_sibling_roots():
    source = (
        'Template("BatteryOverview@1","charging",{}),'
        'HeroActionLayout(Template("BatteryOverview@1","charging",{}),'
        'PillAction({"actionId":"event.setPowerSavingMode"}));'
    )

    framed, repaired = frame_ux_layout_root_children(
        source,
        size="2x2",
        registry=get_cardplan_registry(),
        allowed_layout_ids=("HeroActionLayout",),
    )

    assert repaired is True
    assert parse_ux_layout_card(framed).name == "HeroActionLayout"


def test_ux_mixed_root_framer_moves_sibling_business_into_layout():
    source = (
        'Template("BatteryOverview@1","charging",{}),'
        'HeroActionLayout({"actionPlacement":"bottom"},Column("compact",'
        'Text("省电管理","title")),PillAction({"actionId":'
        '"event.setPowerSavingMode"}));'
    )

    framed, repaired = frame_ux_layout_root_children(
        source,
        size="2x2",
        registry=get_cardplan_registry(),
        allowed_layout_ids=("HeroActionLayout",),
    )
    root = parse_ux_layout_card(framed)

    assert repaired is True
    assert [child.name for child in root.children] == ["BatteryOverview@1", "PillAction"]


def test_ux_mixed_root_framer_does_not_promote_generic_template_sibling():
    source = (
        'Template("text-stack@1","2x2",{}),'
        'HeroActionLayout(Column("compact",Text("省电管理","title")),'
        'PillAction({"actionId":"event.setPowerSavingMode"}));'
    )

    framed, repaired = frame_ux_layout_root_children(
        source,
        size="2x2",
        registry=get_cardplan_registry(),
        allowed_layout_ids=("HeroActionLayout",),
    )
    root = parse_ux_layout_card(framed)

    assert repaired is True
    assert [child.name for child in root.children] == ["Column", "PillAction"]


def test_ux_mixed_root_framer_rejects_removed_python_fallback_wrapper():
    source = (
        'BatteryOverview({"variant":"charging","role":"hero"},'
        'HeroActionLayout({"actionPlacement":"bottom"},Column("compact",'
        'Text("省电管理","title")),PillAction({"actionId":'
        '"event.setPowerSavingMode"})));'
    )

    with pytest.raises(TerseDslNested2ConversionError):
        frame_ux_layout_root_children(
            source,
            size="2x2",
            registry=get_cardplan_registry(),
            allowed_layout_ids=("HeroActionLayout",),
        )


@pytest.mark.asyncio
async def test_advanced_template_converts_to_standard_a2ui():
    output = await AdvancedComponentPipeline().generate(
        _metric_task_spec(),
        OfflineModelClient(),
    )
    assert output is not None
    profile = {
        "version": "v0.9",
        "sizes": {"2x2": {"width": 160, "height": 160}},
    }

    genui = convert_terse_dsl_nested2_to_a2ui(
        output.source_dsl,
        size="2x2",
        protocol_profile=profile,
    )

    assert len(genui.splitlines()) == 3
    assert '"createSurface"' in genui


@pytest.mark.parametrize(
    ("component_id", "invocation", "style_id"),
    [
        (
            "status-ring-action",
            LowPowerInvocation(
                status_text=BindingRef(path="/data/metric/caption"),
                percentage=BindingRef(path="/data/metric/progress"),
                battery_icon="bell",
                action_icon="moon",
                action=ActionRef(event_id="event.go", label="开启省电"),
            ),
            "system-teal",
        ),
    ],
)
def test_other_advanced_templates_convert_to_standard_a2ui(
    component_id,
    invocation,
    style_id,
):
    task_spec = TaskSpec(
        userQuery="生成状态卡片",
        size="2x2",
        eventCandidates=[EventAction(id="event.go", call="clickToApi", args={})],
        dataModelSchema={
            "data": {
                "metric": {
                    name: {
                        "type": "number"
                        if name in {"progress", "major", "minor", "reminder"}
                        else "string",
                        "description": name,
                        "sampleValue": 10
                        if name in {"progress", "major", "minor", "reminder"}
                        else name,
                    }
                    for name in (
                        "caption",
                        "progress",
                        "major",
                        "minor",
                        "title",
                        "start",
                        "end",
                        "reminder",
                    )
                }
            }
        },
        assetCandidates=[
            {
                "id": "bell",
                "src": "resources/base/media/bell.svg",
                "description": "状态图标",
            },
            {
                "id": "moon",
                "src": "resources/base/media/moon.svg",
                "description": "睡眠图标",
            },
        ],
    )
    source_dsl = build_terse_nested2(component_id, invocation, task_spec, style_id)

    genui = convert_terse_dsl_nested2_to_a2ui(
        source_dsl,
        size="2x2",
        protocol_profile={"version": "v0.9", "sizes": {"2x2": {"width": 160, "height": 160}}},
    )

    assert len(genui.splitlines()) == 3
    assert '"linearGradient"' in genui
    assert 'Image("resources/base/media/bell.svg"' in source_dsl
    assert 'Image("resources/base/media/moon.svg"' in source_dsl


def test_nested2_converter_requires_task_spec_leaf_for_data_placeholder():
    task_spec = _template_task_spec().model_dump(mode="json")
    source = 'Column("card", Text("${data.metric.caption}", "title"));'

    genui = convert_terse_dsl_nested2_to_a2ui(
        source,
        size="2x2",
        protocol_profile={"version": "v0.9"},
        task_spec=task_spec,
    )

    assert '"content":"{{ ${/data/metric/caption} }}"' in genui
    with pytest.raises(TerseDslNested2ConversionError, match="not a TaskSpec leaf"):
        convert_terse_dsl_nested2_to_a2ui(
            'Column("card", Text("${data.metric.missing}", "title"));',
            size="2x2",
            protocol_profile={"version": "v0.9"},
            task_spec=task_spec,
        )


@pytest.mark.parametrize(
    ("component_id", "invocation", "style_id"),
    [
        (
            "status-ring-action",
            LowPowerInvocation(
                status_text=BindingRef(path="/data/metric/caption"),
                percentage=BindingRef(path="/data/metric/progress"),
                battery_icon="bell",
                action_icon="moon",
                action=ActionRef(event_id="event.go", label="开启省电"),
            ),
            "system-teal",
        ),
    ],
)
def test_direct_a2ui_templates_use_original_aesthetic_component_tree(
    component_id,
    invocation,
    style_id,
):
    task_spec = _template_task_spec()
    output = build_standard_a2ui(
        component_id,
        invocation,
        task_spec,
        style_id,
    )
    messages = [json.loads(line) for line in output.splitlines()]
    update = messages[1]["updateComponents"]
    ids = {component["id"] for component in update["components"]}
    expected_original_ids = {
        "status-ring-action": {"battery-stack", "battery-progress", "action-wrap"},
    }
    assert update["root"] == "root"
    assert expected_original_ids[component_id] <= ids
    components = {component["id"]: component for component in update["components"]}
    assert components["battery-icon"]["component"] == "Image"
    assert components["battery-icon"]["src"] == "resources/base/media/bell.svg"
    assert components["action-icon"]["component"] == "Image"
    assert components["action-icon"]["src"] == "resources/base/media/moon.svg"


def _template_task_spec():
    numeric = {"type": "number", "description": "数值", "sampleValue": 10}
    text = {"type": "string", "description": "文本", "sampleValue": "示例"}
    return TaskSpec(
        userQuery="生成状态卡片",
        size="2x2",
        eventCandidates=[EventAction(id="event.go", call="clickToApi", args={})],
        dataModelSchema={
            "data": {
                "metric": {
                    "caption": text,
                    "progress": numeric,
                    "major": numeric,
                    "minor": numeric,
                    "title": text,
                    "start": text,
                    "end": text,
                    "reminder": numeric,
                }
            }
        },
        assetCandidates=[
            {
                "id": "bell",
                "src": "resources/base/media/bell.svg",
                "description": "状态图标",
            },
            {
                "id": "moon",
                "src": "resources/base/media/moon.svg",
                "description": "睡眠图标",
            },
        ],
    )


@pytest.mark.asyncio
async def test_terse_endpoint_runs_advanced_pipeline_end_to_end(
    monkeypatch,
):
    saved_genui: list[str] = []
    saved_design_tokens: list[str | None] = []
    saved_task_specs: list[dict] = []

    async def new_mixed_entry(_pipeline, _task_spec, _model_client, *_args, **_kwargs):
        source = (
            'Template("card@1", {"title":"天气"}, SingleFocusLayout(Text("天气状态", "body")));'
        )
        compiled = convert_terse_dsl_nested2_to_a2ui(
            'Column("card", Text("天气状态", "body"));',
            size="2x2",
            protocol_profile=A2UIProtocolRegistry.read_design_protocol_profile(
                TERSE_DSL_NESTED2_PROFILE_ID
            ),
        )
        return AdvancedPipelineOutput(
            component_id="ux-advanced-component-mixed",
            style_id="family-weather-care-blue",
            source_dsl='Column("card", Text("天气状态", "body"));',
            source_format="a2ui",
            ui_brief=AdvancedScopeBrief(
                themeId="family-weather-care-blue",
                advancedComponentIds=("WeatherOverview",),
            ),
            invocation={},
            planner_mode="llm",
            mapper_mode="llm",
            route="hybrid-template",
            confidence_bypassed=True,
            raw_output=source,
            effective_output='Column("card", Text("天气状态", "body"));',
            compiled_a2ui=compiled,
        )

    async def old_entry_must_not_run(*_args, **_kwargs):
        raise AssertionError("fifth interface must bypass the legacy generate entry")

    def save_artifact(store, artifact):
        saved_genui.append(artifact.genui)
        saved_design_tokens.append(store.design_token)
        saved_task_specs.append(artifact.taskSpec)
        return ArtifactSaveResult(
            artifactUrl="https://artifact.test/advanced",
            artifactDigest="sha256:advanced",
        )

    monkeypatch.setattr(AdvancedComponentPipeline, "generate_mixed", new_mixed_entry)
    monkeypatch.setattr(AdvancedComponentPipeline, "generate", old_entry_must_not_run)
    monkeypatch.setattr(ArtifactStore, "save", save_artifact)
    request = GenerateWidgetCardRequest(
        uid="advanced-e2e",
        prdVer="11.7.5.205",
        device={"romVersion": "CLS-AL30 6.0.0.328"},
        userQuery="设备电量低于20%，开启省电模式",
        title="设备电量",
        description="低电量状态和省电操作",
        candidateDataBindings=[
            {
                "capabilityId": "GetPhoneBatteryInfo",
                "arguments": {},
                "writeResultTo": "/data/phoneBattery",
            }
        ],
        candidateEventCandidates=[
            {
                "capabilityId": "event.setPowerSavingMode",
                "action": {
                    "id": "event.setPowerSavingMode",
                    "call": "clickToIntent",
                    "args": {
                        "intentName": "SetSettingSwitch",
                        "params": {
                            "appBundleName": "com.huawei.hmos.settings",
                            "itemName": "battery_saving_mode",
                            "switchFlag": 0,
                        },
                    },
                },
            }
        ],
        candidateAssetIds=["asset.icon_electricity", "asset.icon_save_power"],
    )

    response = await WidgetGenerationService().generate_widget_card_terse_dsl_nested2(request)

    assert response.status == GenerationStatus.SUCCESS
    assert response.artifactUrl == "https://artifact.test/advanced"
    assert len(saved_genui[0].splitlines()) == 3
    assert saved_design_tokens[0] is not None
    assert saved_design_tokens[0].startswith('Column("card"')
    assert "selectedTemplateId" not in saved_task_specs[0]


@pytest.mark.asyncio
async def test_new_mixed_entry_failure_does_not_fall_back_to_old_entry_or_legacy_terse(
    monkeypatch,
):
    calls: list[str] = []

    async def invalid_mixed(_pipeline, _task_spec, _model_client, *_args, **_kwargs):
        raise ValueError("invalid mixed output")

    async def old_entry(_pipeline, _task_spec, _model_client, *_args, **_kwargs):
        calls.append("old-entry")
        raise AssertionError("legacy entry must stay bypassed")

    async def generate_terse(_client, _prompt, _profile):
        calls.append("terse")
        return 'Column("card", Text("回退成功", "title"));'

    monkeypatch.setattr(AdvancedComponentPipeline, "generate_mixed", invalid_mixed)
    monkeypatch.setattr(AdvancedComponentPipeline, "generate", old_entry)
    monkeypatch.setattr(A2UIModelClient, "generate", generate_terse)
    request = GenerateWidgetCardRequest(
        uid="fallback-e2e",
        prdVer="11.7.5.205",
        device={"romVersion": "CLS-AL30 6.0.0.328"},
        userQuery="生成静态摘要",
        title="摘要",
        description="回退测试",
    )

    response = await WidgetGenerationService().generate_widget_card_terse_dsl_nested2(request)

    assert response.status == GenerationStatus.FAILED
    assert response.generationFallbackUsed is False
    assert calls == []


@pytest.mark.asyncio
async def test_disabled_whole_card_route_never_falls_back_to_legacy_terse(monkeypatch):
    calls: list[str] = []

    async def invalid_hybrid(_pipeline, _task_spec, _model_client, *_args, **_kwargs):
        raise ValueError("invalid hybrid output")

    async def generate_terse(_client, _prompt, _profile):
        calls.append("terse")
        return 'Column("card", Text("不应执行", "title"));'

    monkeypatch.setattr(get_settings(), "enable_advanced_whole_card_template", False)
    monkeypatch.setattr(AdvancedComponentPipeline, "generate_mixed", invalid_hybrid)
    monkeypatch.setattr(A2UIModelClient, "generate", generate_terse)
    request = GenerateWidgetCardRequest(
        uid="strict-hybrid-e2e",
        prdVer="11.7.5.205",
        device={"romVersion": "CLS-AL30 6.0.0.328"},
        userQuery="生成静态摘要",
        title="摘要",
        description="严格混合测试",
    )

    response = await WidgetGenerationService().generate_widget_card_terse_dsl_nested2(request)

    assert response.status == GenerationStatus.FAILED
    assert response.generationFallbackUsed is False
    assert calls == []


@pytest.mark.asyncio
async def test_advanced_design_token_is_valid_for_terse_edit_route():
    task_spec = _metric_task_spec()
    output = await AdvancedComponentPipeline().generate(task_spec, OfflineModelClient())
    assert output is not None
    conversion_profile = {
        "version": "v0.9",
        "sizes": {"2x2": {"width": 160, "height": 160}},
    }
    genui = convert_terse_dsl_nested2_to_a2ui(
        output.source_dsl,
        size="2x2",
        protocol_profile=conversion_profile,
    )
    service = WidgetGenerationService()
    artifact = service._build_artifact(
        genui,
        {
            "title": "内存",
            "description": "内存状态",
            "suggestSize": "2x2",
            "dataBindings": [
                {
                    "capabilityId": "ViewMemory",
                    "arguments": {},
                    "writeResultTo": "/data/memory",
                }
            ],
        },
        task_spec.model_dump(mode="json"),
        [],
        task_spec.eventCandidates,
        [],
        [],
        "a2ui-form-rom6.0-v1",
        "v0.9",
        "app-11.7.5.205_rom-6.0",
    )
    source = SourceArtifactLoadResult(
        artifact=artifact,
        design_token=output.source_dsl,
        artifact_digest="sha256:source",
        url_hash="source-url",
        read_latency_ms=1.0,
        parse_latency_ms=1.0,
        download_mode="test",
    )
    policy = GenerationRoutePolicy(
        operation="generateWidgetCardTerseDslNested2",
        protocol_profile_id="a2ui-form-rom6.0-v1",
        backend="openai",
        processor_kind=DslProcessorKind.TERSE_NESTED2,
        source_format=TERSE_DSL_NESTED2_PROFILE_ID,
        model_profile_id=TERSE_DSL_NESTED2_PROFILE_ID,
        model_format=TERSE_DSL_NESTED2_PROFILE_ID,
        design_profile_id=TERSE_DSL_NESTED2_PROFILE_ID,
    )

    valid = await service._validate_source_design_token(
        output.source_dsl,
        source,
        policy,
        conversion_profile,
    )

    assert valid is True


def test_mixed_generation_diagnostics_are_allowlisted_and_payload_free():
    try:
        raise TerseDslNested2ConversionError(
            "Template asset is not approved: private-business-asset"
        )
    except TerseDslNested2ConversionError as exc:
        error_code, error_origin = advanced_pipeline_module.safe_generation_error_metadata(exc)

    assert error_code == "TEMPLATE_ASSET_NOT_APPROVED"
    assert error_origin.startswith(
        "test_mixed_generation_diagnostics_are_allowlisted_and_payload_free:"
    )
    assert "private-business-asset" not in error_code
    assert "private-business-asset" not in error_origin

    unknown_code, _ = advanced_pipeline_module.safe_generation_error_metadata(
        ValueError("private-business-literal")
    )
    assert unknown_code == "PIPELINE_VALUE_ERROR"
    shape = advanced_pipeline_module._safe_raw_contract_shape(
        'SingleFocusLayout(Template("ux-private@1", "small", {"value":18}));',
        (("ux-private@1",),),
    )
    assert shape == (1, 1, 1)
