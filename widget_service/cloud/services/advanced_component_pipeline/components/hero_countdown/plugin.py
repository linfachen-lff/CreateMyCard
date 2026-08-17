"""赛事陪伴：赛事标题、倒计时和训练动作。"""

from pydantic import BaseModel, Field

from models.generation import TaskSpec

from ...component_registry import ComponentPlugin, register_component
from ...models import ActionRef, BindingRef, ComponentSpec, DataShape
from ..a2ui_base import rows_to_a2ui
from ..base import binding, event_handler, root_props, validate_numeric_paths
from ..scene_helpers import asset_src, field_by_terms, first_action, first_asset_id, ref


class Invocation(BaseModel):
    title: str = Field(description="从用户目标提炼的简短倒计时标题。", min_length=1)
    remaining_days: BindingRef = Field(description="剩余天数，必须绑定 number 或 integer 字段。")
    unit: str = Field(default="天剩余", description="倒计时数值后的短说明。")
    action_icon: str | None = Field(
        default=None,
        description="有操作时填写 assetCandidates 中的语义资源 id。",
    )
    action: ActionRef | None = Field(
        default=None,
        description="可选操作；event_id 必须来自 eventCandidates。",
    )


SPEC = ComponentSpec(
    component_id="hero-countdown",
    description="高饱和通用倒计时，可选显示主要操作。",
    slots=["静态短标题", "一个大号倒计时数值", "可选的一个主要操作"],
    supported_sizes=["2x2"],
    required_signals={},
    domains=["sports", "schedule", "productivity", "general"],
    scenarios=["race-countdown", "countdown"],
    content_semantics=["countdown", "event-title"],
    action_semantics=["open-event", "primary-action"],
    layout_archetypes=["hero-countdown"],
    temporalities=["upcoming"],
    min_semantic_score=8.0,
    min_fields=1,
    min_assets=0,
    min_actions=0,
)


def build_rows(invocation: Invocation, tokens: dict[str, object], task_spec: TaskSpec):
    root = root_props(tokens)
    root.update({"padding": 12, "itemMargin": 8, "justifyContent": "spaceBetween"})
    root_children = ["title", "hero"]
    rows = [
        ["root", "Column", root, root_children],
        [
            "title",
            "Text",
            {
                "content": invocation.title,
                "fontSize": 14,
                "fontColor": tokens["secondary"],
                "maxLines": 1,
            },
        ],
        ["hero", "Row", {"alignItems": "end", "itemMargin": 4}, ["days", "unit"]],
        [
            "days",
            "Text",
            {
                "content": binding(invocation.remaining_days),
                "fontSize": 40,
                "fontWeight": 700,
                "fontColor": tokens["primary"],
            },
        ],
        [
            "unit",
            "Text",
            {"content": invocation.unit, "fontSize": 13, "fontColor": tokens["secondary"]},
        ],
    ]
    if invocation.action is None:
        return rows
    root_children.append("action-row")
    action_children = ["action"]
    if invocation.action_icon is not None:
        action_children.insert(0, "action-icon")
    rows.extend(
        [
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
                action_children,
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
                    "fontSize": 13,
                },
            ],
        ]
    )
    if invocation.action_icon is not None:
        rows.append(
            [
                "action-icon",
                "Image",
                {
                    "src": asset_src(invocation.action_icon, task_spec),
                    "width": 18,
                    "height": 18,
                    "objectFit": "contain",
                },
            ]
        )
    return rows


def build_a2ui(invocation: Invocation, tokens: dict[str, object], task_spec: TaskSpec) -> str:
    return rows_to_a2ui(build_rows(invocation, tokens, task_spec), task_spec)


def map_offline(task_spec: TaskSpec, data_shape: DataShape) -> Invocation:
    has_action = any(item.id for item in task_spec.eventCandidates)
    return Invocation(
        title=task_spec.userQuery,
        remaining_days=ref(field_by_terms(data_shape, "days", "剩余", numeric=True)),
        action_icon=(first_asset_id(task_spec, "run", "运动") if has_action else None),
        action=(first_action(task_spec, "查看详情") if has_action else None),
    )


def validate(invocation: Invocation, task_spec: TaskSpec) -> None:
    validate_numeric_paths([invocation.remaining_days.path], task_spec)
    if invocation.action_icon is not None:
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
