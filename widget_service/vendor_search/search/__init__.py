"""Observable-shape and keyword template retrieval."""

from api_schema import (
    JSONArray,
    JSONObject,
    JSONScalar,
    JSONValue,
    KeywordMatchResult,
    MissResult,
    SearchRequest,
    SearchResult,
    StructureMatchResult,
)

from .hashing import PayloadLimits, ShapeSignature, compute_shape_signature
from .repository import (
    SQLiteTemplateDAO,
    SearchTemplateDAO,
    TemplateDAO,
    TemplateRecord,
)
from .retriever import get_default_search_service, search_template
from .service import SearchConfig, SearchService

__all__ = [
    "JSONArray",
    "JSONObject",
    "JSONScalar",
    "JSONValue",
    "KeywordMatchResult",
    "MissResult",
    "PayloadLimits",
    "SearchConfig",
    "SearchRequest",
    "SearchResult",
    "SearchService",
    "ShapeSignature",
    "SQLiteTemplateDAO",
    "StructureMatchResult",
    "SearchTemplateDAO",
    "TemplateDAO",
    "TemplateRecord",
    "compute_shape_signature",
    "get_default_search_service",
    "search_template",
]
