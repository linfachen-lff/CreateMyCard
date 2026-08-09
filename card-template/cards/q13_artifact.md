```cardspec
{
  "title": "抖音时长监控",
  "description": "抖音应用使用时长监控卡片，2*2规格，顶部显示抖音应用名称和沙漏图标，中间大字展示今日使用总时长，底部显示数据更新时间，点击卡片可跳转到系统健康使用手机设置页，整体科技感监控风格",
  "suggestSize": "2x2",
  "dataBindings": [
    {
      "capabilityId": "GetAppUsageDuration",
      "arguments": {
        "appBundleName": "com.ss.hm.ugc.aweme"
      },
      "writeResultTo": "/data/appUsageStats"
    }
  ]
}
```
```genui
{"version":"v0.9","createSurface":{"surfaceId":"surface_card","catalogId":"ohos.a2ui.extended.catalog.form","width":140,"height":140}}
{"version":"v0.9","updateComponents":{"surfaceId":"surface_card","root":"root","components":[{"id":"root","component":"Column","children":["title_area","content_area","action_area"],"itemMargin":8,"styles":{"width":"matchParent","height":"matchParent","linearGradient":{"angle":145,"colors":[["#FFFFFFFF",0.0],["#FFF0F5FF",0.44],["#FF8EB3FF",1.0]]},"borderRadius":20,"padding":12,"clip":true}},{"id":"title_area","component":"Row","children":["title_col","icon"],"itemMargin":4,"styles":{"width":"matchParent","alignItems":"start"}},{"id":"title_col","component":"Column","children":["title_main","title_sub"],"itemMargin":4,"styles":{"width":"matchParent","layoutWeight":1,"flexShrink":1}},{"id":"title_main","component":"Text","content":"应用时长","styles":{"fontSize":12,"fontWeight":700,"width":"matchParent","maxLines":1,"textOverflow":"ellipsis"}},{"id":"title_sub","component":"Text","content":"今日使用","styles":{"fontSize":12,"fontWeight":400,"width":"matchParent","maxLines":1,"textOverflow":"ellipsis"}},{"id":"icon","component":"Image","src":"resources/base/media/hourglass_fill.svg","styles":{"width":20,"height":20,"borderRadius":4,"clip":true,"flexShrink":0}},{"id":"content_area","component":"Column","children":["kv_row_1"],"itemMargin":8,"styles":{"width":"matchParent","layoutWeight":1,"justifyContent":"end"}},{"id":"kv_row_1","component":"Row","children":["label_1","value_1"],"itemMargin":8,"styles":{"width":"matchParent","alignItems":"center"}},{"id":"label_1","component":"Text","content":"抖音","styles":{"fontSize":12,"fontWeight":400,"layoutWeight":1,"width":"matchParent","flexShrink":1,"maxLines":1,"textOverflow":"ellipsis"}},{"id":"value_1","component":"Text","content":"{{ ${/data/appUsageStats/appUsage/durationText} }}","styles":{"fontSize":12,"fontWeight":500,"flexShrink":0,"textAlign":"end","maxLines":1}},{"id":"action_area","component":"Column","children":["btn"],"styles":{"width":"matchParent","flexShrink":0}},{"id":"btn","component":"Button","label":"家长控制","onClick":[{"call":"clickToDeeplink","args":{"abilityName":"com.huawei.hmos.settings.MainAbility","bundleName":"com.huawei.hmos.settings","intentName":"Settings","uri":"parent_control"}}],"styles":{"width":"matchParent","height":36,"borderRadius":20,"padding":{"left":8,"top":0,"right":8,"bottom":0},"backgroundColor":"#0C000000","fontColor":"#FF0A59F7","fontSize":14,"fontWeight":500,"maxFontSize":14,"minFontSize":12,"maxLines":1,"flexShrink":0}}]}}
{"version":"v0.9","updateDataModel":{"surfaceId":"surface_card","path":"/","value":{"data":{"appUsageStats":{"appUsage":{"durationText":"25 分钟"}}}}}}
```
```schema
{
  "schemaVersion": "widget-artifact-v2"
}
```
```taskspec
{
  "userQuery": "使用2*2规格，做个抖音app的应用使用时长监控卡片。",
  "size": "2x2",
  "eventCandidates": [
    {
      "id": "event.open.settings.parentControl",
      "call": "clickToDeeplink",
      "args": {
        "abilityName": "com.huawei.hmos.settings.MainAbility",
        "bundleName": "com.huawei.hmos.settings",
        "intentName": "Settings",
        "uri": "parent_control"
      }
    }
  ],
  "dataModelSchema": {
    "data": {
      "appUsageStats": {
        "appUsage": {
          "appName": {
            "type": "string",
            "description": "应用名称文本，例如：“抖音”",
            "sampleValue": "示例应用"
          },
          "durationText": {
            "type": "string",
            "description": "应用今日运行总时间文本（自带单位），例如：“25 秒”或“1 分钟 21 秒”。",
            "sampleValue": "25 分钟"
          }
        },
        "updatedAt": {
          "type": "string",
          "description": "端侧完成数据查询和归一化的时间，格式如：2026-07-14 10:16。",
          "sampleValue": "2026-07-15 11:30"
        }
      }
    }
  },
  "assetCandidates": [
    {
      "id": "asset.hourglass_fill",
      "src": "resources/base/media/hourglass_fill.svg",
      "description": "沙漏和齿轮组合图标，图形为沙漏线性右下角齿轮组合的造型，适用场景：应用时长"
    },
    {
      "id": "asset.clock_fill",
      "src": "resources/base/media/clock_fill.svg",
      "description": "时钟实心图标，黑白双色，图形为圆形实心表盘加白色指针，适用场景：时间显示、闹钟设置、定时器"
    },
    {
      "id": "asset.bell_fill",
      "src": "resources/base/media/bell_fill.svg",
      "description": "铃铛实心图标，黑色，图形为经典吊铃造型，适用场景：通知提醒、消息提示、闹铃开启状态"
    }
  ]
}
```
```effectivecapabilities
{
  "data": [
    "GetAppUsageDuration"
  ],
  "event": [
    {
      "id": "event.open.settings.parentControl",
      "call": "clickToDeeplink",
      "args": {
        "abilityName": "com.huawei.hmos.settings.MainAbility",
        "bundleName": "com.huawei.hmos.settings",
        "intentName": "Settings",
        "uri": "parent_control"
      }
    }
  ],
  "asset": [
    "asset.hourglass_fill",
    "asset.clock_fill",
    "asset.bell_fill"
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
      "capabilityId": "GetAppUsageDuration",
      "arguments": {
        "appBundleName": "com.ss.hm.ugc.aweme"
      },
      "writeResultTo": "/data/appUsageStats",
      "candidateOutputFields": [
        "/appUsage/appName",
        "/appUsage/durationText",
        "/updatedAt"
      ]
    }
  ],
  "candidateEventCandidates": [
    {
      "capabilityId": "event.open.settings.parentControl",
      "action": {
        "call": "clickToDeeplink",
        "args": {
          "abilityName": "com.huawei.hmos.settings.MainAbility",
          "bundleName": "com.huawei.hmos.settings",
          "intentName": "Settings",
          "uri": "parent_control"
        }
      }
    }
  ],
  "candidateAssetIds": [
    "asset.hourglass_fill",
    "asset.clock_fill",
    "asset.bell_fill"
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
  "artifactId": "6a65e5cc-b46e-4f49-a95e-b5eb5e96166f",
  "createdAt": 1785721464879
}
```
```designcompactdsl
["root","Column",{"width":160,"height":160,"linearGradient":{"angle":145,"colors":[["#FFFFFFFF",0.0],["#FFF0F5FF",0.44],["#FF8EB3FF",1.0]]},"borderRadius":20,"padding":12,"clip":true,"itemMargin":8},["title_area","content_area","action_area"]]
["title_area","Row",{"width":"matchParent","alignItems":"start","itemMargin":4},["title_col","icon"]]
["title_col","Column",{"width":"matchParent","layoutWeight":1,"flexShrink":1,"itemMargin":4},["title_main","title_sub"]]
["title_main","Text",{"content":"应用时长","fontSize":12,"fontWeight":700,"width":"matchParent","maxLines":1,"textOverflow":"ellipsis"}]
["title_sub","Text",{"content":"今日使用","fontSize":12,"fontWeight":400,"width":"matchParent","maxLines":1,"textOverflow":"ellipsis"}]
["icon","Image",{"src":"resources/base/media/hourglass_fill.svg","width":20,"height":20,"borderRadius":4,"clip":true,"flexShrink":0}]
["content_area","Column",{"width":"matchParent","layoutWeight":1,"justifyContent":"end","itemMargin":8},["kv_row_1"]]
["kv_row_1","Row",{"width":"matchParent","alignItems":"center","itemMargin":8},["label_1","value_1"]]
["label_1","Text",{"content":"抖音","design":"body-s","layoutWeight":1,"width":"matchParent","flexShrink":1,"maxLines":1,"textOverflow":"ellipsis"}]
["value_1","Text",{"content":{"path":"/data/appUsageStats/appUsage/durationText"},"fontSize":12,"fontWeight":500,"flexShrink":0,"textAlign":"end","maxLines":1}]
["action_area","Column",{"width":"matchParent","flexShrink":0},["btn"]]
["btn","Button",{"label":"家长控制","design":"capsule","onClick":[{"call":"clickToDeeplink","args":{"abilityName":"com.huawei.hmos.settings.MainAbility","bundleName":"com.huawei.hmos.settings","intentName":"Settings","uri":"parent_control"}}]}]
["/data/appUsageStats/appUsage/durationText","25 分钟"]
```
