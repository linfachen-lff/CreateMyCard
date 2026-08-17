"""高级组件运行时数据的确定性派生规则；这些计算不交给 LLM。"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any


def safe_ratio(value: int | float | None, total: int | float | None) -> float | None:
    """返回 0..1 比例；真实零值返回 0，缺失或非法分母返回 ``None``。"""
    if value is None or total is None or total <= 0:
        return None
    return max(0.0, min(1.0, float(value) / float(total)))


def derive_schedule_state(
    start_at: str,
    end_at: str | None = None,
    *,
    join_uri: str | None = None,
    now: datetime | None = None,
) -> dict[str, Any]:
    current = _aware(now or datetime.now(UTC))
    start = _parse_time(start_at)
    end = _parse_time(end_at) if end_at else None
    minutes_until = int((start - current).total_seconds() // 60)
    ongoing = start <= current and (end is None or current < end)
    duration = int((end - start).total_seconds() // 60) if end is not None else None
    return {
        "minutesUntilStart": minutes_until,
        "isOngoing": ongoing,
        "isJoinable": bool(join_uri) and (ongoing or -10 <= minutes_until <= 15),
        "durationMinutes": max(0, duration) if duration is not None else None,
    }


def derive_task_summary(
    items: list[dict[str, Any]],
    *,
    now: datetime | None = None,
) -> dict[str, Any]:
    current = _aware(now or datetime.now(UTC))
    pending = [item for item in items if item.get("status") == "pending"]
    completed = [item for item in items if item.get("status") == "completed"]
    overdue = [
        item
        for item in pending
        if isinstance(item.get("dueAt"), str) and _parse_time(str(item["dueAt"])) < current
    ]
    next_due = min(
        (
            item
            for item in pending
            if isinstance(item.get("dueAt"), str) and _parse_time(str(item["dueAt"])) >= current
        ),
        key=lambda item: _parse_time(str(item["dueAt"])),
        default=None,
    )
    return {
        "pendingCount": len(pending),
        "completedCount": len(completed),
        "completionRatio": safe_ratio(len(completed), len(items)),
        "overdueCount": len(overdue),
        "nextDueItem": next_due,
    }


def derive_call_summary(records: list[dict[str, Any]]) -> dict[str, Any]:
    latest = max(
        records,
        key=lambda item: _parse_time(str(item["startedAt"])),
        default=None,
    )
    duration = latest.get("durationSeconds") if latest is not None else None
    return {
        "missedCount": sum(item.get("status") == "missed" for item in records),
        "latestRecord": latest,
        "latestDurationText": _duration_text(duration) if isinstance(duration, int) else None,
    }


def derive_battery_state(
    level_percent: int | float | None,
    charge_state: str,
    estimated_minutes: int | None = None,
) -> dict[str, Any]:
    if level_percent is None:
        state = "unknown"
    elif level_percent <= 10:
        state = "alert"
    elif level_percent <= 20:
        state = "warning"
    else:
        state = "normal"
    estimate = (
        estimated_minutes if estimated_minutes is not None and estimated_minutes >= 0 else None
    )
    return {
        "state": state,
        "chargeState": charge_state,
        "levelRatio": safe_ratio(level_percent, 100),
        "trustedEstimatedMinutes": estimate,
    }


def derive_app_usage_state(
    used_seconds: int,
    limit_seconds: int | None,
) -> dict[str, Any]:
    ratio = safe_ratio(used_seconds, limit_seconds)
    return {
        "usageRatio": ratio,
        "nearLimit": ratio is not None and 0.8 <= ratio <= 1.0,
        "overLimit": limit_seconds is not None and used_seconds > limit_seconds,
        "overSeconds": max(0, used_seconds - limit_seconds) if limit_seconds is not None else None,
    }


def derive_workout_state(
    duration_seconds: int,
    calories_kcal: int | float | None = None,
    goal_seconds: int | None = None,
) -> dict[str, Any]:
    return {
        "durationText": _duration_text(duration_seconds),
        "caloriesKcal": calories_kcal,
        "goalRatio": safe_ratio(duration_seconds, goal_seconds),
    }


def derive_sleep_state(
    sleep_at: str,
    wake_at: str,
    *,
    insufficient_threshold_seconds: int = 7 * 60 * 60,
) -> dict[str, Any]:
    duration = max(0, int((_parse_time(wake_at) - _parse_time(sleep_at)).total_seconds()))
    return {
        "durationSeconds": duration,
        "durationText": _duration_text(duration),
        "isInsufficient": duration < insufficient_threshold_seconds,
        "sleepWindow": {"sleepAt": sleep_at, "wakeAt": wake_at},
    }


def derive_location_state(
    updated_at: str,
    *,
    now: datetime | None = None,
    max_age_seconds: int = 15 * 60,
) -> dict[str, Any]:
    current = _aware(now or datetime.now(UTC))
    age_seconds = max(0, int((current - _parse_time(updated_at)).total_seconds()))
    return {"ageSeconds": age_seconds, "isStale": age_seconds > max_age_seconds}


def derive_system_mode_state(
    *,
    focus_enabled: bool,
    do_not_disturb: bool,
    audio_mode: str,
    focus_end_at: str | None = None,
    now: datetime | None = None,
) -> dict[str, Any]:
    if audio_mode not in {"ring", "vibrate", "silent"}:
        raise ValueError("audioMode must be ring, vibrate, or silent")
    remaining = None
    if focus_enabled and focus_end_at:
        current = _aware(now or datetime.now(UTC))
        remaining = max(0, int((_parse_time(focus_end_at) - current).total_seconds() // 60))
    return {
        "focusEnabled": focus_enabled,
        "doNotDisturb": do_not_disturb,
        "audioMode": audio_mode,
        "focusRemainingMinutes": remaining,
    }


def derive_bluetooth_state(
    *,
    connection_state: str,
    updated_at: str | None,
    battery_percent: int | float | None,
    battery_parts: dict[str, int | float | None] | None = None,
    now: datetime | None = None,
    max_age_seconds: int = 15 * 60,
) -> dict[str, Any]:
    parts = battery_parts or {}
    available_parts = [value for value in parts.values() if value is not None]
    stale = False
    if updated_at is not None:
        stale = derive_location_state(
            updated_at,
            now=now,
            max_age_seconds=max_age_seconds,
        )["isStale"]
    return {
        "connectionState": connection_state,
        "isStale": stale,
        "missingBatteryParts": [name for name, value in parts.items() if value is None],
        "summaryBatteryPercent": (min(available_parts) if available_parts else battery_percent),
    }


def _parse_time(value: str) -> datetime:
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise ValueError(f"invalid ISO datetime: {value}") from exc
    return _aware(parsed)


def _aware(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value.astimezone(UTC)


def _duration_text(seconds: int) -> str:
    safe_seconds = max(0, seconds)
    hours, remainder = divmod(safe_seconds, 3600)
    minutes = remainder // 60
    if hours:
        return f"{hours}小时{minutes}分钟"
    return f"{minutes}分钟"
