```cardspec
{
  "title": "睡眠监督",
  "description": "睡眠监督卡片，科技感圆环展示睡眠得分占目标8小时百分比，圆环旁显示具体睡眠时长，睡眠不足7小时顶部标题变红提醒，底部一键打开闹钟设置",
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
{"version":"v0.9","updateComponents":{"surfaceId":"surface_card","root":"root","components":[{"id":"root","component":"Column","children":["title_area","content_area","action_area"],"itemMargin":8,"styles":{"width":"matchParent","height":"matchParent","linearGradient":{"angle":145,"colors":[["#FFFFFFFF",0.0],["#FFF0F5FF",0.44],["#FF8EB3FF",1.0]]},"borderRadius":20,"padding":12,"clip":true}},{"id":"title_area","component":"Row","children":["title_col","title_icon"],"itemMargin":4,"styles":{"width":"matchParent","alignItems":"start"}},{"id":"title_col","component":"Column","children":["title_main","title_sub"],"itemMargin":4,"styles":{"width":"matchParent","layoutWeight":1,"flexShrink":1}},{"id":"title_main","component":"Text","content":"睡眠监督","styles":{"fontSize":12,"fontWeight":700,"width":"matchParent","maxLines":1,"textOverflow":"ellipsis"}},{"id":"title_sub","component":"Text","content":"良好","styles":{"fontSize":12,"fontWeight":400,"width":"matchParent","maxLines":1,"textOverflow":"ellipsis"}},{"id":"title_icon","component":"Image","src":"resources/base/media/icon_sleep.svg","styles":{"width":20,"height":20,"borderRadius":4,"clip":true,"flexShrink":0}},{"id":"content_area","component":"Column","children":["kv_row_1","kv_row_2"],"itemMargin":8,"styles":{"width":"matchParent","layoutWeight":1,"justifyContent":"start"}},{"id":"kv_row_1","component":"Row","children":["label_1","value_1"],"itemMargin":8,"styles":{"width":"matchParent","alignItems":"center"}},{"id":"label_1","component":"Text","content":"深睡","styles":{"fontSize":12,"fontWeight":400,"layoutWeight":1,"width":"matchParent","flexShrink":1,"maxLines":1,"textOverflow":"ellipsis"}},{"id":"value_1","component":"Text","content":"{{ ${/data/healthSport/deepSleepDurationText} }}","styles":{"fontSize":12,"fontWeight":500,"flexShrink":0,"textAlign":"end","maxLines":1}},{"id":"kv_row_2","component":"Row","children":["label_2","value_2"],"itemMargin":8,"styles":{"width":"matchParent","alignItems":"center"}},{"id":"label_2","component":"Text","content":"入睡","styles":{"fontSize":12,"fontWeight":400,"layoutWeight":1,"width":"matchParent","flexShrink":1,"maxLines":1,"textOverflow":"ellipsis"}},{"id":"value_2","component":"Text","content":"{{ ${/data/healthSport/fallAsleepTimeText} }}","styles":{"fontSize":12,"fontWeight":500,"flexShrink":0,"textAlign":"end","maxLines":1}},{"id":"action_area","component":"Column","children":["alarm_btn"],"styles":{"width":"matchParent","flexShrink":0}},{"id":"alarm_btn","component":"Button","label":"设置闹钟","onClick":[{"call":"clickToDeeplink","args":{"abilityName":"com.huawei.hmos.clock.phone","bundleName":"com.huawei.hmos.clock","intentName":"Clock","uri":""}}],"styles":{"width":"matchParent","height":36,"borderRadius":20,"padding":{"left":8,"top":0,"right":8,"bottom":0},"backgroundColor":"#0C000000","fontColor":"#FF0A59F7","fontSize":14,"fontWeight":500,"maxFontSize":14,"minFontSize":12,"maxLines":1,"flexShrink":0}}]}}
{"version":"v0.9","updateDataModel":{"surfaceId":"surface_card","path":"/","value":{"data":{"healthSport":{"deepSleepDurationText":"2小时15分","fallAsleepTimeText":"23:15"}}}}}
```
```schema
{
  "schemaVersion": "widget-artifact-v2"
}
```
```taskspec
{
  "userQuery": "使用2*2规格，创建睡眠监督小组件",
  "size": "2x2",
  "eventCandidates": [
    {
      "id": "event.open.clock.alarm",
      "call": "clickToDeeplink",
      "args": {
        "abilityName": "com.huawei.hmos.clock.phone",
        "bundleName": "com.huawei.hmos.clock",
        "intentName": "Clock",
        "uri": ""
      }
    },
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
        "deepSleepDurationText": {
          "type": "string",
          "description": "夜间正式睡眠中的深睡总时长文本，例如‘2小时15分’。",
          "sampleValue": "2小时15分"
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
        },
        "sleepTypeDesc": {
          "type": "string",
          "description": "睡眠记录方式或类型的描述，例如‘科学睡眠’、‘普通睡眠’、‘手动输入睡眠’、‘手机记录睡眠’。",
          "sampleValue": "科学睡眠"
        }
      }
    }
  },
  "assetCandidates": [
    {
      "id": "asset.icon_sleep",
      "src": "resources/base/media/icon_sleep.svg",
      "description": "睡眠图标，适用场景：睡眠监督"
    },
    {
      "id": "asset.icon_alarm_clock1",
      "src": "resources/base/media/icon_alarm_clock1.svg",
      "description": "闹钟图标，适用场景：睡眠监督"
    },
    {
      "id": "asset.icon_remind",
      "src": "resources/base/media/icon_remind.svg",
      "description": "提醒图标，适用场景：睡眠监督"
    },
    {
      "id": "asset.moon_circle_fill",
      "src": "resources/base/media/moon_circle_fill.svg",
      "description": "月亮圆形实心图标，黑白双色，图形为圆形背景内白色月牙，适用场景：夜间模式、睡眠追踪、勿扰模式"
    },
    {
      "id": "asset.z_alarm_fill",
      "src": "resources/base/media/z_alarm_fill.svg",
      "description": "带Z的闹钟贪睡实心图标，黑色，图形为闹钟旁附带字母Z表示贪睡，适用场景：闹钟贪睡功能、延迟提醒、睡眠场景"
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
      "id": "event.open.clock.alarm",
      "call": "clickToDeeplink",
      "args": {
        "abilityName": "com.huawei.hmos.clock.phone",
        "bundleName": "com.huawei.hmos.clock",
        "intentName": "Clock",
        "uri": ""
      }
    },
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
    "asset.icon_sleep",
    "asset.icon_alarm_clock1",
    "asset.icon_remind",
    "asset.moon_circle_fill",
    "asset.z_alarm_fill"
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
        "/deepSleepDurationText",
        "/fallAsleepTimeText",
        "/wakeupTimeText",
        "/sleepTypeDesc"
      ]
    }
  ],
  "candidateEventCandidates": [
    {
      "capabilityId": "event.open.clock.alarm",
      "action": {
        "call": "clickToDeeplink",
        "args": {
          "abilityName": "com.huawei.hmos.clock.phone",
          "bundleName": "com.huawei.hmos.clock",
          "intentName": "Clock",
          "uri": ""
        }
      }
    },
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
    "asset.icon_sleep",
    "asset.icon_alarm_clock1",
    "asset.icon_remind",
    "asset.moon_circle_fill",
    "asset.z_alarm_fill"
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
  "artifactId": "f779c262-6ff6-41a1-8852-e891daf252fb",
  "createdAt": 1785721378451
}
```
```designcompactdsl
["root","Column",{"width":160,"height":160,"linearGradient":{"angle":145,"colors":[["#FFFFFFFF",0.0],["#FFF0F5FF",0.44],["#FF8EB3FF",1.0]]},"borderRadius":20,"padding":12,"clip":true,"itemMargin":8},["title_area","content_area","action_area"]]
["title_area","Row",{"width":"matchParent","alignItems":"start","itemMargin":4},["title_col","title_icon"]]
["title_col","Column",{"width":"matchParent","layoutWeight":1,"flexShrink":1,"itemMargin":4},["title_main","title_sub"]]
["title_main","Text",{"content":"睡眠监督","fontSize":12,"fontWeight":700,"width":"matchParent","maxLines":1,"textOverflow":"ellipsis"}]
["title_sub","Text",{"content":"良好","fontSize":12,"fontWeight":400,"width":"matchParent","maxLines":1,"textOverflow":"ellipsis"}]
["title_icon","Image",{"src":"resources/base/media/icon_sleep.svg","width":20,"height":20,"borderRadius":4,"clip":true,"flexShrink":0}]
["content_area","Column",{"width":"matchParent","layoutWeight":1,"justifyContent":"start","itemMargin":8},["kv_row_1","kv_row_2"]]
["kv_row_1","Row",{"width":"matchParent","alignItems":"center","itemMargin":8},["label_1","value_1"]]
["label_1","Text",{"content":"深睡","design":"body-s","layoutWeight":1,"width":"matchParent","flexShrink":1,"maxLines":1,"textOverflow":"ellipsis"}]
["value_1","Text",{"content":{"path":"/data/healthSport/deepSleepDurationText"},"fontSize":12,"fontWeight":500,"flexShrink":0,"textAlign":"end","maxLines":1}]
["kv_row_2","Row",{"width":"matchParent","alignItems":"center","itemMargin":8},["label_2","value_2"]]
["label_2","Text",{"content":"入睡","design":"body-s","layoutWeight":1,"width":"matchParent","flexShrink":1,"maxLines":1,"textOverflow":"ellipsis"}]
["value_2","Text",{"content":{"path":"/data/healthSport/fallAsleepTimeText"},"fontSize":12,"fontWeight":500,"flexShrink":0,"textAlign":"end","maxLines":1}]
["action_area","Column",{"width":"matchParent","flexShrink":0},["alarm_btn"]]
["alarm_btn","Button",{"label":"设置闹钟","design":"capsule","fontColor":"#FF0A59F7","onClick":[{"call":"clickToDeeplink","args":{"abilityName":"com.huawei.hmos.clock.phone","bundleName":"com.huawei.hmos.clock","intentName":"Clock","uri":""}}]},["alarm_icon"]]
["alarm_icon","Image",{"src":"resources/base/media/icon_alarm_clock1.svg","width":24,"height":24,"flexShrink":0,"fillColor":"#FF0A59F7"}]
["/data/healthSport/deepSleepDurationText","2小时15分"]
["/data/healthSport/fallAsleepTimeText","23:15"]
```
