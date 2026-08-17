"""防沉迷：应用使用时长和管控动作。"""

from pydantic import BaseModel, Field

from models.generation import TaskSpec

from ...component_registry import ComponentPlugin, register_component
from ...models import ActionRef, BindingRef, ComponentSpec, DataShape
from ..a2ui_base import rows_to_a2ui
from ..base import binding, event_handler, root_props
from ..scene_helpers import asset_src, field_by_terms, first_action, first_asset_id, ref


class Invocation(BaseModel):
    app_name: BindingRef = Field(description="应用名称文本绑定。")
    duration: BindingRef = Field(description="应用使用时长文本绑定，允许自带小时/分钟单位。")
    app_icon: str = Field(description="必须填写 assetCandidates 中的应用图标资源 id。")
    timing_icon: str = Field(description="必须填写 assetCandidates 中的计时图标资源 id。")
    action: ActionRef = Field(description="家长管控动作，event_id 必须来自 eventCandidates。")


SPEC = ComponentSpec(
    component_id="usage-summary-action",
    description="名称、使用量摘要和一个横向主要操作。",
    slots=["对象名称", "使用时长或用量", "状态摘要", "一个横向主要操作"],
    supported_sizes=["2x2"],
    required_signals={"action": 1.0},
    domains=["digital-wellbeing"],
    scenarios=["usage-control"],
    content_semantics=["app-usage", "duration"],
    action_semantics=["manage-usage"],
    layout_archetypes=["usage-summary-action"],
    temporalities=["now", "historical"],
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
            "backgroundColor": "#FFF5F8FF",
            "linearGradient": {
                "direction": "Bottom",
                "colors": [["#FFEAF2FF", 0], ["#FFFFFFFF", 1]],
            },
            "justifyContent": "spaceBetween",
        }
    )
    return [
        ["root", "Column", root, ["header", "duration", "action"]],
        [
            "header",
            "Row",
            {"alignItems": "center", "itemMargin": 5},
            ["app-icon", "app-name", "timing-icon"],
        ],
        [
            "app-icon",
            "Image",
            {
                "src": asset_src(invocation.app_icon, task_spec),
                "width": 18,
                "height": 18,
                "objectFit": "contain",
            },
        ],
        [
            "app-name",
            "Text",
            {
                "content": binding(invocation.app_name),
                "fontSize": 14,
                "fontColor": "#FF30343B",
                "layoutWeight": 1,
                "maxLines": 1,
            },
        ],
        [
            "timing-icon",
            "Image",
            {
                "src": asset_src(invocation.timing_icon, task_spec),
                "width": 18,
                "height": 18,
                "objectFit": "contain",
            },
        ],
        [
            "duration",
            "Text",
            {
                "content": binding(invocation.duration),
                "fontSize": 34,
                "fontWeight": 700,
                "fontColor": "#FF111317",
                "maxLines": 1,
            },
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
                "backgroundColor": "#FFDDE9FF",
                "fontColor": "#FF1266D6",
            },
        ],
    ]


def build_a2ui(invocation: Invocation, tokens: dict[str, object], task_spec: TaskSpec) -> str:
    return rows_to_a2ui(build_rows(invocation, tokens, task_spec), task_spec)


def map_offline(task_spec: TaskSpec, data_shape: DataShape) -> Invocation:
    return Invocation(
        app_name=ref(field_by_terms(data_shape, "appname", "应用", numeric=False)),
        duration=ref(field_by_terms(data_shape, "duration", "时长", numeric=None)),
        app_icon=first_asset_id(task_spec, "tiktok", "应用"),
        timing_icon=first_asset_id(task_spec, "timing", "计时"),
        action=first_action(task_spec, "管控时间"),
    )


def validate(invocation: Invocation, task_spec: TaskSpec) -> None:
    asset_src(invocation.app_icon, task_spec)
    asset_src(invocation.timing_icon, task_spec)


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
