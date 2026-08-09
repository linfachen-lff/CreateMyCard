```cardspec
{
  "title": "马拉松倒计时",
  "description": "马拉松赛事倒计时卡片，带Design Token极简协议，2*2规格，顶部显示赛事名称和跑步图标，中间大字展示倒计时天数，底部显示赛事当日天气预报（温度、天气状况、空气质量、紫外线），整体科技感运动风格",
  "suggestSize": "2x2",
  "dataBindings": [
    {
      "capabilityId": "GetCountdownDays",
      "arguments": {
        "targetDate": "2026-12-06"
      },
      "writeResultTo": "/data/countdown"
    },
    {
      "capabilityId": "ViewWeather",
      "arguments": {
        "districtName": "青浦区",
        "forecastDays": 1,
        "prefectureName": "上海市"
      },
      "writeResultTo": "/data/weather"
    }
  ]
}
```
```genui
{"version":"v0.9","createSurface":{"surfaceId":"surface_card","catalogId":"ohos.a2ui.extended.catalog.form","width":140,"height":140}}
{"version":"v0.9","updateComponents":{"surfaceId":"surface_card","root":"root","components":[{"id":"root","component":"Column","children":["title_area","content_area","action_area"],"itemMargin":8,"styles":{"width":"matchParent","height":"matchParent","linearGradient":{"angle":145,"colors":[["#FFFFFFFF",0.0],["#FFF0F5FF",0.44],["#FF8EB3FF",1.0]]},"borderRadius":20,"padding":12,"clip":true}},{"id":"title_area","component":"Row","children":["title_col","title_icon"],"itemMargin":4,"styles":{"width":"matchParent","alignItems":"start"}},{"id":"title_col","component":"Column","children":["title_main","title_sub"],"itemMargin":4,"styles":{"width":"matchParent","layoutWeight":1,"flexShrink":1}},{"id":"title_main","component":"Text","content":"马拉松倒计时","styles":{"fontSize":12,"fontWeight":700,"width":"matchParent","maxLines":1,"textOverflow":"ellipsis"}},{"id":"title_sub","component":"Text","content":"今日开跑","styles":{"fontSize":12,"fontWeight":400,"width":"matchParent","maxLines":1,"textOverflow":"ellipsis"}},{"id":"title_icon","component":"Image","src":"resources/base/media/stopwatch_fill.svg","styles":{"width":20,"height":20,"borderRadius":4,"clip":true,"flexShrink":0}},{"id":"content_area","component":"Column","children":["kv_row_1","kv_row_2"],"itemMargin":8,"styles":{"width":"matchParent","layoutWeight":1,"justifyContent":"end"}},{"id":"kv_row_1","component":"Row","children":["label_1","value_1"],"itemMargin":8,"styles":{"width":"matchParent","alignItems":"center"}},{"id":"label_1","component":"Text","content":"距离","styles":{"fontSize":12,"fontWeight":400,"layoutWeight":1,"width":"matchParent","flexShrink":1,"maxLines":1,"textOverflow":"ellipsis"}},{"id":"value_1","component":"Text","content":"{{ ${/data/countdown/countdownDays} }}","styles":{"fontSize":12,"fontWeight":500,"flexShrink":0,"textAlign":"end","maxLines":1}},{"id":"kv_row_2","component":"Row","children":["label_2","value_2"],"itemMargin":8,"styles":{"width":"matchParent","alignItems":"center"}},{"id":"label_2","component":"Text","content":"天气","styles":{"fontSize":12,"fontWeight":400,"layoutWeight":1,"width":"matchParent","flexShrink":1,"maxLines":1,"textOverflow":"ellipsis"}},{"id":"value_2","component":"Row","children":["value_2_temp","value_2_cond"],"itemMargin":2,"styles":{"flexShrink":0,"alignItems":"center"}},{"id":"value_2_temp","component":"Text","content":"{{ ${/data/weather/current/temperatureText} }}","styles":{"fontSize":12,"fontWeight":500,"maxLines":1}},{"id":"value_2_cond","component":"Text","content":"{{ ${/data/weather/current/condition} }}","styles":{"fontSize":12,"fontWeight":500,"maxLines":1}},{"id":"action_area","component":"Column","children":["settings_btn"],"styles":{"width":"matchParent","flexShrink":0}},{"id":"settings_btn","component":"Button","label":"设置","onClick":[{"call":"clickToDeeplink","args":{"abilityName":"com.huawei.hmos.settings.MainAbility","bundleName":"com.huawei.hmos.settings","intentName":"Settings","uri":"battery"}}],"styles":{"width":"matchParent","height":36,"borderRadius":20,"padding":{"left":8,"top":0,"right":8,"bottom":0},"backgroundColor":"#0C000000","fontColor":"#FF0A59F7","fontSize":14,"fontWeight":500,"maxFontSize":14,"minFontSize":12,"maxLines":1,"flexShrink":0}}]}}
{"version":"v0.9","updateDataModel":{"surfaceId":"surface_card","path":"/","value":{"data":{"countdown":{"countdownDays":7},"weather":{"current":{"temperatureText":"26℃","condition":"多云"}}}}}}
```
```schema
{
  "schemaVersion": "widget-artifact-v2"
}
```
```taskspec
{
  "userQuery": "使用2*2规格，做个马拉松赛事倒计时卡片。",
  "size": "2x2",
  "eventCandidates": [
    {
      "id": "event.open.settings.battery",
      "call": "clickToDeeplink",
      "args": {
        "abilityName": "com.huawei.hmos.settings.MainAbility",
        "bundleName": "com.huawei.hmos.settings",
        "intentName": "Settings",
        "uri": "battery"
      }
    }
  ],
  "dataModelSchema": {
    "data": {
      "countdown": {
        "countdownDays": {
          "type": "integer",
          "description": "距离目标日期的自然日天数；正数表示未来，0 表示今天，负数表示已经过去。",
          "sampleValue": 7
        }
      },
      "weather": {
        "current": {
          "temperatureText": {
            "type": "string",
            "description": "适合直接显示的温度文本，例如‘29°C’。",
            "sampleValue": "26℃"
          },
          "condition": {
            "type": "string",
            "description": "当前天气现象，例如‘阴’‘多云’‘小雨’。",
            "sampleValue": "多云"
          },
          "airQuality": {
            "type": "string",
            "description": "当前空气质量等级，例如‘优’‘良’。",
            "sampleValue": "优"
          },
          "uvIndex": {
            "type": "string",
            "description": "当前紫外线等级，例如‘弱’‘中等’‘强’。",
            "sampleValue": "中等"
          }
        }
      }
    }
  },
  "assetCandidates": [
    {
      "id": "asset.figure_run",
      "src": "resources/base/media/figure_run.svg",
      "description": "跑步人物图标，黑色，图形为人体奔跑动作侧视轮廓，适用场景：运动记录、跑步锻炼追踪、步数统计"
    },
    {
      "id": "asset.stopwatch_fill",
      "src": "resources/base/media/stopwatch_fill.svg",
      "description": "秒表实心图标，黑白双色，图形为带按钮的圆形秒表造型，适用场景：计时功能、运动计时、倒计时"
    },
    {
      "id": "asset.clock_fill",
      "src": "resources/base/media/clock_fill.svg",
      "description": "时钟实心图标，黑白双色，图形为圆形实心表盘加白色指针，适用场景：时间显示、闹钟设置、定时器"
    },
    {
      "id": "asset.calendar_fill",
      "src": "resources/base/media/calendar_fill.svg",
      "description": "日历实心图标，黑色，图形为带格线的日历本造型，适用场景：日程管理、日历事件查看、当日安排"
    }
  ]
}
```
```effectivecapabilities
{
  "data": [
    "GetCountdownDays",
    "ViewWeather"
  ],
  "event": [
    {
      "id": "event.open.settings.battery",
      "call": "clickToDeeplink",
      "args": {
        "abilityName": "com.huawei.hmos.settings.MainAbility",
        "bundleName": "com.huawei.hmos.settings",
        "intentName": "Settings",
        "uri": "battery"
      }
    }
  ],
  "asset": [
    "asset.figure_run",
    "asset.stopwatch_fill",
    "asset.clock_fill",
    "asset.calendar_fill"
  ]
}
```
```removedcapabilities
[]
```
```generationplan
{
  "candidateDataBindings": [
    {
      "capabilityId": "GetCountdownDays",
      "arguments": {
        "targetDate": "2026-12-06"
      },
      "writeResultTo": "/data/countdown",
      "candidateOutputFields": [
        "/countdownDays"
      ]
    },
    {
      "capabilityId": "ViewWeather",
      "arguments": {
        "districtName": "青浦区",
        "forecastDays": 1,
        "prefectureName": "上海市"
      },
      "writeResultTo": "/data/weather",
      "candidateOutputFields": [
        "/current/temperatureText",
        "/current/condition",
        "/current/airQuality",
        "/current/uvIndex"
      ]
    }
  ],
  "candidateEventCandidates": [
    {
      "capabilityId": "event.open.settings.battery",
      "action": {
        "call": "clickToDeeplink",
        "args": {
          "abilityName": "com.huawei.hmos.settings.MainAbility",
          "bundleName": "com.huawei.hmos.settings",
          "intentName": "Settings",
          "uri": "battery"
        }
      }
    }
  ],
  "candidateAssetIds": [
    "asset.figure_run",
    "asset.stopwatch_fill",
    "asset.clock_fill",
    "asset.calendar_fill"
  ]
}
```
```meta
{
  "apiVersion": "v1",
  "taskSpecVersion": "task-spec-v1",
  "cardSpecVersion": "card-spec-v1",
  "dslProtocolVersion": "v0.9",
  "skillVersion": "skill-widget-v1",
  "protocolProfileId": "a2ui-form-rom6.0-v1",
  "capabilityRegistryVersion": "app-11.7.5.205_rom-6.0",
  "artifactSchemaVersion": "widget-artifact-v2",
  "generationMode": "create",
  "artifactId": "aa4b2799-cf58-48e1-977f-da5c8cd8b138",
  "createdAt": 1785721419767
}
```
```designcompactdsl
["root","Column",{"width":160,"height":160,"linearGradient":{"angle":145,"colors":[["#FFFFFFFF",0.0],["#FFF0F5FF",0.44],["#FF8EB3FF",1.0]]},"borderRadius":20,"padding":12,"clip":true,"itemMargin":8},["title_area","content_area","action_area"]]
["title_area","Row",{"width":"matchParent","alignItems":"start","itemMargin":4},["title_col","title_icon"]]
["title_col","Column",{"width":"matchParent","layoutWeight":1,"flexShrink":1,"itemMargin":4},["title_main","title_sub"]]
["title_main","Text",{"content":"马拉松倒计时","fontSize":12,"fontWeight":700,"width":"matchParent","maxLines":1,"textOverflow":"ellipsis"}]
["title_sub","Text",{"content":"今日开跑","fontSize":12,"fontWeight":400,"width":"matchParent","maxLines":1,"textOverflow":"ellipsis"}]
["title_icon","Image",{"src":"resources/base/media/stopwatch_fill.svg","width":20,"height":20,"borderRadius":4,"clip":true,"flexShrink":0}]
["content_area","Column",{"width":"matchParent","layoutWeight":1,"justifyContent":"end","itemMargin":8},["kv_row_1","kv_row_2"]]
["kv_row_1","Row",{"width":"matchParent","alignItems":"center","itemMargin":8},["label_1","value_1"]]
["label_1","Text",{"content":"距离","design":"body-s","layoutWeight":1,"width":"matchParent","flexShrink":1,"maxLines":1,"textOverflow":"ellipsis"}]
["value_1","Text",{"content":{"path":"/data/countdown/countdownDays"},"fontSize":12,"fontWeight":500,"flexShrink":0,"textAlign":"end","maxLines":1}]
["/data/countdown/countdownDays",7]
["kv_row_2","Row",{"width":"matchParent","alignItems":"center","itemMargin":8},["label_2","value_2"]]
["label_2","Text",{"content":"天气","design":"body-s","layoutWeight":1,"width":"matchParent","flexShrink":1,"maxLines":1,"textOverflow":"ellipsis"}]
["value_2","Row",{"flexShrink":0,"alignItems":"center","itemMargin":2},["value_2_temp","value_2_cond"]]
["value_2_temp","Text",{"content":{"path":"/data/weather/current/temperatureText"},"fontSize":12,"fontWeight":500,"maxLines":1}]
["/data/weather/current/temperatureText","26℃"]
["value_2_cond","Text",{"content":{"path":"/data/weather/current/condition"},"fontSize":12,"fontWeight":500,"maxLines":1}]
["/data/weather/current/condition","多云"]
["action_area","Column",{"width":"matchParent","flexShrink":0},["settings_btn"]]
["settings_btn","Button",{"label":"设置","design":"capsule","onClick":[{"call":"clickToDeeplink","args":{"abilityName":"com.huawei.hmos.settings.MainAbility","bundleName":"com.huawei.hmos.settings","intentName":"Settings","uri":"battery"}}]}]
```
