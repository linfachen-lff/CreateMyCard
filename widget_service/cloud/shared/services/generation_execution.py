# -*- coding: utf-8 -*-
# Copyright (c) Huawei Technologies Co., Ltd. 2026-2026. All rights reserved.
"""封装模型生成、DSL 转换、Artifact 校验、有限修复与产物组装。"""

import inspect
import time
import uuid
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from enum import StrEnum
from typing import Protocol

from anyio import to_thread

from app.logger import json_for_log, logger
from core.errors import ErrorCode
from custom.a2ui_model_client import (
    A2UIModelClient,
    A2UIModelGenerationError,
    require_generated_dsl,
)
from custom.model_runtime import ModelExecutionRuntime
from models.artifact import ArtifactMeta, GenerationPlan, WidgetArtifact
from models.capability import (
    AssetCapability,
    DataCapability,
    RemovedCapability,
)
from models.generation import (
    CandidateDataBinding,
    CardSpec,
    EventAction,
    ModelRequestContext,
    TaskSpec,
    WidgetSize,
)
from services.generation_pipeline import (
    DslProcessingContext,
    DslProcessingResult,
    DslProcessor,
    DslProcessorKind,
    GenerationRoutePolicy,
    QualityIssue,
    get_dsl_processor,
)
from services.prompt_builder import PromptBuilder
from services.retry_controller import RetryController
from services.validator import ArtifactValidator

_MODULE = "[Generation Service]"


class ModelClient(Protocol):
    """生成执行模块依赖的模型客户端能力。"""

    @property
    def model_failure_retry_count(self) -> int:
        ...

    def generate(
        self,
        prompt: list[dict[str, str]],
        protocol_profile: dict,
    ) -> str | Awaitable[str]:
        ...

    def generate_repair(
        self,
        prompt: list[dict[str, str]],
        protocol_profile: dict,
    ) -> str | Awaitable[str]:
        ...

    def extract_genui_payload(self, text: str) -> str:
        ...


class ArtifactValidation(Protocol):
    """生成执行模块依赖的 Artifact 校验能力。"""

    def validate(
        self,
        artifact: WidgetArtifact,
        protocol_profile: dict,
    ) -> list[str]:
        ...


ModelClientFactory = Callable[
    [GenerationRoutePolicy, ModelRequestContext],
    ModelClient,
]
ValidatorFactory = Callable[[], ArtifactValidation]
ProcessorResolver = Callable[[DslProcessorKind], DslProcessor]
BeforeModelCall = Callable[[WidgetSize], Awaitable[None]]


@dataclass(frozen=True)
class ArtifactAssemblyContext:
    """组装不可变 Artifact 所需的具名上下文。"""

    card_spec: CardSpec
    task_spec: TaskSpec
    data_bindings: tuple[CandidateDataBinding, ...]
    data_capabilities: tuple[DataCapability, ...]
    event_candidates: tuple[EventAction, ...]
    asset_candidates: tuple[AssetCapability, ...]
    removed_capabilities: tuple[RemovedCapability, ...]
    protocol_profile_id: str
    protocol_profile_version: str
    capability_registry_version: str
    generation_mode: str
    source_artifact_digest: str | None = None
    source_write_roots: tuple[str, ...] = ()


@dataclass(frozen=True)
class GenerationExecutionOptions:
    """一次生成请求固定使用的质量控制选项。"""

    artifact_validation_enabled: bool
    model_failure_retry_enabled: bool
    validation_retry_enabled: bool
    max_repair_attempts: int


@dataclass(frozen=True)
class GenerationExecutionInput:
    """一次受质量门禁约束的模型执行输入。"""

    prompt: list[dict[str, str]]
    policy: GenerationRoutePolicy
    processing_context: DslProcessingContext
    artifact_context: ArtifactAssemblyContext
    protocol_profile: dict
    model_protocol_profile: dict
    model_request_context: ModelRequestContext
    options: GenerationExecutionOptions
    before_model_call: BeforeModelCall | None = None


class GenerationExecutionOutcome(StrEnum):
    READY = "ready"
    MODEL_FAILED = "model_failed"
    QUALITY_BLOCKED = "quality_blocked"


@dataclass(frozen=True)
class GenerationExecutionResult:
    """生成执行模块对编排层暴露的最小结果。"""

    outcome: GenerationExecutionOutcome
    artifact: WidgetArtifact | None = None
    design_token: str | None = None
    model_failure_retry_count: int = 0
    quality_repair_count: int = 0

    @property
    def total_retry_count(self) -> int:
        return self.model_failure_retry_count + self.quality_repair_count


@dataclass
class _AttemptState:
    """单次调用独占的可变状态，不在并发请求之间共享。"""

    latest_processing_result: DslProcessingResult = field(
        default_factory=lambda: DslProcessingResult(source_dsl="")
    )
    model_call_phase: str = "initial"
    quality_repair_count: int = 0


class GenerationExecutor:
    """统一封装模型生成、转换、校验、修复和产物组装的深模块。"""

    def __init__(
        self,
        model_runtime: ModelExecutionRuntime | None = None,
        *,
        model_client_factory: ModelClientFactory | None = None,
        validator_factory: ValidatorFactory | None = None,
        processor_resolver: ProcessorResolver | None = None,
    ) -> None:
        self._model_runtime = model_runtime
        self._model_client_factory = model_client_factory or self._create_model_client
        self._validator_factory = validator_factory or ArtifactValidator
        self._processor_resolver = processor_resolver or get_dsl_processor

    async def execute(
        self,
        execution: GenerationExecutionInput,
    ) -> GenerationExecutionResult:
        """返回已通过门禁的 Artifact 或具名失败，不负责持久化。"""
        model_client = self._model_client_factory(
            execution.policy,
            execution.model_request_context,
        )
        retry_controller = RetryController()
        processor = self._processor_resolver(execution.policy.processor_kind)
        artifact_id = str(uuid.uuid4())
        state = _AttemptState()
        repair_prompt_type = self._repair_prompt_type(execution)

        async def generate_source_dsl() -> str:
            if execution.before_model_call is not None:
                await execution.before_model_call(execution.artifact_context.card_spec.suggestSize)
            logger.info(
                f"{_MODULE} model_source_generation_started "
                f"operation={execution.policy.operation}"
            )
            result = await self._resolve_model_result(
                model_client.generate(
                    execution.prompt,
                    execution.model_protocol_profile,
                )
            )
            return require_generated_dsl(result)

        async def repair_source_dsl(
            invalid_source_dsl: str,
            quality_errors: list[str],
        ) -> str:
            state.quality_repair_count += 1
            quality_error_payloads = [
                item.to_prompt_payload()
                for item in state.latest_processing_result.errors
            ]
            if len(quality_error_payloads) != len(quality_errors):
                raise RuntimeError("repair quality issue state is inconsistent")
            quality_error_stages = sorted(
                {item["stage"] for item in quality_error_payloads}
            )
            repair_prompt = PromptBuilder().build_repair(
                execution.prompt,
                invalid_source_dsl,
                quality_error_payloads,
                dsl_format=execution.policy.source_format,
            )
            logger.info(
                f"{_MODULE} a2ui_repair_started repair_prompt_type={repair_prompt_type} "
                f"operation={execution.policy.operation} "
                f"model_backend={execution.policy.backend} "
                f"source_format={execution.policy.source_format} "
                f"quality_error_stages={json_for_log(quality_error_stages)} "
                f"repair_attempt={state.quality_repair_count} "
                f"max_repair_attempts={execution.options.max_repair_attempts} "
                f"quality_error_count={len(quality_errors)}"
            )
            state.model_call_phase = "repair"
            result = await self._resolve_model_result(
                model_client.generate_repair(
                    repair_prompt,
                    execution.model_protocol_profile,
                )
            )
            return require_generated_dsl(result)

        def evaluate_source_dsl_sync(source_dsl: str) -> list[str]:
            processing_result = processor.process(
                source_dsl,
                execution.processing_context,
            )
            state.latest_processing_result = processing_result
            warnings = [
                item.repair_message()
                for item in processing_result.issues
                if item.severity == "warning"
            ]
            if warnings:
                logger.warning(
                    f"{_MODULE} dsl_processing_warnings "
                    f"operation={execution.policy.operation} "
                    f"warnings={json_for_log(warnings)}"
                )
            conversion_errors = [
                item.repair_message() for item in processing_result.errors
            ]
            if conversion_errors:
                logger.error(
                    f"{_MODULE} dsl_conversion_failed "
                    f"operation={execution.policy.operation} "
                    f"errors={json_for_log(conversion_errors)}"
                )
                return conversion_errors
            if not execution.options.artifact_validation_enabled:
                logger.info(
                    f"{_MODULE} artifact_validation_skipped "
                    f"operation={execution.policy.operation} "
                    "reason=enable_artifact_validation_false"
                )
                return []

            artifact = self._build_artifact(
                processing_result.standard_dsl,
                execution.artifact_context,
                artifact_id,
            )
            validation_errors = self._validator_factory().validate(
                artifact,
                execution.protocol_profile,
            )
            current_write_roots = {
                item.writeResultTo
                for item in execution.artifact_context.data_bindings
            }
            removed_roots = set(execution.artifact_context.source_write_roots)
            for removed_root in sorted(removed_roots - current_write_roots):
                if removed_root in processing_result.standard_dsl:
                    validation_errors.append(
                        f"removed data path remains in edited genui: {removed_root}"
                    )
            validation_issues = tuple(
                QualityIssue(
                    stage="validation",
                    code="ARTIFACT_VALIDATION_FAILED",
                    message=message,
                )
                for message in validation_errors
            )
            state.latest_processing_result = DslProcessingResult(
                source_dsl=processing_result.source_dsl,
                standard_dsl=processing_result.standard_dsl,
                issues=processing_result.issues + validation_issues,
            )
            return [item.repair_message() for item in validation_issues]

        async def evaluate_source_dsl(source_dsl: str) -> list[str]:
            return await to_thread.run_sync(evaluate_source_dsl_sync, source_dsl)

        try:
            retry_result = await retry_controller.run(
                generate_source_dsl,
                evaluate_source_dsl,
                retry_on_quality_failure=execution.options.validation_retry_enabled,
                max_repair_attempts=execution.options.max_repair_attempts,
                repair=repair_source_dsl,
            )
        except A2UIModelGenerationError as exc:
            model_retry_count = model_client.model_failure_retry_count
            logger.error(
                f"{_MODULE} a2ui_generation_failed phase={state.model_call_phase} "
                f"error_code={ErrorCode.A2UI_GENERATION_FAILED.value} "
                f"model_failure_retry_count={model_retry_count} "
                f"quality_repair_count={state.quality_repair_count} "
                f"exception_type={type(exc).__name__} validation_continued=false "
                "artifact_saved=false"
            )
            return GenerationExecutionResult(
                outcome=GenerationExecutionOutcome.MODEL_FAILED,
                model_failure_retry_count=model_retry_count,
                quality_repair_count=state.quality_repair_count,
            )

        source_dsl = retry_result.result
        genui = state.latest_processing_result.standard_dsl
        errors = tuple(retry_result.errors)
        model_retry_count = model_client.model_failure_retry_count
        total_retry_count = model_retry_count + retry_result.retryCount
        logger.info(
            f"{_MODULE} a2ui_generation_completed retry_count={total_retry_count} "
            f"model_failure_retry_count={model_retry_count} "
            "model_failure_retry_enabled="
            f"{json_for_log(execution.options.model_failure_retry_enabled)} "
            f"quality_repair_count={retry_result.retryCount} "
            "validation_failure_retry_enabled="
            f"{json_for_log(execution.options.validation_retry_enabled)} "
            f"initial_quality_error_count={len(retry_result.initialErrors)} "
            f"repair_attempted={json_for_log(retry_result.repairAttempted)} "
            f"repair_prompt_type={repair_prompt_type} "
            f"quality_error_count={len(errors)}"
        )
        conversion_failed = not genui.strip()
        validation_blocked = execution.policy.validation_failure_blocking and bool(errors)
        if conversion_failed or validation_blocked:
            failure_category = "conversion" if conversion_failed else "validation"
            logger.error(
                f"{_MODULE} strict_generation_validation_failed "
                f"failure_category={failure_category} "
                f"errors={json_for_log(errors)}"
            )
            return GenerationExecutionResult(
                outcome=GenerationExecutionOutcome.QUALITY_BLOCKED,
                model_failure_retry_count=model_retry_count,
                quality_repair_count=retry_result.retryCount,
            )
        if errors:
            logger.error(
                f"{_MODULE} a2ui_generation_validation_failed_non_blocking "
                f"protocol_profile_id={execution.protocol_profile['id']} "
                f"validation_error_code={ErrorCode.VALIDATION_FAILED.value} "
                f"retry_count={total_retry_count} "
                "validation_failure_retry_enabled="
                f"{json_for_log(execution.options.validation_retry_enabled)} "
                f"errors={json_for_log(errors)} proceeding_to_artifact_save=true"
            )

        design_token = None
        if execution.policy.stores_design_token:
            design_token = model_client.extract_genui_payload(source_dsl)
        artifact = self._build_artifact(
            genui,
            execution.artifact_context,
            artifact_id,
        )
        return GenerationExecutionResult(
            outcome=GenerationExecutionOutcome.READY,
            artifact=artifact,
            design_token=design_token,
            model_failure_retry_count=model_retry_count,
            quality_repair_count=retry_result.retryCount,
        )

    def _create_model_client(
        self,
        policy: GenerationRoutePolicy,
        request_context: ModelRequestContext,
    ) -> ModelClient:
        return A2UIModelClient(
            backend=policy.backend,
            runtime=self._model_runtime,
            request_context=request_context,
            operation_name=policy.operation,
        )

    @staticmethod
    async def _resolve_model_result(value: str | Awaitable[str]) -> str:
        if inspect.isawaitable(value):
            return await value
        return value

    @staticmethod
    def _repair_prompt_type(execution: GenerationExecutionInput) -> str:
        is_edit = execution.artifact_context.generation_mode == "edit"
        design_mode = "edit" if is_edit else "create"
        if execution.policy.processor_kind == DslProcessorKind.TERSE_NESTED2:
            return f"terse-dsl-nested-2-{design_mode}"
        if execution.policy.processor_kind == DslProcessorKind.DESIGN_COMPACT:
            return f"design-compact-{design_mode}"
        return design_mode

    @staticmethod
    def _build_artifact(
        genui: str,
        context: ArtifactAssemblyContext,
        artifact_id: str,
    ) -> WidgetArtifact:
        logger.info(
            f"{_MODULE} artifact_building "
            f"protocol_profile_id={context.protocol_profile_id} "
            f"protocol_profile_version={context.protocol_profile_version} "
            f"capability_registry_version={context.capability_registry_version} "
            f"data_capability_count={len(context.data_capabilities)} "
            f"event_candidate_count={len(context.event_candidates)} "
            f"asset_candidate_count={len(context.asset_candidates)} "
            f"removed_count={len(context.removed_capabilities)}"
        )
        return WidgetArtifact(
            genui=genui,
            cardSpec=context.card_spec.model_dump(mode="json", exclude_none=True),
            taskSpec=context.task_spec.model_dump(mode="json", exclude_none=True),
            effectiveCapabilities={
                "data": [item.id for item in context.data_capabilities],
                "event": [
                    item.model_dump(mode="json", exclude_none=True)
                    for item in context.event_candidates
                ],
                "asset": [item.id for item in context.asset_candidates],
            },
            removedCapabilities=list(context.removed_capabilities),
            generationPlan=GenerationPlan(
                candidateDataBindings=list(context.data_bindings),
                candidateEventCandidates=[
                    {
                        "capabilityId": item.id,
                        "action": {
                            "call": item.call,
                            "args": item.args,
                        },
                    }
                    for item in context.event_candidates
                ],
                candidateAssetIds=[item.id for item in context.asset_candidates],
            ),
            meta=ArtifactMeta(
                dslProtocolVersion=context.protocol_profile_version,
                protocolProfileId=context.protocol_profile_id,
                capabilityRegistryVersion=context.capability_registry_version,
                generationMode=context.generation_mode,
                artifactId=artifact_id,
                sourceArtifactDigest=context.source_artifact_digest,
                createdAt=int(time.time() * 1000),
            ),
        )
