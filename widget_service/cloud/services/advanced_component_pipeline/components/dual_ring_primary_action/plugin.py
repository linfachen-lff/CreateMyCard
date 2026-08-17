"""内存清理：双环形占用指标和一键清理动作。"""

from pydantic import BaseModel, Field

from models.generation import TaskSpec

from ...component_registry import ComponentPlugin, register_component
from ...models import ActionRef, BindingRef, ComponentSpec, DataShape
from ..a2ui_base import rows_to_a2ui
from ..base import binding, event_handler, root_props, validate_numeric_paths
from ..scene_helpers import asset_src, field_by_terms, first_action, first_asset_id, ref


class Invocation(BaseModel):
    status_text: str = Field(default="内存不足", description="顶部简短状态文案。")
    primary_value: BindingRef = Field(description="左侧主要占用百分比数值绑定。")
    secondary_value: BindingRef = Field(description="右侧次要占用百分比数值绑定。")
    primary_icon: str = Field(description="必须填写 assetCandidates 中的内存资源 id。")
    secondary_icon: str = Field(description="必须填写 assetCandidates 中的设备资源 id。")
    action: ActionRef = Field(description="清理动作，event_id 必须来自 eventCandidates。")


SPEC = ComponentSpec(
    component_id="dual-ring-primary-action",
    description="两个环形百分比指标和一个横向主要操作。",
    slots=["两个独立百分比数值", "两个环形进度及中心图片", "一个横向主要操作"],
    supported_sizes=["2x2"],
    required_signals={"action": 1.0},
    domains=["device"],
    scenarios=["memory-cleanup"],
    status_semantics=["warning"],
    content_semantics=["memory-usage", "storage-usage", "percentage"],
    action_semantics=["clean-memory"],
    layout_archetypes=["dual-ring-primary-action"],
    temporalities=["now"],
    min_semantic_score=8.0,
    min_fields=2,
    min_assets=2,
    min_actions=1,
)


def _metric_rows(
    prefix: str,
    value: BindingRef,
    icon_id: str,
    color: str,
    task_spec: TaskSpec,
) -> list[list[object]]:
    return [
        [
            prefix,
            "Column",
            {"alignItems": "center", "itemMargin": 3},
            [f"{prefix}-stack", f"{prefix}-value"],
        ],
        [
            f"{prefix}-stack",
            "Stack",
            {"width": 52, "height": 52, "alignContent": "center"},
            [f"{prefix}-progress", f"{prefix}-icon"],
        ],
        [
            f"{prefix}-progress",
            "Progress",
            {
                "value": binding(value),
                "total": 100,
                "type": "ring",
                "width": 50,
                "height": 50,
                "strokeWidth": 6,
                "color": color,
            },
        ],
        [
            f"{prefix}-icon",
            "Image",
            {
                "src": asset_src(icon_id, task_spec),
                "width": 20,
                "height": 20,
                "objectFit": "contain",
            },
        ],
        [
            f"{prefix}-value",
            "Row",
            {"alignItems": "center"},
            [f"{prefix}-number", f"{prefix}-unit"],
        ],
        [
            f"{prefix}-number",
            "Text",
            {
                "content": binding(value),
                "fontSize": 12,
                "fontWeight": 600,
                "fontColor": "#FF202124",
            },
        ],
        [
            f"{prefix}-unit",
            "Text",
            {
                "content": "%",
                "fontSize": 12,
                "fontWeight": 600,
                "fontColor": "#FF202124",
            },
        ],
    ]


def build_rows(invocation: Invocation, tokens: dict[str, object], task_spec: TaskSpec):
    root = root_props(tokens)
    root.update(
        {
            "padding": 12,
            "backgroundColor": "#FFFFFFFF",
            "linearGradient": {
                "direction": "Bottom",
                "colors": [["#FFFFFFFF", 0], ["#FFF8FAFD", 1]],
            },
            "justifyContent": "spaceBetween",
        }
    )
    rows = [
        ["root", "Column", root, ["status", "metrics", "action"]],
        [
            "status",
            "Text",
            {"content": invocation.status_text, "fontSize": 14, "fontColor": "#FF777980"},
        ],
        [
            "metrics",
            "Row",
            {"justifyContent": "spaceAround", "alignItems": "center"},
            ["primary", "secondary"],
        ],
        [
            "action",
            "Button",
            {
                "label": invocation.action.label,
                "onClick": event_handler(invocation.action, task_spec),
                "width": "matchParent",
                "height": 36,
                "borderRadius": 18,
                "backgroundColor": "#FFE4F0FF",
                "fontColor": "#FF087CFF",
                "fontSize": 14,
                "fontWeight": 600,
            },
        ],
    ]
    rows.extend(
        _metric_rows(
            "primary",
            invocation.primary_value,
            invocation.primary_icon,
            "#FFFF9800",
            task_spec,
        )
    )
    rows.extend(
        _metric_rows(
            "secondary",
            invocation.secondary_value,
            invocation.secondary_icon,
            "#FF35C765",
            task_spec,
        )
    )
    return rows


def build_a2ui(invocation: Invocation, tokens: dict[str, object], task_spec: TaskSpec) -> str:
    return rows_to_a2ui(build_rows(invocation, tokens, task_spec), task_spec)


def map_offline(task_spec: TaskSpec, data_shape: DataShape) -> Invocation:
    return Invocation(
        primary_value=ref(field_by_terms(data_shape, "memory", "内存", numeric=True)),
        secondary_value=ref(
            field_by_terms(
                data_shape, "storage", "available", "设备", numeric=True, fallback_index=1
            )
        ),
        primary_icon=first_asset_id(task_spec, "memory", "内存"),
        secondary_icon=first_asset_id(task_spec, "storage", "device", "设备"),
        action=first_action(task_spec, "一键清理"),
    )


def validate(invocation: Invocation, task_spec: TaskSpec) -> None:
    validate_numeric_paths(
        [invocation.primary_value.path, invocation.secondary_value.path], task_spec
    )
    asset_src(invocation.primary_icon, task_spec)
    asset_src(invocation.secondary_icon, task_spec)


PLUGIN = register_component(
    ComponentPlugin(
        component_id=SPEC.component_id,
        spec=SPEC,
        invocation_model=Invocation,
        build_rows=build_rows,
        build_a2ui=build_a2ui,
        map_offline=map_offline,
        validate=validate,
    )
)

__all__ = ["Invocation", "PLUGIN", "build_a2ui", "build_rows"]
