# -*- coding: utf-8 -*-
# Copyright (c) Huawei Technologies Co., Ltd. 2026-2026. All rights reserved.
import json
import os
import re
import threading
import uuid
import zipfile
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import UTC, datetime
from io import BytesIO
from pathlib import Path
from typing import Any

from app.logger import logger
from config.config import Settings, get_settings

BATCH_SCHEMA_VERSION = "widget-batch-run-v1"
CASE_RESPONSE_SCHEMA_VERSION = "widget-batch-case-response-v1"
IDENTIFIER_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,63}$")
ALLOWED_CARD_SIZES = frozenset({"2x2", "2x4"})
_STORE_LOCK = threading.Lock()


class WidgetBatchStoreError(RuntimeError):
    """批测结果存储的基础错误。"""


class WidgetBatchRecordingDisabledError(WidgetBatchStoreError):
    """批测记录开关未开启。"""


class WidgetBatchNotFoundError(WidgetBatchStoreError):
    """目标批次不存在。"""


@dataclass(frozen=True)
class WidgetBatchContext:
    batch_id: str
    case_id: str
    size: str
    operation: str


@dataclass(frozen=True)
class WidgetBatchCaseRecord:
    context: WidgetBatchContext
    request_id: str | None
    raw_payload: dict[str, Any]
    business_response: dict[str, Any]
    final_frame: dict[str, Any]
    render_messages: list[dict[str, Any]]
    duration_ms: float
    started_at: str
    completed_at: str
    status: str
    error_code: str
    artifact_url: str
    artifact_digest: str
    model_steps: list[dict[str, Any]]
    diagnostics: dict[str, Any]


class WidgetBatchStore:
    """把 Nested-2 批量评测输入、输出和耗时原子保存到运行时目录。"""

    def __init__(self, settings: Settings | None = None) -> None:
        self.settings = settings or get_settings()
        self.root = self.settings.resolved_widget_batch_results_path

    @property
    def enabled(self) -> bool:
        return self.settings.enable_widget_batch_recording

    def context_from_query(
        self,
        query: Mapping[str, str],
        operation: str,
    ) -> WidgetBatchContext | None:
        """读取显式批测查询参数；正式调用未携带参数时返回空。"""
        batch_id = query.get("batchId", "")
        case_id = query.get("caseId", "")
        size = query.get("size", "")
        supplied = (bool(batch_id), bool(case_id), bool(size))
        if not any(supplied):
            return None
        if not self.enabled:
            raise WidgetBatchRecordingDisabledError("widget batch recording is disabled")
        if not all(supplied):
            raise ValueError("batchId, caseId and size must be supplied together")
        self._validate_identifier(batch_id, "batchId")
        self._validate_identifier(case_id, "caseId")
        if size not in ALLOWED_CARD_SIZES:
            raise ValueError("size must be 2x2 or 2x4")
        return WidgetBatchContext(
            batch_id=batch_id,
            case_id=case_id,
            size=size,
            operation=operation,
        )

    def record_case(self, record: WidgetBatchCaseRecord) -> dict[str, Any]:
        """保存单条用例文件并更新批次 manifest。"""
        if not self.enabled:
            raise WidgetBatchRecordingDisabledError("widget batch recording is disabled")
        self._validate_identifier(record.context.batch_id, "batchId")
        self._validate_identifier(record.context.case_id, "caseId")
        if record.context.size not in ALLOWED_CARD_SIZES:
            raise ValueError("size must be 2x2 or 2x4")
        input_bytes = self._encoded_json_size(record.raw_payload)
        if input_bytes > self.settings.widget_batch_max_input_bytes:
            raise WidgetBatchStoreError("widget batch input exceeds configured limit")
        output_jsonl = self._render_messages_jsonl(record.render_messages)
        response_document = {
            "schemaVersion": CASE_RESPONSE_SCHEMA_VERSION,
            "businessResponse": record.business_response,
            "pluginFinalFrame": record.final_frame,
        }
        response_bytes = self._encoded_json_size(response_document)
        output_bytes = len(output_jsonl.encode("utf-8"))
        output_limit = self.settings.widget_batch_max_output_bytes
        if response_bytes > output_limit or output_bytes > output_limit:
            raise WidgetBatchStoreError("widget batch output exceeds configured limit")

        with _STORE_LOCK:
            self._ensure_private_dir(self.root)
            batch_dir = self._batch_dir(record.context.batch_id)
            self._ensure_private_dir(batch_dir)
            cases_dir = batch_dir / "cases"
            self._ensure_private_dir(cases_dir)
            case_dir = cases_dir / record.context.case_id
            self._ensure_private_dir(case_dir)
            self._write_json(case_dir / "input.json", record.raw_payload)
            self._write_json(case_dir / "response.json", response_document)
            self._write_text(case_dir / "output.a2ui.jsonl", output_jsonl)
            model_step_files = self._write_model_steps(case_dir, record.model_steps)
            self._write_json(case_dir / "diagnostics.json", record.diagnostics)
            metrics = self._metrics_document(record)
            self._write_json(case_dir / "metrics.json", metrics)
            manifest = self._updated_manifest(batch_dir, record, metrics, model_step_files)
            self._write_json(batch_dir / "manifest.json", manifest)
            return manifest

    def list_batches(self) -> dict[str, Any]:
        """按更新时间倒序返回可下载批次摘要。"""
        self._require_enabled()
        if not self.root.is_dir():
            return {"schemaVersion": BATCH_SCHEMA_VERSION, "batches": []}
        batches: list[dict[str, Any]] = []
        for manifest_path in self.root.glob("*/manifest.json"):
            try:
                manifest = self._read_json(manifest_path)
            except (OSError, json.JSONDecodeError) as exc:
                logger.error(
                    "[WidgetBatchStore] unreadable_manifest "
                    f"path={manifest_path} exception_type={type(exc).__name__}"
                )
                continue
            batches.append(
                {
                    "batchId": manifest.get("batchId", ""),
                    "operation": manifest.get("operation", ""),
                    "size": manifest.get("size", ""),
                    "createdAt": manifest.get("createdAt", ""),
                    "updatedAt": manifest.get("updatedAt", ""),
                    "summary": manifest.get("summary", {}),
                }
            )
        batches.sort(key=lambda item: str(item.get("updatedAt", "")), reverse=True)
        return {"schemaVersion": BATCH_SCHEMA_VERSION, "batches": batches}

    def get_batch(self, batch_id: str) -> dict[str, Any]:
        """读取单个批次 manifest。"""
        self._require_enabled()
        self._validate_identifier(batch_id, "batchId")
        manifest_path = self._batch_dir(batch_id) / "manifest.json"
        if not manifest_path.is_file():
            raise WidgetBatchNotFoundError(f"widget batch does not exist: {batch_id}")
        try:
            return self._read_json(manifest_path)
        except (OSError, json.JSONDecodeError) as exc:
            raise WidgetBatchStoreError("widget batch manifest is unreadable") from exc

    def build_download(self, batch_id: str) -> tuple[str, bytes]:
        """把 manifest 和全部用例文件打包为内存 ZIP。"""
        self.get_batch(batch_id)
        batch_dir = self._batch_dir(batch_id)
        archive_buffer = BytesIO()
        with zipfile.ZipFile(archive_buffer, mode="w", compression=zipfile.ZIP_DEFLATED) as archive:
            for file_path in sorted(batch_dir.rglob("*")):
                if (
                    file_path.is_symlink()
                    or not file_path.is_file()
                    or file_path.name.endswith(".tmp")
                ):
                    continue
                archive.write(file_path, arcname=file_path.relative_to(batch_dir))
        return f"widget-batch-{batch_id}.zip", archive_buffer.getvalue()

    def _updated_manifest(
        self,
        batch_dir: Path,
        record: WidgetBatchCaseRecord,
        metrics: dict[str, Any],
        model_step_files: list[str],
    ) -> dict[str, Any]:
        manifest_path = batch_dir / "manifest.json"
        if manifest_path.is_file():
            manifest = self._read_json(manifest_path)
        else:
            manifest = {
                "schemaVersion": BATCH_SCHEMA_VERSION,
                "batchId": record.context.batch_id,
                "operation": record.context.operation,
                "size": record.context.size,
                "createdAt": record.started_at,
                "updatedAt": record.completed_at,
                "summary": {},
                "cases": [],
            }
        if manifest.get("operation") != record.context.operation:
            raise WidgetBatchStoreError("batch operation cannot change")
        if manifest.get("size") != record.context.size:
            raise WidgetBatchStoreError("batch size cannot change")
        case_summary = self._case_summary(record, metrics, model_step_files)
        cases = [
            item
            for item in manifest.get("cases", [])
            if item.get("caseId") != record.context.case_id
        ]
        cases.append(case_summary)
        cases.sort(key=lambda item: str(item.get("caseId", "")))
        manifest["cases"] = cases
        manifest["updatedAt"] = record.completed_at
        manifest["summary"] = self._summary(cases)
        return manifest

    def _case_summary(
        self,
        record: WidgetBatchCaseRecord,
        metrics: dict[str, Any],
        model_step_files: list[str],
    ) -> dict[str, Any]:
        relative_root = f"cases/{record.context.case_id}"
        return {
            "caseId": record.context.case_id,
            "requestId": record.request_id,
            "size": record.context.size,
            "status": record.status,
            "errorCode": record.error_code,
            "durationMs": metrics["durationMs"],
            "artifactUrl": record.artifact_url,
            "artifactDigest": record.artifact_digest,
            "files": {
                "input": f"{relative_root}/input.json",
                "response": f"{relative_root}/response.json",
                "output": f"{relative_root}/output.a2ui.jsonl",
                "metrics": f"{relative_root}/metrics.json",
                "llmSteps": f"{relative_root}/llm-steps.json",
                "llmOutputs": [f"{relative_root}/{name}" for name in model_step_files],
                "diagnostics": f"{relative_root}/diagnostics.json",
            },
        }

    @staticmethod
    def _summary(cases: list[dict[str, Any]]) -> dict[str, int]:
        passed = sum(item.get("status") in {"success", "degraded"} for item in cases)
        failed = len(cases) - passed
        return {"total": len(cases), "passed": passed, "failed": failed}

    @staticmethod
    def _metrics_document(record: WidgetBatchCaseRecord) -> dict[str, Any]:
        return {
            "requestId": record.request_id,
            "startedAt": record.started_at,
            "completedAt": record.completed_at,
            "durationMs": round(record.duration_ms, 2),
            "status": record.status,
            "errorCode": record.error_code,
        }

    @staticmethod
    def _render_messages_jsonl(messages: list[dict[str, Any]]) -> str:
        if not messages:
            return ""
        rows = [
            json.dumps(message, ensure_ascii=False, separators=(",", ":"))
            for message in messages
        ]
        return "\n".join(rows) + "\n"

    def _write_model_steps(
        self,
        case_dir: Path,
        model_steps: list[dict[str, Any]],
    ) -> list[str]:
        metadata: list[dict[str, Any]] = []
        output_files: list[str] = []
        for index, step in enumerate(model_steps, start=1):
            phase = re.sub(r"[^A-Za-z0-9._-]+", "-", str(step.get("phase", "unknown")))
            output_name = f"llm-step-{index:02d}-{phase or 'unknown'}.txt"
            raw_output = str(step.get("rawOutput", ""))
            if len(raw_output.encode("utf-8")) > self.settings.widget_batch_max_output_bytes:
                raise WidgetBatchStoreError("widget batch LLM step output exceeds configured limit")
            self._write_text(case_dir / output_name, raw_output)
            output_files.append(output_name)
            input_messages = step.get("inputMessages")
            input_name = ""
            input_bytes = 0
            if isinstance(input_messages, list):
                input_jsonl = self._render_messages_jsonl(input_messages)
                input_bytes = len(input_jsonl.encode("utf-8"))
                if input_bytes > self.settings.widget_batch_max_input_bytes:
                    raise WidgetBatchStoreError(
                        "widget batch LLM step input exceeds configured limit"
                    )
                input_name = f"llm-step-{index:02d}-{phase or 'unknown'}-input.jsonl"
                self._write_text(case_dir / input_name, input_jsonl)
                output_files.append(input_name)
            metadata.append(
                {
                    key: value
                    for key, value in step.items()
                    if key not in {"rawOutput", "inputMessages"}
                }
                | {
                    "inputFile": input_name,
                    "inputBytes": input_bytes,
                    "outputFile": output_name,
                    "outputBytes": len(raw_output.encode("utf-8")),
                }
            )
        self._write_json(case_dir / "llm-steps.json", {"steps": metadata})
        return output_files

    @staticmethod
    def _encoded_json_size(value: dict[str, Any]) -> int:
        return len(json.dumps(value, ensure_ascii=False, separators=(",", ":")).encode("utf-8"))

    @staticmethod
    def _validate_identifier(value: str, field_name: str) -> None:
        if not IDENTIFIER_RE.fullmatch(value):
            raise ValueError(f"{field_name} contains unsupported characters or length")

    def _batch_dir(self, batch_id: str) -> Path:
        return self.root / batch_id

    def _require_enabled(self) -> None:
        if not self.enabled:
            raise WidgetBatchRecordingDisabledError("widget batch recording is disabled")

    @staticmethod
    def _ensure_private_dir(path: Path) -> None:
        path.mkdir(parents=True, exist_ok=True, mode=0o700)
        path.chmod(0o700)

    @staticmethod
    def _read_json(path: Path) -> dict[str, Any]:
        value = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(value, dict):
            raise json.JSONDecodeError("JSON root must be an object", str(value), 0)
        return value

    @staticmethod
    def _write_json(path: Path, value: dict[str, Any]) -> None:
        content = json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
        WidgetBatchStore._write_text(path, content)

    @staticmethod
    def _write_text(path: Path, content: str) -> None:
        temp_path = path.with_name(f".{path.name}.{uuid.uuid4().hex}.tmp")
        try:
            temp_path.write_text(content, encoding="utf-8")
            temp_path.chmod(0o600)
            os.replace(temp_path, path)
        finally:
            temp_path.unlink(missing_ok=True)


def utc_now() -> str:
    """返回带时区的 UTC ISO 时间。"""
    return datetime.now(UTC).isoformat()
