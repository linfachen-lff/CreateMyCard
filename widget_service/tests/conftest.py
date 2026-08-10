# -*- coding: utf-8 -*-
# Copyright (c) Huawei Technologies Co., Ltd. 2026-2026. All rights reserved.
"""让测试和生产启动通过同一个 zone 配置 Adapter。"""

import sys
from importlib import import_module
from pathlib import Path

SERVICE_ROOT = Path(__file__).resolve().parents[1]
CLOUD_ROOT = SERVICE_ROOT / "cloud"
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
