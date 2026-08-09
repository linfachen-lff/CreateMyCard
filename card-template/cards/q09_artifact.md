```cardspec
{
  "title": "电量监控",
  "description": "实时手机电量速览",
  "suggestSize": "2x2",
  "dataBindings": [
    {
      "capabilityId": "GetPhoneBatteryInfo",
      "arguments": {},
      "writeResultTo": "/data/phoneBattery"
    }
  ]
}
```
```genui
{"version":"v0.9","createSurface":{"surfaceId":"surface_card","catalogId":"ohos.a2ui.extended.catalog.form","width":140,"height":140}}
{"version":"v0.9","updateComponents":{"surfaceId":"surface_card","root":"root","components":[{"id":"root","component":"Column","children":["title_area","content_area","action_area"],"itemMargin":8,"styles":{"width":"matchParent","height":"matchParent","linearGradient":{"angle":145,"colors":[["#FFFFFFFF",0.0],["#FFF0FBF8",0.44],["#FF92D6CC",1.0]]},"borderRadius":20,"padding":12,"clip":true}},{"id":"title_area","component":"Row","children":["title_col","title_icon"],"itemMargin":4,"styles":{"width":"matchParent","alignItems":"start"}},{"id":"title_col","component":"Column","children":["title_main"],"styles":{"width":"matchParent","layoutWeight":1,"flexShrink":1}},{"id":"title_main","component":"Text","content":"低电量","styles":{"fontSize":12,"fontWeight":400,"width":"matchParent","maxLines":1,"textOverflow":"ellipsis"}},{"id":"title_icon","component":"Image","src":"resources/base/media/bolt_fill.svg","styles":{"width":20,"height":20,"borderRadius":4,"clip":true,"flexShrink":0,"fillColor":"#E5000000"}},{"id":"content_area","component":"Column","children":["ring_unit"],"itemMargin":4,"styles":{"width":"matchParent","layoutWeight":1,"justifyContent":"start","alignItems":"center"}},{"id":"ring_unit","component":"Column","children":["ring_stack","reading_below"],"itemMargin":4,"styles":{"alignItems":"center","flexShrink":0}},{"id":"ring_stack","component":"Stack","children":["ring_bar","center_icon"],"styles":{"width":44,"height":44,"alignContent":"center","flexShrink":0}},{"id":"ring_bar","component":"Progress","value":"{{ ${/data/phoneBattery/batterySOCText} }}","total":100,"styles":{"type":"ring","strokeWidth":6}},{"id":"center_icon","component":"Image","src":"resources/base/media/bolt_fill.svg","styles":{"width":20,"height":20,"flexShrink":0,"fillColor":"#FF0A59F7"}},{"id":"reading_below","component":"Text","content":"{{ ${/data/phoneBattery/batterySOCText} }}","styles":{"fontSize":12,"fontWeight":700,"maxLines":1,"flexShrink":0}},{"id":"action_area","component":"Column","children":["settings_btn"],"styles":{"width":"matchParent","flexShrink":0}},{"id":"settings_btn","component":"Button","label":"电池设置","onClick":[{"call":"clickToDeeplink","args":{"abilityName":"com.huawei.hmos.settings.MainAbility","bundleName":"com.huawei.hmos.settings","intentName":"Settings","uri":"battery"}}],"styles":{"width":"matchParent","height":36,"borderRadius":20,"padding":{"left":8,"top":0,"right":8,"bottom":0},"backgroundColor":"#0C000000","fontColor":"#FF0A59F7","fontSize":14,"fontWeight":500,"maxFontSize":14,"minFontSize":12,"maxLines":1,"flexShrink":0}}]}}
{"version":"v0.9","updateDataModel":{"surfaceId":"surface_card","path":"/","value":{"data":{"phoneBattery":{"batterySOCText":"68%"}}}}}
```
```schema
{
  "schemaVersion": "widget-artifact-v2"
}
```
```taskspec
{
  "userQuery": "使用2*2规格，生成低电量卡片，实时展示手机电量。",
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
      "phoneBattery": {
        "batterySOCText": {
          "type": "string",
          "description": "当前手机设备剩余电池电量百分比格式化文本。",
          "sampleValue": "68%"
        },
        "chargingStatusDesc": {
          "type": "string",
          "description": "当前设备电池的充电状态文本描述。",
          "sampleValue": "充电中"
        },
        "batteryCapacityLevelDesc": {
          "type": "string",
          "description": "设备电池电量等级的语义化文本描述。",
          "sampleValue": "正常电量"
        },
        "batteryTemperatureText": {
          "type": "string",
          "description": "当前设备电池的实时温度文本，带有摄氏度单位。",
          "sampleValue": "29.0 ℃"
        }
      }
    }
  },
  "assetCandidates": [
    {
      "id": "asset.bolt_fill",
      "src": "resources/base/media/bolt_fill.svg",
      "description": "闪电实心图标，黑色，图形为竖向闪电符号，适用场景：充电状态、快充指示、用电量展示"
    },
    {
      "id": "asset.battery_leaf_fill",
      "src": "resources/base/media/battery_leaf_fill.svg",
      "description": "电池与绿叶组合实心图标，黑色，图形为电池加叶片造型，适用场景：节能模式、绿色用电、环保出行"
    }
  ]
}
```
```effectivecapabilities
{
  "data": [
    "GetPhoneBatteryInfo"
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
    "asset.bolt_fill",
    "asset.battery_leaf_fill"
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
      "capabilityId": "GetPhoneBatteryInfo",
      "arguments": {},
      "writeResultTo": "/data/phoneBattery",
      "candidateOutputFields": [
        "/batterySOCText",
        "/chargingStatusDesc",
        "/batteryCapacityLevelDesc",
        "/batteryTemperatureText"
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
    "asset.bolt_fill",
    "asset.battery_leaf_fill"
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
  "artifactId": "2a581f5c-de03-4e4e-a31c-ca325ca70a81",
  "createdAt": 1785721276583
}
```
```designcompactdsl
["root","Column",{"width":160,"height":160,"linearGradient":{"angle":145,"colors":[["#FFFFFFFF",0.0],["#FFF0FBF8",0.44],["#FF92D6CC",1.0]]},"borderRadius":20,"padding":12,"clip":true,"itemMargin":8},["title_area","content_area","action_area"]]
["title_area","Row",{"width":"matchParent","alignItems":"start","itemMargin":4},["title_col","title_icon"]]
["title_col","Column",{"width":"matchParent","layoutWeight":1,"flexShrink":1},["title_main"]]
["title_main","Text",{"content":"低电量","fontSize":12,"fontWeight":400,"width":"matchParent","maxLines":1,"textOverflow":"ellipsis"}]
["title_icon","Image",{"src":"resources/base/media/bolt_fill.svg","width":20,"height":20,"borderRadius":4,"clip":true,"flexShrink":0,"fillColor":"#E5000000"}]
["content_area","Column",{"width":"matchParent","layoutWeight":1,"justifyContent":"start","alignItems":"center","itemMargin":4},["ring_unit"]]
["ring_unit","Column",{"itemMargin":4,"alignItems":"center","flexShrink":0},["ring_stack","reading_below"]]
["ring_stack","Stack",{"width":44,"height":44,"alignContent":"center","flexShrink":0},["ring_bar","center_icon"]]
["ring_bar","Progress",{"type":"ring","value":{"path":"/data/phoneBattery/batterySOCText"},"total":100,"strokeWidth":6}]
["center_icon","Image",{"src":"resources/base/media/bolt_fill.svg","width":20,"height":20,"flexShrink":0,"fillColor":"#FF0A59F7"}]
["reading_below","Text",{"content":{"path":"/data/phoneBattery/batterySOCText"},"fontSize":12,"fontWeight":700,"maxLines":1,"flexShrink":0}]
["action_area","Column",{"width":"matchParent","flexShrink":0},["settings_btn"]]
["settings_btn","Button",{"label":"电池设置","design":"capsule","fontColor":"#FF0A59F7","onClick":[{"call":"clickToDeeplink","args":{"abilityName":"com.huawei.hmos.settings.MainAbility","bundleName":"com.huawei.hmos.settings","intentName":"Settings","uri":"battery"}}]},["settings_icon"]]
["settings_icon","Image",{"src":"resources/base/media/bolt_fill.svg","width":24,"height":24,"flexShrink":0,"fillColor":"#FF0A59F7"}]
["/data/phoneBattery/batterySOCText","68%"]
```
