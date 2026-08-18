"""Import card prompt payloads as safe, data-free Compact template skeletons."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

from api_schema import JSONArray, JSONObject, JSONValue

from .errors import (
    InvalidSearchRequest,
    ObservedShapeError,
    PayloadLimitError,
    TemplateValidationError,
)
from .hashing import PayloadLimits, compute_shape_signature
from .json_boundary import loads_strict_json
from .repository import DescriptionDAO, TemplateDAO, TemplateRecord
from .validation import validate_template


@dataclass(frozen=True)
class ImportRejection:
    template_id: str
    reason: str
    pointer: str | None


@dataclass(frozen=True)
class ImportReport:
    imported_template_ids: tuple[str, ...]
    rejected: tuple[ImportRejection, ...]


class _SkeletonBuilder:
    """Build a conservative Compact skeleton from structure, never sample values."""

    def __init__(self, title: str) -> None:
        self._counter = 0
        self._lines: list[JSONArray] = []
        self._title = title

    def build(self, payload: JSONObject) -> str:
        root_children: JSONArray = ["template_title"]
        self._lines.append(
            [
                "root",
                "Column",
                {
                    "width": "matchParent",
                    "padding": 12,
                    "space": 8,
                    "borderRadius": 16,
                },
                root_children,
            ]
        )
        self._lines.append(
            ["template_title", "Text", {"content": self._title, "design": "title"}]
        )
        for key, value in payload.items():
            component_id = self._build_value(
                key=key,
                value=value,
                absolute_path=f"/{_escape(key)}",
                relative_path=None,
            )
            if component_id is not None:
                root_children.append(component_id)
        return (
            "\n".join(
                json.dumps(line, ensure_ascii=False, separators=(",", ":"))
                for line in self._lines
            )
            + "\n"
        )

    def _next_id(self, prefix: str) -> str:
        self._counter += 1
        return f"{prefix}_{self._counter}"

    def _build_value(
        self,
        *,
        key: str,
        value: JSONValue,
        absolute_path: str,
        relative_path: str | None,
    ) -> str | None:
        if isinstance(value, dict):
            group_id = self._next_id("group")
            children: JSONArray = []
            self._lines.append(
                [group_id, "Column", {"space": 4, "width": "matchParent"}, children]
            )
            for child_key, child_value in value.items():
                child_absolute = f"{absolute_path}/{_escape(child_key)}"
                child_relative = (
                    f"{relative_path}/{_escape(child_key)}"
                    if relative_path
                    else _escape(child_key)
                    if relative_path is not None
                    else None
                )
                child_id = self._build_value(
                    key=child_key,
                    value=child_value,
                    absolute_path=child_absolute,
                    relative_path=child_relative,
                )
                if child_id is not None:
                    children.append(child_id)
            if not children:
                self._lines.pop()
                return None
            return group_id
        if isinstance(value, list):
            if not value or not isinstance(value[0], dict) or relative_path is not None:
                # Scalar and nested arrays still participate in the full signature, but
                # no unapproved item-self or nested relative binding syntax is invented.
                return None
            list_id = self._next_id("list")
            item_id = self._next_id("item")
            item_children: JSONArray = []
            self._lines.append(
                [
                    list_id,
                    "List",
                    {"space": 8, "width": "matchParent"},
                    {"componentId": item_id, "path": absolute_path},
                ]
            )
            self._lines.append(
                [item_id, "Column", {"space": 4, "width": "matchParent"}, item_children]
            )
            for child_key, child_value in value[0].items():
                child_id = self._build_value(
                    key=child_key,
                    value=child_value,
                    absolute_path=f"{absolute_path}/0/{_escape(child_key)}",
                    relative_path=_escape(child_key),
                )
                if child_id is not None:
                    item_children.append(child_id)
            if not item_children:
                # Remove the List and empty item template; data remains in the signature.
                self._lines.pop()
                self._lines.pop()
                return None
            return list_id

        row_id = self._next_id("field")
        label_id = self._next_id("label")
        value_id = self._next_id("value")
        path = relative_path if relative_path is not None else absolute_path
        self._lines.extend(
            [
                [
                    row_id,
                    "Row",
                    {"space": 8, "width": "matchParent"},
                    [label_id, value_id],
                ],
                [label_id, "Text", {"content": key, "design": "caption"}],
                [
                    value_id,
                    "Text",
                    {
                        "content": {"path": path},
                        "layoutWeight": 1,
                        "width": "matchParent",
                    },
                ],
            ]
        )
        return row_id


def _escape(segment: str) -> str:
    return segment.replace("~", "~0").replace("/", "~1")


def import_cards(
    cards_root: str | Path,
    template_dao: TemplateDAO,
    description_dao: DescriptionDAO,
    *,
    replace: bool = False,
    limits: PayloadLimits | None = None,
) -> ImportReport:
    """Import all prompt JSON files; reject unsafe instances with exact pointers."""

    root = Path(cards_root)
    prompt_root = root / "prompts"
    template_dao.initialize()
    imported: list[str] = []
    rejected: list[ImportRejection] = []
    records: list[TemplateRecord] = []
    for prompt_path in sorted(prompt_root.glob("*.json"), key=lambda path: path.name):
        template_id = prompt_path.stem
        try:
            raw = loads_strict_json(prompt_path.read_bytes())
            if not isinstance(raw, dict):
                raise InvalidSearchRequest(
                    "invalid_card", "card prompt must be an object"
                )
            title = raw.get("title")
            payload = raw.get("input")
            if not isinstance(title, str) or not title.strip():
                raise InvalidSearchRequest(
                    "invalid_title", "card title must be non-empty"
                )
            if not isinstance(payload, dict):
                raise InvalidSearchRequest(
                    "invalid_input", "card input must be an object"
                )
            metadata = description_dao.find(title.strip(), payload)
            if metadata is None:
                raise InvalidSearchRequest(
                    "description_not_found",
                    "card has no unique LLM-generated description",
                )
            signature = compute_shape_signature(payload, limits)
            skeleton = _SkeletonBuilder(title.strip()).build(payload)
            reference = validate_template(skeleton, mode="reference").normalized_jsonl
            records.append(
                TemplateRecord(
                    template_id=template_id,
                    description=metadata.description,
                    tags=metadata.tags,
                    reference_jsonl=reference,
                    input_json=json.dumps(
                        payload,
                        ensure_ascii=False,
                        allow_nan=False,
                        separators=(",", ":"),
                    ),
                    structure_hash=signature.signature,
                    signature_version=signature.version,
                )
            )
        except (
            InvalidSearchRequest,
            ObservedShapeError,
            PayloadLimitError,
            TemplateValidationError,
        ) as exc:
            rejected.append(
                ImportRejection(template_id, exc.code, getattr(exc, "pointer", None))
            )
            continue
        imported.append(template_id)
    if replace:
        template_dao.replace_all(records)
    else:
        for record in records:
            template_dao.upsert(record)
    return ImportReport(tuple(imported), tuple(rejected))
