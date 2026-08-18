"""Compact JSONL validation and safe payload binding."""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Literal, NoReturn

from api_schema import JSONArray, JSONObject, JSONValue

from .errors import BindingError, InvalidSearchRequest, TemplateValidationError
from .json_boundary import loads_strict_json

ValidationMode = Literal["reference", "rendered"]

_CONTAINER_TYPES = {"column", "row", "stack", "grid", "list"}
_PATH_TARGET_TYPES: dict[tuple[str, str], tuple[type, ...]] = {
    ("text", "content"): (str, int, float, bool),
    ("image", "src"): (str,),
    ("button", "label"): (str,),
    ("button", "enabled"): (bool,),
    ("radio", "value"): (str, int, float, bool),
    ("radio", "checked"): (bool,),
    ("radio", "group"): (str,),
    ("textinput", "text"): (str,),
    ("textinput", "placeholder"): (str,),
    ("textinput", "enabled"): (bool,),
    ("textinput", "maxlength"): (int,),
    ("toggle", "label"): (str,),
    ("toggle", "ison"): (bool,),
    ("toggle", "enabled"): (bool,),
    ("progress", "value"): (int, float),
    ("progress", "total"): (int, float),
    ("checkbox", "label"): (str,),
    ("checkbox", "group"): (str,),
    ("checkbox", "select"): (bool,),
    ("checkbox", "value"): (str, int, float, bool),
    ("web", "url"): (str,),
    ("navigation", "currentindex"): (int,),
    ("navigation", "title"): (str,),
    ("tabs", "barposition"): (str,),
    ("tabs", "vertical"): (bool,),
    ("tabs", "scrollable"): (bool,),
    ("tabs", "tabindex"): (int,),
    ("tabcontent", "title"): (str,),
    ("tabcontent", "icon"): (str,),
    ("tabcontent", "selectedsrc"): (str,),
    ("select", "options"): (list,),
    ("select", "selected"): (int, str),
    ("select", "value"): (str, int, float, bool),
}


@dataclass(frozen=True)
class PathReference:
    component_id: str
    component_type: str
    property_name: str
    path: str
    line_index: int
    relative: bool
    accepted_types: tuple[type, ...]


@dataclass(frozen=True)
class DynamicListReference:
    component_id: str
    item_component_id: str
    path: str
    line_index: int


@dataclass(frozen=True)
class ValidatedTemplate:
    lines: tuple[JSONArray, ...]
    path_references: tuple[PathReference, ...]
    dynamic_lists: tuple[DynamicListReference, ...]
    normalized_jsonl: str


def _fail(code: str, message: str, *, pointer: str | None = None) -> NoReturn:
    raise TemplateValidationError(code, message, pointer=pointer)


def _validate_pointer_escape(path: str) -> None:
    index = 0
    while index < len(path):
        if path[index] == "~":
            if index + 1 >= len(path) or path[index + 1] not in {"0", "1"}:
                _fail("invalid_path", f"invalid JSON Pointer escape in {path!r}")
            index += 2
            continue
        index += 1


def validate_absolute_pointer(path: str) -> None:
    if not path.startswith("/"):
        _fail("invalid_path", f"absolute path must start with '/': {path!r}")
    _validate_pointer_escape(path)


def validate_relative_pointer(path: str) -> None:
    if not path or path.startswith("/") or path in {".", ".."}:
        _fail("invalid_relative_path", f"invalid relative item path: {path!r}")
    _validate_pointer_escape(path)


def _parse_jsonl(jsonl: str) -> list[JSONArray]:
    if not isinstance(jsonl, str) or not jsonl.strip():
        _fail("empty_jsonl", "Compact JSONL must be non-empty")
    lines: list[JSONArray] = []
    for line_number, raw_line in enumerate(jsonl.splitlines(), start=1):
        stripped = raw_line.strip()
        if not stripped:
            continue
        try:
            parsed = loads_strict_json(stripped)
        except InvalidSearchRequest as exc:
            _fail("invalid_jsonl", f"line {line_number}: {exc}")
        if not isinstance(parsed, list):
            _fail("invalid_jsonl", f"line {line_number} must be a JSON array")
        lines.append(parsed)
    if not lines:
        _fail("empty_jsonl", "Compact JSONL must contain at least one line")
    return lines


def _scan_forbidden(value: JSONValue, *, location: str) -> None:
    if isinstance(value, dict):
        for key, child in value.items():
            if key in {"$bind", "$format"}:
                _fail("private_binding", f"{location} contains forbidden {key}")
            _scan_forbidden(child, location=f"{location}/{key}")
    elif isinstance(value, list):
        for index, child in enumerate(value):
            _scan_forbidden(child, location=f"{location}/{index}")
    elif isinstance(value, str) and ("{{" in value or "}}" in value):
        _fail(
            "unresolved_placeholder", f"{location} contains an unresolved placeholder"
        )


def _collect_path_wrappers(
    value: JSONValue, *, top_property: str | None = None
) -> list[tuple[str, str]]:
    found: list[tuple[str, str]] = []
    if isinstance(value, dict):
        if "path" in value:
            if set(value) != {"path"} or not isinstance(value["path"], str):
                _fail(
                    "invalid_path_wrapper",
                    "path wrappers must be exactly {'path': string}",
                )
            if top_property is None:
                _fail(
                    "invalid_path_target", "path wrapper is not attached to a property"
                )
            found.append((top_property, value["path"]))
            return found
        for key, child in value.items():
            found.extend(
                _collect_path_wrappers(
                    child,
                    top_property=top_property if top_property is not None else key,
                )
            )
    elif isinstance(value, list):
        for child in value:
            found.extend(_collect_path_wrappers(child, top_property=top_property))
    return found


def _component_parts(
    line: JSONArray, line_index: int
) -> tuple[str, str, JSONObject, JSONValue | None]:
    if len(line) not in {3, 4}:
        _fail("invalid_component", f"line {line_index + 1} must have 3 or 4 fields")
    component_id, component_type = line[0], line[1]
    if (
        not isinstance(component_id, str)
        or not component_id
        or component_id.startswith("/")
    ):
        _fail("invalid_component_id", f"line {line_index + 1} has invalid component id")
    if not isinstance(component_type, str) or not component_type:
        _fail(
            "invalid_component_type",
            f"line {line_index + 1} has invalid component type",
        )
    third = line[2]
    if isinstance(third, dict):
        props = third
    elif isinstance(third, list) and len(line) == 3:
        props = {}
    else:
        _fail(
            "invalid_component_props", f"line {line_index + 1} props must be an object"
        )
    children = (
        line[3] if len(line) == 4 else (third if isinstance(third, list) else None)
    )
    return component_id, component_type, props, children


def validate_template(  # noqa: C901, PLR0912, PLR0915 - Compact protocol validator
    jsonl: str, *, mode: ValidationMode
) -> ValidatedTemplate:
    """Validate a reference skeleton or a payload-bound rendered template."""

    lines = _parse_jsonl(jsonl)
    components: dict[str, tuple[str, int, JSONObject, JSONValue | None]] = {}
    data_rows: dict[str, tuple[int, JSONValue]] = {}
    static_graph: dict[str, list[str]] = {}
    dynamic_lists: list[DynamicListReference] = []

    for line_index, line in enumerate(lines):
        if line and isinstance(line[0], str) and line[0].startswith("/"):
            if len(line) != 2:
                _fail(
                    "invalid_data_row",
                    f"line {line_index + 1} data rows have two fields",
                )
            validate_absolute_pointer(line[0])
            if line[0] in data_rows:
                _fail("duplicate_data_path", f"duplicate data row for {line[0]}")
            data_rows[line[0]] = (line_index, line[1])
            continue

        _scan_forbidden(line, location=f"line/{line_index + 1}")
        component_id, component_type, props, children = _component_parts(
            line, line_index
        )
        if component_id in components:
            _fail("duplicate_component_id", f"duplicate component id {component_id}")
        components[component_id] = (component_type, line_index, props, children)
        static_graph[component_id] = []

        if children is None:
            continue
        if isinstance(children, list):
            # LOCAL PATCH: Button 也允许 list children（见 VENDORED.md 补丁说明）
            if component_type.lower() not in _CONTAINER_TYPES and (
                component_type.lower() != "button"
            ):
                _fail(
                    "unsupported_children",
                    f"{component_type} cannot have tuple children",
                )
            if not all(isinstance(child, str) and child for child in children):
                _fail("invalid_children", "static children must be list[str]")
            static_graph[component_id] = [
                child for child in children if isinstance(child, str)
            ]
        elif isinstance(children, dict):
            if component_type.lower() != "list":
                _fail("dynamic_children_non_list", "only List accepts dynamic children")
            if set(children) != {"componentId", "path"}:
                _fail(
                    "invalid_dynamic_list",
                    "dynamic List children require componentId and path only",
                )
            item_id, path = children.get("componentId"), children.get("path")
            if not isinstance(item_id, str) or not item_id or not isinstance(path, str):
                _fail(
                    "invalid_dynamic_list",
                    "dynamic List children values must be strings",
                )
            validate_absolute_pointer(path)
            dynamic_lists.append(
                DynamicListReference(component_id, item_id, path, line_index)
            )
        else:
            _fail(
                "invalid_children",
                "children must be list[str] or a List binding object",
            )

    component_order = [line[0] for line in lines if line and line[0] in components]
    if not component_order or component_order[0] != "root":
        _fail("missing_root", "the first component line must define root")
    for parent, child_ids in static_graph.items():
        for child in child_ids:
            if child not in components:
                _fail(
                    "missing_child_component",
                    f"{parent} references undefined child {child}",
                )
    # LOCAL PATCH: Button 子节点必须是恰好一个 Image（镜像转换器 _validate_button_image_children）。
    # 见 VENDORED.md 补丁说明。
    for parent, child_ids in static_graph.items():
        parent_component = components.get(parent)
        if parent_component is None or parent_component[0].lower() != "button":
            continue
        if not child_ids:
            continue
        if len(child_ids) != 1:
            _fail(
                "unsupported_children",
                f"Button supports at most one Image child, got {len(child_ids)}",
            )
        child_component = components.get(child_ids[0])
        child_type = child_component[0].lower() if child_component else ""
        if child_type != "image":
            _fail(
                "unsupported_children",
                f"Button child must be an Image, got {child_type}",
            )
    for dynamic in dynamic_lists:
        if dynamic.item_component_id not in components:
            _fail(
                "missing_item_component",
                f"List {dynamic.component_id} references undefined item component",
            )

    dynamic_scope: dict[str, str] = {}
    for dynamic in dynamic_lists:
        stack = [dynamic.item_component_id]
        while stack:
            current = stack.pop()
            previous = dynamic_scope.get(current)
            if previous is not None and previous != dynamic.path:
                _fail(
                    "shared_item_template",
                    f"component {current} belongs to two dynamic Lists",
                )
            if previous == dynamic.path:
                continue
            dynamic_scope[current] = dynamic.path
            stack.extend(static_graph.get(current, []))

    path_references: list[PathReference] = []
    for component_id, (
        component_type,
        line_index,
        props,
        _children,
    ) in components.items():
        for property_name, path in _collect_path_wrappers(props):
            accepted = _PATH_TARGET_TYPES.get(
                (component_type.lower(), property_name.lower())
            )
            if accepted is None:
                _fail(
                    "unsupported_path_target",
                    f"{component_type}.{property_name} does not support path binding",
                )
            relative = component_id in dynamic_scope
            if relative:
                validate_relative_pointer(path)
            else:
                validate_absolute_pointer(path)
            path_references.append(
                PathReference(
                    component_id,
                    component_type,
                    property_name,
                    path,
                    line_index,
                    relative,
                    accepted,
                )
            )

    expected_data = {ref.path for ref in path_references if not ref.relative}
    expected_data.update(dynamic.path for dynamic in dynamic_lists)
    if mode == "reference" and data_rows:
        _fail("reference_contains_data", "reference_jsonl must not contain data rows")
    if mode == "rendered":
        if set(data_rows) != expected_data:
            missing = sorted(expected_data - set(data_rows))
            extra = sorted(set(data_rows) - expected_data)
            _fail(
                "rendered_data_mismatch",
                f"rendered data rows mismatch; missing={missing}, extra={extra}",
            )
        first_by_path: dict[str, int] = {}
        for ref in path_references:
            if not ref.relative:
                first_by_path.setdefault(ref.path, ref.line_index)
        for path, component_index in first_by_path.items():
            if data_rows[path][0] != component_index + 1:
                # Multiple distinct paths on one component may occupy consecutive rows.
                siblings = [
                    candidate
                    for candidate, index in first_by_path.items()
                    if index == component_index
                ]
                expected_indices = range(
                    component_index + 1, component_index + 1 + len(siblings)
                )
                if data_rows[path][0] not in expected_indices:
                    _fail(
                        "invalid_data_order",
                        f"data row {path} must follow its first component reference",
                    )
        for dynamic in dynamic_lists:
            if data_rows[dynamic.path][0] != dynamic.line_index - 1:
                _fail(
                    "invalid_array_data_order",
                    f"array data row {dynamic.path} must immediately precede its List",
                )

    normalized = "\n".join(
        json.dumps(line, ensure_ascii=False, separators=(",", ":")) for line in lines
    )
    return ValidatedTemplate(
        lines=tuple(lines),
        path_references=tuple(path_references),
        dynamic_lists=tuple(dynamic_lists),
        normalized_jsonl=normalized + "\n",
    )


def _unescape(segment: str) -> str:
    return segment.replace("~1", "/").replace("~0", "~")


def resolve_absolute_pointer(document: JSONValue, path: str) -> JSONValue:
    validate_absolute_pointer(path)
    current = document
    for encoded in path[1:].split("/"):
        segment = _unescape(encoded)
        if isinstance(current, dict):
            if segment not in current:
                raise BindingError("path_missing", f"missing path {path}", pointer=path)
            current = current[segment]
        elif isinstance(current, list):
            if not segment.isdigit():
                raise BindingError(
                    "path_missing", f"invalid array index in {path}", pointer=path
                )
            index = int(segment)
            if index >= len(current):
                raise BindingError("path_missing", f"missing path {path}", pointer=path)
            current = current[index]
        else:
            raise BindingError("path_missing", f"missing path {path}", pointer=path)
    return current


def resolve_relative_pointer(document: JSONValue, path: str) -> JSONValue:
    validate_relative_pointer(path)
    current = document
    for encoded in path.split("/"):
        segment = _unescape(encoded)
        if isinstance(current, dict) and segment in current:
            current = current[segment]
        elif (
            isinstance(current, list)
            and segment.isdigit()
            and int(segment) < len(current)
        ):
            current = current[int(segment)]
        else:
            raise BindingError(
                "relative_path_missing", f"missing relative item path {path}"
            )
    return current


def _is_accepted(value: JSONValue, accepted: tuple[type, ...]) -> bool:
    if isinstance(value, bool):
        return bool in accepted
    if isinstance(value, int) and bool not in accepted and int not in accepted:
        return float in accepted
    return isinstance(value, accepted)


def bind_template(  # noqa: C901 - binding order and path cases are explicit
    reference_jsonl: str, input_data: JSONObject
) -> str:
    """Bind only referenced payload values and emit deterministic Compact JSONL."""

    template = validate_template(reference_jsonl, mode="reference")
    values: dict[str, JSONValue] = {}
    insert_after: dict[int, list[str]] = {}
    insert_before: dict[int, list[str]] = {}

    for dynamic in template.dynamic_lists:
        value = resolve_absolute_pointer(input_data, dynamic.path)
        if not isinstance(value, list) or not value:
            raise BindingError(
                "array_type_mismatch",
                f"List path {dynamic.path} must resolve to a non-empty array",
                pointer=dynamic.path,
            )
        values[dynamic.path] = value
        insert_before.setdefault(dynamic.line_index, []).append(dynamic.path)

    first_reference: dict[str, PathReference] = {}
    for reference in template.path_references:
        if reference.relative:
            list_path = next(
                scope.path
                for scope in template.dynamic_lists
                if reference.component_id == scope.item_component_id
                or reference.component_id
                in _descendants(template.lines, scope.item_component_id)
            )
            array_value = values[list_path]
            if not isinstance(array_value, list):
                raise BindingError(
                    "array_type_mismatch",
                    f"List path {list_path} must resolve to an array",
                    pointer=list_path,
                )
            for item in array_value:
                item_value = resolve_relative_pointer(item, reference.path)
                if not _is_accepted(item_value, reference.accepted_types):
                    raise BindingError(
                        "path_type_mismatch",
                        f"relative path {reference.path} has an unsupported value type",
                    )
            continue
        value = resolve_absolute_pointer(input_data, reference.path)
        if not _is_accepted(value, reference.accepted_types):
            raise BindingError(
                "path_type_mismatch",
                f"path {reference.path} has an unsupported value type for "
                f"{reference.component_type}.{reference.property_name}",
                pointer=reference.path,
            )
        values[reference.path] = value
        first_reference.setdefault(reference.path, reference)

    for path, reference in first_reference.items():
        insert_after.setdefault(reference.line_index, []).append(path)

    output: list[JSONArray] = []
    for line_index, line in enumerate(template.lines):
        for path in insert_before.get(line_index, []):
            output.append([path, values[path]])
        output.append(line)
        for path in insert_after.get(line_index, []):
            output.append([path, values[path]])
    rendered = (
        "\n".join(
            json.dumps(line, ensure_ascii=False, separators=(",", ":"))
            for line in output
        )
        + "\n"
    )
    validate_template(rendered, mode="rendered")
    return rendered


def _descendants(lines: tuple[JSONArray, ...], root_id: str) -> set[str]:
    graph: dict[str, list[str]] = {}
    for line in lines:
        if not line or not isinstance(line[0], str) or line[0].startswith("/"):
            continue
        children = line[3] if len(line) == 4 else None
        graph[line[0]] = (
            [child for child in children if isinstance(child, str)]
            if isinstance(children, list)
            else []
        )
    result: set[str] = set()
    stack = list(graph.get(root_id, []))
    while stack:
        current = stack.pop()
        if current in result:
            continue
        result.add(current)
        stack.extend(graph.get(current, []))
    return result
