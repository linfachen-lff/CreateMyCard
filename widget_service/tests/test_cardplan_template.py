from __future__ import annotations

import json
import random
import shutil
import sqlite3
import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import Literal

import pytest

from api.schemas import GenerateWidgetCardRequest
from app.logger import json_for_log
from config.config import Settings, get_settings
from custom.deepseek_call_budget import DeepSeekCallBudget, DeepSeekCallBudgetExceeded
from custom.model_transport import ModelTransportError
from custom.unified_model_client import UnifiedModelClient
from models.generation import EventAction, TaskSpec
from services.advanced_component_pipeline.content_selectors import (
    extract_app_usage_overview_facts,
    project_content_component_facts,
)
from services.advanced_component_pipeline.models import (
    UX_LAYOUT_COMPONENT_IDS,
    DataShape,
    UIBrief,
)
from services.advanced_component_pipeline.ui_planner import (
    normalize_action_placement,
    plan_ui_with_llm,
)
from services.card_validation import validate_card
from services.cardplan_template.compiler import (
    _append_missing_required_literals,
    _compact_text_roles,
    _normalize_card_params,
    _normalize_component_values,
    _reclaim_optional_chrome_for_content,
    compile_hybrid_card,
    compile_ux_layout_card,
)
from services.cardplan_template.framer import HybridCardFramer
from services.cardplan_template.models import ActionBinding, HybridBodyContract, HybridLimits
from services.cardplan_template.parser import parse_hybrid_card, parse_ux_layout_card
from services.cardplan_template.prompt import build_hybrid_prompt, selection_candidates
from services.cardplan_template.registry import CardPlanRegistry, get_cardplan_registry
from services.protocol_registry import TERSE_DSL_NESTED2_PROFILE_ID, A2UIProtocolRegistry
from services.terse_dsl_nested2_converter import Nested2Node, TerseDslNested2ConversionError
from services.widget_generation_service import WidgetGenerationService

SERVICE_ROOT = Path(__file__).resolve().parents[1]
GOLDEN_FIXTURE = SERVICE_ROOT / "tests/fixtures/cardplan_golden_scenarios.json"


def _ux_layout_contract(
    layout_id: str,
    *,
    with_action: bool,
) -> HybridBodyContract:
    action_bindings = (
        (
            ActionBinding(
                action_id="event.open",
                display_label="打开",
                call="clickToApi",
                args={},
            ),
        )
        if with_action
        else ()
    )
    return HybridBodyContract(
        theme_profile_id="meeting-paper-neutral",
        allowed_components=(
            "Text",
            "Image",
            "Divider",
            "Progress",
            "Button",
            "Checkbox",
            "Row",
            "Column",
            "List",
            "Stack",
            layout_id,
        ),
        allowed_design_tokens=("body",),
        allowed_layout_tokens=("card", "section", "compact", "between"),
        allowed_template_ids=(),
        allowed_asset_sources=(),
        trusted_literals=("业务摘要", "打开"),
        trusted_numbers=(),
        required_literals=(),
        protected_literals=(),
        action_bindings=action_bindings,
        allowed_layout_component_ids=(layout_id,),
        limits=HybridLimits(
            max_raw_components=18,
            max_expanded_components=48,
            max_nesting_depth=10,
            vertical_budget_vp=126,
        ),
    )


def _ux_layout_task(*, with_action: bool) -> TaskSpec:
    events = (
        [EventAction(id="event.open", displayLabel="打开", call="clickToApi", args={})]
        if with_action
        else []
    )
    return TaskSpec(
        userQuery="业务摘要",
        size="2x2",
        eventCandidates=events,
        dataModelSchema={"data": {}},
        assetCandidates=[],
    )


def _content_template_contract(
    template_id: str,
    theme_id: str,
    literals: tuple[str, ...],
    *,
    assets: tuple[str, ...] = (),
    asset_tags: dict[str, tuple[str, ...]] | None = None,
    numbers: tuple[int | float, ...] = (),
) -> HybridBodyContract:
    return HybridBodyContract(
        theme_profile_id=theme_id,
        allowed_components=(
            "Text",
            "Image",
            "Divider",
            "Progress",
            "Button",
            "Checkbox",
            "Row",
            "Column",
            "List",
            "Stack",
            "SingleFocusLayout",
        ),
        allowed_design_tokens=("body",),
        allowed_layout_tokens=("card", "section", "compact", "between"),
        allowed_template_ids=(template_id,),
        allowed_asset_sources=assets,
        asset_semantic_tags_by_source=asset_tags or {},
        trusted_literals=literals,
        trusted_numbers=numbers,
        required_literals=(),
        protected_literals=(),
        action_bindings=(),
        allowed_layout_component_ids=("SingleFocusLayout",),
        limits=HybridLimits(
            max_raw_components=18,
            max_expanded_components=48,
            max_nesting_depth=10,
            vertical_budget_vp=136,
        ),
    )


def _ux_layout_root_contract(
    layout_id: str,
    *,
    action_id: str | None = None,
    assets: tuple[str, ...] = (),
) -> HybridBodyContract:
    action_bindings = (
        (
            ActionBinding(
                action_id=action_id,
                display_label="打开",
                call="clickToApi",
                args={},
            ),
        )
        if action_id is not None
        else ()
    )
    return HybridBodyContract(
        theme_profile_id="meeting-paper-neutral",
        allowed_components=(
            "Text",
            "Image",
            "Divider",
            "Progress",
            "Button",
            "Checkbox",
            "Row",
            "Column",
            "List",
            "Stack",
            layout_id,
            "PillAction",
            "IconAction",
            "ActionTile",
        ),
        allowed_design_tokens=("body", "icon", "compact-action"),
        allowed_layout_tokens=("card", "section", "compact", "between", "actions", "overlay"),
        allowed_template_ids=(),
        allowed_asset_sources=assets,
        trusted_literals=("业务摘要", "打开"),
        trusted_numbers=(),
        required_literals=(),
        protected_literals=(),
        action_bindings=action_bindings,
        content_action_ids=(action_id,) if action_id is not None else (),
        allowed_layout_component_ids=(layout_id,),
        limits=HybridLimits(
            max_raw_components=18,
            max_expanded_components=48,
            max_nesting_depth=10,
            vertical_budget_vp=136,
        ),
    )


def _direct_layout_inputs(
    layout_id: str,
    *,
    size: Literal["2x2", "2x4"],
    literals: tuple[str, ...],
    action_ids: tuple[str, ...] = (),
    assets: tuple[str, ...] = (),
) -> tuple[TaskSpec, HybridBodyContract]:
    labels = tuple(f"操作{index + 1}" for index in range(len(action_ids)))
    bindings = tuple(
        ActionBinding(
            action_id=action_id,
            display_label=label,
            call="clickToApi",
            args={"intentName": "Settings", "params": {}},
        )
        for action_id, label in zip(action_ids, labels, strict=True)
    )
    events = [
        EventAction(
            id=action_id,
            displayLabel=label,
            call="clickToApi",
            args={"intentName": "Settings", "params": {}},
        )
        for action_id, label in zip(action_ids, labels, strict=True)
    ]
    task_spec = TaskSpec(
        userQuery=literals[0],
        size=size,
        eventCandidates=events,
        dataModelSchema={"data": {}},
        assetCandidates=[],
    )
    contract = HybridBodyContract(
        theme_profile_id="meeting-paper-neutral",
        allowed_components=(
            "Text",
            "Image",
            "Divider",
            "Progress",
            "Button",
            "Checkbox",
            "Row",
            "Column",
            "List",
            "Stack",
            layout_id,
            "PillAction",
            "IconAction",
            "ActionTile",
        ),
        allowed_design_tokens=("body", "title", "icon", "compact-action"),
        allowed_layout_tokens=(
            "card",
            "section",
            "compact",
            "between",
            "actions",
            "overlay",
        ),
        allowed_template_ids=(),
        allowed_asset_sources=assets,
        trusted_literals=(*literals, *labels),
        trusted_numbers=(),
        required_literals=(),
        protected_literals=(),
        action_bindings=bindings,
        content_action_ids=action_ids,
        allowed_layout_component_ids=(layout_id,),
        limits=HybridLimits(
            max_raw_components=32,
            max_expanded_components=96,
            max_nesting_depth=14,
            vertical_budget_vp=136,
        ),
    )
    return task_spec, contract


def _compile_direct_layout(
    source: str,
    *,
    layout_id: str,
    size: Literal["2x2", "2x4"],
    literals: tuple[str, ...],
    action_ids: tuple[str, ...] = (),
    assets: tuple[str, ...] = (),
):
    task_spec, contract = _direct_layout_inputs(
        layout_id,
        size=size,
        literals=literals,
        action_ids=action_ids,
        assets=assets,
    )
    compilation = compile_ux_layout_card(
        source,
        task_spec=task_spec,
        contract=contract,
        protocol_profile=A2UIProtocolRegistry.read_design_protocol_profile(
            TERSE_DSL_NESTED2_PROFILE_ID
        ),
        registry=get_cardplan_registry(),
    )
    errors = [
        item
        for item in validate_card(dsl_text=compilation.a2ui).diagnostics
        if item.severity == "error"
    ]
    context_only_codes = {"ASSET_PATH_NOT_DECLARED"}
    assert not [item for item in errors if item.code not in context_only_codes]
    return compilation


@pytest.mark.parametrize(
    ("layout_id", "child_count", "with_action"),
    [
        ("SingleFocusLayout", 1, False),
        ("HeroActionLayout", 1, True),
        ("HeroSupportLayout", 2, False),
        ("HeroSupportActionLayout", 2, True),
        ("PeerPairLayout", 2, False),
        ("SequentialSummaryLayout", 2, False),
        ("EqualItemsLayout", 2, False),
        ("ListActionLayout", 1, False),
        ("ActionMatrixLayout", 1, True),
        ("WeatherNowForecastLayout", 1, False),
    ],
)
def test_each_ux_layout_is_lowered_to_standard_a2ui(
    layout_id: str,
    child_count: int,
    with_action: bool,
):
    children = ", ".join('Text("业务摘要", "body")' for _ in range(child_count))
    card_params = '{"action":{"label":"打开","id":"event.open"}}' if with_action else "{}"
    source = f'Template("card@1", {card_params}, {layout_id}({children}));'

    compilation = compile_hybrid_card(
        source,
        task_spec=_ux_layout_task(with_action=with_action),
        contract=_ux_layout_contract(layout_id, with_action=with_action),
        protocol_profile=A2UIProtocolRegistry.read_design_protocol_profile(
            TERSE_DSL_NESTED2_PROFILE_ID
        ),
        registry=get_cardplan_registry(),
    )

    assert layout_id not in compilation.effective_output
    assert "Template" not in compilation.a2ui
    assert all(item not in compilation.a2ui for item in UX_LAYOUT_COMPONENT_IDS)


def test_direct_ux_layout_root_owns_pill_action_without_card_template():
    source = 'HeroActionLayout(Text("业务摘要", "body"), PillAction({"actionId":"event.open"}));'
    compilation = compile_ux_layout_card(
        source,
        task_spec=_ux_layout_task(with_action=True),
        contract=_ux_layout_root_contract("HeroActionLayout", action_id="event.open"),
        protocol_profile=A2UIProtocolRegistry.read_design_protocol_profile(
            TERSE_DSL_NESTED2_PROFILE_ID
        ),
        registry=get_cardplan_registry(),
    )

    assert parse_ux_layout_card(source).name == "HeroActionLayout"
    assert "card@1" not in compilation.effective_output
    assert "HeroActionLayout" not in compilation.effective_output
    assert "PillAction" not in compilation.effective_output
    assert '"height":36' in compilation.effective_output
    assert '"borderRadius":18.0' in compilation.effective_output
    assert '"height":"100%"' in compilation.effective_output
    assert '"layoutWeight":1' in compilation.effective_output
    assert '"clip":true' in compilation.effective_output
    assert compilation.effective_output.count("打开") == 1
    assert '"call":"clickToApi"' in compilation.effective_output
    assert "Template" not in compilation.a2ui


def test_direct_ux_layout_icon_action_uses_30_by_30_safe_slot():
    icon = "resources/base/media/action.svg"
    source = (
        'SingleFocusLayout(Text("业务摘要", "body"), '
        f'IconAction({{"actionId":"event.open","icon":"{icon}"}}));'
    )
    compilation = compile_ux_layout_card(
        source,
        task_spec=_ux_layout_task(with_action=True),
        contract=_ux_layout_root_contract(
            "SingleFocusLayout",
            action_id="event.open",
            assets=(icon,),
        ),
        protocol_profile=A2UIProtocolRegistry.read_design_protocol_profile(
            TERSE_DSL_NESTED2_PROFILE_ID
        ),
        registry=get_cardplan_registry(),
    )

    assert '"width":30' in compilation.effective_output
    assert '"height":30' in compilation.effective_output
    assert '"width":16' in compilation.effective_output
    assert '"height":16' in compilation.effective_output


def test_weather_layout_normalizes_icon_backed_pill_to_overlay_icon_action():
    icon = "resources/base/media/action.svg"
    source = (
        'WeatherNowForecastLayout(Text("业务摘要", "body"), '
        f'PillAction({{"actionId":"event.open","icon":"{icon}"}}));'
    )
    compilation = compile_ux_layout_card(
        source,
        task_spec=_ux_layout_task(with_action=True),
        contract=_ux_layout_root_contract(
            "WeatherNowForecastLayout",
            action_id="event.open",
            assets=(icon,),
        ),
        protocol_profile=A2UIProtocolRegistry.read_design_protocol_profile(
            TERSE_DSL_NESTED2_PROFILE_ID
        ),
        registry=get_cardplan_registry(),
    )

    assert '"width":30' in compilation.effective_output
    assert '"height":30' in compilation.effective_output
    assert '"height":36' not in compilation.effective_output


def test_direct_2x2_action_layout_compacts_adjacent_short_metric_rows():
    source = (
        'HeroActionLayout(Column("section", '
        'Row("between", Text("3", "title"), Text("小时", "body")), '
        'Row("between", Text("45", "title"), Text("分钟", "body")), '
        'Text("业务摘要", "body")), PillAction({"actionId":"event.open"}));'
    )
    compilation = compile_ux_layout_card(
        source,
        task_spec=_ux_layout_task(with_action=True),
        contract=_ux_layout_root_contract("HeroActionLayout", action_id="event.open").model_copy(
            update={
                "trusted_literals": ("业务摘要", "3", "小时", "45", "分钟"),
                "allowed_design_tokens": ("body", "title", "icon", "compact-action"),
            }
        ),
        protocol_profile=A2UIProtocolRegistry.read_design_protocol_profile(
            TERSE_DSL_NESTED2_PROFILE_ID
        ),
        registry=get_cardplan_registry(),
    )
    update = json.loads(compilation.a2ui.splitlines()[1])["updateComponents"]
    rows = [item for item in update["components"] if item["component"] == "Row"]

    assert any(len(item.get("children", [])) == 4 for item in rows)


def test_direct_layout_injects_trusted_business_title_inside_content():
    source = 'HeroActionLayout(Text("业务摘要", "body"), PillAction({"actionId":"event.open"}));'
    contract = _ux_layout_root_contract("HeroActionLayout", action_id="event.open").model_copy(
        update={"trusted_literals": ("业务摘要", "业务标题", "打开")}
    )
    compilation = compile_ux_layout_card(
        source,
        task_spec=_ux_layout_task(with_action=True),
        contract=contract,
        protocol_profile=A2UIProtocolRegistry.read_design_protocol_profile(
            TERSE_DSL_NESTED2_PROFILE_ID
        ),
        registry=get_cardplan_registry(),
        business_title="业务标题",
    )

    assert compilation.effective_output.count("业务标题") == 1
    assert compilation.effective_output.index("业务标题") < compilation.effective_output.index(
        "业务摘要"
    )
    update = json.loads(compilation.a2ui.splitlines()[1])["updateComponents"]
    title = next(
        item
        for item in update["components"]
        if item["component"] == "Text" and item["content"] == "业务标题"
    )
    assert title["styles"]["width"] == "100%"
    assert title["styles"]["minFontSize"] == 9
    assert title["styles"]["maxLines"] == 1
    assert title["styles"]["textOverflow"] == "ellipsis"


def test_direct_layout_uses_compact_font_for_long_trusted_business_title():
    source = 'SingleFocusLayout(Text("倒计时", "body"));'
    title = "距离香H100越野赛"
    contract = _ux_layout_root_contract("SingleFocusLayout").model_copy(
        update={"trusted_literals": ("倒计时", title)}
    )
    compilation = compile_ux_layout_card(
        source,
        task_spec=_ux_layout_task(with_action=False),
        contract=contract,
        protocol_profile=A2UIProtocolRegistry.read_design_protocol_profile(
            TERSE_DSL_NESTED2_PROFILE_ID
        ),
        registry=get_cardplan_registry(),
        business_title=title,
    )
    update = json.loads(compilation.a2ui.splitlines()[1])["updateComponents"]
    rendered = next(
        item
        for item in update["components"]
        if item["component"] == "Text" and item["content"] == title
    )

    assert rendered["styles"]["fontSize"] == 10


def test_direct_layout_safely_splits_delimiter_joined_trusted_facts():
    source = (
        'SingleFocusLayout(Column("compact", Text("26°/16°", "body")), '
        'IconAction({"actionId":"event.open","icon":"resources/base/media/action.svg"}));'
    )
    contract = _ux_layout_root_contract(
        "SingleFocusLayout",
        action_id="event.open",
        assets=("resources/base/media/action.svg",),
    ).model_copy(update={"trusted_literals": ("26°", "16°", "打开")})
    compilation = compile_ux_layout_card(
        source,
        task_spec=_ux_layout_task(with_action=True),
        contract=contract,
        protocol_profile=A2UIProtocolRegistry.read_design_protocol_profile(
            TERSE_DSL_NESTED2_PROFILE_ID
        ),
        registry=get_cardplan_registry(),
    )

    assert "26°/16°" in compilation.raw_output
    assert "26°/16°" not in compilation.effective_output
    assert compilation.effective_output.count("26°") == 1
    assert compilation.effective_output.count("16°") == 1

    with pytest.raises(TerseDslNested2ConversionError, match="Raw literal is not trusted"):
        compile_ux_layout_card(
            source.replace("26°/16°", "26°/恶意内容"),
            task_spec=_ux_layout_task(with_action=True),
            contract=contract,
            protocol_profile=A2UIProtocolRegistry.read_design_protocol_profile(
                TERSE_DSL_NESTED2_PROFILE_ID
            ),
            registry=get_cardplan_registry(),
        )


def test_layout_registry_exposes_closed_ux_parameter_and_action_contracts():
    registry = get_cardplan_registry()
    equal_items = registry.require_ux_layout_component("EqualItemsLayout")
    action_matrix = registry.require_ux_layout_component("ActionMatrixLayout")

    assert equal_items.minimum_children("2x2") == 2
    assert equal_items.minimum_children("2x4") == 3
    assert equal_items.parameters_schema["additionalProperties"] is False
    assert action_matrix.minimum_children("2x2") == 0
    assert action_matrix.max_children_by_size == {"2x2": 1, "2x4": 1}
    assert action_matrix.min_action_children_by_size == {"2x2": 2, "2x4": 2}
    assert action_matrix.max_action_children_by_size == {"2x2": 2, "2x4": 4}


@pytest.mark.parametrize("size", ["2x2", "2x4"])
@pytest.mark.parametrize(
    ("layout_id", "source", "literals", "action_ids"),
    [
        (
            "SingleFocusLayout",
            'SingleFocusLayout(Text("主内容", "body"));',
            ("主内容",),
            (),
        ),
        (
            "HeroActionLayout",
            'HeroActionLayout(Text("主指标", "body"), PillAction({"actionId":"event.first"}));',
            ("主指标",),
            ("event.first",),
        ),
        (
            "HeroSupportLayout",
            'HeroSupportLayout(Text("主区", "body"), Text("支持区", "body"));',
            ("主区", "支持区"),
            (),
        ),
        (
            "HeroSupportActionLayout",
            'HeroSupportActionLayout(Text("主区", "body"), Text("支持区", "body"), '
            'PillAction({"actionId":"event.first"}));',
            ("主区", "支持区"),
            ("event.first",),
        ),
        (
            "PeerPairLayout",
            'PeerPairLayout(Text("第一项", "body"), Text("第二项", "body"));',
            ("第一项", "第二项"),
            (),
        ),
        (
            "SequentialSummaryLayout",
            'SequentialSummaryLayout(Text("主摘要", "body"), Text("详情", "body"));',
            ("主摘要", "详情"),
            (),
        ),
        (
            "EqualItemsLayout",
            'EqualItemsLayout(Text("项目一", "body"), Text("项目二", "body"), '
            'Text("项目三", "body"));',
            ("项目一", "项目二", "项目三"),
            (),
        ),
        (
            "ListActionLayout",
            'ListActionLayout(Text("列表", "body"));',
            ("列表",),
            (),
        ),
        (
            "ActionMatrixLayout",
            'ActionMatrixLayout(Text("设置摘要", "body"), '
            'ActionTile({"actionId":"event.first"}), '
            'ActionTile({"actionId":"event.second"}));',
            ("设置摘要",),
            ("event.first", "event.second"),
        ),
        (
            "WeatherNowForecastLayout",
            'WeatherNowForecastLayout(Text("当前天气", "body"));',
            ("当前天气",),
            (),
        ),
    ],
)
def test_every_layout_compiles_for_both_card_sizes_to_standard_a2ui(
    size: Literal["2x2", "2x4"],
    layout_id: str,
    source: str,
    literals: tuple[str, ...],
    action_ids: tuple[str, ...],
):
    if layout_id == "EqualItemsLayout" and size == "2x2":
        source = source.replace(', Text("项目三", "body")', "")
        literals = literals[:2]

    compilation = _compile_direct_layout(
        source,
        layout_id=layout_id,
        size=size,
        literals=literals,
        action_ids=action_ids,
    )

    assert layout_id not in compilation.effective_output
    assert "Template" not in compilation.a2ui
    assert all(item not in compilation.a2ui for item in UX_LAYOUT_COMPONENT_IDS)


def test_single_focus_layout_honors_closed_content_alignment_config():
    compilation = _compile_direct_layout(
        'SingleFocusLayout({"contentAlign":"bottomStart"}, Text("主内容", "body"));',
        layout_id="SingleFocusLayout",
        size="2x2",
        literals=("主内容",),
    )

    assert '"justifyContent":"end"' in compilation.effective_output
    assert '"alignItems":"start"' in compilation.effective_output
    assert '"padding":12' in compilation.effective_output
    assert '"borderRadius":20' in compilation.effective_output
    update = json.loads(compilation.a2ui.splitlines()[1])["updateComponents"]
    root = next(item for item in update["components"] if item["id"] == "root")
    assert root["styles"]["width"] == "matchParent"
    assert root["styles"]["height"] == "matchParent"
    assert root["styles"]["clip"] is True

    with pytest.raises(TerseDslNested2ConversionError, match="parameters are invalid"):
        _compile_direct_layout(
            'SingleFocusLayout({"contentAlign":"center","offset":8}, Text("主内容", "body"));',
            layout_id="SingleFocusLayout",
            size="2x2",
            literals=("主内容",),
        )


def test_hero_action_layout_uses_bottom_on_2x2_and_60_40_end_on_2x4():
    bottom = _compile_direct_layout(
        'HeroActionLayout(Text("主指标", "body"), PillAction({"actionId":"event.first"}));',
        layout_id="HeroActionLayout",
        size="2x2",
        literals=("主指标",),
        action_ids=("event.first",),
    )
    end = _compile_direct_layout(
        'HeroActionLayout({"actionPlacement":"end"}, Text("主指标", "body"), '
        'PillAction({"actionId":"event.first"}));',
        layout_id="HeroActionLayout",
        size="2x4",
        literals=("主指标",),
        action_ids=("event.first",),
    )

    assert '"height":36' in bottom.effective_output
    assert '"justifyContent":"spaceBetween"' in bottom.effective_output
    assert '"layoutWeight":60' in end.effective_output
    assert '"layoutWeight":40' in end.effective_output
    update = json.loads(bottom.a2ui.splitlines()[1])["updateComponents"]
    conflicting_flex = [
        item
        for item in update["components"]
        if item.get("styles", {}).get("layoutWeight") is not None
        and item.get("styles", {}).get("height") == "100%"
    ]
    assert conflicting_flex == []

    with pytest.raises(TerseDslNested2ConversionError, match="only available for 2x4"):
        _compile_direct_layout(
            'HeroActionLayout({"actionPlacement":"end"}, Text("主指标", "body"), '
            'PillAction({"actionId":"event.first"}));',
            layout_id="HeroActionLayout",
            size="2x2",
            literals=("主指标",),
            action_ids=("event.first",),
        )


def test_hero_support_layout_honors_ratio_direction_and_support_panel():
    balanced = _compile_direct_layout(
        'HeroSupportLayout(Text("主区", "body"), Text("支持区", "body"));',
        layout_id="HeroSupportLayout",
        size="2x4",
        literals=("主区", "支持区"),
    )
    compilation = _compile_direct_layout(
        'HeroSupportLayout({"ratio":"supportWide","direction":"horizontal"}, '
        'Text("主区", "body"), Text("支持区", "body"));',
        layout_id="HeroSupportLayout",
        size="2x4",
        literals=("主区", "支持区"),
    )

    assert balanced.effective_output.count('"layoutWeight":50') == 2
    assert '"layoutWeight":44' in compilation.effective_output
    assert '"constraintSize":{"minWidth":0,"minHeight":0}' in (compilation.effective_output)
    assert '"layoutWeight":56' in compilation.effective_output
    assert '"padding":{"left":12,"top":8,"right":12,"bottom":8}' in (compilation.effective_output)
    assert '"borderRadius":8' in compilation.effective_output


def test_hero_support_action_layout_preserves_hero_and_fixed_action_slots():
    compact = _compile_direct_layout(
        'HeroSupportActionLayout(Text("主区", "body"), Text("支持区", "body"), '
        'PillAction({"actionId":"event.first"}));',
        layout_id="HeroSupportActionLayout",
        size="2x2",
        literals=("主区", "支持区"),
        action_ids=("event.first",),
    )
    wide = _compile_direct_layout(
        'HeroSupportActionLayout({"heroRatio":"wide"}, Text("主区", "body"), '
        'Text("支持区", "body"), PillAction({"actionId":"event.first"}));',
        layout_id="HeroSupportActionLayout",
        size="2x4",
        literals=("主区", "支持区"),
        action_ids=("event.first",),
    )

    assert '"height":36,"clip":true' in compact.effective_output
    assert '"layoutWeight":1,"clip":true' in compact.effective_output
    assert '"layoutWeight":56' in wide.effective_output
    assert '"layoutWeight":44' in wide.effective_output


def test_2x2_hero_support_action_drops_only_optional_overflowing_support():
    source = (
        'HeroSupportActionLayout(Text("主区", "body"), Column("compact", '
        'Text("可选一", "body"), Text("可选二", "body"), Text("可选三", "body")), '
        'PillAction({"actionId":"event.first"}));'
    )
    compilation = _compile_direct_layout(
        source,
        layout_id="HeroSupportActionLayout",
        size="2x2",
        literals=("主区", "可选一", "可选二", "可选三"),
        action_ids=("event.first",),
    )

    assert "主区" in compilation.effective_output
    assert all(item not in compilation.effective_output for item in ("可选一", "可选二", "可选三"))
    assert "操作1" in compilation.effective_output

    task_spec, contract = _direct_layout_inputs(
        "HeroSupportActionLayout",
        size="2x2",
        literals=("主区", "可选一", "可选二", "可选三"),
        action_ids=("event.first",),
    )
    with pytest.raises(TerseDslNested2ConversionError, match="cannot drop required Support"):
        compile_ux_layout_card(
            source,
            task_spec=task_spec,
            contract=contract.model_copy(update={"required_literals": ("可选一",)}),
            protocol_profile=A2UIProtocolRegistry.read_design_protocol_profile(
                TERSE_DSL_NESTED2_PROFILE_ID
            ),
            registry=get_cardplan_registry(),
        )


def test_peer_sequential_and_equal_layouts_follow_size_specific_geometry():
    peer = _compile_direct_layout(
        'PeerPairLayout({"orientation":"rows"}, Text("第一项", "body"), Text("第二项", "body"));',
        layout_id="PeerPairLayout",
        size="2x2",
        literals=("第一项", "第二项"),
    )
    sequential = _compile_direct_layout(
        'SequentialSummaryLayout({"detailColumns":2}, Text("主摘要", "body"), '
        'Text("详情一", "body"), Text("详情二", "body"));',
        layout_id="SequentialSummaryLayout",
        size="2x4",
        literals=("主摘要", "详情一", "详情二"),
    )
    equal = _compile_direct_layout(
        'EqualItemsLayout({"arrangement":"grid"}, Text("项目一", "body"), '
        'Text("项目二", "body"), Text("项目三", "body"), Text("项目四", "body"));',
        layout_id="EqualItemsLayout",
        size="2x4",
        literals=("项目一", "项目二", "项目三", "项目四"),
    )

    assert peer.effective_output.count('"layoutWeight":50') == 2
    assert sequential.effective_output.count('"backgroundColor":"#14000000"') == 2
    assert sequential.effective_output.count('"layoutWeight":1') >= 4
    assert equal.effective_output.count('"padding":8') == 4
    assert equal.effective_output.count('"layoutWeight":1') >= 6

    with pytest.raises(TerseDslNested2ConversionError, match="child count is invalid"):
        _compile_direct_layout(
            'EqualItemsLayout(Text("项目一", "body"), Text("项目二", "body"));',
            layout_id="EqualItemsLayout",
            size="2x4",
            literals=("项目一", "项目二"),
        )


def test_list_action_end_and_action_matrix_multi_action_geometry():
    list_end = _compile_direct_layout(
        'ListActionLayout({"actionPlacement":"end"}, Text("列表", "body"), '
        'PillAction({"actionId":"event.first"}));',
        layout_id="ListActionLayout",
        size="2x4",
        literals=("列表",),
        action_ids=("event.first",),
    )
    matrix = _compile_direct_layout(
        'ActionMatrixLayout({"primaryActionIndex":1}, Text("设置摘要", "body"), '
        'ActionTile({"actionId":"event.first"}), '
        'ActionTile({"actionId":"event.second"}), '
        'ActionTile({"actionId":"event.third"}));',
        layout_id="ActionMatrixLayout",
        size="2x4",
        literals=("设置摘要",),
        action_ids=("event.first", "event.second", "event.third"),
    )
    compact_matrix = _compile_direct_layout(
        'ActionMatrixLayout(Text("设置摘要", "body"), '
        'ActionTile({"actionId":"event.first"}), '
        'ActionTile({"actionId":"event.second"}));',
        layout_id="ActionMatrixLayout",
        size="2x2",
        literals=("设置摘要",),
        action_ids=("event.first", "event.second"),
    )

    assert '"layoutWeight":60' in list_end.effective_output
    assert '"layoutWeight":40' in list_end.effective_output
    assert matrix.effective_output.index("操作2") < matrix.effective_output.index("操作1")
    assert set(matrix.stats.action_used_ids) == {
        "event.first",
        "event.second",
        "event.third",
    }
    assert '"height":"100%"' in compact_matrix.effective_output
    assert "ActionMatrixLayout" not in matrix.a2ui
    assert "ActionTile" not in matrix.a2ui

    with pytest.raises(TerseDslNested2ConversionError, match="Action count is invalid"):
        _compile_direct_layout(
            'ActionMatrixLayout(Text("设置摘要", "body"), ActionTile({"actionId":"event.first"}));',
            layout_id="ActionMatrixLayout",
            size="2x4",
            literals=("设置摘要",),
            action_ids=("event.first",),
        )
    with pytest.raises(TerseDslNested2ConversionError, match="requires ActionTile"):
        _compile_direct_layout(
            'ActionMatrixLayout(Text("设置摘要", "body"), '
            'PillAction({"actionId":"event.first"}), '
            'PillAction({"actionId":"event.second"}));',
            layout_id="ActionMatrixLayout",
            size="2x2",
            literals=("设置摘要",),
            action_ids=("event.first", "event.second"),
        )


def test_weather_layout_reserves_2x2_icon_slot_and_builds_2x4_forecast_strip():
    icon = "resources/base/media/weather_action_white.svg"
    compact = _compile_direct_layout(
        'WeatherNowForecastLayout(Text("当前天气", "body"), '
        f'IconAction({{"actionId":"event.first","icon":"{icon}"}}));',
        layout_id="WeatherNowForecastLayout",
        size="2x2",
        literals=("当前天气",),
        action_ids=("event.first",),
        assets=(icon,),
    )
    wide = _compile_direct_layout(
        'WeatherNowForecastLayout(Text("当前天气", "body"), '
        'Text("明日", "body"), Text("后日", "body"), Text("大后日", "body"));',
        layout_id="WeatherNowForecastLayout",
        size="2x4",
        literals=("当前天气", "明日", "后日", "大后日"),
    )

    assert '"alignContent":"bottomEnd"' in compact.effective_output
    assert '"padding":{"right":38,"bottom":38}' in compact.effective_output
    assert '"backgroundColor":"#FFE84026"' in compact.effective_output
    assert '"fillColor":"#FFFFFFFF"' in compact.effective_output
    assert wide.effective_output.count('"backgroundColor":"#14000000"') == 3
    assert '"layoutWeight":3' in wide.effective_output
    assert '"layoutWeight":2' in wide.effective_output

    with pytest.raises(TerseDslNested2ConversionError, match="child count is invalid"):
        _compile_direct_layout(
            'WeatherNowForecastLayout(Text("当前天气", "body"), Text("明日", "body"));',
            layout_id="WeatherNowForecastLayout",
            size="2x2",
            literals=("当前天气", "明日"),
        )


@pytest.mark.parametrize(
    ("source", "message"),
    [
        (
            'HeroActionLayout(PillAction({"actionId":"event.open"}), Text("业务摘要", "body"));',
            "final child",
        ),
        (
            'HeroActionLayout(Text("业务摘要", "body"));',
            "requires one embedded Action",
        ),
        (
            'HeroActionLayout(Text("业务摘要", "body"), PillAction({"actionId":"event.evil"}));',
            "not approved",
        ),
    ],
)
def test_direct_ux_layout_action_contract_fails_closed(source: str, message: str):
    with pytest.raises(TerseDslNested2ConversionError, match=message):
        compile_ux_layout_card(
            source,
            task_spec=_ux_layout_task(with_action=True),
            contract=_ux_layout_root_contract("HeroActionLayout", action_id="event.open"),
            protocol_profile=A2UIProtocolRegistry.read_design_protocol_profile(
                TERSE_DSL_NESTED2_PROFILE_ID
            ),
            registry=get_cardplan_registry(),
        )


def test_ux_layout_rejects_child_budget_overflow():
    source = (
        'Template("card@1", {}, SingleFocusLayout('
        'Text("业务摘要", "body"), Text("业务摘要", "body")));'
    )

    with pytest.raises(TerseDslNested2ConversionError, match="child count is invalid"):
        compile_hybrid_card(
            source,
            task_spec=_ux_layout_task(with_action=False),
            contract=_ux_layout_contract("SingleFocusLayout", with_action=False),
            protocol_profile=A2UIProtocolRegistry.read_design_protocol_profile(
                TERSE_DSL_NESTED2_PROFILE_ID
            ),
            registry=get_cardplan_registry(),
        )


def test_ux_layout_rejects_required_action_missing_from_card_shell():
    source = 'Template("card@1", {}, HeroActionLayout(Text("业务摘要", "body")));'

    with pytest.raises(TerseDslNested2ConversionError, match="requires the card@1"):
        compile_hybrid_card(
            source,
            task_spec=_ux_layout_task(with_action=True),
            contract=_ux_layout_contract("HeroActionLayout", with_action=True),
            protocol_profile=A2UIProtocolRegistry.read_design_protocol_profile(
                TERSE_DSL_NESTED2_PROFILE_ID
            ),
            registry=get_cardplan_registry(),
        )


def test_ux_layout_rejects_nested_layout_components():
    source = (
        'Template("card@1", {}, HeroSupportLayout('
        'SingleFocusLayout(Text("业务摘要", "body")), Text("业务摘要", "body")));'
    )
    contract = _ux_layout_contract("HeroSupportLayout", with_action=False).model_copy(
        update={
            "allowed_components": (
                *_ux_layout_contract(
                    "HeroSupportLayout",
                    with_action=False,
                ).allowed_components,
                "SingleFocusLayout",
            )
        }
    )

    with pytest.raises(TerseDslNested2ConversionError, match="cannot be nested"):
        compile_hybrid_card(
            source,
            task_spec=_ux_layout_task(with_action=False),
            contract=contract,
            protocol_profile=A2UIProtocolRegistry.read_design_protocol_profile(
                TERSE_DSL_NESTED2_PROFILE_ID
            ),
            registry=get_cardplan_registry(),
        )


def _sample_schema(value: object) -> object:
    if isinstance(value, dict):
        return {key: _sample_schema(child) for key, child in value.items()}
    if isinstance(value, list):
        return [_sample_schema(value[0])] if value else []
    data_type = "boolean" if isinstance(value, bool) else "number"
    if not isinstance(value, (bool, int, float)):
        data_type = "string"
    return {
        "type": data_type,
        "description": "Golden sample",
        "sampleValue": value,
    }


def _scenario_inputs(scenario: dict) -> tuple[TaskSpec, dict, UIBrief]:
    data = {item["capabilityId"]: item["dataSlice"] for item in scenario["dataEntries"]}
    task_spec = TaskSpec(
        userQuery=scenario["userQuery"],
        size=scenario["cardSize"],
        eventCandidates=[
            EventAction(
                id=action_id,
                displayLabel=label,
                call="fixtureAction",
                args={},
            )
            for action_id, label in scenario["eventDisplayLabels"].items()
        ],
        dataModelSchema={"data": _sample_schema(data)},
        assetCandidates=scenario["assets"],
    )
    capability_ids = {item["capabilityId"] for item in scenario["dataEntries"]}
    if (
        "GetAppUsageDuration" in capability_ids
        and extract_app_usage_overview_facts(task_spec.dataModelSchema) is not None
    ):
        task_spec = project_content_component_facts(
            task_spec,
            capability_ids,
            ("AppUsageOverview",),
        )
    card_spec = {
        "title": scenario["title"],
        "description": scenario["description"],
        "suggestSize": scenario["cardSize"],
    }
    ui_brief = UIBrief(
        purpose="Golden cross-language regression",
        primaryInformation=[scenario["description"]],
        informationHierarchy=["main", "action"],
        visualTone="fixture-derived",
        themeId=scenario["cardTemplate"]["themeProfileId"],
        themeSemantics=[scenario["cardTemplate"]["themeProfileId"]],
        layoutSemantics=["compact 2x2"],
        localTemplateIds=[
            item for item in scenario["cardTemplate"]["requestTemplateIds"] if item != "card@1"
        ],
        contentPriorities=["preserve supplied facts"],
        reason="Exercise the Python port against the exported TypeScript baseline.",
    )
    return task_spec, card_spec, ui_brief


def _compile_scenario(scenario: dict):
    task_spec, card_spec, ui_brief = _scenario_inputs(scenario)
    registry = get_cardplan_registry()
    projection = build_hybrid_prompt(
        task_spec=task_spec,
        card_spec=card_spec,
        ui_brief=ui_brief,
        registry=registry,
    )
    profile = A2UIProtocolRegistry.read_design_protocol_profile(TERSE_DSL_NESTED2_PROFILE_ID)
    result = compile_hybrid_card(
        scenario["rawHybridSource"],
        task_spec=task_spec,
        contract=projection.contract,
        protocol_profile=profile,
        registry=registry,
    )
    return result, task_spec, projection


def test_generated_prompt_bundle_has_no_drift() -> None:
    subprocess.run(
        [sys.executable, "scripts/build_cardplan_bundle.py", "--check"],
        cwd=SERVICE_ROOT,
        check=True,
    )


def test_theme_registry_matches_ux_color_style_matrix() -> None:
    registry = get_cardplan_registry()
    expected = {
        "family-weather-care-blue": (
            "text-on-accent",
            "#FF317AF7",
            ("#FF317AF7", "#FF46B1E3"),
        ),
        "rainy-commute-gray-blue": (
            "text-on-accent",
            "#FF46484D",
            ("#FF46484D", "#FF467794"),
        ),
        "sleep-night-violet": (
            "text-on-accent",
            "#FFAC49F5",
            ("#FFAC49F5", "#FFC386F0"),
        ),
        "race-sunrise-action": (
            "text-on-accent",
            "#FFED6F21",
            ("#FFED6F21", "#FFF9A01E"),
        ),
        "device-clean-blue-teal": (
            "text-primary",
            "#FFFFFFFF",
            ("#1A0A59F7", "#00FFFFFF"),
        ),
        "system-low-power-blue": (
            "text-primary",
            "#FFFFFFFF",
            ("#1AF9A01E", "#00FFFFFF"),
        ),
        "audio-product-neutral-violet": (
            "text-primary",
            "#FFFFFFFF",
            ("#1A64BB5C", "#00FFFFFF"),
        ),
        "meeting-paper-neutral": (
            "text-primary",
            "#FFFFFFFF",
            ("#1AE84026", "#00FFFFFF"),
        ),
    }

    for theme_id, (text_role, background, gradient_colors) in expected.items():
        theme = registry.require_theme(theme_id)
        assert theme.text_role == text_role
        assert theme.root_styles["backgroundColor"] == background
        assert tuple(
            item[0] for item in theme.root_styles["linearGradient"]["colors"]
        ) == gradient_colors


@pytest.mark.parametrize(
    (
        "template_id",
        "theme_id",
        "source",
        "literals",
        "assets",
        "asset_tags",
        "expected_styles",
    ),
    [
        (
            "ux-weather-overview@2",
            "family-weather-care-blue",
            'SingleFocusLayout(Template("ux-weather-overview@2", "medium", '
            '{"city":"深圳","conditionIcon":"resources/base/media/weather.svg",'
            '"temperature":"38°","condition":"晴","airQuality":"空气优",'
            '"temperatureRange":"26° / 16°"}));',
            ("深圳", "38°", "晴", "空气优", "26° / 16°"),
            ("resources/base/media/weather.svg",),
            {"resources/base/media/weather.svg": ("condition", "weather")},
            ('"fontSize":38', '"width":56', '"fontSize":14'),
        ),
        (
            "ux-date-overview@2",
            "meeting-paper-neutral",
            'SingleFocusLayout(Template("ux-date-overview@2", "hero", '
            '{"date":"27日","weekday":"星期一"}));',
            ("27日", "星期一"),
            (),
            {},
            ('"fontSize":30', '"fontSize":14'),
        ),
    ],
)
def test_v2_content_templates_follow_ux_type_scale_and_compile_without_leak(
    template_id: str,
    theme_id: str,
    source: str,
    literals: tuple[str, ...],
    assets: tuple[str, ...],
    asset_tags: dict[str, tuple[str, ...]],
    expected_styles: tuple[str, ...],
) -> None:
    task_spec = TaskSpec(
        userQuery="内容高级组件",
        size="2x2",
        dataModelSchema={"data": {}},
        assetCandidates=[],
    )
    result = compile_ux_layout_card(
        source,
        task_spec=task_spec,
        contract=_content_template_contract(
            template_id,
            theme_id,
            literals,
            assets=assets,
            asset_tags=asset_tags,
        ),
        protocol_profile=A2UIProtocolRegistry.read_design_protocol_profile(
            TERSE_DSL_NESTED2_PROFILE_ID
        ),
        registry=get_cardplan_registry(),
    )

    assert result.stats.template_used_ids == (template_id,)
    assert "Template" not in result.effective_output
    assert "Template" not in result.a2ui
    assert all(style in result.effective_output for style in expected_styles)


@pytest.mark.parametrize(
    ("template_id", "theme_id", "source", "literals", "numbers", "assets", "tags", "style"),
    [
        (
            "ux-battery-overview@2",
            "system-low-power-blue",
            'SingleFocusLayout(Template("ux-battery-overview@2", "medium", '
            '{"batterySOC":0,"batterySOCText":"0%",'
            '"batteryCapacityLevelDesc":"电量低","chargingStatusDesc":"未充电",'
            '"batteryIcon":"resources/base/media/battery.svg"}));',
            ("0%", "电量低", "未充电"),
            (0,),
            ("resources/base/media/battery.svg",),
            {"resources/base/media/battery.svg": ("battery", "power")},
            '"width":52',
        ),
        (
            "ux-app-usage-overview@2",
            "digital-wellbeing-neutral-dark",
            'SingleFocusLayout(Template("ux-app-usage-overview@2", "medium", '
            '{"appName":"示例应用","durationText":"3小时45分钟",'
            '"durationPrimaryValueText":"3","durationPrimaryUnitText":"小时",'
            '"durationSecondaryValueText":"45","durationSecondaryUnitText":"分钟",'
            '"updatedAt":"2026-08-11 10:00"}));',
            ("示例应用", "3小时45分钟", "3", "小时", "45", "分钟", "2026-08-11 10:00"),
            (),
            (),
            {},
            '"fontSize":30',
        ),
        (
            "ux-activity-overview@2",
            "meeting-paper-neutral",
            'SingleFocusLayout(Template("ux-activity-overview@2", "medium", '
            '{"dailySteps":6320,"dailyTotalCaloriesText":"998 千卡",'
            '"dailyDistanceText":"5.42 公里"}));',
            ("998 千卡", "5.42 公里"),
            (6320,),
            (),
            {},
            '"fontSize":38',
        ),
        (
            "ux-workout-overview@2",
            "meeting-paper-neutral",
            'SingleFocusLayout(Template("ux-workout-overview@2", "medium", '
            '{"exerciseTypeName":"户外跑步","exerciseDurationText":"40分",'
            '"exerciseCalorieText":"298 千卡"}));',
            ("户外跑步", "40分", "298 千卡"),
            (),
            (),
            {},
            '"fontSize":30',
        ),
        (
            "ux-workout-overview@2",
            "race-sunrise-action",
            'SingleFocusLayout(Template("ux-workout-overview@2", "hero", {"countdownDays":32}));',
            (),
            (32,),
            (),
            {},
            '"fontSize":38',
        ),
        (
            "ux-heart-rate-overview@2",
            "meeting-paper-neutral",
            'SingleFocusLayout(Template("ux-heart-rate-overview@2", "small", '
            '{"exerciseHeartRateAvg":132,"updatedAt":"2026-08-11 10:00"}));',
            ("2026-08-11 10:00",),
            (132,),
            (),
            {},
            '"fontSize":30',
        ),
        (
            "ux-sleep-overview@2",
            "sleep-night-violet",
            'SingleFocusLayout(Template("ux-sleep-overview@2", "medium", '
            '{"sleepStatus":"睡眠不足","nightSleepDurationText":"5小时45分",'
            '"sleepDurationPrimaryValueText":"5","sleepDurationPrimaryUnitText":"小时",'
            '"sleepDurationSecondaryValueText":"45",'
            '"sleepDurationSecondaryUnitText":"分钟",'
            '"fallAsleepTimeText":"23:15","wakeupTimeText":"05:00"}));',
            ("睡眠不足", "5小时45分", "5", "小时", "45", "分钟", "23:15", "05:00"),
            (),
            (),
            {},
            '"fontSize":30',
        ),
        (
            "ux-bluetooth-overview@2",
            "audio-product-neutral-violet",
            'SingleFocusLayout(Template("ux-bluetooth-overview@2", "medium", '
            '{"earphoneName":"FreeBuds Pro 3","leftBatteryLevel":0,'
            '"rightBatteryLevel":74,"batteryLevel":80}));',
            ("FreeBuds Pro 3",),
            (0, 74, 80),
            (),
            {},
            '"width":44',
        ),
        (
            "ux-resource-usage-overview@2",
            "device-clean-blue-teal",
            'SingleFocusLayout(Template("ux-resource-usage-overview@2", "medium", '
            '{"usagePercent":43.75,"availableMemText":"4.50 GB",'
            '"totalMemText":"8.00 GB"}));',
            ("4.50 GB", "8.00 GB"),
            (43.75,),
            (),
            {},
            '"width":52',
        ),
    ],
)
def test_provider_backed_v2_content_templates_compile_strict_values(
    template_id: str,
    theme_id: str,
    source: str,
    literals: tuple[str, ...],
    numbers: tuple[int | float, ...],
    assets: tuple[str, ...],
    tags: dict[str, tuple[str, ...]],
    style: str,
) -> None:
    result = compile_ux_layout_card(
        source,
        task_spec=TaskSpec(
            userQuery="真实数据内容组件",
            size="2x2",
            dataModelSchema={"data": {}},
            assetCandidates=[],
        ),
        contract=_content_template_contract(
            template_id,
            theme_id,
            literals,
            assets=assets,
            asset_tags=tags,
            numbers=numbers,
        ),
        protocol_profile=A2UIProtocolRegistry.read_design_protocol_profile(
            TERSE_DSL_NESTED2_PROFILE_ID
        ),
        registry=get_cardplan_registry(),
    )

    assert result.stats.template_used_ids == (template_id,)
    assert "Template" not in result.a2ui
    assert style in result.effective_output


@pytest.mark.parametrize(
    ("template_id", "theme_id", "parameters", "literals"),
    [
        (
            "ux-task-overview@2",
            "meeting-paper-neutral",
            '{"title":"提交方案","status":"待完成","dueText":"今天 18:00"}',
            ("提交方案", "待完成", "今天 18:00"),
        ),
        (
            "ux-memo-preview@2",
            "meeting-paper-neutral",
            '{"title":"会议记录","body":"确认下一步任务","updatedText":"10分钟前更新"}',
            ("会议记录", "确认下一步任务", "10分钟前更新"),
        ),
        (
            "ux-call-overview@2",
            "meeting-paper-neutral",
            '{"contactName":"张先生","phoneMasked":"138****0000",'
            '"status":"未接","timeText":"10:30"}',
            ("张先生", "138****0000", "未接", "10:30"),
        ),
        (
            "ux-location-overview@2",
            "meeting-paper-neutral",
            '{"label":"上次位置","city":"深圳市龙岗区","updatedText":"10分钟前更新"}',
            ("上次位置", "深圳市龙岗区", "10分钟前更新"),
        ),
        (
            "ux-system-mode-overview@2",
            "focus-warm-amber",
            '{"focusName":"工作专注","audioMode":"静音","focusEndText":"18:00结束"}',
            ("工作专注", "静音", "18:00结束"),
        ),
        (
            "ux-settings-overview@2",
            "meeting-paper-neutral",
            '{"label":"免打扰","valueText":"已开启","detail":"18:00结束"}',
            ("免打扰", "已开启", "18:00结束"),
        ),
    ],
)
def test_provider_gated_v2_content_templates_have_deterministic_compilers(
    template_id: str,
    theme_id: str,
    parameters: str,
    literals: tuple[str, ...],
) -> None:
    result = compile_ux_layout_card(
        f'SingleFocusLayout(Template("{template_id}", "small", {parameters}));',
        task_spec=TaskSpec(
            userQuery="受控内容组件编译",
            size="2x2",
            dataModelSchema={"data": {}},
            assetCandidates=[],
        ),
        contract=_content_template_contract(template_id, theme_id, literals),
        protocol_profile=A2UIProtocolRegistry.read_design_protocol_profile(
            TERSE_DSL_NESTED2_PROFILE_ID
        ),
        registry=get_cardplan_registry(),
    )

    assert result.stats.template_used_ids == (template_id,)
    assert "Template" not in result.a2ui
    assert '"fontSize":14' in result.effective_output
    assert '"fontSize":10' in result.effective_output
    messages = [json.loads(line) for line in result.a2ui.splitlines()]
    components = messages[1]["updateComponents"]["components"]
    by_id = {component["id"]: component for component in components}
    root = by_id[messages[1]["updateComponents"]["root"]]
    layout_root = by_id[root["children"][0]]
    template_root = by_id[layout_root["children"][0]]
    assert template_root["component"] == "Column"
    assert template_root["styles"]["justifyContent"] == "start"
    assert by_id[template_root["children"][0]]["component"] == "Text"


def test_call_template_rejects_unmasked_phone_number() -> None:
    source = (
        'SingleFocusLayout(Template("ux-call-overview@2", "small", '
        '{"contactName":"张先生","phoneMasked":"13812340000",'
        '"status":"未接","timeText":"10:30"}));'
    )

    with pytest.raises(TerseDslNested2ConversionError, match="does not match"):
        compile_ux_layout_card(
            source,
            task_spec=TaskSpec(
                userQuery="最近来电",
                size="2x2",
                dataModelSchema={"data": {}},
                assetCandidates=[],
            ),
            contract=_content_template_contract(
                "ux-call-overview@2",
                "meeting-paper-neutral",
                ("张先生", "13812340000", "未接", "10:30"),
            ),
            protocol_profile=A2UIProtocolRegistry.read_design_protocol_profile(
                TERSE_DSL_NESTED2_PROFILE_ID
            ),
            registry=get_cardplan_registry(),
        )


def test_parser_wraps_single_local_template_content_in_trusted_column() -> None:
    parsed = parse_hybrid_card(
        'Template("card@1", {}, Template("ux-countdown@1", "small", '
        '{"label": "距离开始", "value": "2天"}));'
    )

    assert parsed.children[0].kind == "component"
    assert parsed.children[0].name == "Column"
    assert parsed.children[0].values == ()
    assert parsed.children[0].children[0].kind == "template"
    assert parsed.children[0].children[0].name == "ux-countdown@1"


def test_compact_container_normalizes_nested_title_role() -> None:
    normalized = _compact_text_roles(
        Nested2Node(
            "Column",
            (),
            (Nested2Node("Text", ("项目阶段性汇报", "title"), ()),),
        )
    )

    assert normalized.children[0].values == ("项目阶段性汇报", "compact-title")


def test_registry_fails_closed_on_source_sha_drift(tmp_path: Path) -> None:
    source = SERVICE_ROOT / "cloud/data/cardplan_template/source"
    copied = tmp_path / "source"
    shutil.copytree(source, copied)
    registry_path = copied / "template-registry.json"
    registry_path.write_text(registry_path.read_text() + " ", encoding="utf-8")

    with pytest.raises(ValueError, match="file drift"):
        CardPlanRegistry(copied)


def test_all_ten_cross_language_golden_programs_compile_without_template_leak() -> None:
    payload = json.loads(GOLDEN_FIXTURE.read_text(encoding="utf-8"))
    assert len(payload["scenarios"]) == 10
    for scenario in payload["scenarios"]:
        result, _task_spec, projection = _compile_scenario(scenario)
        assert result.fallback_used is False
        assert result.stats.template_call_count >= 2
        used_ids = set(result.stats.template_used_ids)
        assert used_ids.issubset(set(projection.requested_template_ids))
        golden_local_ids = {
            item for item in scenario["cardTemplate"]["requestTemplateIds"] if item != "card@1"
        }
        assert golden_local_ids.issubset(used_ids)
        assert "Template" not in result.effective_output
        assert "Template" not in result.a2ui
        rows = [json.loads(line) for line in result.a2ui.splitlines()]
        assert [next(key for key in row if key != "version") for row in rows] == [
            "createSurface",
            "updateComponents",
            "updateDataModel",
        ]
        assert all(row["version"] == "v0.9" for row in rows)


def test_focus_golden_keeps_required_title_in_card_chrome_only() -> None:
    scenario = next(
        item
        for item in json.loads(GOLDEN_FIXTURE.read_text(encoding="utf-8"))["scenarios"]
        if item["id"] == "focus-mode"
    )

    result, _task_spec, _projection = _compile_scenario(scenario)

    assert result.effective_output.count('"下一个日程"') == 1
    assert (
        'Image("resources/base/media/icon_schedule.svg", "compact-icon")' in result.effective_output
    )
    assert result.stats.space_constrained is False


def test_compiler_appends_missing_must_keep_literals_without_model_retry() -> None:
    scenario = next(
        item
        for item in json.loads(GOLDEN_FIXTURE.read_text(encoding="utf-8"))["scenarios"]
        if item["id"] == "family-care-weather"
    )
    task_spec, card_spec, ui_brief = _scenario_inputs(scenario)
    ui_brief = ui_brief.model_copy(update={"action_placement": "none"})
    projection = build_hybrid_prompt(
        task_spec=task_spec,
        card_spec=card_spec,
        ui_brief=ui_brief,
        registry=get_cardplan_registry(),
    )
    result = compile_hybrid_card(
        'Template("card@1", {}, Column("section", Text("31°", "title")));',
        task_spec=task_spec,
        contract=projection.contract,
        protocol_profile=A2UIProtocolRegistry.read_design_protocol_profile(
            TERSE_DSL_NESTED2_PROFILE_ID
        ),
        registry=get_cardplan_registry(),
    )

    assert "高温预警" not in result.raw_output
    assert "高温预警" in result.effective_output
    assert result.fallback_used is False


def test_missing_short_peer_facts_share_one_compact_row() -> None:
    contract = _ux_layout_contract("SingleFocusLayout", with_action=False).model_copy(
        update={
            "trusted_literals": ("深圳", "空气优", "26°", "16°"),
            "required_literals": ("深圳", "空气优", "26°", "16°"),
        }
    )
    content = Nested2Node(
        "Column",
        ("compact",),
        (Nested2Node("Text", ("深圳", "body"), ()),),
    )

    result = _append_missing_required_literals(content, contract)

    peer_row = result.children[-1]
    assert peer_row.component_type == "Row"
    assert {child.values[0] for child in peer_row.children} == {"空气优", "26°", "16°"}
    assert any(isinstance(value, dict) and value.get("height") == 18 for value in peer_row.values)


def test_segmented_required_duration_is_not_reappended_as_duplicate_text() -> None:
    contract = _ux_layout_contract("SingleFocusLayout", with_action=False).model_copy(
        update={
            "trusted_literals": ("5小时45分钟", "5", "小时", "45", "分钟"),
            "required_literals": ("5小时45分钟",),
        }
    )
    content = Nested2Node(
        "Row",
        ("between",),
        tuple(Nested2Node("Text", (item, "body"), ()) for item in ("5", "小时", "45", "分钟")),
    )

    result = _append_missing_required_literals(content, contract)

    assert result == content


def test_optional_subtitle_is_reclaimed_without_removing_card_title() -> None:
    contract = _ux_layout_contract("HeroActionLayout", with_action=True)
    content = Nested2Node(
        "Column",
        ("compact", {"height": 60}),
        (Nested2Node("Text", ("业务摘要", "body"), ()),),
    )
    params = {
        "title": "可选标题",
        "subtitle": "可选副标题",
        "action": {"label": "打开", "id": "event.open"},
    }

    result = _reclaim_optional_chrome_for_content(
        params,
        content,
        contract,
        get_cardplan_registry(),
    )

    assert result["title"] == params["title"]
    assert "subtitle" not in result
    assert result["action"] == params["action"]


def test_compiler_deduplicates_text_only_up_to_independent_fact_count() -> None:
    scenario = next(
        item
        for item in json.loads(GOLDEN_FIXTURE.read_text(encoding="utf-8"))["scenarios"]
        if item["id"] == "family-care-weather"
    )
    task_spec, card_spec, ui_brief = _scenario_inputs(scenario)
    ui_brief = ui_brief.model_copy(update={"action_placement": "none"})
    projection = build_hybrid_prompt(
        task_spec=task_spec,
        card_spec=card_spec,
        ui_brief=ui_brief,
        registry=get_cardplan_registry(),
    )
    result = compile_hybrid_card(
        'Template("card@1", {}, Column("section", Text("高温预警", "warning"), '
        'Text("高温预警", "warning")));',
        task_spec=task_spec,
        contract=projection.contract,
        protocol_profile=A2UIProtocolRegistry.read_design_protocol_profile(
            TERSE_DSL_NESTED2_PROFILE_ID
        ),
        registry=get_cardplan_registry(),
    )
    update = json.loads(result.a2ui.splitlines()[1])["updateComponents"]
    visible = [
        item.get("content") for item in update["components"] if item.get("component") == "Text"
    ]

    assert visible.count("高温预警") == 1


def test_text_on_accent_theme_applies_to_card_chrome_and_standard_text() -> None:
    scenario = next(
        item
        for item in json.loads(GOLDEN_FIXTURE.read_text(encoding="utf-8"))["scenarios"]
        if item["id"] == "sleep"
    )
    result, _task_spec, _projection = _compile_scenario(scenario)
    update = json.loads(result.a2ui.splitlines()[1])["updateComponents"]
    text_by_content = {
        item.get("content"): item.get("styles", {})
        for item in update["components"]
        if item.get("component") == "Text"
    }

    assert text_by_content["睡眠不足"]["fontColor"] == "#FFFFFFFF"
    assert text_by_content["设置早睡提醒"]["fontColor"] == "#FFAC49F5"


def test_device_clean_theme_applies_trusted_card_action_style() -> None:
    scenario = next(
        item
        for item in json.loads(GOLDEN_FIXTURE.read_text(encoding="utf-8"))["scenarios"]
        if item["id"] == "device-clean"
    )
    result, _task_spec, _projection = _compile_scenario(scenario)
    update = json.loads(result.a2ui.splitlines()[1])["updateComponents"]
    text_by_content = {
        item.get("content"): item.get("styles", {})
        for item in update["components"]
        if item.get("component") == "Text"
    }

    assert text_by_content["一键清理"]["fontColor"] == "#FF0A59F7"
    action_stack = next(
        item
        for item in update["components"]
        if item.get("component") == "Stack" and item.get("onClick")
    )
    assert action_stack["styles"]["height"] == 28
    assert action_stack["styles"]["borderRadius"] == 14
    assert action_stack["styles"]["backgroundColor"] == "#1A0A59F7"


def test_white_theme_local_templates_keep_business_text_readable() -> None:
    scenarios = json.loads(GOLDEN_FIXTURE.read_text(encoding="utf-8"))["scenarios"]
    focus = next(item for item in scenarios if item["id"] == "focus-mode")
    low_power = next(item for item in scenarios if item["id"] == "low-power")

    _base_result, focus_task_spec, focus_projection = _compile_scenario(focus)
    focus_result = compile_hybrid_card(
        'Template("card@1", {action: {label: "专注模式", '
        'id: "event.open.settings.dnd"}}, Column("section", '
        'Template("ux-calendar-content@1", "hero", '
        '{title: "Agent需求评审会", time: "14:00–15:30", '
        'status: "还有15分钟开启", '
        'alarmIcon: "resources/base/media/ux_golden_asset_time_yellow.svg"})));',
        task_spec=focus_task_spec,
        contract=focus_projection.contract,
        protocol_profile=A2UIProtocolRegistry.read_design_protocol_profile(
            TERSE_DSL_NESTED2_PROFILE_ID
        ),
        registry=get_cardplan_registry(),
    )
    focus_update = json.loads(focus_result.a2ui.splitlines()[1])["updateComponents"]
    focus_styles = [
        (item.get("content"), item.get("styles", {}))
        for item in focus_update["components"]
        if item.get("component") == "Text"
    ]
    assert any(styles.get("fontColor") == "#FF1A1A1A" for _text, styles in focus_styles)
    assert any(
        text == "14:00–15:30"
        and styles.get("fontColor") == "#FF1A1A1A"
        and styles.get("fontSize") == 14
        for text, styles in focus_styles
    )

    low_result, _task_spec, _projection = _compile_scenario(low_power)
    low_update = json.loads(low_result.a2ui.splitlines()[1])["updateComponents"]
    low_styles = {
        item.get("content"): item.get("styles", {})
        for item in low_update["components"]
        if item.get("component") == "Text"
    }
    assert low_styles["18%"]["fontColor"] == "#FF1A1A1A"
    assert low_styles["手机电量低于"]["fontColor"] == "#FF6B6B6B"


@pytest.mark.parametrize(
    ("source", "message"),
    [
        ('__import__("os")', "Unsupported component"),
        ('Template("card@1", {}, Column("section"));', "Raw container"),
        ('Template("card@1", {}, Column("section", Text("伪造", "body")));', "trusted"),
        (
            'Template("card@1", {}, Column("section", '
            'Button("打开详情", "primary", {onClick: [{call: "evil", args: {}}]})));',
            "Direct events",
        ),
        (
            'Template("card@1", {}, Column("section", Template("missing@1", "small", {})));',
            "not allowed",
        ),
    ],
)
def test_illegal_hybrid_inputs_fail_closed(source: str, message: str) -> None:
    scenario = json.loads(GOLDEN_FIXTURE.read_text(encoding="utf-8"))["scenarios"][0]
    _result, task_spec, projection = _compile_scenario(scenario)
    profile = A2UIProtocolRegistry.read_design_protocol_profile(TERSE_DSL_NESTED2_PROFILE_ID)
    with pytest.raises(TerseDslNested2ConversionError, match=message):
        compile_hybrid_card(
            source,
            task_spec=task_spec,
            contract=projection.contract,
            protocol_profile=profile,
            registry=get_cardplan_registry(),
        )


def test_template_schema_and_asset_validation_fail_closed() -> None:
    scenario = json.loads(GOLDEN_FIXTURE.read_text(encoding="utf-8"))["scenarios"][0]
    _result, task_spec, projection = _compile_scenario(scenario)
    profile = A2UIProtocolRegistry.read_design_protocol_profile(TERSE_DSL_NESTED2_PROFILE_ID)
    invalid = scenario["rawHybridSource"].replace(
        '"resources/base/media/ux_golden_asset_time_beige.svg"',
        '"resources/base/media/unapproved.svg"',
    )
    with pytest.raises(TerseDslNested2ConversionError, match="asset is not approved"):
        compile_hybrid_card(
            invalid,
            task_spec=task_spec,
            contract=projection.contract,
            protocol_profile=profile,
            registry=get_cardplan_registry(),
        )


def test_space_fit_sheds_optional_card_chrome_before_clipping() -> None:
    payload = json.loads(GOLDEN_FIXTURE.read_text(encoding="utf-8"))
    scenario = next(item for item in payload["scenarios"] if item["id"] == "headset-music")
    result, _task_spec, _projection = _compile_scenario(scenario)
    assert result.stats.space_constrained is False
    assert result.stats.estimated_height_vp <= result.stats.vertical_budget_vp
    assert 'Text("蓝牙耳机", "compact-title")' not in result.effective_output
    assert "ux-audio-device-status@1" in result.stats.template_used_ids


def test_card_shell_uniquely_owns_title_and_primary_action() -> None:
    payload = json.loads(GOLDEN_FIXTURE.read_text(encoding="utf-8"))
    scenario = next(item for item in payload["scenarios"] if item["id"] == "sleep")
    _result, task_spec, projection = _compile_scenario(scenario)
    profile = A2UIProtocolRegistry.read_design_protocol_profile(TERSE_DSL_NESTED2_PROFILE_ID)
    duplicated = scenario["rawHybridSource"].replace(
        'Column("section", Template(',
        'Column("section", Text("睡眠不足", "body"), Text("设置早睡提醒", "body"), Template(',
        1,
    )

    result = compile_hybrid_card(
        duplicated,
        task_spec=task_spec,
        contract=projection.contract,
        protocol_profile=profile,
        registry=get_cardplan_registry(),
    )

    assert result.effective_output.count('"睡眠不足"') == 1
    assert result.effective_output.count('"设置早睡提醒"') == 1
    assert 'Text("睡眠不足", "compact-title"' in result.effective_output
    assert result.effective_output.index('Text("睡眠不足"') < result.effective_output.index(
        'Text("设置早睡提醒"'
    )


def test_card_composed_title_owns_direct_fact_atoms_without_reappending() -> None:
    task_spec = TaskSpec(
        userQuery="会议日期",
        size="2x2",
        eventCandidates=[],
        dataModelSchema={
            "data": {
                "date": {"type": "string", "sampleValue": "27"},
                "weekday": {"type": "string", "sampleValue": "星期一"},
                "subject": {"type": "string", "sampleValue": "会议"},
            }
        },
        assetCandidates=[],
    )
    contract = _ux_layout_contract("SingleFocusLayout", with_action=False).model_copy(
        update={
            "trusted_literals": ("27日 星期一", "27", "星期一", "会议"),
            "required_literals": ("27", "星期一", "会议"),
            "protected_literals": ("27", "星期一", "会议"),
        }
    )
    source = (
        'Template("card@1", {"title":"27日 星期一"}, '
        'SingleFocusLayout(Column("section", Text("27", "body"), '
        'Text("星期一", "body"), Text("会议", "body"))));'
    )

    result = compile_hybrid_card(
        source,
        task_spec=task_spec,
        contract=contract,
        protocol_profile=A2UIProtocolRegistry.read_design_protocol_profile(
            TERSE_DSL_NESTED2_PROFILE_ID
        ),
        registry=get_cardplan_registry(),
    )

    assert result.effective_output.count('Text("27日 星期一"') == 1
    assert 'Text("27",' not in result.effective_output
    assert 'Text("星期一",' not in result.effective_output
    assert 'Text("会议",' in result.effective_output


def test_atomic_template_keeps_matching_context_while_redundant_chrome_is_dropped() -> None:
    payload = json.loads(GOLDEN_FIXTURE.read_text(encoding="utf-8"))
    scenario = next(item for item in payload["scenarios"] if item["id"] == "rainy-commute")
    _result, task_spec, projection = _compile_scenario(scenario)
    profile = A2UIProtocolRegistry.read_design_protocol_profile(TERSE_DSL_NESTED2_PROFILE_ID)
    source = scenario["rawHybridSource"].replace(
        '{"action":',
        '{"title":"项目阶段性汇报","subtitle":"项目阶段性汇报","action":',
        1,
    )

    result = compile_hybrid_card(
        source,
        task_spec=task_spec,
        contract=projection.contract,
        protocol_profile=profile,
        registry=get_cardplan_registry(),
    )

    assert result.effective_output.count('"项目阶段性汇报"') == 1
    assert 'Text("项目阶段性汇报", "compact-title"' not in result.effective_output
    assert 'Text("项目阶段性汇报", "subtitle"' not in result.effective_output
    assert "ux-context-summary@1" in result.stats.template_used_ids


def test_card_subtitle_composed_entirely_from_template_text_is_dropped() -> None:
    payload = json.loads(GOLDEN_FIXTURE.read_text(encoding="utf-8"))
    scenario = next(item for item in payload["scenarios"] if item["id"] == "device-clean")
    _result, task_spec, projection = _compile_scenario(scenario)
    profile = A2UIProtocolRegistry.read_design_protocol_profile(TERSE_DSL_NESTED2_PROFILE_ID)
    source = scenario["rawHybridSource"].replace(
        '{"action":',
        '{"subtitle":"内存已使用87%","action":',
        1,
    )

    result = compile_hybrid_card(
        source,
        task_spec=task_spec,
        contract=projection.contract,
        protocol_profile=profile,
        registry=get_cardplan_registry(),
    )

    assert 'Text("内存已使用87%", "subtitle"' not in result.effective_output
    assert 'Text("内存已使用"' in result.effective_output
    assert 'Text("87%"' in result.effective_output


def test_template_asset_semantics_repair_approved_wrong_role_when_unique() -> None:
    payload = json.loads(GOLDEN_FIXTURE.read_text(encoding="utf-8"))
    scenario = next(item for item in payload["scenarios"] if item["id"] == "headset-music")
    _result, task_spec, projection = _compile_scenario(scenario)
    profile = A2UIProtocolRegistry.read_design_protocol_profile(TERSE_DSL_NESTED2_PROFILE_ID)
    invalid = scenario["rawHybridSource"].replace(
        '"resources/base/media/ux_golden_asset_headset_product.png"',
        '"resources/base/media/ux_golden_asset_music_purple.svg"',
    )
    result = compile_hybrid_card(
        invalid,
        task_spec=task_spec,
        contract=projection.contract,
        protocol_profile=profile,
        registry=get_cardplan_registry(),
    )

    assert "resources/base/media/ux_golden_asset_headset_product.png" in result.a2ui
    assert result.fallback_used is False


def test_event_display_label_survives_request_normalization() -> None:
    request = GenerateWidgetCardRequest(
        uid="test-user",
        device={"romVersion": "6.0"},
        userQuery="设置早睡提醒",
        title="睡眠",
        description="睡眠计划",
        candidateEventCandidates=[
            {
                "capabilityId": "event.open.health.sleep",
                "action": {
                    "displayLabel": "设置早睡提醒",
                    "call": "clickToApi",
                    "args": {},
                },
            }
        ],
    )

    events = WidgetGenerationService()._normalize_event_candidates(request)

    assert events[0].displayLabel == "设置早睡提醒"


def test_stream_framer_accepts_random_chunks_and_rejects_partial_or_crossed() -> None:
    source = 'Template("card@1", {}, Column("section", Text("A, [B]", "body")));'
    for seed in range(50):
        randomizer = random.Random(seed)
        framer = HybridCardFramer()
        units = []
        offset = 0
        while offset < len(source):
            width = randomizer.randint(1, 7)
            units.extend(framer.push(source[offset : offset + width]))
            offset += width
        assert framer.finish() == source
        assert [unit.source for unit in units if unit.kind == "program"] == [source]

    with pytest.raises(TerseDslNested2ConversionError, match="crossed"):
        HybridCardFramer().push('Template("card@1", {])')
    partial = HybridCardFramer()
    partial.push('Template("card@1", {}, Column(')
    with pytest.raises(TerseDslNested2ConversionError, match="before delimiters closed"):
        partial.finish()


def test_parser_accepts_safe_model_child_array_variant() -> None:
    source = 'Template("card@1", {}, Column({layout: "section"}, [Text("事实", "body")]));'
    parsed = parse_hybrid_card(source)
    content = parsed.children[0]
    assert content.values == ({"layout": "section"},)
    assert [child.name for child in content.children] == ["Text"]


def test_hybrid_prompt_exposes_template_parameter_json_types() -> None:
    scenario = json.loads(GOLDEN_FIXTURE.read_text(encoding="utf-8"))["scenarios"][0]
    _result, _task_spec, projection = _compile_scenario(scenario)
    system_prompt = projection.messages[0]["content"]
    assert '"type": "string"' in system_prompt
    assert "看起来像数字的 string 仍需加引号" in system_prompt
    assert 'Text 严格写成 Text("可见文字", "designToken")' in system_prompt
    assert "禁止写成 action: { action: {...} }" in system_prompt


def test_action_placement_splits_card_and_content_actions() -> None:
    payload = json.loads(GOLDEN_FIXTURE.read_text(encoding="utf-8"))
    family = next(item for item in payload["scenarios"] if item["id"] == "family-care-weather")
    result, task_spec, projection = _compile_scenario(family)
    assert projection.contract.content_action_ids == ("event.call.phone",)
    assert '"contentActionCandidates"' in projection.messages[1]["content"]
    assert "Button(" not in result.effective_output

    profile = A2UIProtocolRegistry.read_design_protocol_profile(TERSE_DSL_NESTED2_PROFILE_ID)
    invalid = family["rawHybridSource"].replace(
        'Template("card@1", {},',
        'Template("card@1", {action: {label: "拨打电话", id: "event.call.phone"}},',
    )
    with pytest.raises(TerseDslNested2ConversionError, match="content Action"):
        compile_hybrid_card(
            invalid,
            task_spec=task_spec,
            contract=projection.contract,
            protocol_profile=profile,
            registry=get_cardplan_registry(),
        )

    duplicate = (
        'Template("card@1", {}, Column("section", '
        'Template("ux-icon-action@1", "small", '
        '{icon: "resources/base/media/ux_golden_asset_call_white.svg", '
        'actionId: "event.call.phone"}), '
        'Template("ux-icon-action@1", "small", '
        '{icon: "resources/base/media/ux_golden_asset_call_white.svg", '
        'actionId: "event.call.phone"})));'
    )
    with pytest.raises(TerseDslNested2ConversionError, match="do not match"):
        compile_hybrid_card(
            duplicate,
            task_spec=task_spec,
            contract=projection.contract,
            protocol_profile=profile,
            registry=get_cardplan_registry(),
        )


def test_theme_template_reconciliation_prefers_active_ux_palette() -> None:
    payload = json.loads(GOLDEN_FIXTURE.read_text(encoding="utf-8"))
    race = next(item for item in payload["scenarios"] if item["id"] == "race-countdown")
    task_spec, card_spec, brief = _scenario_inputs(race)
    candidates = selection_candidates(task_spec, get_cardplan_registry())
    candidate_ids = {item["id"] for item in candidates["localTemplates"]}
    assert {"ux-countdown@1", "ux-action-summary@1"} <= candidate_ids

    mismatched = brief.model_copy(update={"theme_id": "race-night-violet"})
    projection = build_hybrid_prompt(
        task_spec=task_spec,
        card_spec=card_spec,
        ui_brief=mismatched,
        registry=get_cardplan_registry(),
    )
    assert projection.theme_id == "race-sunrise-action"


def test_device_metric_hero_rejects_mismatched_numeric_display_value() -> None:
    payload = json.loads(GOLDEN_FIXTURE.read_text(encoding="utf-8"))
    scenario = next(item for item in payload["scenarios"] if item["id"] == "device-clean")
    _result, task_spec, projection = _compile_scenario(scenario)
    invalid = (
        scenario["rawHybridSource"]
        .replace(
            '"small", { value: 72,',
            '"small", { value: 87,',
        )
        .replace(
            '"hero", { value: 87, valueText: "87%"',
            '"hero", { value: 72, valueText: "87%"',
        )
    )
    profile = A2UIProtocolRegistry.read_design_protocol_profile(TERSE_DSL_NESTED2_PROFILE_ID)

    with pytest.raises(TerseDslNested2ConversionError, match="parameter relation"):
        compile_hybrid_card(
            invalid,
            task_spec=task_spec,
            contract=projection.contract,
            protocol_profile=profile,
            registry=get_cardplan_registry(),
        )


def test_hybrid_contract_rejects_missing_numeric_fact() -> None:
    payload = json.loads(GOLDEN_FIXTURE.read_text(encoding="utf-8"))
    scenario = next(item for item in payload["scenarios"] if item["id"] == "device-clean")
    _result, task_spec, projection = _compile_scenario(scenario)
    missing = scenario["rawHybridSource"].replace(
        ', Template("ux-device-metric@1", "small", { value: 72, '
        'icon: "resources/base/media/ux_golden_asset_phone_gray.svg" })',
        "",
    )
    profile = A2UIProtocolRegistry.read_design_protocol_profile(TERSE_DSL_NESTED2_PROFILE_ID)

    with pytest.raises(TerseDslNested2ConversionError, match="missing required numeric"):
        compile_hybrid_card(
            missing,
            task_spec=task_spec,
            contract=projection.contract,
            protocol_profile=profile,
            registry=get_cardplan_registry(),
        )


def test_registry_variant_order_places_inline_metrics_before_hero() -> None:
    payload = json.loads(GOLDEN_FIXTURE.read_text(encoding="utf-8"))
    scenario = next(item for item in payload["scenarios"] if item["id"] == "device-clean")
    _result, task_spec, projection = _compile_scenario(scenario)
    source = (
        'Template("card@1", {action: {label: "一键清理", id: "event.clean.memory"}}, '
        'Column("section", Template("ux-device-metric@1", "hero", '
        '{value: 87, valueText: "87%", description: "内存已使用", '
        'icon: "resources/base/media/ux_golden_asset_clear_gray.svg"}), '
        'Row("between", Template("ux-device-metric@1", "small", {value: 78, '
        'icon: "resources/base/media/ux_golden_asset_electricity_gray.svg"}), '
        'Template("ux-device-metric@1", "small", {value: 68, '
        'icon: "resources/base/media/ux_golden_asset_earphone_gray.svg"}), '
        'Template("ux-device-metric@1", "small", {value: 72, '
        'icon: "resources/base/media/ux_golden_asset_phone_gray.svg"}))));'
    )
    profile = A2UIProtocolRegistry.read_design_protocol_profile(TERSE_DSL_NESTED2_PROFILE_ID)
    result = compile_hybrid_card(
        source,
        task_spec=task_spec,
        contract=projection.contract,
        protocol_profile=profile,
        registry=get_cardplan_registry(),
    )

    assert result.effective_output.index("ux_golden_asset_electricity_gray.svg") < (
        result.effective_output.index("内存已使用")
    )


def test_countdown_content_fits_when_optional_card_title_is_present() -> None:
    payload = json.loads(GOLDEN_FIXTURE.read_text(encoding="utf-8"))
    scenario = next(item for item in payload["scenarios"] if item["id"] == "race-countdown")
    _result, task_spec, projection = _compile_scenario(scenario)
    titled = scenario["rawHybridSource"].replace(
        'Template("card@1", {},',
        'Template("card@1", {title: "马拉松倒计时"},',
    )
    profile = A2UIProtocolRegistry.read_design_protocol_profile(TERSE_DSL_NESTED2_PROFILE_ID)
    result = compile_hybrid_card(
        titled,
        task_spec=task_spec,
        contract=projection.contract,
        protocol_profile=profile,
        registry=get_cardplan_registry(),
    )

    assert result.stats.estimated_height_vp <= result.stats.vertical_budget_vp
    assert result.stats.space_constrained is False


def test_action_summary_repairs_calendar_icon_to_unique_running_asset() -> None:
    payload = json.loads(GOLDEN_FIXTURE.read_text(encoding="utf-8"))
    scenario = next(item for item in payload["scenarios"] if item["id"] == "race-countdown")
    _result, task_spec, projection = _compile_scenario(scenario)
    wrong_icon = scenario["rawHybridSource"].replace(
        "ux_golden_asset_figure_run_white.svg",
        "ux_golden_asset_calendar_lavender.svg",
    )
    profile = A2UIProtocolRegistry.read_design_protocol_profile(TERSE_DSL_NESTED2_PROFILE_ID)
    result = compile_hybrid_card(
        wrong_icon,
        task_spec=task_spec,
        contract=projection.contract,
        protocol_profile=profile,
        registry=get_cardplan_registry(),
    )

    assert "ux_golden_asset_figure_run_white.svg" in result.effective_output


def test_ui_brief_candidates_expose_variant_parameter_semantics() -> None:
    payload = json.loads(GOLDEN_FIXTURE.read_text(encoding="utf-8"))
    sleep = next(item for item in payload["scenarios"] if item["id"] == "sleep")
    task_spec, _card_spec, _brief = _scenario_inputs(sleep)

    candidates = selection_candidates(task_spec, get_cardplan_registry())
    sleep_metric = next(
        item for item in candidates["localTemplates"] if item["id"] == "ux-sleep-metric@1"
    )
    hero = next(item for item in sleep_metric["variants"] if item["size"] == "hero")
    kinds = {item["name"]: item["valueKind"] for item in hero["requiredParameters"]}

    assert kinds["hours"] == "literal"
    assert kinds["minutes"] == "literal"
    assert kinds["sleepIcon"] == "asset-source"


def test_compiler_allows_only_complete_composition_of_trusted_template_literals() -> None:
    payload = json.loads(GOLDEN_FIXTURE.read_text(encoding="utf-8"))
    sleep = next(item for item in payload["scenarios"] if item["id"] == "sleep")
    task_spec, card_spec, brief = _scenario_inputs(sleep)
    brief = brief.model_copy(update={"local_template_ids": ["sleep-summary@1"]})
    projection = build_hybrid_prompt(
        task_spec=task_spec,
        card_spec=card_spec,
        ui_brief=brief,
        registry=get_cardplan_registry(),
    )
    profile = A2UIProtocolRegistry.read_design_protocol_profile(TERSE_DSL_NESTED2_PROFILE_ID)
    source = (
        'Template("card@1", { title: "睡眠不足", subtitle: "6小时45分", '
        'titleIcon: "resources/base/media/ux_golden_asset_sleep_white.svg", '
        'action: { label: "设置早睡提醒", id: "event.open.clock.alarm" } }, '
        'Column("section", Template("sleep-summary@1", "hero", '
        '{ value: 6.75, total: 8, valueText: "6", detail: "小时45分", '
        'status: "睡眠不足" })));'
    )

    compiled = compile_hybrid_card(
        source,
        task_spec=task_spec,
        contract=projection.contract,
        protocol_profile=profile,
        registry=get_cardplan_registry(),
    )

    assert "小时45分" in compiled.a2ui
    with pytest.raises(TerseDslNested2ConversionError, match="not trusted"):
        compile_hybrid_card(
            source.replace('detail: "小时45分"', 'detail: "小时45分!"'),
            task_spec=task_spec,
            contract=projection.contract,
            protocol_profile=profile,
            registry=get_cardplan_registry(),
        )


def test_card_action_contract_hides_content_action_variants() -> None:
    payload = json.loads(GOLDEN_FIXTURE.read_text(encoding="utf-8"))
    meeting = next(item for item in payload["scenarios"] if item["id"] == "current-meeting")
    task_spec, card_spec, brief = _scenario_inputs(meeting)
    brief = brief.model_copy(update={"action_placement": "card"})

    projection = build_hybrid_prompt(
        task_spec=task_spec,
        card_spec=card_spec,
        ui_brief=brief,
        registry=get_cardplan_registry(),
    )
    system = projection.messages[0]["content"]

    assert projection.contract.content_action_ids == ()
    assert "Template('ux-meeting-metadata@1', 'medium'" in system
    assert "Template('ux-meeting-metadata@1', 'hero'" not in system


def test_redundant_generic_action_template_returns_action_to_card_shell() -> None:
    payload = json.loads(GOLDEN_FIXTURE.read_text(encoding="utf-8"))
    focus = next(item for item in payload["scenarios"] if item["id"] == "focus-mode")
    task_spec, card_spec, brief = _scenario_inputs(focus)
    brief = brief.model_copy(
        update={
            "local_template_ids": ["ux-calendar-content@1", "status-action@1"],
            "action_placement": "content",
        }
    )
    projection = build_hybrid_prompt(
        task_spec=task_spec,
        card_spec=card_spec,
        ui_brief=brief,
        registry=get_cardplan_registry(),
    )
    assert projection.requested_template_ids == ("ux-calendar-content@1",)
    assert projection.contract.content_action_ids == ()
    assert '"cardActionCandidates"' in projection.messages[1]["content"]


def test_unthemed_generic_action_is_pruned_beside_device_content_template() -> None:
    payload = json.loads(GOLDEN_FIXTURE.read_text(encoding="utf-8"))
    device = next(item for item in payload["scenarios"] if item["id"] == "device-clean")
    task_spec, card_spec, brief = _scenario_inputs(device)
    brief = brief.model_copy(
        update={
            "local_template_ids": ["ux-device-metric@1", "status-action@1"],
            "action_placement": "content",
        }
    )
    projection = build_hybrid_prompt(
        task_spec=task_spec,
        card_spec=card_spec,
        ui_brief=brief,
        registry=get_cardplan_registry(),
    )

    assert projection.requested_template_ids == ("ux-device-metric@1",)
    assert projection.contract.content_action_ids == ()
    assert '"cardActionCandidates"' in projection.messages[1]["content"]


def test_action_only_brief_adds_theme_content_and_prunes_generic_action() -> None:
    payload = json.loads(GOLDEN_FIXTURE.read_text(encoding="utf-8"))
    low_power = next(item for item in payload["scenarios"] if item["id"] == "low-power")
    task_spec, card_spec, brief = _scenario_inputs(low_power)
    brief = brief.model_copy(
        update={
            "local_template_ids": ["status-action@1"],
            "action_placement": "content",
        }
    )
    projection = build_hybrid_prompt(
        task_spec=task_spec,
        card_spec=card_spec,
        ui_brief=brief,
        registry=get_cardplan_registry(),
    )
    assert projection.requested_template_ids == ("ux-battery-status@1",)
    assert projection.contract.content_action_ids == ()
    assert '"cardActionCandidates"' in projection.messages[1]["content"]


def test_card_action_and_capsule_progress_lower_to_basic_projection() -> None:
    payload = json.loads(GOLDEN_FIXTURE.read_text(encoding="utf-8"))
    digital = next(item for item in payload["scenarios"] if item["id"] == "digital-wellbeing")
    result, _task_spec, _projection = _compile_scenario(digital)
    assert "Progress(" not in result.effective_output
    assert "Button(" not in result.effective_output
    assert 'Stack("overlay"' in result.effective_output
    assert 'Text(" "' in result.effective_output


def test_status_action_template_binds_trusted_event_alias() -> None:
    payload = json.loads(GOLDEN_FIXTURE.read_text(encoding="utf-8"))
    focus = next(item for item in payload["scenarios"] if item["id"] == "focus-mode")
    task_spec, card_spec, brief = _scenario_inputs(focus)
    brief = brief.model_copy(
        update={
            "local_template_ids": ["ux-calendar-content@1", "status-action@1"],
            "action_placement": "content",
        }
    )
    registry = get_cardplan_registry()
    projection = build_hybrid_prompt(
        task_spec=task_spec,
        card_spec=card_spec,
        ui_brief=brief,
        registry=registry,
    )
    source = (
        'Template("card@1", {title: "下一个日程", '
        'titleIcon: "resources/base/media/icon_schedule.svg"}, Column("compact", '
        'Template("ux-calendar-content@1", "small", '
        '{title: "Agent需求评审会", time: "14:00–15:30"}), '
        'Template("status-action@1", "medium", {status: "还有15分钟开启", '
        'actionLabel: "专注模式", actionId: "event.open.settings.dnd"})));'
    )
    profile = A2UIProtocolRegistry.read_design_protocol_profile(TERSE_DSL_NESTED2_PROFILE_ID)
    compiler_contract = projection.contract.model_copy(
        update={
            "allowed_template_ids": (
                "ux-calendar-content@1",
                "status-action@1",
            ),
            "allowed_design_tokens": (
                *projection.contract.allowed_design_tokens,
                "body",
                "action-frosted",
            ),
            "allowed_layout_tokens": (
                *projection.contract.allowed_layout_tokens,
                "action-bottom-compact",
            ),
            "content_action_ids": ("event.open.settings.dnd",),
        }
    )
    result = compile_hybrid_card(
        source,
        task_spec=task_spec,
        contract=compiler_contract,
        protocol_profile=profile,
        registry=registry,
    )
    assert result.stats.action_used_ids == ("event.open.settings.dnd",)
    assert "Template" not in result.a2ui


@pytest.mark.asyncio
async def test_content_action_placement_without_action_template_normalizes_to_card() -> None:
    scenario = json.loads(GOLDEN_FIXTURE.read_text(encoding="utf-8"))["scenarios"][0]
    task_spec, _card_spec, _brief = _scenario_inputs(scenario)

    async def invalid_brief(_messages, _phase):
        return {
            "purpose": "show summary",
            "primaryInformation": ["summary"],
            "informationHierarchy": ["summary", "action"],
            "visualTone": "clear",
            "actionPlacement": "content",
            "localTemplateIds": [],
            "contentPriorities": ["summary"],
            "reason": "content action",
        }

    brief = await plan_ui_with_llm(task_spec, DataShape(action_count=1), invalid_brief)
    assert brief.action_placement == "card"


def test_optional_action_template_promotes_primary_action_to_card_shell() -> None:
    payload = json.loads(GOLDEN_FIXTURE.read_text(encoding="utf-8"))
    meeting = next(item for item in payload["scenarios"] if item["id"] == "current-meeting")
    _task_spec, _card_spec, brief = _scenario_inputs(meeting)
    brief = brief.model_copy(
        update={
            "action_placement": "content",
            "local_template_ids": ["ux-meeting-metadata@1"],
        }
    )

    normalized = normalize_action_placement(brief, DataShape(action_count=1))

    assert normalized.action_placement == "card"


def test_ui_brief_preserves_order_while_deduplicating_valid_template_ids() -> None:
    brief = UIBrief(
        purpose="device summary",
        primaryInformation=["battery"],
        informationHierarchy=["device", "actions"],
        visualTone="compact",
        localTemplateIds=[
            "ux-audio-device-status@1",
            "ux-action-metric@1",
            "ux-action-metric@1",
        ],
        contentPriorities=["device status"],
        reason="two actions use the same reusable template",
    )

    assert brief.local_template_ids == [
        "ux-audio-device-status@1",
        "ux-action-metric@1",
    ]


def test_required_local_action_template_keeps_content_action_placement() -> None:
    payload = json.loads(GOLDEN_FIXTURE.read_text(encoding="utf-8"))
    family = next(item for item in payload["scenarios"] if item["id"] == "family-care-weather")
    _task_spec, _card_spec, brief = _scenario_inputs(family)
    brief = brief.model_copy(
        update={
            "action_placement": "content",
            "local_template_ids": ["ux-icon-action@1"],
        }
    )

    normalized = normalize_action_placement(brief, DataShape(action_count=1))

    assert normalized.action_placement == "content"


def test_ts_layout_design_and_card_icon_aliases_lower_to_existing_adapter() -> None:
    assert _normalize_component_values("Column", ("metric-stack",)) == ("section",)
    assert _normalize_component_values("Column", ("dense",)) == ("compact",)
    assert _normalize_component_values("Row", ("compact",)) == ("between",)
    assert _normalize_component_values("Text", ("42", "metric-hero")) == (
        "42",
        "title",
    )
    assert _normalize_card_params({"icon": "asset.svg"}) == {"titleIcon": "asset.svg"}
    with pytest.raises(TerseDslNested2ConversionError, match="icon and titleIcon"):
        _normalize_card_params({"icon": "a.svg", "titleIcon": "b.svg"})


def test_budget_is_atomic_across_threads_and_enforces_exact_hard_limit(tmp_path: Path) -> None:
    budget = DeepSeekCallBudget(tmp_path / "concurrent.sqlite3")
    with ThreadPoolExecutor(max_workers=20) as executor:
        statuses = list(executor.map(lambda _: budget.reserve("deepseek_platform"), range(40)))
    assert sorted(item.used for item in statuses) == list(range(1, 41))
    assert budget.status().used == 40

    capped = DeepSeekCallBudget(tmp_path / "capped.sqlite3")
    capped.reserve("deepseek_platform")
    with sqlite3.connect(capped.path) as connection:
        connection.execute("UPDATE budget SET used = 399 WHERE id = 1")
    assert capped.reserve("deepseek_platform").used == 400
    assert capped.status().remaining == 0
    with pytest.raises(DeepSeekCallBudgetExceeded, match="used=400"):
        capped.reserve("deepseek_platform")


def test_settings_keep_production_budget_default_and_allow_explicit_unlimited_mode() -> None:
    settings = Settings(_env_file=None, deepseek_call_budget_limit="400")  # type: ignore[arg-type]
    assert settings.deepseek_call_budget_limit == 400
    assert Settings(_env_file=None, deepseek_call_budget_limit=0).deepseek_call_budget_limit == 0
    with pytest.raises(ValueError, match="greater than or equal to 0"):
        Settings(_env_file=None, deepseek_call_budget_limit=-1)


def test_unlimited_budget_preserves_counter_and_reserves_beyond_default_cap(tmp_path: Path) -> None:
    budget = DeepSeekCallBudget(tmp_path / "unlimited.sqlite3", limit=0)
    budget.reserve("llmclient")
    with sqlite3.connect(budget.path) as connection:
        connection.execute("UPDATE budget SET used = 400 WHERE id = 1")

    status = budget.reserve("llmclient")

    assert status.used == 401
    assert status.remaining is None
    assert status.limit is None


@pytest.mark.asyncio
async def test_failed_physical_model_call_still_consumes_budget(tmp_path: Path) -> None:
    class FailingRuntime:
        async def generate_once(self, *_args, **_kwargs):
            raise ModelTransportError("physical failure")

    settings = Settings(
        _env_file=None,
        deepseek_call_budget_path=str(tmp_path / "failed.sqlite3"),
        enable_model_failure_retry=False,
    )
    client = UnifiedModelClient(settings, FailingRuntime(), operation_name="budget-test")
    with pytest.raises(ModelTransportError, match="physical failure"):
        await client.generate("openai", [], None, phase="initial")
    assert client.deepseek_budget.status().used == 1


def test_hybrid_bypass_requires_flag_environment_enablement_and_token(monkeypatch) -> None:
    settings = get_settings()
    request = GenerateWidgetCardRequest(
        uid="test-user",
        device={"romVersion": "6.0"},
        userQuery="测试 Hybrid",
        title="测试",
        description="安全边界",
    )
    assert WidgetGenerationService._authorize_hybrid_bypass(request) is False

    request.options.forceHybridTemplate = True
    request.options.testAuthorization = "expected"
    monkeypatch.setattr(settings, "enable_hybrid_test_bypass", False)
    monkeypatch.setattr(settings, "hybrid_test_bypass_token", "expected")
    monkeypatch.setattr(settings, "env", "test")
    with pytest.raises(ValueError, match="not authorized"):
        WidgetGenerationService._authorize_hybrid_bypass(request)

    monkeypatch.setattr(settings, "enable_hybrid_test_bypass", True)
    monkeypatch.setattr(settings, "env", "production")
    with pytest.raises(ValueError, match="not authorized"):
        WidgetGenerationService._authorize_hybrid_bypass(request)

    monkeypatch.setattr(settings, "env", "test")
    request.options.testAuthorization = "wrong"
    with pytest.raises(ValueError, match="not authorized"):
        WidgetGenerationService._authorize_hybrid_bypass(request)

    request.options.testAuthorization = "expected"
    assert WidgetGenerationService._authorize_hybrid_bypass(request) is True


def test_test_authorization_is_never_serialized_or_logged() -> None:
    request = GenerateWidgetCardRequest(
        uid="test-user",
        device={"romVersion": "6.0"},
        userQuery="测试",
        title="测试",
        description="测试",
        options={"forceHybridTemplate": True, "testAuthorization": "top-secret"},
    )
    dumped = request.model_dump(mode="json")
    logged = json_for_log({"request": request, "authorization": "bearer-secret"})
    assert "testAuthorization" not in json.dumps(dumped)
    assert "top-secret" not in logged
    assert "bearer-secret" not in logged


def test_production_structured_logs_remove_business_payloads(monkeypatch) -> None:
    monkeypatch.setattr(get_settings(), "env", "production")
    logged = json_for_log(
        {
            "requestId": "request-safe-to-log",
            "request": {
                "userQuery": "private intent",
                "dataSlice": {"medical": "private value"},
            },
            "rawOutput": "private model result",
        }
    )
    assert "request-safe-to-log" in logged
    assert "private intent" not in logged
    assert "private value" not in logged
    assert "private model result" not in logged


def test_ui_brief_rejects_unversioned_and_deduplicates_local_templates() -> None:
    base = {
        "purpose": "status",
        "primaryInformation": ["状态"],
        "informationHierarchy": ["状态"],
        "visualTone": "calm",
        "contentPriorities": ["状态"],
        "reason": "测试",
    }
    with pytest.raises(ValueError, match="versioned"):
        UIBrief(**base, localTemplateIds=["weather-summary"])
    brief = UIBrief(**base, localTemplateIds=["weather-summary@1", "weather-summary@1"])
    assert brief.local_template_ids == ["weather-summary@1"]
    brief = UIBrief(**base, contentSemantics=["metric", "model-invented-value"])
    assert brief.content_semantics == ["metric"]
