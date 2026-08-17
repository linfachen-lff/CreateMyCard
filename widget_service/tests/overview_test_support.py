"""Shared fixtures for direct health overview component tests."""

from __future__ import annotations

from copy import deepcopy
from dataclasses import replace
from typing import Any

from models.generation import EventAction, TaskSpec
from services.advanced_component_pipeline.content_selectors import (
    project_content_component_facts,
)
from services.advanced_component_pipeline.models import AdvancedScopeBrief
from services.advanced_component_pipeline.pipeline import (
    _with_provider_template_binding_projection,
)
from services.advanced_component_pipeline.ux_mixed_prompt import build_ux_mixed_prompt
from services.cardplan_template.compiler import compile_ux_layout_card
from services.cardplan_template.models import HybridBodyContract
from services.cardplan_template.registry import CardPlanRegistry, get_cardplan_registry
from services.protocol_registry import TERSE_DSL_NESTED2_PROFILE_ID, A2UIProtocolRegistry


def field(value: Any, data_type: str) -> dict[str, Any]:
    return {"type": data_type, "sampleValue": value}


def sport_action(action_id: str = "event.open.health.sport") -> EventAction:
    return EventAction(
        id=action_id,
        displayLabel="打开运动健康",
        call="clickToIntent",
        args={"intentName": "HealthSport"},
    )


def prepare_provider_scope_projection(
    task_spec: TaskSpec,
    capability_ids: set[str],
    component_ids: tuple[str, ...],
    *,
    force_template: bool = False,
):
    registry = CardPlanRegistry() if force_template else get_cardplan_registry()
    if force_template:
        for component_id in component_ids:
            capability = registry.require_ux_business_component(component_id)
            registry.ux_business_components[component_id] = capability.model_copy(
                update={"implementation": "template"}
            )
    source_task = task_spec
    if "data" not in task_spec.dataModelSchema:
        source_task = task_spec.model_copy(
            update={"dataModelSchema": {"data": deepcopy(task_spec.dataModelSchema)}}
        )
    card_spec = {
        "suggestSize": task_spec.size,
        "dataBindings": [
            {
                "capabilityId": capability_id,
                "writeResultTo": f"/data/{capability_id}",
            }
            for capability_id in sorted(capability_ids)
        ],
    }
    projected = project_content_component_facts(
        source_task,
        capability_ids,
        component_ids,
    )
    projected = _with_provider_template_binding_projection(
        source_task,
        projected,
        card_spec,
        component_ids,
        registry,
    )
    return projected, card_spec, registry


def provider_direct_shadow_contract(
    contract: HybridBodyContract,
    source: str,
    component_ids: tuple[str, ...],
) -> HybridBodyContract:
    registry = get_cardplan_registry()
    direct_ids = tuple(
        component_id
        for component_id in component_ids
        if f"{component_id}(" in source
    )
    if not direct_ids:
        return contract
    direct_template_ids = {
        template_id
        for component_id in direct_ids
        for template_id in registry.require_ux_business_component(
            component_id
        ).local_template_ids
    }
    required_groups = tuple(
        group
        for group in contract.required_template_groups
        if not direct_template_ids.intersection(group)
    )
    return contract.model_copy(
        update={
            "required_template_groups": required_groups,
            "allowed_components": tuple(
                dict.fromkeys((*contract.allowed_components, *direct_ids))
            ),
            "allowed_business_component_ids": tuple(
                dict.fromkeys((*contract.allowed_business_component_ids, *direct_ids))
            ),
            "required_business_component_ids": tuple(
                dict.fromkeys((*contract.required_business_component_ids, *direct_ids))
            ),
        }
    )


def provider_direct_shadow_projection(projection, source: str, component_ids: tuple[str, ...]):
    contract = provider_direct_shadow_contract(
        projection.contract,
        source,
        component_ids,
    )
    registry = get_cardplan_registry()
    direct_template_ids = {
        template_id
        for component_id in component_ids
        if f"{component_id}(" in source
        for template_id in registry.require_ux_business_component(
            component_id
        ).local_template_ids
    }
    requested = tuple(
        template_id
        for template_id in projection.requested_template_ids
        if template_id not in direct_template_ids
    )
    return replace(projection, contract=contract, requested_template_ids=requested)


def compile_health_scope(
    task_spec: TaskSpec,
    component_ids: tuple[str, ...],
    capability_ids: set[str],
    source: str,
):
    uses_provider_template = any(
        get_cardplan_registry().require_ux_business_component(component_id).implementation
        == "template"
        for component_id in component_ids
    )
    if uses_provider_template:
        projected, card_spec, registry = prepare_provider_scope_projection(
            task_spec,
            capability_ids,
            component_ids,
        )
    else:
        registry = get_cardplan_registry()
        projected = project_content_component_facts(
            task_spec,
            capability_ids,
            component_ids,
        )
        card_spec = {
            "suggestSize": task_spec.size,
            "dataBindings": [
                {"capabilityId": capability_id}
                for capability_id in sorted(capability_ids)
            ],
        }
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
    contract = projection.contract
    compiled = compile_ux_layout_card(
        source,
        task_spec=projected,
        contract=contract,
        protocol_profile=A2UIProtocolRegistry.read_design_protocol_profile(
            TERSE_DSL_NESTED2_PROFILE_ID
        ),
        registry=registry,
        card_spec=card_spec if contract.required_template_groups else None,
        enable_data_bindings=bool(contract.required_template_groups),
    )
    return compiled, projection, projected
