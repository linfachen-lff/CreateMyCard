# -*- coding: utf-8 -*-
# Copyright (c) Huawei Technologies Co., Ltd. 2026-2026. All rights reserved.
"""在共享代码与区内配置 Adapter 之间提供唯一配置 seam。"""

from collections.abc import Callable

from runtime_settings.schema import Settings

SettingsFactory = Callable[[], Settings]
SecretReader = Callable[[str], bytes | str]

_settings_factory: SettingsFactory | None = None
_settings: Settings | None = None
_secret_reader: SecretReader | None = None


class SettingsProviderNotInstalledError(RuntimeError):
    """区内启动入口尚未安装配置 Adapter。"""


def _validate_runtime_boundaries(settings: Settings) -> None:
    shared_root = settings.package_root.resolve()
    runtime_paths = {
        "PROJECT_ROOT": settings.PROJECT_ROOT.resolve(),
        "WORKSPACE_ROOT": settings.WORKSPACE_ROOT.resolve(),
    }
    for field_name, runtime_path in runtime_paths.items():
        if runtime_path.is_relative_to(shared_root):
            raise ValueError(
                f"{field_name} must be outside the replaceable shared directory: {shared_root}"
            )


def install_runtime_providers(
    settings_factory: SettingsFactory,
    secret_reader: SecretReader,
) -> None:
    """在导入应用前原子安装区内配置与安全配置读取函数。"""
    if not callable(settings_factory):
        raise TypeError("settings provider must be callable")
    if not callable(secret_reader):
        raise TypeError("secret provider must be callable")
    global _secret_reader, _settings, _settings_factory
    same_settings_factory = _settings_factory is settings_factory
    same_secret_reader = _secret_reader is secret_reader
    if same_settings_factory and same_secret_reader:
        return
    if _settings_factory is not None or _secret_reader is not None:
        raise RuntimeError("runtime providers are already installed")
    settings = settings_factory()
    if not isinstance(settings, Settings):
        raise TypeError("settings provider must return runtime_settings.Settings")
    _validate_runtime_boundaries(settings)
    _settings_factory = settings_factory
    _settings = settings
    _secret_reader = secret_reader


def get_settings() -> Settings:
    """返回当前区配置；未安装 Adapter 时立即失败。"""
    settings = _settings
    if settings is None:
        raise SettingsProviderNotInstalledError(
            "settings provider is not installed; start the service through "
            "python -m cloud.start_websocket_server"
        )
    return settings


def get_secret(config_key: str) -> bytes | str:
    """通过当前区函数读取安全配置；共享代码不保存任何区内密钥。"""
    reader = _secret_reader
    if reader is None:
        raise SettingsProviderNotInstalledError(
            "secret provider is not installed; start the service through "
            "python -m cloud.start_websocket_server"
        )
    return reader(config_key)
