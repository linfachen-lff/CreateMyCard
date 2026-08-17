# -*- coding: utf-8 -*-
# Copyright (c) Huawei Technologies Co., Ltd. 2026-2026. All rights reserved.
import asyncio
import json
import secrets
import time
import traceback
import uuid
from contextlib import suppress
from typing import Any

from fastapi import APIRouter, HTTPException, Request, Response, WebSocket, WebSocketDisconnect
from fastapi.responses import FileResponse
from pydantic import BaseModel, ValidationError
from starlette.concurrency import run_in_threadpool

from api.schemas import (
    CapabilityOverviewRequest,
    DataCapabilitySchemasRequest,
    GenerateWidgetCardRequest,
    ToolRequestEnvelope,
    VersionedToolRequest,
)
from app.logger import json_for_log, logger, task_logger
from app.websocket_metrics import websocket_metrics
from config.config import get_settings
from core.errors import ErrorCode
from custom.model_runtime import ModelExecutionRuntime
from models.generation import DEFAULT_WIDGET_SIZE, ModelRequestContext, WidgetSize
from models.service import (
    WidgetPluginReply,
    WidgetPluginStreamResponse,
    WidgetStreamInfo,
    WidgetWebSocketErrorMessage,
    WidgetWebSocketResultMessage,
)
from services.capability_registry import CapabilityRegistry
from services.widget_batch_store import (
    WidgetBatchCaseRecord,
    WidgetBatchContext,
    WidgetBatchNotFoundError,
    WidgetBatchRecordingDisabledError,
    WidgetBatchStore,
    utc_now,
)
from services.widget_directive import (
    WidgetDirectiveState,
    build_widget_directive_response,
)
from services.widget_generation_service import WidgetGenerationService

_MODULE = "[WS Router]"

router = APIRouter(prefix="/api/v1")

TEMPORARY_COMPACT_DIRECTIVE_OPERATION = "generateWidgetCardCompactDslWithDirective"
GENERATION_OPERATIONS = frozenset(
    {
        "generateWidgetCard",
        "generateWidgetCardCompactDsl",
        "generateWidgetCardTerseDslNested2",
        TEMPORARY_COMPACT_DIRECTIVE_OPERATION,
    }
)
# 临时接口只在路由层强制开启指令帧；删除临时入口时一并删除该集合即可。
FORCED_WIDGET_DIRECTIVE_OPERATIONS = frozenset(
    {TEMPORARY_COMPACT_DIRECTIVE_OPERATION}
)

ERROR_EXPLANATIONS = {
    ErrorCode.INVALID_ARGUMENTS.value: (
        "工具参数传入有误，请检查必填字段、字段类型和字段取值后重新调用。报错信息如下"
    ),
    ErrorCode.UNKNOWN_CAPABILITY.value: (
        "工具参数中包含未注册的能力 ID，请重新获取能力概述，并仅使用返回的能力 ID。报错信息如下"
    ),
    ErrorCode.WRITE_RESULT_CONFLICT.value: (
        "多个数据能力的写入路径存在冲突，请调整 writeResultTo，"
        "避免路径相同、嵌套或相互覆盖。报错信息如下"
    ),
    ErrorCode.NO_EFFECTIVE_CAPABILITY.value: (
        "本次请求没有可用于生成卡片的有效能力，请检查候选能力、参数和设备可用性后重新规划。报错信息如下"
    ),
    ErrorCode.PROTOCOL_CAPABILITY_UNSUPPORTED.value: (
        "当前指定的 DSL 协议不支持本次请求中的动态能力或编辑模式，"
        "请改为静态新建请求，"
        "或选择支持对应能力的生成接口。报错信息如下"
    ),
    ErrorCode.APP_VERSION_UNSUPPORTED.value: (
        "当前设备的 App 或 ROM 版本不在服务支持范围内，请停止继续生成，并向用户说明版本暂不支持。"
        "报错信息如下"
    ),
    ErrorCode.PACKAGE_NOT_INSTALLED.value: (
        "当前设备未安装能力依赖的应用，请移除对应候选能力，或提示用户安装依赖应用后重试。报错信息如下"
    ),
    ErrorCode.A2UI_GENERATION_FAILED.value: (
        "卡片生成模型调用失败，或模型没有返回有效 DSL；"
        "本次没有可继续处理的卡片结果，建议稍后重新调用。"
        "报错信息如下"
    ),
    ErrorCode.VALIDATION_FAILED.value: (
        "模型生成的卡片 DSL 存在 error 级校验问题，且当前结果未通过修复校验，"
        "请结合错误位置重新生成。"
        "报错信息如下"
    ),
    ErrorCode.ARTIFACT_UPLOAD_FAILED.value: (
        "卡片内容已经生成，但产物保存或上传失败，当前没有可用的 artifactUrl，"
        "建议稍后重新调用。报错信息如下"
    ),
    ErrorCode.WIDGET_EDIT_DISABLED.value: (
        "当前服务没有开启卡片编辑功能，无法处理 sourceArtifactUrl；"
        "请改为新建卡片，或开启编辑功能后重试。"
        "报错信息如下"
    ),
    ErrorCode.SOURCE_ARTIFACT_NOT_FOUND.value: (
        "没有找到待编辑的来源卡片产物，请检查 sourceArtifactUrl 是否正确，"
        "或重新创建卡片。报错信息如下"
    ),
    ErrorCode.SOURCE_ARTIFACT_DOWNLOAD_FAILED.value: (
        "待编辑的来源卡片产物下载失败，请检查 sourceArtifactUrl 的可访问性后重试。报错信息如下"
    ),
    ErrorCode.SOURCE_ARTIFACT_SCHEMA_UNSUPPORTED.value: (
        "待编辑的来源卡片产物版本或结构不受当前服务支持，请重新创建卡片，不要继续沿用该产物。报错信息如下"
    ),
    ErrorCode.SOURCE_ARTIFACT_INVALID.value: (
        "待编辑的来源卡片产物内容无效或不完整，请检查来源产物，或重新创建卡片。报错信息如下"
    ),
    ErrorCode.TIMEOUT.value: (
        "工具执行超时，本次调用未在限定时间内完成，建议稍后重试；不要把本次结果当作成功结果。报错信息如下"
    ),
}
DEFAULT_ERROR_EXPLANATION = (
    "工具执行过程中发生未分类的服务异常，本次调用未成功完成，建议稍后重试。报错信息如下"
)


def get_service(
    model_runtime: ModelExecutionRuntime | None = None,
) -> WidgetGenerationService:
    """创建卡片生成服务对象。

    入参：无。
    出参：WidgetGenerationService 实例。
    """
    return WidgetGenerationService(model_runtime=model_runtime)


def _card_template_authorized(websocket: WebSocket) -> bool:
    """校验 CardTemplate UX 兼容入口的静态 Bearer Token。"""
    expected = get_settings().websocket_bearer_token
    authorization = websocket.headers.get("authorization", "")
    prefix = "Bearer "
    if not expected or not authorization.startswith(prefix):
        return False
    return secrets.compare_digest(authorization[len(prefix) :], expected)


def _batch_http_authorized(request: Request) -> bool:
    """批测 HTTP 查询与工具 WebSocket 复用同一个静态 Bearer Token。"""
    expected = get_settings().websocket_bearer_token
    if not expected:
        return True
    authorization = request.headers.get("authorization", "")
    prefix = "Bearer "
    if not authorization.startswith(prefix):
        return False
    return secrets.compare_digest(authorization.removeprefix(prefix), expected)


def _require_batch_http_access(request: Request, store: WidgetBatchStore) -> None:
    """拒绝未授权或未开启的批测查询，不暴露运行时目录状态。"""
    if not store.enabled:
        raise HTTPException(status_code=404, detail="widget batch recording is disabled")
    if not _batch_http_authorized(request):
        raise HTTPException(
            status_code=401,
            detail="invalid bearer token",
            headers={"WWW-Authenticate": "Bearer"},
        )


def _widget_batch_http_error(exc: Exception) -> HTTPException:
    """把批测存储错误映射为稳定 HTTP 状态码。"""
    if isinstance(exc, WidgetBatchNotFoundError):
        return HTTPException(status_code=404, detail=str(exc))
    if isinstance(exc, ValueError):
        return HTTPException(status_code=400, detail=str(exc))
    logger.error(
        f"{_MODULE} widget_batch_http_failed exception_type={type(exc).__name__}",
        exc_info=True,
    )
    return HTTPException(status_code=500, detail="widget batch storage failed")


def _card_template_surface_metadata(messages: list[dict[str, Any]]) -> tuple[str, int]:
    """从标准 A2UI 消息中提取 surfaceId 和最终 revision。"""
    surface_id = ""
    revision = 0
    for message in messages:
        create_surface = message.get("createSurface")
        if isinstance(create_surface, dict):
            surface_id = str(create_surface.get("surfaceId") or surface_id)
        for key in ("updateComponents", "updateDataModel"):
            update = message.get(key)
            if isinstance(update, dict):
                surface_id = str(update.get("surfaceId") or surface_id)
                raw_revision = update.get("surfaceRevision")
                if isinstance(raw_revision, int):
                    revision = max(revision, raw_revision)
    return surface_id, revision


async def card_template_compat_ws(websocket: WebSocket) -> None:
    """兼容端侧现有 card.generate 协议，并路由到 Python CardPlan 正式链路。"""
    if not _card_template_authorized(websocket):
        await websocket.close(code=1008, reason="invalid bearer token")
        return
    await websocket.accept()
    try:
        while True:
            payload = await websocket.receive_json()
            request_id = str(payload.get("requestId") or "") if isinstance(payload, dict) else ""
            started_at = time.perf_counter()
            try:
                if not isinstance(payload, dict) or payload.get("type") != "card.generate":
                    raise ValueError("only card.generate is supported")
                if payload.get("pipeline", "card-plan-template") != "card-plan-template":
                    raise ValueError("only card-plan-template pipeline is supported")
                context = payload.get("context")
                if not isinstance(context, dict):
                    raise ValueError("context must be an object")
                options = payload.get("options", {})
                if not isinstance(options, dict):
                    raise ValueError("options must be an object")
                request = GenerateWidgetCardRequest(
                    uid="card-template-ux",
                    prdVer=get_settings().default_prd_version,
                    device={"romVersion": get_settings().default_device_rom_version},
                    userQuery=context.get("userQuery"),
                    size=context.get("size", "2x2"),
                    title=context.get("title"),
                    description=context.get("description"),
                    candidateDataBindings=context.get("candidateDataBindings", []),
                    candidateEventCandidates=context.get("candidateEventCandidates", []),
                    candidateAssetIds=context.get("candidateAssetIds", []),
                    options=options,
                )
                model_runtime = getattr(websocket.app.state, "model_runtime", None)
                result = await get_service(model_runtime).generate_widget_card_terse_dsl_nested2(
                    request
                )
                messages = result.renderMessages
                surface_id, surface_revision = _card_template_surface_metadata(messages)
                if messages:
                    await websocket.send_json(
                        {
                            "serviceProtocolVersion": "widget-service-card-template/1.0",
                            "type": "card.generate.delta",
                            "requestId": request_id,
                            "ok": True,
                            "phase": "body",
                            "messages": messages,
                            "diagnostics": [],
                        }
                    )
                completed = result.status.value in {"success", "degraded"}
                diagnostics = [] if completed else [
                    {
                        "severity": "error",
                        "code": result.errorCode or "GENERATION_FAILED",
                        "message": result.message,
                    }
                ]
                await websocket.send_json(
                    {
                        "serviceProtocolVersion": "widget-service-card-template/1.0",
                        "type": "card.generate.result",
                        "requestId": request_id,
                        "ok": completed,
                        "status": "completed" if completed else "rejected",
                        "pipeline": "card-plan-template",
                        "surfaceId": surface_id,
                        "surfaceRevision": surface_revision,
                        "messages": messages,
                        "diagnostics": diagnostics,
                        "metrics": {
                            "totalLatencyMs": round((time.perf_counter() - started_at) * 1000, 2),
                            "totalInputTokens": -1,
                            "totalOutputTokens": -1,
                            "firstBodySubtreeMs": -1,
                            "templateCallCount": result.templateCallCount,
                            "expandedComponentCount": result.expandedComponentCount,
                            "chromeFallbackUsed": False,
                            "bodyFallbackUsed": result.generationFallbackUsed or not completed,
                        },
                    }
                )
            except (ValueError, ValidationError) as exc:
                await websocket.send_json(
                    {
                        "serviceProtocolVersion": "widget-service-card-template/1.0",
                        "type": "error",
                        "requestId": request_id,
                        "ok": False,
                        "error": {"code": "INVALID_ARGUMENTS", "message": str(exc)},
                    }
                )
    except WebSocketDisconnect:
        return


def _request_id_from_envelope(envelope: ToolRequestEnvelope) -> str | None:
    """从外部请求包络中生成 requestId。

    入参：
    - envelope：已经解析后的 WebSocket 外部请求包络。
    出参：`sessionId&interactionId` 格式的 requestId；会话字段缺失时返回 None。
    """
    session_id = envelope.session.sessionId
    interaction_id = envelope.session.interactionId
    if session_id and interaction_id:
        return f"{session_id}&{interaction_id}"
    if session_id:
        return session_id
    return None


def _request_id_from_raw_payload(payload: Any) -> str | None:
    """在完整协议校验前，从原始请求中提取稳定的 requestId。"""
    if not isinstance(payload, dict):
        return None
    session = payload.get("session")
    if isinstance(session, dict):
        session_id = str(session.get("sessionId") or "").strip()
        interaction_id = str(session.get("interactionId") or "").strip()
        if session_id and interaction_id:
            return f"{session_id}&{interaction_id}"
        if session_id:
            return session_id
    request_id = payload.get("requestId")
    if request_id is None:
        return None
    return str(request_id).strip() or None


def _normalize_directive_size(
    value: Any,
    fallback: WidgetSize = DEFAULT_WIDGET_SIZE,
) -> WidgetSize:
    """将指令尺寸限制为服务支持的标准值。"""
    if value == "2x4":
        return "2x4"
    if value == "2x2":
        return "2x2"
    return fallback


def _directive_size_from_raw_payload(payload: Any) -> WidgetSize:
    """在请求模型构造前读取显式尺寸，缺失或非法时使用首次生成默认值。"""
    if not isinstance(payload, dict):
        return DEFAULT_WIDGET_SIZE
    content = payload.get("content")
    if not isinstance(content, dict):
        return DEFAULT_WIDGET_SIZE
    return _normalize_directive_size(content.get("size"))


def _pick_device_rom_version(device_info: dict[str, Any]) -> str:
    """从 deviceInfo 中读取 ROM 版本。

    入参：
    - device_info：外部请求中的 deviceInfo 字典。
    出参：内部 DeviceContext 使用的 romVersion。
    """
    settings = get_settings()
    value = device_info.get("romVersion")
    if value is not None and str(value).strip():
        return CapabilityRegistry.normalize_rom_version(str(value))
    return CapabilityRegistry.normalize_rom_version(settings.default_device_rom_version)


def _device_context_from_envelope(
    envelope: ToolRequestEnvelope,
    odid: Any = None,
) -> dict[str, Any]:
    """把外部 deviceInfo 和 content.odid 转换成内部 DeviceContext 字典。

    入参：
    - envelope：已经解析后的 WebSocket 外部请求包络。
    - odid：content 中可选的设备 odid。
    出参：可直接传给 DeviceContext 的字典。
    """
    device_info = envelope.deviceInfo.model_dump(mode="json", exclude_none=True)
    phone_type = device_info.get("phoneType")
    raw_rom_version = device_info.get("romVersion")
    if raw_rom_version is None or not str(raw_rom_version).strip():
        raw_rom_version = get_settings().default_device_rom_version
    return {
        "deviceId": device_info.get("deviceId"),
        "deviceType": phone_type or str(device_info.get("deviceType", "")),
        "sysVersion": device_info.get("sysVer"),
        "deviceName": device_info.get("deviceFormation"),
        "odid": odid,
        "udid": device_info.get("udid"),
        "romVersion": _pick_device_rom_version(device_info),
        "_sourceRomVersion": str(raw_rom_version),
        "marketingName": device_info.get("marketingName") or phone_type,
    }


def _arguments_from_envelope(envelope: ToolRequestEnvelope, operation: str) -> dict[str, Any]:
    """从外部请求包络中组装内部业务入参。

    入参：
    - envelope：已经解析后的 WebSocket 外部请求包络。
    - operation：当前 WebSocket path 对应的业务能力名。
    出参：可直接传给具体请求模型的业务入参字典。
    """
    arguments = dict(envelope.content)
    odid = arguments.pop("odid", None)
    if operation in GENERATION_OPERATIONS and not arguments.get("userQuery"):
        arguments["userQuery"] = envelope.utterance.original if envelope.utterance else ""
    arguments["uid"] = envelope.userAuth.user.userId or ""
    arguments["locale"] = envelope.deviceInfo.locale or "zh-CN"
    arguments["prdVer"] = envelope.deviceInfo.prdVer
    arguments["device"] = _device_context_from_envelope(envelope, odid)
    return arguments


def _normalize_payload(
    payload: dict[str, Any],
    operation: str,
) -> tuple[str | None, dict[str, Any]]:
    """归一化 WebSocket 原始报文。

    入参：
    - payload：客户端发送的 JSON 对象。
    - operation：当前 WebSocket path 对应的业务能力名。
    出参：requestId 与内部业务入参；优先支持 content/deviceInfo/session 新协议。
    """
    if "content" in payload or "deviceInfo" in payload or "session" in payload:
        envelope = ToolRequestEnvelope(**payload)
        return _request_id_from_envelope(envelope), _arguments_from_envelope(
            envelope, operation
        )
    return payload.get("requestId"), payload.get("arguments", payload)


def _mapping(value: Any) -> dict[str, Any]:
    """把请求中的可选对象安全归一化为字典。"""
    return value if isinstance(value, dict) else {}


def _first_text(*values: Any, default: str = "") -> str:
    """按顺序选择第一个非空值并转换为字符串。"""
    for value in values:
        if value is not None and str(value).strip():
            return str(value)
    return default


def _model_request_context_from_payload(
    payload: dict[str, Any],
    request: VersionedToolRequest,
) -> ModelRequestContext:
    """从原始工具请求构造模型服务使用的稳定动态上下文。"""
    settings = get_settings()
    session = _mapping(payload.get("session"))
    device_info = _mapping(payload.get("deviceInfo"))
    content = _mapping(payload.get("content"))
    arguments = _mapping(payload.get("arguments"))
    session_id = _first_text(session.get("sessionId"), default=uuid.uuid4().hex)
    interaction_id = _first_text(
        session.get("interactionId"),
        default=uuid.uuid4().hex,
    )
    device_id = _first_text(
        session.get("deviceId"),
        device_info.get("deviceId"),
        request.device.deviceId,
        default=f"aiwidget-{uuid.uuid4().hex}",
    )
    app_version = _first_text(
        session.get("clientVersion"),
        session.get("prdVer"),
        device_info.get("prdVer"),
        request.prdVer,
        default=settings.default_prd_version,
    )
    app_name = _first_text(
        session.get("packageName"),
        payload.get("bundleName"),
        content.get("bundleName"),
        arguments.get("bundleName"),
        default=settings.deepseek_platform_default_app_name,
    )
    country_code = _first_text(
        device_info.get("countryCode"),
        default=settings.deepseek_platform_default_country_code,
    )
    return ModelRequestContext(
        session_id=session_id,
        interaction_id=interaction_id,
        device_id=device_id,
        country_code=country_code,
        app_version=app_version,
        app_name=app_name,
    )


def _error_details(exc: ValidationError | ValueError) -> list[dict[str, Any]] | str:
    """将参数异常转换成可序列化详情。

    入参：
    - exc：Pydantic 校验异常或业务参数异常。
    出参：可写入 WebSocket 错误消息的详情对象。
    """
    if isinstance(exc, ValidationError):
        # Pydantic 的 ctx 可能携带原生 ValueError，input 可能包含完整请求或注册表；
        # 二者既不适合对外返回，也可能导致错误响应再次序列化失败。
        return exc.errors(include_context=False, include_input=False)
    return str(exc)


def _build_plugin_stream_response(
    legacy_message: WidgetWebSocketResultMessage | WidgetWebSocketErrorMessage,
    streaming_text_id: str | None = None,
) -> WidgetPluginStreamResponse:
    """把旧版完整消息转换成华为流处理插件输出包络。

    入参：
    - legacy_message：旧版 WebSocket 完整出参。
    出参：插件顶层始终成功；业务异常说明和完整旧消息放入 streamContent。
    """
    resolved_streaming_text_id = streaming_text_id or legacy_message.requestId or uuid.uuid4().hex
    stream_content = str(legacy_message)
    error_explanation = _error_explanation(legacy_message.errorCode)
    if error_explanation:
        stream_content = f"{error_explanation}：{stream_content}"
    return WidgetPluginStreamResponse(
        errorCode="0",
        errorMessage="",
        reply=WidgetPluginReply(
            streamInfo=WidgetStreamInfo(
                # 插件只消费字符串字段；保留旧消息的完整字符串表现，避免拆散旧协议字段。
                streamContent=stream_content,
                streamingTextId=resolved_streaming_text_id,
            ),
            items=[],
        ),
    )


def _error_explanation(error_code: str) -> str:
    """把内部错误码转换成主 Agent 可理解、可采取下一步动作的异常说明。"""
    if not error_code:
        return ""
    return ERROR_EXPLANATIONS.get(error_code, DEFAULT_ERROR_EXPLANATION)


async def _send_websocket_json(
    websocket: WebSocket,
    payload: dict[str, Any],
    operation: str,
    request_id: str | None,
    frame_type: str,
) -> bool:
    """发送 WebSocket JSON 帧，并处理客户端已断开的情况。"""
    try:
        await websocket.send_json(payload)
        return True
    except (WebSocketDisconnect, RuntimeError) as exc:
        logger.error(
            f"{_MODULE} widget_operation_ws_send_failed request_id={request_id} "
            f"operation={operation} frame_type={frame_type} "
            f"exception_type={type(exc).__name__} exception={exc!r} "
            f"traceback={traceback.format_exc()}"
        )
        return False


async def _send_widget_directive_command(
    websocket: WebSocket,
    raw_payload: dict[str, Any],
    operation: str,
    request_id: str | None,
    streaming_text_id: str,
    state: WidgetDirectiveState,
    card_id: str,
    size: WidgetSize,
    artifact_url: str = "",
) -> bool:
    """按开关发送生成进度指令，不改变原有业务帧和异常处理。"""
    if not _widget_directive_commands_enabled(operation):
        return True
    response = build_widget_directive_response(
        raw_payload,
        state,
        streaming_text_id,
        card_id,
        request_id or "",
        size,
        artifact_url,
    )
    return await _send_websocket_json(
        websocket,
        response.model_dump(mode="json", exclude_none=True),
        operation,
        request_id,
        f"command_{state.value}",
    )


def _widget_directive_commands_enabled(operation: str) -> bool:
    """判断当前生成接口是否需要下发端侧卡片指令。"""
    settings_enabled = get_settings().enable_widget_directive_commands
    operation_forced = operation in FORCED_WIDGET_DIRECTIVE_OPERATIONS
    return settings_enabled or operation_forced


def _generation_result_directive(
    result_data: dict[str, Any],
) -> tuple[WidgetDirectiveState, str]:
    """根据生成结果是否具有有效 artifact 地址选择结束指令。"""
    status = result_data.get("status")
    artifact_url = result_data.get("artifactUrl")
    valid_artifact_url = isinstance(artifact_url, str) and bool(artifact_url.strip())
    if status in {"success", "degraded"} and valid_artifact_url:
        return WidgetDirectiveState.SUCCESS, artifact_url
    return WidgetDirectiveState.FAILURE, ""


async def _heartbeat_sender(
    websocket: WebSocket,
    streaming_text_id: str,
    interval: float = 6.0,
) -> None:
    """周期性向客户端发送 partial 心跳帧。

    入参：
    - websocket：客户端 WebSocket 连接。
    - streaming_text_id：一次请求内稳定的流式文本 ID。
    - interval：心跳发送间隔秒数，默认 6 秒。
    出参：无；协程会持续运行直到被取消或连接关闭。
    """
    partial_frame = WidgetPluginStreamResponse(
        errorCode="0",
        errorMessage="",
        reply=WidgetPluginReply(
            streamInfo=WidgetStreamInfo(
                streamContent="",
                streamingTextId=streaming_text_id,
                streamType="partial",
                textType="markdown",
            ),
            items=[],
        ),
    )
    partial_json = json.dumps(
        partial_frame.model_dump(mode="json", exclude_none=True),
        ensure_ascii=False,
    )
    try:
        while True:
            await asyncio.sleep(interval)
            await websocket.send_text(partial_json)
    except asyncio.CancelledError:
        logger.error(f"{_MODULE} widget_operation_ws_heartbeat_cancelled")
        return
    except Exception:
        logger.error(f"{_MODULE} widget_operation_ws_heartbeat_failed", exc_info=True)


async def _record_widget_batch_case(
    store: WidgetBatchStore | None,
    context: WidgetBatchContext | None,
    request_id: str | None,
    raw_payload: dict[str, Any],
    business_response: dict[str, Any],
    final_frame: dict[str, Any],
    render_messages: list[dict[str, Any]],
    duration_ms: float,
    started_at: str,
    status: str,
    error_code: str,
    artifact_url: str = "",
    artifact_digest: str = "",
    model_steps: list[dict[str, Any]] | None = None,
    diagnostics: dict[str, Any] | None = None,
) -> None:
    """批测记录失败不反向改变正式工具响应。"""
    if store is None or context is None:
        return
    record = WidgetBatchCaseRecord(
        context=context,
        request_id=request_id,
        raw_payload=raw_payload,
        business_response=business_response,
        final_frame=final_frame,
        render_messages=render_messages,
        duration_ms=duration_ms,
        started_at=started_at,
        completed_at=utc_now(),
        status=status,
        error_code=error_code,
        artifact_url=artifact_url,
        artifact_digest=artifact_digest,
        model_steps=model_steps or [],
        diagnostics=diagnostics or {},
    )
    try:
        await run_in_threadpool(store.record_case, record)
        logger.info(
            f"{_MODULE} widget_batch_case_recorded batch_id={context.batch_id} "
            f"case_id={context.case_id} status={status} duration_ms={duration_ms}"
        )
    except Exception:
        logger.error(
            f"{_MODULE} widget_batch_case_record_failed batch_id={context.batch_id} "
            f"case_id={context.case_id}",
            exc_info=True,
        )


async def _serve_operation_websocket(
    websocket: WebSocket,
    operation: str,
    request_model: type[BaseModel],
    handler,
    heartbeat: bool = False,
    heartbeat_interval: float = 6.0,
    handler_in_threadpool: bool = True,
    batch_store: WidgetBatchStore | None = None,
    batch_context: WidgetBatchContext | None = None,
) -> None:
    """承载单个工具能力的 WebSocket 循环。

    每条消息依次经过：原始日志、协议归一化、start/heartbeat、业务调用和 final 封装。
    同步查询在线程池执行，长耗时生成链路直接等待异步 service。

    入参：
    - websocket：客户端 WebSocket 连接。
    - operation：当前 WS path 对应的能力名。
    - request_model：当前能力的入参实体类。
    - handler：当前能力对应的 service 方法。
    - handler_in_threadpool：同步查询为 true，异步生成链路为 false。
    出参：无；服务端通过 WebSocket 返回华为流处理插件格式消息。
    """
    # 每个 WS path 只承载一个业务能力，客户端不需要再传 operation 字段。
    if get_settings().websocket_bearer_token and not _card_template_authorized(websocket):
        await websocket.close(code=1008, reason="invalid bearer token")
        return
    metrics = websocket_metrics
    await websocket.accept()
    metrics.connection_opened()
    logger.info(f"{_MODULE} widget_operation_ws_connected operation={operation}")
    try:
        model_runtime = getattr(websocket.app.state, "model_runtime", None)
        service = get_service(model_runtime)
        while True:
            card_id = str(uuid.uuid4())
            directive_size = DEFAULT_WIDGET_SIZE
            widget_directive_started = False
            try:
                payload = await websocket.receive_json()
            except ValueError as exc:
                logger.error(
                    f"{_MODULE} widget_operation_ws_invalid_json operation={operation} "
                    f"exception_type={type(exc).__name__} exception={exc!r}"
                )
                error_message = WidgetWebSocketErrorMessage(
                    tool=operation,
                    operation=operation,
                    errorCode=ErrorCode.INVALID_ARGUMENTS.value,
                    error={
                        "message": "WebSocket request body must be valid JSON.",
                        "details": str(exc),
                    },
                )
                streaming_text_id = uuid.uuid4().hex
                plugin_response = _build_plugin_stream_response(
                    error_message,
                    streaming_text_id,
                )
                if not await _send_websocket_json(
                    websocket,
                    plugin_response.model_dump(mode="json", exclude_none=True),
                    operation,
                    None,
                    "final_error",
                ):
                    return
                continue
            # 完整协议校验前只提取关联 ID，保证原始请求日志也能归属当前轮次。
            raw_request_id = _request_id_from_raw_payload(payload)
            directive_size = _directive_size_from_raw_payload(payload)
            task_logger.set_session_id(raw_request_id or "None")
            logger.info(
                f"widget_operation_ws_raw_request_received operation={operation} "
                f"request_body={json_for_log(payload)}"
            )
            started_at = time.perf_counter()
            batch_started_at = utc_now()
            request_id = None
            arguments: dict[str, Any] = {}
            heartbeat_task: asyncio.Task | None = None
            streaming_text_id = uuid.uuid4().hex
            metrics.task_started()
            try:
                if not isinstance(payload, dict):
                    raise ValueError("WebSocket request body must be a JSON object")
                request_id, arguments = _normalize_payload(payload, operation)
                # 解析出 requestId 后立即写入日志上下文，后续链路共用同一日志标识。
                task_logger.set_session_id(request_id or "None")
                logger.info(
                    f"{_MODULE} widget_operation_ws_payload_received request_id={request_id} "
                    f"operation={operation} payload_keys={json_for_log(sorted(payload))} "
                    f"argument_keys={json_for_log(sorted(arguments))}"
                )
                # 有 requestId 时沿用它，否则为当前消息生成稳定的流式文本 ID。
                streaming_text_id = request_id or uuid.uuid4().hex
                device_arguments = arguments.get("device")
                source_rom_version = None
                if isinstance(device_arguments, dict):
                    source_rom_version = device_arguments.pop("_sourceRomVersion", None)
                request = request_model(**arguments)
                request.device._source_rom_version = source_rom_version
                request._widget_batch_request = batch_context is not None
                if operation in GENERATION_OPERATIONS:
                    request._model_request_context = _model_request_context_from_payload(
                        payload,
                        request,
                    )
                request_log = json_for_log(
                    request.model_dump(
                        mode="json",
                        exclude={"uid", "sourceArtifactUrl"},
                        exclude_none=True,
                    )
                )
                logger.info(
                    f"{_MODULE} widget_operation_ws_message_received request_id={request_id} "
                    f"operation={operation} "
                    f"request={request_log}"
                )
                # 收到合法请求后先发送 start 帧，再启动心跳协程。
                start_frame = WidgetPluginStreamResponse(
                    errorCode="0",
                    errorMessage="",
                    reply=WidgetPluginReply(
                        streamInfo=WidgetStreamInfo(
                            streamContent="",
                            streamingTextId=streaming_text_id,
                            streamType="start",
                            textType="markdown",
                        ),
                        items=[],
                    ),
                )
                if not await _send_websocket_json(
                    websocket,
                    start_frame.model_dump(mode="json", exclude_none=True),
                    operation,
                    request_id,
                    "start",
                ):
                    return
                if heartbeat:
                    heartbeat_task = asyncio.create_task(
                        _heartbeat_sender(websocket, streaming_text_id, heartbeat_interval)
                    )
                if handler_in_threadpool:
                    result = await run_in_threadpool(handler, service, request)
                else:
                    # 心跳通道断开不取消内部生成、repair 或 artifact 保存。
                    async def send_model_start_command(
                        resolved_size: WidgetSize | None = None,
                        raw_payload=payload,
                        current_request_id=request_id,
                        current_streaming_text_id=streaming_text_id,
                        current_card_id=card_id,
                    ) -> None:
                        nonlocal directive_size, widget_directive_started
                        directive_size = _normalize_directive_size(
                            resolved_size,
                            directive_size,
                        )
                        command_enabled = _widget_directive_commands_enabled(operation)
                        command_sent = await _send_widget_directive_command(
                            websocket,
                            raw_payload,
                            operation,
                            current_request_id,
                            current_streaming_text_id,
                            WidgetDirectiveState.START,
                            current_card_id,
                            directive_size,
                        )
                        if command_enabled and command_sent:
                            widget_directive_started = True

                    result = await handler(service, request, send_model_start_command)
                result_data = result.model_dump(mode="json", exclude_none=True)
                duration_ms = round((time.perf_counter() - started_at) * 1000, 2)
                logger.info(
                    f"{_MODULE} widget_operation_ws_handler_completed request_id={request_id} "
                    f"operation={operation} duration_ms={duration_ms} "
                    f"response={json_for_log(result_data)}"
                )
                result_message = WidgetWebSocketResultMessage(
                    tool=operation,
                    operation=operation,
                    requestId=request_id,
                    data=result_data,
                    status=result_data.get("status", "success"),
                    errorCode=result_data.get("errorCode", ""),
                    error={},
                )
                plugin_response = _build_plugin_stream_response(
                    result_message,
                    streaming_text_id,
                )
                plugin_response_data = plugin_response.model_dump(
                    mode="json",
                    exclude_none=True,
                )
                render_messages = getattr(result, "renderMessages", [])
                await _record_widget_batch_case(
                    batch_store,
                    batch_context,
                    request_id,
                    payload,
                    result_data,
                    plugin_response_data,
                    render_messages,
                    duration_ms,
                    batch_started_at,
                    str(result_data.get("status", "success")),
                    str(result_data.get("errorCode", "")),
                    str(result_data.get("artifactUrl", "")),
                    str(result_data.get("artifactDigest", "")),
                    getattr(result, "modelSteps", []),
                    getattr(result, "batchDiagnostics", {}),
                )
                if operation in GENERATION_OPERATIONS and widget_directive_started:
                    directive_state, artifact_url = _generation_result_directive(result_data)
                    directive_size = _normalize_directive_size(
                        result_data.get("suggestSize"),
                        directive_size,
                    )
                    if not await _send_widget_directive_command(
                        websocket,
                        payload,
                        operation,
                        request_id,
                        streaming_text_id,
                        directive_state,
                        card_id,
                        directive_size,
                        artifact_url,
                    ):
                        return
                if not await _send_websocket_json(
                    websocket,
                    plugin_response_data,
                    operation,
                    request_id,
                    "final",
                ):
                    return
            except ValueError as exc:
                duration_ms = round((time.perf_counter() - started_at) * 1000, 2)
                logger.error(
                    f"{_MODULE} widget_operation_ws_invalid_arguments request_id={request_id} "
                    f"operation={operation} duration_ms={duration_ms} "
                    f"details={json_for_log(_error_details(exc))} "
                    f"exception_type={type(exc).__name__} exception={exc!r} "
                    f"traceback={traceback.format_exc()}"
                )
                error_message = WidgetWebSocketErrorMessage(
                    tool=operation,
                    operation=operation,
                    requestId=request_id,
                    errorCode="INVALID_ARGUMENTS",
                    error={
                        "message": f"Invalid {operation} arguments.",
                        "details": _error_details(exc),
                    },
                )
                plugin_response = _build_plugin_stream_response(
                    error_message,
                    streaming_text_id,
                )
                plugin_response_data = plugin_response.model_dump(
                    mode="json",
                    exclude_none=True,
                )
                raw_payload = payload if isinstance(payload, dict) else {"rawPayload": payload}
                await _record_widget_batch_case(
                    batch_store,
                    batch_context,
                    request_id,
                    raw_payload,
                    error_message.model_dump(mode="json", exclude_none=True),
                    plugin_response_data,
                    [],
                    duration_ms,
                    batch_started_at,
                    "failed",
                    "INVALID_ARGUMENTS",
                )
                if operation in GENERATION_OPERATIONS and widget_directive_started:
                    if not await _send_widget_directive_command(
                        websocket,
                        raw_payload,
                        operation,
                        request_id,
                        streaming_text_id,
                        WidgetDirectiveState.FAILURE,
                        card_id,
                        directive_size,
                    ):
                        return
                if not await _send_websocket_json(
                    websocket,
                    plugin_response_data,
                    operation,
                    request_id,
                    "final_error",
                ):
                    return
            except Exception as exc:
                duration_ms = round((time.perf_counter() - started_at) * 1000, 2)
                logger.error(
                    f"{_MODULE} widget_operation_ws_failed request_id={request_id} "
                    f"operation={operation} duration_ms={duration_ms} error={exc} "
                    f"exception_type={type(exc).__name__} exception={exc!r} "
                    f"traceback={traceback.format_exc()}"
                )
                error_message = WidgetWebSocketErrorMessage(
                    tool=operation,
                    operation=operation,
                    requestId=request_id,
                    errorCode="FAILED",
                    error={"message": str(exc)},
                )
                plugin_response = _build_plugin_stream_response(
                    error_message,
                    streaming_text_id,
                )
                plugin_response_data = plugin_response.model_dump(
                    mode="json",
                    exclude_none=True,
                )
                raw_payload = payload if isinstance(payload, dict) else {"rawPayload": payload}
                await _record_widget_batch_case(
                    batch_store,
                    batch_context,
                    request_id,
                    raw_payload,
                    error_message.model_dump(mode="json", exclude_none=True),
                    plugin_response_data,
                    [],
                    duration_ms,
                    batch_started_at,
                    "failed",
                    "FAILED",
                )
                if operation in GENERATION_OPERATIONS and widget_directive_started:
                    if not await _send_widget_directive_command(
                        websocket,
                        raw_payload,
                        operation,
                        request_id,
                        streaming_text_id,
                        WidgetDirectiveState.FAILURE,
                        card_id,
                        directive_size,
                    ):
                        return
                if not await _send_websocket_json(
                    websocket,
                    plugin_response_data,
                    operation,
                    request_id,
                    "final_error",
                ):
                    return
            finally:
                metrics.task_finished()
                if heartbeat_task:
                    heartbeat_task.cancel()
                    with suppress(asyncio.CancelledError):
                        await heartbeat_task
    except WebSocketDisconnect:
        logger.info(f"{_MODULE} widget_operation_ws_disconnected operation={operation}")
        return
    finally:
        metrics.connection_closed()


@router.get("/artifacts/{file_name}")
async def download_widget_artifact(file_name: str) -> FileResponse:
    """下载本地 mock OBS 中的不可变卡片产物。"""
    prefix = "artifact_"
    suffix = ".md"
    if not file_name.startswith(prefix) or not file_name.endswith(suffix):
        raise HTTPException(status_code=404, detail="artifact not found")
    artifact_id = file_name[len(prefix) : -len(suffix)]
    try:
        uuid.UUID(artifact_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail="artifact not found") from exc
    artifact_path = get_settings().WORKSPACE_ROOT / "mock_obs" / file_name
    if not artifact_path.is_file():
        raise HTTPException(status_code=404, detail="artifact not found")
    return FileResponse(
        artifact_path,
        media_type="text/markdown; charset=utf-8",
        headers={"Cache-Control": "public, max-age=31536000, immutable"},
    )


@router.get("/widget-batches")
async def list_widget_batches(request: Request) -> dict[str, Any]:
    """列出服务器上已记录的 Nested-2 批测批次。"""
    store = WidgetBatchStore()
    _require_batch_http_access(request, store)
    try:
        return await run_in_threadpool(store.list_batches)
    except Exception as exc:
        raise _widget_batch_http_error(exc) from exc


@router.get("/widget-batches/{batch_id}")
async def get_widget_batch(request: Request, batch_id: str) -> dict[str, Any]:
    """读取一个批次的 manifest 和用例统计。"""
    store = WidgetBatchStore()
    _require_batch_http_access(request, store)
    try:
        return await run_in_threadpool(store.get_batch, batch_id)
    except Exception as exc:
        raise _widget_batch_http_error(exc) from exc


@router.get("/widget-batches/{batch_id}/download")
async def download_widget_batch(request: Request, batch_id: str) -> Response:
    """下载包含输入、输出和耗时信息的批次 ZIP。"""
    store = WidgetBatchStore()
    _require_batch_http_access(request, store)
    try:
        filename, content = await run_in_threadpool(store.build_download, batch_id)
    except Exception as exc:
        raise _widget_batch_http_error(exc) from exc
    return Response(
        content=content,
        media_type="application/zip",
        headers={
            "Cache-Control": "no-store",
            "Content-Disposition": f'attachment; filename="{filename}"',
        },
    )


@router.websocket("/ws/tools/getWidgetCapabilityOverview")
async def get_widget_capability_overview_ws(websocket: WebSocket):
    """能力概述 WebSocket 入口。

    入参：
    - websocket：客户端 WebSocket 连接，消息体需符合 CapabilityOverviewRequest。
    出参：无；服务端通过 WebSocket 返回 result 或 error 消息。
    """
    await _serve_operation_websocket(
        websocket,
        "getWidgetCapabilityOverview",
        CapabilityOverviewRequest,
        lambda service, request: service.get_widget_capability_overview(request),
    )


@router.websocket("/ws/tools/getDataCapabilitySchemas")
async def get_data_capability_schemas_ws(websocket: WebSocket):
    """数据能力 schema WebSocket 入口。

    入参：
    - websocket：客户端 WebSocket 连接，消息体需符合 DataCapabilitySchemasRequest。
    出参：无；服务端通过 WebSocket 返回 result 或 error 消息。
    """
    await _serve_operation_websocket(
        websocket,
        "getDataCapabilitySchemas",
        DataCapabilitySchemasRequest,
        lambda service, request: service.get_data_capability_schemas(request),
    )


@router.websocket("/ws/tools/generateWidgetCard")
async def generate_widget_card_ws(websocket: WebSocket):
    """卡片生成 WebSocket 入口。

    入参：
    - websocket：客户端 WebSocket 连接，消息体需符合 GenerateWidgetCardRequest。
    出参：无；服务端通过 WebSocket 返回 result 或 error 消息。
    """
    await _serve_operation_websocket(
        websocket,
        "generateWidgetCard",
        GenerateWidgetCardRequest,
        lambda service, request, before_model_call: service.generate_widget_card_a2ui_form(
            request,
            before_model_call=before_model_call,
        ),
        heartbeat=True,
        heartbeat_interval=6.0,
        handler_in_threadpool=False,
    )


@router.websocket("/ws/tools/generateWidgetCardCompactDsl")
async def generate_widget_card_compact_dsl_ws(websocket: WebSocket):
    """Compact DSL 卡片生成 WebSocket 入口。"""
    await _serve_operation_websocket(
        websocket,
        "generateWidgetCardCompactDsl",
        GenerateWidgetCardRequest,
        lambda service, request, before_model_call: service.generate_widget_card_compact_dsl(
            request,
            before_model_call=before_model_call,
        ),
        heartbeat=True,
        heartbeat_interval=6.0,
        handler_in_threadpool=False,
    )


@router.websocket(f"/ws/tools/{TEMPORARY_COMPACT_DIRECTIVE_OPERATION}")
async def generate_widget_card_compact_dsl_with_directive_ws(websocket: WebSocket):
    """临时复用第四接口，并始终发送端侧指令帧。"""
    await _serve_operation_websocket(
        websocket,
        TEMPORARY_COMPACT_DIRECTIVE_OPERATION,
        GenerateWidgetCardRequest,
        lambda service, request, before_model_call: service.generate_widget_card_compact_dsl(
            request,
            before_model_call=before_model_call,
        ),
        heartbeat=True,
        heartbeat_interval=6.0,
        handler_in_threadpool=False,
    )


@router.websocket("/ws/tools/generateWidgetCardTerseDslNested2")
async def generate_widget_card_terse_dsl_nested2_ws(websocket: WebSocket):
    """TerseDSL-Nested-2 卡片生成 WebSocket 入口。"""
    if get_settings().websocket_bearer_token and not _card_template_authorized(websocket):
        await websocket.close(code=1008, reason="invalid bearer token")
        return
    store = WidgetBatchStore()
    try:
        context = store.context_from_query(
            websocket.query_params,
            "generateWidgetCardTerseDslNested2",
        )
    except (ValueError, WidgetBatchRecordingDisabledError) as exc:
        logger.error(f"{_MODULE} widget_batch_query_rejected exception_type={type(exc).__name__}")
        await websocket.close(code=1008, reason=str(exc))
        return
    await _serve_operation_websocket(
        websocket,
        "generateWidgetCardTerseDslNested2",
        GenerateWidgetCardRequest,
        lambda service, request, before_model_call: service.generate_widget_card_terse_dsl_nested2(
            request,
            before_model_call=before_model_call,
        ),
        heartbeat=True,
        heartbeat_interval=6.0,
        handler_in_threadpool=False,
        batch_store=store if context is not None else None,
        batch_context=context,
    )
