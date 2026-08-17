#!/usr/bin/env python3
"""Run deterministic or real-model CardPlan evaluation against nine UX Goldens."""

from __future__ import annotations

import argparse
import asyncio
import hashlib
import json
import os
import re
import sys
import time
from collections import Counter
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from difflib import SequenceMatcher
from pathlib import Path
from typing import Any

SERVICE_ROOT = Path(__file__).resolve().parents[1]
CLOUD_ROOT = SERVICE_ROOT / "cloud"
if str(CLOUD_ROOT) not in sys.path:
    sys.path.insert(0, str(CLOUD_ROOT))

from config.config import get_settings  # noqa: E402
from custom.a2ui_model_client import A2UIModelClient  # noqa: E402
from custom.deepseek_call_budget import (  # noqa: E402
    DeepSeekCallBudget,
    DeepSeekCallBudgetExceeded,
)
from models.generation import EventAction, ModelRequestContext, TaskSpec  # noqa: E402
from services.advanced_component_pipeline import AdvancedComponentPipeline  # noqa: E402
from services.advanced_component_pipeline.content_selectors import (  # noqa: E402
    apply_content_selectors,
    project_content_component_facts,
)
from services.advanced_component_pipeline.models import (  # noqa: E402
    AdvancedScopeBrief,
    UIBrief,
)
from services.advanced_component_pipeline.ux_mixed_prompt import (  # noqa: E402
    build_ux_mixed_prompt,
)
from services.cardplan_template.compiler import compile_ux_layout_card  # noqa: E402
from services.cardplan_template.registry import get_cardplan_registry  # noqa: E402
from services.protocol_registry import (  # noqa: E402
    TERSE_DSL_NESTED2_PROFILE_ID,
    A2UIProtocolRegistry,
)

FIXTURE_PATH = SERVICE_ROOT / "tests/fixtures/cardplan_ux_v2_scenarios.json"
DEFAULT_REPORT_ROOT = SERVICE_ROOT / "workspace/runtime/cardplan_template_evaluation"
UX_GOLDEN_ROOT = SERVICE_ROOT.parents[1] / "intermediate_expression/tests/golden/ux-design-2x2"
UX_GOLDEN_MANIFEST = UX_GOLDEN_ROOT / "manifest.json"


@dataclass
class RecordedCall:
    phase: str
    prompt: list[dict[str, str]]
    raw_output: str
    latency_ms: float
    protocol_success: bool
    finish_reason: str
    raw_finish_reason: str | None
    usage: dict[str, int | str]
    raw_usage: dict[str, Any] | None
    error: str = ""


class RecordingA2UIModelClient(A2UIModelClient):
    """Capture evaluation evidence while preserving the production client path."""

    def __init__(self, *, scenario_id: str) -> None:
        settings = get_settings()
        context = ModelRequestContext(
            session_id=f"cardplan-eval-{scenario_id}",
            interaction_id=f"cardplan-eval-{scenario_id}",
            device_id=f"cardplan-eval-{scenario_id}",
            country_code=settings.deepseek_platform_default_country_code,
            app_version=settings.default_prd_version,
            app_name=settings.deepseek_platform_default_app_name,
        )
        super().__init__(
            use_mock=False,
            backend="openai",
            request_context=context,
            operation_name="cardplan-template-golden-evaluation",
        )
        self.calls: list[RecordedCall] = []

    async def _call_transport(
        self,
        prompt: list[dict[str, str]],
        protocol_profile: dict,
        *,
        phase: str,
    ) -> str:
        started = time.perf_counter()
        try:
            raw_output = await super()._call_transport(
                prompt,
                protocol_profile,
                phase=phase,
            )
        except Exception as exc:
            self.calls.append(
                RecordedCall(
                    phase=phase,
                    prompt=prompt,
                    raw_output="",
                    latency_ms=_elapsed_ms(started),
                    protocol_success=False,
                    finish_reason="transport-error",
                    raw_finish_reason=None,
                    usage=_estimated_usage(prompt, ""),
                    raw_usage=None,
                    error=f"{type(exc).__name__}: {exc}",
                )
            )
            raise
        self.calls.append(
            RecordedCall(
                phase=phase,
                prompt=prompt,
                raw_output=raw_output,
                latency_ms=_elapsed_ms(started),
                protocol_success=bool(raw_output.strip()),
                finish_reason=str(self._response_metadata().get("finishReason") or "unknown"),
                raw_finish_reason=self._response_metadata().get("finishReason"),
                usage=_estimated_usage(prompt, raw_output),
                raw_usage=self._response_metadata().get("usage"),
            )
        )
        return raw_output

    def _response_metadata(self) -> dict[str, Any]:
        if self.runtime is None:
            return {}
        runtime_metadata = getattr(self.runtime, "last_response_metadata", None)
        if isinstance(runtime_metadata, dict) and runtime_metadata:
            return runtime_metadata
        transport = getattr(self.runtime, "_deepseek_platform_transport", None)
        metadata = getattr(transport, "last_response_metadata", None)
        return metadata if isinstance(metadata, dict) else {}


def _estimated_usage(
    prompt: list[dict[str, str]],
    output: str,
) -> dict[str, int | str]:
    input_chars = sum(len(item.get("content", "")) for item in prompt)
    output_chars = len(output)
    input_tokens = (input_chars + 3) // 4
    output_tokens = (output_chars + 3) // 4
    return {
        "source": "char-estimate",
        "inputTokens": input_tokens,
        "outputTokens": output_tokens,
        "totalTokens": input_tokens + output_tokens,
    }


def _sample_schema(value: object) -> object:
    if isinstance(value, dict):
        return {key: _sample_schema(child) for key, child in value.items()}
    if isinstance(value, list):
        return [_sample_schema(value[0])] if value else []
    data_type = "boolean" if isinstance(value, bool) else "number"
    if not isinstance(value, (bool, int, float)):
        data_type = "string"
    return {"type": data_type, "description": "Golden sample", "sampleValue": value}


def _scenario_inputs(scenario: dict[str, Any]) -> tuple[TaskSpec, dict[str, Any]]:
    data = {item["capabilityId"]: item["dataSlice"] for item in scenario["dataEntries"]}
    events = [
        EventAction(
            id=action_id,
            displayLabel=label,
            call="fixtureAction",
            args={"actionId": action_id},
        )
        for action_id, label in scenario["eventDisplayLabels"].items()
    ]
    task_spec = TaskSpec(
        userQuery=scenario["userQuery"],
        size=scenario["cardSize"],
        eventCandidates=events,
        dataModelSchema={"data": _sample_schema(data)},
        assetCandidates=scenario["assets"],
    )
    card_spec = {
        "title": scenario["title"],
        "description": scenario["description"],
        "suggestSize": scenario["cardSize"],
    }
    return task_spec, card_spec


def _fixture_brief(scenario: dict[str, Any]) -> UIBrief:
    return UIBrief(
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
        reason="Compile the mechanically exported TypeScript Golden program.",
    )


def _fixture_scope(scenario: dict[str, Any]) -> AdvancedScopeBrief:
    mapping: dict[str, tuple[str, str]] = {
        "current-meeting": ("meeting-paper-neutral", "ScheduleOverview"),
        "family-care-weather": ("family-weather-care-blue", "WeatherOverview"),
        "focus-mode": ("focus-warm-amber", "ScheduleOverview"),
        "device-clean": ("device-clean-blue-teal", "ResourceUsageOverview"),
        "rainy-commute": ("rainy-commute-gray-blue", "WeatherOverview"),
        "low-power": ("system-low-power-blue", "BatteryOverview"),
        "sleep": ("sleep-night-violet", "SleepOverview"),
        "race-countdown": ("race-sunrise-action", "WorkoutOverview"),
        "digital-wellbeing": (
            "digital-wellbeing-neutral-dark",
            "AppUsageOverview",
        ),
    }
    try:
        theme_id, component_id = mapping[scenario["id"]]
    except KeyError as exc:
        raise ValueError(f"Missing deterministic UX scope: {scenario['id']}") from exc
    return AdvancedScopeBrief(
        themeId=theme_id,
        advancedComponentIds=(component_id,),
    )


def _a2ui_summary(a2ui: str, action_ids: tuple[str, ...]) -> dict[str, Any]:
    rows = [json.loads(line) for line in a2ui.splitlines() if line.strip()]
    update = next((row.get("updateComponents") for row in rows if "updateComponents" in row), {})
    components = update.get("components", []) if isinstance(update, dict) else []
    component_types: Counter[str] = Counter()
    visible_texts: list[str] = []
    style_pairs: set[str] = set()
    root: dict[str, Any] = {}
    for component in components:
        component_types[str(component.get("component", ""))] += 1
        for key in ("content", "label", "valueText"):
            value = component.get(key)
            if isinstance(value, str) and value:
                visible_texts.append(value)
        styles = component.get("styles")
        if isinstance(styles, dict):
            for key, value in styles.items():
                style_pairs.add(f"{key}={json.dumps(value, sort_keys=True, ensure_ascii=False)}")
        if component.get("id") == "root":
            root = component
    return {
        "visibleTexts": visible_texts,
        "actionIds": list(action_ids),
        "componentTypes": dict(component_types),
        "componentCount": len(components),
        "rootComponent": root.get("component"),
        "rootStyles": root.get("styles", {}),
        "stylePairs": sorted(style_pairs),
    }


def _golden_manifest() -> dict[str, Any]:
    payload = json.loads(UX_GOLDEN_MANIFEST.read_text(encoding="utf-8"))
    if payload.get("version") != "2.0.0":
        raise ValueError("UX Golden manifest must use version 2.0.0")
    if payload.get("wireVersion") != "v0.9":
        raise ValueError("UX Golden wire version must be v0.9")
    if payload.get("catalogId") != "ohos.a2ui.extended.catalog":
        raise ValueError("UX Golden Catalog is invalid")
    scenes = payload.get("scenes")
    if not isinstance(scenes, list) or len(scenes) != 9:
        raise ValueError("UX Golden v2 must contain exactly nine scenes")
    return payload


def _golden_baseline(scenario_id: str) -> dict[str, Any]:
    manifest = _golden_manifest()
    scene = next(
        (item for item in manifest["scenes"] if item.get("id") == scenario_id),
        None,
    )
    if not isinstance(scene, dict):
        raise ValueError(f"UX Golden scene is missing: {scenario_id}")
    source_path = UX_GOLDEN_ROOT / str(scene["protocolFile"])
    source = source_path.read_text(encoding="utf-8")
    action_ids = tuple(str(item) for item in scene.get("actionIds", []))
    summary = _a2ui_summary(source, action_ids)
    rows = [json.loads(line) for line in source.splitlines() if line.strip()]
    create = rows[0].get("createSurface", {}) if rows else {}
    protocol_success = (
        len(rows) == 2
        and create.get("catalogId") == "ohos.a2ui.extended.catalog"
        and all(row.get("version") == "v0.9" for row in rows)
    )
    return {
        "version": manifest["version"],
        "wireVersion": manifest["wireVersion"],
        "catalogId": manifest["catalogId"],
        "protocolSuccess": protocol_success,
        "path": str(source_path),
        "sha256": "sha256:" + hashlib.sha256(source.encode()).hexdigest(),
        "compiledA2UI": source,
        "summary": summary,
    }


def _histogram_similarity(left: dict[str, int], right: dict[str, int]) -> float:
    keys = set(left) | set(right)
    denominator = sum(max(left.get(key, 0), right.get(key, 0)) for key in keys)
    if denominator == 0:
        return 1.0
    numerator = sum(min(left.get(key, 0), right.get(key, 0)) for key in keys)
    return round(numerator / denominator, 4)


def _jaccard(left: set[str], right: set[str]) -> float:
    if not left and not right:
        return 1.0
    return round(len(left & right) / len(left | right), 4)


def _flatten_styles(styles: dict[str, Any]) -> set[str]:
    return {
        f"{key}={json.dumps(value, sort_keys=True, ensure_ascii=False)}"
        for key, value in styles.items()
    }


def _alignment(
    actual: dict[str, Any],
    expected: dict[str, Any],
    *,
    ignored_title: str = "",
) -> dict[str, Any]:
    actual_text_by_semantic = {
        _semantic_text(value): value for value in actual["visibleTexts"] if value.strip()
    }
    expected_text_by_semantic = {
        _semantic_text(value): value for value in expected["visibleTexts"] if value.strip()
    }
    expected_texts = set(expected_text_by_semantic)
    actual_text_blob = "".join(_semantic_phrase(value) for value in actual["visibleTexts"])
    expected_text_blob = "".join(_semantic_phrase(value) for value in expected["visibleTexts"])
    actual_actions = set(actual["actionIds"])
    expected_actions = set(expected["actionIds"])
    type_similarity = _histogram_similarity(
        actual["componentTypes"],
        expected["componentTypes"],
    )
    component_count_similarity = round(
        min(actual["componentCount"], expected["componentCount"])
        / max(actual["componentCount"], expected["componentCount"], 1),
        4,
    )
    expected_style_pairs = _flatten_styles(expected["rootStyles"])
    root_style_similarity = _jaccard(
        _flatten_styles(actual["rootStyles"]),
        expected_style_pairs,
    )
    semantic_style_similarity = _jaccard(
        set(actual["stylePairs"]),
        expected_style_pairs,
    )
    raw_missing_texts = sorted(
        value
        for value in expected_text_by_semantic.values()
        if _semantic_phrase(value) and not _visible_text_matches(value, actual_text_blob)
    )
    ignored_title_phrase = _semantic_phrase(ignored_title)
    ignored_title_differences = [
        value
        for value in raw_missing_texts
        if ignored_title_phrase
        and (
            _semantic_phrase(value) in ignored_title_phrase
            or ignored_title_phrase in _semantic_phrase(value)
        )
    ]
    missing_texts = [value for value in raw_missing_texts if value not in ignored_title_differences]
    extra_texts = sorted(
        value
        for value in actual_text_by_semantic.values()
        if _semantic_phrase(value) and not _visible_text_matches(value, expected_text_blob)
    )
    missing_actions = sorted(expected_actions - actual_actions)
    reasons: list[str] = []
    if missing_texts:
        reasons.append(f"missing-texts:{len(missing_texts)}")
    if missing_actions:
        reasons.append(f"missing-actions:{len(missing_actions)}")
    if type_similarity < 0.35:
        reasons.append("component-type-similarity<0.35")
    if component_count_similarity < 0.4:
        reasons.append("component-count-similarity<0.4")
    if root_style_similarity < 0.2:
        reasons.append("root-style-similarity<0.2")
    return {
        "passed": not reasons,
        "missingTexts": missing_texts,
        "ignoredTitleDifferences": ignored_title_differences,
        "extraTexts": extra_texts,
        "semanticTextCoverage": round(
            1 - len(missing_texts) / max(len(expected_texts), 1),
            4,
        ),
        "expectedActionIds": sorted(expected_actions),
        "actualActionIds": sorted(actual_actions),
        "missingActionIds": missing_actions,
        "componentTypeSimilarity": type_similarity,
        "componentCountSimilarity": component_count_similarity,
        "semanticStyleSimilarity": semantic_style_similarity,
        "rootStyleSimilarity": root_style_similarity,
        "expectedComponentCount": expected["componentCount"],
        "actualComponentCount": actual["componentCount"],
        "failureReasons": reasons,
    }


def _semantic_text(value: str) -> str:
    normalized = value.replace("–", "-").replace("—", "-")
    return re.sub(r"\s+", " ", normalized).strip().casefold()


def _semantic_phrase(value: str) -> str:
    normalized = _semantic_text(value).replace("…", "").replace("...", "")
    return "".join(re.findall(r"[a-z0-9\u4e00-\u9fff°%]+", normalized))


def _phrase_matches(needle: str, haystack: str) -> bool:
    if needle in haystack:
        return True
    matcher = SequenceMatcher(a=needle, b=haystack, autojunk=False)
    matched = sum(block.size for block in matcher.get_matching_blocks())
    return matched / len(needle) >= 0.8


def _visible_text_matches(value: str, haystack: str) -> bool:
    phrase = _semantic_phrase(value)
    if _phrase_matches(phrase, haystack):
        return True
    parts = tuple(
        _semantic_phrase(part) for part in re.split(r"[|｜/·•]+", value) if _semantic_phrase(part)
    )
    return len(parts) > 1 and all(_phrase_matches(part, haystack) for part in parts)


def _deterministic_scene(scenario: dict[str, Any]) -> dict[str, Any]:
    started = time.perf_counter()
    task_spec, card_spec = _scenario_inputs(scenario)
    capability_ids = {item["capabilityId"] for item in scenario["dataEntries"]}
    task_spec = apply_content_selectors(task_spec, capability_ids)
    scope = _fixture_scope(scenario)
    task_spec = project_content_component_facts(
        task_spec,
        capability_ids,
        scope.advanced_component_ids,
    )
    registry = get_cardplan_registry()
    projection = build_ux_mixed_prompt(
        task_spec=task_spec,
        card_spec=card_spec,
        scope=scope,
        registry=registry,
    )
    profile = A2UIProtocolRegistry.read_design_protocol_profile(TERSE_DSL_NESTED2_PROFILE_ID)
    compilation = compile_ux_layout_card(
        scenario["rawHybridSource"],
        task_spec=task_spec,
        contract=projection.contract,
        protocol_profile=profile,
        registry=registry,
        business_title=card_spec.get("title"),
    )
    baseline = _golden_baseline(scenario["id"])
    actual = _a2ui_summary(compilation.a2ui, compilation.stats.action_used_ids)
    return {
        "scenarioId": scenario["id"],
        "fixtureId": scenario["fixtureId"],
        "uiBrief": scope.model_dump(mode="json", by_alias=True),
        "candidateTemplates": list(projection.requested_template_ids),
        "wholeCardConfidence": None,
        "wholeCardCandidates": [],
        "confidenceBypassed": True,
        "providerContractStatus": scenario["providerContractStatus"],
        "providerContractGaps": scenario["providerContractGaps"],
        "route": "hybrid-template-deterministic",
        "rawHybridOutput": compilation.raw_output,
        "effectiveHybridOutput": compilation.effective_output,
        "compiledA2UI": compilation.a2ui,
        "modelCalls": [],
        "modelRawProtocolSuccess": None,
        "uiBriefFallback": False,
        "finalReady": True,
        "fallback": False,
        "template": compilation.stats.model_dump(mode="json"),
        "tokens": {"source": "not-applicable", "totalTokens": 0},
        "latencyMs": _elapsed_ms(started),
        "standardA2UIBaseline": baseline,
        "goldenAlignment": _alignment(
            actual,
            baseline["summary"],
            ignored_title=scenario.get("title", ""),
        ),
        "failureReason": "",
    }


def _deterministic_failure(
    scenario: dict[str, Any],
    exc: Exception,
) -> dict[str, Any]:
    baseline = _golden_baseline(scenario["id"])
    return {
        "scenarioId": scenario["id"],
        "fixtureId": scenario["fixtureId"],
        "uiBrief": None,
        "candidateTemplates": [],
        "wholeCardConfidence": None,
        "wholeCardCandidates": [],
        "confidenceBypassed": True,
        "providerContractStatus": scenario["providerContractStatus"],
        "providerContractGaps": scenario["providerContractGaps"],
        "route": "hybrid-template-deterministic",
        "rawHybridOutput": scenario.get("rawHybridSource", ""),
        "effectiveHybridOutput": "",
        "compiledA2UI": "",
        "modelCalls": [],
        "modelRawProtocolSuccess": None,
        "uiBriefFallback": False,
        "finalReady": False,
        "fallback": False,
        "template": {},
        "tokens": {"source": "not-applicable", "totalTokens": 0},
        "latencyMs": 0.0,
        "standardA2UIBaseline": baseline,
        "goldenAlignment": None,
        "failureReason": f"{type(exc).__name__}: {exc}",
    }


async def _live_scene(scenario: dict[str, Any]) -> dict[str, Any]:
    started = time.perf_counter()
    task_spec, card_spec = _scenario_inputs(scenario)
    client = RecordingA2UIModelClient(scenario_id=scenario["id"])
    output = None
    failure_reason = ""
    try:
        output = await AdvancedComponentPipeline().generate_mixed(
            task_spec,
            client,
            card_spec,
            allow_offline_fallback=False,
        )
    except DeepSeekCallBudgetExceeded:
        raise
    except Exception as exc:
        failure_reason = f"{type(exc).__name__}: {exc}"
    finally:
        await client.aclose()
    calls = [asdict(item) for item in client.calls]
    baseline = _golden_baseline(scenario["id"])
    protocol_success = False
    if output is None:
        return {
            "scenarioId": scenario["id"],
            "fixtureId": scenario["fixtureId"],
            "uiBrief": None,
            "candidateTemplates": [],
            "wholeCardConfidence": None,
            "wholeCardCandidates": [],
            "confidenceBypassed": True,
            "providerContractStatus": scenario["providerContractStatus"],
            "providerContractGaps": scenario["providerContractGaps"],
            "route": "hybrid-template",
            "rawHybridOutput": calls[-1]["raw_output"] if calls else "",
            "effectiveHybridOutput": "",
            "compiledA2UI": "",
            "modelCalls": calls,
            "modelRawProtocolSuccess": protocol_success,
            "uiBriefFallback": False,
            "finalReady": False,
            "fallback": False,
            "template": {},
            "tokens": _aggregate_usage(calls),
            "latencyMs": _elapsed_ms(started),
            "standardA2UIBaseline": baseline,
            "goldenAlignment": None,
            "failureReason": failure_reason or "pipeline returned no output",
        }
    actual = _a2ui_summary(output.compiled_a2ui, tuple(output.template_used_ids))
    actual["actionIds"] = _action_ids_from_a2ui(output.compiled_a2ui)
    if calls:
        calls[0]["protocol_success"] = output.planner_mode == "llm"
    if len(calls) > 1:
        calls[1]["protocol_success"] = bool(output.compiled_a2ui)
    protocol_success = len(calls) == 2 and all(item["protocol_success"] for item in calls)
    return {
        "scenarioId": scenario["id"],
        "fixtureId": scenario["fixtureId"],
        "uiBrief": output.ui_brief.model_dump(mode="json", by_alias=True),
        "candidateTemplates": output.invocation.get("requestedTemplateIds", []),
        "wholeCardConfidence": output.whole_card_confidence,
        "wholeCardCandidates": [
            item.model_dump(mode="json") for item in output.whole_card_candidates
        ],
        "confidenceBypassed": output.confidence_bypassed,
        "providerContractStatus": scenario["providerContractStatus"],
        "providerContractGaps": scenario["providerContractGaps"],
        "route": output.route,
        "rawHybridOutput": output.raw_output,
        "effectiveHybridOutput": output.effective_output,
        "compiledA2UI": output.compiled_a2ui,
        "modelCalls": calls,
        "modelRawProtocolSuccess": protocol_success,
        "uiBriefFallback": output.planner_mode != "llm",
        "finalReady": bool(output.compiled_a2ui) and "Template" not in output.compiled_a2ui,
        "fallback": output.fallback_used,
        "template": {
            "callCount": output.template_call_count,
            "usedIds": output.template_used_ids,
            "expandedComponentCount": output.expanded_component_count,
        },
        "tokens": _aggregate_usage(calls),
        "latencyMs": _elapsed_ms(started),
        "standardA2UIBaseline": baseline,
        "goldenAlignment": _alignment(
            actual,
            baseline["summary"],
            ignored_title=scenario.get("title", ""),
        ),
        "failureReason": failure_reason,
    }


def _action_ids_from_a2ui(a2ui: str) -> list[str]:
    action_ids: list[str] = []
    for line in a2ui.splitlines():
        row = json.loads(line)
        update = row.get("updateComponents")
        if not isinstance(update, dict):
            continue
        for component in update.get("components", []):
            for handler in component.get("onClick", []):
                args = handler.get("args", {})
                action_id = args.get("actionId") if isinstance(args, dict) else None
                if isinstance(action_id, str):
                    action_ids.append(action_id)
    return action_ids


def _aggregate_usage(calls: list[dict[str, Any]]) -> dict[str, int | str]:
    raw_usages = [item.get("raw_usage") for item in calls]
    if raw_usages and all(isinstance(item, dict) for item in raw_usages):
        input_tokens = sum(
            int(item.get("prompt_tokens", item.get("input_tokens", 0))) for item in raw_usages
        )
        output_tokens = sum(
            int(item.get("completion_tokens", item.get("output_tokens", 0))) for item in raw_usages
        )
        total_tokens = sum(int(item.get("total_tokens", 0)) for item in raw_usages)
        return {
            "source": "provider-raw",
            "inputTokens": input_tokens,
            "outputTokens": output_tokens,
            "totalTokens": total_tokens or input_tokens + output_tokens,
        }
    input_tokens = sum(int(item["usage"]["inputTokens"]) for item in calls)
    output_tokens = sum(int(item["usage"]["outputTokens"]) for item in calls)
    return {
        "source": "char-estimate",
        "inputTokens": input_tokens,
        "outputTokens": output_tokens,
        "totalTokens": input_tokens + output_tokens,
    }


def _elapsed_ms(started: float) -> float:
    return round((time.perf_counter() - started) * 1000, 2)


def _summary(results: list[dict[str, Any]]) -> dict[str, Any]:
    compatible = [item for item in results if item["providerContractStatus"] == "compatible"]
    partial = [item for item in results if item["providerContractStatus"] == "partial"]
    return {
        "scenarioCount": len(results),
        "providerCompatibleScenarioCount": len(compatible),
        "providerPartialScenarioCount": len(partial),
        "modelRawProtocolSuccessCount": sum(
            item["modelRawProtocolSuccess"] is True for item in results
        ),
        "finalReadyCount": sum(item["finalReady"] is True for item in results),
        "fallbackCount": sum(item["fallback"] is True for item in results),
        "goldenAlignmentPassCount": sum(
            item["goldenAlignment"] is not None and item["goldenAlignment"]["passed"] is True
            for item in results
        ),
        "providerCompatibleAlignmentPassCount": sum(
            item["goldenAlignment"] is not None and item["goldenAlignment"]["passed"] is True
            for item in compatible
        ),
        "totalTokens": sum(int(item["tokens"].get("totalTokens", 0)) for item in results),
        "totalLatencyMs": round(sum(float(item["latencyMs"]) for item in results), 2),
    }


async def _run(mode: str, scenario_id: str | None = None) -> dict[str, Any]:
    payload = json.loads(FIXTURE_PATH.read_text(encoding="utf-8"))
    scenario_by_id = {item["id"]: item for item in payload["scenarios"]}
    scenarios = [scenario_by_id[item["id"]] for item in _golden_manifest()["scenes"]]
    if scenario_id is not None:
        scenarios = [item for item in scenarios if item["id"] == scenario_id]
        if not scenarios:
            raise ValueError(f"Unknown scenario ID: {scenario_id}")
    settings = get_settings()
    budget = None
    if mode == "live":
        settings.enable_a2ui_model_mock = False
        settings.enable_openai_fallback = False
        settings.enable_model_failure_retry = False
        budget = DeepSeekCallBudget(
            settings.resolved_deepseek_call_budget_path,
            settings.deepseek_call_budget_limit,
        )
        budget_status_before = budget.status()
        results = []
        for scenario in scenarios:
            results.append(await _live_scene(scenario))
    else:
        budget_status_before = None
        results = []
        for scenario in scenarios:
            try:
                results.append(_deterministic_scene(scenario))
            except Exception as exc:
                results.append(_deterministic_failure(scenario, exc))
    if mode == "live":
        budget_status_after = budget.status() if budget is not None else None
    else:
        budget_status_after = None
    return {
        "schemaVersion": "cardplan-template-python-evaluation/2",
        "mode": mode,
        "createdAt": datetime.now(UTC).isoformat(),
        "fallbackRequired": False,
        "budgetBefore": asdict(budget_status_before) if budget_status_before else None,
        "budgetAfter": asdict(budget_status_after) if budget_status_after else None,
        "summary": _summary(results),
        "scenarios": results,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--mode", choices=("deterministic", "live"), default="deterministic")
    parser.add_argument("--confirm-live", action="store_true")
    parser.add_argument("--scenario")
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    if args.mode == "live" and not args.confirm_live:
        raise SystemExit("Live evaluation requires --confirm-live")
    report = asyncio.run(_run(args.mode, args.scenario))
    output = args.output or (
        DEFAULT_REPORT_ROOT / f"{args.mode}-{datetime.now(UTC).strftime('%Y%m%dT%H%M%SZ')}.json"
    )
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    os.chmod(output, 0o600)
    print(json.dumps({"output": str(output), "summary": report["summary"]}, ensure_ascii=False))
    summary = report["summary"]
    live_failed = args.mode == "live" and (
        summary["modelRawProtocolSuccessCount"] != summary["scenarioCount"]
        or summary["finalReadyCount"] != summary["scenarioCount"]
        or summary["fallbackCount"] != 0
    )
    return 1 if live_failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
