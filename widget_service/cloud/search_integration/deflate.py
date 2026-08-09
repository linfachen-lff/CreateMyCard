"""dataModelSchema 降维工具。

CreateMyCard 的 TaskSpec.dataModelSchema 叶子是 ``{type, description, sampleValue}``
元数据结构，而 search 模块的 structure_hash / bind_template 期望的是「纯数据实例」
（叶子为标量）。本模块把 dataModelSchema 递归降维为 sampleValue 实例，
建库（build_db）与运行时（adapter）共用同一实现，保证两侧结构一致。
"""

from __future__ import annotations

from typing import Any


def deflate_data_model_schema(schema: Any) -> Any:
    """把 dataModelSchema 叶子 ``{type, description, sampleValue}`` 降维为 sampleValue。

    - dict 含 ``sampleValue`` 键 → 直接取 sampleValue（叶子元数据形态）；
    - dict → 对每个值递归；
    - list → 对每个元素递归；
    - 其他标量 → 原样返回。
    """
    if isinstance(schema, dict):
        if "sampleValue" in schema:
            return schema["sampleValue"]
        return {key: deflate_data_model_schema(value) for key, value in schema.items()}
    if isinstance(schema, list):
        return [deflate_data_model_schema(item) for item in schema]
    return schema
