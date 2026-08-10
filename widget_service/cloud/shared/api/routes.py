# -*- coding: utf-8 -*-
# Copyright (c) Huawei Technologies Co., Ltd. 2026-2026. All rights reserved.
"""WebSocket 路径与卡片业务 operation 的声明式绑定。"""

from fastapi import APIRouter, WebSocket

from api.schemas import (
    CapabilityOverviewRequest,
    DataCapabilitySchemasRequest,
    GenerateWidgetCardRequest,
)
from services.websocket_operation_runner import (
    TEMPORARY_COMPACT_DIRECTIVE_OPERATION,
    WebSocketOperationRunner,
    WebSocketOperationSpec,
)

router = APIRouter(prefix="/api/v1")
_websocket_runner = WebSocketOperationRunner()

_CAPABILITY_OVERVIEW = WebSocketOperationSpec(
    operation="getWidgetCapabilityOverview",
    request_model=CapabilityOverviewRequest,
    handler=lambda service, request: service.get_widget_capability_overview(request),
)
_DATA_CAPABILITY_SCHEMAS = WebSocketOperationSpec(
    operation="getDataCapabilitySchemas",
    request_model=DataCapabilitySchemasRequest,
    handler=lambda service, request: service.get_data_capability_schemas(request),
)
_GENERATE_A2UI_FORM = WebSocketOperationSpec(
    operation="generateWidgetCard",
    request_model=GenerateWidgetCardRequest,
    handler=lambda service, request, before_model_call: (
        service.generate_widget_card_a2ui_form(
            request,
            before_model_call=before_model_call,
        )
    ),
    heartbeat=True,
    handler_in_threadpool=False,
)
_GENERATE_COMPACT_DSL = WebSocketOperationSpec(
    operation="generateWidgetCardCompactDsl",
    request_model=GenerateWidgetCardRequest,
    handler=lambda service, request, before_model_call: (
        service.generate_widget_card_compact_dsl(
            request,
            before_model_call=before_model_call,
        )
    ),
    heartbeat=True,
    handler_in_threadpool=False,
)
_GENERATE_COMPACT_DSL_WITH_DIRECTIVE = WebSocketOperationSpec(
    operation=TEMPORARY_COMPACT_DIRECTIVE_OPERATION,
    request_model=GenerateWidgetCardRequest,
    handler=lambda service, request, before_model_call: (
        service.generate_widget_card_compact_dsl(
            request,
            before_model_call=before_model_call,
        )
    ),
    heartbeat=True,
    handler_in_threadpool=False,
)
_GENERATE_TERSE_DSL = WebSocketOperationSpec(
    operation="generateWidgetCardTerseDslNested2",
    request_model=GenerateWidgetCardRequest,
    handler=lambda service, request, before_model_call: (
        service.generate_widget_card_terse_dsl_nested2(
            request,
            before_model_call=before_model_call,
        )
    ),
    heartbeat=True,
    handler_in_threadpool=False,
)


@router.websocket("/ws/tools/getWidgetCapabilityOverview")
async def get_widget_capability_overview_ws(websocket: WebSocket) -> None:
    """能力概述 WebSocket 入口。"""
    await _websocket_runner.serve(websocket, _CAPABILITY_OVERVIEW)


@router.websocket("/ws/tools/getDataCapabilitySchemas")
async def get_data_capability_schemas_ws(websocket: WebSocket) -> None:
    """数据能力 schema WebSocket 入口。"""
    await _websocket_runner.serve(websocket, _DATA_CAPABILITY_SCHEMAS)


@router.websocket("/ws/tools/generateWidgetCard")
async def generate_widget_card_ws(websocket: WebSocket) -> None:
    """标准 A2UI 卡片生成 WebSocket 入口。"""
    await _websocket_runner.serve(websocket, _GENERATE_A2UI_FORM)


@router.websocket("/ws/tools/generateWidgetCardCompactDsl")
async def generate_widget_card_compact_dsl_ws(websocket: WebSocket) -> None:
    """Compact DSL 卡片生成 WebSocket 入口。"""
    await _websocket_runner.serve(websocket, _GENERATE_COMPACT_DSL)


@router.websocket(f"/ws/tools/{TEMPORARY_COMPACT_DIRECTIVE_OPERATION}")
async def generate_widget_card_compact_dsl_with_directive_ws(
    websocket: WebSocket,
) -> None:
    """临时复用 Compact DSL 业务，并始终发送端侧指令帧。"""
    await _websocket_runner.serve(
        websocket,
        _GENERATE_COMPACT_DSL_WITH_DIRECTIVE,
    )


@router.websocket("/ws/tools/generateWidgetCardTerseDslNested2")
async def generate_widget_card_terse_dsl_nested2_ws(websocket: WebSocket) -> None:
    """TerseDSL-Nested-2 卡片生成 WebSocket 入口。"""
    await _websocket_runner.serve(websocket, _GENERATE_TERSE_DSL)
