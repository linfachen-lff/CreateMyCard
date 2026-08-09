```cardspec
{
  "title": "内存优化",
  "description": "内存占用速览",
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
    }
  ]
}
```
```genui
{"version":"v0.9","createSurface":{"surfaceId":"surface_card","catalogId":"ohos.a2ui.extended.catalog.form","width":140,"height":140}}
{"version":"v0.9","updateComponents":{"surfaceId":"surface_card","root":"root","components":[{"id":"root","component":"Column","children":["title_area","content_area","action_area"],"itemMargin":8,"styles":{"width":"matchParent","height":"matchParent","linearGradient":{"angle":145,"colors":[["#FFFFFFFF",0.0],["#FFF0F5FF",0.44],["#FF8EB3FF",1.0]]},"borderRadius":20,"padding":12,"clip":true}},{"id":"title_area","component":"Row","children":["title_col","title_icon"],"itemMargin":4,"styles":{"width":"matchParent","alignItems":"start"}},{"id":"title_col","component":"Column","children":["title_main","title_sub"],"itemMargin":4,"styles":{"width":"matchParent","layoutWeight":1,"flexShrink":1}},{"id":"title_main","component":"Text","content":"存储清理","styles":{"fontSize":12,"fontWeight":700,"width":"matchParent","maxLines":1,"textOverflow":"ellipsis"}},{"id":"title_sub","component":"Text","content":"内存占用高","styles":{"fontSize":12,"fontWeight":400,"width":"matchParent","maxLines":1,"textOverflow":"ellipsis"}},{"id":"title_icon","component":"Image","src":"resources/base/media/clean_fill.svg","styles":{"width":20,"height":20,"borderRadius":4,"clip":true,"flexShrink":0,"fillColor":"#E5000000"}},{"id":"content_area","component":"Column","children":["ring_unit","battery_row"],"itemMargin":8,"styles":{"width":"matchParent","layoutWeight":1,"justifyContent":"start"}},{"id":"ring_unit","component":"Column","children":["ring_stack","reading_below"],"itemMargin":4,"styles":{"alignItems":"center","flexShrink":0}},{"id":"ring_stack","component":"Stack","children":["ring_bar","center_icon"],"styles":{"width":44,"height":44,"alignContent":"center","flexShrink":0}},{"id":"ring_bar","component":"Progress","value":"{{ ${/data/systemMem/usagePercent} }}","total":100,"styles":{"type":"ring","strokeWidth":6,"color":"#FFE84026"}},{"id":"center_icon","component":"Image","src":"resources/base/media/clean_fill.svg","styles":{"width":20,"height":20,"flexShrink":0,"fillColor":"#FFE84026"}},{"id":"reading_below","component":"Row","children":["reading_num","reading_unit"],"styles":{"alignItems":"center","flexShrink":0}},{"id":"reading_num","component":"Text","content":"{{ ${/data/systemMem/usagePercent} }}","styles":{"fontSize":12,"fontWeight":700,"maxLines":1,"flexShrink":0}},{"id":"reading_unit","component":"Text","content":"%","styles":{"fontSize":12,"fontWeight":700,"maxLines":1,"flexShrink":0}},{"id":"battery_row","component":"Row","children":["battery_icon","battery_text"],"itemMargin":8,"styles":{"width":"matchParent","alignItems":"center"}},{"id":"battery_icon","component":"Image","src":"resources/base/media/bolt_fill.svg","styles":{"width":14,"height":14,"flexShrink":0,"fillColor":"#99000000"}},{"id":"battery_text","component":"Text","content":"手机 68%","styles":{"fontSize":10,"fontWeight":400,"maxLines":1,"textOverflow":"ellipsis","flexShrink":1}},{"id":"action_area","component":"Column","children":["clean_btn"],"styles":{"width":"matchParent","flexShrink":0}},{"id":"clean_btn","component":"Button","label":"一键清理","onClick":[{"call":"clickToApi","args":{"intentName":"CleanRAMMemory","params":{}}}],"styles":{"width":"matchParent","height":36,"borderRadius":20,"padding":{"left":8,"top":0,"right":8,"bottom":0},"backgroundColor":"#0C000000","fontColor":"#FF0A59F7","fontSize":14,"fontWeight":500,"maxFontSize":14,"minFontSize":12,"maxLines":1,"flexShrink":0}}]}}
{"version":"v0.9","updateDataModel":{"surfaceId":"surface_card","path":"/","value":{"data":{"systemMem":{"usagePercent":43.75}}}}}
```
```schema
{
  "schemaVersion": "widget-artifact-v2"
}
```
```taskspec
{
  "userQuery": "使用2*2规格，建个内存优化卡片。卡片需要展示整机储存空间总容量、已用空间、占用占比，右侧有清理按钮，底部显示手机剩余电量及连接设备电量。使用环形进度条展示内存占用占比，内存占用高时标红告警。",
  "size": "2x2",
  "eventCandidates": [
    {
      "id": "event.clean.memory",
      "call": "clickToApi",
      "args": {
        "intentName": "CleanRAMMemory",
        "params": {}
      }
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
        }
      }
    }
  },
  "assetCandidates": [
    {
      "id": "asset.clean_fill",
      "src": "resources/base/media/clean_fill.svg",
      "description": "清洁实心图标，黑色，图形为清洁工具或净化造型，适用场景：清洁模式、空气净化、家居清洁提醒"
    },
    {
      "id": "asset.bolt_fill",
      "src": "resources/base/media/bolt_fill.svg",
      "description": "闪电实心图标，黑色，图形为竖向闪电符号，适用场景：充电状态、快充指示、用电量展示"
    }
  ]
}
```
```effectivecapabilities
{
  "data": [
    "GetSystemMemInfo",
    "GetPhoneBatteryInfo"
  ],
  "event": [
    {
      "id": "event.clean.memory",
      "call": "clickToApi",
      "args": {
        "intentName": "CleanRAMMemory",
        "params": {}
      }
    }
  ],
  "asset": [
    "asset.clean_fill",
    "asset.bolt_fill"
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
        "/chargingStatusDesc"
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
    }
  ],
  "candidateAssetIds": [
    "asset.clean_fill",
    "asset.bolt_fill"
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
  "artifactId": "9fa02eb2-5dde-4cdd-9802-ad0ad8504754",
  "createdAt": 1785721114930
}
```
```designcompactdsl
["root","Column",{"width":160,"height":160,"linearGradient":{"angle":145,"colors":[["#FFFFFFFF",0.0],["#FFF0F5FF",0.44],["#FF8EB3FF",1.0]]},"borderRadius":20,"padding":12,"clip":true,"itemMargin":8},["title_area","content_area","action_area"]]
["title_area","Row",{"width":"matchParent","alignItems":"start","itemMargin":4},["title_col","title_icon"]]
["title_col","Column",{"width":"matchParent","layoutWeight":1,"flexShrink":1,"itemMargin":4},["title_main","title_sub"]]
["title_main","Text",{"content":"存储清理","fontSize":12,"fontWeight":700,"width":"matchParent","maxLines":1,"textOverflow":"ellipsis"}]
["title_sub","Text",{"content":"内存占用高","fontSize":12,"fontWeight":400,"width":"matchParent","maxLines":1,"textOverflow":"ellipsis"}]
["title_icon","Image",{"src":"resources/base/media/clean_fill.svg","width":20,"height":20,"borderRadius":4,"clip":true,"flexShrink":0,"fillColor":"#E5000000"}]
["content_area","Column",{"width":"matchParent","layoutWeight":1,"justifyContent":"start","itemMargin":8},["ring_unit","battery_row"]]
["ring_unit","Column",{"itemMargin":4,"alignItems":"center","flexShrink":0},["ring_stack","reading_below"]]
["ring_stack","Stack",{"width":44,"height":44,"alignContent":"center","flexShrink":0},["ring_bar","center_icon"]]
["ring_bar","Progress",{"type":"ring","value":{"path":"/data/systemMem/usagePercent"},"total":100,"strokeWidth":6,"color":"#FFE84026"}]
["center_icon","Image",{"src":"resources/base/media/clean_fill.svg","width":20,"height":20,"flexShrink":0,"fillColor":"#FFE84026"}]
["reading_below","Row",{"alignItems":"center","flexShrink":0},["reading_num","reading_unit"]]
["reading_num","Text",{"content":{"path":"/data/systemMem/usagePercent"},"fontSize":12,"fontWeight":700,"maxLines":1,"flexShrink":0}]
["reading_unit","Text",{"content":"%","fontSize":12,"fontWeight":700,"maxLines":1,"flexShrink":0}]
["battery_row","Row",{"width":"matchParent","alignItems":"center","itemMargin":8},["battery_icon","battery_text"]]
["battery_icon","Image",{"src":"resources/base/media/bolt_fill.svg","width":14,"height":14,"flexShrink":0,"fillColor":"#99000000"}]
["battery_text","Text",{"content":"手机 68%","fontSize":10,"fontWeight":400,"maxLines":1,"textOverflow":"ellipsis","flexShrink":1}]
["action_area","Column",{"width":"matchParent","flexShrink":0},["clean_btn"]]
["clean_btn","Button",{"label":"一键清理","design":"capsule","fontColor":"#FF0A59F7","onClick":[{"call":"clickToApi","args":{"intentName":"CleanRAMMemory","params":{}}}]},["clean_icon"]]
["clean_icon","Image",{"src":"resources/base/media/clean_fill.svg","width":24,"height":24,"flexShrink":0,"fillColor":"#FF0A59F7"}]
["/data/systemMem/usagePercent",43.75]
```
