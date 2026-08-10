# -*- coding: utf-8 -*-
# Copyright (c) Huawei Technologies Co., Ltd. 2026-2026. All rights reserved.
"""创建 Widget Service 的 FastAPI 应用并管理应用生命周期。"""

import asyncio
from contextlib import asynccontextmanager, suppress

from anyio import to_thread
from fastapi import FastAPI, Request, Response

from api.routes import router
from app.logger import logger
from app.websocket_metrics import report_websocket_metrics, websocket_metrics
from custom.model_runtime import ModelExecutionRuntime
from runtime_settings import get_settings

_MODULE = "[Main]"


def configure_anyio_thread_pool() -> int:
    """配置 Starlette 同步业务处理使用的 AnyIO 默认线程池容量。"""
    limiter = to_thread.current_default_thread_limiter()
    previous_tokens = limiter.total_tokens
    configured_tokens = get_settings().anyio_thread_pool_tokens
    limiter.total_tokens = configured_tokens
    logger.info(
        f"{_MODULE} anyio_thread_pool_configured previous_tokens={previous_tokens} "
        f"total_tokens={configured_tokens}"
    )
    return configured_tokens


def create_app() -> FastAPI:
    """创建配置好路由、生命周期和健康检查的 FastAPI 应用。"""

    @asynccontextmanager
    async def lifespan(_app: FastAPI):
        configure_anyio_thread_pool()
        model_runtime = ModelExecutionRuntime()
        _app.state.model_runtime = model_runtime
        reporter = asyncio.create_task(report_websocket_metrics(websocket_metrics))
        try:
            yield
        finally:
            reporter.cancel()
            with suppress(asyncio.CancelledError):
                await reporter
            await model_runtime.aclose()

    fastapi_app = FastAPI(
        title="Widget Service",
        version="0.1.0",
        description="AI widget card generation microservice.",
        lifespan=lifespan,
    )
    fastapi_app.include_router(router)

    @fastapi_app.middleware("http")
    async def request_logging_middleware(request: Request, call_next) -> Response:
        """调用下一个 HTTP 处理器；请求日志由既有追踪链路统一记录。"""
        return await call_next(request)

    @fastapi_app.get("/health")
    async def health() -> dict[str, str]:
        """返回服务存活状态。"""
        return {"status": "ok"}

    return fastapi_app


app = create_app()
