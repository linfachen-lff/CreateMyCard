"""高级组件模板共用的 TerseDSL-Nested-2 构造函数。"""

from __future__ import annotations

import json
from typing import Any

from models.generation import TaskSpec

from ..models import ActionRef, BindingRef, DataShape, FieldProfile


def binding(ref: BindingRef) -> dict[str, str]:
    return {"path": ref.path}


def event_handler(action: ActionRef, task_spec: TaskSpec) -> list[dict[str, Any]]:
    for event in task_spec.eventCandidates:
        if event.id != action.event_id:
            continue
        handler: dict[str, Any] = {"call": event.call, "args": event.args}
        return [handler]
    raise ValueError(f"event not found: {action.event_id}")


def select_field(
    data_shape: DataShape,
    *,
    roles: tuple[str, ...] = (),
    terms: tuple[str, ...] = (),
    numeric: bool = False,
) -> FieldProfile:
    required = set(roles)
    candidates: list[tuple[int, str, FieldProfile]] = []
    for field in data_shape.fields:
        if not required.issubset(field.roles):
            continue
        if numeric and field.data_type not in {"integer", "number"}:
            continue
        text = f"{field.name} {field.description}".lower()
        score = sum(term.lower() in text for term in terms)
        candidates.append((-score, field.path, field))
    if not candidates:
        raise ValueError(f"no field matches roles={sorted(required)}")
    candidates.sort()
    return candidates[0][2]


def primary_action(task_spec: TaskSpec, label: str, icon: str) -> ActionRef:
    event = next((item for item in task_spec.eventCandidates if item.id), None)
    if event is None or event.id is None:
        raise ValueError("advanced component requires an event candidate")
    return ActionRef(event_id=event.id, label=label, icon=icon)


def validate_numeric_paths(paths: list[str], task_spec: TaskSpec) -> None:
    fields: dict[str, str] = {}

    def visit(node: Any, path: str) -> None:
        if isinstance(node, dict) and "type" in node:
            fields[path] = str(node["type"]).lower()
            return
        if isinstance(node, dict):
            for key, value in node.items():
                visit(value, f"{path}/{key}" if path else f"/{key}")
        elif isinstance(node, list) and node:
            visit(node[0], f"{path}/0")

    visit(task_spec.dataModelSchema, "")
    for path in paths:
        if fields.get(path) not in {"integer", "number"}:
            raise ValueError(
                f"advanced progress binding must be numeric: {path} "
                f"has type {fields.get(path, 'unknown')}"
            )


def sample_data(node: Any) -> Any:
    if isinstance(node, dict) and "type" in node:
        return node.get("sampleValue")
    if isinstance(node, dict):
        return {key: sample_data(value) for key, value in node.items()}
    if isinstance(node, list):
        return [sample_data(value) for value in node]
    return node


def root_props(tokens: dict[str, object]) -> dict[str, Any]:
    return {
        "width": 160,
        "height": 160,
        "padding": 8,
        "borderRadius": 20,
        "clip": True,
        "backgroundColor": tokens["background"],
        "linearGradient": tokens["gradient"],
        "itemMargin": 4,
    }


_DESIGN_PROPS: dict[str, dict[str, dict[str, Any]]] = {
    "Text": {
        "title-s": {"fontSize": 20, "fontWeight": 700},
        "subtitle-s": {"fontSize": 14, "fontWeight": 500},
        "body-s": {"fontSize": 12, "fontWeight": 400},
        "caption-m": {"fontSize": 10, "fontWeight": 500},
    },
    "Button": {
        "capsule": {
            "width": "matchParent",
            "height": 36,
            "borderRadius": 20,
            "padding": {"left": 8, "top": 0, "right": 8, "bottom": 0},
            "backgroundColor": "comp_background_tertiary",
            "fontColor": "font_emphasize",
            "fontSize": 14,
            "fontWeight": 500,
            "maxFontSize": 14,
            "minFontSize": 12,
            "maxLines": 1,
            "flexShrink": 0,
        },
    },
    "Progress": {
        "linear-bar": {
            "type": "linear",
            "width": "matchParent",
            "height": 8,
            "borderRadius": 4,
            "backgroundColor": "comp_background_secondary",
        },
        "ring": {
            "type": "ring",
            "width": "matchParent",
            "height": "matchParent",
            "strokeWidth": 6,
            "backgroundColor": "comp_background_secondary",
            "color": "multi_color_10",
        },
    },
}


def _literal(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, separators=(",", ":"))


def _component_call(component_id: str, rows_by_id: dict[str, list[Any]]) -> str:
    row = rows_by_id[component_id]
    component_type = row[1]
    props = dict(row[2])
    design = props.pop("design", None)
    if isinstance(design, str):
        props = {**_DESIGN_PROPS.get(component_type, {}).get(design, {}), **props}
    if component_id != "root":
        props["_id"] = component_id
    child_ids = row[3] if len(row) > 3 else []
    values: list[str] = []

    if component_type in {"Row", "Column", "List", "Stack"}:
        if component_id == "root":
            values.append(_literal("card"))
            props.pop("width", None)
            props.pop("height", None)
        if props:
            values.append(_literal(props))
    elif component_type == "Text":
        values.append(_literal(props.pop("content")))
        if props:
            values.append(_literal(props))
    elif component_type == "Button":
        values.append(_literal(props.pop("label")))
        if props:
            values.append(_literal(props))
    elif component_type == "Image":
        values.append(_literal(props.pop("src")))
        if design:
            values.append(_literal(design))
        if props:
            values.append(_literal(props))
    else:
        if props:
            values.append(_literal(props))

    values.extend(_component_call(child_id, rows_by_id) for child_id in child_ids)
    return f"{component_type}({','.join(values)})"


def serialize(rows: list[list[Any]], task_spec: TaskSpec) -> str:
    """把模板的内部行结构编译为一个直接嵌套的 TerseDSL-Nested-2 调用树。"""
    rows_by_id = {str(row[0]): row for row in rows if not str(row[0]).startswith("/")}
    if "root" not in rows_by_id:
        raise ValueError("advanced component template must define root")
    data = sample_data(task_spec.dataModelSchema.get("data", {}))
    return _component_call("root", rows_by_id) + ";\ndata = " + _literal(data) + ";"


def serialize_compact(rows: list[list[Any]], task_spec: TaskSpec) -> str:
    """恢复高级组件最初使用的 Design Compact 行格式。"""
    output = [list(row) for row in rows]
    output.append(["/data", sample_data(task_spec.dataModelSchema.get("data", {}))])
    return "\n".join(_literal(row) for row in output)
