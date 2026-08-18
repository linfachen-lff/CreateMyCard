# -*- coding: utf-8 -*-
"""search 缓存与 compact 生成路由的集成测试。

MOCK DATA: 通过 monkeypatch _search_adapter.lookup 注入 canned SearchDecision，
模型输出用合法 Compact DSL 桩；不调用真实模板库或 DeepSeek API。
"""

import importlib
import json
import sys
from pathlib import Path

from fastapi.testclient import TestClient

from ws_response_parser import parse_legacy_stream_content

PROJECT_ROOT = Path(__file__).resolve().parents[1]
CLOUD_ROOT = PROJECT_ROOT / "cloud"
SESSION_ID = "7676c2c8-a6d3-413c-8074-c62ed30db8de"
DEVICE_ODID = "5e64f3e9-0a80-d719-d689-3c36eca5eeb6"
APP_VERSION = ".".join(("11", "7", "5", "205"))
ROM_VERSION = "CLS-AL30 " + ".".join(("6", "0", "0", "328"))
DEVICE_INFO = {
    "countryCode": "CN",
    "deviceFormation": "HDSpeaker",
    "deviceType": 0,
    "locale": "zh-CN",
    "phoneType": "CLS-AL30",
    "prdVer": APP_VERSION,
    "sysVer": "EmotionUI_9.0.0",
    "romVersion": ROM_VERSION,
    "time": "20260707115342975",
}

if str(CLOUD_ROOT) not in sys.path:
    sys.path.insert(0, str(CLOUD_ROOT))

app = importlib.import_module("start_websocket_server").app
vendored_loader = importlib.import_module("cloud.search_integration.vendored_loader")
A2UIModelClient = importlib.import_module("custom.a2ui_model_client").A2UIModelClient
ArtifactSaveResult = importlib.import_module("models.service").ArtifactSaveResult
ArtifactStore = importlib.import_module("services.artifact_store").ArtifactStore
get_settings = importlib.import_module("config.config").get_settings
widget_generation_service = importlib.import_module("services.widget_generation_service")
SearchDecision = importlib.import_module(
    "search_integration.adapter"
).SearchDecision


def _tool_payload(content: dict, interaction_id: str) -> dict:
    """构造新协议 WebSocket 请求包络。"""
    return {
        "content": {"odid": DEVICE_ODID, **content},
        "deviceInfo": DEVICE_INFO,
        "pagination": {"limit": 5, "start": ""},
        "session": {
            "interactionId": interaction_id,
            "isNew": False,
            "sessionId": SESSION_ID,
        },
        "userAuth": {"user": {"userId": "test-user-001"}},
        "utterance": {"original": content.get("userQuery", ""), "type": "text"},
        "version": "1.0",
        "bundleName": "com.omega_w_0823.hmservice",
    }


def _request_id(interaction_id: str) -> str:
    return f"{SESSION_ID}&{interaction_id}"


def _receive_final_frame(websocket, expected_request_id: str) -> dict:
    start_received = False
    while True:
        message = websocket.receive_json()
        assert message["errorCode"] == "0"
        assert message["errorMessage"] == ""
        stream_info = message["reply"]["streamInfo"]
        assert stream_info["streamingTextId"] == expected_request_id
        stream_type = stream_info["streamType"]
        if stream_type == "start":
            assert not start_received
            start_received = True
            continue
        if stream_type == "partial":
            assert start_received
            continue
        assert stream_type == "final"
        assert start_received
        return message


def _assert_success_envelope(message: dict, operation: str, request_id: str) -> dict:
    stream_info = message["reply"]["streamInfo"]
    assert stream_info["streamType"] == "final"
    assert message["reply"]["items"] == []
    legacy = parse_legacy_stream_content(stream_info["streamContent"])
    assert legacy["type"] == "result"
    assert legacy["operation"] == operation
    assert legacy["requestId"] == request_id
    assert legacy["error"] == {}
    return legacy


def _compact_dsl(title: str = "Cached Card") -> str:
    """返回可被 compact 转换器合法转换的静态 Compact DSL。"""
    rows = [
        [
            "root",
            "Column",
            {
                "width": 320,
                "height": 160,
                "padding": 8,
                "borderRadius": 16,
                "clip": True,
                "itemMargin": 8,
                "backgroundColor": "comp_background_primary",
            },
            ["title"],
        ],
        [
            "title",
            "Text",
            {"content": title, "design": "title-s", "fontColor": "font_primary"},
        ],
        ["/ui/state", "ready"],
    ]
    return "\n".join(
        json.dumps(row, ensure_ascii=False, separators=(",", ":")) for row in rows
    )


def _compact_payload(
    interaction_id: str,
    user_query: str = "生成静态卡片",
    size: str = "2x4",
) -> dict:
    return _tool_payload(
        {
            "userQuery": user_query,
            "size": size,
            "title": "静态卡片",
            "description": "Search Cache 转换",
            "candidateDataBindings": [],
            "candidateEventCandidates": [],
            "candidateAssetIds": [],
        },
        interaction_id,
    )


def _patch_lookup(monkeypatch, decision: SearchDecision) -> None:
    """把 _search_adapter.lookup 替换为返回固定 decision 的异步桩。"""

    async def fake_lookup(
        request,
        *,
        service=None,
        enabled=True,
        input_data=None,
        data_model_schema=None,
        size=None,
    ):
        if not enabled:
            return SearchDecision(outcome="disabled")
        return decision

    monkeypatch.setattr(
        widget_generation_service._search_adapter,
        "lookup",
        fake_lookup,
    )


def _patch_model(monkeypatch, *, raise_on_call: bool = False) -> list:
    """把 A2UIModelClient.generate 替换为记录调用并返回合法 DSL 的桩。"""
    calls: list = []

    def fake_generate(_self, prompt, protocol_profile):
        calls.append(prompt)
        if raise_on_call:
            raise RuntimeError("model should not have been called")
        return _compact_dsl("Generated")

    monkeypatch.setattr(A2UIModelClient, "generate", fake_generate)
    return calls


def _capture_artifacts(monkeypatch) -> tuple[list, list]:
    saved: list = []
    design_tokens: list = []

    def capture_artifact(store, artifact):
        design_tokens.append(store.design_token)
        saved.append(artifact.model_dump(mode="json", exclude_none=True))
        return ArtifactSaveResult(
            artifactUrl="https://test.invalid/cache.json",
            artifactDigest="sha256:cache",
        )

    monkeypatch.setattr(ArtifactStore, "save", capture_artifact)
    return saved, design_tokens


def _run_compact_route(interaction_id: str, payload: dict) -> dict:
    client = TestClient(app)
    request_id = _request_id(interaction_id)
    with client.websocket_connect(
        "/api/v1/ws/tools/generateWidgetCardCompactDsl"
    ) as websocket:
        websocket.send_json(payload)
        message = _receive_final_frame(websocket, request_id)
    return _assert_success_envelope(
        message, "generateWidgetCardCompactDsl", request_id
    )


def test_compact_route_structure_match_short_circuits_model(monkeypatch):
    """结构命中 → 短路模型调用，直接出卡（模型被调则失败）。"""
    print("MOCK DATA: canned structure_match（rendered_jsonl）")
    monkeypatch.setattr(get_settings(), "enable_search_cache", True)
    monkeypatch.setattr(get_settings(), "enable_a2ui_model_mock", True)
    rendered = _compact_dsl("Cached Card")
    _patch_lookup(
        monkeypatch,
        SearchDecision(
            outcome="structure_match",
            rendered_jsonl=rendered,
            template_id="t-cached",
        ),
    )
    saved, design_tokens = _capture_artifacts(monkeypatch)
    _patch_model(monkeypatch, raise_on_call=True)

    message = _run_compact_route("search-cached", _compact_payload("search-cached"))

    assert message["data"]["status"] == "success"
    assert len(saved) == 1
    # 命中缓存时 design_token 即 rendered_jsonl（未走模型）
    assert design_tokens[0] == rendered
    rows = [json.loads(line) for line in saved[0]["genui"].splitlines()]
    assert "createSurface" in rows[0]
    assert rows[0]["createSurface"]["surfaceId"] == "surface_card"


def test_compact_route_structure_match_fallback_to_model(monkeypatch):
    """缓存 DSL 语义非法 → 单次无 few-shot 模型回退。"""
    print("MOCK DATA: canned structure_match（非法 DSL）→ 回退模型")
    monkeypatch.setattr(get_settings(), "enable_search_cache", True)
    monkeypatch.setattr(get_settings(), "enable_a2ui_model_mock", True)
    # 可解析但绑定路径不在空数据模型中的 Compact DSL → 转换错误 → 触发回退
    _patch_lookup(
        monkeypatch,
        SearchDecision(
            outcome="structure_match",
            rendered_jsonl=(
                '["root","Column",{},["t"]]\n'
                '["t","Text",{"content":{"path":"/name"}}]'
            ),
            template_id="t-bad",
        ),
    )
    _capture_artifacts(monkeypatch)
    model_calls = _patch_model(monkeypatch)

    message = _run_compact_route("search-fallback", _compact_payload("search-fallback"))

    assert message["data"]["status"] == "success"
    assert len(model_calls) == 1
    # 回退 prompt 不携带 referenceExamples
    user_payload = json.loads(model_calls[0][1]["content"])
    assert "referenceExamples" not in user_payload


def test_compact_route_keyword_match_injects_few_shot(monkeypatch):
    """关键词命中 → few-shot 注入 prompt。"""
    print("MOCK DATA: canned keyword_match（reference_jsonl）")
    monkeypatch.setattr(get_settings(), "enable_search_cache", True)
    monkeypatch.setattr(get_settings(), "enable_a2ui_model_mock", True)
    reference = '["root","Column",{},["t"]]\n["t","Text",{"content":"示例"}]'
    _patch_lookup(
        monkeypatch,
        SearchDecision(
            outcome="keyword_match",
            reference_jsonl=reference,
            template_id="t-ref",
        ),
    )
    _capture_artifacts(monkeypatch)
    model_calls = _patch_model(monkeypatch)

    message = _run_compact_route("search-keyword", _compact_payload("search-keyword"))

    assert message["data"]["status"] == "success"
    assert len(model_calls) == 1
    user_payload = json.loads(model_calls[0][1]["content"])
    assert user_payload["referenceExamples"] == reference
    assert "referenceExamples" in user_payload["instruction"]


def test_compact_route_miss_generates_normally(monkeypatch):
    """未命中 → 正常生成，prompt 无 few-shot。"""
    print("MOCK DATA: canned miss")
    monkeypatch.setattr(get_settings(), "enable_search_cache", True)
    monkeypatch.setattr(get_settings(), "enable_a2ui_model_mock", True)
    _patch_lookup(
        monkeypatch,
        SearchDecision(outcome="miss", miss_reason="no_match"),
    )
    _capture_artifacts(monkeypatch)
    model_calls = _patch_model(monkeypatch)

    message = _run_compact_route("search-miss", _compact_payload("search-miss"))

    assert message["data"]["status"] == "success"
    assert len(model_calls) == 1
    user_payload = json.loads(model_calls[0][1]["content"])
    assert "referenceExamples" not in user_payload


def test_compact_route_search_disabled_by_default(monkeypatch):
    """开关默认关闭 → 门禁传 disabled，模型正常生成。"""
    print("MOCK DATA: 默认关闭开关（lookup 不应触发检索）")
    monkeypatch.setattr(get_settings(), "enable_a2ui_model_mock", True)
    seen_enabled = []

    async def fake_lookup(
        request,
        *,
        service=None,
        enabled=True,
        input_data=None,
        data_model_schema=None,
        size=None,
    ):
        seen_enabled.append(enabled)
        if not enabled:
            return SearchDecision(outcome="disabled")
        raise AssertionError("search should be disabled by default")

    monkeypatch.setattr(
        widget_generation_service._search_adapter,
        "lookup",
        fake_lookup,
    )
    _capture_artifacts(monkeypatch)
    _patch_model(monkeypatch)

    message = _run_compact_route("search-off", _compact_payload("search-off"))

    assert message["data"]["status"] == "success"
    assert seen_enabled == [False]


# 全通路测试用最小模板（仅 Text 绑定，规避转换器对 Button 子节点的行为不确定性）
_FULL_PIPELINE_MD = """```cardspec
{
  "title": "上海天气",
  "description": "上海今日天气小卡片",
  "suggestSize": "2x2",
  "dataBindings": []
}
```
```taskspec
{
  "userQuery": "创建上海今日天气小卡片",
  "size": "2x2",
  "eventCandidates": [],
  "dataModelSchema": {
    "data": {
      "weather": {
        "current": {
          "temperatureText": {"type": "string", "description": "温度", "sampleValue": "26℃"}
        }
      }
    }
  },
  "assetCandidates": []
}
```
```generationplan
{
  "candidateDataBindings": [
    {"capabilityId": "ViewWeather", "arguments": {}, "writeResultTo": "/data/weather",
     "candidateOutputFields": ["/current/temperatureText"]}
  ],
  "candidateEventCandidates": [],
  "candidateAssetIds": []
}
```
```designcompactdsl
["root","Column",{"width":160,"height":160},["title"]]
["title","Text",{"content":{"path":"/data/weather/current/temperatureText"}}]
["/data/weather/current/temperatureText","26℃"]
```
"""


def test_compact_route_full_pipeline_structure_match(monkeypatch, tmp_path):
    """真实 adapter + 真实 search 模块 + 临时库：structure_match 全通路短路。

    MOCK DATA: 用内嵌最小模板构建临时 SQLite 库，不依赖真实 subagent_genui 数据。
    """
    print("MOCK DATA: 内嵌最小模板构建临时库，全通路验证")
    from cloud.search_integration.build_db import build_template_record, parse_artifact_md

    fixture = tmp_path / "q01_artifact.md"
    fixture.write_text(_FULL_PIPELINE_MD, encoding="utf-8")
    db_path = tmp_path / "templates.sqlite3"
    dao = vendored_loader.search.SQLiteTemplateDAO(str(db_path))
    dao.initialize()
    dao.upsert(build_template_record(parse_artifact_md(fixture), template_id="q01"))
    monkeypatch.setenv("SEARCH_DB_PATH", str(db_path))
    vendored_loader.search.get_default_search_service.cache_clear()

    monkeypatch.setattr(get_settings(), "enable_search_cache", True)
    monkeypatch.setattr(get_settings(), "enable_a2ui_model_mock", True)
    saved, design_tokens = _capture_artifacts(monkeypatch)
    # 短路时模型不被调用：被调则抛错
    _patch_model(monkeypatch, raise_on_call=True)

    payload = _compact_payload(
        "search-full",
        user_query="生成上海天气卡片",
        size="2x2",
    )
    payload["content"]["candidateDataBindings"] = [
        {
            "capabilityId": "ViewWeather",
            "arguments": {"districtName": "上海"},
            "writeResultTo": "/data/weather",
            "candidateOutputFields": ["/current/temperatureText"],
        }
    ]
    message = _run_compact_route("search-full", payload)

    assert message["data"]["status"] == "success"
    assert len(saved) == 1
    rows = [json.loads(line) for line in saved[0]["genui"].splitlines()]
    assert "createSurface" in rows[0]
    # 缓存命中：design_token 即为模板 rendered_jsonl（模型零调用）
    assert design_tokens[0].startswith('["root","Column"')


def test_compact_route_passes_data_model_schema_and_size(monkeypatch):
    """生成服务把 task_spec.dataModelSchema 与 resolved size 传给 lookup。"""
    print("MOCK DATA: 捕获 lookup 收到的 data_model_schema 与 size")
    monkeypatch.setattr(get_settings(), "enable_search_cache", True)
    monkeypatch.setattr(get_settings(), "enable_a2ui_model_mock", True)
    captured: dict = {}

    async def fake_lookup(
        request,
        *,
        service=None,
        enabled=True,
        input_data=None,
        data_model_schema=None,
        size=None,
    ):
        captured["data_model_schema"] = data_model_schema
        captured["size"] = size
        if not enabled:
            return SearchDecision(outcome="disabled")
        return SearchDecision(outcome="miss", miss_reason="no_hit")

    monkeypatch.setattr(
        widget_generation_service._search_adapter,
        "lookup",
        fake_lookup,
    )
    _capture_artifacts(monkeypatch)
    _patch_model(monkeypatch)

    message = _run_compact_route(
        "search-schema",
        _compact_payload("search-schema", size="2x4"),
    )

    assert message["data"]["status"] == "success"
    # 空候选绑定 → dataModelSchema 为 {"data":{}}；size 透传 2x4
    assert captured["data_model_schema"] == {"data": {}}
    assert captured["size"] == "2x4"


def test_a2ui_form_route_ignores_search(monkeypatch):
    """非 compact 路由（a2ui-form）即使开关打开也不检索。"""
    print("MOCK DATA: a2ui-form 路由（lookup 不应触发）")
    monkeypatch.setattr(get_settings(), "enable_search_cache", True)
    monkeypatch.setattr(get_settings(), "enable_a2ui_model_mock", True)
    seen_enabled = []

    async def fake_lookup(
        request,
        *,
        service=None,
        enabled=True,
        input_data=None,
        data_model_schema=None,
        size=None,
    ):
        seen_enabled.append(enabled)
        if not enabled:
            return SearchDecision(outcome="disabled")
        raise AssertionError("a2ui-form route must not search")

    monkeypatch.setattr(
        widget_generation_service._search_adapter,
        "lookup",
        fake_lookup,
    )
    _capture_artifacts(monkeypatch)
    _patch_model(monkeypatch)

    client = TestClient(app)
    request_id = _request_id("a2ui-search")
    with client.websocket_connect("/api/v1/ws/tools/generateWidgetCard") as websocket:
        websocket.send_json(_compact_payload("a2ui-search"))
        message = _receive_final_frame(websocket, request_id)

    result = _assert_success_envelope(message, "generateWidgetCard", request_id)
    assert result["data"]["status"] == "success"
    assert seen_enabled == [False]
