"""vendored search 模块加载器。

把 ``widget_service/vendor_search/`` 加入 ``sys.path`` 并导入 ``search`` 包与
``api_schema`` 模块。被拷贝代码保持字节不变，任何导入失败（如 jieba 缺失、
文件缺失）都记录到 :data:`_IMPORT_ERROR`，由 adapter 统一优雅降级为 miss，
不阻断服务启动。
"""

from __future__ import annotations

import sys
from pathlib import Path

# vendor_search 根目录：widget_service/vendor_search（无 __init__.py，纯 sys.path 容器）
VENDOR_ROOT = Path(__file__).resolve().parents[2] / "vendor_search"

# 由 _load() 填充；不可用时保持 None。
search = None
api_schema = None
search_template = None
get_default_search_service = None

_IMPORT_ERROR: str | None = None


def _install_vendor_path() -> None:
    """把 vendor_search 插入 sys.path（cloud 之后），不重复插入。"""
    vendor = str(VENDOR_ROOT)
    if vendor in sys.path:
        return
    cloud_root = str(Path(__file__).resolve().parents[1])
    if cloud_root in sys.path:
        sys.path.insert(sys.path.index(cloud_root) + 1, vendor)
    else:
        sys.path.insert(0, vendor)


def _load() -> None:
    """导入 vendored 模块；失败时记录原因并置 None。"""
    global search, api_schema, search_template, get_default_search_service
    global _IMPORT_ERROR
    try:
        _install_vendor_path()
        import api_schema
        import search
        from search.retriever import get_default_search_service, search_template
    except Exception as exc:
        _IMPORT_ERROR = f"{type(exc).__name__}: {exc}"
        return
    _IMPORT_ERROR = None


_load()


def search_available() -> bool:
    """vendored search 是否可导入。"""
    return _IMPORT_ERROR is None


def import_error() -> str | None:
    """返回导入失败原因（可导入时为 None）。"""
    return _IMPORT_ERROR
