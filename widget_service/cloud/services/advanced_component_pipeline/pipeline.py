"""高级组件分支的独立两轮模型编排。"""

from __future__ import annotations

import inspect
import traceback
from copy import deepcopy
from typing import Any, Literal

from app.logger import json_for_log, logger
from config.config import get_settings
from custom.a2ui_model_client import A2UIModelClient
from custom.deepseek_call_budget import DeepSeekCallBudgetExceeded
from models.generation import CandidateDataBinding, TaskSpec
from services.cardplan_template.compiler import compile_hybrid_card, compile_ux_layout_card
from services.cardplan_template.parser import ParsedCall, parse_ux_layout_card
from services.cardplan_template.prompt import build_hybrid_prompt
from services.cardplan_template.registry import CardPlanRegistry, get_cardplan_registry
from services.protocol_registry import TERSE_DSL_NESTED2_PROFILE_ID, A2UIProtocolRegistry
from services.terse_dsl_nested2_converter import TerseDslNested2ConversionError

from .argument_mapper import map_arguments_offline, map_arguments_with_llm
from .compiler import build_component_output
from .component_registry import get_component
from .component_selector import select_component, structural_compatibility
from .composition import build_advanced_composition_plan
from .content_selectors import (
    advanced_component_data_admission_is_relaxed,
    apply_content_selectors,
    extract_weather_overview_facts,
    project_content_component_facts,
)
from .data_shape import extract_data_shape
from .models import AdvancedPipelineOutput, SelectionConstraints
from .scope_planner import (
    TemplateRouteNotApplicable,
    plan_advanced_scope_offline,
    plan_advanced_scope_with_llm,
    plan_template_route_with_llm,
    resolve_available_capability_ids,
)
from .styles import select_style
from .ui_planner import normalize_action_placement, plan_ui_offline, plan_ui_with_llm
from .ux_mixed_framer import frame_ux_layout_root_children
from .ux_mixed_prompt import (
    build_ux_mixed_prompt,
    build_ux_mixed_validation_retry_prompt,
)

_MODULE = "[Advanced Component Pipeline]"

_WEATHER_REQUEST_FIELD_TERMS: dict[str, tuple[str, ...]] = {
    "city": ("city", "location", "district", "城市", "地点", "地区"),
    "temperature": ("temperature", "当前温度", "气温"),
    "condition": ("condition", "weather", "天气", "天气状况"),
    "airQuality": ("air quality", "空气质量"),
    "temperatureRange": ("temperature range", "high low", "高低温", "温度范围"),
    "feelsLike": ("feels like", "体感温度"),
    "humidity": ("humidity", "湿度"),
    "wind": ("wind", "风力", "风速", "风向"),
    "uvIndex": ("uv index", "ultraviolet", "紫外线"),
    "alert": ("weather alert", "weather warning", "天气预警", "预警", "预警信息", "极端天气"),
    "rainProbability": ("rain probability", "precipitation probability", "降雨概率", "降水概率"),
}

_SAFE_CONTRACT_ERROR_PREFIXES: tuple[tuple[str, str], ...] = (
    ("CardPlan syntax error", "DSL_SYNTAX_INVALID"),
    ("CardPlan output", "DSL_OUTPUT_INVALID"),
    ("UX Mixed root", "LAYOUT_ROOT_INVALID"),
    ("UX Layout", "LAYOUT_CONTRACT_INVALID"),
    ("Template is not allowed", "TEMPLATE_NOT_ALLOWED"),
    ("Template variant is not allowed", "TEMPLATE_VARIANT_NOT_ALLOWED"),
    ("Template parent is not allowed", "TEMPLATE_PARENT_INVALID"),
    ("Template params are invalid", "TEMPLATE_PARAMS_INVALID"),
    ("Template parameter is missing", "TEMPLATE_PARAMETER_MISSING"),
    ("Template asset is not approved", "TEMPLATE_ASSET_NOT_APPROVED"),
    ("Template literal is not trusted", "TEMPLATE_LITERAL_NOT_TRUSTED"),
    ("Template number is not trusted", "TEMPLATE_NUMBER_NOT_TRUSTED"),
    ("Required Template group is missing", "REQUIRED_TEMPLATE_MISSING"),
    ("Raw component is not allowed", "RAW_COMPONENT_NOT_ALLOWED"),
    ("Raw literal is not trusted", "RAW_LITERAL_NOT_TRUSTED"),
    ("Raw number is not trusted", "RAW_NUMBER_NOT_TRUSTED"),
    ("Direct events are forbidden", "DIRECT_EVENT_FORBIDDEN"),
    ("Direct Buttons are forbidden", "DIRECT_BUTTON_FORBIDDEN"),
    ("IconAction requires an approved icon", "ACTION_ICON_REQUIRED"),
    ("UX Action", "ACTION_CONTRACT_INVALID"),
    ("Hybrid content Actions", "ACTION_CONTRACT_INVALID"),
    ("Hybrid content is missing required numeric facts", "REQUIRED_NUMBER_MISSING"),
    ("Hybrid raw component budget", "RAW_COMPONENT_BUDGET_EXCEEDED"),
    ("Hybrid expanded component budget", "EXPANDED_COMPONENT_BUDGET_EXCEEDED"),
    ("Hybrid component depth budget", "COMPONENT_DEPTH_BUDGET_EXCEEDED"),
)


def safe_generation_error_metadata(exc: Exception) -> tuple[str, str]:
    """Return allow-listed diagnostics without logging model or business payloads."""
    message = str(exc)
    error_code = next(
        (code for prefix, code in _SAFE_CONTRACT_ERROR_PREFIXES if message.startswith(prefix)),
        "CONTRACT_VALIDATION_FAILED"
        if isinstance(exc, TerseDslNested2ConversionError)
        else "PIPELINE_VALUE_ERROR",
    )
    frames = traceback.extract_tb(exc.__traceback__)
    origin = "unknown"
    if frames:
        frame = frames[-1]
        origin = f"{frame.name}:{frame.lineno}"
    return error_code, origin


def _safe_raw_contract_shape(
    source: str,
    required_groups: tuple[tuple[str, ...], ...],
) -> tuple[int, int, int]:
    """Count protocol structure only; never return literals or model text."""
    try:
        root = parse_ux_layout_card(source)
    except (RuntimeError, ValueError):
        return -1, -1, -1
    template_ids: list[str] = []
    numeric_literal_count = 0

    def count_value(value: object) -> None:
        nonlocal numeric_literal_count
        if isinstance(value, bool) or value is None:
            return
        if isinstance(value, (int, float)):
            numeric_literal_count += 1
            return
        if isinstance(value, dict):
            for child in value.values():
                count_value(child)
            return
        if isinstance(value, (list, tuple)):
            for child in value:
                count_value(child)

    def visit(call: ParsedCall) -> None:
        if call.kind == "template":
            template_ids.append(call.name)
        for value in call.values:
            count_value(value)
        for child in call.children:
            visit(child)

    visit(root)
    required_group_hit_count = sum(
        any(template_id in group for template_id in template_ids) for group in required_groups
    )
    return len(template_ids), required_group_hit_count, numeric_literal_count


def weather_field_coverage(
    query: str,
    task_spec: TaskSpec,
    compiled_a2ui: str,
) -> dict[str, Any]:
    """Report semantic field names only; never copy business values into metrics."""
    normalized = query.casefold()
    requested_names = {
        field_name
        for field_name, terms in _WEATHER_REQUEST_FIELD_TERMS.items()
        if any(term in normalized for term in terms)
    }
    if any(term in normalized for term in ("weather", "temperature", "天气", "温度")):
        requested_names.update(
            {"city", "temperature", "condition", "airQuality", "temperatureRange"}
        )
    requested = [
        field_name for field_name in _WEATHER_REQUEST_FIELD_TERMS if field_name in requested_names
    ]
    facts = extract_weather_overview_facts(task_spec.dataModelSchema)
    if facts is None:
        return {
            "requested": requested,
            "renderable": [],
            "visible": [],
            "requestedCount": len(requested),
            "renderableCount": 0,
            "visibleCount": 0,
        }
    values = {
        "city": facts.city,
        "temperature": facts.temperature,
        "condition": facts.condition,
        "airQuality": facts.air_quality,
        "temperatureRange": facts.temperature_range,
    }
    renderable = list(values)
    visible = [field_name for field_name, value in values.items() if value in compiled_a2ui]
    return {
        "requested": requested,
        "renderable": renderable,
        "visible": visible,
        "requestedCount": len(requested),
        "renderableCount": len(renderable),
        "visibleCount": len(visible),
    }


class AdvancedComponentPipeline:
    """模型负责语义规划和参数映射，服务端负责选择与模板编译。"""

    async def generate_mixed(
        self,
        task_spec: TaskSpec,
        model_client: A2UIModelClient,
        card_spec: dict[str, Any] | None = None,
        *,
        allow_offline_fallback: bool = False,
        coverage_bindings: tuple[CandidateDataBinding, ...] | None = None,
    ) -> AdvancedPipelineOutput:
        """第五接口新入口；从第一层请求起完全旁路旧整卡选择与参数映射。"""
        registry = get_cardplan_registry()
        data_admission_bypass = advanced_component_data_admission_is_relaxed()
        if card_spec is None:
            card_spec = {
                "suggestSize": task_spec.size,
            }
        available_capability_ids = _card_spec_capability_ids(card_spec)
        effective_capability_ids = resolve_available_capability_ids(
            task_spec,
            registry,
            available_capability_ids,
        )
        task_spec = apply_content_selectors(task_spec, effective_capability_ids)
        data_shape = extract_data_shape(task_spec)

        async def generate_json(
            prompt: list[dict[str, str]],
            phase: str,
        ) -> dict[str, Any]:
            logger.info(
                f"{_MODULE} scope_prompt_built phase={phase} message_count={len(prompt)} "
                f"prompt_chars={sum(len(item['content']) for item in prompt)} "
                f"data_admission_bypass={str(data_admission_bypass).lower()}"
            )
            response = await model_client.generate_json(prompt, phase=phase)
            logger.info(
                f"{_MODULE} model_response_received phase={phase} field_count={len(response)}"
            )
            return response

        planner_mode: Literal["llm", "offline"] = "llm"
        try:
            if coverage_bindings is None:
                scope = await plan_advanced_scope_with_llm(
                    task_spec,
                    data_shape,
                    generate_json,
                    registry,
                    available_capability_ids,
                )
            else:
                scope = await plan_template_route_with_llm(
                    task_spec,
                    data_shape,
                    generate_json,
                    registry,
                    coverage_bindings,
                    available_capability_ids,
                    card_spec,
                )
        except DeepSeekCallBudgetExceeded:
            raise
        except TemplateRouteNotApplicable:
            raise
        except (RuntimeError, ValueError) as exc:
            if coverage_bindings is not None:
                raise TemplateRouteNotApplicable("Template first-layer decision failed") from exc
            if not allow_offline_fallback:
                raise
            planner_mode = "offline"
            scope = plan_advanced_scope_offline(
                task_spec,
                data_shape,
                registry,
                available_capability_ids,
            )
            logger.warning(f"{_MODULE} advanced_scope_fallback exception_type={type(exc).__name__}")
        mixed_task_spec = project_content_component_facts(
            task_spec,
            effective_capability_ids,
            scope.advanced_component_ids,
        )
        mixed_task_spec = _with_provider_template_binding_projection(
            task_spec,
            mixed_task_spec,
            card_spec,
            scope.advanced_component_ids,
            registry,
        )
        projection = build_ux_mixed_prompt(
            task_spec=mixed_task_spec,
            card_spec=card_spec,
            scope=scope,
            registry=registry,
        )
        logger.info(
            f"{_MODULE} ux_mixed_prompt_built message_count={len(projection.messages)} "
            f"prompt_chars={sum(len(item['content']) for item in projection.messages)} "
            f"scope_component_count={len(scope.advanced_component_ids)} "
            f"layout_candidate_count={len(projection.allowed_layout_ids)} "
            f"template_candidate_count={len(projection.requested_template_ids)}"
        )
        protocol_profile = A2UIProtocolRegistry.read_design_protocol_profile(
            TERSE_DSL_NESTED2_PROFILE_ID
        )
        generation_messages = projection.messages
        validation_repair_count = 0
        while True:
            phase = (
                "advanced-mixed-body"
                if validation_repair_count == 0
                else "advanced-mixed-body-repair"
            )
            raw_output = await _generate_hybrid_body(
                model_client,
                generation_messages,
                phase=phase,
            )
            try:
                framed_output, layout_children_framed = frame_ux_layout_root_children(
                    raw_output,
                    size=task_spec.size,
                    registry=registry,
                    allowed_layout_ids=projection.allowed_layout_ids,
                )
                compilation = compile_ux_layout_card(
                    framed_output,
                    task_spec=task_spec,
                    contract=projection.contract,
                    protocol_profile=protocol_profile,
                    registry=registry,
                    business_title=(
                        str(card_spec.get("title")) if card_spec.get("title") else None
                    ),
                    card_spec=card_spec,
                    enable_data_bindings=True,
                )
                break
            except TerseDslNested2ConversionError as exc:
                error_code, error_origin = safe_generation_error_metadata(exc)
                (
                    raw_template_call_count,
                    required_template_group_hit_count,
                    raw_numeric_literal_count,
                ) = _safe_raw_contract_shape(
                    raw_output,
                    projection.contract.required_template_groups,
                )
                max_repairs = get_settings().ux_mixed_validation_max_retry_attempts
                if validation_repair_count >= max_repairs:
                    logger.error(
                        f"{_MODULE} ux_mixed_contract_rejected "
                        f"validation_error_code={error_code} "
                        f"error_origin={error_origin} "
                        f"repair_attempts={validation_repair_count} "
                        f"raw_template_call_count={raw_template_call_count} "
                        "required_template_group_hit_count="
                        f"{required_template_group_hit_count} "
                        f"raw_numeric_literal_count={raw_numeric_literal_count} "
                        "business_payload_logged=false"
                    )
                    raise
                validation_repair_count += 1
                logger.warning(
                    f"{_MODULE} ux_mixed_contract_retry "
                    f"repair_attempt={validation_repair_count} "
                    f"max_repair_attempts={max_repairs} "
                    f"exception_type={type(exc).__name__} "
                    f"validation_error_code={error_code} "
                    f"error_origin={error_origin} "
                    f"raw_template_call_count={raw_template_call_count} "
                    "required_template_group_hit_count="
                    f"{required_template_group_hit_count} "
                    f"raw_numeric_literal_count={raw_numeric_literal_count}"
                )
                generation_messages = build_ux_mixed_validation_retry_prompt(
                    projection.messages,
                    raw_output,
                    exc,
                )
        logger.info(
            f"{_MODULE} ux_mixed_generation_completed "
            f"scope_component_count={len(scope.advanced_component_ids)} "
            f"template_call_count={compilation.stats.template_call_count} "
            "template_variant_normalization_count="
            f"{compilation.stats.template_variant_normalization_count} "
            "template_provider_param_normalization_count="
            f"{compilation.stats.template_provider_param_normalization_count} "
            "template_relation_number_normalization_count="
            f"{compilation.stats.template_relation_number_normalization_count} "
            f"expanded_component_count={compilation.stats.expanded_component_count} "
            f"validation_repair_count={validation_repair_count} "
            "whole_card_scoring_bypassed=true fallback_used=false"
        )
        requested_asset_sources = {
            source
            for item in task_spec.assetCandidates
            if isinstance(item, dict)
            for source in (item.get("src"),)
            if isinstance(source, str)
        }
        trusted_internal_asset_sources = tuple(
            source
            for source in projection.contract.allowed_asset_sources
            if source not in requested_asset_sources and source in compilation.a2ui
        )
        weather_coverage: dict[str, Any] = {}
        if "WeatherOverview" in scope.advanced_component_ids:
            weather_coverage = weather_field_coverage(
                task_spec.userQuery,
                mixed_task_spec,
                compilation.a2ui,
            )
        batch_evidence: dict[str, Any] = {}
        if get_settings().enable_widget_batch_recording:
            batch_evidence = {
                "temporaryDataAdmissionBypass": data_admission_bypass,
                "projectedTaskSpec": mixed_task_spec.model_dump(mode="json"),
                "precompileDsl": framed_output,
            }
        return AdvancedPipelineOutput(
            component_id="ux-advanced-component-mixed",
            style_id=projection.theme_id,
            source_dsl=compilation.effective_output,
            source_format="a2ui",
            ui_brief=scope,
            invocation={
                "advancedScope": scope.model_dump(by_alias=True),
                "temporaryDataAdmissionBypass": data_admission_bypass,
                "allowedLayoutIds": projection.allowed_layout_ids,
                "requestedTemplateIds": projection.requested_template_ids,
                "layoutChildrenFramed": layout_children_framed,
                "validationRepairCount": validation_repair_count,
                "templateVariantNormalizationCount": (
                    compilation.stats.template_variant_normalization_count
                ),
                "templateProviderParamNormalizationCount": (
                    compilation.stats.template_provider_param_normalization_count
                ),
                "templateRelationNumberNormalizationCount": (
                    compilation.stats.template_relation_number_normalization_count
                ),
                "weatherFieldCoverage": weather_coverage,
                "batchEvidence": batch_evidence,
            },
            planner_mode=planner_mode,
            mapper_mode="llm",
            route="hybrid-template",
            whole_card_confidence=0.0,
            whole_card_candidates=[],
            confidence_bypassed=True,
            raw_output=raw_output,
            effective_output=compilation.effective_output,
            compiled_a2ui=compilation.a2ui,
            fallback_used=False,
            template_call_count=compilation.stats.template_call_count,
            template_used_ids=list(compilation.stats.template_used_ids),
            expanded_component_count=compilation.stats.expanded_component_count,
            advanced_composition=None,
            trusted_internal_asset_sources=trusted_internal_asset_sources,
        )

    async def generate(
        self,
        task_spec: TaskSpec,
        model_client: A2UIModelClient,
        card_spec: dict[str, Any] | None = None,
        *,
        force_hybrid: bool = False,
        allow_offline_fallback: bool = True,
    ) -> AdvancedPipelineOutput | None:
        data_shape = extract_data_shape(task_spec)
        registry = get_cardplan_registry()
        composition_plan = build_advanced_composition_plan(task_spec, data_shape, registry)

        async def generate_json(
            prompt: list[dict[str, str]],
            phase: str,
        ) -> dict[str, Any]:
            if phase == "advanced-ui-brief":
                logger.info(
                    f"{_MODULE} ui_planner_prompt_built phase={phase} "
                    f"message_count={len(prompt)} "
                    f"prompt_chars={sum(len(item['content']) for item in prompt)}"
                )
            elif phase == "advanced-argument-map":
                logger.info(
                    f"{_MODULE} argument_mapper_prompt_built "
                    f"phase={phase} message_count={len(prompt)} "
                    f"prompt_chars={sum(len(item['content']) for item in prompt)}"
                )
            response = await model_client.generate_json(prompt, phase=phase)
            logger.info(
                f"{_MODULE} model_response_received phase={phase} field_count={len(response)}"
            )
            return response

        planner_mode: Literal["llm", "offline"] = "llm"
        try:
            ui_brief = await plan_ui_with_llm(
                task_spec,
                data_shape,
                generate_json,
                composition_plan,
                card_spec,
            )
        except DeepSeekCallBudgetExceeded:
            raise
        except (RuntimeError, ValueError) as exc:
            if not allow_offline_fallback:
                raise
            planner_mode = "offline"
            ui_brief = plan_ui_offline(task_spec, data_shape, composition_plan)
            logger.warning(f"{_MODULE} ui_brief_fallback exception_type={type(exc).__name__}")
        ui_brief = normalize_action_placement(ui_brief, data_shape, registry)
        logger.info(
            f"{_MODULE} ui_brief_resolved mode={planner_mode} "
            f"template_candidate_count={len(ui_brief.local_template_ids)} "
            f"theme_selected={ui_brief.theme_id is not None} "
            f"effective_template_ids={json_for_log(ui_brief.local_template_ids)}"
        )
        if composition_plan is not None:
            logger.info(
                f"{_MODULE} advanced_composition_resolved "
                f"registry_version={composition_plan.registry_version} "
                f"primary_domain={composition_plan.primary_domain} "
                f"adaptive_template_id={composition_plan.adaptive_template_id or 'none'} "
                f"component_count={len(composition_plan.assignments)} "
                f"action_count={composition_plan.action_count} "
                f"chart_count={composition_plan.primary_chart_count}"
            )

        selection = select_component(
            data_shape,
            ui_brief,
            SelectionConstraints(
                size=task_spec.size,
                action_count=len(task_spec.eventCandidates),
                asset_count=len(task_spec.assetCandidates),
            ),
        )
        selection_candidates = selection.candidates if selection is not None else []
        confidence = selection.confidence if selection is not None else 0.0
        settings = get_settings()
        whole_card_enabled = getattr(settings, "enable_advanced_whole_card_template", True)
        selected_compatibility = 0.0
        if selection is not None:
            selected_compatibility = structural_compatibility(
                data_shape,
                SelectionConstraints(
                    size=task_spec.size,
                    action_count=len(task_spec.eventCandidates),
                    asset_count=len(task_spec.assetCandidates),
                ),
                get_component(selection.component_id).spec,
            )["score"]
        # A selected whole-card component is authoritative while the legacy
        # route remains enabled. Confidence and structural compatibility stay
        # observable, but only the explicit server switch or force flag can
        # bypass a valid selection. The fifth interface uses generate_mixed().
        use_hybrid = force_hybrid or not whole_card_enabled or selection is None
        selected_component = selection.component_id if selection is not None else "none"
        logger.info(
            f"{_MODULE} component_selection_completed selected_component_id={selected_component} "
            f"confidence={confidence} force_hybrid={force_hybrid} "
            f"whole_card_enabled={whole_card_enabled} "
            f"task_spec_compatibility={selected_compatibility} "
            f"route={'hybrid-template' if use_hybrid else 'whole-card-template'} "
            f"candidate_count={len(selection_candidates)}"
        )

        if use_hybrid and getattr(model_client, "use_mock", False) and not force_hybrid:
            logger.info(f"{_MODULE} hybrid_route_skipped reason=legacy-mock-compatibility")
            return None

        if use_hybrid:
            if card_spec is None:
                card_spec = {
                    "title": task_spec.userQuery[:8],
                    "description": task_spec.userQuery[:12],
                    "suggestSize": task_spec.size,
                }
            projection = build_hybrid_prompt(
                task_spec=task_spec,
                card_spec=card_spec,
                ui_brief=ui_brief,
                registry=registry,
            )
            logger.info(
                f"{_MODULE} hybrid_prompt_built message_count={len(projection.messages)} "
                f"prompt_chars={sum(len(item['content']) for item in projection.messages)} "
                f"template_candidate_count={len(projection.requested_template_ids)}"
            )
            raw_output = await _generate_hybrid_body(
                model_client,
                projection.messages,
            )
            protocol_profile = A2UIProtocolRegistry.read_design_protocol_profile(
                TERSE_DSL_NESTED2_PROFILE_ID
            )
            try:
                compilation = compile_hybrid_card(
                    raw_output,
                    task_spec=task_spec,
                    contract=projection.contract,
                    protocol_profile=protocol_profile,
                    registry=registry,
                    card_spec=card_spec,
                    enable_data_bindings=True,
                )
            except TerseDslNested2ConversionError as exc:
                logger.error(
                    f"{_MODULE} hybrid_compilation_failed error={json_for_log(str(exc))} "
                    f"raw_output={json_for_log(raw_output)}"
                )
                raise
            logger.info(
                f"{_MODULE} hybrid_generation_completed template_call_count="
                f"{compilation.stats.template_call_count} expanded_component_count="
                f"{compilation.stats.expanded_component_count} fallback_used=false"
            )
            return AdvancedPipelineOutput(
                component_id="cardplan-template-hybrid",
                style_id=projection.theme_id,
                source_dsl=compilation.raw_output,
                source_format="a2ui",
                ui_brief=ui_brief,
                invocation={"requestedTemplateIds": projection.requested_template_ids},
                planner_mode=planner_mode,
                mapper_mode="llm",
                route="hybrid-template",
                whole_card_confidence=confidence,
                whole_card_candidates=selection_candidates,
                confidence_bypassed=force_hybrid or not whole_card_enabled,
                raw_output=compilation.raw_output,
                effective_output=compilation.effective_output,
                compiled_a2ui=compilation.a2ui,
                fallback_used=False,
                template_call_count=compilation.stats.template_call_count,
                template_used_ids=list(compilation.stats.template_used_ids),
                expanded_component_count=compilation.stats.expanded_component_count,
                advanced_composition=composition_plan,
            )

        if selection is None:
            return None

        style_id, _tokens = select_style(ui_brief)
        mapper_mode: Literal["llm", "offline"] = "llm"
        try:
            invocation = await map_arguments_with_llm(
                selection.component_id,
                task_spec,
                data_shape,
                ui_brief,
                generate_json,
            )
        except (RuntimeError, ValueError) as exc:
            if not allow_offline_fallback:
                raise
            mapper_mode = "offline"
            try:
                invocation = map_arguments_offline(
                    selection.component_id,
                    task_spec,
                    data_shape,
                )
            except ValueError:
                logger.warning(
                    f"{_MODULE} invocation_fallback_failed "
                    f"exception_type={type(exc).__name__} fallback=terse"
                )
                return None
            logger.warning(f"{_MODULE} invocation_fallback exception_type={type(exc).__name__}")

        logger.info(
            f"{_MODULE} invocation_resolved mode={mapper_mode} "
            f"component_id={selection.component_id} "
            f"invocation_field_count={len(invocation.model_dump())}"
        )

        output_format = get_settings().advanced_component_output_format
        source_dsl = build_component_output(
            selection.component_id,
            invocation,
            task_spec,
            style_id,
            output_format,
        )
        logger.info(
            f"{_MODULE} generation_completed component_id={selection.component_id} "
            f"style_id={style_id} output_format={output_format} "
            f"planner_mode={planner_mode} mapper_mode={mapper_mode}"
        )
        return AdvancedPipelineOutput(
            component_id=selection.component_id,
            style_id=style_id,
            source_dsl=source_dsl,
            source_format=output_format,
            ui_brief=ui_brief,
            invocation=invocation.model_dump(mode="json"),
            planner_mode=planner_mode,
            mapper_mode=mapper_mode,
            route="whole-card-template",
            whole_card_confidence=selection.confidence,
            whole_card_candidates=selection.candidates,
            raw_output=source_dsl,
            effective_output=source_dsl,
            advanced_composition=composition_plan,
        )


def _with_provider_template_binding_projection(
    source: TaskSpec,
    projected: TaskSpec,
    card_spec: dict[str, Any],
    component_ids: tuple[str, ...],
    registry: CardPlanRegistry,
) -> TaskSpec:
    schema = deepcopy(projected.dataModelSchema)
    changed = False
    for component_id in component_ids:
        capability = registry.require_ux_business_component(component_id)
        if capability.implementation != "template":
            continue
        for template_id in capability.local_template_ids:
            definition = registry.require_template(template_id)
            if definition.source_format != "cardtpl/1" or not definition.capability_id:
                continue
            root = _provider_binding_root(card_spec, definition.capability_id)
            if root is None:
                continue
            for binding in definition.bindings.values():
                path = f"{root.rstrip('/')}{binding.path}"
                value = _pointer_value(source.dataModelSchema, path)
                if value is None:
                    continue
                _set_pointer_value(schema, path, deepcopy(value))
                changed = True
    if not changed:
        return projected
    return projected.model_copy(update={"dataModelSchema": schema})


def _provider_binding_root(
    card_spec: dict[str, Any],
    capability_id: str,
) -> str | None:
    raw_bindings = card_spec.get("dataBindings")
    if not isinstance(raw_bindings, list):
        return None
    roots = {
        item.get("writeResultTo")
        for item in raw_bindings
        if isinstance(item, dict)
        and item.get("capabilityId") == capability_id
        and _valid_provider_binding_root(item.get("writeResultTo"))
    }
    return next(iter(roots)) if len(roots) == 1 else None


def _valid_provider_binding_root(value: Any) -> bool:
    return isinstance(value, str) and (value == "/data" or value.startswith("/data/"))


def _pointer_value(value: Any, pointer: str) -> Any | None:
    current = value
    for part in _pointer_parts(pointer):
        if isinstance(current, dict):
            current = current.get(part)
            continue
        if isinstance(current, list) and part.isdigit():
            index = int(part)
            current = current[index] if index < len(current) else None
            continue
        return None
    return current


def _set_pointer_value(root: dict[str, Any], pointer: str, value: Any) -> None:
    _set_pointer_parts(root, _pointer_parts(pointer), value)


def _set_pointer_parts(current: Any, parts: tuple[str, ...], value: Any) -> None:
    part = parts[0]
    if isinstance(current, dict):
        if len(parts) == 1:
            current[part] = value
            return
        child = current.get(part)
        expected = list if parts[1].isdigit() else dict
        if not isinstance(child, expected):
            child = expected()
            current[part] = child
        _set_pointer_parts(child, parts[1:], value)
        return
    if not isinstance(current, list) or not part.isdigit():
        return
    index = int(part)
    while len(current) <= index:
        current.append(None)
    if len(parts) == 1:
        current[index] = value
        return
    child = current[index]
    expected = list if parts[1].isdigit() else dict
    if not isinstance(child, expected):
        child = expected()
        current[index] = child
    _set_pointer_parts(child, parts[1:], value)


def _pointer_parts(pointer: str) -> tuple[str, ...]:
    return tuple(
        part.replace("~1", "/").replace("~0", "~")
        for part in pointer.removeprefix("/").split("/")
    )


def _card_spec_capability_ids(card_spec: dict[str, Any]) -> tuple[str, ...] | None:
    bindings = card_spec.get("dataBindings")
    if bindings is None:
        return None
    if not isinstance(bindings, list):
        return ()
    return tuple(
        capability_id
        for binding in bindings
        if isinstance(binding, dict)
        for capability_id in (binding.get("capabilityId"),)
        if isinstance(capability_id, str)
    )


async def _generate_hybrid_body(
    model_client: A2UIModelClient,
    messages: list[dict[str, str]],
    *,
    phase: str = "hybrid-body",
) -> str:
    profile = {"id": TERSE_DSL_NESTED2_PROFILE_ID, "format": "hybrid-card"}
    generate = model_client.generate
    parameters = inspect.signature(generate).parameters
    accepts_keywords = any(
        parameter.kind == inspect.Parameter.VAR_KEYWORD for parameter in parameters.values()
    )
    if accepts_keywords or "suppress_prompt_log" in parameters:
        result = generate(
            messages,
            profile,
            suppress_prompt_log=True,
            phase=phase,
        )
    else:
        result = generate(messages, profile)
    if inspect.isawaitable(result):
        return await result
    return result
