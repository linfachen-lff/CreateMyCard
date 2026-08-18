"""Strict JSON parsing for card import and future Search API boundaries."""

from __future__ import annotations

import json
from typing import cast

from api_schema import JSONObject, JSONValue

from .errors import InvalidSearchRequest


def _reject_constant(value: str) -> None:
    raise InvalidSearchRequest(
        "non_finite_number", f"{value} is not a valid JSON number"
    )


def _object_without_duplicates(
    pairs: list[tuple[str, JSONValue]],
) -> JSONObject:
    result: JSONObject = {}
    for key, value in pairs:
        if key in result:
            raise InvalidSearchRequest(
                "duplicate_key", f"duplicate JSON object key: {key}"
            )
        result[key] = value
    return result


def loads_strict_json(raw: str | bytes, *, max_bytes: int | None = None) -> JSONValue:
    """Parse standards-compliant JSON while rejecting duplicate object keys."""

    encoded = raw.encode("utf-8") if isinstance(raw, str) else raw
    if max_bytes is not None and len(encoded) > max_bytes:
        raise InvalidSearchRequest(
            "request_too_large", f"request body exceeds {max_bytes} bytes"
        )
    try:
        text = encoded.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise InvalidSearchRequest("invalid_encoding", "request must be UTF-8") from exc
    try:
        return cast(
            JSONValue,
            json.loads(
                text,
                object_pairs_hook=_object_without_duplicates,
                parse_constant=_reject_constant,
            ),
        )
    except InvalidSearchRequest:
        raise
    except json.JSONDecodeError as exc:
        raise InvalidSearchRequest("invalid_json", str(exc)) from exc


def parse_search_http_request(
    raw: bytes, *, max_bytes: int
) -> tuple[str | None, JSONObject | None]:
    """Return normalized query and inputData from a strict HTTP JSON object."""

    value = loads_strict_json(raw, max_bytes=max_bytes)
    if not isinstance(value, dict):
        raise InvalidSearchRequest("invalid_request", "request body must be an object")
    query = value.get("query")
    input_data = value.get("inputData")
    if query is not None and not isinstance(query, str):
        raise InvalidSearchRequest("invalid_query", "query must be a string or null")
    if input_data is not None and not isinstance(input_data, dict):
        raise InvalidSearchRequest(
            "invalid_input_data", "inputData must be an object or null"
        )
    normalized_query = query.strip() if isinstance(query, str) else None
    normalized_query = normalized_query or None
    if normalized_query is None and input_data is None:
        raise InvalidSearchRequest(
            "missing_input", "query and inputData cannot both be empty"
        )
    return normalized_query, input_data
