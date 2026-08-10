# -*- coding: utf-8 -*-
# Copyright (c) Huawei Technologies Co., Ltd. 2026-2026. All rights reserved.
import asyncio
import importlib
import json
import sys
from collections import deque
from pathlib import Path
from types import SimpleNamespace
from typing import Any

from fastapi import WebSocketDisconnect
from pydantic import BaseModel

from ws_response_parser import parse_legacy_stream_content

CLOUD_ROOT = Path(__file__).resolve().parents[1] / "cloud" / "shared"
if str(CLOUD_ROOT) not in sys.path:
    sys.path.insert(0, str(CLOUD_ROOT))

runner_module = importlib.import_module("services.websocket_operation_runner")
schemas_module = importlib.import_module("api.schemas")
metrics_module = importlib.import_module("app.websocket_metrics")

WebSocketOperationRunner = runner_module.WebSocketOperationRunner
WebSocketOperationSpec = runner_module.WebSocketOperationSpec
TEMPORARY_COMPACT_DIRECTIVE_OPERATION = runner_module.TEMPORARY_COMPACT_DIRECTIVE_OPERATION
CapabilityOverviewRequest = schemas_module.CapabilityOverviewRequest
GenerateWidgetCardRequest = schemas_module.GenerateWidgetCardRequest
WebSocketMetrics = metrics_module.WebSocketMetrics


class _QueryResult(BaseModel):
    status: str = "success"
    token: str


class _GenerationResult(BaseModel):
    status: str = "success"
    artifactUrl: str
    suggestSize: str = "2x2"
    errorCode: str = ""


class FakeWebSocket:
    def __init__(self, incoming: list[Any]) -> None:
        self._incoming = deque(incoming)
        self.app = SimpleNamespace(state=SimpleNamespace(model_runtime=None))
        self.accept_count = 0
        self.json_frames: list[dict[str, Any]] = []
        self.text_frames: list[str] = []
        self.ordered_frames: list[dict[str, Any]] = []
        self.text_sent = asyncio.Event()

    async def accept(self) -> None:
        self.accept_count += 1

    async def receive_json(self) -> Any:
        if not self._incoming:
            raise AssertionError("FakeWebSocket input exhausted before disconnect")
        incoming = self._incoming.popleft()
        if isinstance(incoming, BaseException):
            raise incoming
        return incoming

    async def send_json(self, payload: dict[str, Any]) -> None:
        self.json_frames.append(payload)
        self.ordered_frames.append(payload)

    async def send_text(self, payload: str) -> None:
        self.text_frames.append(payload)
        self.ordered_frames.append(json.loads(payload))
        self.text_sent.set()


def _query_payload(request_id: str, uid: str) -> dict[str, Any]:
    return {
        "requestId": request_id,
        "arguments": {
            "uid": uid,
            "device": {
                "deviceId": f"device-{uid}",
                "deviceType": "phone",
                "romVersion": "6.0",
            },
            "prdVer": "1.0",
        },
    }


def _generation_payload(request_id: str) -> dict[str, Any]:
    payload = _query_payload(request_id, "generation-user")
    payload["arguments"].update(
        {
            "userQuery": "生成天气卡片",
            "title": "天气",
            "description": "展示今日天气",
            "size": "2x2",
        }
    )
    return payload


def _stream_info(frame: dict[str, Any]) -> dict[str, Any]:
    return frame["reply"]["streamInfo"]


def _assert_metrics_balanced(metrics: WebSocketMetrics, total_connections: int = 1) -> None:
    snapshot = metrics.snapshot()
    assert snapshot.active_connections == 0
    assert snapshot.total_connections == total_connections
    assert snapshot.running_tasks == 0


def _run_query(
    websocket: FakeWebSocket,
    handler: Any,
) -> WebSocketMetrics:
    metrics = WebSocketMetrics()
    service = object()
    runner = WebSocketOperationRunner(
        service_factory=lambda _runtime: service,
        metrics=metrics,
    )
    spec = WebSocketOperationSpec(
        operation="getWidgetCapabilityOverview",
        request_model=CapabilityOverviewRequest,
        handler=handler,
    )
    asyncio.run(runner.serve(websocket, spec))
    return metrics


def test_query_success_balances_connection_and_task_metrics() -> None:
    handled_requests = []

    def handler(_service: object, request: CapabilityOverviewRequest) -> _QueryResult:
        handled_requests.append(request)
        return _QueryResult(token=request.uid)

    websocket = FakeWebSocket(
        [_query_payload("request-1", "user-1"), WebSocketDisconnect(code=1000)]
    )
    metrics = _run_query(websocket, handler)

    assert websocket.accept_count == 1
    assert len(handled_requests) == 1
    assert [_stream_info(frame)["streamType"] for frame in websocket.json_frames] == [
        "start",
        "final",
    ]
    assert all(
        _stream_info(frame)["streamingTextId"] == "request-1"
        for frame in websocket.json_frames
    )
    final_message = parse_legacy_stream_content(
        _stream_info(websocket.json_frames[-1])["streamContent"]
    )
    assert final_message["data"] == {"status": "success", "token": "user-1"}
    _assert_metrics_balanced(metrics)


def test_invalid_json_does_not_close_connection_before_next_request() -> None:
    handled_request_ids = []

    def handler(_service: object, request: CapabilityOverviewRequest) -> _QueryResult:
        handled_request_ids.append(request.uid)
        return _QueryResult(token=request.uid)

    websocket = FakeWebSocket(
        [
            ValueError("invalid JSON"),
            _query_payload("request-after-error", "user-after-error"),
            WebSocketDisconnect(code=1000),
        ]
    )
    metrics = _run_query(websocket, handler)

    assert handled_request_ids == ["user-after-error"]
    assert [_stream_info(frame)["streamType"] for frame in websocket.json_frames] == [
        "final",
        "start",
        "final",
    ]
    invalid_message = parse_legacy_stream_content(
        _stream_info(websocket.json_frames[0])["streamContent"]
    )
    assert invalid_message["type"] == "error"
    assert invalid_message["errorCode"] == "INVALID_ARGUMENTS"
    continued_frames = websocket.json_frames[1:]
    assert all(
        _stream_info(frame)["streamingTextId"] == "request-after-error"
        for frame in continued_frames
    )
    _assert_metrics_balanced(metrics)


def test_two_requests_on_one_connection_keep_ids_and_results_isolated() -> None:
    handled_uids = []

    def handler(_service: object, request: CapabilityOverviewRequest) -> _QueryResult:
        handled_uids.append(request.uid)
        return _QueryResult(status=f"status-{request.uid}", token=request.uid)

    websocket = FakeWebSocket(
        [
            _query_payload("request-a", "user-a"),
            _query_payload("request-b", "user-b"),
            WebSocketDisconnect(code=1000),
        ]
    )
    metrics = _run_query(websocket, handler)

    assert handled_uids == ["user-a", "user-b"]
    frame_states = [
        (_stream_info(frame)["streamingTextId"], _stream_info(frame)["streamType"])
        for frame in websocket.json_frames
    ]
    assert frame_states == [
        ("request-a", "start"),
        ("request-a", "final"),
        ("request-b", "start"),
        ("request-b", "final"),
    ]
    first_result = parse_legacy_stream_content(
        _stream_info(websocket.json_frames[1])["streamContent"]
    )
    second_result = parse_legacy_stream_content(
        _stream_info(websocket.json_frames[3])["streamContent"]
    )
    assert first_result["requestId"] == "request-a"
    assert first_result["status"] == "status-user-a"
    assert first_result["data"]["token"] == "user-a"
    assert second_result["requestId"] == "request-b"
    assert second_result["status"] == "status-user-b"
    assert second_result["data"]["token"] == "user-b"
    _assert_metrics_balanced(metrics)


def test_generation_pairs_start_and_success_directives() -> None:
    async def handler(
        _service: object,
        _request: GenerateWidgetCardRequest,
        before_model_call: Any,
    ) -> _GenerationResult:
        await before_model_call("2x2")
        return _GenerationResult(artifactUrl="https://example.test/card.json")

    websocket = FakeWebSocket(
        [_generation_payload("generation-1"), WebSocketDisconnect(code=1000)]
    )
    metrics = WebSocketMetrics()
    runner = WebSocketOperationRunner(
        service_factory=lambda _runtime: object(),
        metrics=metrics,
    )
    spec = WebSocketOperationSpec(
        operation=TEMPORARY_COMPACT_DIRECTIVE_OPERATION,
        request_model=GenerateWidgetCardRequest,
        handler=handler,
        handler_in_threadpool=False,
    )

    asyncio.run(runner.serve(websocket, spec))

    frame_types = [_stream_info(frame)["streamType"] for frame in websocket.json_frames]
    assert frame_types == ["start", "command", "command", "final"]
    command_params = []
    for frame in websocket.json_frames[1:3]:
        command_message = json.loads(_stream_info(frame)["streamContent"])
        directive = json.loads(command_message["content"])
        command_params.append(directive["directives"][0]["payload"]["executeParam"])
    start_param, end_param = command_params
    assert start_param["intentName"] == "AIWidgetStart"
    assert end_param["intentName"] == "AIWidgetEnd"
    assert start_param["cardId"] == end_param["cardId"]
    assert end_param["status"] is True
    assert end_param["intentParam"] == {
        "genWidgetResult": "https://example.test/card.json"
    }
    _assert_metrics_balanced(metrics)


def test_heartbeat_finishes_before_final_and_does_not_leak() -> None:
    async def handler(
        _service: object,
        _request: GenerateWidgetCardRequest,
        _before_model_call: Any,
    ) -> _GenerationResult:
        await asyncio.wait_for(websocket.text_sent.wait(), timeout=0.1)
        return _GenerationResult(artifactUrl="https://example.test/card.json")

    websocket = FakeWebSocket(
        [_generation_payload("heartbeat-1"), WebSocketDisconnect(code=1000)]
    )
    metrics = WebSocketMetrics()
    runner = WebSocketOperationRunner(
        service_factory=lambda _runtime: object(),
        metrics=metrics,
    )
    spec = WebSocketOperationSpec(
        operation="generateWidgetCard",
        request_model=GenerateWidgetCardRequest,
        handler=handler,
        heartbeat=True,
        heartbeat_interval=0.001,
        handler_in_threadpool=False,
    )

    async def run_and_check_no_tail_frame() -> None:
        await runner.serve(websocket, spec)
        frame_count = len(websocket.ordered_frames)
        await asyncio.sleep(0.005)
        assert len(websocket.ordered_frames) == frame_count

    asyncio.run(run_and_check_no_tail_frame())

    frame_types = [
        _stream_info(frame)["streamType"] for frame in websocket.ordered_frames
    ]
    assert frame_types[0] == "start"
    assert "partial" in frame_types
    assert frame_types[-1] == "final"
    _assert_metrics_balanced(metrics)
