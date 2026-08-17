"""TerseDSL-Nested-2 的高级组件生成流水线。

该包只服务于 ``generateWidgetCardTerseDslNested2``。它与既有的通用 DSL
生成链路隔离，未选中高级组件时由调用方继续使用原有 Terse 生成流程。
"""

__all__ = ["AdvancedComponentPipeline", "build_terse_nested2"]


def __getattr__(name: str):
    """延迟加载，避免 Registry 读取严格模型时形成包级循环依赖。"""
    if name == "AdvancedComponentPipeline":
        from .pipeline import AdvancedComponentPipeline

        return AdvancedComponentPipeline
    if name == "build_terse_nested2":
        from .compiler import build_terse_nested2

        return build_terse_nested2
    raise AttributeError(name)
