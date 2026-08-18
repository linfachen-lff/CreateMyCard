```cardspec
{
  "title": "省电助手",
  "description": "电量监控与省电管理",
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
{"version":"v0.9","updateComponents":{"surfaceId":"surface_card","root":"root","components":[{"id":"root","component":"Column","children":["title_area","content_area","action_area"],"itemMargin":8,"styles":{"width":"matchParent","height":"matchParent","linearGradient":{"angle":145,"colors":[["#FF1A1A2E",0.0],["#FF16213E",0.5],["#FF0F3460",1.0]]},"borderRadius":20,"padding":12,"clip":true}},{"id":"title_area","component":"Row","children":["title_col","icon"],"itemMargin":4,"styles":{"width":"matchParent","alignItems":"start"}},{"id":"title_col","component":"Column","children":["title_main","title_sub"],"itemMargin":4,"styles":{"width":"matchParent","layoutWeight":1,"flexShrink":1}},{"id":"title_main","component":"Text","content":"省电","styles":{"fontSize":12,"fontWeight":700,"width":"matchParent","maxLines":1,"textOverflow":"ellipsis","fontColor":"#FFFFFFFF"}},{"id":"title_sub","component":"Text","content":"夜间守护","styles":{"fontSize":12,"fontWeight":400,"width":"matchParent","maxLines":1,"textOverflow":"ellipsis","fontColor":"#99FFFFFF"}},{"id":"icon","component":"Image","src":"resources/base/media/battery_leaf_fill.svg","styles":{"width":20,"height":20,"borderRadius":4,"clip":true,"flexShrink":0,"fillColor":"#FFFFFFFF"}},{"id":"content_area","component":"Column","children":["ring_group","status_row"],"itemMargin":8,"styles":{"width":"matchParent","layoutWeight":1,"justifyContent":"start"}},{"id":"ring_group","component":"Column","children":["ring_unit"],"itemMargin":4,"styles":{"width":"matchParent","alignItems":"center"}},{"id":"ring_unit","component":"Column","children":["ring_stack","reading_below"],"itemMargin":4,"styles":{"alignItems":"center","flexShrink":0}},{"id":"ring_stack","component":"Stack","children":["ring_bar","center_icon"],"styles":{"width":44,"height":44,"alignContent":"center","flexShrink":0}},{"id":"ring_bar","component":"Progress","value":"{{ ${/data/phoneBattery/batterySOCText} }}","total":100,"styles":{"type":"ring","strokeWidth":6,"color":"#FFE84026"}},{"id":"center_icon","component":"Image","src":"resources/base/media/bolt_fill.svg","styles":{"width":20,"height":20,"flexShrink":0,"fillColor":"#FFFFFFFF"}},{"id":"reading_below","component":"Row","children":["reading_value","reading_unit"],"styles":{"alignItems":"center","flexShrink":0}},{"id":"reading_value","component":"Text","content":"{{ ${/data/phoneBattery/batterySOCText} }}","styles":{"fontSize":12,"fontWeight":700,"maxLines":1,"flexShrink":0,"fontColor":"#FFE84026"}},{"id":"reading_unit","component":"Text","content":"%","styles":{"fontSize":12,"fontWeight":700,"maxLines":1,"flexShrink":0,"fontColor":"#FFE84026"}},{"id":"status_row","component":"Row","children":["status_text","status_icon"],"styles":{"width":"matchParent","alignItems":"center","justifyContent":"spaceBetween"}},{"id":"status_text","component":"Text","content":"{{ ${/data/phoneBattery/batteryCapacityLevelDesc} }}","styles":{"fontSize":12,"fontWeight":400,"maxLines":1,"textOverflow":"ellipsis","width":"matchParent","layoutWeight":1,"flexShrink":1,"fontColor":"#99FFFFFF"}},{"id":"status_icon","component":"Image","src":"resources/base/media/bell_slash_fill.svg","styles":{"width":16,"height":16,"flexShrink":0,"fillColor":"#99FFFFFF"}},{"id":"action_area","component":"Column","children":["power_saving_btn"],"styles":{"width":"matchParent","flexShrink":0}},{"id":"power_saving_btn","component":"Button","label":"开启省电","onClick":[{"call":"clickToIntent","args":{"intentName":"SetSettingSwitch","params":{"appBundleName":"com.huawei.hmos.settings","itemName":"battery_saving_mode","switchFlag":1}}}],"styles":{"width":"matchParent","height":36,"borderRadius":20,"padding":{"left":8,"top":0,"right":8,"bottom":0},"backgroundColor":"#0C000000","fontColor":"#FF0A59F7","fontSize":14,"fontWeight":500,"maxFontSize":14,"minFontSize":12,"maxLines":1,"flexShrink":0}}]}}
{"version":"v0.9","updateDataModel":{"surfaceId":"surface_card","path":"/","value":{"data":{"phoneBattery":{"batterySOCText":"68%","batteryCapacityLevelDesc":"正常电量"}}}}}
```
```schema
{
  "schemaVersion": "widget-artifact-v2"
}
```
```taskspec
{
  "userQuery": "使用2*2规格，创建省电小组件，显示手机剩余电量百分比，电量低于15%时红色告警，带一键开启省电模式开关和勿扰模式开关，深色夜晚渐变风格",
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
    },
    {
      "id": "asset.bell_slash_fill",
      "src": "resources/base/media/bell_slash_fill.svg",
      "description": "铃铛加斜杠实心图标，黑白双色，图形为铃铛上叠加删除线，适用场景：静音模式、关闭通知、勿扰设置"
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
    }
  ],
  "asset": [
    "asset.bolt_fill",
    "asset.battery_leaf_fill",
    "asset.bell_slash_fill"
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
    }
  ],
  "candidateAssetIds": [
    "asset.bolt_fill",
    "asset.battery_leaf_fill",
    "asset.bell_slash_fill"
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
  "artifactId": "56b84ce7-d8ad-4a10-9dc4-b08e32665a9c",
  "createdAt": 1785721011874
}
```
```designcompactdsl
["root","Column",{"width":160,"height":160,"linearGradient":{"angle":145,"colors":[["#FF1A1A2E",0.0],["#FF16213E",0.5],["#FF0F3460",1.0]]},"borderRadius":20,"padding":12,"clip":true,"itemMargin":8},["title_area","content_area","action_area"]]
["title_area","Row",{"width":"matchParent","alignItems":"start","itemMargin":4},["title_col","icon"]]
["title_col","Column",{"width":"matchParent","layoutWeight":1,"flexShrink":1,"itemMargin":4},["title_main","title_sub"]]
["title_main","Text",{"content":"省电","fontSize":12,"fontWeight":700,"width":"matchParent","maxLines":1,"textOverflow":"ellipsis","fontColor":"#FFFFFFFF"}]
["title_sub","Text",{"content":"夜间守护","fontSize":12,"fontWeight":400,"width":"matchParent","maxLines":1,"textOverflow":"ellipsis","fontColor":"#99FFFFFF"}]
["icon","Image",{"src":"resources/base/media/battery_leaf_fill.svg","width":20,"height":20,"borderRadius":4,"clip":true,"flexShrink":0,"fillColor":"#FFFFFFFF"}]
["content_area","Column",{"width":"matchParent","layoutWeight":1,"justifyContent":"start","itemMargin":8},["ring_group","status_row"]]
["ring_group","Column",{"width":"matchParent","alignItems":"center","itemMargin":4},["ring_unit"]]
["ring_unit","Column",{"itemMargin":4,"alignItems":"center","flexShrink":0},["ring_stack","reading_below"]]
["ring_stack","Stack",{"width":44,"height":44,"alignContent":"center","flexShrink":0},["ring_bar","center_icon"]]
["ring_bar","Progress",{"type":"ring","value":{"path":"/data/phoneBattery/batterySOCText"},"total":100,"strokeWidth":6,"color":"#FFE84026"}]
["center_icon","Image",{"src":"resources/base/media/bolt_fill.svg","width":20,"height":20,"flexShrink":0,"fillColor":"#FFFFFFFF"}]
["reading_below","Row",{"alignItems":"center","flexShrink":0},["reading_value","reading_unit"]]
["reading_value","Text",{"content":{"path":"/data/phoneBattery/batterySOCText"},"fontSize":12,"fontWeight":700,"maxLines":1,"flexShrink":0,"fontColor":"#FFE84026"}]
["reading_unit","Text",{"content":"%","fontSize":12,"fontWeight":700,"maxLines":1,"flexShrink":0,"fontColor":"#FFE84026"}]
["status_row","Row",{"width":"matchParent","alignItems":"center","justifyContent":"spaceBetween"},["status_text","status_icon"]]
["status_text","Text",{"content":{"path":"/data/phoneBattery/batteryCapacityLevelDesc"},"design":"body-s","maxLines":1,"textOverflow":"ellipsis","width":"matchParent","layoutWeight":1,"flexShrink":1,"fontColor":"#99FFFFFF"}]
["status_icon","Image",{"src":"resources/base/media/bell_slash_fill.svg","width":16,"height":16,"flexShrink":0,"fillColor":"#99FFFFFF"}]
["action_area","Column",{"width":"matchParent","flexShrink":0},["power_saving_btn"]]
["power_saving_btn","Button",{"label":"开启省电","design":"capsule","fontColor":"#FF0A59F7","onClick":[{"call":"clickToIntent","args":{"intentName":"SetSettingSwitch","params":{"appBundleName":"com.huawei.hmos.settings","itemName":"battery_saving_mode","switchFlag":1}}}]},["power_saving_icon"]]
["power_saving_icon","Image",{"src":"resources/base/media/battery_leaf_fill.svg","width":24,"height":24,"flexShrink":0,"fillColor":"#FF0A59F7"}]
["/data/phoneBattery/batterySOCText","68%"]
["/data/phoneBattery/batteryCapacityLevelDesc","正常电量"]
```
