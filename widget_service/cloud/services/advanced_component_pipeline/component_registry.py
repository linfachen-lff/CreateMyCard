"""高级组件插件注册、自动发现和查询。"""

from __future__ import annotations

import importlib
import pkgutil
from collections.abc import Callable
from dataclasses import dataclass

from pydantic import BaseModel

from models.generation import TaskSpec

from .models import ComponentSpec, DataShape


@dataclass(frozen=True)
class ComponentPlugin:
    """一个高级组件插件必须提供的完整能力。"""

    component_id: str
    spec: ComponentSpec
    invocation_model: type[BaseModel]
    build_rows: Callable[[BaseModel, dict[str, object], TaskSpec], list[list[object]]]
    build_a2ui: Callable[[BaseModel, dict[str, object], TaskSpec], str]
    map_offline: Callable[[TaskSpec, DataShape], BaseModel]
    validate: Callable[[BaseModel, TaskSpec], None]


_PLUGINS: dict[str, ComponentPlugin] = {}
_DISCOVERED = False


def register_component(plugin: ComponentPlugin) -> ComponentPlugin:
    """由组件目录在导入时注册自身。"""
    if plugin.component_id != plugin.spec.component_id:
        raise ValueError("component plugin id must match its spec")
    existing = _PLUGINS.get(plugin.component_id)
    if existing is not None and existing is not plugin:
        raise ValueError(f"duplicate advanced component: {plugin.component_id}")
    _PLUGINS[plugin.component_id] = plugin
    return plugin


def _discover_components() -> None:
    global _DISCOVERED
    if _DISCOVERED:
        return
    package = importlib.import_module(f"{__package__}.components")
    for module in pkgutil.iter_modules(package.__path__, package.__name__ + "."):
        if module.ispkg:
            importlib.import_module(module.name)
    _DISCOVERED = True


def component_plugins() -> tuple[ComponentPlugin, ...]:
    _discover_components()
    return tuple(_PLUGINS[key] for key in sorted(_PLUGINS))


def component_specs() -> tuple[ComponentSpec, ...]:
    return tuple(plugin.spec for plugin in component_plugins())


def get_component(component_id: str) -> ComponentPlugin:
    _discover_components()
    try:
        return _PLUGINS[component_id]
    except KeyError as exc:
        raise ValueError(f"unknown advanced component: {component_id}") from exc


def reset_component_registry_for_test() -> None:
    """仅用于测试隔离动态注册。"""
    global _DISCOVERED
    _PLUGINS.clear()
    _DISCOVERED = False


__all__ = [
    "ComponentPlugin",
    "component_plugins",
    "component_specs",
    "get_component",
    "register_component",
]
