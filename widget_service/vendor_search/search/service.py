"""Hash-first Search orchestration and keyword fallback."""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import cast

from api_schema import (
    JSONArray,
    JSONValue,
    KeywordMatchResult,
    MissResult,
    SearchRequest,
    SearchResult,
    StructureMatchResult,
)

from .errors import (
    BindingError,
    ObservedShapeError,
    PayloadLimitError,
    TemplateStoreError,
    TemplateValidationError,
)
from .hashing import PayloadLimits, compute_shape_signature
from .repository import KeywordCandidate, SearchTemplateDAO
from .tokenization import tokenize
from .validation import bind_template, validate_template


@dataclass(frozen=True)
class SearchConfig:
    coverage_threshold: float = 0.4
    candidate_limit: int = 20
    payload_limits: PayloadLimits = field(default_factory=PayloadLimits)


class SearchService:
    def __init__(
        self,
        template_dao: SearchTemplateDAO,
        config: SearchConfig | None = None,
    ) -> None:
        self.template_dao = template_dao
        self.config = config or SearchConfig()

    def search(  # noqa: PLR0911 - explicit outcome routing table
        self, request: SearchRequest
    ) -> SearchResult:
        started = time.perf_counter()
        normalized = request.normalized()
        if normalized.query is None and normalized.input_data is None:
            raise ValueError("query and input_data cannot both be empty")

        diagnostics: dict[str, JSONValue] = {}
        structure_hash: str | None = None
        if normalized.input_data is not None:
            try:
                signature = compute_shape_signature(
                    normalized.input_data, self.config.payload_limits
                )
            except (ObservedShapeError, PayloadLimitError) as exc:
                diagnostics.update(
                    {
                        "signature_version": None,
                        "error_category": exc.code,
                        "error_pointer": exc.pointer,
                    }
                )
                return self._miss(
                    exc.code,
                    structure_hash=None,
                    diagnostics=diagnostics,
                    started=started,
                )
            structure_hash = signature.signature
            diagnostics["signature_version"] = signature.version
            try:
                matches = self.template_dao.find_by_signature(
                    signature.signature, signature.version
                )
            except TemplateStoreError:
                diagnostics["error_category"] = "store_unavailable"
                return self._miss(
                    "store_unavailable",
                    structure_hash=structure_hash,
                    diagnostics=diagnostics,
                    started=started,
                )
            if len(matches) > 1:
                diagnostics["candidate_count"] = len(matches)
                diagnostics["error_category"] = "ambiguous_structure"
                return self._miss(
                    "ambiguous_structure",
                    structure_hash=structure_hash,
                    diagnostics=diagnostics,
                    started=started,
                )
            if len(matches) == 1:
                template = matches[0]
                try:
                    rendered = bind_template(
                        template.reference_jsonl, normalized.input_data
                    )
                except (TemplateValidationError, BindingError) as exc:
                    diagnostics.update(
                        {
                            "error_category": exc.code,
                            "error_pointer": exc.pointer,
                        }
                    )
                    return self._miss(
                        exc.code,
                        structure_hash=structure_hash,
                        diagnostics=diagnostics,
                        started=started,
                    )
                diagnostics["elapsed_ms"] = self._elapsed_ms(started)
                return StructureMatchResult(
                    rendered_jsonl=rendered,
                    template_id=template.template_id,
                    structure_hash=structure_hash,
                    diagnostics=diagnostics,
                )

        if normalized.query is None:
            return self._miss(
                "structure_not_found" if structure_hash else "query_not_provided",
                structure_hash=structure_hash,
                diagnostics=diagnostics,
                started=started,
            )
        return self._keyword_search(
            normalized.query,
            structure_hash=structure_hash,
            diagnostics=diagnostics,
            started=started,
        )

    def _keyword_search(
        self,
        query: str,
        *,
        structure_hash: str | None,
        diagnostics: dict[str, JSONValue],
        started: float,
    ) -> SearchResult:
        query_tokens = tokenize(query)
        diagnostics["query_tokens"] = cast(JSONArray, query_tokens.copy())
        if not query_tokens:
            return self._miss(
                "keyword_not_found",
                structure_hash=structure_hash,
                diagnostics=diagnostics,
                started=started,
            )
        try:
            candidates = self.template_dao.keyword_candidates(
                query_tokens, self.config.candidate_limit
            )
        except TemplateStoreError:
            diagnostics["error_category"] = "store_unavailable"
            return self._miss(
                "store_unavailable",
                structure_hash=structure_hash,
                diagnostics=diagnostics,
                started=started,
            )
        diagnostics["candidate_count"] = len(candidates)
        scored = [
            (candidate, self._coverage(query_tokens, candidate))
            for candidate in candidates
        ]
        eligible = [
            item for item in scored if item[1] >= self.config.coverage_threshold
        ]
        eligible.sort(
            key=lambda item: (
                item[0].bm25_score,
                -item[1],
                item[0].template.template_id,
            )
        )
        if not eligible:
            diagnostics["coverage"] = max((score for _, score in scored), default=0.0)
            return self._miss(
                "coverage_below_threshold" if candidates else "keyword_not_found",
                structure_hash=structure_hash,
                diagnostics=diagnostics,
                started=started,
            )
        candidate, coverage = eligible[0]
        try:
            reference = validate_template(
                candidate.template.reference_jsonl, mode="reference"
            ).normalized_jsonl
        except TemplateValidationError as exc:
            diagnostics.update(
                {"error_category": exc.code, "error_pointer": exc.pointer}
            )
            return self._miss(
                "template_invalid",
                structure_hash=structure_hash,
                diagnostics=diagnostics,
                started=started,
            )
        reference_tokens = tokenize(
            " ".join(
                [
                    candidate.template.description,
                    *candidate.template.tags,
                ]
            )
        )
        diagnostics.update(
            {
                "reference_tokens": cast(JSONArray, reference_tokens),
                "bm25_score": candidate.bm25_score,
                "coverage": coverage,
                "elapsed_ms": self._elapsed_ms(started),
            }
        )
        return KeywordMatchResult(
            reference_jsonl=reference,
            template_id=candidate.template.template_id,
            structure_hash=structure_hash,
            diagnostics=diagnostics,
        )

    @staticmethod
    def _coverage(query_tokens: list[str], candidate: KeywordCandidate) -> float:
        query_set = set(query_tokens)
        reference_set = set(
            tokenize(
                " ".join([candidate.template.description, *candidate.template.tags])
            )
        )
        return len(query_set & reference_set) / len(query_set)

    def _miss(
        self,
        reason: str,
        *,
        structure_hash: str | None,
        diagnostics: dict[str, JSONValue],
        started: float,
    ) -> SearchResult:
        diagnostics.setdefault("elapsed_ms", self._elapsed_ms(started))
        return MissResult(
            structure_hash=structure_hash,
            miss_reason=reason,
            diagnostics=diagnostics,
        )

    @staticmethod
    def _elapsed_ms(started: float) -> float:
        return round((time.perf_counter() - started) * 1000, 3)
