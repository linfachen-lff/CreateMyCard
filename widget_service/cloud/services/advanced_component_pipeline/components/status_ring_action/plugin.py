"""设备电量：阈值提醒、环形电量和省电动作。"""

from pydantic import BaseModel, Field

from models.generation import TaskSpec

from ...component_registry import ComponentPlugin, register_component
from ...models import ActionRef, BindingRef, ComponentSpec, DataShape
from ..a2ui_base import rows_to_a2ui
from ..base import binding, event_handler, root_props
from ..scene_helpers import asset_src, field_by_terms, first_action, first_asset_id, ref


class Invocation(BaseModel):
    status_text: BindingRef = Field(description="低电量状态或省电建议文本绑定。")
    percentage: BindingRef = Field(
        description=(
            "电池百分比绑定。优先选择 number 或 integer 字段；若 TaskSpec 只提供"
            "已格式化的百分比字符串（例如 batterySOCText），允许直接绑定该字符串路径。"
        )
    )
    battery_icon: str = Field(description="必须填写 assetCandidates 中的电池资源 id。")
    action_icon: str = Field(description="必须填写 assetCandidates 中的省电资源 id。")
    action: ActionRef = Field(description="省电动作，event_id 必须来自 eventCandidates。")


SPEC = ComponentSpec(
    component_id="status-ring-action",
    description="状态摘要、单环形指标和圆形图片操作。",
    slots=["状态摘要", "一个百分比环形进度", "环形中心图片", "一个主要操作"],
    supported_sizes=["2x2"],
    required_signals={"action": 1.0},
    domains=["device"],
    scenarios=["low-power"],
    status_semantics=["low-power", "warning"],
    content_semantics=["battery-level", "percentage", "status"],
    action_semantics=["enable-power-saving"],
    layout_archetypes=["status-ring-action"],
    temporalities=["now"],
    min_semantic_score=8.0,
    min_fields=2,
    min_assets=1,
    min_actions=1,
)


def build_rows(invocation: Invocation, tokens: dict[str, object], task_spec: TaskSpec):
    root = root_props(tokens)
    root.update(
        {
            "padding": 12,
            "backgroundColor": "#FFFFFBF2",
            "linearGradient": {
                "direction": "Bottom",
                "colors": [["#FFFFF4DC", 0], ["#FFFFFFFF", 1]],
            },
            "justifyContent": "spaceBetween",
        }
    )
    return [
        ["root", "Column", root, ["title", "status", "bottom"]],
        [
            "title",
            "Text",
            {"content": "设备电量", "fontSize": 15, "fontWeight": 700, "fontColor": "#FF171717"},
        ],
        [
            "status",
            "Text",
            {
                "content": binding(invocation.status_text),
                "fontSize": 13,
                "fontColor": "#FF55565A",
                "maxLines": 2,
            },
        ],
        [
            "bottom",
            "Row",
            {"alignItems": "center", "justifyContent": "spaceBetween"},
            ["battery-stack", "action-wrap"],
        ],
        [
            "battery-stack",
            "Stack",
            {"width": 52, "height": 52, "alignContent": "center"},
            ["battery-progress", "battery-icon"],
        ],
        [
            "battery-progress",
            "Progress",
            {
                "value": binding(invocation.percentage),
                "total": 100,
                "type": "ring",
                "width": 50,
                "height": 50,
                "strokeWidth": 6,
                "color": "#FFFF8A00",
            },
        ],
        [
            "battery-icon",
            "Image",
            {
                "src": asset_src(invocation.battery_icon, task_spec),
                "width": 22,
                "height": 22,
                "objectFit": "contain",
            },
        ],
        [
            "action-wrap",
            "Stack",
            {"width": 44, "height": 44, "alignContent": "center"},
            ["action", "action-icon"],
        ],
        [
            "action",
            "Button",
            {
                "label": invocation.action.label,
                "onClick": event_handler(invocation.action, task_spec),
                "width": 44,
                "height": 44,
                "borderRadius": 22,
                "backgroundColor": "#FFE8E8E8",
                "fontColor": "#00222222",
                "fontSize": 1,
            },
        ],
        [
            "action-icon",
            "Image",
            {
                "src": asset_src(invocation.action_icon, task_spec),
                "width": 20,
                "height": 20,
                "objectFit": "contain",
            },
        ],
    ]


def build_a2ui(invocation: Invocation, tokens: dict[str, object], task_spec: TaskSpec) -> str:
    return rows_to_a2ui(build_rows(invocation, tokens, task_spec), task_spec)


def map_offline(task_spec: TaskSpec, data_shape: DataShape) -> Invocation:
    return Invocation(
        status_text=ref(field_by_terms(data_shape, "status", "状态", numeric=False)),
        percentage=ref(field_by_terms(data_shape, "percent", "soc", "电量", numeric=None)),
        battery_icon=first_asset_id(task_spec, "electricity", "电池"),
        action_icon=first_asset_id(task_spec, "save_power", "省电"),
        action=first_action(task_spec, "省电"),
    )


def validate(invocation: Invocation, task_spec: TaskSpec) -> None:
    asset_src(invocation.battery_icon, task_spec)
    asset_src(invocation.action_icon, task_spec)


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
