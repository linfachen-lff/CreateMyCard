"""Golden structure gates for the Provider Template migration.

The retained Python constructors are the migration oracle.  Runtime-bound
content and values intentionally differ, while the component tree and styles
must remain identical.
"""

from __future__ import annotations

import json
from typing import Any

from overview_test_support import compile_health_scope
from test_activity_overview import _activity_task
from test_app_usage_overview import _app_assets, _app_usage_task, _compile_app_usage
from test_battery_overview import _battery_assets, _battery_task, _compile_battery
from test_bluetooth_device_overview import (
    _MISSING,
    _bluetooth_task,
)
from test_bluetooth_device_overview import (
    _compile as _compile_bluetooth,
)
from test_date_overview import _compile_date
from test_resource_usage_overview import _compile_resource, _resource_assets, _resource_task
from test_schedule_overview import _compile_schedule, _schedule_assets, _schedule_task
from test_sleep_overview import _compile_sleep, _sleep_assets, _sleep_task
from test_workout_overview import _countdown_task, _latest_task


def _component_signature(compilation: Any) -> list[dict[str, Any]]:
    messages = [json.loads(line) for line in compilation.a2ui.splitlines()]
    components = messages[1]["updateComponents"]["components"]
    signature: list[dict[str, Any]] = []
    for component in components:
        item = {
            key: value
            for key, value in component.items()
            if key not in {"id", "children", "content", "text", "value", "select", "source", "src"}
        }
        if "children" in component:
            item["childCount"] = len(component["children"])
        signature.append(item)
    return signature


def _normalize_runtime_expressions(provider: Any, python: Any) -> tuple[Any, Any]:
    if isinstance(provider, str) and "{{" in provider:
        return "<runtime-expression>", "<runtime-expression>"
    if isinstance(provider, dict) and isinstance(python, dict):
        provider_result: dict[str, Any] = {}
        python_result: dict[str, Any] = {}
        for key in provider.keys() | python.keys():
            provider_result[key], python_result[key] = _normalize_runtime_expressions(
                provider.get(key), python.get(key)
            )
        return provider_result, python_result
    if isinstance(provider, list) and isinstance(python, list):
        pairs = [
            _normalize_runtime_expressions(provider_item, python_item)
            for provider_item, python_item in zip(provider, python, strict=True)
        ]
        return [item[0] for item in pairs], [item[1] for item in pairs]
    return provider, python


def _assert_golden(case: str, provider: Any, python: Any) -> None:
    provider_signature, python_signature = _normalize_runtime_expressions(
        _component_signature(provider),
        _component_signature(python),
    )
    assert provider_signature == python_signature, case
    assert provider.stats.template_used_ids
    assert python.stats.template_used_ids == ()
    assert "IfParam" not in provider.a2ui
    assert "IfMissingParam" not in provider.a2ui
    assert "IfBind" not in provider.a2ui
    assert "IfMissingBind" not in provider.a2ui


def test_all_migrated_provider_templates_match_canonical_python_golden() -> None:
    battery_task = _battery_task()
    _assert_golden(
        "battery",
        _compile_battery(
            battery_task,
            'SingleFocusLayout(Template("BatteryOverview@1","normal",{}));',
        )[0],
        _compile_battery(
            battery_task,
            'SingleFocusLayout(BatteryOverview({"variant":"normal","role":"hero"}));',
        )[0],
    )

    resource_task = _resource_task()
    _assert_golden(
        "resource",
        _compile_resource(
            resource_task,
            'SingleFocusLayout(Template("ResourceUsageOverview@1","memory",{}));',
        )[0],
        _compile_resource(
            resource_task,
            'SingleFocusLayout(ResourceUsageOverview({"variant":"memory","role":"hero"}));',
        )[0],
    )

    bluetooth_task = _bluetooth_task()
    _assert_golden(
        "bluetooth",
        _compile_bluetooth(
            bluetooth_task,
            'SingleFocusLayout(Template("BluetoothDeviceOverview@1","earbudsFull",{}));',
        )[0],
        _compile_bluetooth(
            bluetooth_task,
            'SingleFocusLayout(BluetoothDeviceOverview({"variant":"earbuds","role":"hero"}));',
        )[0],
    )

    _assert_golden(
        "date",
        _compile_date(
            "2x2",
            'SingleFocusLayout(Template("DateOverview@1","dateHero",{}));',
        ),
        _compile_date(
            "2x2",
            'SingleFocusLayout(DateOverview({"variant":"dateHero","role":"hero"}));',
        ),
    )

    schedule_task = _schedule_task()
    _assert_golden(
        "schedule",
        _compile_schedule(
            schedule_task,
            'SingleFocusLayout(Template("ScheduleOverview@1","nextEventLocation",{}));',
        )[0],
        _compile_schedule(
            schedule_task,
            'SingleFocusLayout(ScheduleOverview({"variant":"nextEvent","role":"hero"}));',
        )[0],
    )

    app_task = _app_usage_task()
    _assert_golden(
        "app-usage",
        _compile_app_usage(
            app_task,
            'SingleFocusLayout(Template("AppUsageOverview@1","singleAppDetailed",{}));',
        )[0],
        _compile_app_usage(
            app_task,
            'SingleFocusLayout(AppUsageOverview({"variant":"singleApp","role":"hero"}));',
        )[0],
    )

    activity_task = _activity_task()
    _assert_golden(
        "activity",
        compile_health_scope(
            activity_task,
            ("ActivityOverview",),
            {"GetHealthAndSportSummary"},
            'SingleFocusLayout(Template("ActivityOverview@1","dailySummary",{}));',
        )[0],
        compile_health_scope(
            activity_task,
            ("ActivityOverview",),
            {"GetHealthAndSportSummary"},
            'SingleFocusLayout(ActivityOverview({"variant":"dailySummary","role":"hero"}));',
        )[0],
    )

    workout_task = _latest_task()
    _assert_golden(
        "workout",
        compile_health_scope(
            workout_task,
            ("WorkoutOverview",),
            {"GetHealthAndSportSummary"},
            'SingleFocusLayout(Template("WorkoutOverview@1","latest",{}));',
        )[0],
        compile_health_scope(
            workout_task,
            ("WorkoutOverview",),
            {"GetHealthAndSportSummary"},
            'SingleFocusLayout(WorkoutOverview({"variant":"latest","role":"hero"}));',
        )[0],
    )

    countdown_task = _countdown_task()
    _assert_golden(
        "countdown",
        compile_health_scope(
            countdown_task,
            ("WorkoutOverview",),
            {"GetCountdownDays"},
            'SingleFocusLayout(Template("WorkoutCountdown@1","countdown",{}));',
        )[0],
        compile_health_scope(
            countdown_task,
            ("WorkoutOverview",),
            {"GetCountdownDays"},
            'SingleFocusLayout(WorkoutOverview({"variant":"countdown","role":"hero"}));',
        )[0],
    )

    sleep_task = _sleep_task()
    _assert_golden(
        "sleep",
        _compile_sleep(
            sleep_task,
            'SingleFocusLayout(Template("SleepOverview@1","durationDetailed",{}));',
        )[0],
        _compile_sleep(
            sleep_task,
            'SingleFocusLayout(SleepOverview({"variant":"duration","role":"hero"}));',
        )[0],
    )


def test_wide_and_conditional_provider_variants_match_python_golden() -> None:
    activity_task = _activity_task(size="2x4")
    _assert_golden(
        "activity-wide",
        compile_health_scope(
            activity_task,
            ("ActivityOverview",),
            {"GetHealthAndSportSummary"},
            'SingleFocusLayout(Template("ActivityOverview@1","dailySummaryWide",{}));',
        )[0],
        compile_health_scope(
            activity_task,
            ("ActivityOverview",),
            {"GetHealthAndSportSummary"},
            'SingleFocusLayout(ActivityOverview({"variant":"dailySummary","role":"hero"}));',
        )[0],
    )

    sleep_task = _sleep_task(
        size="2x4",
        status="睡眠充足",
        fall_asleep="23:10",
        wakeup="06:15",
    )
    _assert_golden(
        "sleep-wide-status-details",
        _compile_sleep(
            sleep_task,
            'SingleFocusLayout(Template("SleepOverview@1","scheduleDetailedStatus",{}));',
        )[0],
        _compile_sleep(
            sleep_task,
            'SingleFocusLayout(SleepOverview({"variant":"duration","role":"hero"}));',
        )[0],
    )


def test_provider_template_dynamic_logic_is_preserved_as_device_expressions() -> None:
    battery = _compile_battery(
        _battery_task(),
        'SingleFocusLayout(Template("BatteryOverview@1","normal",{}));',
    )[0]
    bluetooth = _compile_bluetooth(
        _bluetooth_task(),
        'SingleFocusLayout(Template("BluetoothDeviceOverview@1","earbudsFull",{}));',
    )[0]
    resource = _compile_resource(
        _resource_task(),
        'SingleFocusLayout(Template("ResourceUsageOverview@1","memory",{}));',
    )[0]

    assert (
        "{{ '电量 ' + ${/data/GetPhoneBatteryInfo/batterySOCText} + '，' + "
        "${/data/GetPhoneBatteryInfo/batteryCapacityLevelDesc} + '，' + "
        "${/data/GetPhoneBatteryInfo/chargingStatusDesc} }}"
    ) in battery.a2ui
    assert "${/data/GetEarphoneInfo/leftBatteryLevel} <= 20 ?" in bluetooth.a2ui
    assert "${/data/GetEarphoneInfo/rightBatteryLevel} <= 20 ?" in bluetooth.a2ui
    assert "${/data/GetSystemMemInfo/usagePercent} + 0.5" in resource.a2ui


def test_optional_provider_assets_match_python_golden_without_extra_variants() -> None:
    battery_task = _battery_task(assets=_battery_assets())
    _assert_golden(
        "battery-icon",
        _compile_battery(
            battery_task,
            'SingleFocusLayout(Template("BatteryOverview@1","normal",'
            '{"batteryIcon":"resources/base/media/phone-battery.svg"}));',
        )[0],
        _compile_battery(
            battery_task,
            'SingleFocusLayout(BatteryOverview({"variant":"normal","role":"hero",'
            '"batteryIcon":"resources/base/media/phone-battery.svg"}));',
        )[0],
    )

    resource_task = _resource_task(assets=_resource_assets())
    _assert_golden(
        "resource-icon",
        _compile_resource(
            resource_task,
            'SingleFocusLayout(Template("ResourceUsageOverview@1","memory",'
            '{"icon":"resources/base/media/memory.svg"}));',
        )[0],
        _compile_resource(
            resource_task,
            'SingleFocusLayout(ResourceUsageOverview({"variant":"memory","role":"hero",'
            '"icon":"resources/base/media/memory.svg"}));',
        )[0],
    )

    bluetooth_task = _bluetooth_task()
    provider_params = (
        '{"sourceIcon":"resources/base/media/earphone-source.svg",'
        '"leftEarIcon":"resources/base/media/left-ear.svg",'
        '"rightEarIcon":"resources/base/media/right-ear.svg"}'
    )
    direct_params = (
        '{"variant":"earbuds","role":"hero",'
        '"sourceIcon":"resources/base/media/earphone-source.svg",'
        '"leftEarIcon":"resources/base/media/left-ear.svg",'
        '"rightEarIcon":"resources/base/media/right-ear.svg"}'
    )
    _assert_golden(
        "bluetooth-icons",
        _compile_bluetooth(
            bluetooth_task,
            'SingleFocusLayout(Template("BluetoothDeviceOverview@1","earbudsFull",'
            f"{provider_params}));",
        )[0],
        _compile_bluetooth(
            bluetooth_task,
            f"SingleFocusLayout(BluetoothDeviceOverview({direct_params}));",
        )[0],
    )

    app_task = _app_usage_task(assets=_app_assets())
    _assert_golden(
        "app-icon",
        _compile_app_usage(
            app_task,
            'SingleFocusLayout(Template("AppUsageOverview@1","singleAppDetailed",'
            '{"appIcon":"resources/base/media/douyin.svg"}));',
        )[0],
        _compile_app_usage(
            app_task,
            'SingleFocusLayout(AppUsageOverview({"variant":"singleApp","role":"hero",'
            '"appIcon":"resources/base/media/douyin.svg"}));',
        )[0],
    )

    sleep_task = _sleep_task(assets=_sleep_assets())
    _assert_golden(
        "sleep-icon",
        _compile_sleep(
            sleep_task,
            'SingleFocusLayout(Template("SleepOverview@1","durationDetailed",'
            '{"sourceIcon":"resources/base/media/moon.svg"}));',
        )[0],
        _compile_sleep(
            sleep_task,
            'SingleFocusLayout(SleepOverview({"variant":"duration","role":"hero",'
            '"sourceIcon":"resources/base/media/moon.svg"}));',
        )[0],
    )

    schedule_task = _schedule_task(assets=_schedule_assets())
    _assert_golden(
        "schedule-icons",
        _compile_schedule(
            schedule_task,
            'SingleFocusLayout(Template("ScheduleOverview@1","nextEventLocation",'
            '{"sourceIcon":"resources/base/media/calendar.svg",'
            '"timeIcon":"resources/base/media/time.svg",'
            '"locationIcon":"resources/base/media/location.svg"}));',
        )[0],
        _compile_schedule(
            schedule_task,
            'SingleFocusLayout(ScheduleOverview({"variant":"nextEvent","role":"hero",'
            '"sourceIcon":"resources/base/media/calendar.svg",'
            '"timeIcon":"resources/base/media/time.svg",'
            '"locationIcon":"resources/base/media/location.svg"}));',
        )[0],
    )

    health_assets = [
        {
            "src": "resources/base/media/steps.svg",
            "description": "步数图标",
            "sceneTags": ["steps"],
        },
        {
            "src": "resources/base/media/calories.svg",
            "description": "热量图标",
            "sceneTags": ["calories"],
        },
        {
            "src": "resources/base/media/distance.svg",
            "description": "距离图标",
            "sceneTags": ["distance"],
        },
        {
            "src": "resources/base/media/run.svg",
            "description": "运动图标",
            "sceneTags": ["sport", "run", "workout"],
        },
    ]
    activity_task = _activity_task().model_copy(update={"assetCandidates": health_assets})
    _assert_golden(
        "activity-icons",
        compile_health_scope(
            activity_task,
            ("ActivityOverview",),
            {"GetHealthAndSportSummary"},
            'SingleFocusLayout(Template("ActivityOverview@1","dailySummary",'
            '{"stepsIcon":"resources/base/media/steps.svg",'
            '"caloriesIcon":"resources/base/media/calories.svg",'
            '"distanceIcon":"resources/base/media/distance.svg"}));',
        )[0],
        compile_health_scope(
            activity_task,
            ("ActivityOverview",),
            {"GetHealthAndSportSummary"},
            'SingleFocusLayout(ActivityOverview({"variant":"dailySummary","role":"hero",'
            '"stepsIcon":"resources/base/media/steps.svg",'
            '"caloriesIcon":"resources/base/media/calories.svg",'
            '"distanceIcon":"resources/base/media/distance.svg"}));',
        )[0],
    )

    workout_task = _latest_task().model_copy(update={"assetCandidates": health_assets})
    _assert_golden(
        "workout-icons",
        compile_health_scope(
            workout_task,
            ("WorkoutOverview",),
            {"GetHealthAndSportSummary"},
            'SingleFocusLayout(Template("WorkoutOverview@1","latest",'
            '{"sourceIcon":"resources/base/media/run.svg",'
            '"caloriesIcon":"resources/base/media/calories.svg"}));',
        )[0],
        compile_health_scope(
            workout_task,
            ("WorkoutOverview",),
            {"GetHealthAndSportSummary"},
            'SingleFocusLayout(WorkoutOverview({"variant":"latest","role":"hero",'
            '"sourceIcon":"resources/base/media/run.svg",'
            '"caloriesIcon":"resources/base/media/calories.svg"}));',
        )[0],
    )

    countdown_task = _countdown_task().model_copy(update={"assetCandidates": health_assets})
    _assert_golden(
        "countdown-icon",
        compile_health_scope(
            countdown_task,
            ("WorkoutOverview",),
            {"GetCountdownDays"},
            'SingleFocusLayout(Template("WorkoutCountdown@1","countdown",'
            '{"sourceIcon":"resources/base/media/run.svg"}));',
        )[0],
        compile_health_scope(
            countdown_task,
            ("WorkoutOverview",),
            {"GetCountdownDays"},
            'SingleFocusLayout(WorkoutOverview({"variant":"countdown","role":"hero",'
            '"sourceIcon":"resources/base/media/run.svg"}));',
        )[0],
    )


def test_phone_earphone_provider_compositions_match_python_golden() -> None:
    for size, layout, bluetooth_variant in (
        ("2x2", "PeerPairLayout", "earbudsPhone"),
        ("2x4", "HeroSupportLayout", "earbudsPhoneWide"),
    ):
        task = _bluetooth_task(
            size=size,
            query="显示手机和蓝牙耳机设备电量",
            include_phone=True,
        )
        provider = (
            f'{layout}(Template("BatteryOverview@1","normalPhone",'
            '{"batteryIcon":"resources/base/media/phone.svg"}),'
            f'Template("BluetoothDeviceOverview@1","{bluetooth_variant}",'
            '{"leftEarIcon":"resources/base/media/left-ear.svg",'
            '"rightEarIcon":"resources/base/media/right-ear.svg"}));'
        )
        direct = (
            f'{layout}(BatteryOverview({{"variant":"normal","role":"hero",'
            '"batteryIcon":"resources/base/media/phone.svg"}),'
            'BluetoothDeviceOverview({"variant":"earbuds","role":"support",'
            '"leftEarIcon":"resources/base/media/left-ear.svg",'
            '"rightEarIcon":"resources/base/media/right-ear.svg"}));'
        )
        _assert_golden(
            f"phone-earphone-{size}",
            _compile_bluetooth(
                task,
                provider,
                ("BatteryOverview", "BluetoothDeviceOverview"),
            )[0],
            _compile_bluetooth(
                task,
                direct,
                ("BatteryOverview", "BluetoothDeviceOverview"),
            )[0],
        )

    disconnected = _bluetooth_task(
        connected=False,
        query="显示手机和蓝牙耳机设备电量",
        include_phone=True,
    )
    _assert_golden(
        "phone-earphone-disconnected",
        _compile_bluetooth(
            disconnected,
            'PeerPairLayout(Template("BatteryOverview@1","normalPhone",{}),'
            'Template("BluetoothDeviceOverview@1","disconnectedPhone",{}));',
            ("BatteryOverview", "BluetoothDeviceOverview"),
        )[0],
        _compile_bluetooth(
            disconnected,
            'PeerPairLayout(BatteryOverview({"variant":"normal","role":"hero"}),'
            'BluetoothDeviceOverview({"variant":"earbuds","role":"support"}));',
            ("BatteryOverview", "BluetoothDeviceOverview"),
        )[0],
    )


def test_bluetooth_optional_binding_matrix_matches_python_golden() -> None:
    cases = (
        ("case", _MISSING, _MISSING, 64, "earbuds"),
        ("left", 76, _MISSING, _MISSING, "leftEarbud"),
        ("right", _MISSING, 72, _MISSING, "rightEarbud"),
        ("left-case", 76, _MISSING, 64, "leftEarbud"),
        ("right-case", _MISSING, 72, 64, "rightEarbud"),
        ("pair", 76, 72, _MISSING, "earbudPair"),
        ("full", 76, 72, 64, "earbudsFull"),
    )
    for case, left, right, case_battery, compact_variant in cases:
        for size in ("2x2", "2x4"):
            task = _bluetooth_task(
                size=size,
                left=left,
                right=right,
                case=case_battery,
            )
            provider_variant = compact_variant if size == "2x2" else "earbudsDynamicWide"
            _assert_golden(
                f"bluetooth-{case}-{size}",
                _compile_bluetooth(
                    task,
                    'SingleFocusLayout(Template("BluetoothDeviceOverview@1",'
                    f'"{provider_variant}",{{}}));',
                )[0],
                _compile_bluetooth(
                    task,
                    "SingleFocusLayout(BluetoothDeviceOverview("
                    '{"variant":"earbuds","role":"hero"}));',
                )[0],
            )

        for size, layout, provider_variant in (
            ("2x2", "PeerPairLayout", "earbudsPhone"),
            ("2x4", "HeroSupportLayout", "earbudsPhoneWide"),
        ):
            task = _bluetooth_task(
                size=size,
                query="显示手机和蓝牙耳机设备电量",
                left=left,
                right=right,
                case=case_battery,
                include_phone=True,
            )
            _assert_golden(
                f"bluetooth-{case}-phone-{size}",
                _compile_bluetooth(
                    task,
                    f'{layout}(Template("BatteryOverview@1","normalPhone",{{}}),'
                    'Template("BluetoothDeviceOverview@1",'
                    f'"{provider_variant}",{{}}));',
                    ("BatteryOverview", "BluetoothDeviceOverview"),
                )[0],
                _compile_bluetooth(
                    task,
                    f"{layout}(BatteryOverview("
                    '{"variant":"normal","role":"hero"}),'
                    "BluetoothDeviceOverview("
                    '{"variant":"earbuds","role":"support"}));',
                    ("BatteryOverview", "BluetoothDeviceOverview"),
                )[0],
            )
