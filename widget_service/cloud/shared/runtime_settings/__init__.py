# -*- coding: utf-8 -*-
# Copyright (c) Huawei Technologies Co., Ltd. 2026-2026. All rights reserved.
"""共享配置契约与区内 Adapter 安装接口。"""

from runtime_settings.provider import (
    SettingsProviderNotInstalledError,
    get_secret,
    get_settings,
    install_runtime_providers,
)
from runtime_settings.schema import Settings

__all__ = [
    "Settings",
    "SettingsProviderNotInstalledError",
    "get_secret",
    "get_settings",
    "install_runtime_providers",
]
