# -*- coding: utf-8 -*-
# Copyright (c) Huawei Technologies Co., Ltd. 2026-2026. All rights reserved.
"""蓝区配置 Adapter；绿区保留同名文件并替换为本区取值实现。"""

from pathlib import Path

from runtime_settings import Settings

ZONE_ROOT = Path(__file__).resolve().parent
ZONE_RUNTIME_ROOT = ZONE_ROOT / "runtime"
ZONE_SECRETS: dict[str, bytes] = {
    "genui.deepseek.platform.secret.key": b"22222",
    "genui.model.secret.key": b"22222",
    "ids.secret.key": b"22222",
}


class ZoneSettings(Settings):
    """当前蓝区的默认值；这些值不会随 shared 文件夹进入绿区。"""

    ids_query_url: str = "http://{{ip}}:{{port}}/hiai/ids/databus/v1/kvcommondata/query"
    ids_calling_uid: str = "decisionhub"
    ids_dev_fake_id: str = "123**********postmantestdevFakeId"
    ids_access_key: str = "23232323232"
    deepseek_platform_secret_key_sts_config_key: str = (
        "genui.deepseek.platform.secret.key"
    )
    deepseek_platform_model_name: str = "AGENT-DEEPSEEK-V4-FLASH"
    deepseek_platform_api_key: str = "AccessService"
    deepseek_platform_sender: str = "superagent"
    deepseek_platform_receiver: str = "LLM-WS"
    deepseek_platform_message_name: str = "llmRecognize"
    deepseek_api_key: str = "AccessService"
    deepseek_model: str = "deepseek-ai/DeepSeek-V4-Flash"
    deepseek_ws_url: str = (
        "ws://10.32.101.24:18087/llm/websocket/openai/chat/completions"
    )
    deepseek_user: str = "genui_user"
    deepseek_request_id: str = "genui_ui"
    artifact_base_url: str = "https://obs.todo.local/widget"
    PROJECT_ROOT: Path = ZONE_RUNTIME_ROOT
    WORKSPACE_ROOT: Path = ZONE_RUNTIME_ROOT / "workspace"


def create_settings() -> Settings:
    """读取当前区的 `.env` 和区内函数结果，构造共享配置契约。"""
    return ZoneSettings(_env_file=ZONE_ROOT / ".env")


def read_secret(config_key: str) -> bytes:
    """蓝区安全配置读取 Adapter；绿区在这里改为调用本区安全配置函数。"""
    try:
        return ZONE_SECRETS[config_key]
    except KeyError as exc:
        raise KeyError(f"未找到区内安全配置: {config_key}") from exc
