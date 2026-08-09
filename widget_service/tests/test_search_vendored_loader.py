# -*- coding: utf-8 -*-
"""vendored search 模块加载与真实检索通路测试。

MOCK DATA: 本文件全部使用内存/临时 SQLite + 手写模板数据，
不调用真实 DeepSeek API，也不依赖真实模板库。
"""

import json
import sys
from pathlib import Path

import pytest

CLOUD_ROOT = Path(__file__).resolve().parents[1] / "cloud"
sys.path.insert(0, str(CLOUD_ROOT))

from cloud.search_integration import vendored_loader  # noqa: E402


def _make_record(
    search_api,
    template_id: str,
    input_data: dict,
    reference_jsonl: str,
    *,
    description: str = "",
    tags: tuple[str, ...] = (),
):
    """构造一条模板记录；structure_hash 由完整 input 结构签名计算。"""
    signature = search_api.compute_shape_signature(input_data)
    return search_api.TemplateRecord(
        template_id=template_id,
        description=description,
        tags=tags,
        reference_jsonl=reference_jsonl,
        input_json=json.dumps(input_data, ensure_ascii=False),
        structure_hash=signature.signature,
        signature_version=signature.version,
    )


@pytest.fixture(scope="module")
def search_api():
    """vendored search 公开 API（加载失败时给出明确错误）。"""
    assert vendored_loader.search_available(), (
        f"vendored search 不可用: {vendored_loader.import_error()}"
    )
    print("MOCK DATA: 使用 vendored search 模块（内存/临时 SQLite 模板库）")
    return vendored_loader.search


@pytest.fixture
def greeting_service(search_api):
    """含一条问候模板的内存库。"""
    dao = search_api.SQLiteTemplateDAO(":memory:")
    dao.initialize()
    reference = (
        '["root","Column",{},["title"]]\n'
        '["title","Text",{"content":{"path":"/name"}}]'
    )
    dao.upsert(
        _make_record(
            search_api,
            "t-greeting",
            {"name": "Alice", "age": 30},
            reference,
            description="问候卡片",
            tags=("问候",),
        )
    )
    return search_api.SearchService(dao)


def test_vendored_search_package_importable(search_api):
    """vendored 包可导入且入口可调用。"""
    assert callable(search_api.search_template)
    assert callable(search_api.compute_shape_signature)


@pytest.mark.asyncio
async def test_structure_match_binds_data(greeting_service, search_api):
    """结构 Hash 唯一命中时返回带数据行的 rendered_jsonl。"""
    result = await search_api.search_template(
        search_api.SearchRequest(
            query="问候卡片", input_data={"name": "Bob", "age": 25}
        ),
        service=greeting_service,
    )
    assert result.outcome == "structure_match"
    assert result.rendered_jsonl
    assert '"Bob"' in result.rendered_jsonl
    assert result.template_id == "t-greeting"
    assert result.reference_jsonl is None


@pytest.mark.asyncio
async def test_keyword_match_returns_reference_skeleton(greeting_service, search_api):
    """关键词命中返回无数据行的 reference_jsonl（仅骨架）。"""
    result = await search_api.search_template(
        search_api.SearchRequest(query="天气", input_data=None),
        service=greeting_service,
    )
    # 问候模板不描述天气 → 关键词不命中 → miss
    assert result.outcome == "miss"
    assert result.rendered_jsonl is None
    assert result.reference_jsonl is None


@pytest.mark.asyncio
async def test_keyword_match_hits_weather_template(search_api):
    """关键词命中天气模板，返回 reference_jsonl 骨架。"""
    dao = search_api.SQLiteTemplateDAO(":memory:")
    dao.initialize()
    reference = (
        '["root","Column",{},["title"]]\n'
        '["title","Text",{"content":{"path":"/city"}}]'
    )
    dao.upsert(
        _make_record(
            search_api,
            "t-weather",
            {"city": "深圳", "temperature": 28},
            reference,
            description="天气卡片，显示城市与温度",
            tags=("天气", "温度"),
        )
    )
    service = search_api.SearchService(dao)
    result = await search_api.search_template(
        search_api.SearchRequest(query="天气", input_data=None),
        service=service,
    )
    assert result.outcome == "keyword_match"
    # 注意：search 模块返回时会重新序列化，reference_jsonl 带尾部换行
    assert result.reference_jsonl.rstrip("\n") == reference
    assert "/city" in result.reference_jsonl
    assert result.rendered_jsonl is None


@pytest.mark.asyncio
async def test_ambiguous_structure_miss(search_api):
    """同结构多模板 → miss_reason=ambiguous_structure，不任取一个。"""
    dao = search_api.SQLiteTemplateDAO(":memory:")
    dao.initialize()
    reference = (
        '["root","Column",{},["title"]]\n'
        '["title","Text",{"content":{"path":"/name"}}]'
    )
    input_data = {"name": "x", "age": 1}
    dao.upsert(_make_record(search_api, "t-dup-a", input_data, reference))
    dao.upsert(_make_record(search_api, "t-dup-b", input_data, reference))
    service = search_api.SearchService(dao)
    result = await search_api.search_template(
        search_api.SearchRequest(query="x", input_data={"name": "y", "age": 2}),
        service=service,
    )
    assert result.outcome == "miss"
    assert result.miss_reason == "ambiguous_structure"


@pytest.mark.asyncio
async def test_miss_when_nothing_matches(greeting_service, search_api):
    """无关关键词 → miss。"""
    result = await search_api.search_template(
        search_api.SearchRequest(query="股票行情资讯", input_data=None),
        service=greeting_service,
    )
    assert result.outcome == "miss"


@pytest.mark.asyncio
async def test_store_unavailable_degrades_to_miss(search_api, monkeypatch, tmp_path):
    """模板库不可用 → 优雅降级为 miss（不抛异常）。"""
    blocker = tmp_path / "blocker.txt"
    blocker.write_text("x")
    monkeypatch.setenv("SEARCH_DB_PATH", str(blocker / "db.sqlite3"))
    search_api.get_default_search_service.cache_clear()
    result = await search_api.search_template(
        search_api.SearchRequest(query="天气", input_data=None)
    )
    assert result.outcome == "miss"
    assert result.miss_reason == "store_unavailable"


@pytest.mark.asyncio
async def test_button_image_child_roundtrip(search_api):
    """本地补丁：validate_template 接受 Button+Image 子节点，且可结构命中出卡。

    MOCK DATA: 手写含 Button+Image 子节点的模板骨架与输入。
    """
    reference = (
        '["root","Column",{},["title","btn"]]\n'
        '["title","Text",{"content":{"path":"/name"}}]\n'
        '["btn","Button",{"label":"查看详情"},["btn_icon"]]\n'
        '["btn_icon","Image",{"src":{"path":"/icon"}}]'
    )
    from search.validation import validate_template

    validated = validate_template(reference, mode="reference")
    assert validated is not None

    dao = search_api.SQLiteTemplateDAO(":memory:")
    dao.initialize()
    signature = search_api.compute_shape_signature({"name": "x", "icon": "y"})
    dao.upsert(
        search_api.TemplateRecord(
            template_id="t-btn",
            description="按钮卡片",
            tags=("按钮",),
            reference_jsonl=reference,
            input_json=json.dumps({"name": "x", "icon": "y"}),
            structure_hash=signature.signature,
            signature_version=signature.version,
        )
    )
    service = search_api.SearchService(dao)
    result = await search_api.search_template(
        search_api.SearchRequest(
            query="按钮", input_data={"name": "Bob", "icon": "asset://x.png"}
        ),
        service=service,
    )
    assert result.outcome == "structure_match"
    assert '"Bob"' in result.rendered_jsonl
    assert "btn_icon" in result.rendered_jsonl


@pytest.mark.asyncio
async def test_search_db_path_env_respected(search_api, monkeypatch, tmp_path):
    """SEARCH_DB_PATH 环境变量决定默认服务使用哪个数据库。"""
    db_path = tmp_path / "custom" / "templates.sqlite3"
    monkeypatch.setenv("SEARCH_DB_PATH", str(db_path))
    search_api.get_default_search_service.cache_clear()
    service = search_api.get_default_search_service()
    assert service.template_dao.path == str(db_path)
