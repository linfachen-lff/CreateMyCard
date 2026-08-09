```cardspec
{
  "title": "耳机播控",
  "description": "华为耳机播控中心，实时展示耳机连接状态、左右耳及充电盒电量，点击可跳转蓝牙设置",
  "suggestSize": "2x2",
  "dataBindings": [
    {
      "capabilityId": "GetEarphoneInfo",
      "arguments": {},
      "writeResultTo": "/data/earphone"
    }
  ]
}
```
```genui
{"version":"v0.9","createSurface":{"surfaceId":"surface_card","catalogId":"ohos.a2ui.extended.catalog.form","width":140,"height":140}}
{"version":"v0.9","updateComponents":{"surfaceId":"surface_card","root":"root","components":[{"id":"root","component":"Column","children":["title_area","content_area","action_area"],"itemMargin":8,"styles":{"width":"matchParent","height":"matchParent","linearGradient":{"angle":145,"colors":[["#FFFFFFFF",0.0],["#FFF0F5FF",0.44],["#FF8EB3FF",1.0]]},"borderRadius":20,"padding":12,"clip":true}},{"id":"title_area","component":"Row","children":["title_col"],"itemMargin":4,"styles":{"width":"matchParent","alignItems":"start"}},{"id":"title_col","component":"Column","children":["title_main","title_sub"],"itemMargin":4,"styles":{"width":"matchParent","layoutWeight":1,"flexShrink":1}},{"id":"title_main","component":"Text","content":"耳机播控","styles":{"fontSize":12,"fontWeight":700,"width":"matchParent","maxLines":1,"textOverflow":"ellipsis"}},{"id":"title_sub","component":"Text","content":"FreeBuds Pro 3","styles":{"fontSize":12,"fontWeight":400,"width":"matchParent","maxLines":1,"textOverflow":"ellipsis"}},{"id":"content_area","component":"Column","children":["kv_row_1","kv_row_2"],"itemMargin":8,"styles":{"width":"matchParent","layoutWeight":1,"justifyContent":"start"}},{"id":"kv_row_1","component":"Row","children":["label_1","value_1"],"itemMargin":8,"styles":{"width":"matchParent","alignItems":"center"}},{"id":"label_1","component":"Text","content":"左耳电量","styles":{"fontSize":12,"fontWeight":400,"layoutWeight":1,"width":"matchParent","flexShrink":1,"maxLines":1,"textOverflow":"ellipsis"}},{"id":"value_1","component":"Row","children":["num_1","unit_1"],"styles":{"alignItems":"center","flexShrink":0}},{"id":"num_1","component":"Text","content":"{{ ${/data/earphone/leftBatteryLevel} }}","styles":{"fontSize":12,"fontWeight":500,"maxLines":1}},{"id":"unit_1","component":"Text","content":"%","styles":{"fontSize":12,"fontWeight":500,"maxLines":1}},{"id":"kv_row_2","component":"Row","children":["label_2","value_2"],"itemMargin":8,"styles":{"width":"matchParent","alignItems":"center"}},{"id":"label_2","component":"Text","content":"右耳电量","styles":{"fontSize":12,"fontWeight":400,"layoutWeight":1,"width":"matchParent","flexShrink":1,"maxLines":1,"textOverflow":"ellipsis"}},{"id":"value_2","component":"Row","children":["num_2","unit_2"],"styles":{"alignItems":"center","flexShrink":0}},{"id":"num_2","component":"Text","content":"{{ ${/data/earphone/rightBatteryLevel} }}","styles":{"fontSize":12,"fontWeight":500,"maxLines":1}},{"id":"unit_2","component":"Text","content":"%","styles":{"fontSize":12,"fontWeight":500,"maxLines":1}},{"id":"action_area","component":"Column","children":["btn"],"styles":{"width":"matchParent","flexShrink":0}},{"id":"btn","component":"Button","label":"蓝牙设置","onClick":[{"call":"clickToDeeplink","args":{"abilityName":"com.huawei.hmos.settings.MainAbility","bundleName":"com.huawei.hmos.settings","intentName":"Settings","uri":"bluetooth"}}],"styles":{"width":"matchParent","height":36,"borderRadius":20,"padding":{"left":8,"top":0,"right":8,"bottom":0},"backgroundColor":"#0C000000","fontColor":"#FF0A59F7","fontSize":14,"fontWeight":500,"maxFontSize":14,"minFontSize":12,"maxLines":1,"flexShrink":0}}]}}
{"version":"v0.9","updateDataModel":{"surfaceId":"surface_card","path":"/","value":{"data":{"earphone":{"leftBatteryLevel":76,"rightBatteryLevel":74}}}}}
```
```schema
{
  "schemaVersion": "widget-artifact-v2"
}
```
```taskspec
{
  "userQuery": "使用2*2规格，创建华为耳机播控卡片。",
  "size": "2x2",
  "eventCandidates": [
    {
      "id": "event.open.settings.bluetooth",
      "call": "clickToDeeplink",
      "args": {
        "abilityName": "com.huawei.hmos.settings.MainAbility",
        "bundleName": "com.huawei.hmos.settings",
        "intentName": "Settings",
        "uri": "bluetooth"
      }
    }
  ],
  "dataModelSchema": {
    "data": {
      "earphone": {
        "isConnected": {
          "type": "boolean",
          "description": "当前是否有蓝牙耳机处于连接活跃状态。",
          "sampleValue": true
        },
        "earphoneName": {
          "type": "string",
          "description": "耳机的设备广播名称，如果未连接则返回'未连接耳机'。如: 'FreeBuds Pro 3'。",
          "sampleValue": "FreeBuds Pro 3"
        },
        "batteryLevel": {
          "type": "integer",
          "description": "耳机盒（或整体）的当前电量百分比，取值范围 0-100。",
          "sampleValue": 80
        },
        "chargingStatusDesc": {
          "type": "string",
          "description": "耳机盒（或整体）当前的充电状态中文语义描述，'充电中' 或 '未充电'。",
          "sampleValue": "未充电"
        },
        "leftBatteryLevel": {
          "type": "integer",
          "description": "左耳机的当前电量百分比，取值范围 0-100。若未连接则为 0。",
          "sampleValue": 76
        },
        "leftChargingStatusDesc": {
          "type": "string",
          "description": "左耳机当前的充电状态中文语义描述，'充电中' 或 '未充电'。",
          "sampleValue": "未充电"
        },
        "rightBatteryLevel": {
          "type": "integer",
          "description": "右耳机的当前电量百分比，取值范围 0-100。若未连接则为 0。",
          "sampleValue": 74
        },
        "rightChargingStatusDesc": {
          "type": "string",
          "description": "右耳机当前的充电状态中文语义描述，'充电中' 或 '未充电'。",
          "sampleValue": "未充电"
        }
      }
    }
  },
  "assetCandidates": []
}
```
```effectivecapabilities
{
  "data": [
    "GetEarphoneInfo"
  ],
  "event": [
    {
      "id": "event.open.settings.bluetooth",
      "call": "clickToDeeplink",
      "args": {
        "abilityName": "com.huawei.hmos.settings.MainAbility",
        "bundleName": "com.huawei.hmos.settings",
        "intentName": "Settings",
        "uri": "bluetooth"
      }
    }
  ],
  "asset": []
}
```
```removedcapabilities
[
  {
    "id": "asset.music_note_fill",
    "type": "asset",
    "reason": "UNKNOWN_CAPABILITY",
    "userReadableReason": "能力未注册"
  },
  {
    "id": "asset.earphone_fill",
    "type": "asset",
    "reason": "UNKNOWN_CAPABILITY",
    "userReadableReason": "能力未注册"
  },
  {
    "id": "asset.bluetooth_fill",
    "type": "asset",
    "reason": "UNKNOWN_CAPABILITY",
    "userReadableReason": "能力未注册"
  }
]
```
```generationplan
{
  "candidateDataBindings": [
    {
      "capabilityId": "GetEarphoneInfo",
      "arguments": {},
      "writeResultTo": "/data/earphone",
      "candidateOutputFields": [
        "/isConnected",
        "/earphoneName",
        "/batteryLevel",
        "/chargingStatusDesc",
        "/leftBatteryLevel",
        "/leftChargingStatusDesc",
        "/rightBatteryLevel",
        "/rightChargingStatusDesc"
      ]
    }
  ],
  "candidateEventCandidates": [
    {
      "capabilityId": "event.open.settings.bluetooth",
      "action": {
        "call": "clickToDeeplink",
        "args": {
          "abilityName": "com.huawei.hmos.settings.MainAbility",
          "bundleName": "com.huawei.hmos.settings",
          "intentName": "Settings",
          "uri": "bluetooth"
        }
      }
    }
  ],
  "candidateAssetIds": []
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
  "artifactId": "0646780b-a5c1-4912-9383-6aa760674610",
  "createdAt": 1785721334627
}
```
```designcompactdsl
["root","Column",{"width":160,"height":160,"linearGradient":{"angle":145,"colors":[["#FFFFFFFF",0.0],["#FFF0F5FF",0.44],["#FF8EB3FF",1.0]]},"borderRadius":20,"padding":12,"clip":true,"itemMargin":8},["title_area","content_area","action_area"]]
["title_area","Row",{"width":"matchParent","alignItems":"start","itemMargin":4},["title_col"]]
["title_col","Column",{"width":"matchParent","layoutWeight":1,"flexShrink":1,"itemMargin":4},["title_main","title_sub"]]
["title_main","Text",{"content":"耳机播控","fontSize":12,"fontWeight":700,"width":"matchParent","maxLines":1,"textOverflow":"ellipsis"}]
["title_sub","Text",{"content":"FreeBuds Pro 3","fontSize":12,"fontWeight":400,"width":"matchParent","maxLines":1,"textOverflow":"ellipsis"}]
["content_area","Column",{"width":"matchParent","layoutWeight":1,"justifyContent":"start","itemMargin":8},["kv_row_1","kv_row_2"]]
["kv_row_1","Row",{"width":"matchParent","alignItems":"center","itemMargin":8},["label_1","value_1"]]
["label_1","Text",{"content":"左耳电量","design":"body-s","layoutWeight":1,"width":"matchParent","flexShrink":1,"maxLines":1,"textOverflow":"ellipsis"}]
["value_1","Row",{"alignItems":"center","flexShrink":0},["num_1","unit_1"]]
["num_1","Text",{"content":{"path":"/data/earphone/leftBatteryLevel"},"fontSize":12,"fontWeight":500,"maxLines":1}]
["unit_1","Text",{"content":"%","fontSize":12,"fontWeight":500,"maxLines":1}]
["kv_row_2","Row",{"width":"matchParent","alignItems":"center","itemMargin":8},["label_2","value_2"]]
["label_2","Text",{"content":"右耳电量","design":"body-s","layoutWeight":1,"width":"matchParent","flexShrink":1,"maxLines":1,"textOverflow":"ellipsis"}]
["value_2","Row",{"alignItems":"center","flexShrink":0},["num_2","unit_2"]]
["num_2","Text",{"content":{"path":"/data/earphone/rightBatteryLevel"},"fontSize":12,"fontWeight":500,"maxLines":1}]
["unit_2","Text",{"content":"%","fontSize":12,"fontWeight":500,"maxLines":1}]
["action_area","Column",{"width":"matchParent","flexShrink":0},["btn"]]
["btn","Button",{"label":"蓝牙设置","design":"capsule","fontColor":"#FF0A59F7","onClick":[{"call":"clickToDeeplink","args":{"abilityName":"com.huawei.hmos.settings.MainAbility","bundleName":"com.huawei.hmos.settings","intentName":"Settings","uri":"bluetooth"}}]},["btn_icon"]]
["btn_icon","Image",{"src":"resources/base/media/icon_settings.svg","width":24,"height":24,"flexShrink":0,"fillColor":"#FF0A59F7"}]
["/data/earphone/leftBatteryLevel",76]
["/data/earphone/rightBatteryLevel",74]
```
