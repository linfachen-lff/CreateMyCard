"""带两个语义图片的单个大号主指标和快捷操作。"""

from pydantic import BaseModel, Field

from models.generation import TaskSpec

from ...component_registry import ComponentPlugin, register_component
from ...models import ActionRef, BindingRef, ComponentSpec, DataShape
from ..a2ui_base import rows_to_a2ui
from ..base import binding, event_handler, root_props
from ..scene_helpers import asset_src, field_by_terms, first_action, first_asset_id, ref


class Invocation(BaseModel):
    location: BindingRef | None = Field(default=None, description="可选的顶部地点文本绑定。")
    temperature: BindingRef = Field(description="当前温度主指标绑定。")
    condition: BindingRef = Field(description="降雨等天气状态文本绑定。")
    range_text: BindingRef | None = Field(default=None, description="可选的底部补充摘要绑定。")
    weather_icon: str = Field(description="必须填写 assetCandidates 中的天气资源 id。")
    taxi_icon: str = Field(description="必须填写 assetCandidates 中的打车资源 id。")
    action: ActionRef = Field(description="打车动作，event_id 必须来自 eventCandidates。")


SPEC = ComponentSpec(
    component_id="hero-metric-icon-action",
    description="单个大号主指标、双语义图片和圆形图片操作。",
    slots=["可选顶部短文本和图片", "一个大号主指标", "至少一条状态摘要", "图片式圆形操作"],
    supported_sizes=["2x2"],
    required_signals={"action": 1.0},
    domains=["weather"],
    scenarios=["bad-weather-commute"],
    status_semantics=["warning"],
    content_semantics=["location", "temperature", "status"],
    action_semantics=["hail-taxi"],
    layout_archetypes=["hero-metric-icon-action"],
    temporalities=["now"],
    min_semantic_score=8.0,
    min_fields=2,
    min_assets=2,
    min_actions=1,
)


def build_rows(invocation: Invocation, tokens: dict[str, object], task_spec: TaskSpec):
    root = root_props(tokens)
    root.update(
        {
            "padding": 12,
            "backgroundColor": "#FF315668",
            "linearGradient": {
                "direction": "Bottom",
                "colors": [["#FF414B52", 0], ["#FF1686A8", 1]],
            },
            "justifyContent": "spaceBetween",
        }
    )
    header_children = ["weather"]
    if invocation.location is not None:
        header_children = ["pin", "location", "weather"]
    footer_children = ["taxi-wrap"]
    if invocation.range_text is not None:
        footer_children = ["range", "taxi-wrap"]
    rows = [
        ["root", "Column", root, ["header", "temperature", "condition", "footer"]],
        [
            "header",
            "Row",
            {"alignItems": "center", "itemMargin": 5},
            header_children,
        ],
        [
            "weather",
            "Image",
            {
                "src": asset_src(invocation.weather_icon, task_spec),
                "width": 22,
                "height": 22,
                "objectFit": "contain",
            },
        ],
        [
            "temperature",
            "Text",
            {
                "content": binding(invocation.temperature),
                "fontSize": 38,
                "fontWeight": 700,
                "fontColor": "#FFFFFFFF",
            },
        ],
        [
            "condition",
            "Text",
            {"content": binding(invocation.condition), "fontSize": 13, "fontColor": "#FFE8F6FA"},
        ],
        ["footer", "Row", {"alignItems": "center"}, footer_children],
        [
            "taxi-wrap",
            "Stack",
            {"width": 40, "height": 40, "alignContent": "center"},
            ["action", "taxi-icon"],
        ],
        [
            "action",
            "Button",
            {
                "label": invocation.action.label,
                "onClick": event_handler(invocation.action, task_spec),
                "width": 40,
                "height": 40,
                "borderRadius": 20,
                "backgroundColor": "#FFFFFFFF",
                "fontColor": "#00FFFFFF",
                "fontSize": 1,
            },
        ],
        [
            "taxi-icon",
            "Image",
            {
                "src": asset_src(invocation.taxi_icon, task_spec),
                "width": 21,
                "height": 21,
                "objectFit": "contain",
            },
        ],
    ]
    if invocation.location is not None:
        rows.extend(
            [
                ["pin", "Text", {"content": "●", "fontSize": 10, "fontColor": "#FFFFFFFF"}],
                [
                    "location",
                    "Text",
                    {
                        "content": binding(invocation.location),
                        "fontSize": 14,
                        "fontWeight": 600,
                        "fontColor": "#FFFFFFFF",
                        "layoutWeight": 1,
                    },
                ],
            ]
        )
    if invocation.range_text is not None:
        rows.append(
            [
                "range",
                "Text",
                {
                    "content": binding(invocation.range_text),
                    "fontSize": 12,
                    "fontColor": "#FFD7EDF4",
                    "layoutWeight": 1,
                },
            ]
        )
    return rows


def build_a2ui(invocation: Invocation, tokens: dict[str, object], task_spec: TaskSpec) -> str:
    return rows_to_a2ui(build_rows(invocation, tokens, task_spec), task_spec)


def map_offline(task_spec: TaskSpec, data_shape: DataShape) -> Invocation:
    def optional_ref(*terms: str) -> BindingRef | None:
        try:
            return ref(field_by_terms(data_shape, *terms, numeric=False))
        except ValueError:
            return None

    return Invocation(
        location=optional_ref("prefecture", "city", "城市"),
        temperature=ref(field_by_terms(data_shape, "temperaturetext", "温度", numeric=None)),
        condition=ref(field_by_terms(data_shape, "condition", "天气", "雨", numeric=False)),
        range_text=optional_ref("range", "最高"),
        weather_icon=first_asset_id(task_spec, "rain", "weather", "天气"),
        taxi_icon=first_asset_id(task_spec, "taxi", "car", "打车"),
        action=first_action(task_spec, "打车"),
    )


def validate(invocation: Invocation, task_spec: TaskSpec) -> None:
    asset_src(invocation.weather_icon, task_spec)
    asset_src(invocation.taxi_icon, task_spec)


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
