```cardspec
{
  "title": "省电管理",
  "description": "省电管理卡片",
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
{"version":"v0.9","updateComponents":{"surfaceId":"surface_card","root":"root","components":[{"id":"root","component":"Column","children":["title_area","content_area","action_area"],"itemMargin":8,"styles":{"width":"matchParent","height":"matchParent","linearGradient":{"angle":145,"colors":[["#FF1A1A2E",0.0],["#FF16213E",0.5],["#FF0F3460",1.0]]},"borderRadius":20,"padding":12,"clip":true}},{"id":"title_area","component":"Row","children":["title_col","title_icon"],"itemMargin":4,"styles":{"width":"matchParent","alignItems":"start"}},{"id":"title_col","component":"Column","children":["title_main","title_sub"],"itemMargin":4,"styles":{"width":"matchParent","layoutWeight":1,"flexShrink":1}},{"id":"title_main","component":"Text","content":"省电助手","styles":{"fontSize":12,"fontWeight":700,"width":"matchParent","maxLines":1,"textOverflow":"ellipsis","fontColor":"#FFFFFFFF"}},{"id":"title_sub","component":"Text","content":"正常电量","styles":{"fontSize":12,"fontWeight":400,"width":"matchParent","maxLines":1,"textOverflow":"ellipsis","fontColor":"#99FFFFFF"}},{"id":"title_icon","component":"Image","src":"resources/base/media/battery_leaf_fill.svg","styles":{"width":20,"height":20,"borderRadius":4,"clip":true,"flexShrink":0,"fillColor":"#FFFFFFFF"}},{"id":"content_area","component":"Column","children":["ring_unit","switch_row"],"itemMargin":8,"styles":{"width":"matchParent","layoutWeight":1,"justifyContent":"center","alignItems":"center"}},{"id":"ring_unit","component":"Column","children":["ring_stack","reading_below"],"itemMargin":4,"styles":{"alignItems":"center","flexShrink":0}},{"id":"ring_stack","component":"Stack","children":["ring_bar","center_icon"],"styles":{"width":52,"height":52,"alignContent":"center","flexShrink":0}},{"id":"ring_bar","component":"Progress","value":"{{ ${/data/phoneBattery/batterySOC} }}","total":100,"styles":{"type":"ring","color":"#FF64BB5C","strokeWidth":6}},{"id":"center_icon","component":"Image","src":"resources/base/media/bolt_fill.svg","styles":{"width":24,"height":24,"flexShrink":0,"fillColor":"#FFFFFFFF"}},{"id":"reading_below","component":"Row","children":["reading_num","reading_unit"],"styles":{"alignItems":"center","flexShrink":0}},{"id":"reading_num","component":"Text","content":"{{ ${/data/phoneBattery/batterySOC} }}","styles":{"fontSize":12,"fontWeight":700,"maxLines":1,"flexShrink":0,"fontColor":"#FFFFFFFF"}},{"id":"reading_unit","component":"Text","content":"%","styles":{"fontSize":12,"fontWeight":700,"maxLines":1,"flexShrink":0,"fontColor":"#FFFFFFFF"}},{"id":"switch_row","component":"Row","children":["saving_switch","dnd_switch"],"itemMargin":8,"styles":{"width":"matchParent","justifyContent":"spaceBetween"}},{"id":"saving_switch","component":"Row","children":["saving_icon","saving_text"],"itemMargin":4,"styles":{"alignItems":"center"}},{"id":"saving_icon","component":"Image","src":"resources/base/media/battery_leaf_fill.svg","styles":{"width":16,"height":16,"flexShrink":0,"fillColor":"#FFFFFFFF"}},{"id":"saving_text","component":"Text","content":"省电","styles":{"fontSize":10,"fontWeight":500,"maxLines":1,"fontColor":"#FFFFFFFF"}},{"id":"dnd_switch","component":"Row","children":["dnd_icon","dnd_text"],"itemMargin":4,"styles":{"alignItems":"center"}},{"id":"dnd_icon","component":"Image","src":"resources/base/media/moon_circle_fill.svg","styles":{"width":16,"height":16,"flexShrink":0,"fillColor":"#FFFFFFFF"}},{"id":"dnd_text","component":"Text","content":"勿扰","styles":{"fontSize":10,"fontWeight":500,"maxLines":1,"fontColor":"#FFFFFFFF"}},{"id":"action_area","component":"Column","children":["battery_btn"],"styles":{"width":"matchParent","flexShrink":0}},{"id":"battery_btn","component":"Button","label":"电池设置","onClick":[{"call":"clickToDeeplink","args":{"abilityName":"com.huawei.hmos.settings.MainAbility","bundleName":"com.huawei.hmos.settings","intentName":"Settings","uri":"battery"}}],"styles":{"width":"matchParent","height":36,"borderRadius":20,"padding":{"left":8,"top":0,"right":8,"bottom":0},"backgroundColor":"#0C000000","fontColor":"#FF0A59F7","fontSize":14,"fontWeight":500,"maxFontSize":14,"minFontSize":12,"maxLines":1,"flexShrink":0}}]}}
{"version":"v0.9","updateDataModel":{"surfaceId":"surface_card","path":"/","value":{"data":{"phoneBattery":{"batterySOC":68,"batteryCapacityLevelDesc":"正常电量"}}}}}
```
```schema
{
  "schemaVersion": "widget-artifact-v2"
}
```
```taskspec
{
  "userQuery": "做一个2x2省电小组件，暗色夜晚深色渐变背景，中央环形电池图标叠加百分比数字，省电模式开关和勿扰开关可一键切换，电量低于15%时环形图标变红色告警，底部按钮跳转系统电池设置页",
  "size": "2x2",
  "eventCandidates": [
    {
      "id": "event.setPowerSavingMode",
      "call": "clickToIntent",
      "args": {
        "intentName": "SetSettingSwitch",
        "params": {
          "appBundleName": "com.huawei.hmos.settings",
          "itemName": "battery_saving_mode",
          "switchFlag": 1
        }
      }
    },
    {
      "id": "event.open.settings.dnd",
      "call": "clickToDeeplink",
      "args": {
        "abilityName": "com.huawei.hmos.settings.MainAbility",
        "bundleName": "com.huawei.hmos.settings",
        "intentName": "Settings",
        "uri": "intelligent_scene_entry"
      }
    },
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
        "batterySOC": {
          "type": "integer",
          "description": "当前手机设备剩余电池电量百分比纯数字，取值范围为 0 到 100。",
          "sampleValue": 68
        },
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
        }
      }
    }
  },
  "assetCandidates": [
    {
      "id": "asset.battery_leaf_fill",
      "src": "resources/base/media/battery_leaf_fill.svg",
      "description": "电池与绿叶组合实心图标，黑色，图形为电池加叶片造型，适用场景：节能模式、绿色用电、环保出行"
    },
    {
      "id": "asset.bolt_fill",
      "src": "resources/base/media/bolt_fill.svg",
      "description": "闪电实心图标，黑色，图形为竖向闪电符号，适用场景：充电状态、快充指示、用电量展示"
    },
    {
      "id": "asset.bell_slash_fill",
      "src": "resources/base/media/bell_slash_fill.svg",
      "description": "铃铛加斜杠实心图标，黑白双色，图形为铃铛上叠加删除线，适用场景：静音模式、关闭通知、勿扰设置"
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
    "GetPhoneBatteryInfo"
  ],
  "event": [
    {
      "id": "event.setPowerSavingMode",
      "call": "clickToIntent",
      "args": {
        "intentName": "SetSettingSwitch",
        "params": {
          "appBundleName": "com.huawei.hmos.settings",
          "itemName": "battery_saving_mode",
          "switchFlag": 1
        }
      }
    },
    {
      "id": "event.open.settings.dnd",
      "call": "clickToDeeplink",
      "args": {
        "abilityName": "com.huawei.hmos.settings.MainAbility",
        "bundleName": "com.huawei.hmos.settings",
        "intentName": "Settings",
        "uri": "intelligent_scene_entry"
      }
    },
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
    "asset.battery_leaf_fill",
    "asset.bolt_fill",
    "asset.bell_slash_fill",
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
      "capabilityId": "GetPhoneBatteryInfo",
      "arguments": {},
      "writeResultTo": "/data/phoneBattery",
      "candidateOutputFields": [
        "/batterySOC",
        "/batterySOCText",
        "/chargingStatusDesc",
        "/batteryCapacityLevelDesc"
      ]
    }
  ],
  "candidateEventCandidates": [
    {
      "capabilityId": "event.setPowerSavingMode",
      "action": {
        "call": "clickToIntent",
        "args": {
          "intentName": "SetSettingSwitch",
          "params": {
            "appBundleName": "com.huawei.hmos.settings",
            "itemName": "battery_saving_mode",
            "switchFlag": 1
          }
        }
      }
    },
    {
      "capabilityId": "event.open.settings.dnd",
      "action": {
        "call": "clickToDeeplink",
        "args": {
          "abilityName": "com.huawei.hmos.settings.MainAbility",
          "bundleName": "com.huawei.hmos.settings",
          "intentName": "Settings",
          "uri": "intelligent_scene_entry"
        }
      }
    },
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
    "asset.battery_leaf_fill",
    "asset.bolt_fill",
    "asset.bell_slash_fill",
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
  "artifactId": "f048c340-b72e-46da-bc22-4ab6a886557b",
  "createdAt": 1785721223471
}
```
```designcompactdsl
["root","Column",{"width":160,"height":160,"linearGradient":{"angle":145,"colors":[["#FF1A1A2E",0.0],["#FF16213E",0.5],["#FF0F3460",1.0]]},"borderRadius":20,"padding":12,"clip":true,"itemMargin":8},["title_area","content_area","action_area"]]
["title_area","Row",{"width":"matchParent","alignItems":"start","itemMargin":4},["title_col","title_icon"]]
["title_col","Column",{"width":"matchParent","layoutWeight":1,"flexShrink":1,"itemMargin":4},["title_main","title_sub"]]
["title_main","Text",{"content":"省电助手","fontSize":12,"fontWeight":700,"width":"matchParent","maxLines":1,"textOverflow":"ellipsis","fontColor":"#FFFFFFFF"}]
["title_sub","Text",{"content":"正常电量","fontSize":12,"fontWeight":400,"width":"matchParent","maxLines":1,"textOverflow":"ellipsis","fontColor":"#99FFFFFF"}]
["title_icon","Image",{"src":"resources/base/media/battery_leaf_fill.svg","width":20,"height":20,"borderRadius":4,"clip":true,"flexShrink":0,"fillColor":"#FFFFFFFF"}]
["content_area","Column",{"width":"matchParent","layoutWeight":1,"justifyContent":"center","alignItems":"center","itemMargin":8},["ring_unit","switch_row"]]
["ring_unit","Column",{"itemMargin":4,"alignItems":"center","flexShrink":0},["ring_stack","reading_below"]]
["ring_stack","Stack",{"width":52,"height":52,"alignContent":"center","flexShrink":0},["ring_bar","center_icon"]]
["ring_bar","Progress",{"type":"ring","value":{"path":"/data/phoneBattery/batterySOC"},"total":100,"color":"#FF64BB5C","strokeWidth":6}]
["center_icon","Image",{"src":"resources/base/media/bolt_fill.svg","width":24,"height":24,"flexShrink":0,"fillColor":"#FFFFFFFF"}]
["reading_below","Row",{"alignItems":"center","flexShrink":0},["reading_num","reading_unit"]]
["reading_num","Text",{"content":{"path":"/data/phoneBattery/batterySOC"},"fontSize":12,"fontWeight":700,"maxLines":1,"flexShrink":0,"fontColor":"#FFFFFFFF"}]
["reading_unit","Text",{"content":"%","fontSize":12,"fontWeight":700,"maxLines":1,"flexShrink":0,"fontColor":"#FFFFFFFF"}]
["switch_row","Row",{"width":"matchParent","justifyContent":"spaceBetween","itemMargin":8},["saving_switch","dnd_switch"]]
["saving_switch","Row",{"alignItems":"center","itemMargin":4},["saving_icon","saving_text"]]
["saving_icon","Image",{"src":"resources/base/media/battery_leaf_fill.svg","width":16,"height":16,"flexShrink":0,"fillColor":"#FFFFFFFF"}]
["saving_text","Text",{"content":"省电","fontSize":10,"fontWeight":500,"maxLines":1,"fontColor":"#FFFFFFFF"}]
["dnd_switch","Row",{"alignItems":"center","itemMargin":4},["dnd_icon","dnd_text"]]
["dnd_icon","Image",{"src":"resources/base/media/moon_circle_fill.svg","width":16,"height":16,"flexShrink":0,"fillColor":"#FFFFFFFF"}]
["dnd_text","Text",{"content":"勿扰","fontSize":10,"fontWeight":500,"maxLines":1,"fontColor":"#FFFFFFFF"}]
["action_area","Column",{"width":"matchParent","flexShrink":0},["battery_btn"]]
["battery_btn","Button",{"label":"电池设置","design":"capsule","fontColor":"#FF0A59F7","onClick":[{"call":"clickToDeeplink","args":{"abilityName":"com.huawei.hmos.settings.MainAbility","bundleName":"com.huawei.hmos.settings","intentName":"Settings","uri":"battery"}}]},["btn_icon"]]
["btn_icon","Image",{"src":"resources/base/media/battery_leaf_fill.svg","width":24,"height":24,"flexShrink":0,"fillColor":"#FF0A59F7"}]
["/data/phoneBattery/batterySOC",68]
["/data/phoneBattery/batteryCapacityLevelDesc","正常电量"]
```
