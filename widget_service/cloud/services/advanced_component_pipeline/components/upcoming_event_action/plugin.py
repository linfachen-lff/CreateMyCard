"""专注模式：下一个日程、时间范围和专注动作。"""

from pydantic import BaseModel, Field

from models.generation import TaskSpec

from ...component_registry import ComponentPlugin, register_component
from ...models import ActionRef, BindingRef, ComponentSpec, DataShape
from ..a2ui_base import rows_to_a2ui
from ..base import binding, event_handler, root_props
from ..scene_helpers import asset_src, field_by_terms, first_action, first_asset_id, ref


class Invocation(BaseModel):
    event_title: BindingRef = Field(description="下一个日程或会议标题绑定。")
    start_time: BindingRef = Field(description="开始时间文本绑定。")
    end_time: BindingRef = Field(description="结束时间文本绑定。")
    meeting_icon: str = Field(description="必须填写 assetCandidates 中的会议资源 id。")
    action: ActionRef = Field(description="专注模式动作，event_id 必须来自 eventCandidates。")


SPEC = ComponentSpec(
    component_id="upcoming-event-action",
    description="下一个事项、时间范围和主要操作。",
    slots=["下一个事项标题", "开始和结束时间", "提醒摘要", "一个主要操作"],
    supported_sizes=["2x2"],
    required_signals={"action": 1.0},
    domains=["schedule", "productivity"],
    scenarios=["upcoming-event"],
    status_semantics=["do-not-disturb", "active"],
    content_semantics=["event-title", "time-range", "event-count"],
    action_semantics=["open-dnd-settings", "enable-focus"],
    layout_archetypes=["upcoming-event-action"],
    temporalities=["upcoming"],
    min_semantic_score=8.0,
    min_fields=3,
    required_field_roles={"time-start": 1, "time-end": 1},
    min_assets=1,
    min_actions=1,
)


def build_rows(invocation: Invocation, tokens: dict[str, object], task_spec: TaskSpec):
    root = root_props(tokens)
    root.update(
        {
            "padding": 12,
            "backgroundColor": "#FFF4F8FF",
            "linearGradient": {
                "direction": "Bottom",
                "colors": [["#FFE6F0FF", 0], ["#FFFFFFFF", 1]],
            },
            "justifyContent": "spaceBetween",
        }
    )
    return [
        ["root", "Column", root, ["header", "event", "time", "action"]],
        ["header", "Row", {"alignItems": "center"}, ["caption", "meeting-icon"]],
        [
            "caption",
            "Text",
            {"content": "下一个日程", "fontSize": 14, "fontColor": "#FF666A73", "layoutWeight": 1},
        ],
        [
            "meeting-icon",
            "Image",
            {
                "src": asset_src(invocation.meeting_icon, task_spec),
                "width": 20,
                "height": 20,
                "objectFit": "contain",
            },
        ],
        [
            "event",
            "Text",
            {
                "content": binding(invocation.event_title),
                "fontSize": 22,
                "fontWeight": 700,
                "fontColor": "#FF111317",
                "maxLines": 1,
                "textOverflow": "ellipsis",
            },
        ],
        ["time", "Row", {"itemMargin": 3}, ["start", "separator", "end"]],
        [
            "start",
            "Text",
            {"content": binding(invocation.start_time), "fontSize": 13, "fontColor": "#FF555A64"},
        ],
        ["separator", "Text", {"content": "-", "fontSize": 13, "fontColor": "#FF555A64"}],
        [
            "end",
            "Text",
            {"content": binding(invocation.end_time), "fontSize": 13, "fontColor": "#FF555A64"},
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
        event_title=ref(field_by_terms(data_shape, "title", "会议", numeric=False)),
        start_time=ref(field_by_terms(data_shape, "start", "开始", numeric=False)),
        end_time=ref(field_by_terms(data_shape, "end", "结束", numeric=False)),
        meeting_icon=first_asset_id(task_spec, "meeting", "会议"),
        action=first_action(task_spec, "专注模式"),
    )


def validate(invocation: Invocation, task_spec: TaskSpec) -> None:
    asset_src(invocation.meeting_icon, task_spec)


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
