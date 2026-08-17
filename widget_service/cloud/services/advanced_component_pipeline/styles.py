"""高级组件的服务端主题 Catalog。"""

from __future__ import annotations

from .models import UIBrief

STYLE_TOKENS: dict[str, dict[str, object]] = {
    "electric-blue": {
        "gradient": {
            "direction": "Bottom",
            "colors": [["#FF087CFF", 0.0], ["#FF02B8DF", 1.0]],
        },
        "background": "#FF087CFF",
        "surface": "#33FFFFFF",
        "surfaceBorder": "#66FFFFFF",
        "primary": "#FFFFFFFF",
        "secondary": "#D9FFFFFF",
        "accent": "#FF087CFF",
        "accentSecondary": "#FF02B8DF",
        "track": "#55FFFFFF",
        "button": "#FFFFFFFF",
        "buttonBorder": "#99FFFFFF",
        "danger": "#FFFF4E64",
    },
    "race-orange": {
        "gradient": {
            "direction": "Bottom",
            "colors": [["#FFFF4B00", 0.0], ["#FFFF9700", 1.0]],
        },
        "background": "#FFFF4B00",
        "surface": "#33FFFFFF",
        "surfaceBorder": "#66FFFFFF",
        "primary": "#FFFFFFFF",
        "secondary": "#E6FFFFFF",
        "accent": "#FFFF5A00",
        "accentSecondary": "#FFFF9700",
        "track": "#55FFFFFF",
        "button": "#FFFFFFFF",
        "buttonBorder": "#FFFFFFFF",
        "danger": "#FFFFE000",
    },
    "night-violet": {
        "gradient": {
            "direction": "RightBottom",
            "colors": [
                ["#FF2E124D", 0.0],
                ["#FF67299F", 0.34],
                ["#FF6B2BCA", 0.56],
                ["#FF542AC2", 0.76],
                ["#FF7355EA", 1.0],
            ],
        },
        "background": "#FF542AC2",
        "surface": "#3DFFFFFF",
        "surfaceBorder": "#5CFFFFFF",
        "primary": "#FFFFFFFF",
        "secondary": "#D6FFFFFF",
        "accent": "#FFF7CE00",
        "track": "#4D4F2E83",
        "button": "#33FFFFFF",
        "buttonBorder": "#72FFFFFF",
        "danger": "#FFFF5376",
    },
    "warm-copper": {
        "gradient": {
            "direction": "RightBottom",
            "colors": [["#FF8B513F", 0.0], ["#FFC18470", 1.0]],
        },
        "background": "#FFC18470",
        "surface": "#22FFFFFF",
        "surfaceBorder": "#78FFE5D6",
        "primary": "#FFFFFFFF",
        "secondary": "#C8F7E9DF",
        "accent": "#FFFFE300",
        "track": "#38FFFFFF",
        "button": "#18FFFFFF",
        "buttonBorder": "#89FFE9D9",
        "danger": "#FFFF4E64",
    },
    "system-teal": {
        "gradient": {
            "direction": "RightBottom",
            "colors": [["#FF062A42", 0.0], ["#FF08779B", 1.0]],
        },
        "background": "#FF08779B",
        "surface": "#6B143B5B",
        "surfaceBorder": "#35FFFFFF",
        "primary": "#FFFFFFFF",
        "secondary": "#C9E6F3FF",
        "accent": "#FF42D67A",
        "track": "#3CFFFFFF",
        "button": "#80126791",
        "buttonBorder": "#668FD2ED",
        "danger": "#FFFF4770",
        "metricPalette": ["#FF56D880", "#FF67D86F", "#FF39C9A0"],
    },
}

# aesthetic_plan_a 原始 A2UI 模板使用的 token 名称。保留现有名称供 Terse
# 模板使用，同时提供原模板的同义字段，避免两条输出链路互相改写。
for _tokens in STYLE_TOKENS.values():
    _gradient = _tokens["gradient"]
    _tokens["rootGradient"] = _gradient["colors"]
    _tokens["textPrimary"] = _tokens["primary"]
    _tokens["textSecondary"] = _tokens["secondary"]
    _tokens.setdefault("accentSecondary", _tokens["secondary"])


def select_style(brief: UIBrief) -> tuple[str, dict[str, object]]:
    """根据抽象意图选择受控主题，模板不接受模型直接下发的颜色。"""
    text = f"{brief.purpose} {brief.visual_tone}".lower()
    if any(item in text for item in ("family-care", "亲人关怀", "家庭关怀", "weather care")):
        style_id = "electric-blue"
    elif any(item in text for item in ("race-countdown", "赛事", "马拉松")):
        style_id = "race-orange"
    elif any(item in text for item in ("schedule", "warm", "focus", "日程")):
        style_id = "warm-copper"
    elif any(item in text for item in ("resource", "technical", "memory", "内存")):
        style_id = "system-teal"
    else:
        style_id = "night-violet"
    return style_id, STYLE_TOKENS[style_id]
