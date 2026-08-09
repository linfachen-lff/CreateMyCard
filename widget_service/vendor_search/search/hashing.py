"""Versioned observable-payload-shape signatures.

The signature describes only fields and JSON types present in one complete JSON
instance.  It deliberately does not infer a JSON Schema.
"""

from __future__ import annotations

import hashlib
import json
import math
from dataclasses import dataclass
from typing import TypeAlias

from api_schema import JSONArray, JSONValue

from .errors import ObservedShapeError, PayloadLimitError

SIGNATURE_VERSION = 1
SIGNATURE_ALGORITHM = "sha256"

ShapeAst: TypeAlias = JSONArray


@dataclass(frozen=True)
class PayloadLimits:
    """Resource limits applied before and during full shape traversal."""

    max_bytes: int = 1_048_576
    max_depth: int = 64
    max_array_items: int = 10_000
    max_nodes: int = 100_000


@dataclass(frozen=True)
class ShapeSignature:
    signature: str
    version: int
    canonical_ast: ShapeAst
    canonical_json: str


def _escape_pointer_segment(segment: str) -> str:
    return segment.replace("~", "~0").replace("/", "~1")


def _child_pointer(pointer: str, segment: str | int) -> str:
    escaped = _escape_pointer_segment(str(segment))
    return f"{pointer}/{escaped}" if pointer else f"/{escaped}"


class _ShapeBuilder:
    def __init__(self, limits: PayloadLimits) -> None:
        self._limits = limits
        self._nodes = 0

    def build(  # noqa: C901, PLR0912 - recursive JSON type dispatch
        self, value: JSONValue, *, pointer: str = "", depth: int = 0
    ) -> ShapeAst:
        if depth > self._limits.max_depth:
            raise PayloadLimitError(
                "max_depth_exceeded",
                f"payload nesting exceeds {self._limits.max_depth}",
                pointer=pointer,
            )

        self._nodes += 1
        if self._nodes > self._limits.max_nodes:
            raise PayloadLimitError(
                "max_nodes_exceeded",
                f"payload node count exceeds {self._limits.max_nodes}",
                pointer=pointer,
            )

        if value is None:
            return ["null"]
        if isinstance(value, bool):
            return ["boolean"]
        if isinstance(value, (int, float)):
            if isinstance(value, float) and not math.isfinite(value):
                raise ObservedShapeError(
                    "non_finite_number",
                    "NaN and Infinity are not valid JSON numbers",
                    pointer=pointer,
                )
            return ["number"]
        if isinstance(value, str):
            return ["string"]
        if isinstance(value, dict):
            entries: list[JSONValue] = []
            if not all(isinstance(key, str) for key in value):
                raise ObservedShapeError(
                    "non_string_key",
                    "JSON object keys must be strings",
                    pointer=pointer,
                )
            for key in sorted(value):
                entries.append(
                    [
                        key,
                        self.build(
                            value[key],
                            pointer=_child_pointer(pointer, key),
                            depth=depth + 1,
                        ),
                    ]
                )
            return ["object", entries]
        if isinstance(value, list):
            if len(value) > self._limits.max_array_items:
                raise PayloadLimitError(
                    "max_array_items_exceeded",
                    f"array length exceeds {self._limits.max_array_items}",
                    pointer=pointer,
                )
            if not value:
                raise ObservedShapeError(
                    "empty_array",
                    "empty arrays have no observable element shape",
                    pointer=pointer,
                )
            first = self.build(
                value[0], pointer=_child_pointer(pointer, 0), depth=depth + 1
            )
            for index, item in enumerate(value[1:], start=1):
                current = self.build(
                    item,
                    pointer=_child_pointer(pointer, index),
                    depth=depth + 1,
                )
                if current != first:
                    raise ObservedShapeError(
                        "heterogeneous_array",
                        "array elements have different recursive observable shapes",
                        pointer=_child_pointer(pointer, index),
                    )
            return ["array", first]
        raise ObservedShapeError(
            "non_json_type",
            f"unsupported JSON value type: {type(value).__name__}",
            pointer=pointer,
        )


def canonical_shape(value: JSONValue, limits: PayloadLimits | None = None) -> ShapeAst:
    """Build the canonical recursive shape AST after checking byte limits."""

    active_limits = limits or PayloadLimits()
    try:
        encoded = json.dumps(
            value,
            ensure_ascii=False,
            allow_nan=False,
            separators=(",", ":"),
        ).encode("utf-8")
    except (TypeError, ValueError) as exc:
        raise ObservedShapeError("invalid_json_value", str(exc)) from exc
    if len(encoded) > active_limits.max_bytes:
        raise PayloadLimitError(
            "max_bytes_exceeded",
            f"payload encoding exceeds {active_limits.max_bytes} bytes",
            pointer="",
        )
    return _ShapeBuilder(active_limits).build(value)


def compute_shape_signature(
    value: JSONValue, limits: PayloadLimits | None = None
) -> ShapeSignature:
    """Compute a deterministic SHA-256 signature for the canonical shape AST."""

    ast = canonical_shape(value, limits)
    canonical_json = json.dumps(
        ast,
        ensure_ascii=False,
        allow_nan=False,
        separators=(",", ":"),
    )
    prefix = f"observed-payload-shape:v{SIGNATURE_VERSION}\0".encode()
    digest = hashlib.sha256(prefix + canonical_json.encode("utf-8")).hexdigest()
    return ShapeSignature(
        signature=digest,
        version=SIGNATURE_VERSION,
        canonical_ast=ast,
        canonical_json=canonical_json,
    )
