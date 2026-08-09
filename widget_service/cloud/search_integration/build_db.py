"""从 ``subagent_genui/taskspec/md`` 的 artifact 产物构建 search 模板库。

用法（在 widget_service 目录下）：

    py -3.12 -m cloud.search_integration.build_db \
        --source D:/Program/work/subagent_genui/taskspec/md \
        --db vendor_search/search/data/templates.sqlite3 --replace

每个 ``q*_artifact.md`` 含 cardspec / genui / schema / taskspec / effectivecapabilities /
removedcapabilities / generationplan / meta / designcompactdsl 九个 fenced block。
本脚本取其 ``taskspec.dataModelSchema``（降维为 sampleValue 实例）作为 input_json、
``designcompactdsl``（去掉 data 行）作为 reference_jsonl，经 search 校验后入库。
"""

from __future__ import annotations

import argparse
import json
import logging
import re
from pathlib import Path
from typing import Any

from . import vendored_loader
from .deflate import deflate_data_model_schema

logger = logging.getLogger(__name__)

_OPEN_FENCE_RE = re.compile(r"^```(\w+)\s*$")


def parse_artifact_md(path: Path) -> dict[str, str]:
    """解析 q*_artifact.md，返回 {block_name: 块内原始文本}。"""
    blocks: dict[str, str] = {}
    current: str | None = None
    buffer: list[str] = []
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        open_match = _OPEN_FENCE_RE.match(raw_line)
        if open_match:
            if current is not None:
                blocks[current] = "\n".join(buffer)
            current = open_match.group(1)
            buffer = []
            continue
        if raw_line.strip() == "```":
            if current is not None:
                blocks[current] = "\n".join(buffer)
            current = None
            buffer = []
            continue
        if current is not None:
            buffer.append(raw_line)
    if current is not None:
        blocks[current] = "\n".join(buffer)
    return blocks


def reference_from_design_dsl(design_dsl: str) -> str:
    """去掉 data 行（首元素是 ``/`` 开头的路径），得到无数据的 reference 骨架。"""
    component_lines = [
        line
        for line in design_dsl.strip().splitlines()
        if line.strip() and not line.strip().startswith('["/')
    ]
    return "\n".join(component_lines)


def derive_metadata(cardspec: dict, taskspec: dict, generationplan: dict) -> tuple[str, list[str]]:
    """从产物派生 description 与 tags。

    description 用 cardspec.description；tags 用 capabilityId + userQuery 分词。
    """
    description = str(cardspec.get("description") or "")
    capability_ids = [
        str(binding.get("capabilityId"))
        for binding in (generationplan.get("candidateDataBindings") or [])
        if binding.get("capabilityId")
    ]
    user_query = str(taskspec.get("userQuery") or "")
    tokens = _safe_tokenize(user_query)
    tags = list(dict.fromkeys([*capability_ids, *tokens]))
    return description, tags


def _safe_tokenize(text: str) -> list[str]:
    try:
        from search.tokenization import tokenize

        return tokenize(text)
    except Exception:  # noqa: BLE001 - 分词失败时退化为空标签
        return []


def build_template_record(parsed: dict, template_id: str) -> Any:
    """从解析块构建一条 TemplateRecord；reference 结构非法时抛异常。"""
    if not vendored_loader.search_available():
        raise RuntimeError(f"vendored search 不可用: {vendored_loader.import_error()}")
    search = vendored_loader.search
    cardspec = json.loads(parsed["cardspec"])
    taskspec = json.loads(parsed["taskspec"])
    generationplan = json.loads(parsed["generationplan"])
    design_dsl = parsed["designcompactdsl"]

    schema = taskspec.get("dataModelSchema")
    if not isinstance(schema, dict):
        raise ValueError("taskspec.dataModelSchema must be an object")
    input_payload = deflate_data_model_schema(schema)
    reference_jsonl = reference_from_design_dsl(design_dsl)

    from search.validation import validate_template

    validate_template(reference_jsonl, mode="reference")
    signature = search.compute_shape_signature(input_payload)
    description, tags = derive_metadata(cardspec, taskspec, generationplan)
    return search.TemplateRecord(
        template_id=template_id,
        description=description,
        tags=tuple(tags),
        reference_jsonl=reference_jsonl,
        input_json=json.dumps(input_payload, ensure_ascii=False),
        structure_hash=signature.signature,
        signature_version=signature.version,
    )


def _bind_check(reference_jsonl: str, input_payload: dict, template_id: str) -> str | None:
    """软门禁：用自身样例数据试渲染；失败仅记录，模板仍可作 keyword_match 使用。"""
    try:
        from search.validation import bind_template

        bind_template(reference_jsonl, input_payload)
    except Exception as exc:  # noqa: BLE001 - 绑定失败仅告警
        return f"{template_id}: bind check failed: {exc}"
    return None


def main() -> None:
    parser = argparse.ArgumentParser(description="build search template db from artifact md")
    parser.add_argument("--source", required=True, help="taskspec/md 目录")
    parser.add_argument("--db", required=True, help="输出 sqlite3 路径")
    parser.add_argument("--replace", action="store_true", help="覆盖已有模板")
    args = parser.parse_args()

    if not vendored_loader.search_available():
        raise SystemExit(f"vendored search 不可用: {vendored_loader.import_error()}")
    search = vendored_loader.search
    dao = search.SQLiteTemplateDAO(args.db)
    dao.initialize()

    records = []
    skipped: list[str] = []
    bind_warnings: list[str] = []
    for path in sorted(Path(args.source).glob("q*_artifact.md")):
        template_id = path.stem.split("_")[0]
        try:
            parsed = parse_artifact_md(path)
            record = build_template_record(parsed, template_id)
        except Exception as exc:  # noqa: BLE001 - 单文件失败不影响整体
            skipped.append(f"{path.name}: {exc}")
            print(f"SKIP {path.name}: {exc}")
            continue
        input_payload = json.loads(record.input_json)
        bind_warning = _bind_check(record.reference_jsonl, input_payload, template_id)
        if bind_warning:
            bind_warnings.append(bind_warning)
        records.append(record)
        print(f"OK   {path.name} -> {template_id}")

    if records:
        if args.replace:
            dao.replace_all(records)
        else:
            for record in records:
                dao.upsert(record)
    print(f"imported={len(records)} skipped={len(skipped)} total={dao.count()}")
    for warning in bind_warnings:
        print(f"WARN {warning}")


if __name__ == "__main__":
    main()
