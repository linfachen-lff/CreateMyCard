"""Temporary batch-only Advanced Component admission bypass tests."""

from __future__ import annotations

import json
from types import SimpleNamespace

import pytest

from models.generation import TaskSpec
from services.advanced_component_pipeline import content_selectors, scope_planner
from services.advanced_component_pipeline.content_selectors import (
    advanced_component_batch_data_admission,
)
from services.advanced_component_pipeline.data_shape import extract_data_shape
from services.advanced_component_pipeline.models import AdvancedScopeBrief
from services.cardplan_template.registry import get_cardplan_registry


def _settings(*, batch: bool, bypass: bool = True) -> SimpleNamespace:
    return SimpleNamespace(
        enable_widget_batch_recording=batch,
        enable_advanced_component_data_admission_bypass_for_batch=bypass,
    )


def _incompatible_battery_task() -> TaskSpec:
    return TaskSpec(
        userQuery="只显示电池温度",
        size="2x2",
        dataModelSchema={"GetPhoneBatteryInfo": {}},
        assetCandidates=[],
    )


def test_batch_mode_temporarily_exposes_capability_backed_component(monkeypatch):
    task_spec = _incompatible_battery_task()
    monkeypatch.setattr(content_selectors, "get_settings", lambda: _settings(batch=True))

    with advanced_component_batch_data_admission(True):
        messages = scope_planner.build_advanced_scope_prompt(
            task_spec,
            extract_data_shape(task_spec),
            get_cardplan_registry(),
            available_capability_ids=("GetPhoneBatteryInfo",),
        )
    payload = json.loads(messages[1]["content"])

    assert payload["temporaryDataAdmissionBypass"] is True
    assert [item["id"] for item in payload["advancedComponents"]] == [
        "BatteryOverview"
    ]
    assert payload["advancedComponents"][0]["variants"] == [
        "normal",
        "charging",
        "low",
    ]
    assert "临时批跑模式" in messages[0]["content"]


@pytest.mark.parametrize(
    ("batch", "bypass"),
    [(False, True), (True, False)],
)
def test_non_batch_or_disabled_bypass_keeps_strict_admission(
    monkeypatch,
    batch: bool,
    bypass: bool,
):
    task_spec = _incompatible_battery_task()
    monkeypatch.setattr(
        content_selectors,
        "get_settings",
        lambda: _settings(batch=batch, bypass=bypass),
    )

    with pytest.raises(ValueError, match="no provider-backed"):
        scope_planner.build_advanced_scope_prompt(
            task_spec,
            extract_data_shape(task_spec),
            get_cardplan_registry(),
            available_capability_ids=("GetPhoneBatteryInfo",),
        )


@pytest.mark.asyncio
async def test_batch_bypass_accepts_first_layer_selection(monkeypatch):
    task_spec = _incompatible_battery_task()
    monkeypatch.setattr(content_selectors, "get_settings", lambda: _settings(batch=True))

    async def generate_json(_messages, _phase):
        return {
            "scopeVersion": "advanced-scope-brief/1",
            "themeId": "system-low-power-blue",
            "advancedComponentIds": ["BatteryOverview"],
        }

    with advanced_component_batch_data_admission(True):
        scope = await scope_planner.plan_advanced_scope_with_llm(
            task_spec,
            extract_data_shape(task_spec),
            generate_json,
            get_cardplan_registry(),
            available_capability_ids=("GetPhoneBatteryInfo",),
        )

    assert scope.advanced_component_ids == ("BatteryOverview",)


def test_batch_bypass_keeps_provider_gate(monkeypatch):
    task_spec = _incompatible_battery_task()
    monkeypatch.setattr(content_selectors, "get_settings", lambda: _settings(batch=True))

    with pytest.raises(ValueError, match="no provider-backed"):
        scope_planner.build_advanced_scope_prompt(
            task_spec,
            extract_data_shape(task_spec),
            get_cardplan_registry(),
            available_capability_ids=(),
        )


def test_batch_bypass_temporarily_skips_template_data_matching(monkeypatch):
    task_spec = TaskSpec(
        userQuery="显示当前位置",
        size="2x2",
        dataModelSchema={},
        assetCandidates=[],
    )
    registry = get_cardplan_registry()
    scope = AdvancedScopeBrief(
        themeId="generic-neutral",
        advancedComponentIds=("LocationOverview",),
    )
    expected = registry.require_ux_business_component(
        "LocationOverview"
    ).local_template_ids
    monkeypatch.setattr(content_selectors, "get_settings", lambda: _settings(batch=True))

    assert scope_planner.scope_template_ids(scope, registry, task_spec) == ()
    with advanced_component_batch_data_admission(True):
        selected = scope_planner.scope_template_ids(scope, registry, task_spec)

    assert selected == expected


def test_disabled_batch_bypass_keeps_template_data_matching(monkeypatch):
    task_spec = TaskSpec(
        userQuery="显示当前位置",
        size="2x2",
        dataModelSchema={},
        assetCandidates=[],
    )
    registry = get_cardplan_registry()
    scope = AdvancedScopeBrief(
        themeId="generic-neutral",
        advancedComponentIds=("LocationOverview",),
    )
    monkeypatch.setattr(
        content_selectors,
        "get_settings",
        lambda: _settings(batch=True, bypass=False),
    )

    with advanced_component_batch_data_admission(True):
        selected = scope_planner.scope_template_ids(scope, registry, task_spec)

    assert selected == ()
