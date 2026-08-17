"""同一高级组件模板的 TerseDSL 与标准 A2UI 双输出编译器。"""

from typing import Literal

from pydantic import BaseModel

from models.generation import TaskSpec

from .component_registry import get_component
from .components.base import serialize
from .styles import STYLE_TOKENS

AdvancedOutputFormat = Literal["terse", "a2ui"]


def _build_rows(
    component_id: str,
    invocation: BaseModel,
    task_spec: TaskSpec,
    style_id: str,
) -> list[list[object]]:
    plugin = get_component(component_id)
    if not isinstance(invocation, plugin.invocation_model):
        raise ValueError(f"invocation does not match component {component_id}")
    return plugin.build_rows(invocation, STYLE_TOKENS[style_id], task_spec)


def build_terse_nested2(
    component_id: str,
    invocation: BaseModel,
    task_spec: TaskSpec,
    style_id: str,
) -> str:
    return serialize(_build_rows(component_id, invocation, task_spec, style_id), task_spec)


def build_standard_a2ui(
    component_id: str,
    invocation: BaseModel,
    task_spec: TaskSpec,
    style_id: str,
) -> str:
    """直接调用从 aesthetic_plan_a 移植的原始 A2UI build() 模板。"""
    plugin = get_component(component_id)
    if not isinstance(invocation, plugin.invocation_model):
        raise ValueError(f"invocation does not match component {component_id}")
    return plugin.build_a2ui(invocation, STYLE_TOKENS[style_id], task_spec)


def build_component_output(
    component_id: str,
    invocation: BaseModel,
    task_spec: TaskSpec,
    style_id: str,
    output_format: AdvancedOutputFormat,
) -> str:
    if output_format == "a2ui":
        return build_standard_a2ui(component_id, invocation, task_spec, style_id)
    return build_terse_nested2(component_id, invocation, task_spec, style_id)
