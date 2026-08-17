"""睡眠监测：小时、分钟双主指标和提醒动作。"""

from pydantic import BaseModel, Field

from models.generation import TaskSpec

from ...component_registry import ComponentPlugin, register_component
from ...models import ActionRef, BindingRef, ComponentSpec, DataShape
from ..a2ui_base import rows_to_a2ui
from ..base import binding, event_handler, root_props
from ..scene_helpers import asset_src, field_by_terms, first_action, first_asset_id, ref


class Invocation(BaseModel):
    title: str = Field(default="睡眠时长", description="顶部简短标题。")
    hours: BindingRef = Field(description="睡眠小时数或包含小时的主展示字段。")
    minutes: BindingRef = Field(description="睡眠分钟数或包含分钟的次展示字段。")
    reminder_icon: str = Field(description="必须填写 assetCandidates 中的闹钟资源 id。")
    action: ActionRef = Field(description="早睡提醒动作，event_id 必须来自 eventCandidates。")


SPEC = ComponentSpec(
    component_id="dual-duration-action",
    description="两个时长数字和一个主要操作。",
    slots=["状态摘要", "两个并列的时长或数值指标", "一个主要操作"],
    supported_sizes=["2x2"],
    required_signals={"action": 1.0},
    domains=["health"],
    scenarios=["sleep-summary"],
    status_semantics=["sleep-quality"],
    content_semantics=["duration", "status"],
    action_semantics=["remind-sleep", "open-details"],
    layout_archetypes=["dual-duration-action"],
    temporalities=["now", "historical"],
    min_semantic_score=8.0,
    min_fields=2,
    min_assets=1,
    min_actions=1,
)


def build_rows(invocation: Invocation, tokens: dict[str, object], task_spec: TaskSpec):
    root = root_props(tokens)
    root.update({"padding": 12, "itemMargin": 8, "justifyContent": "spaceBetween"})
    return [
        ["root", "Column", root, ["title", "duration", "action-row"]],
        [
            "title",
            "Text",
            {"content": invocation.title, "fontSize": 14, "fontColor": tokens["secondary"]},
        ],
        [
            "duration",
            "Row",
            {"alignItems": "end", "itemMargin": 3},
            ["hours", "hours-unit", "minutes", "minutes-unit"],
        ],
        [
            "hours",
            "Text",
            {
                "content": binding(invocation.hours),
                "fontSize": 34,
                "fontWeight": 700,
                "fontColor": tokens["primary"],
            },
        ],
        [
            "hours-unit",
            "Text",
            {"content": "小时", "fontSize": 12, "fontColor": tokens["secondary"]},
        ],
        [
            "minutes",
            "Text",
            {
                "content": binding(invocation.minutes),
                "fontSize": 34,
                "fontWeight": 700,
                "fontColor": tokens["primary"],
            },
        ],
        [
            "minutes-unit",
            "Text",
            {"content": "分钟", "fontSize": 12, "fontColor": tokens["secondary"]},
        ],
        [
            "action-row",
            "Row",
            {
                "width": "matchParent",
                "height": 36,
                "borderRadius": 18,
                "backgroundColor": "#F2FFFFFF",
                "alignItems": "center",
                "justifyContent": "center",
                "itemMargin": 6,
            },
            ["reminder-icon", "action"],
        ],
        [
            "reminder-icon",
            "Image",
            {
                "src": asset_src(invocation.reminder_icon, task_spec),
                "width": 18,
                "height": 18,
                "objectFit": "contain",
            },
        ],
        [
            "action",
            "Button",
            {
                "label": invocation.action.label,
                "onClick": event_handler(invocation.action, task_spec),
                "height": 32,
                "backgroundColor": "#00FFFFFF",
                "fontColor": tokens["accent"],
            },
        ],
    ]


def build_a2ui(invocation: Invocation, tokens: dict[str, object], task_spec: TaskSpec) -> str:
    return rows_to_a2ui(build_rows(invocation, tokens, task_spec), task_spec)


def map_offline(task_spec: TaskSpec, data_shape: DataShape) -> Invocation:
    return Invocation(
        hours=ref(field_by_terms(data_shape, "hour", "小时", numeric=None)),
        minutes=ref(field_by_terms(data_shape, "minute", "分钟", numeric=None, fallback_index=1)),
        reminder_icon=first_asset_id(task_spec, "alarm", "闹钟"),
        action=first_action(task_spec, "早睡提醒"),
    )


def validate(invocation: Invocation, task_spec: TaskSpec) -> None:
    asset_src(invocation.reminder_icon, task_spec)


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
