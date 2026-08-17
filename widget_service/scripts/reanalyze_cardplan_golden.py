#!/usr/bin/env python3
"""Recompile saved real-model CardPlan evidence without spending model budget."""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import json_repair

SERVICE_ROOT = Path(__file__).resolve().parents[1]
CLOUD_ROOT = SERVICE_ROOT / "cloud"
if str(CLOUD_ROOT) not in sys.path:
    sys.path.insert(0, str(CLOUD_ROOT))

from evaluate_cardplan_golden import (  # noqa: E402
    FIXTURE_PATH,
    _a2ui_summary,
    _aggregate_usage,
    _alignment,
    _scenario_inputs,
    _summary,
)

from services.advanced_component_pipeline.models import AdvancedScopeBrief  # noqa: E402
from services.advanced_component_pipeline.ux_mixed_framer import (  # noqa: E402
    frame_ux_layout_root_children,
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


def _sources(paths: list[Path]) -> tuple[dict[str, dict[str, Any]], list[dict[str, Any]]]:
    selected: dict[str, dict[str, Any]] = {}
    reports: list[dict[str, Any]] = []
    for path in paths:
        report = json.loads(path.read_text(encoding="utf-8"))
        reports.append(report)
        for scene in report["scenarios"]:
            selected[scene["scenarioId"]] = scene
    return selected, reports


def _reanalyze_scene(
    fixture: dict[str, Any],
    evidence: dict[str, Any],
) -> dict[str, Any]:
    started = time.perf_counter()
    calls = evidence.get("modelCalls", [])
    result = dict(evidence)
    body_calls = [
        item for item in calls if str(item.get("phase", "")).startswith("advanced-mixed-body")
    ]
    if not calls or not body_calls:
        result.update(
            modelRawProtocolSuccess=False,
            finalReady=False,
            fallback=False,
            goldenAlignment=_failed_alignment(
                evidence.get("goldenAlignment"),
                "Expected saved Advanced Scope and mixed-body model calls.",
            ),
            failureReason="Expected saved Advanced Scope and mixed-body model calls.",
        )
        return result
    try:
        effective_scope = evidence.get("uiBrief")
        brief_payload = (
            effective_scope
            if isinstance(effective_scope, dict)
            else json_repair.loads(calls[0]["raw_output"])
        )
        scope = AdvancedScopeBrief.model_validate(brief_payload)
        task_spec, card_spec = _scenario_inputs(fixture)
        registry = get_cardplan_registry()
        projection = build_ux_mixed_prompt(
            task_spec=task_spec,
            card_spec=card_spec,
            scope=scope,
            registry=registry,
        )
        profile = A2UIProtocolRegistry.read_design_protocol_profile(TERSE_DSL_NESTED2_PROFILE_ID)
        framed_output, _layout_children_framed = frame_ux_layout_root_children(
            body_calls[-1]["raw_output"],
            size=task_spec.size,
            registry=registry,
        )
        compilation = compile_ux_layout_card(
            framed_output,
            task_spec=task_spec,
            contract=projection.contract,
            protocol_profile=profile,
            registry=registry,
            business_title=card_spec.get("title"),
        )
        actual = _a2ui_summary(compilation.a2ui, compilation.stats.action_used_ids)
        calls[0]["protocol_success"] = True
        body_calls[-1]["protocol_success"] = True
        baseline = evidence.get("standardA2UIBaseline", {})
        baseline_summary = baseline.get("summary") if isinstance(baseline, dict) else None
        if not isinstance(baseline_summary, dict):
            baseline_summary = fixture["goldenSummary"]
        result.update(
            uiBrief=scope.model_dump(mode="json", by_alias=True),
            candidateTemplates=list(projection.requested_template_ids),
            wholeCardConfidence=None,
            wholeCardCandidates=[],
            confidenceBypassed=True,
            route="hybrid-template",
            rawHybridOutput=compilation.raw_output,
            effectiveHybridOutput=compilation.effective_output,
            compiledA2UI=compilation.a2ui,
            modelCalls=calls,
            modelRawProtocolSuccess=bool(evidence.get("modelRawProtocolSuccess")),
            uiBriefFallback=False,
            finalReady=True,
            fallback=False,
            template={
                "callCount": compilation.stats.template_call_count,
                "usedIds": compilation.stats.template_used_ids,
                "expandedComponentCount": compilation.stats.expanded_component_count,
            },
            tokens=_aggregate_usage(calls),
            latencyMs=round(
                float(evidence.get("latencyMs", 0)) + (time.perf_counter() - started) * 1000,
                2,
            ),
            goldenAlignment=_alignment(
                actual,
                baseline_summary,
                ignored_title=fixture.get("title", ""),
            ),
            failureReason="",
        )
    except Exception as exc:
        failure_reason = f"{type(exc).__name__}: {exc}"
        if calls:
            calls[0]["protocol_success"] = bool(calls[0].get("raw_output", "").strip())
        if body_calls:
            body_calls[-1]["protocol_success"] = False
        result.update(
            modelCalls=calls,
            modelRawProtocolSuccess=False,
            finalReady=False,
            fallback=False,
            goldenAlignment=_failed_alignment(evidence.get("goldenAlignment"), failure_reason),
            failureReason=failure_reason,
        )
    return result


def _failed_alignment(existing: Any, reason: str) -> dict[str, Any]:
    alignment = dict(existing) if isinstance(existing, dict) else {}
    alignment["passed"] = False
    alignment["failureReasons"] = [reason]
    return alignment


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", type=Path, action="append", required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    evidence, reports = _sources(args.input)
    fixture = json.loads(FIXTURE_PATH.read_text(encoding="utf-8"))
    results = [_reanalyze_scene(scene, evidence[scene["id"]]) for scene in fixture["scenarios"]]
    summary = _summary(results)
    report = {
        "schemaVersion": "cardplan-template-python-evaluation/1",
        "mode": "live-reanalysis",
        "createdAt": datetime.now(UTC).isoformat(),
        "sourceReports": [str(path) for path in args.input],
        "fallbackRequired": False,
        "budgetBefore": reports[0].get("budgetBefore"),
        "budgetAfter": reports[-1].get("budgetAfter"),
        "summary": summary,
        "scenarios": results,
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    os.chmod(args.output, 0o600)
    print(json.dumps({"output": str(args.output), "summary": summary}))
    passed = summary["finalReadyCount"] == len(results)
    no_fallback = summary["fallbackCount"] == 0
    return 0 if passed and no_fallback else 1


if __name__ == "__main__":
    raise SystemExit(main())
