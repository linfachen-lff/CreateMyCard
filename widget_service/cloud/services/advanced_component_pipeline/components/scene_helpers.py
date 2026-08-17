"""截图场景模板共用的小型、无业务布局构造函数。"""

from __future__ import annotations

from models.generation import TaskSpec

from ..models import ActionRef, BindingRef, DataShape, FieldProfile


def asset_src(asset_id: str, task_spec: TaskSpec) -> str:
    for candidate in task_spec.assetCandidates:
        if candidate.get("id") == asset_id and candidate.get("src"):
            return str(candidate["src"])
    raise ValueError(f"asset is not in TaskSpec or has no src: {asset_id}")


def first_asset_id(task_spec: TaskSpec, *terms: str) -> str:
    candidates = [item for item in task_spec.assetCandidates if item.get("id") and item.get("src")]
    for term in terms:
        lowered = term.lower()
        for candidate in candidates:
            text = f"{candidate.get('id', '')} {candidate.get('description', '')}".lower()
            if lowered in text:
                return str(candidate["id"])
    if candidates:
        return str(candidates[0]["id"])
    raise ValueError("advanced scene component requires an asset candidate")


def first_action(task_spec: TaskSpec, label: str) -> ActionRef:
    event = next((item for item in task_spec.eventCandidates if item.id), None)
    if event is None or event.id is None:
        raise ValueError("advanced scene component requires an event candidate")
    return ActionRef(event_id=event.id, label=label)


def field_by_terms(
    data_shape: DataShape,
    *terms: str,
    numeric: bool | None = None,
    fallback_index: int = 0,
) -> FieldProfile:
    candidates = data_shape.fields
    if numeric is True:
        candidates = [item for item in candidates if item.data_type in {"integer", "number"}]
    elif numeric is False:
        candidates = [item for item in candidates if item.data_type == "string"]
    for term in terms:
        lowered = term.lower()
        for field in candidates:
            if lowered in f"{field.name} {field.description}".lower():
                return field
    if not candidates:
        raise ValueError(f"no field matches terms={terms}")
    return candidates[min(fallback_index, len(candidates) - 1)]


def ref(field: FieldProfile) -> BindingRef:
    return BindingRef(path=field.path)


__all__ = ["asset_src", "field_by_terms", "first_action", "first_asset_id", "ref"]
