"""从 aesthetic_plan_a 移植的原始高级组件 A2UI 公共函数。"""

from __future__ import annotations

import json
from copy import deepcopy
from typing import Any

from models.generation import TaskSpec

from ..models import ActionRef, BindingRef
from .base import sample_data

CATALOG_ID = "ohos.a2ui.extended.catalog"


def binding_expression(binding: BindingRef) -> str:
    parts = [
        part.replace("~1", "/").replace("~0", "~") for part in binding.path.lstrip("/").split("/")
    ]
    expression = "$__dataModel"
    for part in parts:
        if part.isdigit():
            expression += f"[{part}]"
        elif part.replace("_", "").isalnum() and not part[0].isdigit():
            expression += "." + part
        else:
            expression += "[" + json.dumps(part, ensure_ascii=False) + "]"
    return "{{ " + expression + " }}"


def event_handler(action: ActionRef, task_spec: TaskSpec) -> list[dict[str, Any]]:
    for candidate in task_spec.eventCandidates:
        if candidate.id == action.event_id:
            handler: dict[str, Any] = {"call": candidate.call}
            if candidate.args:
                handler["args"] = deepcopy(candidate.args)
            return [handler]
    raise ValueError(f"event not found: {action.event_id}")


def root_styles(tokens: dict[str, object]) -> dict[str, Any]:
    gradient = tokens["rootGradient"]
    return {
        "width": 160,
        "height": 160,
        "padding": 8,
        "borderRadius": 20,
        "clip": True,
        "backgroundColor": gradient[0][0],
        "linearGradient": {"angle": 180, "colors": gradient},
        "shadow": {"offsetX": 0, "offsetY": 3, "radius": 8, "color": "#26000000"},
    }


def make_a2ui(components: list[dict[str, Any]], task_spec: TaskSpec) -> str:
    # 只适配当前服务的 A2UI 包络；模板的组件树、布局与样式保持原样。
    compatible_components = deepcopy(components)
    for component in compatible_components:
        component.pop("suppressResourceBackdrop", None)
        component.pop("iconChrome", None)
        component.pop("iconUseStyleColor", None)
        if component.get("id") == "root":
            component["styles"]["width"] = "matchParent"
            component["styles"]["height"] = "matchParent"
    data_model = sample_data(task_spec.dataModelSchema)
    lines = [
        {
            "version": "v0.9",
            "createSurface": {
                "surfaceId": "surface_card",
                "catalogId": CATALOG_ID,
                "width": 160,
                "height": 160,
            },
        },
        {
            "version": "v0.9",
            "updateComponents": {
                "surfaceId": "surface_card",
                "root": "root",
                "components": compatible_components,
            },
        },
        {
            "version": "v0.9",
            "updateDataModel": {
                "surfaceId": "surface_card",
                "path": "/",
                "value": data_model,
            },
        },
    ]
    return "\n".join(json.dumps(line, ensure_ascii=False, separators=(",", ":")) for line in lines)


_SEMANTIC_FIELDS: dict[str, set[str]] = {
    "Text": {"content"},
    "Image": {"src"},
    "Progress": {"value", "total"},
    "Button": {"label", "onClick"},
}
_CONTAINERS = {"Row", "Column", "Stack", "List"}


def _a2ui_value(value: Any) -> Any:
    if isinstance(value, dict) and set(value) == {"path"}:
        return f"{{{{ ${{{value['path']}}} }}}}"
    if isinstance(value, dict):
        return {key: _a2ui_value(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_a2ui_value(item) for item in value]
    return value


def rows_to_a2ui(rows: list[list[Any]], task_spec: TaskSpec) -> str:
    """将插件行模板直接编译成标准 A2UI，保证 Terse/A2UI 使用同一组件树。"""
    components: list[dict[str, Any]] = []
    for row in rows:
        component_id, component_type, raw_props = row[:3]
        props = deepcopy(raw_props)
        component: dict[str, Any] = {"id": component_id, "component": component_type}
        if len(row) > 3:
            component["children"] = list(row[3])
        styles: dict[str, Any] = {}
        semantic = _SEMANTIC_FIELDS.get(component_type, set())
        for key, value in props.items():
            value = _a2ui_value(value)
            if key in semantic or (key == "itemMargin" and component_type in _CONTAINERS):
                component[key] = value
            else:
                styles[key] = value
        if component_id == "root":
            styles["width"] = "matchParent"
            styles["height"] = "matchParent"
        if styles:
            component["styles"] = styles
        components.append(component)
    return make_a2ui(components, task_spec)


__all__ = [
    "binding_expression",
    "event_handler",
    "make_a2ui",
    "root_styles",
    "rows_to_a2ui",
]
