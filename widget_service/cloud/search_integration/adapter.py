"""search 整合适配器。

把生成请求 :class:`GenerateWidgetCardRequest` 映射为 vendored 的
``SearchRequest``，并统一路由为 :class:`SearchDecision`。任何失败
（vendored 不可导入、检索异常、模板库不可用）都优雅降级为 miss，
绝不阻断生成主流程。
"""

from __future__ import annotations

import logging
import os
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any, Literal

from api.schemas import GenerateWidgetCardRequest

from . import vendored_loader

logger = logging.getLogger(__name__)

SearchOutcomeKind = Literal["structure_match", "keyword_match", "miss", "disabled"]

#: 把生成请求的候选数据映射为检索用的结构化 JSON。
InputDataMapper = Callable[[GenerateWidgetCardRequest], dict[str, Any]]


def default_input_data_mapper(request: GenerateWidgetCardRequest) -> dict[str, Any]:
    """把 candidateDataBindings 序列化为规范 JSON，供结构 Hash 使用。

    该映射是可配置的：真实模板库数据格式对齐时，替换
    :class:`SearchIntegrationAdapter` 的 ``input_data_mapper`` 即可。
    """
    return {
        "dataBindings": [
            {
                "capabilityId": binding.capabilityId,
                "arguments": binding.arguments,
                "writeResultTo": binding.writeResultTo,
                "candidateOutputFields": list(binding.candidateOutputFields or []),
            }
            for binding in (request.candidateDataBindings or [])
        ]
    }


@dataclass(frozen=True)
class SearchDecision:
    """面向生成主流程的检索结论（vendored SearchResult 的本地投影）。"""

    outcome: SearchOutcomeKind
    rendered_jsonl: str | None = None
    reference_jsonl: str | None = None
    template_id: str | None = None
    structure_hash: str | None = None
    miss_reason: str | None = None
    diagnostics: dict[str, Any] = field(default_factory=dict)

    @property
    def few_shot(self) -> str | None:
        """keyword_match 时的少样本骨架。"""
        return self.reference_jsonl

    @property
    def cached_dsl(self) -> str | None:
        """structure_match 时可直接喂转换器的 Compact DSL。"""
        return self.rendered_jsonl if self.outcome == "structure_match" else None


class SearchIntegrationAdapter:
    """生成请求 → SearchRequest → SearchDecision 的适配器。"""

    def __init__(self, input_data_mapper: InputDataMapper | None = None) -> None:
        self.input_data_mapper = input_data_mapper or default_input_data_mapper

    def build_search_request(
        self,
        request: GenerateWidgetCardRequest,
        input_data: dict[str, Any] | None = None,
    ) -> Any | None:
        """构建 vendored SearchRequest；vendored 不可用时返回 None。

        input_data 显式传入时使用它（如降维后的 dataModelSchema）；
        否则回退到可配置的 input_data_mapper。
        """
        if not vendored_loader.search_available():
            return None
        effective_input = (
            input_data if input_data is not None else self.input_data_mapper(request)
        )
        return vendored_loader.api_schema.SearchRequest(
            query=request.userQuery or None,
            input_data=effective_input,
        )

    async def lookup(
        self,
        request: GenerateWidgetCardRequest,
        *,
        service: Any | None = None,
        enabled: bool = True,
        input_data: dict[str, Any] | None = None,
    ) -> SearchDecision:
        """执行检索并返回 SearchDecision。

        - enabled=False → disabled；
        - vendored 不可用 → miss(vendored_unavailable)；
        - 检索异常 → miss(search_error)；
        - input_data：显式传入的检索载荷（推荐降维后的 dataModelSchema）；
          缺省时回退到 input_data_mapper。
        - 其他按 outcome 投影。
        """
        if not enabled:
            return SearchDecision(outcome="disabled")
        if not vendored_loader.search_available():
            logger.warning(
                "search_vendored_unavailable error=%s",
                vendored_loader.import_error(),
            )
            return SearchDecision(outcome="miss", miss_reason="vendored_unavailable")
        if service is None:
            self._configure_default_db_path()
        search_request = self.build_search_request(request, input_data=input_data)
        if search_request is None:
            return SearchDecision(outcome="miss", miss_reason="vendored_unavailable")
        try:
            result = await vendored_loader.search_template(
                search_request, service=service
            )
        except ValueError:
            # query 与 input_data 同时为空等输入不合法 → 不参与检索
            return SearchDecision(outcome="miss", miss_reason="invalid_search_request")
        except Exception as exc:  # noqa: BLE001 - 双保险优雅降级
            logger.warning("search_failed error=%s", exc)
            return SearchDecision(outcome="miss", miss_reason="search_error")
        return self._classify(result)

    @staticmethod
    def _classify(result: Any) -> SearchDecision:
        outcome = getattr(result, "outcome", "miss")
        diagnostics = dict(getattr(result, "diagnostics", None) or {})
        if outcome == "structure_match":
            return SearchDecision(
                outcome="structure_match",
                rendered_jsonl=result.rendered_jsonl,
                template_id=result.template_id,
                structure_hash=result.structure_hash,
                diagnostics=diagnostics,
            )
        if outcome == "keyword_match":
            return SearchDecision(
                outcome="keyword_match",
                reference_jsonl=result.reference_jsonl,
                template_id=result.template_id,
                structure_hash=result.structure_hash,
                diagnostics=diagnostics,
            )
        return SearchDecision(
            outcome="miss",
            miss_reason=result.miss_reason or "miss",
            structure_hash=getattr(result, "structure_hash", None),
            diagnostics=diagnostics,
        )

    @staticmethod
    def _configure_default_db_path() -> None:
        """把配置里的 search_db_path 写入 SEARCH_DB_PATH（首次调用前）。"""
        if os.environ.get("SEARCH_DB_PATH"):
            return
        try:
            from config.config import get_settings

            search_db_path = get_settings().search_db_path
        except Exception:  # noqa: BLE001 - 配置读取失败不阻断
            return
        if search_db_path:
            os.environ["SEARCH_DB_PATH"] = search_db_path
