"""单个大号主指标、状态摘要和快捷操作。"""

from pydantic import BaseModel, Field

from models.generation import TaskSpec

from ...component_registry import ComponentPlugin, register_component
from ...models import ActionRef, BindingRef, ComponentSpec, DataShape
from ..a2ui_base import rows_to_a2ui
from ..base import binding, event_handler, root_props
from ..scene_helpers import asset_src, field_by_terms, first_action, first_asset_id, ref


class Invocation(BaseModel):
    location: BindingRef = Field(description="城市或关怀对象所在地点的数据绑定。")
    temperature: BindingRef = Field(description="当前温度的大号主指标绑定。")
    condition: BindingRef = Field(description="当前天气状态文本绑定。")
    range_text: BindingRef = Field(description="今日最高/最低温度范围文本绑定。")
    location_icon: str | None = Field(
        default=None,
        description="可选的定位或天气资源 id；没有素材时仅显示地点文本。",
    )
    action: ActionRef = Field(description="关怀动作，event_id 必须来自 eventCandidates。")


SPEC = ComponentSpec(
    component_id="hero-metric-action",
    description="单个大号主指标、状态摘要和可选语义操作。",
    slots=["顶部短文本", "一个大号主指标", "两条状态摘要", "一个快捷操作"],
    supported_sizes=["2x2"],
    required_signals={"action": 1.0},
    domains=["weather"],
    scenarios=["family-care", "status-summary"],
    content_semantics=["location", "temperature", "status"],
    action_semantics=["call-contact", "open-details"],
    layout_archetypes=["hero-metric-action"],
    temporalities=["now"],
    min_semantic_score=8.0,
    min_fields=3,
    min_assets=0,
    min_actions=1,
)


def build_rows(invocation: Invocation, tokens: dict[str, object], task_spec: TaskSpec):
    root = root_props(tokens)
    root.update({"padding": 12, "itemMargin": 6, "justifyContent": "spaceBetween"})
    header_children = ["location"]
    if invocation.location_icon is not None:
        header_children.append("location-icon")
    rows = [
        ["root", "Column", root, ["header", "temperature", "condition", "footer"]],
        ["header", "Row", {"alignItems": "center"}, header_children],
        [
            "location",
            "Text",
            {
                "content": binding(invocation.location),
                "fontSize": 14,
                "fontColor": tokens["primary"],
                "layoutWeight": 1,
            },
        ],
        [
            "temperature",
            "Text",
            {
                "content": binding(invocation.temperature),
                "fontSize": 38,
                "fontWeight": 700,
                "fontColor": tokens["primary"],
            },
        ],
        [
            "condition",
            "Text",
            {
                "content": binding(invocation.condition),
                "fontSize": 13,
                "fontColor": tokens["primary"],
            },
        ],
        ["footer", "Row", {"alignItems": "center"}, ["range", "action"]],
        [
            "range",
            "Text",
            {
                "content": binding(invocation.range_text),
                "fontSize": 12,
                "fontColor": tokens["secondary"],
                "layoutWeight": 1,
            },
        ],
        [
            "action",
            "Button",
            {
                "label": invocation.action.label,
                "onClick": event_handler(invocation.action, task_spec),
                "width": 38,
                "height": 38,
                "borderRadius": 19,
                "backgroundColor": "#FFFFFFFF",
                "fontColor": tokens["accent"],
            },
        ],
    ]
    if invocation.location_icon is not None:
        rows.append(
            [
                "location-icon",
                "Image",
                {
                    "src": asset_src(invocation.location_icon, task_spec),
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
    return Invocation(
        location=ref(field_by_terms(data_shape, "prefecture", "city", "城市", numeric=False)),
        temperature=ref(field_by_terms(data_shape, "temperaturetext", "温度", numeric=None)),
        condition=ref(field_by_terms(data_shape, "condition", "天气", numeric=False)),
        range_text=ref(field_by_terms(data_shape, "range", "最高", numeric=False)),
        location_icon=(
            first_asset_id(task_spec, "location", "天气") if task_spec.assetCandidates else None
        ),
        action=first_action(task_spec, "关怀"),
    )


def validate(invocation: Invocation, task_spec: TaskSpec) -> None:
    if invocation.location_icon is not None:
        asset_src(invocation.location_icon, task_spec)


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
