# -*- coding: utf-8 -*-
# Copyright (c) Huawei Technologies Co., Ltd. 2026-2026. All rights reserved.
"""固定启动入口：先安装区内配置，再加载 shared 应用。"""

import sys
from importlib import import_module
from pathlib import Path

import uvicorn

CLOUD_ROOT = Path(__file__).resolve().parent
SERVICE_ROOT = CLOUD_ROOT.parent
SHARED_ROOT = CLOUD_ROOT / "shared"
sys.pycache_prefix = str(CLOUD_ROOT / "zone" / "runtime" / "pycache")

for import_root in (SHARED_ROOT, SERVICE_ROOT):
    import_path = str(import_root)
    if import_path not in sys.path:
        sys.path.insert(0, import_path)

runtime_settings = import_module("runtime_settings")
zone_config = import_module("cloud.zone.config")

runtime_settings.install_runtime_providers(
    zone_config.create_settings,
    zone_config.read_secret,
)

shared_application = import_module("app.application")
app = shared_application.app

__all__ = ["app"]


def run_local_server() -> None:
    """使用当前区配置启动 Uvicorn 服务。"""
    settings = runtime_settings.get_settings()
    uvicorn.run(
        app,
        host=settings.server_host,
        port=settings.server_port,
        log_config=None,
    )


if __name__ == "__main__":
    run_local_server()
