"""模板路由独立模块的关键边界和天气 POC。"""

from __future__ import annotations

import json
from typing import Any

import pytest

from api.schemas import GenerateWidgetCardRequest
from core.errors import GenerationStatus
from models.generation import CandidateDataBinding, TaskSpec
from models.service import ArtifactSaveResult
from services.artifact_store import ArtifactStore
from services.generation_pipeline import (
    DslProcessorKind,
    GenerationRoutePolicy,
)
from services.protocol_registry import A2UI_FORM_PROTOCOL_PROFILE_ID
from services.template_generation import facade
from services.template_generation.engine.advanced.scope_planner import (
    TemplateRouteNotApplicable,
)
from services.template_generation.engine.cardplan.registry import get_cardplan_registry
from services.template_generation.engine.pipeline import (
    TemplateGenerationError,
    generate_template_a2ui,
)
from services.widget_generation_service import WidgetGenerationService

_WEATHER_BODY = (
    'SingleFocusLayout(Template("WeatherOverview@1","heroIcon",'
    '{"conditionIcon":"resources/base/media/icon_weather1.svg"}));'
)


def test_all_provider_templates_are_loaded_from_the_isolated_directory():
    registry = get_cardplan_registry()

    assert set(registry.provider_template_ids) == {
        "ActivityOverview@1",
        "AppUsageOverview@1",
        "BatteryOverview@1",
        "BluetoothDeviceOverview@1",
        "DateOverview@1",
        "HeartRateOverview@1",
        "ResourceUsageOverview@1",
        "ScheduleOverview@1",
        "SleepOverview@1",
        "WeatherOverview@1",
        "WorkoutCountdown@1",
        "WorkoutOverview@1",
    }


class WeatherTemplateModel:
    def __init__(self) -> None:
        self.body_called = False

    async def generate_json(self, *_args: Any, **_kwargs: Any) -> dict[str, Any]:
        return {
            "routeVersion": "template-route-decision/1",
            "templateUsable": True,
            "themeId": "family-weather-care-blue",
            "advancedComponentIds": ["WeatherOverview"],
        }

    async def generate(self, *_args: Any, **_kwargs: Any) -> str:
        self.body_called = True
        return _WEATHER_BODY


def _policy() -> GenerationRoutePolicy:
    return GenerationRoutePolicy(
        operation="generateWidgetCardCompactDsl",
        protocol_profile_id=A2UI_FORM_PROTOCOL_PROFILE_ID,
        backend="openai",
        processor_kind=DslProcessorKind.DESIGN_COMPACT,
        source_format="design-compact-dsl",
        model_profile_id="design-compact-dsl",
        model_format="compact-dsl",
        design_profile_id="design-compact-dsl",
        validation_failure_blocking=True,
        stores_design_token=True,
    )


def _weather_request() -> GenerateWidgetCardRequest:
    return GenerateWidgetCardRequest(
        uid="template-test",
        prdVer="11.7.5.205",
        device={"romVersion": "6.0"},
        userQuery="做一个天气卡片，显示城市、温度、天气、空气质量和温度范围",
        size="2x2",
        title="今日天气",
        description="天气概览",
        candidateDataBindings=[
            {
                "capabilityId": "ViewWeather",
                "arguments": {"districtName": "青浦区", "forecastDays": 1},
                "writeResultTo": "/data/weather",
                "candidateOutputFields": [
                    "/location/districtName",
                    "/current/temperatureText",
                    "/current/condition",
                    "/current/airQuality",
                    "/daily/0/temperatureRangeText",
                ],
            }
        ],
        candidateAssetIds=["asset.icon_weather1"],
    )


def _weather_task_spec() -> TaskSpec:
    def field(value: str) -> dict[str, Any]:
        return {
            "type": "string",
            "description": "weather field",
            "sampleValue": value,
        }

    return TaskSpec(
        userQuery="天气",
        size="2x2",
        eventCandidates=[],
        assetCandidates=[
            {
                "src": "resources/base/media/icon_weather1.svg",
                "description": "天气状态图标",
                "sceneTags": ["condition", "weather"],
            }
        ],
        dataModelSchema={
            "data": {
                "weather": {
                    "location": {"districtName": field("青浦区")},
                    "current": {
                        "temperatureText": field("29°C"),
                        "condition": field("多云"),
                        "airQuality": field("良"),
                    },
                    "daily": [{"temperatureRangeText": field("25° / 32°")}],
                }
            }
        },
    )


def _weather_card_spec() -> dict[str, Any]:
    return {
        "title": "今日天气",
        "description": "天气概览",
        "suggestSize": "2x2",
        "dataBindings": [
            {
                "capabilityId": "ViewWeather",
                "arguments": {"districtName": "青浦区", "forecastDays": 1},
                "writeResultTo": "/data/weather",
            }
        ],
    }


@pytest.mark.asyncio
async def test_weather_template_generates_a2ui_and_compact_artifact(monkeypatch):
    model = WeatherTemplateModel()
    captured: dict[str, Any] = {}

    monkeypatch.setattr(
        facade,
        "create_template_model_client",
        lambda _runtime, _context: model,
    )

    async def save(store: ArtifactStore, artifact: Any) -> ArtifactSaveResult:
        captured["artifact"] = artifact
        captured["compact"] = store.design_token
        return ArtifactSaveResult(
            artifactUrl="https://artifact.test/weather-template",
            artifactDigest="sha256:weather-template",
        )

    monkeypatch.setattr(ArtifactStore, "save", save)
    starts: list[str] = []

    async def before_model_call(size: str) -> None:
        starts.append(size)

    response = await WidgetGenerationService(
        model_runtime=object(),
    ).generate_widget_card_compact_dsl(
        _weather_request(),
        before_model_call=before_model_call,
    )

    assert response.status == GenerationStatus.SUCCESS
    assert response.artifactUrl == "https://artifact.test/weather-template"
    assert starts == ["2x2"]
    assert model.body_called is True
    assert captured["compact"]
    assert "{{ ${/data/weather/current/condition}" in captured["compact"]
    messages = [json.loads(line) for line in captured["artifact"].genui.splitlines()]
    assert messages[0]["createSurface"]["catalogId"] == (
        "ohos.a2ui.extended.catalog.form"
    )
    root = next(
        item
        for item in messages[1]["updateComponents"]["components"]
        if item["id"] == "root"
    )
    assert root["styles"]["borderRadius"] == 18
    assert captured["artifact"].effectiveCapabilities["data"] == ["ViewWeather"]


@pytest.mark.asyncio
async def test_uncovered_requested_field_rejects_template_before_body_generation():
    model = WeatherTemplateModel()
    binding = CandidateDataBinding(
        capabilityId="ViewWeather",
        arguments={"districtName": "青浦区"},
        writeResultTo="/data/weather",
        candidateOutputFields=[
            "/current/condition",
            "/current/humidityPercent",
        ],
    )

    with pytest.raises(TemplateRouteNotApplicable, match="do not cover every"):
        await generate_template_a2ui(
            _weather_task_spec(),
            _weather_card_spec(),
            (binding,),
            model,
        )

    assert model.body_called is False


@pytest.mark.asyncio
async def test_edit_skips_template_attempt_and_uses_original_flow(monkeypatch):
    request = _weather_request().model_copy(
        update={"sourceArtifactUrl": "https://artifact.test/source.md"}
    )
    request.model_fields_set.add("sourceArtifactUrl")
    original_response = object()

    class Host:
        async def _generate_widget_card_with_policy(self, *_args: Any, **_kwargs: Any) -> Any:
            return original_response

    async def unexpected_attempt(*_args: Any, **_kwargs: Any) -> Any:
        pytest.fail("edit must not enter the template attempt")

    monkeypatch.setattr(facade, "_try_generate_template_artifact", unexpected_attempt)
    response = await facade.route_compact_generation(Host(), request, _policy())

    assert response is original_response


@pytest.mark.asyncio
async def test_selected_template_failure_does_not_fallback_to_original(monkeypatch):
    original_called = False

    class Host:
        async def _generate_widget_card_with_policy(self, *_args: Any, **_kwargs: Any) -> Any:
            nonlocal original_called
            original_called = True
            return object()

    async def selected_failure(*_args: Any, **_kwargs: Any) -> Any:
        raise TemplateGenerationError("selected route failed")

    monkeypatch.setattr(facade, "_try_generate_template_artifact", selected_failure)
    response = await facade.route_compact_generation(
        Host(),
        _weather_request(),
        _policy(),
    )

    assert response.status == GenerationStatus.FAILED
    assert original_called is False


@pytest.mark.asyncio
async def test_first_layer_rejection_falls_back_and_notifies_model_start_once(monkeypatch):
    notifications: list[str] = []

    class Host:
        async def _generate_widget_card_with_policy(
            self,
            _request: Any,
            _policy_value: Any,
            *,
            before_model_call: Any,
        ) -> str:
            await before_model_call("2x2")
            await before_model_call("2x2")
            return "original"

    async def rejected(
        _host: Any,
        _request: Any,
        _policy_value: Any,
        notify: Any,
    ) -> Any:
        await notify("2x2")
        raise TemplateRouteNotApplicable("LLM rejected template route")

    async def notify(size: str) -> None:
        notifications.append(size)

    monkeypatch.setattr(facade, "_try_generate_template_artifact", rejected)
    response = await facade.route_compact_generation(
        Host(),
        _weather_request(),
        _policy(),
        before_model_call=notify,
    )

    assert response == "original"
    assert notifications == ["2x2"]
