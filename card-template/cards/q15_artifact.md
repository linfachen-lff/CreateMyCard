```cardspec
{
  "title": "抖音防沉迷",
  "description": "抖音防沉迷监控",
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
{"version":"v0.9","updateComponents":{"surfaceId":"surface_card","root":"root","components":[{"id":"root","component":"Column","children":["title_area","content_area","action_area"],"itemMargin":8,"styles":{"width":"matchParent","height":"matchParent","linearGradient":{"angle":145,"colors":[["#FFFFFFFF",0.0],["#FFF0F5FF",0.44],["#FF8EB3FF",1.0]]},"borderRadius":20,"padding":12,"clip":true}},{"id":"title_area","component":"Row","children":["title_col","icon"],"itemMargin":4,"styles":{"width":"matchParent","alignItems":"start"}},{"id":"title_col","component":"Column","children":["title_main","title_sub"],"itemMargin":4,"styles":{"width":"matchParent","layoutWeight":1,"flexShrink":1}},{"id":"title_main","component":"Text","content":"应用时长","styles":{"fontSize":12,"fontWeight":700,"width":"matchParent","maxLines":1,"textOverflow":"ellipsis"}},{"id":"title_sub","component":"Text","content":"今日使用","styles":{"fontSize":12,"fontWeight":400,"width":"matchParent","maxLines":1,"textOverflow":"ellipsis"}},{"id":"icon","component":"Image","src":"resources/base/media/hourglass_fill.svg","styles":{"width":20,"height":20,"borderRadius":4,"clip":true,"flexShrink":0,"fillColor":"#E5000000"}},{"id":"content_area","component":"Column","children":["progress_row","stats_row"],"itemMargin":4,"styles":{"width":"matchParent","layoutWeight":1,"justifyContent":"start"}},{"id":"progress_row","component":"Row","children":["progress_bar","progress_label"],"itemMargin":8,"styles":{"width":"matchParent","alignItems":"center"}},{"id":"progress_bar","component":"Progress","value":"{{ ${/data/appUsageStats/appUsage/durationText} }}","total":100,"styles":{"type":"linear","width":"matchParent","height":8,"borderRadius":4,"backgroundColor":"#19000000","color":"#FFED6F21"}},{"id":"progress_label","component":"Text","content":"超出","styles":{"fontSize":10,"fontWeight":500,"flexShrink":0,"fontColor":"#FFE84026"}},{"id":"stats_row","component":"Row","children":["total_col","over_col"],"itemMargin":8,"styles":{"width":"matchParent","justifyContent":"spaceBetween"}},{"id":"total_col","component":"Column","children":["total_label","total_value"],"itemMargin":2,"styles":{"width":"matchParent","layoutWeight":1,"flexShrink":1}},{"id":"total_label","component":"Text","content":"总时长","styles":{"fontSize":10,"fontWeight":400,"maxLines":1,"textOverflow":"ellipsis","fontColor":"#99000000"}},{"id":"total_value","component":"Text","content":"{{ ${/data/appUsageStats/appUsage/durationText} }}","styles":{"fontSize":12,"fontWeight":700,"maxLines":1,"textOverflow":"ellipsis"}},{"id":"over_col","component":"Column","children":["over_label","over_value"],"itemMargin":2,"styles":{"width":"matchParent","layoutWeight":1,"flexShrink":1}},{"id":"over_label","component":"Text","content":"超出时长","styles":{"fontSize":10,"fontWeight":400,"maxLines":1,"textOverflow":"ellipsis","fontColor":"#99000000"}},{"id":"over_value","component":"Text","content":"0 分钟","styles":{"fontSize":12,"fontWeight":700,"maxLines":1,"textOverflow":"ellipsis","fontColor":"#FFE84026"}},{"id":"action_area","component":"Column","children":["settings_btn"],"styles":{"width":"matchParent","flexShrink":0}},{"id":"settings_btn","component":"Button","label":"重新设置","onClick":[{"call":"clickToDeeplink","args":{"abilityName":"com.huawei.hmos.settings.MainAbility","bundleName":"com.huawei.hmos.settings","intentName":"Settings","uri":"parent_control"}}],"styles":{"width":"matchParent","height":36,"borderRadius":20,"padding":{"left":8,"top":0,"right":8,"bottom":0},"backgroundColor":"#0C000000","fontColor":"#FF0A59F7","fontSize":14,"fontWeight":500,"maxFontSize":14,"minFontSize":12,"maxLines":1,"flexShrink":0}}]}}
{"version":"v0.9","updateDataModel":{"surfaceId":"surface_card","path":"/","value":{"data":{"appUsageStats":{"appUsage":{"durationText":"25 分钟"}}}}}}
```
```schema
{
  "schemaVersion": "widget-artifact-v2"
}
```
```taskspec
{
  "userQuery": "使用2*2规格，创建抖音防沉迷小组件。卡片顶部显示应用使用时长监控标题；中间横向进度条展示今日使用进度，正常与超出设定值用不同颜色区分，橙色代表超出时长；中间显示每日使用具体参数（总时长及超出时长）；底部按钮点击进入系统设置重新设置每日使用时长上限。",
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
    "asset.hourglass_fill"
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
    "asset.hourglass_fill"
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
  "artifactId": "7f364f6e-03d3-45ed-8a5d-68d63db277dd",
  "createdAt": 1785721553096
}
```
```designcompactdsl
["root","Column",{"width":160,"height":160,"linearGradient":{"angle":145,"colors":[["#FFFFFFFF",0.0],["#FFF0F5FF",0.44],["#FF8EB3FF",1.0]]},"borderRadius":20,"padding":12,"clip":true,"itemMargin":8},["title_area","content_area","action_area"]]
["title_area","Row",{"width":"matchParent","alignItems":"start","itemMargin":4},["title_col","icon"]]
["title_col","Column",{"width":"matchParent","layoutWeight":1,"flexShrink":1,"itemMargin":4},["title_main","title_sub"]]
["title_main","Text",{"content":"应用时长","fontSize":12,"fontWeight":700,"width":"matchParent","maxLines":1,"textOverflow":"ellipsis"}]
["title_sub","Text",{"content":"今日使用","fontSize":12,"fontWeight":400,"width":"matchParent","maxLines":1,"textOverflow":"ellipsis"}]
["icon","Image",{"src":"resources/base/media/hourglass_fill.svg","width":20,"height":20,"borderRadius":4,"clip":true,"flexShrink":0,"fillColor":"#E5000000"}]
["content_area","Column",{"width":"matchParent","layoutWeight":1,"justifyContent":"start","itemMargin":4},["progress_row","stats_row"]]
["progress_row","Row",{"width":"matchParent","alignItems":"center","itemMargin":8},["progress_bar","progress_label"]]
["progress_bar","Progress",{"design":"linear-bar","value":{"path":"/data/appUsageStats/appUsage/durationText"},"total":100,"color":"#FFED6F21"}]
["progress_label","Text",{"content":"超出","fontSize":10,"fontWeight":500,"flexShrink":0,"fontColor":"#FFE84026"}]
["stats_row","Row",{"width":"matchParent","justifyContent":"spaceBetween","itemMargin":8},["total_col","over_col"]]
["total_col","Column",{"width":"matchParent","layoutWeight":1,"flexShrink":1,"itemMargin":2},["total_label","total_value"]]
["total_label","Text",{"content":"总时长","fontSize":10,"fontWeight":400,"maxLines":1,"textOverflow":"ellipsis","fontColor":"#99000000"}]
["total_value","Text",{"content":{"path":"/data/appUsageStats/appUsage/durationText"},"fontSize":12,"fontWeight":700,"maxLines":1,"textOverflow":"ellipsis"}]
["over_col","Column",{"width":"matchParent","layoutWeight":1,"flexShrink":1,"itemMargin":2},["over_label","over_value"]]
["over_label","Text",{"content":"超出时长","fontSize":10,"fontWeight":400,"maxLines":1,"textOverflow":"ellipsis","fontColor":"#99000000"}]
["over_value","Text",{"content":"0 分钟","fontSize":12,"fontWeight":700,"maxLines":1,"textOverflow":"ellipsis","fontColor":"#FFE84026"}]
["action_area","Column",{"width":"matchParent","flexShrink":0},["settings_btn"]]
["settings_btn","Button",{"label":"重新设置","design":"capsule","fontColor":"#FF0A59F7","onClick":[{"call":"clickToDeeplink","args":{"abilityName":"com.huawei.hmos.settings.MainAbility","bundleName":"com.huawei.hmos.settings","intentName":"Settings","uri":"parent_control"}}]},["settings_icon"]]
["settings_icon","Image",{"src":"resources/base/media/hourglass_fill.svg","width":24,"height":24,"flexShrink":0,"fillColor":"#FF0A59F7"}]
["/data/appUsageStats/appUsage/durationText","25 分钟"]
```
