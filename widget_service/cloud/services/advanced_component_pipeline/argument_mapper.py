"""把 TaskSpec 中已有数据和事件映射为已注册组件的 Invocation。"""

from __future__ import annotations

import json
from collections.abc import Awaitable, Callable
from typing import Any

from pydantic import BaseModel, ValidationError

from models.generation import TaskSpec

from .component_registry import get_component
from .models import DataShape, FieldProfile, UIBrief


def invocation_model(component_id: str) -> type[BaseModel]:
    return get_component(component_id).invocation_model


def build_argument_mapper_prompt(
    component_id: str,
    task_spec: TaskSpec,
    data_shape: DataShape,
    ui_brief: UIBrief,
) -> list[dict[str, str]]:
    model = invocation_model(component_id)
    payload = {
        "componentId": component_id,
        "uiBrief": ui_brief.model_dump(by_alias=True),
        "fields": [field.model_dump() for field in data_shape.fields],
        "eventCandidates": [
            event.model_dump(exclude_none=True) for event in task_spec.eventCandidates
        ],
        "assetCandidates": task_spec.assetCandidates,
        "invocationSchema": model.model_json_schema(),
    }
    return [
        {
            "role": "system",
            "content": (
                "你只负责为已选高级组件填写 Invocation JSON。"
                "BindingRef.path 必须来自 fields；action.event_id 必须来自 eventCandidates；"
                "字段说明要求使用资源时，资源 id 必须来自 assetCandidates；"
                "严格遵守 invocationSchema 的字段说明和类型约束；"
                "不得新增业务数据、事件、颜色、布局或组件。只输出 JSON 对象。"
            ),
        },
        {"role": "user", "content": json.dumps(payload, ensure_ascii=False)},
    ]


def map_arguments_offline(
    component_id: str,
    task_spec: TaskSpec,
    data_shape: DataShape,
) -> BaseModel:
    """把离线映射委托给组件插件，主流程不包含组件特例。"""
    return get_component(component_id).map_offline(task_spec, data_shape)


def validate_invocation(
    component_id: str,
    invocation: BaseModel,
    task_spec: TaskSpec,
) -> None:
    """执行通用引用白名单校验，再执行插件自己的槽位校验。"""
    dumped = invocation.model_dump()
    valid_paths = {field.path for field in _iter_fields(task_spec.dataModelSchema)}
    valid_events = {event.id for event in task_spec.eventCandidates if event.id}

    def visit(value: Any) -> None:
        if isinstance(value, dict):
            if "path" in value and value["path"] not in valid_paths:
                raise ValueError(f"binding path is not in TaskSpec: {value['path']}")
            if "event_id" in value and value["event_id"] not in valid_events:
                raise ValueError(f"event is not in TaskSpec: {value['event_id']}")
            for item in value.values():
                visit(item)
        elif isinstance(value, list):
            for item in value:
                visit(item)

    visit(dumped)
    get_component(component_id).validate(invocation, task_spec)


def _iter_fields(schema: Any, path: str = "") -> list[FieldProfile]:
    result: list[FieldProfile] = []
    if isinstance(schema, dict) and {"type", "description"}.issubset(schema):
        result.append(
            FieldProfile(
                path=path,
                name=path.rsplit("/", 1)[-1],
                data_type=str(schema["type"]),
                description=str(schema["description"]),
            )
        )
    elif isinstance(schema, dict):
        for key, value in schema.items():
            child = f"{path}/{key}" if path else f"/{key}"
            result.extend(_iter_fields(value, child))
    elif isinstance(schema, list) and schema:
        result.extend(_iter_fields(schema[0], f"{path}/0"))
    return result


async def map_arguments_with_llm(
    component_id: str,
    task_spec: TaskSpec,
    data_shape: DataShape,
    ui_brief: UIBrief,
    generate_json: Callable[[list[dict[str, str]], str], Awaitable[dict[str, Any]]],
) -> BaseModel:
    raw = await generate_json(
        build_argument_mapper_prompt(component_id, task_spec, data_shape, ui_brief),
        "advanced-argument-map",
    )
    try:
        invocation = invocation_model(component_id).model_validate(raw)
    except ValidationError as exc:
        raise ValueError(f"invalid component invocation: {exc}") from exc
    validate_invocation(component_id, invocation, task_spec)
    return invocation
