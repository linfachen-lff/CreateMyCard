# -*- coding: utf-8 -*-
# Copyright (c) Huawei Technologies Co., Ltd. 2026-2026. All rights reserved.
import importlib
import json
import sys
import zipfile
from io import BytesIO
from pathlib import Path

from fastapi.testclient import TestClient

PROJECT_ROOT = Path(__file__).resolve().parents[1]
CLOUD_ROOT = PROJECT_ROOT / "cloud"
if str(CLOUD_ROOT) not in sys.path:
    sys.path.insert(0, str(CLOUD_ROOT))

routes = importlib.import_module("api.routes")
GenerateWidgetCardResponse = importlib.import_module("api.schemas").GenerateWidgetCardResponse
GenerationStatus = importlib.import_module("core.errors").GenerationStatus
get_settings = importlib.import_module("config.config").get_settings
app = importlib.import_module("start_websocket_server").app


class _FakeWidgetService:
    async def generate_widget_card_terse_dsl_nested2(
        self,
        _request,
        before_model_call=None,
    ) -> GenerateWidgetCardResponse:
        if before_model_call is not None:
            await before_model_call()
        return GenerateWidgetCardResponse(
            status=GenerationStatus.SUCCESS,
            artifactUrl="https://example.test/widget.md",
            artifactDigest="sha256:batch-route",
            suggestSize="2x2",
            message="generated",
            renderMessages=[
                {"createSurface": {"surfaceId": "card"}},
                {"updateComponents": {"surfaceId": "card", "components": []}},
            ],
        )


def _payload() -> dict:
    return {
        "content": {
            "odid": "device-1",
            "userQuery": "生成天气卡片",
            "size": "2x2",
            "title": "天气",
            "description": "批量测试",
            "candidateDataBindings": [],
            "candidateEventCandidates": [],
            "candidateAssetIds": [],
        },
        "deviceInfo": {
            "countryCode": "CN",
            "phoneType": "CLS-AL30",
            "prdVer": "11.7.5.205",
            "romVersion": "CLS-AL30 6.0.0.328",
        },
        "session": {"sessionId": "batch-session", "interactionId": "q1"},
        "userAuth": {"user": {"userId": "batch-user"}},
        "utterance": {"original": "生成天气卡片", "type": "text"},
        "version": "1.0",
        "bundleName": "com.example.batch",
    }


def _receive_final(websocket) -> dict:
    while True:
        message = websocket.receive_json()
        stream_info = message["reply"]["streamInfo"]
        if stream_info["streamType"] == "final":
            return message


def test_nested2_batch_route_records_and_exposes_download(monkeypatch, tmp_path):
    settings = get_settings()
    monkeypatch.setattr(settings, "enable_widget_batch_recording", True)
    monkeypatch.setattr(settings, "widget_batch_results_path", str(tmp_path))
    monkeypatch.setattr(settings, "websocket_bearer_token", "batch-token")
    monkeypatch.setattr(settings, "enable_widget_directive_commands", False)
    monkeypatch.setattr(routes, "get_service", lambda _runtime=None: _FakeWidgetService())

    client = TestClient(app)
    headers = {"Authorization": "Bearer batch-token"}
    websocket_url = (
        "/api/v1/ws/tools/generateWidgetCardTerseDslNested2"
        "?batchId=nested2-2x2-test&caseId=2x2-q1&size=2x2"
    )
    with client.websocket_connect(websocket_url, headers=headers) as websocket:
        websocket.send_json(_payload())
        final_frame = _receive_final(websocket)

    manifest_response = client.get(
        "/api/v1/widget-batches/nested2-2x2-test",
        headers=headers,
    )
    assert manifest_response.status_code == 200
    manifest = manifest_response.json()
    assert manifest["summary"] == {"total": 1, "passed": 1, "failed": 0}
    assert manifest["cases"][0]["requestId"] == "batch-session&q1"

    case_dir = tmp_path / "nested2-2x2-test" / "cases" / "2x2-q1"
    response_document = json.loads((case_dir / "response.json").read_text(encoding="utf-8"))
    assert response_document["pluginFinalFrame"] == final_frame
    output_rows = [
        json.loads(line)
        for line in (case_dir / "output.a2ui.jsonl").read_text(encoding="utf-8").splitlines()
    ]
    assert output_rows[0] == {"createSurface": {"surfaceId": "card"}}

    download = client.get(
        "/api/v1/widget-batches/nested2-2x2-test/download",
        headers=headers,
    )
    assert download.status_code == 200
    assert download.headers["content-type"] == "application/zip"
    with zipfile.ZipFile(BytesIO(download.content)) as archive:
        assert "cases/2x2-q1/output.a2ui.jsonl" in archive.namelist()


def test_artifact_download_exposes_only_uuid_named_mock_obs_files(monkeypatch, tmp_path):
    artifact_id = "5b2efdf6-2aa3-485a-9c48-23cc50a2fa56"
    artifact_dir = tmp_path / "mock_obs"
    artifact_dir.mkdir()
    artifact_path = artifact_dir / f"artifact_{artifact_id}.md"
    artifact_path.write_text("```genui\n{}\n```\n", encoding="utf-8")
    monkeypatch.setattr(get_settings(), "WORKSPACE_ROOT", tmp_path)

    response = TestClient(app).get(f"/api/v1/artifacts/{artifact_path.name}")

    assert response.status_code == 200
    assert response.text == artifact_path.read_text(encoding="utf-8")
    assert response.headers["cache-control"] == "public, max-age=31536000, immutable"
    assert TestClient(app).get("/api/v1/artifacts/not-an-artifact.md").status_code == 404


def test_batch_http_routes_reuse_websocket_bearer_token(monkeypatch, tmp_path):
    settings = get_settings()
    monkeypatch.setattr(settings, "enable_widget_batch_recording", True)
    monkeypatch.setattr(settings, "widget_batch_results_path", str(tmp_path))
    monkeypatch.setattr(settings, "websocket_bearer_token", "batch-token")

    client = TestClient(app)
    assert client.get("/api/v1/widget-batches").status_code == 401
    response = client.get(
        "/api/v1/widget-batches",
        headers={"Authorization": "Bearer batch-token"},
    )
    assert response.status_code == 200
    assert response.json()["batches"] == []
