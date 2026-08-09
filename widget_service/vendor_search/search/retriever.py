"""Typed public Search entry point for future callers."""

from __future__ import annotations

import os
from functools import lru_cache
from pathlib import Path
from api_schema import JSONValue, MissResult, SearchRequest, SearchResult

from .errors import ObservedShapeError, PayloadLimitError, TemplateStoreError
from .hashing import compute_shape_signature
from .repository import SQLiteTemplateDAO
from .service import SearchService


@lru_cache(maxsize=1)
def get_default_search_service() -> SearchService:
    configured_path = os.environ.get("SEARCH_DB_PATH")
    database_path = (
        Path(configured_path)
        if configured_path
        else Path(__file__).resolve().parent / "data" / "templates.sqlite3"
    )
    template_dao = SQLiteTemplateDAO(database_path)
    template_dao.initialize()
    return SearchService(template_dao)


async def search_template(
    request: SearchRequest,
    *,
    service: SearchService | None = None,
) -> SearchResult:
    """Search by complete payload shape first, then by query tokens."""

    normalized = request.normalized()
    if normalized.query is None and normalized.input_data is None:
        raise ValueError("query and input_data cannot both be empty")
    payload = normalized.input_data
    if service is not None:
        active_service = service
    else:
        try:
            active_service = get_default_search_service()
        except (OSError, TemplateStoreError):
            structure_hash: str | None = None
            diagnostics: dict[str, JSONValue] = {"error_category": "store_unavailable"}
            if payload is not None:
                try:
                    signature = compute_shape_signature(payload)
                except (ObservedShapeError, PayloadLimitError) as exc:
                    diagnostics.update(
                        {"error_category": exc.code, "error_pointer": exc.pointer}
                    )
                    return MissResult(
                        miss_reason=exc.code,
                        diagnostics=diagnostics,
                    )
                structure_hash = signature.signature
                diagnostics["signature_version"] = signature.version
            return MissResult(
                structure_hash=structure_hash,
                miss_reason="store_unavailable",
                diagnostics=diagnostics,
            )
    return active_service.search(normalized)
