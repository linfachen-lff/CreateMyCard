```cardspec
{
  "title": "睡眠卡片",
  "description": "睡眠数据速览",
  "suggestSize": "2x2",
  "dataBindings": [
    {
      "capabilityId": "GetHealthAndSportSummary",
      "arguments": {
        "targetDayOffset": 0
      },
      "writeResultTo": "/data/healthSport"
    }
  ]
}
```
```genui
{"version":"v0.9","createSurface":{"surfaceId":"surface_card","catalogId":"ohos.a2ui.extended.catalog.form","width":140,"height":140}}
{"version":"v0.9","updateComponents":{"surfaceId":"surface_card","root":"root","components":[{"id":"root","component":"Column","children":["title_area","content_area","action_area"],"itemMargin":8,"styles":{"width":"matchParent","height":"matchParent","linearGradient":{"angle":145,"colors":[["#FFFFFFFF",0.0],["#FFF0F5FF",0.44],["#FF8EB3FF",1.0]]},"borderRadius":20,"padding":12,"clip":true}},{"id":"title_area","component":"Row","children":["title_col","title_icon"],"itemMargin":4,"styles":{"width":"matchParent","alignItems":"start"}},{"id":"title_col","component":"Column","children":["title_main","title_sub"],"itemMargin":4,"styles":{"width":"matchParent","layoutWeight":1,"flexShrink":1}},{"id":"title_main","component":"Text","content":"睡眠","styles":{"fontSize":12,"fontWeight":700,"width":"matchParent","maxLines":1,"textOverflow":"ellipsis"}},{"id":"title_sub","component":"Text","content":"昨晚","styles":{"fontSize":12,"fontWeight":400,"width":"matchParent","maxLines":1,"textOverflow":"ellipsis"}},{"id":"title_icon","component":"Image","src":"resources/base/media/moon_z_fill_1.svg","styles":{"width":20,"height":20,"borderRadius":4,"clip":true,"flexShrink":0}},{"id":"content_area","component":"Column","children":["score_row","detail_row"],"itemMargin":8,"styles":{"width":"matchParent","layoutWeight":1,"justifyContent":"start"}},{"id":"score_row","component":"Row","children":["score_label","score_value"],"itemMargin":8,"styles":{"width":"matchParent","alignItems":"center"}},{"id":"score_label","component":"Text","content":"评分","styles":{"fontSize":12,"fontWeight":400,"layoutWeight":1,"width":"matchParent","flexShrink":1,"maxLines":1,"textOverflow":"ellipsis"}},{"id":"score_value","component":"Text","content":"{{ ${/data/healthSport/sleepScore} }}","styles":{"fontSize":12,"fontWeight":500,"flexShrink":0,"textAlign":"end","maxLines":1}},{"id":"detail_row","component":"Row","children":["detail_label","detail_value"],"itemMargin":8,"styles":{"width":"matchParent","alignItems":"center"}},{"id":"detail_label","component":"Text","content":"时长","styles":{"fontSize":12,"fontWeight":400,"layoutWeight":1,"width":"matchParent","flexShrink":1,"maxLines":1,"textOverflow":"ellipsis"}},{"id":"detail_value","component":"Text","content":"{{ ${/data/healthSport/nightSleepDurationText} }}","styles":{"fontSize":12,"fontWeight":500,"flexShrink":0,"textAlign":"end","maxLines":1}},{"id":"action_area","component":"Column","children":["detail_btn"],"styles":{"width":"matchParent","flexShrink":0}},{"id":"detail_btn","component":"Button","label":"查看详情","onClick":[{"call":"clickToDeeplink","args":{"abilityName":"","bundleName":"","intentName":"Health","uri":"huaweischeme://healthapp/router/sleepDetail"}}],"styles":{"width":"matchParent","height":36,"borderRadius":20,"padding":{"left":8,"top":0,"right":8,"bottom":0},"backgroundColor":"#0C000000","fontColor":"#FF0A59F7","fontSize":14,"fontWeight":500,"maxFontSize":14,"minFontSize":12,"maxLines":1,"flexShrink":0}}]}}
{"version":"v0.9","updateDataModel":{"surfaceId":"surface_card","path":"/","value":{"data":{"healthSport":{"sleepScore":86,"nightSleepDurationText":"7小时1分"}}}}}
```
```schema
{
  "schemaVersion": "widget-artifact-v2"
}
```
```taskspec
{
  "userQuery": "使用2*2规格，生成一个睡眠卡片，显示昨晚睡眠评分、睡眠状态、睡眠时长、入睡时间和起床时间，点击可跳转运动健康睡眠详情页",
  "size": "2x2",
  "eventCandidates": [
    {
      "id": "event.open.health.sleep",
      "call": "clickToDeeplink",
      "args": {
        "abilityName": "",
        "bundleName": "",
        "intentName": "Health",
        "uri": "huaweischeme://healthapp/router/sleepDetail"
      }
    }
  ],
  "dataModelSchema": {
    "data": {
      "healthSport": {
        "sleepScore": {
          "type": "integer",
          "description": "睡眠综合得分，取值范围 0-100。",
          "sampleValue": 86
        },
        "sleepStatus": {
          "type": "string",
          "description": "基于得分智能生成的睡眠状态语义判定，包括：'优秀'、'良好'、'一般'、'较差'。",
          "sampleValue": "良好"
        },
        "nightSleepDurationText": {
          "type": "string",
          "description": "夜间正式睡眠的总时长文本，例如‘7小时1分’。",
          "sampleValue": "7小时1分"
        },
        "fallAsleepTimeText": {
          "type": "string",
          "description": "格式化后的确切入睡时刻短文本（HH:mm），例如‘23:15’。",
          "sampleValue": "23:15"
        },
        "wakeupTimeText": {
          "type": "string",
          "description": "格式化后的确切醒来时刻短文本（HH:mm），例如‘07:30’。",
          "sampleValue": "07:30"
        }
      }
    }
  },
  "assetCandidates": [
    {
      "id": "asset.moon_z_fill_1",
      "src": "resources/base/media/moon_z_fill_1.svg",
      "description": "月亮加Z睡眠实心图标，黑色，图形为月牙旁附带字母Z表示入睡，适用场景：睡眠模式开启、休息提醒、晚安场景"
    },
    {
      "id": "asset.moon_circle_fill",
      "src": "resources/base/media/moon_circle_fill.svg",
      "description": "月亮圆形实心图标，黑白双色，图形为圆形背景内白色月牙，适用场景：夜间模式、睡眠追踪、勿扰模式"
    }
  ]
}
```
```effectivecapabilities
{
  "data": [
    "GetHealthAndSportSummary"
  ],
  "event": [
    {
      "id": "event.open.health.sleep",
      "call": "clickToDeeplink",
      "args": {
        "abilityName": "",
        "bundleName": "",
        "intentName": "Health",
        "uri": "huaweischeme://healthapp/router/sleepDetail"
      }
    }
  ],
  "asset": [
    "asset.moon_z_fill_1",
    "asset.moon_circle_fill"
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
      "capabilityId": "GetHealthAndSportSummary",
      "arguments": {
        "targetDayOffset": 0
      },
      "writeResultTo": "/data/healthSport",
      "candidateOutputFields": [
        "/sleepScore",
        "/sleepStatus",
        "/nightSleepDurationText",
        "/fallAsleepTimeText",
        "/wakeupTimeText"
      ]
    }
  ],
  "candidateEventCandidates": [
    {
      "capabilityId": "event.open.health.sleep",
      "action": {
        "call": "clickToDeeplink",
        "args": {
          "abilityName": "",
          "bundleName": "",
          "intentName": "Health",
          "uri": "huaweischeme://healthapp/router/sleepDetail"
        }
      }
    }
  ],
  "candidateAssetIds": [
    "asset.moon_z_fill_1",
    "asset.moon_circle_fill"
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
  "artifactId": "86aa899b-1831-4cf1-8237-dae2878eac7e",
  "createdAt": 1785721055237
}
```
```designcompactdsl
["root","Column",{"width":160,"height":160,"linearGradient":{"angle":145,"colors":[["#FFFFFFFF",0.0],["#FFF0F5FF",0.44],["#FF8EB3FF",1.0]]},"borderRadius":20,"padding":12,"clip":true,"itemMargin":8},["title_area","content_area","action_area"]]
["title_area","Row",{"width":"matchParent","alignItems":"start","itemMargin":4},["title_col","title_icon"]]
["title_col","Column",{"width":"matchParent","layoutWeight":1,"flexShrink":1,"itemMargin":4},["title_main","title_sub"]]
["title_main","Text",{"content":"睡眠","fontSize":12,"fontWeight":700,"width":"matchParent","maxLines":1,"textOverflow":"ellipsis"}]
["title_sub","Text",{"content":"昨晚","fontSize":12,"fontWeight":400,"width":"matchParent","maxLines":1,"textOverflow":"ellipsis"}]
["title_icon","Image",{"src":"resources/base/media/moon_z_fill_1.svg","width":20,"height":20,"borderRadius":4,"clip":true,"flexShrink":0}]
["content_area","Column",{"width":"matchParent","layoutWeight":1,"justifyContent":"start","itemMargin":8},["score_row","detail_row"]]
["score_row","Row",{"width":"matchParent","alignItems":"center","itemMargin":8},["score_label","score_value"]]
["score_label","Text",{"content":"评分","design":"body-s","layoutWeight":1,"width":"matchParent","flexShrink":1,"maxLines":1,"textOverflow":"ellipsis"}]
["score_value","Text",{"content":{"path":"/data/healthSport/sleepScore"},"fontSize":12,"fontWeight":500,"flexShrink":0,"textAlign":"end","maxLines":1}]
["detail_row","Row",{"width":"matchParent","alignItems":"center","itemMargin":8},["detail_label","detail_value"]]
["detail_label","Text",{"content":"时长","design":"body-s","layoutWeight":1,"width":"matchParent","flexShrink":1,"maxLines":1,"textOverflow":"ellipsis"}]
["detail_value","Text",{"content":{"path":"/data/healthSport/nightSleepDurationText"},"fontSize":12,"fontWeight":500,"flexShrink":0,"textAlign":"end","maxLines":1}]
["action_area","Column",{"width":"matchParent","flexShrink":0},["detail_btn"]]
["detail_btn","Button",{"label":"查看详情","design":"capsule","fontColor":"#FF0A59F7","onClick":[{"call":"clickToDeeplink","args":{"abilityName":"","bundleName":"","intentName":"Health","uri":"huaweischeme://healthapp/router/sleepDetail"}}]},["detail_icon"]]
["detail_icon","Image",{"src":"resources/base/media/moon_circle_fill.svg","width":24,"height":24,"flexShrink":0,"fillColor":"#FF0A59F7"}]
["/data/healthSport/sleepScore",86]
["/data/healthSport/nightSleepDurationText","7小时1分"]
```
