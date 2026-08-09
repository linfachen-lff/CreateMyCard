# -*- coding: utf-8 -*-
"""SearchIntegrationAdapter 单元测试。

MOCK DATA: 本文件 monkeypatch search_template 返回 canned 结果，
不调用真实模板库或 DeepSeek API。
"""

import sys
from pathlib import Path

import pytest

CLOUD_ROOT = Path(__file__).resolve().parents[1] / "cloud"
sys.path.insert(0, str(CLOUD_ROOT))

from cloud.search_integration import vendored_loader  # noqa: E402
from cloud.search_integration.adapter import (  # noqa: E402
    SearchIntegrationAdapter,
    default_input_data_mapper,
)

from api.schemas import GenerateWidgetCardRequest  # noqa: E402
from models.generation import CandidateDataBinding, DeviceContext  # noqa: E402


def _make_request(user_query: str = "生成问候卡片") -> GenerateWidgetCardRequest:
    return GenerateWidgetCardRequest(
        uid="u1",
        device=DeviceContext(romVersion="HarmonyOS-6.0"),
        userQuery=user_query,
        title="问候",
        description="问候卡片",
        candidateDataBindings=[
            CandidateDataBinding(
                capabilityId="cap.weather",
                arguments={"city": "深圳"},
                writeResultTo="weather",
                candidateOutputFields=["city"],
            )
        ],
    )


@pytest.mark.asyncio
async def test_build_search_request_maps_bindings():
    """userQuery → query；candidateDataBindings → input_data。"""
    adapter = SearchIntegrationAdapter()
    search_request = adapter.build_search_request(_make_request())
    assert search_request.query == "生成问候卡片"
    assert search_request.input_data["dataBindings"][0]["capabilityId"] == "cap.weather"
    assert search_request.input_data["dataBindings"][0]["writeResultTo"] == "weather"


def test_default_input_data_mapper_serializes_bindings():
    """默认 mapper 把候选绑定序列化为规范 JSON。"""
    payload = default_input_data_mapper(_make_request())
    assert payload["dataBindings"][0]["arguments"] == {"city": "深圳"}
    assert payload["dataBindings"][0]["candidateOutputFields"] == ["city"]


@pytest.mark.asyncio
async def test_lookup_disabled():
    """开关关闭 → outcome=disabled。"""
    adapter = SearchIntegrationAdapter()
    decision = await adapter.lookup(_make_request(), enabled=False)
    assert decision.outcome == "disabled"
    assert decision.cached_dsl is None
    assert decision.few_shot is None


@pytest.mark.asyncio
async def test_lookup_structure_match(monkeypatch):
    """结构命中 → rendered_jsonl 进入 cached_dsl。"""
    print("MOCK DATA: canned structure_match 结果")

    async def fake_search(request, *, service=None):
        return vendored_loader.api_schema.StructureMatchResult(
            rendered_jsonl='["root","Column",{},["t"]]\n["t","Text",{"content":{"path":"/name"}}]',
            template_id="t-canned",
            structure_hash="canned-hash",
        )

    monkeypatch.setattr(vendored_loader, "search_template", fake_search)
    decision = await SearchIntegrationAdapter().lookup(_make_request(), enabled=True)
    assert decision.outcome == "structure_match"
    assert decision.cached_dsl
    assert decision.few_shot is None
    assert decision.template_id == "t-canned"


@pytest.mark.asyncio
async def test_lookup_keyword_match(monkeypatch):
    """关键词命中 → reference_jsonl 进入 few_shot。"""
    print("MOCK DATA: canned keyword_match 结果")

    async def fake_search(request, *, service=None):
        return vendored_loader.api_schema.KeywordMatchResult(
            reference_jsonl='["root","Column",{},["t"]]\n["t","Text",{"content":{"path":"/name"}}]',
            template_id="t-canned",
        )

    monkeypatch.setattr(vendored_loader, "search_template", fake_search)
    decision = await SearchIntegrationAdapter().lookup(_make_request(), enabled=True)
    assert decision.outcome == "keyword_match"
    assert decision.few_shot
    assert decision.cached_dsl is None


@pytest.mark.asyncio
async def test_lookup_miss(monkeypatch):
    """未命中 → miss，无 rendered/reference。"""
    print("MOCK DATA: canned miss 结果")

    async def fake_search(request, *, service=None):
        return vendored_loader.api_schema.MissResult(
            miss_reason="no_match", structure_hash="h1"
        )

    monkeypatch.setattr(vendored_loader, "search_template", fake_search)
    decision = await SearchIntegrationAdapter().lookup(_make_request(), enabled=True)
    assert decision.outcome == "miss"
    assert decision.miss_reason == "no_match"
    assert decision.cached_dsl is None
    assert decision.few_shot is None


@pytest.mark.asyncio
async def test_lookup_exception_degrades_to_miss(monkeypatch):
    """检索异常 → 优雅降级为 miss。"""
    print("MOCK DATA: 抛异常的 fake search_template")

    async def fake_search(request, *, service=None):
        raise RuntimeError("boom")

    monkeypatch.setattr(vendored_loader, "search_template", fake_search)
    decision = await SearchIntegrationAdapter().lookup(_make_request(), enabled=True)
    assert decision.outcome == "miss"
    assert decision.miss_reason == "search_error"


@pytest.mark.asyncio
async def test_lookup_vendored_unavailable_degrades(monkeypatch):
    """vendored 不可导入 → miss(vendored_unavailable)。"""
    monkeypatch.setattr(vendored_loader, "search_available", lambda: False)
    decision = await SearchIntegrationAdapter().lookup(_make_request(), enabled=True)
    assert decision.outcome == "miss"
    assert decision.miss_reason == "vendored_unavailable"


@pytest.mark.asyncio
async def test_custom_input_data_mapper_is_used(monkeypatch):
    """自定义 mapper 决定 input_data。"""
    captured: dict = {}

    async def fake_search(request, *, service=None):
        captured["input_data"] = request.input_data
        return vendored_loader.api_schema.MissResult(miss_reason="no_hit")

    monkeypatch.setattr(vendored_loader, "search_template", fake_search)
    adapter = SearchIntegrationAdapter(
        input_data_mapper=lambda req: {"custom": 1},
    )
    await adapter.lookup(_make_request(), enabled=True)
    assert captured["input_data"] == {"custom": 1}


@pytest.mark.asyncio
async def test_lookup_uses_explicit_input_data(monkeypatch):
    """显式传入的 input_data（如降维后的 dataModelSchema）直接用于检索。"""
    captured: dict = {}

    async def fake_search(request, *, service=None):
        captured["input_data"] = request.input_data
        return vendored_loader.api_schema.MissResult(miss_reason="no_hit")

    monkeypatch.setattr(vendored_loader, "search_template", fake_search)
    explicit = {"data": {"weather": {"current": {"temperatureText": "26℃"}}}}
    await SearchIntegrationAdapter().lookup(
        _make_request(),
        enabled=True,
        input_data=explicit,
    )
    assert captured["input_data"] == explicit
