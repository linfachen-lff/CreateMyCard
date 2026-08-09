# -*- coding: utf-8 -*-
# Copyright (c) Huawei Technologies Co., Ltd. 2026-2026. All rights reserved.
"""Deterministically convert Design Compact DSL to standard A2UI NDJSON."""

from __future__ import annotations

import copy
import hashlib
import json
from dataclasses import dataclass
from typing import Any, Literal

ThemeMode = Literal["light", "dark"]

_A2UI_FORM_CATALOG_ID = "ohos.a2ui.extended.catalog.form"
_A2UI_ICON_BUTTON_LABEL = "\u200B"
_COMPONENT_TYPES = frozenset(
    {
        "Row",
        "Column",
        "List",
        "Stack",
        "Text",
        "Image",
        "Divider",
        "Progress",
        "Button",
        "ActionUnit",
        "RingUnit",
        "Checkbox",
    }
)
_CONTAINER_TYPES = frozenset({"Row", "Column", "List", "Stack"})
_SEMANTIC_FIELDS = {
    "Text": frozenset({"content"}),
    "Image": frozenset({"src"}),
    "Progress": frozenset({"value", "total"}),
    "Button": frozenset({"label", "enabled"}),
    "ActionUnit": frozenset({"label", "enabled"}),
    "Checkbox": frozenset({"label", "value", "select"}),
}
_COMPACT_ONLY_FIELDS = {
    "Progress": frozenset({"threshold"}),
}
_REQUIRED_FIELDS = {
    "Text": "content",
    "Image": "src",
    "Progress": "value",
}
_COMMON_STYLE_PROPERTIES = frozenset(
    {
        "alignSelf",
        "aspectRatio",
        "backgroundColor",
        "backgroundImage",
        "backgroundImageSizeWithStyle",
        "borderColor",
        "borderRadius",
        "borderWidth",
        "clip",
        "constraintSize",
        "flexShrink",
        "height",
        "layoutWeight",
        "linearGradient",
        "margin",
        "maxHeight",
        "maxWidth",
        "minHeight",
        "minWidth",
        "opacity",
        "padding",
        "shadow",
        "visibility",
        "width",
    }
)
_COMPONENT_STYLE_PROPERTIES = {
    "Text": frozenset(
        {
            "fontColor",
            "fontSize",
            "fontWeight",
            "maxFontSize",
            "maxLines",
            "minFontSize",
            "textAlign",
            "textOverflow",
        }
    ),
    "Image": frozenset({"fillColor", "objectFit"}),
    "Divider": frozenset({"color", "strokeWidth", "vertical"}),
    "Progress": frozenset({"color", "strokeWidth", "type"}),
    "Button": frozenset(
        {
            "backgroundColor",
            "borderRadius",
            "fontColor",
            "fontSize",
            "fontWeight",
            "maxFontSize",
            "maxLines",
            "minFontSize",
        }
    ),
    "Checkbox": frozenset(
        {
            "mark",
            "selectedColor",
            "shape",
            "unSelectedColor",
        }
    ),
    "Row": frozenset({"alignItems", "itemMargin", "justifyContent"}),
    "Column": frozenset({"alignItems", "itemMargin", "justifyContent"}),
    "List": frozenset({"listDirection", "scrollBar", "space"}),
    "Stack": frozenset({"alignContent"}),
}
_COMMON_COMPACT_PROPERTIES = frozenset({"design", "onClick"})
_ACTION_UNIT_PROPERTIES = frozenset({"state", "icon", "actionInk"})
_RING_UNIT_PROPERTIES = frozenset(
    {"state", "size", "value", "total", "centerIcon", "reading"}
)
_ACTION_UNIT_FORBIDDEN_SKIN_PROPERTIES = frozenset(
    {
        "backgroundColor",
        "borderColor",
        "borderRadius",
        "borderWidth",
        "color",
        "design",
        "fillColor",
        "fontColor",
        "fontSize",
        "fontWeight",
        "height",
        "layoutWeight",
        "linearGradient",
        "maxFontSize",
        "maxLines",
        "minFontSize",
        "opacity",
        "padding",
        "textAlign",
        "textOverflow",
        "width",
    }
)
_NUMBER_PROPERTIES = frozenset(
    {
        "borderRadius",
        "borderWidth",
        "flexShrink",
        "fontSize",
        "layoutWeight",
        "maxFontSize",
        "maxHeight",
        "maxLines",
        "maxWidth",
        "minFontSize",
        "minHeight",
        "minWidth",
        "opacity",
        "strokeWidth",
    }
)
_BOOLEAN_PROPERTIES = frozenset({"clip", "vertical"})
_STRING_PROPERTIES = frozenset(
    {
        "alignContent",
        "alignItems",
        "alignSelf",
        "backgroundImage",
        "backgroundImageSizeWithStyle",
        "listDirection",
        "objectFit",
        "scrollBar",
        "shape",
        "textAlign",
        "textOverflow",
        "type",
        "visibility",
        "state",
        "icon",
        "actionInk",
    }
)
_FORBIDDEN_PROPERTIES = frozenset({"action", "event", "submit_form"})
_FORBIDDEN_STRING_FRAGMENTS = ("{{", "$item", "$__dataModel")
_LEGACY_TOKEN_PREFIXES = (
    "padding_level",
    "corner_radius_level",
    "font_weight_",
)
_LEGACY_FONT_SIZE_TOKENS = frozenset(
    {
        "Display_L",
        "Display_M",
        "Display_S",
        "Title_L",
        "Title_M",
        "Title_S",
        "Subtitle_L",
        "Subtitle_M",
        "Subtitle_S",
        "Body_L",
        "Body_M",
        "Body_S",
        "Caption_L",
        "Caption_M",
    }
)
_TOKEN_AWARE_PROPERTIES = frozenset(
    {
        "borderRadius",
        "fontSize",
        "fontWeight",
        "height",
        "itemMargin",
        "margin",
        "maxHeight",
        "maxWidth",
        "minHeight",
        "minWidth",
        "padding",
        "space",
        "strokeWidth",
        "width",
    }
)
_COLOR_PROPERTIES = frozenset(
    {
        "backgroundColor",
        "borderColor",
        "color",
        "fillColor",
        "fontColor",
        "actionInk",
        "selectedColor",
        "shadowColor",
        "strokeColor",
        "unSelectedColor",
    }
)
_COLOR_TOKENS = {
    "font_primary": "#E5000000",
    "font_secondary": "#99000000",
    "font_tertiary": "#66000000",
    "font_emphasize": "#FF0A59F7",
    "font_on_primary": "#FFFFFFFF",
    "warning": "#FFE84026",
    "alert": "#FFED6F21",
    "confirm": "#FF64BB5C",
    "icon_primary": "#E5000000",
    "icon_secondary": "#99000000",
    "icon_tertiary": "#66000000",
    "icon_fourth": "#33000000",
    "icon_emphasize": "#FF0A59F7",
    "icon_on_primary": "#FFFFFFFF",
    "icon_on_secondary": "#99FFFFFF",
    "icon_on_tertiary": "#66FFFFFF",
    "icon_on_fourth": "#33FFFFFF",
    "background_primary": "#FFFFFFFF",
    "background_emphasize": "#FF0A59F7",
    "comp_background_list_card": "#FFFFFFFF",
    "comp_background_emphasize": "#FF0A59F7",
    "comp_background_tertiary": "#0C000000",
    "comp_background_secondary": "#19000000",
    "comp_background_primary_contrary": "#FFFFFFFF",
    "comp_divider": "#33000000",
    "container40": "#66000000",
    "primary50": "#7F000000",
    "multi_color_01": "#FF564AF7",
    "multi_color_02": "#FF46B1E3",
    "multi_color_03": "#FF61CFBE",
    "multi_color_04": "#FF64BB5C",
    "multi_color_05": "#FFA5D61D",
    "multi_color_06": "#FFAC49F5",
    "multi_color_07": "#FFE64566",
    "multi_color_08": "#FFE84026",
    "multi_color_09": "#FFED6F21",
    "multi_color_10": "#FFF9A01E",
    "multi_color_11": "#FFF7CE00",
    "multi_color_aux_01": "#FF8981F7",
    "multi_color_aux_02": "#FF86C5E3",
    "multi_color_aux_03": "#FF92D6CC",
    "multi_color_aux_04": "#FF92C48D",
    "multi_color_aux_05": "#FFBDDB69",
    "multi_color_aux_06": "#FFC386F0",
    "multi_color_aux_07": "#FFE67C92",
    "multi_color_aux_08": "#FFE87361",
    "multi_color_aux_09": "#FFED955F",
    "multi_color_aux_10": "#FFF9BC64",
    "multi_color_aux_11": "#FFF5DC62",
    "mask_primary": "#CC000000",
    "mask_secondary": "#99000000",
    "mask_tertiary": "#66000000",
    "mask_fourth": "#33000000",
    "mask_fifth": "#19000000",
    "mask_sixth": "#0C000000",
}
_ROOT_LINEAR_GRADIENT_PALETTES = (
    {
        "angle": 145,
        "colors": [["#FFFFFFFF", 0.0], ["#FFF4FBFF", 0.44], ["#FF86C5E3", 1.0]],
    },
    {
        "angle": 145,
        "colors": [["#FFFFFFFF", 0.0], ["#FFEAF9F3", 0.46], ["#FF8FDCCC", 1.0]],
    },
    {
        "angle": 145,
        "colors": [["#FFFFFFFF", 0.0], ["#FFF0FBF8", 0.44], ["#FF92D6CC", 1.0]],
    },
    {
        "angle": 145,
        "colors": [["#FFFFFFFF", 0.0], ["#FFFFF7CC", 0.46], ["#FFFFE066", 1.0]],
    },
    {
        "angle": 145,
        "colors": [["#FFFFFFFF", 0.0], ["#FFFFF1E6", 0.46], ["#FFFFC58F", 1.0]],
    },
    {
        "angle": 145,
        "colors": [["#FFFFFFFF", 0.0], ["#FFF5EFFF", 0.44], ["#FFCBB7FF", 1.0]],
    },
    {
        "angle": 145,
        "colors": [["#FFFFFFFF", 0.0], ["#FFFFEFF4", 0.44], ["#FFFFB8CA", 1.0]],
    },
    {
        "angle": 145,
        "colors": [["#FFFFFFFF", 0.0], ["#FFF2F8FF", 0.44], ["#FFBCD6FF", 1.0]],
    },
)
_TEXT_DESIGNS: dict[str, dict[str, Any]] = {
    "display-l": {"fontSize": 56, "fontWeight": 300},
    "display-m": {"fontSize": 48, "fontWeight": 300},
    "display-s": {"fontSize": 36, "fontWeight": 700},
    "title-l": {"fontSize": 30, "fontWeight": 700},
    "title-m": {"fontSize": 24, "fontWeight": 700},
    "title-s": {"fontSize": 20, "fontWeight": 700},
    "subtitle-l": {"fontSize": 18, "fontWeight": 500},
    "subtitle-m": {"fontSize": 16, "fontWeight": 500},
    "subtitle-s": {"fontSize": 14, "fontWeight": 500},
    "body-l": {"fontSize": 16, "fontWeight": 500},
    "body-m": {"fontSize": 14, "fontWeight": 400},
    "body-s": {"fontSize": 12, "fontWeight": 400},
    "caption-l": {"fontSize": 12, "fontWeight": 500},
    "caption-m": {"fontSize": 10, "fontWeight": 500},
    "card-title": {"fontSize": 14, "fontWeight": 500},
    "hero-value": {"fontSize": 28, "fontWeight": 700},
    "hero-label": {"fontSize": 12, "fontWeight": 400},
    "meta-text": {"fontSize": 12, "fontWeight": 400},
}
_BUTTON_DESIGNS: dict[str, dict[str, Any]] = {
    "capsule": {
        "width": "matchParent",
        "height": 30,
        "borderRadius": 15,
        "padding": {"left": 8, "top": 0, "right": 8, "bottom": 0},
        "backgroundColor": "#190A59F7",
        "fontColor": "font_emphasize",
        "fontSize": 14,
        "fontWeight": 700,
        "maxFontSize": 14,
        "minFontSize": 12,
        "maxLines": 1,
        "flexShrink": 0,
    },
    "icon-round": {
        "width": 30,
        "height": 30,
        "borderRadius": 15,
        "padding": 0,
        "backgroundColor": "comp_background_tertiary",
        "flexShrink": 0,
    },
}
_IMAGE_DESIGNS: dict[str, dict[str, Any]] = {
    "icon-lg": {
        "width": "matchParent",
        "height": "matchParent",
        "aspectRatio": 1.0,
        "borderRadius": 8,
        "objectFit": "cover",
        "clip": True,
        "flexShrink": 0,
    },
    "source-icon": {
        "width": 20,
        "height": 20,
        "objectFit": "contain",
        "flexShrink": 0,
    },
    "hero-icon": {
        "width": 36,
        "height": 36,
        "objectFit": "contain",
        "flexShrink": 0,
    },
}
_PROGRESS_DESIGNS: dict[str, dict[str, Any]] = {
    "linear-bar": {
        "type": "linear",
        "width": "matchParent",
        "height": 8,
        "borderRadius": 4,
        "backgroundColor": "comp_background_secondary",
    },
    "linear-bar-small": {
        "type": "linear",
        "width": "matchParent",
        "height": 4,
        "borderRadius": 2,
        "backgroundColor": "comp_background_secondary",
    },
    "segmented-bar": {
        "type": "linear",
        "width": "matchParent",
        "height": 8,
        "borderRadius": 4,
        "backgroundColor": "comp_background_secondary",
    },
    "threshold-bar": {
        "type": "linear",
        "width": "matchParent",
        "height": 20,
        "borderRadius": 10,
        "backgroundColor": "#6B7F91",
        "color": "#C8F000",
    },
    "ring": {
        "type": "ring",
        "width": "matchParent",
        "height": "matchParent",
        "strokeWidth": 6,
        "backgroundColor": "comp_background_secondary",
        "color": "multi_color_10",
    },
}
_DIVIDER_DESIGNS: dict[str, dict[str, Any]] = {
    "line": {
        "strokeWidth": 1,
        "vertical": False,
        "color": "comp_divider",
    },
    "bar": {
        "strokeWidth": 8,
        "vertical": False,
        "color": "comp_background_tertiary",
    },
}
_CHECKBOX_DESIGNS: dict[str, dict[str, Any]] = {
    "default": {
        "width": 20,
        "height": 20,
        "borderRadius": 10,
        "selectedColor": "#FF0A59F7",
        "unSelectedColor": "#66000000",
        "mark": {
            "strokeColor": "#FFFFFFFF",
            "size": 20,
            "strokeWidth": 2,
        },
        "shape": "circle",
    },
    "check": {
        "width": 16,
        "height": 16,
        "borderRadius": 4,
        "selectedColor": "icon_on_fourth",
        "unSelectedColor": "icon_tertiary",
        "mark": {
            "strokeColor": "icon_on_primary",
            "size": 16,
            "strokeWidth": 2,
        },
        "shape": "rounded_square",
    },
}
_COMPONENT_DESIGNS = {
    "Text": _TEXT_DESIGNS,
    "Image": _IMAGE_DESIGNS,
    "Button": _BUTTON_DESIGNS,
    "Progress": _PROGRESS_DESIGNS,
    "Divider": _DIVIDER_DESIGNS,
    "Checkbox": _CHECKBOX_DESIGNS,
}
_COMPACT_ROOT_DIMENSIONS = {
    "2x2": {"width": 160, "height": 160},
    "2x4": {"width": 320, "height": 160},
    "4x2": {"width": 320, "height": 160},
}
_A2UI_FALLBACK_DIMENSIONS = {
    "2x2": {"width": 160, "height": 160},
    "2x4": {"width": 320, "height": 160},
    "4x2": {"width": 320, "height": 160},
}
_RING_UNIT_STATE_ALIASES = {
    "center-icon": "center-icon",
    "without-reading": "center-icon",
    "center-text": "center-text",
    "center-reading": "center-text",
    "center-icon-below-text": "center-icon-below-text",
    "with-reading": "center-icon-below-text",
}
_RING_READING_TEXT_STYLES = {
    "fontSize": 12,
    "fontWeight": 700,
    "fontColor": "#E5000000",
    "maxLines": 1,
    "textOverflow": "ellipsis",
    "flexShrink": 0,
}


class CompactDslConversionError(ValueError):
    """Raised when valid A2UI cannot be derived from Compact DSL."""


@dataclass(frozen=True)
class ComponentRow:
    """One Compact DSL component tuple."""

    component_id: str
    component_type: str
    props: dict[str, Any]
    children: tuple[str, ...] = ()


@dataclass(frozen=True)
class DataRow:
    """One Compact DSL data tuple."""

    path: str
    value: Any


CompactRow = ComponentRow | DataRow


@dataclass(frozen=True)
class CompactDslContextValidation:
    """Deterministic validation result for TaskSpec and CardSpec usage."""

    warnings: tuple[str, ...] = ()


def normalize_compact_dsl_design_tokens(
    compact_dsl: str,
    *,
    theme: ThemeMode = "light",
) -> str:
    """Expand the design aliases defined by the current Design Compact prompt."""
    _validate_theme(theme)
    rows = _parse_compact_rows(compact_dsl)
    _validate_component_tree(rows)
    normalized_rows: list[list[Any]] = []

    for row in rows:
        if isinstance(row, DataRow):
            normalized_rows.append([row.path, copy.deepcopy(row.value)])
            continue
        normalized = _normalize_component(row)
        normalized_rows.append(_component_to_tuple(normalized))

    return _serialize_rows(normalized_rows)


def repair_compact_dsl_binding_paths(
    compact_dsl: str,
    *,
    task_spec: dict[str, Any],
    card_spec: dict[str, Any],
) -> str:
    """Repair unique data roots or safely inline unbacked local values."""
    rows = _parse_compact_rows(compact_dsl)
    components, data_rows = _validate_component_tree(rows)
    event_replacements = _event_handler_replacements(components, task_spec)
    schema = task_spec.get("dataModelSchema")
    if not isinstance(schema, dict):
        if event_replacements:
            return _serialize_repaired_rows(
                rows,
                event_replacements=event_replacements,
            )
        return compact_dsl

    component_paths = _component_binding_paths(components)
    paths = list(component_paths)
    paths.extend(row.path for row in data_rows)
    roots = _card_spec_data_roots(card_spec)
    data_values = {row.path: row.value for row in data_rows}
    path_replacements: dict[str, str] = {}
    literal_replacements: dict[str, Any] = {}
    for path in dict.fromkeys(paths):
        if _schema_node_at_path(schema, path) is not None:
            continue
        suffix = path
        if path == "/data" or path.startswith("/data/"):
            suffix = path[len("/data"):]
        candidates: set[str] = set()
        for root in roots:
            candidate = f"{root.rstrip('/')}{suffix}"
            if _schema_node_at_path(schema, candidate) is not None:
                candidates.add(candidate)
        if len(candidates) == 1:
            path_replacements[path] = candidates.pop()
            continue
        if not roots and path in component_paths and path in data_values:
            literal_replacements[path] = copy.deepcopy(data_values[path])

    if not path_replacements and not literal_replacements and not event_replacements:
        return compact_dsl
    return _serialize_repaired_rows(
        rows,
        path_replacements=path_replacements,
        literal_replacements=literal_replacements,
        event_replacements=event_replacements,
    )


def _serialize_repaired_rows(
    rows: list[CompactRow],
    *,
    path_replacements: dict[str, str] | None = None,
    literal_replacements: dict[str, Any] | None = None,
    event_replacements: dict[str, dict[str, Any]] | None = None,
) -> str:
    path_replacements = path_replacements or {}
    literal_replacements = literal_replacements or {}
    event_replacements = event_replacements or {}
    repaired_rows: list[list[Any]] = []
    for row in rows:
        if isinstance(row, DataRow):
            if row.path in literal_replacements:
                continue
            repaired_rows.append(
                [
                    path_replacements.get(row.path, row.path),
                    copy.deepcopy(row.value),
                ]
            )
            continue
        props = _replace_binding_paths(
            row.props,
            path_replacements,
            literal_replacements,
        )
        props = _replace_event_handlers(props, event_replacements)
        original_content = row.props.get("content")
        content = props.get("content")
        if row.component_type == "Text" and _is_path_binding(original_content):
            binding_path = original_content["path"]
            if binding_path in literal_replacements and not isinstance(content, str):
                props["content"] = str(content)
        repaired_rows.append(
            _component_to_tuple(
                ComponentRow(
                    row.component_id,
                    row.component_type,
                    props,
                    row.children,
                )
            )
        )
    return _serialize_rows(repaired_rows)


def validate_compact_dsl_context(
    compact_dsl: str,
    *,
    task_spec: dict[str, Any],
    card_spec: dict[str, Any],
) -> CompactDslContextValidation:
    """Validate model bindings, events and assets without another model call."""
    rows = _parse_compact_rows(compact_dsl)
    components, data_rows = _validate_component_tree(rows)
    normalized_components = [_normalize_component(row) for row in components]
    data_model = _build_data_model(data_rows)
    _validate_binding_paths(normalized_components, data_model)

    binding_paths = _component_binding_paths(normalized_components)
    data_model_schema = task_spec.get("dataModelSchema")
    if not isinstance(data_model_schema, dict):
        raise CompactDslConversionError(
            "TaskSpec.dataModelSchema must be an object."
        )
    _validate_binding_schema_types(
        binding_paths,
        data_model,
        data_model_schema,
    )
    _validate_data_capability_roots(binding_paths, card_spec)
    _validate_asset_candidates(normalized_components, task_spec)
    _validate_event_candidates(normalized_components, task_spec)

    warnings = _unused_data_capability_warnings(binding_paths, card_spec)
    return CompactDslContextValidation(warnings=tuple(warnings))


def convert_compact_dsl_to_a2ui(
    compact_dsl: str,
    *,
    size: str,
    protocol_profile: dict[str, Any],
    theme: ThemeMode = "light",
    surface_id: str = "surface_card",
) -> str:
    """Convert one Design Compact DSL card to standard three-message A2UI."""
    _validate_theme(theme)
    _validate_surface_id(surface_id)
    rows = _parse_compact_rows(compact_dsl)
    components, data_rows = _validate_component_tree(rows)
    _validate_compact_root_dimensions(components[0], size)

    normalized_components = [_normalize_component(row) for row in components]
    data_model = _build_data_model(data_rows)
    _validate_binding_paths(normalized_components, data_model)

    icon_round_button_ids = _button_ids_with_design(components, "icon-round")
    fallback_root_gradient = _fallback_root_linear_gradient(compact_dsl)
    converted_components = []
    for component in normalized_components:
        hide_label = component.component_id in icon_round_button_ids
        converted_components.extend(
            _convert_component_rows(
                component,
                hide_label=hide_label,
                fallback_root_gradient=fallback_root_gradient,
            )
        )
    surface_dimensions = _surface_dimensions(size, protocol_profile)
    version = str(protocol_profile.get("version") or "v0.9")
    messages = [
        {
            "version": version,
            "createSurface": {
                "surfaceId": surface_id,
                "catalogId": _A2UI_FORM_CATALOG_ID,
                "width": surface_dimensions["width"],
                "height": surface_dimensions["height"],
            },
        },
        {
            "version": version,
            "updateComponents": {
                "surfaceId": surface_id,
                "root": "root",
                "components": converted_components,
            },
        },
        {
            "version": version,
            "updateDataModel": {
                "surfaceId": surface_id,
                "path": "/",
                "value": data_model,
            },
        },
    ]
    return _serialize_rows(messages)


def _validate_theme(theme: str) -> None:
    if theme not in {"light", "dark"}:
        raise CompactDslConversionError(
            f'Unsupported compatibility theme "{theme}".'
        )


def _validate_surface_id(surface_id: str) -> None:
    if not isinstance(surface_id, str) or not surface_id.strip():
        raise CompactDslConversionError("surface_id must be a non-empty string.")


def _strip_optional_genui_fence(compact_dsl: str) -> str:
    text = compact_dsl.lstrip("\ufeff").strip()
    lines = text.splitlines()
    opening_index = _find_fence_opening(lines)
    if opening_index is None:
        return text

    closing_index = _find_fence_closing(lines, opening_index + 1)
    body_end = closing_index if closing_index is not None else len(lines)
    body = "\n".join(lines[opening_index + 1:body_end]).strip()
    if "```" in body:
        raise CompactDslConversionError(
            "Compact DSL must contain exactly one genui fence."
        )
    if closing_index is not None:
        _validate_no_additional_fence(lines[closing_index + 1:])
    return body


def _find_fence_opening(lines: list[str]) -> int | None:
    supported_openings = {
        "```",
        "```genui",
        "```json",
        "```text",
        "```designcompactdsl",
        "```design-compact-dsl",
    }
    for index, line in enumerate(lines):
        if line.strip().lower() in supported_openings:
            return index
    return None


def _find_fence_closing(lines: list[str], start: int) -> int | None:
    for index in range(start, len(lines)):
        if lines[index].strip() == "```":
            return index
    return None


def _validate_no_additional_fence(lines: list[str]) -> None:
    for line in lines:
        if line.strip().startswith("```"):
            raise CompactDslConversionError(
                "Compact DSL must contain exactly one genui fence."
            )


def _repair_compact_json_rows(compact_dsl: str) -> str:
    body = _strip_optional_genui_fence(compact_dsl)
    rows = _extract_top_level_array_rows(body)
    repaired_rows: list[str] = []
    for line_number, row in enumerate(rows, 1):
        repaired = _remove_trailing_json_commas(row)
        value = _parse_json_line(repaired, line_number)
        repaired_rows.append(
            json.dumps(value, ensure_ascii=False, separators=(",", ":"))
        )
    return "\n".join(repaired_rows)


def _extract_top_level_array_rows(body: str) -> list[str]:
    rows: list[str] = []
    current: list[str] = []
    expected_closers: list[str] = []
    outside: list[str] = []
    in_string = False
    escaped = False

    for char in body:
        if not expected_closers:
            if char == "[":
                _validate_text_between_rows(outside, bool(rows))
                outside = []
                current = [char]
                expected_closers = ["]"]
                in_string = False
                escaped = False
            else:
                outside.append(char)
            continue

        current.append(char)
        if in_string:
            if escaped:
                escaped = False
            elif char == "\\":
                escaped = True
            elif char == '"':
                in_string = False
            continue

        if char == '"':
            in_string = True
            continue
        if char in {"[", "{"}:
            expected_closers.append("]" if char == "[" else "}")
            continue
        if char not in {"]", "}"}:
            continue
        if char != expected_closers[-1]:
            raise CompactDslConversionError(
                "Compact DSL contains mismatched JSON delimiters."
            )
        expected_closers.pop()
        if not expected_closers:
            rows.append("".join(current))
            current = []

    if expected_closers:
        if in_string:
            raise CompactDslConversionError(
                "Compact DSL contains an unclosed JSON string."
            )
        current.extend(reversed(expected_closers))
        rows.append("".join(current))

    if not rows:
        raise CompactDslConversionError("Compact DSL output is empty.")
    return rows


def _validate_text_between_rows(outside: list[str], has_previous_row: bool) -> None:
    if not has_previous_row:
        return
    text = "".join(outside)
    for char in text:
        if not char.isspace() and char not in {"]", "}"}:
            raise CompactDslConversionError(
                "Compact DSL contains non-JSON text between rows."
            )


def _remove_trailing_json_commas(row: str) -> str:
    output: list[str] = []
    in_string = False
    escaped = False
    index = 0

    while index < len(row):
        char = row[index]
        if in_string:
            output.append(char)
            if escaped:
                escaped = False
            elif char == "\\":
                escaped = True
            elif char == '"':
                in_string = False
            index += 1
            continue

        if char == '"':
            in_string = True
            output.append(char)
            index += 1
            continue
        if char == "," and _next_non_whitespace_is_closer(row, index + 1):
            index += 1
            continue
        output.append(char)
        index += 1

    return "".join(output)


def _next_non_whitespace_is_closer(text: str, start: int) -> bool:
    for index in range(start, len(text)):
        if text[index].isspace():
            continue
        return text[index] in {"]", "}"}
    return False


def _parse_compact_rows(compact_dsl: str) -> list[CompactRow]:
    body = _repair_compact_json_rows(compact_dsl)
    rows: list[CompactRow] = []

    for line_number, raw_line in enumerate(body.splitlines(), 1):
        line = raw_line.strip()
        if not line:
            continue
        value = _parse_json_line(line, line_number)
        rows.append(_parse_row(value, line_number))

    if not rows:
        raise CompactDslConversionError("Compact DSL output is empty.")
    _validate_button_image_children(rows)
    visible_rows = _drop_empty_image_components(rows)
    return _canonicalize_component_order(visible_rows)


def _canonicalize_component_order(rows: list[CompactRow]) -> list[CompactRow]:
    components_by_id: dict[str, ComponentRow] = {}
    data_rows: list[DataRow] = []
    duplicate_ids: set[str] = set()

    for row in rows:
        if isinstance(row, DataRow):
            data_rows.append(row)
            continue
        if row.component_id in components_by_id:
            duplicate_ids.add(row.component_id)
        components_by_id[row.component_id] = row

    if duplicate_ids:
        return rows
    root = components_by_id.get("root")
    if root is None:
        return rows
    if root.component_type not in _CONTAINER_TYPES:
        return rows

    ordered_components: list[ComponentRow] = []
    visiting: set[str] = set()
    visited: set[str] = set()
    is_complete = _append_component_preorder(
        "root",
        components_by_id,
        ordered_components,
        visiting,
        visited,
    )
    if not is_complete:
        return rows
    return [*ordered_components, *data_rows]


def _append_component_preorder(
    component_id: str,
    components_by_id: dict[str, ComponentRow],
    ordered_components: list[ComponentRow],
    visiting: set[str],
    visited: set[str],
) -> bool:
    if component_id in visiting:
        return False
    if component_id in visited:
        return False
    component = components_by_id.get(component_id)
    if component is None:
        return False

    visiting.add(component_id)
    ordered_components.append(component)
    for child_id in component.children:
        child_added = _append_component_preorder(
            child_id,
            components_by_id,
            ordered_components,
            visiting,
            visited,
        )
        if not child_added:
            return False
    visiting.remove(component_id)
    visited.add(component_id)
    return True


def _parse_json_line(line: str, line_number: int) -> list[Any]:
    try:
        value = json.loads(line)
    except json.JSONDecodeError as exc:
        raise CompactDslConversionError(
            f"Compact DSL line {line_number} is invalid JSON: {exc.msg}."
        ) from exc
    if not isinstance(value, list):
        raise CompactDslConversionError(
            f"Compact DSL line {line_number} must be a JSON array."
        )
    return value


def _parse_row(value: list[Any], line_number: int) -> CompactRow:
    if _looks_like_data_row(value):
        path = value[0]
        _decode_json_pointer(path)
        _validate_source_value(value[1], f"data row {path}")
        return DataRow(path=path, value=copy.deepcopy(value[1]))
    if _looks_like_data_def_row(value):
        props = value[2]
        path = props.get("path", "/")
        _decode_json_pointer(path)
        _validate_source_value(props["value"], f"data row {path}")
        return DataRow(path=path, value=copy.deepcopy(props["value"]))
    return _parse_component_row(value, line_number)


def _looks_like_data_row(value: list[Any]) -> bool:
    if len(value) != 2:
        return False
    return isinstance(value[0], str) and value[0].startswith("/")


def _looks_like_data_def_row(value: list[Any]) -> bool:
    if len(value) != 3:
        return False
    if value[1] != "DataDef" or not isinstance(value[2], dict):
        return False
    path = value[2].get("path", "/")
    return isinstance(path, str) and "value" in value[2]


def _parse_component_row(value: list[Any], line_number: int) -> ComponentRow:
    value = _repair_legacy_component_row(value)
    if len(value) not in {3, 4}:
        raise CompactDslConversionError(
            f"Compact DSL line {line_number} has an unsupported row shape."
        )
    component_id, component_type, props = value[:3]
    component_type, props = _repair_legacy_component_props(
        component_id,
        component_type,
        props,
    )
    _validate_component_header(
        component_id,
        component_type,
        props,
        line_number,
    )
    children = _parse_children(value, component_id, component_type)
    if not _is_empty_image_component(component_type, props):
        _validate_component_props(component_id, component_type, props)
    return ComponentRow(
        component_id=component_id,
        component_type=component_type,
        props=copy.deepcopy(props),
        children=children,
    )


def _repair_legacy_component_row(value: list[Any]) -> list[Any]:
    if len(value) not in {3, 4}:
        return value
    props = value[2]
    if not isinstance(props, dict) or "children" not in props:
        return value

    repaired_props = copy.deepcopy(props)
    props_children = repaired_props.pop("children")
    repaired_value = [value[0], value[1], repaired_props]
    if len(value) == 4:
        repaired_value.append(value[3])
        return repaired_value
    if isinstance(props_children, list):
        repaired_value.append(props_children)
        return repaired_value

    repaired_props["children"] = props_children
    return repaired_value


def _repair_legacy_component_props(
    component_id: Any,
    component_type: Any,
    props: Any,
) -> tuple[Any, Any]:
    if not isinstance(props, dict):
        return component_type, props

    repaired_props = _repair_legacy_bindings(copy.deepcopy(props))
    repaired_type = component_type
    if isinstance(component_id, str) and component_id == "root":
        repaired_props.pop("size", None)
    if "flexGrow" in repaired_props:
        if "layoutWeight" not in repaired_props:
            repaired_props["layoutWeight"] = repaired_props["flexGrow"]
        repaired_props.pop("flexGrow", None)
    _repair_dimension_aliases(repaired_props)
    _repair_axis_value_aliases(repaired_type, repaired_props)

    _repair_spacing_aliases(repaired_type, repaired_props)
    if repaired_type == "Text":
        _repair_text_value_alias(repaired_props)
    if repaired_type == "Image":
        _drop_image_fill_color(repaired_props)
    if repaired_type == "Progress":
        _repair_progress_alias_props(repaired_props)
    if repaired_type == "Ring":
        repaired_type = "Progress"
        _repair_progress_alias_props(repaired_props, default_design="ring")
    _repair_on_click_aliases(repaired_props)
    return repaired_type, repaired_props


def _drop_image_fill_color(props: dict[str, Any]) -> None:
    props.pop("fillColor", None)


def _repair_on_click_aliases(props: dict[str, Any]) -> None:
    if "onClick" not in props:
        return
    normalized = _normalize_on_click_alias(props["onClick"])
    if normalized is not None:
        props["onClick"] = normalized


def _normalize_on_click_alias(value: Any) -> list[dict[str, Any]] | None:
    if isinstance(value, dict):
        return [copy.deepcopy(value)]
    if _is_on_click_pair(value):
        return [_on_click_pair_to_handler(value)]
    if isinstance(value, list):
        return _normalize_on_click_list(value)
    return None


def _is_on_click_pair(value: Any) -> bool:
    if not isinstance(value, list):
        return False
    if len(value) != 2:
        return False
    return isinstance(value[0], str) and isinstance(value[1], dict)


def _on_click_pair_to_handler(value: list[Any]) -> dict[str, Any]:
    args = copy.deepcopy(value[1])
    if set(args) == {"args"} and isinstance(args.get("args"), dict):
        args = copy.deepcopy(args["args"])
    return {"call": value[0], "args": args}


def _normalize_on_click_list(value: list[Any]) -> list[dict[str, Any]] | None:
    if _is_on_click_pair(value):
        return [_on_click_pair_to_handler(value)]
    normalized: list[dict[str, Any]] = []
    for item in value:
        if not isinstance(item, dict):
            return None
        normalized.append(copy.deepcopy(item))
    return normalized


def _repair_text_value_alias(props: dict[str, Any]) -> None:
    if "content" in props:
        return
    if "value" in props:
        props["content"] = props.pop("value")
    elif "text" in props:
        props["content"] = props.pop("text")


def _repair_progress_alias_props(
    props: dict[str, Any],
    *,
    default_design: str | None = None,
) -> None:
    if default_design is not None and "design" not in props and "type" not in props:
        props["design"] = default_design
    size = props.pop("size", None)
    if size is not None:
        if "width" not in props:
            props["width"] = size
        if "height" not in props:
            props["height"] = size
    _repair_progress_color_alias(props)


def _repair_progress_color_alias(props: dict[str, Any]) -> None:
    colors = props.pop("colors", None)
    if colors is None or "color" in props:
        return
    color = _first_progress_color(colors)
    if color is not None:
        props["color"] = color


def _first_progress_color(colors: Any) -> str | None:
    if not isinstance(colors, list) or not colors:
        return None
    first_color = colors[0]
    if isinstance(first_color, dict) and isinstance(first_color.get("color"), str):
        return first_color["color"]
    if isinstance(first_color, list) and first_color:
        color = first_color[0]
        if isinstance(color, str):
            return color
    return None


def _repair_dimension_aliases(props: dict[str, Any]) -> None:
    for dimension_name in ("width", "height"):
        if props.get(dimension_name) in {"100%", "stretch"}:
            props[dimension_name] = "matchParent"


def _repair_spacing_aliases(
    component_type: Any,
    props: dict[str, Any],
) -> None:
    if component_type in {"Row", "Column"} and "space" in props:
        if "itemMargin" not in props:
            props["itemMargin"] = props["space"]
        props.pop("space", None)
    elif component_type == "List" and "itemMargin" in props:
        if "space" not in props:
            props["space"] = props["itemMargin"]
        props.pop("itemMargin", None)


def _repair_axis_value_aliases(
    component_type: Any,
    props: dict[str, Any],
) -> None:
    justify_content = props.get("justifyContent")
    if justify_content == "space-between":
        props["justifyContent"] = "spaceBetween"
    elif justify_content == "space-around":
        props["justifyContent"] = "spaceAround"
    elif justify_content == "space-evenly":
        props["justifyContent"] = "spaceEvenly"
    elif justify_content == "flex-start":
        props["justifyContent"] = "start"
    elif justify_content == "flex-end":
        props["justifyContent"] = "end"

    align_items = props.get("alignItems")
    if component_type == "Row":
        if align_items in {"flex-start", "start"}:
            props["alignItems"] = "top"
        elif align_items in {"flex-end", "end"}:
            props["alignItems"] = "bottom"
    elif component_type == "Column":
        if align_items in {"flex-start", "top"}:
            props["alignItems"] = "start"
        elif align_items in {"flex-end", "bottom"}:
            props["alignItems"] = "end"


def _repair_legacy_bindings(value: Any) -> Any:
    if isinstance(value, dict):
        legacy_path = _legacy_binding_path(value)
        if legacy_path is not None:
            return {"path": legacy_path}
        repaired: dict[str, Any] = {}
        for key, child_value in value.items():
            repaired[key] = _repair_legacy_bindings(child_value)
        return repaired
    if isinstance(value, list):
        repaired_items: list[Any] = []
        for item in value:
            repaired_items.append(_repair_legacy_bindings(item))
        return repaired_items
    return value


def _legacy_binding_path(value: dict[str, Any]) -> str | None:
    if len(value) != 1:
        return None
    key, path = next(iter(value.items()))
    if not isinstance(key, str) or not isinstance(path, str):
        return None
    normalized_key = key.replace("\\", "").replace("(", "").replace(")", "")
    if "data" in normalized_key.lower() and path.startswith("/"):
        return path
    return None


def _validate_component_header(
    component_id: Any,
    component_type: Any,
    props: Any,
    line_number: int,
) -> None:
    if not isinstance(component_id, str) or not component_id:
        raise CompactDslConversionError(
            f"Compact DSL line {line_number} has an invalid component id."
        )
    if (
        not isinstance(component_type, str)
        or component_type not in _COMPONENT_TYPES
    ):
        raise CompactDslConversionError(
            f'{component_id}: unsupported component type "{component_type}".'
        )
    if not isinstance(props, dict):
        raise CompactDslConversionError(
            f"{component_id}: component props must be an object."
        )


def _parse_children(
    value: list[Any],
    component_id: str,
    component_type: str,
) -> tuple[str, ...]:
    is_container = component_type in _CONTAINER_TYPES
    if len(value) != 4:
        if is_container:
            raise CompactDslConversionError(
                f"{component_id}: {component_type} requires a children array."
            )
        return ()
    if not isinstance(value[3], list):
        raise CompactDslConversionError(
            f"{component_id}: children must be an array."
        )

    children: list[str] = []
    for child in value[3]:
        if not isinstance(child, str) or not child:
            raise CompactDslConversionError(
                f"{component_id}: every child id must be a non-empty string."
            )
        children.append(child)
    if len(children) != len(set(children)):
        raise CompactDslConversionError(
            f"{component_id}: children contain duplicate component ids."
        )
    if is_container or component_type == "Button":
        return tuple(children)
    if children:
        raise CompactDslConversionError(
            f"{component_id}: non-container components cannot have children."
        )
    return ()


def _validate_button_image_children(rows: list[CompactRow]) -> None:
    components_by_id = {
        row.component_id: row
        for row in rows
        if isinstance(row, ComponentRow)
    }
    button_icon_ids: set[str] = set()

    for row in rows:
        if not isinstance(row, ComponentRow):
            continue
        if row.component_type != "Button" or not row.children:
            continue
        if len(row.children) != 1:
            raise CompactDslConversionError(
                f"{row.component_id}: Button supports at most one Image child."
            )
        icon_id = row.children[0]
        icon = components_by_id.get(icon_id)
        if icon is None or icon.component_type != "Image":
            raise CompactDslConversionError(
                f"{row.component_id}: Button child must be an Image."
            )
        button_icon_ids.add(icon_id)

    if button_icon_ids:
        _validate_button_icon_ownership(rows, button_icon_ids)


def _drop_empty_image_components(rows: list[CompactRow]) -> list[CompactRow]:
    empty_image_ids = {
        row.component_id
        for row in rows
        if isinstance(row, ComponentRow)
        and _is_empty_image_component(row.component_type, row.props)
    }
    if not empty_image_ids:
        return rows

    visible_rows: list[CompactRow] = []
    for row in rows:
        if not isinstance(row, ComponentRow):
            visible_rows.append(row)
            continue
        if row.component_id in empty_image_ids:
            continue
        visible_rows.append(_without_children(row, empty_image_ids))
    return visible_rows


def _without_children(
    row: ComponentRow,
    removed_ids: set[str],
) -> ComponentRow:
    if not row.children:
        return row
    children = tuple(child_id for child_id in row.children if child_id not in removed_ids)
    if children == row.children:
        return row
    return ComponentRow(
        row.component_id,
        row.component_type,
        copy.deepcopy(row.props),
        children,
    )


def _is_empty_image_component(
    component_type: Any,
    props: Any,
) -> bool:
    if component_type != "Image" or not isinstance(props, dict):
        return False
    return props.get("src") == ""


def _validate_button_icon_ownership(
    rows: list[CompactRow],
    button_icon_ids: set[str],
) -> None:
    parent_counts = dict.fromkeys(button_icon_ids, 0)
    for row in rows:
        if not isinstance(row, ComponentRow):
            continue
        for child_id in row.children:
            if child_id in parent_counts:
                parent_counts[child_id] += 1
    shared_icons = [
        icon_id
        for icon_id, parent_count in parent_counts.items()
        if parent_count != 1
    ]
    if shared_icons:
        icon_list = ", ".join(sorted(shared_icons))
        raise CompactDslConversionError(
            f"Button Image children must have one parent: {icon_list}."
        )


def _validate_component_props(
    component_id: str,
    component_type: str,
    props: dict[str, Any],
) -> None:
    for property_name in _FORBIDDEN_PROPERTIES:
        if property_name in props:
            raise CompactDslConversionError(
                f"{component_id}: legacy property {property_name} is forbidden."
            )
    if "functionCall" in props:
        raise CompactDslConversionError(
            f"{component_id}: legacy functionCall is forbidden."
        )
    if component_type in {"Row", "Column"} and "space" in props:
        raise CompactDslConversionError(
            f"{component_id}: {component_type} must use itemMargin, not space."
        )
    if component_type != "List" and "space" in props:
        raise CompactDslConversionError(
            f"{component_id}: only List supports space."
        )
    if component_type == "List" and "itemMargin" in props:
        raise CompactDslConversionError(
            f"{component_id}: List must use space, not itemMargin."
        )
    if "itemMargin" in props and component_type not in {"Row", "Column"}:
        raise CompactDslConversionError(
            f"{component_id}: only Row and Column support itemMargin."
        )
    for property_name, value in props.items():
        _resolve_tokens(property_name, value, component_id)
    _validate_allowed_component_properties(
        component_id,
        component_type,
        props,
    )
    _validate_component_property_types(component_id, component_type, props)

    required_field = _REQUIRED_FIELDS.get(component_type)
    if required_field is not None and required_field not in props:
        raise CompactDslConversionError(
            f"{component_id}: {component_type}.{required_field} is required."
        )
    if component_type == "Button":
        _validate_button_props(component_id, props)
    if component_type == "ActionUnit":
        _validate_action_unit_props(component_id, props)
    if component_type == "RingUnit":
        _validate_ring_unit_props(component_id, props)
    _validate_semantic_props(component_id, component_type, props)
    if "onClick" in props:
        _validate_on_click(component_id, props["onClick"])
    _validate_source_value(
        _source_value_for_validation(component_type, props),
        component_id,
    )


def _validate_allowed_component_properties(
    component_id: str,
    component_type: str,
    props: dict[str, Any],
) -> None:
    allowed = set(_COMMON_STYLE_PROPERTIES)
    allowed.update(_COMMON_COMPACT_PROPERTIES)
    if component_type == "ActionUnit":
        allowed.update(_ACTION_UNIT_PROPERTIES)
    if component_type == "RingUnit":
        allowed.update(_RING_UNIT_PROPERTIES)
    allowed.update(_SEMANTIC_FIELDS.get(component_type, frozenset()))
    allowed.update(_COMPACT_ONLY_FIELDS.get(component_type, frozenset()))
    allowed.update(_COMPONENT_STYLE_PROPERTIES.get(component_type, frozenset()))
    unknown = sorted(set(props) - allowed)
    if not unknown:
        return
    names = ", ".join(unknown)
    raise CompactDslConversionError(
        f"{component_id}: unsupported properties for {component_type}: {names}."
    )


def _validate_component_property_types(
    component_id: str,
    component_type: str,
    props: dict[str, Any],
) -> None:
    for property_name, value in props.items():
        if property_name in _NUMBER_PROPERTIES:
            _validate_number_property(component_id, property_name, value)
            continue
        if property_name in _BOOLEAN_PROPERTIES:
            if not isinstance(value, bool):
                raise CompactDslConversionError(
                    f"{component_id}: {property_name} must be boolean."
                )
            continue
        if property_name in _STRING_PROPERTIES:
            if not isinstance(value, str) or not value:
                raise CompactDslConversionError(
                    f"{component_id}: {property_name} must be a non-empty string."
                )
            continue
        if property_name in {"itemMargin", "space"}:
            _validate_number_property(component_id, property_name, value)
            continue
        if property_name in {"margin", "padding"}:
            _validate_spacing_property(component_id, property_name, value)
            continue
        if property_name in {"width", "height"}:
            _validate_dimension_property(component_id, property_name, value)
            continue
        if component_type == "RingUnit" and property_name == "size":
            _validate_number_property(component_id, property_name, value)


def _validate_number_property(
    component_id: str,
    property_name: str,
    value: Any,
) -> None:
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        return
    raise CompactDslConversionError(
        f"{component_id}: {property_name} must be numeric."
    )


def _validate_spacing_property(
    component_id: str,
    property_name: str,
    value: Any,
) -> None:
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        return
    if not isinstance(value, dict):
        raise CompactDslConversionError(
            f"{component_id}: {property_name} must be numeric or an edge object."
        )
    allowed_edges = {"top", "right", "bottom", "left"}
    if set(value) - allowed_edges:
        raise CompactDslConversionError(
            f"{component_id}: {property_name} contains unsupported edges."
        )
    for edge_value in value.values():
        if not isinstance(edge_value, (int, float)) or isinstance(edge_value, bool):
            raise CompactDslConversionError(
                f"{component_id}: {property_name} edge values must be numeric."
            )


def _validate_dimension_property(
    component_id: str,
    property_name: str,
    value: Any,
) -> None:
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        return
    if isinstance(value, str) and value:
        return
    raise CompactDslConversionError(
        f"{component_id}: {property_name} must be numeric or a dimension string."
    )


def _validate_button_label(component_id: str, label: Any) -> None:
    if not isinstance(label, str) or not label.strip():
        raise CompactDslConversionError(
            f"{component_id}: Button.label must be a non-empty string."
        )


def _validate_button_props(component_id: str, props: dict[str, Any]) -> None:
    if props.get("design") == "icon-round":
        return
    _validate_button_label(component_id, props.get("label"))


def _validate_action_unit_props(component_id: str, props: dict[str, Any]) -> None:
    _validate_action_unit_skin_props(component_id, props)
    state = props.get("state")
    if state not in {"capsule", "icon-round"}:
        raise CompactDslConversionError(
            f'{component_id}: ActionUnit.state must be "capsule" or "icon-round".'
        )
    if "onClick" not in props:
        raise CompactDslConversionError(
            f"{component_id}: ActionUnit requires an onClick event."
        )
    if state == "capsule":
        _validate_button_label(component_id, props.get("label"))
        _validate_optional_action_unit_icon(component_id, props)
        return
    if "label" in props:
        raise CompactDslConversionError(
            f"{component_id}: icon-round ActionUnit must not contain label."
        )
    _validate_required_action_unit_icon(component_id, props)


def _validate_action_unit_skin_props(
    component_id: str,
    props: dict[str, Any],
) -> None:
    unsupported = sorted(set(props).intersection(_ACTION_UNIT_FORBIDDEN_SKIN_PROPERTIES))
    if not unsupported:
        return
    names = ", ".join(unsupported)
    raise CompactDslConversionError(
        f"{component_id}: ActionUnit must not define skin properties: {names}."
    )


def _validate_optional_action_unit_icon(
    component_id: str,
    props: dict[str, Any],
) -> None:
    icon = props.get("icon")
    if icon is None:
        return
    _validate_image_source(component_id, icon)


def _validate_required_action_unit_icon(
    component_id: str,
    props: dict[str, Any],
) -> None:
    icon = props.get("icon")
    if icon is None:
        raise CompactDslConversionError(
            f"{component_id}: icon-round ActionUnit requires icon."
        )
    _validate_image_source(component_id, icon)


def _validate_ring_unit_props(component_id: str, props: dict[str, Any]) -> None:
    state = _canonical_ring_unit_state(component_id, props.get("state"))
    size = props.get("size")
    if size not in {44, 52}:
        raise CompactDslConversionError(
            f"{component_id}: RingUnit.size must be 44 or 52."
        )
    _require_numeric_or_binding(component_id, "RingUnit.value", props.get("value"))
    if "total" not in props:
        raise CompactDslConversionError(
            f"{component_id}: RingUnit.total is required."
        )
    _require_numeric_or_binding(component_id, "RingUnit.total", props["total"])

    reading = props.get("reading")
    center_icon = props.get("centerIcon")
    if state == "center-icon":
        _validate_required_ring_center_icon(component_id, center_icon)
        if reading is not None:
            raise CompactDslConversionError(
                f"{component_id}: center-icon RingUnit must not contain reading."
            )
        return
    if state == "center-text":
        if size != 52:
            raise CompactDslConversionError(
                f"{component_id}: center-text RingUnit requires size 52."
            )
        if center_icon is not None:
            raise CompactDslConversionError(
                f"{component_id}: center-text RingUnit must not contain centerIcon."
            )
        _validate_ring_reading(component_id, reading)
        return
    _validate_required_ring_center_icon(component_id, center_icon)
    _validate_ring_reading(component_id, reading)


def _canonical_ring_unit_state(component_id: str, state: Any) -> str:
    if not isinstance(state, str) or not state:
        raise CompactDslConversionError(
            f"{component_id}: RingUnit.state must be a non-empty string."
        )
    canonical_state = _RING_UNIT_STATE_ALIASES.get(state)
    if canonical_state is None:
        valid_states = ", ".join(sorted(_RING_UNIT_STATE_ALIASES))
        raise CompactDslConversionError(
            f"{component_id}: unsupported RingUnit.state {state!r}; "
            f"expected one of: {valid_states}."
        )
    return canonical_state


def _validate_required_ring_center_icon(component_id: str, icon: Any) -> None:
    if icon is None:
        raise CompactDslConversionError(
            f"{component_id}: RingUnit.centerIcon is required."
        )
    _validate_image_source(component_id, icon)


def _validate_ring_reading(component_id: str, reading: Any) -> None:
    if not isinstance(reading, dict):
        raise CompactDslConversionError(
            f"{component_id}: RingUnit.reading must be an object."
        )
    allowed = {"path", "unit"}
    unknown = sorted(set(reading) - allowed)
    if unknown:
        names = ", ".join(unknown)
        raise CompactDslConversionError(
            f"{component_id}: unsupported RingUnit.reading fields: {names}."
        )
    path = reading.get("path")
    if not isinstance(path, str) or not path.startswith("/"):
        raise CompactDslConversionError(
            f"{component_id}: RingUnit.reading.path must be a JSON Pointer."
        )
    _decode_json_pointer(path)
    unit = reading.get("unit")
    if unit is not None and not isinstance(unit, str):
        raise CompactDslConversionError(
            f"{component_id}: RingUnit.reading.unit must be a string."
        )


def _source_value_for_validation(
    component_type: str,
    props: dict[str, Any],
) -> dict[str, Any]:
    if component_type != "RingUnit" or "reading" not in props:
        return props
    source_props = copy.deepcopy(props)
    source_props.pop("reading", None)
    return source_props


def _validate_semantic_props(
    component_id: str,
    component_type: str,
    props: dict[str, Any],
) -> None:
    if component_type == "Text":
        _require_literal_or_binding(
            component_id,
            "Text.content",
            props.get("content"),
            str,
        )
        return
    if component_type == "Image":
        _validate_image_source(component_id, props.get("src"))
        return
    if component_type == "Progress":
        _validate_progress_props(component_id, props)
        return
    if component_type == "Button":
        _validate_optional_bool(component_id, "Button.enabled", props)
        return
    if component_type == "ActionUnit":
        _validate_optional_bool(component_id, "ActionUnit.enabled", props)
        return
    if component_type == "Checkbox":
        _validate_checkbox_props(component_id, props)


def _require_literal_or_binding(
    component_id: str,
    property_name: str,
    value: Any,
    literal_type: type,
) -> None:
    is_literal = isinstance(value, literal_type)
    if literal_type in {int, float} and isinstance(value, bool):
        is_literal = False
    if is_literal or _is_path_binding(value):
        return
    raise CompactDslConversionError(
        f"{component_id}: {property_name} has an invalid value."
    )


def _validate_image_source(component_id: str, source: Any) -> None:
    if not isinstance(source, str) or not source:
        raise CompactDslConversionError(
            f"{component_id}: Image.src must be a non-empty local path."
        )
    if not source.startswith("resources/base/media/"):
        raise CompactDslConversionError(
            f"{component_id}: Image.src must use resources/base/media/."
        )


def _validate_progress_props(
    component_id: str,
    props: dict[str, Any],
) -> None:
    _require_numeric_or_binding(
        component_id,
        "Progress.value",
        props.get("value"),
    )
    if "total" not in props:
        raise CompactDslConversionError(
            f"{component_id}: Progress.total is required."
        )
    _require_numeric_or_binding(
        component_id,
        "Progress.total",
        props["total"],
    )


def _require_numeric_or_binding(
    component_id: str,
    property_name: str,
    value: Any,
) -> None:
    is_number = isinstance(value, (int, float))
    if isinstance(value, bool):
        is_number = False
    if is_number or _is_path_binding(value):
        return
    raise CompactDslConversionError(
        f"{component_id}: {property_name} must be numeric or a path binding."
    )


def _validate_optional_bool(
    component_id: str,
    property_name: str,
    props: dict[str, Any],
) -> None:
    field_name = property_name.rsplit(".", 1)[-1]
    if field_name not in props:
        return
    value = props[field_name]
    if isinstance(value, bool) or _is_path_binding(value):
        return
    raise CompactDslConversionError(
        f"{component_id}: {property_name} must be boolean or a path binding."
    )


def _validate_checkbox_props(
    component_id: str,
    props: dict[str, Any],
) -> None:
    for property_name in ("label", "value"):
        if property_name not in props:
            continue
        _require_literal_or_binding(
            component_id,
            f"Checkbox.{property_name}",
            props[property_name],
            str,
        )
    _validate_optional_bool(component_id, "Checkbox.select", props)


def _is_path_binding(value: Any) -> bool:
    if not isinstance(value, dict) or set(value) != {"path"}:
        return False
    path = value.get("path")
    return isinstance(path, str) and path.startswith("/")


def _validate_on_click(component_id: str, on_click: Any) -> None:
    if not isinstance(on_click, list) or not on_click:
        raise CompactDslConversionError(
            f"{component_id}: onClick must be a non-empty array."
        )
    for handler in on_click:
        _validate_event_handler(component_id, handler)


def _validate_event_handler(component_id: str, handler: Any) -> None:
    if not isinstance(handler, dict):
        raise CompactDslConversionError(
            f"{component_id}: each onClick handler must be an object."
        )
    allowed_keys = {"call", "args"}
    unknown_keys = set(handler) - allowed_keys
    if unknown_keys:
        names = ", ".join(sorted(unknown_keys))
        raise CompactDslConversionError(
            f"{component_id}: onClick has unsupported fields: {names}."
        )
    call = handler.get("call")
    if not isinstance(call, str) or not call:
        raise CompactDslConversionError(
            f"{component_id}: onClick.call must be a non-empty string."
        )
    args = handler.get("args")
    if args is not None and not isinstance(args, dict):
        raise CompactDslConversionError(
            f"{component_id}: onClick.args must be an object."
        )


def _validate_source_value(value: Any, context: str) -> None:
    if isinstance(value, str):
        _validate_source_string(value, context)
        return
    if isinstance(value, list):
        for item in value:
            _validate_source_value(item, context)
        return
    if not isinstance(value, dict):
        return

    if "functionCall" in value:
        raise CompactDslConversionError(
            f"{context}: legacy functionCall is forbidden."
        )
    if "path" in value:
        _validate_path_binding(value, context)
        return
    for child_value in value.values():
        _validate_source_value(child_value, context)


def _validate_source_string(value: str, context: str) -> None:
    for fragment in _FORBIDDEN_STRING_FRAGMENTS:
        if fragment in value:
            raise CompactDslConversionError(
                f'{context}: forbidden binding expression "{fragment}".'
            )


def _validate_path_binding(value: dict[str, Any], context: str) -> None:
    if set(value) != {"path"}:
        raise CompactDslConversionError(
            f"{context}: a path binding must contain only the path field."
        )
    path = value.get("path")
    if not isinstance(path, str) or not path.startswith("/"):
        raise CompactDslConversionError(
            f"{context}: path binding must contain a JSON Pointer."
        )
    _decode_json_pointer(path)


def _validate_component_tree(
    rows: list[CompactRow],
) -> tuple[list[ComponentRow], list[DataRow]]:
    first_row = rows[0]
    if not isinstance(first_row, ComponentRow):
        raise CompactDslConversionError(
            "The root Column component is missing; model output may be truncated."
        )
    if first_row.component_id != "root" or first_row.component_type != "Column":
        first_component = (
            f"{first_row.component_id}/{first_row.component_type}"
        )
        raise CompactDslConversionError(
            "The root Column component is missing; model output may be "
            f"truncated. First parsed component: {first_component}."
        )

    components: list[ComponentRow] = []
    data_rows: list[DataRow] = []
    seen_ids: set[str] = set()
    announced_ids = {"root"}
    parent_by_child: dict[str, str] = {}

    for row in rows:
        if isinstance(row, DataRow):
            data_rows.append(row)
            continue
        _validate_component_position(row, seen_ids, announced_ids)
        seen_ids.add(row.component_id)
        components.append(row)
        _announce_children(row, announced_ids, parent_by_child)

    unresolved_ids = announced_ids - seen_ids
    if unresolved_ids:
        unresolved = ", ".join(sorted(unresolved_ids))
        raise CompactDslConversionError(
            f"Compact DSL references missing components: {unresolved}."
        )
    return components, data_rows


def _validate_component_position(
    component: ComponentRow,
    seen_ids: set[str],
    announced_ids: set[str],
) -> None:
    component_id = component.component_id
    if component_id in seen_ids:
        raise CompactDslConversionError(
            f'Duplicate Compact DSL component id "{component_id}".'
        )
    if component_id not in announced_ids:
        raise CompactDslConversionError(
            f'{component_id}: component must be declared by an earlier parent.'
        )


def _announce_children(
    component: ComponentRow,
    announced_ids: set[str],
    parent_by_child: dict[str, str],
) -> None:
    for child_id in component.children:
        if child_id == "root":
            raise CompactDslConversionError("root cannot be a child component.")
        existing_parent = parent_by_child.get(child_id)
        if existing_parent is not None:
            raise CompactDslConversionError(
                f"{child_id}: referenced by both {existing_parent} "
                f"and {component.component_id}."
            )
        parent_by_child[child_id] = component.component_id
        announced_ids.add(child_id)


def _normalize_component(component: ComponentRow) -> ComponentRow:
    props = _expand_component_design(component)
    resolved_props: dict[str, Any] = {}
    for property_name, value in props.items():
        resolved_props[property_name] = _resolve_tokens(
            property_name,
            value,
            component.component_id,
        )
    return ComponentRow(
        component_id=component.component_id,
        component_type=component.component_type,
        props=resolved_props,
        children=component.children,
    )


def _expand_component_design(component: ComponentRow) -> dict[str, Any]:
    explicit_props = copy.deepcopy(component.props)
    design = explicit_props.pop("design", None)
    if design is None:
        return explicit_props
    if not isinstance(design, str) or not design:
        raise CompactDslConversionError(
            f"{component.component_id}: design must be a non-empty string."
        )

    component_designs = _COMPONENT_DESIGNS.get(component.component_type)
    if component_designs is None or design not in component_designs:
        raise CompactDslConversionError(
            f"{component.component_id}: unsupported "
            f'{component.component_type}.design "{design}".'
        )
    expanded = copy.deepcopy(component_designs[design])
    for property_name, value in explicit_props.items():
        expanded[property_name] = copy.deepcopy(value)
    return expanded


def _resolve_tokens(
    property_name: str,
    value: Any,
    component_id: str,
) -> Any:
    if isinstance(value, dict):
        resolved: dict[str, Any] = {}
        for child_name, child_value in value.items():
            nested_name = child_name
            if property_name in {"margin", "padding"}:
                nested_name = property_name
            resolved[child_name] = _resolve_tokens(
                nested_name,
                child_value,
                component_id,
            )
        return resolved
    if isinstance(value, list):
        if property_name == "colors":
            return _resolve_gradient_stops(value, component_id)
        resolved_items: list[Any] = []
        for item in value:
            resolved_items.append(
                _resolve_tokens(property_name, item, component_id)
            )
        return resolved_items
    if not isinstance(value, str):
        return value
    if property_name in _COLOR_PROPERTIES:
        return _COLOR_TOKENS.get(value, value)
    if property_name in _TOKEN_AWARE_PROPERTIES:
        _reject_legacy_style_token(component_id, property_name, value)
    return value


def _resolve_gradient_stops(
    stops: list[Any],
    component_id: str,
) -> list[Any]:
    resolved_stops: list[Any] = []
    for stop in stops:
        if not isinstance(stop, list) or len(stop) != 2:
            raise CompactDslConversionError(
                f"{component_id}: each gradient color must be [color, position]."
            )
        color, position = stop
        if not isinstance(color, str):
            raise CompactDslConversionError(
                f"{component_id}: gradient colors must be strings."
            )
        if not isinstance(position, (int, float)):
            raise CompactDslConversionError(
                f"{component_id}: gradient positions must be numbers."
            )
        resolved_stops.append([_COLOR_TOKENS.get(color, color), position])
    return resolved_stops


def _reject_legacy_style_token(
    component_id: str,
    property_name: str,
    value: str,
) -> None:
    is_legacy_prefix = value.startswith(_LEGACY_TOKEN_PREFIXES)
    is_legacy_font_size = value in _LEGACY_FONT_SIZE_TOKENS
    if is_legacy_prefix or is_legacy_font_size:
        raise CompactDslConversionError(
            f'{component_id}: legacy token "{value}" is not defined by PROMPT.md '
            f"for {property_name}."
        )


def _component_to_tuple(component: ComponentRow) -> list[Any]:
    row: list[Any] = [
        component.component_id,
        component.component_type,
        copy.deepcopy(component.props),
    ]
    if component.component_type in _CONTAINER_TYPES or component.children:
        row.append(list(component.children))
    return row


def _button_ids_with_design(
    components: list[ComponentRow],
    design: str,
) -> set[str]:
    button_ids: set[str] = set()
    for component in components:
        if component.component_type != "Button":
            continue
        if component.props.get("design") == design:
            button_ids.add(component.component_id)
    return button_ids


def _convert_component_rows(
    component: ComponentRow,
    *,
    hide_label: bool = False,
    fallback_root_gradient: dict[str, Any] | None = None,
) -> list[dict[str, Any]]:
    if component.component_type == "ActionUnit":
        return _convert_action_unit(component)
    if component.component_type == "RingUnit":
        return _convert_ring_unit(component)
    return [
        _convert_component(
            component,
            hide_label=hide_label,
            fallback_root_gradient=fallback_root_gradient,
        )
    ]


def _convert_ring_unit(component: ComponentRow) -> list[dict[str, Any]]:
    state = _canonical_ring_unit_state(component.component_id, component.props["state"])
    if state == "center-icon":
        return _convert_ring_unit_center_icon(component)
    if state == "center-text":
        return _convert_ring_unit_center_text(component)
    return _convert_ring_unit_center_icon_below_text(component)


def _convert_ring_unit_center_icon(component: ComponentRow) -> list[dict[str, Any]]:
    ring_id = _ring_unit_child_id(component.component_id, "ring")
    icon_id = _ring_unit_child_id(component.component_id, "center_icon")
    stack = _ring_unit_stack(component, [ring_id, icon_id])
    ring = _ring_unit_progress(component, ring_id)
    icon = _ring_unit_icon(component, icon_id)
    return [stack, ring, icon]


def _convert_ring_unit_center_text(component: ComponentRow) -> list[dict[str, Any]]:
    ring_id = _ring_unit_child_id(component.component_id, "ring")
    reading_id = _ring_unit_child_id(component.component_id, "center_reading")
    stack = _ring_unit_stack(component, [ring_id, reading_id])
    ring = _ring_unit_progress(component, ring_id)
    reading = _ring_unit_reading_rows(
        reading_id,
        component.props["reading"],
        component_id=component.component_id,
    )
    return [stack, ring, *reading]


def _convert_ring_unit_center_icon_below_text(
    component: ComponentRow,
) -> list[dict[str, Any]]:
    stack_id = _ring_unit_child_id(component.component_id, "ring_stack")
    ring_id = _ring_unit_child_id(component.component_id, "ring")
    icon_id = _ring_unit_child_id(component.component_id, "center_icon")
    reading_id = _ring_unit_child_id(component.component_id, "reading")
    root = {
        "id": component.component_id,
        "component": "Column",
        "children": [stack_id, reading_id],
        "itemMargin": 4,
        "styles": {
            "alignItems": "center",
            "flexShrink": component.props.get("flexShrink", 0),
        },
    }
    stack = _ring_unit_stack(
        component,
        [ring_id, icon_id],
        component_id=stack_id,
    )
    ring = _ring_unit_progress(component, ring_id)
    icon = _ring_unit_icon(component, icon_id)
    reading = _ring_unit_reading_rows(
        reading_id,
        component.props["reading"],
        component_id=component.component_id,
    )
    return [root, stack, ring, icon, *reading]


def _ring_unit_stack(
    component: ComponentRow,
    children: list[str],
    *,
    component_id: str | None = None,
) -> dict[str, Any]:
    size = int(component.props["size"])
    styles = {
        "width": size,
        "height": size,
        "alignContent": "center",
        "flexShrink": component.props.get("flexShrink", 0),
    }
    return {
        "id": component_id or component.component_id,
        "component": "Stack",
        "children": children,
        "styles": styles,
    }


def _ring_unit_progress(component: ComponentRow, ring_id: str) -> dict[str, Any]:
    styles = _resolved_design_styles(component.component_id, _PROGRESS_DESIGNS["ring"])
    styles["width"] = "matchParent"
    styles["height"] = "matchParent"
    styles["strokeWidth"] = 4 if component.props["size"] == 44 else 6
    return {
        "id": ring_id,
        "component": "Progress",
        "value": _convert_path_bindings(component.props["value"]),
        "total": _convert_path_bindings(component.props["total"]),
        "styles": styles,
    }


def _ring_unit_icon(component: ComponentRow, icon_id: str) -> dict[str, Any]:
    icon_size = 24 if component.props["size"] >= 52 else 20
    return {
        "id": icon_id,
        "component": "Image",
        "src": component.props["centerIcon"],
        "styles": {
            "width": icon_size,
            "height": icon_size,
            "objectFit": "contain",
            "flexShrink": 0,
        },
    }


def _ring_unit_reading_rows(
    reading_id: str,
    reading: dict[str, Any],
    *,
    component_id: str,
) -> list[dict[str, Any]]:
    path = reading["path"]
    unit = reading.get("unit")
    content = _convert_path_bindings({"path": path})
    if unit is None or unit == "":
        return [
            {
                "id": reading_id,
                "component": "Text",
                "content": content,
                "styles": copy.deepcopy(_RING_READING_TEXT_STYLES),
            }
        ]

    number_id = _ring_unit_child_id(component_id, "reading_num")
    unit_id = _ring_unit_child_id(component_id, "reading_unit")
    return [
        {
            "id": reading_id,
            "component": "Row",
            "children": [number_id, unit_id],
            "itemMargin": 0,
            "styles": {
                "alignItems": "center",
                "justifyContent": "center",
                "flexShrink": 0,
            },
        },
        {
            "id": number_id,
            "component": "Text",
            "content": content,
            "styles": copy.deepcopy(_RING_READING_TEXT_STYLES),
        },
        {
            "id": unit_id,
            "component": "Text",
            "content": unit,
            "styles": copy.deepcopy(_RING_READING_TEXT_STYLES),
        },
    ]


def _ring_unit_child_id(component_id: str, suffix: str) -> str:
    return f"{component_id}_{suffix}"


def _convert_action_unit(component: ComponentRow) -> list[dict[str, Any]]:
    state = component.props["state"]
    if state == "capsule":
        return _convert_action_unit_capsule(component)
    return _convert_action_unit_icon_round(component)


def _convert_action_unit_capsule(component: ComponentRow) -> list[dict[str, Any]]:
    icon = component.props.get("icon")
    if isinstance(icon, str) and icon:
        return _convert_action_unit_capsule_with_icon(component, icon)

    converted: dict[str, Any] = {
        "id": component.component_id,
        "component": "Button",
        "label": component.props["label"],
        "onClick": _convert_path_bindings(component.props["onClick"]),
    }
    if "enabled" in component.props:
        converted["enabled"] = _convert_path_bindings(component.props["enabled"])
    styles = _resolved_design_styles(component.component_id, _BUTTON_DESIGNS["capsule"])
    action_ink = component.props.get("actionInk")
    if action_ink is not None:
        styles["fontColor"] = action_ink
    converted["styles"] = styles
    return [converted]


def _convert_action_unit_capsule_with_icon(
    component: ComponentRow,
    icon_source: str,
) -> list[dict[str, Any]]:
    icon_id = f"{component.component_id}_icon"
    text_id = f"{component.component_id}_text"
    styles = _resolved_design_styles(component.component_id, _BUTTON_DESIGNS["capsule"])
    text_styles = _capsule_text_styles(styles, component.props.get("actionInk"))
    row_styles = _capsule_row_styles(styles)
    row: dict[str, Any] = {
        "id": component.component_id,
        "component": "Row",
        "children": [icon_id, text_id],
        "itemMargin": 4,
        "onClick": _convert_path_bindings(component.props["onClick"]),
        "styles": row_styles,
    }
    icon = {
        "id": icon_id,
        "component": "Image",
        "src": icon_source,
        "styles": {
            "width": 16,
            "height": 16,
            "objectFit": "contain",
            "flexShrink": 0,
        },
    }
    text = {
        "id": text_id,
        "component": "Text",
        "content": component.props["label"],
        "styles": text_styles,
    }
    return [row, icon, text]


def _capsule_row_styles(styles: dict[str, Any]) -> dict[str, Any]:
    row_style_names = {
        "backgroundColor",
        "borderRadius",
        "flexShrink",
        "height",
        "padding",
        "width",
    }
    row_styles = {
        name: copy.deepcopy(value)
        for name, value in styles.items()
        if name in row_style_names
    }
    row_styles["justifyContent"] = "center"
    row_styles["alignItems"] = "center"
    return row_styles


def _capsule_text_styles(
    capsule_styles: dict[str, Any],
    action_ink: Any,
) -> dict[str, Any]:
    text_style_names = {
        "fontColor",
        "fontSize",
        "fontWeight",
        "maxFontSize",
        "maxLines",
        "minFontSize",
    }
    text_styles = {
        name: copy.deepcopy(value)
        for name, value in capsule_styles.items()
        if name in text_style_names
    }
    if action_ink is not None:
        text_styles["fontColor"] = action_ink
    text_styles.update(
        {
            "width": 94,
            "height": capsule_styles.get("height", 30),
            "textAlign": "center",
            "textOverflow": "ellipsis",
            "flexShrink": 0,
        }
    )
    return text_styles


def _convert_action_unit_icon_round(component: ComponentRow) -> list[dict[str, Any]]:
    icon_id = f"{component.component_id}_icon"
    styles = _resolved_design_styles(component.component_id, _BUTTON_DESIGNS["icon-round"])
    _normalize_icon_button_stack(styles)
    stack = {
        "id": component.component_id,
        "component": "Stack",
        "children": [icon_id],
        "onClick": _convert_path_bindings(component.props["onClick"]),
        "styles": styles,
    }
    icon = {
        "id": icon_id,
        "component": "Image",
        "src": component.props["icon"],
        "styles": {
            "width": 16,
            "height": 16,
            "objectFit": "contain",
            "flexShrink": 0,
        },
    }
    return [stack, icon]


def _resolved_design_styles(
    component_id: str,
    styles: dict[str, Any],
) -> dict[str, Any]:
    resolved: dict[str, Any] = {}
    for property_name, value in styles.items():
        resolved[property_name] = _resolve_tokens(property_name, value, component_id)
    return resolved


def _convert_component(
    component: ComponentRow,
    *,
    hide_label: bool = False,
    fallback_root_gradient: dict[str, Any] | None = None,
) -> dict[str, Any]:
    output_type = _output_component_type(component, hide_label)
    converted: dict[str, Any] = {
        "id": component.component_id,
        "component": output_type,
    }
    if output_type in _CONTAINER_TYPES:
        converted["children"] = list(component.children)
    if hide_label and output_type == "Button":
        converted["label"] = _A2UI_ICON_BUTTON_LABEL

    styles: dict[str, Any] = {}
    semantic_fields = _SEMANTIC_FIELDS.get(
        component.component_type,
        frozenset(),
    )
    compact_only_fields = _COMPACT_ONLY_FIELDS.get(
        component.component_type,
        frozenset(),
    )
    for property_name, source_value in component.props.items():
        if property_name == "label" and hide_label:
            continue
        if property_name in compact_only_fields:
            continue
        value = _convert_path_bindings(source_value)
        if _move_component_property(
            converted,
            component,
            property_name,
            value,
            semantic_fields,
        ):
            continue
        styles[property_name] = value

    if component.component_id == "root":
        _normalize_root_component(
            component,
            converted,
            styles,
            fallback_root_gradient,
        )
    if _is_icon_button_stack(component, hide_label):
        _normalize_icon_button_stack(styles)
    if component.component_type == "Text":
        _normalize_text_component(styles)
    if styles:
        converted["styles"] = styles
    return converted


def _output_component_type(component: ComponentRow, hide_label: bool) -> str:
    if _is_icon_button_stack(component, hide_label):
        return "Stack"
    return component.component_type


def _is_icon_button_stack(component: ComponentRow, hide_label: bool) -> bool:
    if not hide_label or component.component_type != "Button":
        return False
    return bool(component.children)


def _normalize_icon_button_stack(styles: dict[str, Any]) -> None:
    styles["alignContent"] = "center"
    styles["clip"] = True


def _normalize_text_component(styles: dict[str, Any]) -> None:
    styles["maxLines"] = 1
    styles["textOverflow"] = "ellipsis"


def _normalize_root_component(
    component: ComponentRow,
    converted: dict[str, Any],
    styles: dict[str, Any],
    fallback_gradient: dict[str, Any] | None,
) -> None:
    styles["width"] = "matchParent"
    styles["height"] = "matchParent"
    if _is_2x2_root(component.props):
        styles["padding"] = 12
        styles["borderRadius"] = 20
        styles["clip"] = True
        styles.setdefault("justifyContent", "spaceBetween")
        converted["itemMargin"] = 8
    _ensure_root_background(styles, fallback_gradient)


def _is_2x2_root(props: dict[str, Any]) -> bool:
    return props.get("width") == 160 and props.get("height") == 160


def _ensure_root_background(
    styles: dict[str, Any],
    fallback_gradient: dict[str, Any] | None,
) -> None:
    has_background = any(
        name in styles
        for name in ("linearGradient", "backgroundColor", "backgroundImage")
    )
    if has_background:
        return
    gradient = fallback_gradient or _ROOT_LINEAR_GRADIENT_PALETTES[0]
    styles["linearGradient"] = copy.deepcopy(gradient)


def _fallback_root_linear_gradient(seed: str) -> dict[str, Any]:
    digest = hashlib.sha256(seed.encode("utf-8")).digest()
    palette_index = int.from_bytes(digest[:2], "big")
    palette_index %= len(_ROOT_LINEAR_GRADIENT_PALETTES)
    return copy.deepcopy(_ROOT_LINEAR_GRADIENT_PALETTES[palette_index])


def _move_component_property(
    converted: dict[str, Any],
    component: ComponentRow,
    property_name: str,
    value: Any,
    semantic_fields: frozenset[str],
) -> bool:
    if property_name in semantic_fields:
        converted[property_name] = value
        return True
    if property_name == "onClick":
        converted["onClick"] = value
        return True
    if (
        property_name == "itemMargin"
        and component.component_type in {"Row", "Column"}
    ):
        converted["itemMargin"] = value
        return True
    if property_name == "space" and component.component_type == "List":
        converted["space"] = value
        return True
    return False


def _convert_path_bindings(value: Any) -> Any:
    if isinstance(value, dict):
        if set(value) == {"path"}:
            return f"{{{{ ${{{value['path']}}} }}}}"
        converted: dict[str, Any] = {}
        for key, child_value in value.items():
            converted[key] = _convert_path_bindings(child_value)
        return converted
    if isinstance(value, list):
        converted_items: list[Any] = []
        for item in value:
            converted_items.append(_convert_path_bindings(item))
        return converted_items
    return copy.deepcopy(value)


def _validate_compact_root_dimensions(
    root: ComponentRow,
    size: str,
) -> None:
    expected = _COMPACT_ROOT_DIMENSIONS.get(size)
    if expected is None:
        raise CompactDslConversionError(f'Unsupported Form size "{size}".')
    width = root.props.get("width")
    height = root.props.get("height")
    if width == expected["width"] and height == expected["height"]:
        return
    raise CompactDslConversionError(
        f"root dimensions must be {expected['width']}x{expected['height']} "
        f'for size "{size}".'
    )


def _surface_dimensions(
    size: str,
    protocol_profile: dict[str, Any],
) -> dict[str, int]:
    if size not in _A2UI_FALLBACK_DIMENSIONS:
        raise CompactDslConversionError(f'Unsupported Form size "{size}".')
    if size in _COMPACT_ROOT_DIMENSIONS:
        return copy.deepcopy(_COMPACT_ROOT_DIMENSIONS[size])
    sizes = protocol_profile.get("sizes")
    dimensions = _profile_dimensions(size, sizes)
    if dimensions is not None:
        return dimensions
    return copy.deepcopy(_A2UI_FALLBACK_DIMENSIONS[size])


def _profile_dimensions(
    size: str,
    sizes: Any,
) -> dict[str, int] | None:
    if not isinstance(sizes, dict):
        return None
    dimensions = sizes.get(size)
    if dimensions is None and size == "4x2":
        dimensions = sizes.get("2x4")
    if not isinstance(dimensions, dict):
        return None
    width = dimensions.get("width")
    height = dimensions.get("height")
    if not _is_positive_integer(width) or not _is_positive_integer(height):
        return None
    return {"width": width, "height": height}


def _is_positive_integer(value: Any) -> bool:
    return isinstance(value, int) and not isinstance(value, bool) and value > 0


def _build_data_model(data_rows: list[DataRow]) -> dict[str, Any]:
    if not data_rows:
        return {"data": {}}

    root: dict[str, Any] = {}
    data_values: dict[str, Any] = {}
    for row in data_rows:
        existing = data_values.get(row.path)
        if row.path in data_values and existing != row.value:
            raise CompactDslConversionError(
                f'{row.path}: duplicate data rows contain different values.'
            )
        data_values[row.path] = copy.deepcopy(row.value)
        _set_json_pointer(root, row.path, copy.deepcopy(row.value))
    return root


def _set_json_pointer(root: dict[str, Any], path: str, value: Any) -> None:
    tokens = _decode_json_pointer(path)
    if not tokens:
        _merge_root_data(root, value)
        return

    current: dict[str, Any] | list[Any] = root
    for index, token in enumerate(tokens):
        is_last = index == len(tokens) - 1
        next_token = None if is_last else tokens[index + 1]
        if isinstance(current, dict):
            current = _set_dict_pointer_part(
                current,
                token,
                next_token,
                value,
                is_last,
                path,
            )
            if is_last:
                return
            continue
        current = _set_list_pointer_part(
            current,
            token,
            next_token,
            value,
            is_last,
            path,
        )
        if is_last:
            return


def _merge_root_data(root: dict[str, Any], value: Any) -> None:
    if not isinstance(value, dict):
        raise CompactDslConversionError(
            "Compact DSL root DataModel row must contain an object."
        )
    merged = _merge_compatible_values(root, value, "/")
    root.clear()
    root.update(merged)


def _set_dict_pointer_part(
    current: dict[str, Any],
    token: str,
    next_token: str | None,
    value: Any,
    is_last: bool,
    path: str,
) -> dict[str, Any] | list[Any]:
    if is_last:
        existing = current.get(token)
        current[token] = _merge_compatible_values(existing, value, path)
        return current

    expected_type = list if _is_array_index(next_token) else dict
    child = current.get(token)
    if child is None:
        child = expected_type()
        current[token] = child
    if not isinstance(child, expected_type):
        raise CompactDslConversionError(
            f'{path}: data path conflicts with an existing scalar value.'
        )
    return child


def _set_list_pointer_part(
    current: list[Any],
    token: str,
    next_token: str | None,
    value: Any,
    is_last: bool,
    path: str,
) -> dict[str, Any] | list[Any]:
    array_index = _parse_array_index(token, path)
    while len(current) <= array_index:
        current.append(None)
    if is_last:
        current[array_index] = _merge_compatible_values(
            current[array_index],
            value,
            path,
        )
        return current

    expected_type = list if _is_array_index(next_token) else dict
    child = current[array_index]
    if child is None:
        child = expected_type()
        current[array_index] = child
    if not isinstance(child, expected_type):
        raise CompactDslConversionError(
            f'{path}: data path conflicts with an existing scalar value.'
        )
    return child


def _merge_compatible_values(existing: Any, incoming: Any, path: str) -> Any:
    if existing is None:
        return copy.deepcopy(incoming)
    if isinstance(existing, dict) and isinstance(incoming, dict):
        merged = copy.deepcopy(existing)
        for key, value in incoming.items():
            child_path = f"{path.rstrip('/')}/{key}"
            merged[key] = _merge_compatible_values(
                merged.get(key),
                value,
                child_path,
            )
        return merged
    if isinstance(existing, list) and isinstance(incoming, list):
        return _merge_lists(existing, incoming, path)
    if existing == incoming:
        return copy.deepcopy(existing)
    raise CompactDslConversionError(
        f'{path}: data rows contain incompatible values.'
    )


def _merge_lists(existing: list[Any], incoming: list[Any], path: str) -> list[Any]:
    merged = copy.deepcopy(existing)
    for index, value in enumerate(incoming):
        while len(merged) <= index:
            merged.append(None)
        child_path = f"{path.rstrip('/')}/{index}"
        merged[index] = _merge_compatible_values(
            merged[index],
            value,
            child_path,
        )
    return merged


def _validate_binding_paths(
    components: list[ComponentRow],
    data_model: dict[str, Any],
) -> None:
    for component in components:
        paths: list[str] = []
        _collect_binding_paths(component.props, paths)
        for path in paths:
            if not _json_pointer_exists(data_model, path):
                raise CompactDslConversionError(
                    f"{component.component_id}: binding path {path} "
                    "has no matching data value."
                )


def _component_binding_paths(
    components: list[ComponentRow],
) -> list[str]:
    paths: list[str] = []
    for component in components:
        _collect_binding_paths(component.props, paths)
    return list(dict.fromkeys(paths))


def _validate_binding_schema_types(
    binding_paths: list[str],
    data_model: dict[str, Any],
    data_model_schema: dict[str, Any],
) -> None:
    for path in binding_paths:
        schema_node = _schema_node_at_path(data_model_schema, path)
        if schema_node is None:
            raise CompactDslConversionError(
                f"{path}: binding path is not declared by TaskSpec.dataModelSchema."
            )
        found, value = _json_pointer_value(data_model, path)
        if not found:
            continue
        expected_type = _schema_type(schema_node)
        if expected_type is None or _value_matches_schema_type(
            value,
            expected_type,
        ):
            continue
        actual_type = _json_type_name(value)
        raise CompactDslConversionError(
            f"{path}: DataModel type {actual_type} does not match "
            f"schema type {expected_type}."
        )


def _schema_node_at_path(
    schema: Any,
    path: str,
) -> Any | None:
    current = schema
    for token in _decode_json_pointer(path):
        current = _schema_child(current, token)
        if current is None:
            return None
    return current


def _schema_child(current: Any, token: str) -> Any | None:
    if isinstance(current, list):
        if not token.isdigit() or not current:
            return None
        return current[0]
    if not isinstance(current, dict):
        return None
    if current.get("type") == "array":
        if not token.isdigit():
            return None
        return current.get("items")
    if current.get("type") == "object":
        properties = current.get("properties")
        if isinstance(properties, dict):
            return properties.get(token)
    return current.get(token)


def _schema_type(schema_node: Any) -> str | None:
    if isinstance(schema_node, list):
        return "array"
    if not isinstance(schema_node, dict):
        return None
    schema_type = schema_node.get("type")
    return schema_type if isinstance(schema_type, str) else None


def _value_matches_schema_type(value: Any, expected_type: str) -> bool:
    if expected_type == "string":
        return isinstance(value, str)
    if expected_type == "integer":
        return isinstance(value, int) and not isinstance(value, bool)
    if expected_type == "number":
        return isinstance(value, (int, float)) and not isinstance(value, bool)
    if expected_type == "boolean":
        return isinstance(value, bool)
    if expected_type == "object":
        return isinstance(value, dict)
    if expected_type == "array":
        return isinstance(value, list)
    if expected_type == "null":
        return value is None
    return True


def _json_type_name(value: Any) -> str:
    if value is None:
        return "null"
    if isinstance(value, bool):
        return "boolean"
    if isinstance(value, str):
        return "string"
    if isinstance(value, int):
        return "integer"
    if isinstance(value, float):
        return "number"
    if isinstance(value, dict):
        return "object"
    if isinstance(value, list):
        return "array"
    return type(value).__name__


def _validate_data_capability_roots(
    binding_paths: list[str],
    card_spec: dict[str, Any],
) -> None:
    roots = _card_spec_data_roots(card_spec)
    for path in binding_paths:
        if path != "/data" and not path.startswith("/data/"):
            continue
        if any(_path_is_within(path, root) for root in roots):
            continue
        raise CompactDslConversionError(
            f"{path}: binding is not backed by CardSpec.dataBindings."
        )


def _unused_data_capability_warnings(
    binding_paths: list[str],
    card_spec: dict[str, Any],
) -> list[str]:
    warnings: list[str] = []
    for root in _card_spec_data_roots(card_spec):
        if any(_path_is_within(path, root) for path in binding_paths):
            continue
        warnings.append(
            f"{root}: declared data capability is not used by any component."
        )
    return warnings


def _card_spec_data_roots(card_spec: dict[str, Any]) -> list[str]:
    bindings = card_spec.get("dataBindings")
    if not isinstance(bindings, list):
        return []
    roots: list[str] = []
    for binding in bindings:
        if not isinstance(binding, dict):
            continue
        root = binding.get("writeResultTo")
        if isinstance(root, str) and root.startswith("/"):
            roots.append(root)
    return roots


def _path_is_within(path: str, root: str) -> bool:
    normalized_root = root.rstrip("/")
    return path == normalized_root or path.startswith(f"{normalized_root}/")


def _validate_asset_candidates(
    components: list[ComponentRow],
    task_spec: dict[str, Any],
) -> None:
    allowed_sources = _candidate_asset_sources(task_spec)
    for component in components:
        source = _candidate_component_asset_source(component)
        if source is None or source in allowed_sources:
            continue
        raise CompactDslConversionError(
            f'{component.component_id}: asset "{source}" is not present '
            "in TaskSpec.assetCandidates."
        )


def _candidate_component_asset_source(component: ComponentRow) -> str | None:
    if component.component_type == "Image":
        source = component.props.get("src")
    elif component.component_type == "ActionUnit":
        source = component.props.get("icon")
    elif component.component_type == "RingUnit":
        source = component.props.get("centerIcon")
    else:
        return None
    return source if isinstance(source, str) and source else None


def _candidate_asset_sources(task_spec: dict[str, Any]) -> set[str]:
    candidates = task_spec.get("assetCandidates")
    if not isinstance(candidates, list):
        return set()
    sources: set[str] = set()
    for candidate in candidates:
        if not isinstance(candidate, dict):
            continue
        source = candidate.get("src")
        if isinstance(source, str) and source:
            sources.add(source)
    return sources


def _validate_event_candidates(
    components: list[ComponentRow],
    task_spec: dict[str, Any],
) -> None:
    allowed_handlers = _candidate_event_handlers(task_spec)
    allowed_keys = {_stable_json(handler) for handler in allowed_handlers}
    for component in components:
        handlers = component.props.get("onClick")
        if component.component_type in {"Button", "ActionUnit"} and handlers is None:
            raise CompactDslConversionError(
                f"{component.component_id}: component requires an onClick event."
            )
        if not isinstance(handlers, list):
            continue
        for handler in handlers:
            if _stable_json(handler) in allowed_keys:
                continue
            raise CompactDslConversionError(
                f"{component.component_id}: onClick is not present in "
                "TaskSpec.eventCandidates."
            )


def _candidate_event_handlers(
    task_spec: dict[str, Any],
) -> list[dict[str, Any]]:
    candidates = task_spec.get("eventCandidates")
    if not isinstance(candidates, list):
        return []
    handlers: list[dict[str, Any]] = []
    for candidate in candidates:
        if not isinstance(candidate, dict):
            continue
        handler = _candidate_event_handler(candidate)
        if handler is None:
            continue
        handlers.append(handler)
    return handlers


def _candidate_event_handler(candidate: dict[str, Any]) -> dict[str, Any] | None:
    call = candidate.get("call")
    args = candidate.get("args")
    if not isinstance(call, str) or not isinstance(args, dict):
        action = candidate.get("action")
        if not isinstance(action, dict):
            return None
        call = action.get("call")
        args = action.get("args")
    if not isinstance(call, str) or not isinstance(args, dict):
        return None
    return {"call": call, "args": copy.deepcopy(args)}


def _stable_json(value: Any) -> str:
    return json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    )


def _event_handler_replacements(
    components: list[ComponentRow],
    task_spec: dict[str, Any],
) -> dict[str, dict[str, Any]]:
    allowed_handlers = _candidate_event_handlers(task_spec)
    allowed_keys = {_stable_json(handler) for handler in allowed_handlers}
    replacements: dict[str, dict[str, Any]] = {}
    for component in components:
        handlers = component.props.get("onClick")
        if not isinstance(handlers, list):
            continue
        for handler in handlers:
            if not isinstance(handler, dict):
                continue
            key = _stable_json(handler)
            if key in allowed_keys:
                continue
            matched = _matching_event_handler(handler, allowed_handlers)
            if matched is not None:
                replacements[key] = copy.deepcopy(matched)
    return replacements


def _matching_event_handler(
    handler: dict[str, Any],
    allowed_handlers: list[dict[str, Any]],
) -> dict[str, Any] | None:
    call = handler.get("call")
    args = handler.get("args")
    if not isinstance(call, str) or not isinstance(args, dict):
        return None
    same_call_handlers = [
        candidate
        for candidate in allowed_handlers
        if candidate.get("call") == call
    ]
    for candidate in same_call_handlers:
        candidate_args = candidate.get("args")
        if isinstance(candidate_args, dict) and _event_args_match(args, candidate_args):
            return candidate
    if len(same_call_handlers) == 1:
        return same_call_handlers[0]
    return None


def _event_args_match(
    model_args: dict[str, Any],
    candidate_args: dict[str, Any],
) -> bool:
    if _dict_subset(model_args, candidate_args):
        return True
    if _dict_subset(candidate_args, model_args):
        return True
    return _same_string_arg(model_args, candidate_args, "uri") or _same_string_arg(
        model_args,
        candidate_args,
        "intentName",
    )


def _dict_subset(left: dict[str, Any], right: dict[str, Any]) -> bool:
    for key, value in left.items():
        if key not in right:
            return False
        right_value = right[key]
        if isinstance(value, dict) and isinstance(right_value, dict):
            if not _dict_subset(value, right_value):
                return False
            continue
        if value != right_value:
            return False
    return True


def _same_string_arg(
    left: dict[str, Any],
    right: dict[str, Any],
    key: str,
) -> bool:
    left_value = left.get(key)
    right_value = right.get(key)
    return isinstance(left_value, str) and left_value == right_value


def _replace_event_handlers(
    props: dict[str, Any],
    event_replacements: dict[str, dict[str, Any]],
) -> dict[str, Any]:
    handlers = props.get("onClick")
    if not event_replacements or not isinstance(handlers, list):
        return props

    repaired_handlers: list[Any] = []
    changed = False
    for handler in handlers:
        if isinstance(handler, dict):
            replacement = event_replacements.get(_stable_json(handler))
            if replacement is not None:
                repaired_handlers.append(copy.deepcopy(replacement))
                changed = True
                continue
        repaired_handlers.append(copy.deepcopy(handler))
    if not changed:
        return props

    repaired_props = copy.deepcopy(props)
    repaired_props["onClick"] = repaired_handlers
    return repaired_props


def _collect_binding_paths(value: Any, paths: list[str]) -> None:
    if isinstance(value, dict):
        if set(value) == {"path"}:
            paths.append(value["path"])
            return
        path = value.get("path")
        if isinstance(path, str) and path.startswith("/"):
            paths.append(path)
        for child_value in value.values():
            _collect_binding_paths(child_value, paths)
        return
    if isinstance(value, list):
        for item in value:
            _collect_binding_paths(item, paths)


def _replace_binding_paths(
    value: Any,
    path_replacements: dict[str, str],
    literal_replacements: dict[str, Any],
) -> Any:
    if isinstance(value, dict):
        if set(value) == {"path"} and isinstance(value.get("path"), str):
            path = value["path"]
            if path in literal_replacements:
                return copy.deepcopy(literal_replacements[path])
            return {"path": path_replacements.get(path, path)}
        return {
            key: _replace_binding_paths(
                item,
                path_replacements,
                literal_replacements,
            )
            for key, item in value.items()
        }
    if isinstance(value, list):
        return [
            _replace_binding_paths(
                item,
                path_replacements,
                literal_replacements,
            )
            for item in value
        ]
    return copy.deepcopy(value)


def _json_pointer_value(
    root: dict[str, Any],
    path: str,
) -> tuple[bool, Any]:
    tokens = _decode_json_pointer(path)
    current: Any = root
    for token in tokens:
        if isinstance(current, dict):
            if token not in current:
                return False, None
            current = current[token]
            continue
        if isinstance(current, list):
            if not token.isdigit():
                return False, None
            index = int(token)
            if index >= len(current):
                return False, None
            current = current[index]
            continue
        return False, None
    return True, current


def _json_pointer_exists(root: dict[str, Any], path: str) -> bool:
    found, _value = _json_pointer_value(root, path)
    return found


def _decode_json_pointer(path: str) -> list[str]:
    if path == "/":
        return []
    if not isinstance(path, str) or not path.startswith("/"):
        raise CompactDslConversionError(
            f'Compact DSL path "{path}" is not a JSON Pointer.'
        )
    tokens: list[str] = []
    for raw_token in path[1:].split("/"):
        _validate_pointer_escape(raw_token, path)
        tokens.append(raw_token.replace("~1", "/").replace("~0", "~"))
    return tokens


def _validate_pointer_escape(token: str, path: str) -> None:
    index = 0
    while index < len(token):
        if token[index] != "~":
            index += 1
            continue
        if index + 1 >= len(token) or token[index + 1] not in {"0", "1"}:
            raise CompactDslConversionError(
                f'Compact DSL path "{path}" has an invalid JSON Pointer escape.'
            )
        index += 2


def _is_array_index(token: str | None) -> bool:
    return token is not None and token.isdigit()


def _parse_array_index(token: str, path: str) -> int:
    if not token.isdigit():
        raise CompactDslConversionError(
            f'Compact DSL path "{path}" contains a non-numeric list index.'
        )
    return int(token)


def _serialize_rows(rows: list[Any]) -> str:
    serialized_rows: list[str] = []
    for row in rows:
        serialized_rows.append(
            json.dumps(row, ensure_ascii=False, separators=(",", ":"))
        )
    return "\n".join(serialized_rows)
