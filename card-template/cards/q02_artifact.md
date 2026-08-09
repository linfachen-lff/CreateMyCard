```cardspec
{
  "title": "内存清理",
  "description": "2*2规格内存清理卡片，深色无渐变背景。顶部标题'内存清理'配清除图标(asset.icon_cle",
  "suggestSize": "2x2",
  "dataBindings": [
    {
      "capabilityId": "GetSystemMemInfo",
      "arguments": {},
      "writeResultTo": "/data/systemMem"
    },
    {
      "capabilityId": "GetPhoneBatteryInfo",
      "arguments": {},
      "writeResultTo": "/data/phoneBattery"
    },
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
{"version":"v0.9","updateComponents":{"surfaceId":"surface_card","root":"root","components":[{"id":"root","component":"Column","children":["title_area","content_area","action_area"],"itemMargin":8,"styles":{"width":"matchParent","height":"matchParent","linearGradient":{"angle":145,"colors":[["#FFFFFFFF",0.0],["#FFF0F5FF",0.44],["#FF8EB3FF",1.0]]},"borderRadius":20,"padding":12,"clip":true}},{"id":"title_area","component":"Row","children":["title_col","title_icon"],"itemMargin":4,"styles":{"width":"matchParent","alignItems":"start"}},{"id":"title_col","component":"Column","children":["title_main","title_sub"],"itemMargin":4,"styles":{"width":"matchParent","layoutWeight":1,"flexShrink":1}},{"id":"title_main","component":"Text","content":"内存清理","styles":{"fontSize":12,"fontWeight":700,"width":"matchParent","maxLines":1,"textOverflow":"ellipsis"}},{"id":"title_sub","component":"Text","content":"系统状态","styles":{"fontSize":12,"fontWeight":400,"width":"matchParent","maxLines":1,"textOverflow":"ellipsis"}},{"id":"title_icon","component":"Image","src":"resources/base/media/externaldrive_fill.svg","styles":{"width":20,"height":20,"borderRadius":4,"clip":true,"flexShrink":0,"fillColor":"#E5000000"}},{"id":"content_area","component":"Column","children":["kv_row_1","kv_row_2"],"itemMargin":8,"styles":{"width":"matchParent","layoutWeight":1,"justifyContent":"start"}},{"id":"kv_row_1","component":"Row","children":["label_1","value_1"],"itemMargin":8,"styles":{"width":"matchParent","alignItems":"center"}},{"id":"label_1","component":"Text","content":"可用内存","styles":{"fontSize":12,"fontWeight":400,"layoutWeight":1,"width":"matchParent","flexShrink":1,"maxLines":1,"textOverflow":"ellipsis"}},{"id":"value_1","component":"Text","content":"{{ ${/data/systemMem/availableMemText} }}","styles":{"fontSize":12,"fontWeight":500,"flexShrink":0,"textAlign":"end","maxLines":1}},{"id":"kv_row_2","component":"Row","children":["label_2","value_2"],"itemMargin":8,"styles":{"width":"matchParent","alignItems":"center"}},{"id":"label_2","component":"Text","content":"总内存","styles":{"fontSize":12,"fontWeight":400,"layoutWeight":1,"width":"matchParent","flexShrink":1,"maxLines":1,"textOverflow":"ellipsis"}},{"id":"value_2","component":"Text","content":"{{ ${/data/systemMem/totalMemText} }}","styles":{"fontSize":12,"fontWeight":500,"flexShrink":0,"textAlign":"end","maxLines":1}},{"id":"action_area","component":"Column","children":["clean_btn"],"styles":{"width":"matchParent","flexShrink":0}},{"id":"clean_btn","component":"Button","label":"一键清理","onClick":[{"call":"clickToApi","args":{"intentName":"CleanRAMMemory","params":{}}}],"styles":{"width":"matchParent","height":36,"borderRadius":20,"padding":{"left":8,"top":0,"right":8,"bottom":0},"backgroundColor":"#0C000000","fontColor":"#FF0A59F7","fontSize":14,"fontWeight":500,"maxFontSize":14,"minFontSize":12,"maxLines":1,"flexShrink":0}}]}}
{"version":"v0.9","updateDataModel":{"surfaceId":"surface_card","path":"/","value":{"data":{"systemMem":{"availableMemText":"4.50 GB","totalMemText":"8.00 GB"}}}}}
```
```schema
{
  "schemaVersion": "widget-artifact-v2"
}
```
```taskspec
{
  "userQuery": "使用2*2规格，创建内存清理卡片",
  "size": "2x2",
  "eventCandidates": [
    {
      "id": "event.clean.memory",
      "call": "clickToApi",
      "args": {
        "intentName": "CleanRAMMemory",
        "params": {}
      }
    },
    {
      "id": "event.open.settings.storage",
      "call": "clickToDeeplink",
      "args": {}
    }
  ],
  "dataModelSchema": {
    "data": {
      "systemMem": {
        "totalMemText": {
          "type": "string",
          "description": "系统总内存，格式化后的文本（如 '8.00 GB'）。",
          "sampleValue": "8.00 GB"
        },
        "availableMemText": {
          "type": "string",
          "description": "系统可用于重新分配的可用内存，格式化后的文本（如 '4.50 GB'）。判断系统是否存在内存瓶颈的核心指标。",
          "sampleValue": "4.50 GB"
        },
        "usagePercent": {
          "type": "number",
          "description": "当前系统内存真实占用百分比（计算方式：(总内存-可用内存)/总内存 * 100），取值范围 0-100。",
          "sampleValue": 43.75
        }
      },
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
      },
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
  "assetCandidates": [
    {
      "id": "asset.icon_clear",
      "src": "resources/base/media/icon_clear.svg",
      "description": "清除图标，适用场景：清理无忧"
    },
    {
      "id": "asset.bolt_fill",
      "src": "resources/base/media/bolt_fill.svg",
      "description": "闪电实心图标，黑色，图形为竖向闪电符号，适用场景：充电状态、快充指示、用电量展示"
    },
    {
      "id": "asset.externaldrive_fill",
      "src": "resources/base/media/externaldrive_fill.svg",
      "description": "外置存储设备实心图标，黑色，图形为矩形硬盘盒造型，适用场景：本地存储管理、数据备份、文件传输"
    },
    {
      "id": "asset.icon_earphone",
      "src": "resources/base/media/icon_earphone.svg",
      "description": "耳机图标，适用场景：戴耳机播控"
    },
    {
      "id": "asset.icon_electricity",
      "src": "resources/base/media/icon_electricity.svg",
      "description": "电池图标，适用场景：低电模式"
    }
  ]
}
```
```effectivecapabilities
{
  "data": [
    "GetSystemMemInfo",
    "GetPhoneBatteryInfo",
    "GetEarphoneInfo"
  ],
  "event": [
    {
      "id": "event.clean.memory",
      "call": "clickToApi",
      "args": {
        "intentName": "CleanRAMMemory",
        "params": {}
      }
    },
    {
      "id": "event.open.settings.storage",
      "call": "clickToDeeplink",
      "args": {}
    }
  ],
  "asset": [
    "asset.icon_clear",
    "asset.bolt_fill",
    "asset.externaldrive_fill",
    "asset.icon_earphone",
    "asset.icon_electricity"
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
      "capabilityId": "GetSystemMemInfo",
      "arguments": {},
      "writeResultTo": "/data/systemMem",
      "candidateOutputFields": [
        "/totalMemText",
        "/availableMemText",
        "/usagePercent"
      ]
    },
    {
      "capabilityId": "GetPhoneBatteryInfo",
      "arguments": {},
      "writeResultTo": "/data/phoneBattery",
      "candidateOutputFields": [
        "/batterySOCText",
        "/chargingStatusDesc",
        "/batteryCapacityLevelDesc"
      ]
    },
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
      "capabilityId": "event.clean.memory",
      "action": {
        "call": "clickToApi",
        "args": {
          "intentName": "CleanRAMMemory",
          "params": {}
        }
      }
    },
    {
      "capabilityId": "event.open.settings.storage",
      "action": {
        "call": "clickToDeeplink",
        "args": {}
      }
    }
  ],
  "candidateAssetIds": [
    "asset.icon_clear",
    "asset.bolt_fill",
    "asset.externaldrive_fill",
    "asset.icon_earphone",
    "asset.icon_electricity"
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
  "artifactId": "3a65c34c-a8e0-47e3-9019-8ed1038e237f",
  "createdAt": 1785720906512
}
```
```designcompactdsl
["root","Column",{"width":160,"height":160,"linearGradient":{"angle":145,"colors":[["#FFFFFFFF",0.0],["#FFF0F5FF",0.44],["#FF8EB3FF",1.0]]},"borderRadius":20,"padding":12,"clip":true,"itemMargin":8},["title_area","content_area","action_area"]]
["title_area","Row",{"width":"matchParent","alignItems":"start","itemMargin":4},["title_col","title_icon"]]
["title_col","Column",{"width":"matchParent","layoutWeight":1,"flexShrink":1,"itemMargin":4},["title_main","title_sub"]]
["title_main","Text",{"content":"内存清理","fontSize":12,"fontWeight":700,"width":"matchParent","maxLines":1,"textOverflow":"ellipsis"}]
["title_sub","Text",{"content":"系统状态","fontSize":12,"fontWeight":400,"width":"matchParent","maxLines":1,"textOverflow":"ellipsis"}]
["title_icon","Image",{"src":"resources/base/media/externaldrive_fill.svg","width":20,"height":20,"borderRadius":4,"clip":true,"flexShrink":0,"fillColor":"#E5000000"}]
["content_area","Column",{"width":"matchParent","layoutWeight":1,"justifyContent":"start","itemMargin":8},["kv_row_1","kv_row_2"]]
["kv_row_1","Row",{"width":"matchParent","alignItems":"center","itemMargin":8},["label_1","value_1"]]
["label_1","Text",{"content":"可用内存","design":"body-s","layoutWeight":1,"width":"matchParent","flexShrink":1,"maxLines":1,"textOverflow":"ellipsis"}]
["value_1","Text",{"content":{"path":"/data/systemMem/availableMemText"},"fontSize":12,"fontWeight":500,"flexShrink":0,"textAlign":"end","maxLines":1}]
["kv_row_2","Row",{"width":"matchParent","alignItems":"center","itemMargin":8},["label_2","value_2"]]
["label_2","Text",{"content":"总内存","design":"body-s","layoutWeight":1,"width":"matchParent","flexShrink":1,"maxLines":1,"textOverflow":"ellipsis"}]
["value_2","Text",{"content":{"path":"/data/systemMem/totalMemText"},"fontSize":12,"fontWeight":500,"flexShrink":0,"textAlign":"end","maxLines":1}]
["action_area","Column",{"width":"matchParent","flexShrink":0},["clean_btn"]]
["clean_btn","Button",{"label":"一键清理","design":"capsule","fontColor":"#FF0A59F7","onClick":[{"call":"clickToApi","args":{"intentName":"CleanRAMMemory","params":{}}}]},["clean_icon"]]
["clean_icon","Image",{"src":"resources/base/media/icon_clear.svg","width":24,"height":24,"flexShrink":0,"fillColor":"#FF0A59F7"}]
["/data/systemMem/availableMemText","4.50 GB"]
["/data/systemMem/totalMemText","8.00 GB"]
```
