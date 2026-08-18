"""从 ``card-template/cards`` 的 artifact md 构建 search 模板库。

直接运行（无需任何参数，默认读取本目录 ``cards/``，输出到
``widget_service/vendor_search/search/data/templates.sqlite3``）：

    py -3.12 build_db.py

每个 ``q*_artifact.md`` 含 cardspec / genui / schema / taskspec / effectivecapabilities /
removedcapabilities / generationplan / meta / designcompactdsl 九个 fenced block。
本脚本取 ``taskspec.dataModelSchema``（降维为 sampleValue 实例）作为 input_json、
``designcompactdsl``（去掉 data 行）作为 reference_jsonl，经 vendored search 校验后入库。

依赖：jieba；vendored search 模块（``widget_service/vendor_search/``）。
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any

# 让 vendored search 包可导入（保持自包含，不依赖 cloud/search_integration）
REPO_ROOT = Path(__file__).resolve().parents[1]
VENDOR_SEARCH = REPO_ROOT / "widget_service" / "vendor_search"
if str(VENDOR_SEARCH) not in sys.path:
    sys.path.insert(0, str(VENDOR_SEARCH))

from search.hashing import compute_shape_signature  # noqa: E402
from search.repository import SQLiteTemplateDAO, TemplateRecord  # noqa: E402
from search.validation import bind_template, validate_template  # noqa: E402

_OPEN_FENCE_RE = re.compile(r"^```(\w+)\s*$")


def deflate_data_model_schema(schema: Any) -> Any:
    """把 dataModelSchema 叶子 ``{type, description, sampleValue}`` 降维为 sampleValue。

    与 ``widget_service/cloud/search_integration/deflate.py`` 保持一致。
    """
    if isinstance(schema, dict):
        if "sampleValue" in schema:
            return schema["sampleValue"]
        return {key: deflate_data_model_schema(value) for key, value in schema.items()}
    if isinstance(schema, list):
        return [deflate_data_model_schema(item) for item in schema]
    return schema


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


def _safe_tokenize(text: str) -> list[str]:
    try:
        from search.tokenization import tokenize

        return tokenize(text)
    except Exception:  # noqa: BLE001 - 分词失败时退化为空标签
        return []


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


def build_template_record(parsed: dict, template_id: str) -> TemplateRecord:
    """从解析块构建一条 TemplateRecord；reference 结构非法时抛异常。"""
    cardspec = json.loads(parsed["cardspec"])
    taskspec = json.loads(parsed["taskspec"])
    generationplan = json.loads(parsed["generationplan"])
    design_dsl = parsed["designcompactdsl"]

    schema = taskspec.get("dataModelSchema")
    if not isinstance(schema, dict):
        raise ValueError("taskspec.dataModelSchema must be an object")
    input_payload = deflate_data_model_schema(schema)
    reference_jsonl = reference_from_design_dsl(design_dsl)

    validate_template(reference_jsonl, mode="reference")
    signature = compute_shape_signature(input_payload)
    description, tags = derive_metadata(cardspec, taskspec, generationplan)
    size = cardspec.get("suggestSize") or None
    return TemplateRecord(
        template_id=template_id,
        description=description,
        tags=tuple(tags),
        reference_jsonl=reference_jsonl,
        input_json=json.dumps(input_payload, ensure_ascii=False),
        structure_hash=signature.signature,
        signature_version=signature.version,
        size=size if isinstance(size, str) else None,
    )


def _bind_check(reference_jsonl: str, input_payload: dict, template_id: str) -> str | None:
    """软门禁：用自身样例数据试渲染；失败仅记录，模板仍可作 keyword_match 使用。"""
    try:
        bind_template(reference_jsonl, input_payload)
    except Exception as exc:  # noqa: BLE001 - 绑定失败仅告警
        return f"{template_id}: bind check failed: {exc}"
    return None


def main() -> None:
    parser = argparse.ArgumentParser(
        description="build search template db from card-template artifact md"
    )
    parser.add_argument(
        "--source",
        default=str(Path(__file__).resolve().parent / "cards"),
        help="卡片 artifact md 目录（默认本目录 cards/）",
    )
    parser.add_argument(
        "--db",
        default=str(REPO_ROOT / "widget_service" / "vendor_search" / "search" / "data" / "templates.sqlite3"),
        help="输出 sqlite3 路径",
    )
    parser.add_argument("--replace", action="store_true", help="覆盖已有模板")
    args = parser.parse_args()

    dao = SQLiteTemplateDAO(args.db)
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
