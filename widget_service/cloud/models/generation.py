# -*- coding: utf-8 -*-
# Copyright (c) Huawei Technologies Co., Ltd. 2026-2026. All rights reserved.
import json
import math
from dataclasses import dataclass
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, PrivateAttr, field_validator

WidgetSize = Literal["2x2", "2x4"]
DEFAULT_WIDGET_SIZE: WidgetSize = "2x2"


@dataclass(frozen=True)
class ModelRequestContext:
    """一次工具请求传递给物理模型服务的稳定会话上下文。"""

    session_id: str
    interaction_id: str
    device_id: str
    country_code: str
    app_version: str
    app_name: str


class DeviceContext(BaseModel):
    _source_rom_version: str | None = PrivateAttr(default=None)

    deviceId: str | None = None
    deviceType: str | None = None
    sysVersion: str | None = None
    deviceName: str | None = None
    odid: str | None = None
    udid: str | None = None
    romVersion: str
    marketingName: str | None = None


class CandidateDataBinding(BaseModel):
    model_config = ConfigDict(extra="forbid")

    capabilityId: str
    arguments: dict[str, Any] = Field(default_factory=dict)
    writeResultTo: str
    candidateOutputFields: list[str] = Field(default_factory=list)
    # 受控调用可提供用于设计生成的即时数据预览。该字段只参与 TaskSpec Prompt，
    # 不进入 CardSpec、工具响应或生产请求日志。
    previewData: dict[str, Any] | None = Field(default=None, exclude=True)

    @field_validator("previewData")
    @classmethod
    def validate_preview_data(cls, value: dict[str, Any] | None) -> dict[str, Any] | None:
        if value is None:
            return None
        node_count = 0

        def walk(item: Any, depth: int) -> None:
            nonlocal node_count
            node_count += 1
            if node_count > 128:
                raise ValueError("previewData exceeds the node limit")
            if depth > 8:
                raise ValueError("previewData exceeds the depth limit")
            if isinstance(item, dict):
                for key, child in item.items():
                    if not isinstance(key, str) or not key or len(key) > 128:
                        raise ValueError("previewData keys must be non-empty short strings")
                    if key in {"__proto__", "constructor", "prototype"}:
                        raise ValueError("previewData contains a forbidden key")
                    walk(child, depth + 1)
                return
            if isinstance(item, list):
                if len(item) > 32:
                    raise ValueError("previewData arrays exceed the item limit")
                for child in item:
                    walk(child, depth + 1)
                return
            if isinstance(item, str):
                if len(item) > 512:
                    raise ValueError("previewData strings exceed the size limit")
                return
            if isinstance(item, bool) or item is None or isinstance(item, int):
                return
            if isinstance(item, float) and math.isfinite(item):
                return
            raise ValueError("previewData accepts JSON literals only")

        walk(value, 0)
        if len(json.dumps(value, ensure_ascii=False, separators=(",", ":"))) > 16_384:
            raise ValueError("previewData exceeds the encoded size limit")
        return value


class CardSpecDataBinding(BaseModel):
    """微服务裁决后写入最终 CardSpec 的数据绑定。"""

    model_config = ConfigDict(extra="forbid")

    capabilityId: str
    arguments: dict[str, Any] = Field(default_factory=dict)
    writeResultTo: str


class EventAction(BaseModel):
    id: str | None = None
    displayLabel: str | None = None
    call: str
    args: dict[str, Any]


class GenerationOptions(BaseModel):
    model_config = ConfigDict(extra="forbid")

    allowDegradation: bool = True
    forceHybridTemplate: bool = False
    testAuthorization: str | None = Field(default=None, exclude=True)


class CardSpec(BaseModel):
    title: str = Field(min_length=1)
    description: str = Field(min_length=1)
    suggestSize: WidgetSize
    dataBindings: list[CardSpecDataBinding] | None = None


class TaskSpec(BaseModel):
    model_config = ConfigDict(extra="forbid")

    userQuery: str
    size: WidgetSize
    eventCandidates: list[EventAction] = Field(default_factory=list)
    dataModelSchema: dict[str, Any]
    assetCandidates: list[dict[str, Any]] = Field(default_factory=list)
    selectedTemplateId: str | None = None
