```cardspec
{
  "title": "运动会倒数日",
  "description": "运动会倒计时天数",
  "suggestSize": "2x2",
  "dataBindings": [
    {
      "capabilityId": "GetCountdownDays",
      "arguments": {
        "targetDate": "2026-09-15"
      },
      "writeResultTo": "/data/countdown"
    }
  ]
}
```
```genui
{"version":"v0.9","createSurface":{"surfaceId":"surface_card","catalogId":"ohos.a2ui.extended.catalog.form","width":140,"height":140}}
{"version":"v0.9","updateComponents":{"surfaceId":"surface_card","root":"root","components":[{"id":"root","component":"Column","children":["title_area","content_area"],"itemMargin":8,"styles":{"width":"matchParent","height":"matchParent","linearGradient":{"angle":145,"colors":[["#FFFFFFFF",0.0],["#FFF0F5FF",0.44],["#FF8EB3FF",1.0]]},"borderRadius":20,"padding":12,"clip":true}},{"id":"title_area","component":"Row","children":["title_col","icon"],"itemMargin":4,"styles":{"width":"matchParent","alignItems":"start"}},{"id":"title_col","component":"Column","children":["title_main"],"styles":{"width":"matchParent","layoutWeight":1,"flexShrink":1}},{"id":"title_main","component":"Text","content":"运动会","styles":{"fontSize":12,"fontWeight":400,"width":"matchParent","maxLines":1,"textOverflow":"ellipsis"}},{"id":"icon","component":"Image","src":"resources/base/media/stopwatch_fill.svg","styles":{"width":20,"height":20,"borderRadius":4,"clip":true,"flexShrink":0}},{"id":"content_area","component":"Column","children":["ringUnit"],"itemMargin":4,"styles":{"width":"matchParent","layoutWeight":1,"justifyContent":"end","alignItems":"center"}},{"id":"ringUnit","component":"Column","children":["ring","readingBelow"],"itemMargin":4,"styles":{"alignItems":"center","flexShrink":0}},{"id":"ring","component":"Stack","children":["ringBar","centerIcon"],"styles":{"width":44,"height":44,"alignContent":"center","flexShrink":0}},{"id":"ringBar","component":"Progress","value":"{{ ${/data/countdown/countdownDays} }}","total":30,"styles":{"type":"ring","strokeWidth":6}},{"id":"centerIcon","component":"Image","src":"resources/base/media/figure_run.svg","styles":{"width":20,"height":20,"flexShrink":0}},{"id":"readingBelow","component":"Row","children":["num","unit"],"styles":{"alignItems":"center","flexShrink":0}},{"id":"num","component":"Text","content":"{{ ${/data/countdown/countdownDays} }}","styles":{"fontSize":12,"fontWeight":700,"maxLines":1,"flexShrink":0}},{"id":"unit","component":"Text","content":"天","styles":{"fontSize":12,"fontWeight":700,"maxLines":1,"flexShrink":0}}]}}
{"version":"v0.9","updateDataModel":{"surfaceId":"surface_card","path":"/","value":{"data":{"countdown":{"countdownDays":7}}}}}
```
```schema
{
  "schemaVersion": "widget-artifact-v2"
}
```
```taskspec
{
  "userQuery": "使用2*2规格，做个运动会倒数日卡片。展示距离运动会的倒计时天数，风格活力运动感，配色明亮。",
  "size": "2x2",
  "eventCandidates": [],
  "dataModelSchema": {
    "data": {
      "countdown": {
        "countdownDays": {
          "type": "integer",
          "description": "距离目标日期的自然日天数；正数表示未来，0 表示今天，负数表示已经过去。",
          "sampleValue": 7
        }
      }
    }
  },
  "assetCandidates": [
    {
      "id": "asset.calendar_fill",
      "src": "resources/base/media/calendar_fill.svg",
      "description": "日历实心图标，黑色，图形为带格线的日历本造型，适用场景：日程管理、日历事件查看、当日安排"
    },
    {
      "id": "asset.stopwatch_fill",
      "src": "resources/base/media/stopwatch_fill.svg",
      "description": "秒表实心图标，黑白双色，图形为带按钮的圆形秒表造型，适用场景：计时功能、运动计时、倒计时"
    },
    {
      "id": "asset.figure_run",
      "src": "resources/base/media/figure_run.svg",
      "description": "跑步人物图标，黑色，图形为人体奔跑动作侧视轮廓，适用场景：运动记录、跑步锻炼追踪、步数统计"
    }
  ]
}
```
```effectivecapabilities
{
  "data": [
    "GetCountdownDays"
  ],
  "event": [],
  "asset": [
    "asset.calendar_fill",
    "asset.stopwatch_fill",
    "asset.figure_run"
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
        "targetDate": "2026-09-15"
      },
      "writeResultTo": "/data/countdown",
      "candidateOutputFields": [
        "/countdownDays"
      ]
    }
  ],
  "candidateEventCandidates": [],
  "candidateAssetIds": [
    "asset.calendar_fill",
    "asset.stopwatch_fill",
    "asset.figure_run"
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
  "artifactId": "5afa93ad-468c-41c3-a435-13e8d19c5a62",
  "createdAt": 1785721647663
}
```
```designcompactdsl
["root","Column",{"width":160,"height":160,"linearGradient":{"angle":145,"colors":[["#FFFFFFFF",0.0],["#FFF0F5FF",0.44],["#FF8EB3FF",1.0]]},"borderRadius":20,"padding":12,"clip":true,"itemMargin":8},["title_area","content_area"]]
["title_area","Row",{"width":"matchParent","alignItems":"start","itemMargin":4},["title_col","icon"]]
["title_col","Column",{"width":"matchParent","layoutWeight":1,"flexShrink":1},["title_main"]]
["title_main","Text",{"content":"运动会","fontSize":12,"fontWeight":400,"width":"matchParent","maxLines":1,"textOverflow":"ellipsis"}]
["icon","Image",{"src":"resources/base/media/stopwatch_fill.svg","width":20,"height":20,"borderRadius":4,"clip":true,"flexShrink":0}]
["content_area","Column",{"width":"matchParent","layoutWeight":1,"justifyContent":"end","alignItems":"center","itemMargin":4},["ringUnit"]]
["ringUnit","Column",{"itemMargin":4,"alignItems":"center","flexShrink":0},["ring","readingBelow"]]
["ring","Stack",{"width":44,"height":44,"alignContent":"center","flexShrink":0},["ringBar","centerIcon"]]
["ringBar","Progress",{"type":"ring","value":{"path":"/data/countdown/countdownDays"},"total":30,"strokeWidth":6}]
["centerIcon","Image",{"src":"resources/base/media/figure_run.svg","width":20,"height":20,"flexShrink":0}]
["readingBelow","Row",{"alignItems":"center","flexShrink":0},["num","unit"]]
["num","Text",{"content":{"path":"/data/countdown/countdownDays"},"fontSize":12,"fontWeight":700,"maxLines":1,"flexShrink":0}]
["unit","Text",{"content":"天","fontSize":12,"fontWeight":700,"maxLines":1,"flexShrink":0}]
["/data/countdown/countdownDays",7]
```
