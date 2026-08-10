# -*- coding: utf-8 -*-
# Copyright (c) Huawei Technologies Co., Ltd. 2026-2026. All rights reserved.

import pytest

from custom.a2ui_model_client import A2UIModelGenerationError
from models.generation import CardSpec, ModelRequestContext, TaskSpec
from services.generation_execution import (
    ArtifactAssemblyContext,
    GenerationExecutionInput,
    GenerationExecutionOptions,
    GenerationExecutionOutcome,
    GenerationExecutor,
)
from services.generation_pipeline import (
    DslProcessingContext,
    DslProcessingResult,
    DslProcessorKind,
    GenerationRoutePolicy,
)


class _ModelClient:
    model_failure_retry_count = 0

    def __init__(self) -> None:
        self.generate_calls = 0
        self.repair_calls = 0

    def generate(self, _prompt, _profile):
        self.generate_calls += 1
        return "first-source"

    def generate_repair(self, _prompt, _profile):
        self.repair_calls += 1
        return "repaired-source"

    def extract_genui_payload(self, text: str) -> str:
        return text


class _FailingModelClient(_ModelClient):
    def generate(self, _prompt, _profile):
        self.generate_calls += 1
        raise A2UIModelGenerationError("model failed")


class _Processor:
    def process(self, source_dsl, _context):
        return DslProcessingResult(
            source_dsl=source_dsl,
            standard_dsl=f"standard:{source_dsl}",
        )


class _Validator:
    def __init__(self) -> None:
        self.calls: list[str] = []

    def validate(self, artifact, _profile):
        self.calls.append(artifact.genui)
        if len(self.calls) == 1:
            return ["first result is invalid"]
        return []


def _execution_input(
    before_model_call,
    *,
    validation_failure_blocking: bool = False,
    validation_retry_enabled: bool = True,
) -> GenerationExecutionInput:
    card_spec = CardSpec(
        title="Weather",
        description="Current weather",
        suggestSize="2x2",
    )
    task_spec = TaskSpec(
        userQuery="Show weather",
        size="2x2",
        dataModelSchema={},
    )
    return GenerationExecutionInput(
        prompt=[
            {"role": "system", "content": "system"},
            {"role": "user", "content": "generate"},
        ],
        policy=GenerationRoutePolicy(
            operation="generateWidgetCard",
            protocol_profile_id="profile",
            backend="mep",
            processor_kind=DslProcessorKind.STANDARD_A2UI,
            source_format="a2ui",
            model_profile_id="model-profile",
            model_format="a2ui",
            validation_failure_blocking=validation_failure_blocking,
        ),
        processing_context=DslProcessingContext(
            size="2x2",
            card_spec=card_spec.model_dump(mode="json"),
            task_spec=task_spec.model_dump(mode="json"),
            protocol_profile={},
        ),
        artifact_context=ArtifactAssemblyContext(
            card_spec=card_spec,
            task_spec=task_spec,
            data_bindings=(),
            data_capabilities=(),
            event_candidates=(),
            asset_candidates=(),
            removed_capabilities=(),
            protocol_profile_id="profile",
            protocol_profile_version="1.0",
            capability_registry_version="registry-v1",
            generation_mode="create",
        ),
        protocol_profile={"id": "profile"},
        model_protocol_profile={"id": "model-profile", "format": "a2ui"},
        model_request_context=ModelRequestContext(
            session_id="session",
            interaction_id="interaction",
            device_id="device",
            country_code="CN",
            app_version="1.0",
            app_name="app",
        ),
        options=GenerationExecutionOptions(
            artifact_validation_enabled=True,
            model_failure_retry_enabled=False,
            validation_retry_enabled=validation_retry_enabled,
            max_repair_attempts=1,
        ),
        before_model_call=before_model_call,
    )


@pytest.mark.asyncio
async def test_executor_owns_conversion_validation_repair_and_artifact_assembly():
    model_client = _ModelClient()
    validator = _Validator()
    start_sizes: list[str] = []

    async def before_model_call(size):
        start_sizes.append(size)

    executor = GenerationExecutor(
        model_client_factory=lambda _policy, _context: model_client,
        validator_factory=lambda: validator,
        processor_resolver=lambda _kind: _Processor(),
    )

    result = await executor.execute(_execution_input(before_model_call))

    assert result.outcome == GenerationExecutionOutcome.READY
    assert result.artifact is not None
    assert result.artifact.genui == "standard:repaired-source"
    assert result.quality_repair_count == 1
    assert result.total_retry_count == 1
    assert model_client.generate_calls == 1
    assert model_client.repair_calls == 1
    assert validator.calls == ["standard:first-source", "standard:repaired-source"]
    assert start_sizes == ["2x2"]


@pytest.mark.asyncio
async def test_executor_returns_model_failed_without_validation_or_artifact():
    model_client = _FailingModelClient()
    validator = _Validator()
    start_sizes: list[str] = []

    async def before_model_call(size):
        start_sizes.append(size)

    executor = GenerationExecutor(
        model_client_factory=lambda _policy, _context: model_client,
        validator_factory=lambda: validator,
        processor_resolver=lambda _kind: _Processor(),
    )

    result = await executor.execute(_execution_input(before_model_call))

    assert result.outcome == GenerationExecutionOutcome.MODEL_FAILED
    assert result.artifact is None
    assert result.total_retry_count == 0
    assert model_client.generate_calls == 1
    assert model_client.repair_calls == 0
    assert validator.calls == []
    assert start_sizes == ["2x2"]


@pytest.mark.asyncio
async def test_executor_blocks_strict_route_after_validation_failure():
    model_client = _ModelClient()
    validator = _Validator()
    executor = GenerationExecutor(
        model_client_factory=lambda _policy, _context: model_client,
        validator_factory=lambda: validator,
        processor_resolver=lambda _kind: _Processor(),
    )

    result = await executor.execute(
        _execution_input(
            None,
            validation_failure_blocking=True,
            validation_retry_enabled=False,
        )
    )

    assert result.outcome == GenerationExecutionOutcome.QUALITY_BLOCKED
    assert result.artifact is None
    assert result.total_retry_count == 0
    assert model_client.generate_calls == 1
    assert model_client.repair_calls == 0
    assert validator.calls == ["standard:first-source"]


@pytest.mark.asyncio
async def test_executor_keeps_non_blocking_route_ready_after_validation_failure():
    model_client = _ModelClient()
    validator = _Validator()
    executor = GenerationExecutor(
        model_client_factory=lambda _policy, _context: model_client,
        validator_factory=lambda: validator,
        processor_resolver=lambda _kind: _Processor(),
    )

    result = await executor.execute(
        _execution_input(
            None,
            validation_failure_blocking=False,
            validation_retry_enabled=False,
        )
    )

    assert result.outcome == GenerationExecutionOutcome.READY
    assert result.artifact is not None
    assert result.artifact.genui == "standard:first-source"
    assert result.total_retry_count == 0
    assert model_client.generate_calls == 1
    assert model_client.repair_calls == 0
    assert validator.calls == ["standard:first-source"]
