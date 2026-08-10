# -*- coding: utf-8 -*-
# Copyright (c) Huawei Technologies Co., Ltd. 2026-2026. All rights reserved.
"""验证 shared 配置契约与 zone Adapter 的启动约束。"""

import ast
import os
import subprocess
import sys
from importlib import import_module
from pathlib import Path

import pytest

from runtime_settings import get_settings, install_runtime_providers

SERVICE_ROOT = Path(__file__).resolve().parents[1]
CLOUD_ROOT = SERVICE_ROOT / "cloud"
SHARED_ROOT = CLOUD_ROOT / "shared"
ZONE_RUNTIME_ROOT = CLOUD_ROOT / "zone" / "runtime"


def _run_without_test_bootstrap(source: str) -> subprocess.CompletedProcess[str]:
    env = dict(os.environ)
    env["PYTHONPATH"] = str(SHARED_ROOT)
    env["PYTHONPYCACHEPREFIX"] = str(ZONE_RUNTIME_ROOT / "pycache")
    return subprocess.run(
        [sys.executable, "-c", source],
        cwd=SERVICE_ROOT,
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )


def test_provider_fails_before_zone_adapter_is_installed() -> None:
    result = _run_without_test_bootstrap(
        "from runtime_settings import get_settings; get_settings()"
    )

    assert result.returncode != 0
    assert "settings provider is not installed" in result.stderr


def test_required_zone_field_is_named_before_shared_app_import() -> None:
    source = "\n".join(
        (
            "from runtime_settings import Settings, install_runtime_providers",
            "class GreenSettings(Settings):",
            "    a: str",
            "install_runtime_providers(",
            "    lambda: GreenSettings(_env_file=None),",
            "    lambda _key: b'',",
            ")",
        )
    )
    result = _run_without_test_bootstrap(source)

    assert result.returncode != 0
    assert "a" in result.stderr
    assert "Field required" in result.stderr


def test_provider_rejects_runtime_paths_inside_replaceable_shared_directory() -> None:
    source = "\n".join(
        (
            "from runtime_settings import Settings, install_runtime_providers",
            "install_runtime_providers(Settings, lambda _key: b'')",
        )
    )
    result = _run_without_test_bootstrap(source)

    assert result.returncode != 0
    assert "PROJECT_ROOT must be outside the replaceable shared directory" in result.stderr


def test_zone_adapter_keeps_runtime_state_outside_shared() -> None:
    settings = get_settings()

    assert settings.repository_root == SERVICE_ROOT
    assert settings.resolved_system_prompt_file == SHARED_ROOT / "prompts" / "system_prompt.txt"
    assert not settings.PROJECT_ROOT.is_relative_to(SHARED_ROOT)
    assert not settings.WORKSPACE_ROOT.is_relative_to(SHARED_ROOT)
    assert not (SHARED_ROOT / "logs").exists()
    assert not (SHARED_ROOT / "workspace").exists()


def _is_zone_module(module_name: str) -> bool:
    exact_module = module_name in {"zone", "cloud.zone"}
    nested_module = module_name.startswith(("zone.", "cloud.zone."))
    return exact_module or nested_module


def test_shared_cloud_does_not_import_zone_implementation() -> None:
    zone_imports: list[str] = []
    for source_path in SHARED_ROOT.rglob("*.py"):
        tree = ast.parse(source_path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom):
                imported_modules = [node.module or ""]
            elif isinstance(node, ast.Import):
                imported_modules = [alias.name for alias in node.names]
            else:
                continue
            if any(_is_zone_module(name) for name in imported_modules):
                zone_imports.append(str(source_path.relative_to(SHARED_ROOT)))

    assert zone_imports == []


def test_provider_is_idempotent_but_cannot_be_replaced_after_imports() -> None:
    zone_config = import_module("cloud.zone.config")
    install_runtime_providers(zone_config.create_settings, zone_config.read_secret)

    with pytest.raises(RuntimeError, match="already installed"):
        install_runtime_providers(
            lambda: zone_config.create_settings(),
            zone_config.read_secret,
        )
