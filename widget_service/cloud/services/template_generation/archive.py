"""模板 A2UI 到 dev 标准 A2UI/A2UI-Compact 双产物归档。"""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any

from anyio import to_thread

from services.generation_pipeline import (
    DslProcessingContext,
    DslProcessorKind,
    get_dsl_processor,
)
from services.template_generation.engine.compact_dsl_a2ui_converter import (
    CompactDslConversionError,
    convert_a2ui_to_compact_dsl,
)


class TemplateArchiveError(RuntimeError):
    """模板输出无法稳定归档为当前 dev Compact Token。"""


@dataclass(frozen=True)
class TemplateArchive:
    a2ui: str
    compact_dsl: str


async def build_template_archive(
    template_a2ui: str,
    *,
    size: str,
    card_spec: dict[str, Any],
    task_spec: dict[str, Any],
    protocol_profile: dict[str, Any],
    design_protocol_profile: dict[str, Any],
    design_profile_id: str,
    data_capabilities: list[Any],
    event_candidates: list[Any],
) -> TemplateArchive:
    """先归档 Compact，再由 dev 原转换器生成最终 A2UI，保证编辑链一致。"""
    adapted_a2ui = _adapt_to_dev_profile(template_a2ui, protocol_profile)
    try:
        compact_dsl = convert_a2ui_to_compact_dsl(adapted_a2ui, size=size)
    except CompactDslConversionError as exc:
        raise TemplateArchiveError("template A2UI cannot be archived as Compact DSL") from exc

    context = DslProcessingContext(
        size=size,
        card_spec=card_spec,
        task_spec=task_spec,
        protocol_profile=design_protocol_profile,
        design_profile_id=design_profile_id,
        data_capabilities=data_capabilities,
        event_candidates=event_candidates,
    )
    processor = get_dsl_processor(DslProcessorKind.DESIGN_COMPACT)
    result = await to_thread.run_sync(processor.process, compact_dsl, context)
    if result.errors:
        messages = "; ".join(item.repair_message() for item in result.errors)
        raise TemplateArchiveError(f"template Compact archive is invalid: {messages}")
    if not result.standard_dsl.strip():
        raise TemplateArchiveError("template Compact archive produced empty A2UI")
    _parse_three_messages(result.standard_dsl)
    return TemplateArchive(a2ui=result.standard_dsl, compact_dsl=compact_dsl)


def _adapt_to_dev_profile(
    a2ui: str,
    protocol_profile: dict[str, Any],
) -> str:
    messages = _parse_three_messages(a2ui)
    create_surface = messages[0]["createSurface"]
    update_components = messages[1]["updateComponents"]
    update_data_model = messages[2]["updateDataModel"]
    surface_ids = {
        create_surface.get("surfaceId"),
        update_components.get("surfaceId"),
        update_data_model.get("surfaceId"),
    }
    if len(surface_ids) != 1 or not all(isinstance(item, str) and item for item in surface_ids):
        raise TemplateArchiveError("template A2UI surfaceId values do not match")
    create_surface["catalogId"] = protocol_profile["catalogId"]
    components = update_components.get("components")
    if not isinstance(components, list):
        raise TemplateArchiveError("template A2UI components must be an array")
    root = next(
        (
            item
            for item in components
            if isinstance(item, dict) and item.get("id") == update_components.get("root")
        ),
        None,
    )
    if root is None:
        raise TemplateArchiveError("template A2UI root component is missing")
    styles = root.setdefault("styles", {})
    if not isinstance(styles, dict):
        raise TemplateArchiveError("template A2UI root styles must be an object")
    styles.update(
        {
            "width": "matchParent",
            "height": "matchParent",
            "borderRadius": 18,
            "clip": True,
        }
    )
    return "\n".join(
        json.dumps(item, ensure_ascii=False, separators=(",", ":"))
        for item in messages
    )


def _parse_three_messages(a2ui: str) -> list[dict[str, Any]]:
    lines = [line.strip() for line in a2ui.splitlines() if line.strip()]
    if len(lines) != 3:
        raise TemplateArchiveError("template A2UI must contain exactly three messages")
    messages: list[dict[str, Any]] = []
    expected_keys = ("createSurface", "updateComponents", "updateDataModel")
    for line, expected_key in zip(lines, expected_keys, strict=True):
        try:
            message = json.loads(line)
        except json.JSONDecodeError as exc:
            raise TemplateArchiveError("template A2UI contains invalid JSON") from exc
        if not isinstance(message, dict) or not isinstance(message.get(expected_key), dict):
            raise TemplateArchiveError(f"template A2UI is missing {expected_key}")
        if message.get("version") != "v0.9":
            raise TemplateArchiveError("template A2UI wire version must be v0.9")
        messages.append(message)
    return messages
