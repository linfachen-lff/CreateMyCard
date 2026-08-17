"""日程管家：日期、会议详情、地点和加入动作。"""

from pydantic import BaseModel, Field

from models.generation import TaskSpec

from ...component_registry import ComponentPlugin, register_component
from ...models import ActionRef, BindingRef, ComponentSpec, DataShape
from ..a2ui_base import rows_to_a2ui
from ..base import binding, event_handler, root_props
from ..scene_helpers import field_by_terms, first_action, ref


class Invocation(BaseModel):
    date_text: BindingRef = Field(description="日期短文本绑定，例如 27日。")
    weekday: BindingRef = Field(description="星期文本绑定。")
    event_title: BindingRef = Field(description="当前会议或日程标题绑定。")
    start_time: BindingRef = Field(description="开始时间文本绑定。")
    end_time: BindingRef = Field(description="结束时间文本绑定。")
    location: BindingRef = Field(description="会议地点短文本绑定。")
    action: ActionRef = Field(description="加入或查看会议动作，event_id 必须来自 eventCandidates。")


SPEC = ComponentSpec(
    component_id="timeline-event-action",
    description="日期、事项详情、时间地点和主要操作。",
    slots=["日期", "事项标题", "开始和结束时间", "地点详情", "一个主要操作"],
    supported_sizes=["2x2"],
    required_signals={"action": 1.0},
    domains=["schedule"],
    scenarios=["ongoing-event"],
    status_semantics=["active"],
    content_semantics=["event-title", "time-range", "location-detail"],
    action_semantics=["join-meeting"],
    layout_archetypes=["timeline-event-action"],
    temporalities=["now"],
    min_semantic_score=8.0,
    min_fields=5,
    required_field_roles={"time-start": 1, "time-end": 1},
    min_actions=1,
)


def build_rows(invocation: Invocation, tokens: dict[str, object], task_spec: TaskSpec):
    root = root_props(tokens)
    root.update(
        {
            "padding": 12,
            "backgroundColor": "#FFFFF8F6",
            "linearGradient": {
                "direction": "Bottom",
                "colors": [["#FFFFE7E3", 0], ["#FFFFFFFF", 1]],
            },
            "justifyContent": "spaceBetween",
        }
    )
    return [
        ["root", "Column", root, ["date-row", "event-row", "time", "location", "action"]],
        ["date-row", "Row", {"itemMargin": 5}, ["date", "weekday"]],
        [
            "date",
            "Text",
            {
                "content": binding(invocation.date_text),
                "fontSize": 14,
                "fontWeight": 700,
                "fontColor": "#FFFF2020",
            },
        ],
        [
            "weekday",
            "Text",
            {
                "content": binding(invocation.weekday),
                "fontSize": 14,
                "fontWeight": 600,
                "fontColor": "#FF202124",
            },
        ],
        ["event-row", "Row", {"alignItems": "center", "itemMargin": 6}, ["dot", "event"]],
        ["dot", "Text", {"content": "○", "fontSize": 18, "fontColor": "#FFFF2020"}],
        [
            "event",
            "Text",
            {
                "content": binding(invocation.event_title),
                "fontSize": 16,
                "fontWeight": 700,
                "fontColor": "#FF202124",
                "maxLines": 1,
                "layoutWeight": 1,
            },
        ],
        ["time", "Row", {"itemMargin": 3, "margin": {"left": 22}}, ["start", "separator", "end"]],
        [
            "start",
            "Text",
            {"content": binding(invocation.start_time), "fontSize": 12, "fontColor": "#FF777980"},
        ],
        ["separator", "Text", {"content": "-", "fontSize": 12, "fontColor": "#FF777980"}],
        [
            "end",
            "Text",
            {"content": binding(invocation.end_time), "fontSize": 12, "fontColor": "#FF777980"},
        ],
        [
            "location",
            "Text",
            {
                "content": binding(invocation.location),
                "fontSize": 11,
                "fontColor": "#FF8A8C92",
                "maxLines": 1,
                "margin": {"left": 22},
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
                "backgroundColor": "#FFFFDED9",
                "fontColor": "#FFFF2020",
            },
        ],
    ]


def build_a2ui(invocation: Invocation, tokens: dict[str, object], task_spec: TaskSpec) -> str:
    return rows_to_a2ui(build_rows(invocation, tokens, task_spec), task_spec)


def map_offline(task_spec: TaskSpec, data_shape: DataShape) -> Invocation:
    return Invocation(
        date_text=ref(field_by_terms(data_shape, "date", "日期", numeric=False)),
        weekday=ref(field_by_terms(data_shape, "weekday", "星期", numeric=False)),
        event_title=ref(field_by_terms(data_shape, "title", "会议", numeric=False)),
        start_time=ref(field_by_terms(data_shape, "start", "开始", numeric=False)),
        end_time=ref(field_by_terms(data_shape, "end", "结束", numeric=False)),
        location=ref(field_by_terms(data_shape, "location", "地点", numeric=False)),
        action=first_action(task_spec, "加入会议"),
    )


def validate(invocation: Invocation, task_spec: TaskSpec) -> None:
    return None


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
