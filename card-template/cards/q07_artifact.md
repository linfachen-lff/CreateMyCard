```cardspec
{
  "title": "雨天叫车",
  "description": "雨天出行叫车",
  "suggestSize": "2x2",
  "dataBindings": [
    {
      "capabilityId": "ViewWeather",
      "arguments": {
        "districtName": "青浦区",
        "forecastDays": 1
      },
      "writeResultTo": "/data/weather"
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
{"version":"v0.9","updateComponents":{"surfaceId":"surface_card","root":"root","components":[{"id":"root","component":"Column","children":["title_area","content_area","action_area"],"itemMargin":8,"styles":{"width":"matchParent","height":"matchParent","linearGradient":{"angle":145,"colors":[["#FFFFFFFF",0.0],["#FFF0F5FF",0.44],["#FF8EB3FF",1.0]]},"borderRadius":20,"padding":12,"clip":true}},{"id":"title_area","component":"Row","children":["title_col","title_icon"],"itemMargin":4,"styles":{"width":"matchParent","alignItems":"start"}},{"id":"title_col","component":"Column","children":["title_main","title_sub"],"itemMargin":4,"styles":{"width":"matchParent","layoutWeight":1,"flexShrink":1}},{"id":"title_main","component":"Text","content":"雨天叫车","styles":{"fontSize":12,"fontWeight":700,"width":"matchParent","maxLines":1,"textOverflow":"ellipsis"}},{"id":"title_sub","component":"Text","content":"降雨提醒","styles":{"fontSize":12,"fontWeight":400,"width":"matchParent","maxLines":1,"textOverflow":"ellipsis"}},{"id":"title_icon","component":"Image","src":"resources/base/media/drop_1.svg","styles":{"width":20,"height":20,"borderRadius":4,"clip":true,"flexShrink":0,"fillColor":"#E5000000"}},{"id":"content_area","component":"Column","children":["weather_row","humidity_row"],"itemMargin":8,"styles":{"width":"matchParent","layoutWeight":1,"justifyContent":"start"}},{"id":"weather_row","component":"Row","children":["temp_text","condition_text"],"itemMargin":8,"styles":{"width":"matchParent","alignItems":"center"}},{"id":"temp_text","component":"Text","content":"{{ ${/data/weather/current/temperatureText} }}","styles":{"fontSize":14,"fontWeight":700,"maxLines":1,"flexShrink":0}},{"id":"condition_text","component":"Text","content":"{{ ${/data/weather/current/condition} }}","styles":{"fontSize":12,"fontWeight":400,"maxLines":1,"textOverflow":"ellipsis","layoutWeight":1,"width":"matchParent","flexShrink":1}},{"id":"humidity_row","component":"Row","children":["humidity_icon","humidity_value"],"itemMargin":8,"styles":{"width":"matchParent","alignItems":"center"}},{"id":"humidity_icon","component":"Image","src":"resources/base/media/drop_1.svg","styles":{"width":16,"height":16,"flexShrink":0,"fillColor":"#99000000"}},{"id":"humidity_value","component":"Text","content":"{{ ${/data/weather/current/humidityPercent} }}","styles":{"fontSize":12,"fontWeight":500,"maxLines":1,"flexShrink":0}},{"id":"action_area","component":"Column","children":["nav_btn"],"styles":{"width":"matchParent","flexShrink":0}},{"id":"nav_btn","component":"Button","label":"一键导航回家","onClick":[{"call":"clickToIntent","args":{"intentName":"StartNavigate","params":{"dstLocation":{"location":"回家"}}}}],"styles":{"width":"matchParent","height":36,"borderRadius":20,"padding":{"left":8,"top":0,"right":8,"bottom":0},"backgroundColor":"#0C000000","fontColor":"#FF0A59F7","fontSize":14,"fontWeight":500,"maxFontSize":14,"minFontSize":12,"maxLines":1,"flexShrink":0}}]}}
{"version":"v0.9","updateDataModel":{"surfaceId":"surface_card","path":"/","value":{"data":{"weather":{"current":{"temperatureText":"26℃","condition":"小雨","humidityPercent":68}}}}}}
```
```schema
{
  "schemaVersion": "widget-artifact-v2"
}
```
```taskspec
{
  "userQuery": "使用2*2规格，生成雨天叫车小组件。卡片展示当前天气状况（温度、天气现象、湿度），雨天时突出显示降雨提醒，底部显示手机电量，点击可一键导航回家。",
  "size": "2x2",
  "eventCandidates": [
    {
      "id": "event.startNavigate",
      "call": "clickToIntent",
      "args": {
        "intentName": "StartNavigate",
        "params": {
          "dstLocation": {
            "location": "回家"
          }
        }
      }
    }
  ],
  "dataModelSchema": {
    "data": {
      "weather": {
        "current": {
          "temperatureText": {
            "type": "string",
            "description": "适合直接显示的温度文本，例如‘29°C’。",
            "sampleValue": "26℃"
          },
          "condition": {
            "type": "string",
            "description": "当前天气现象，例如‘阴’‘多云’‘小雨’。",
            "sampleValue": "多云"
          },
          "humidityPercent": {
            "type": "number",
            "description": "当前相对湿度百分比。",
            "sampleValue": 68
          }
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
      "id": "asset.drop_1",
      "src": "resources/base/media/drop_1.svg",
      "description": "水滴图标，黑色，图形为圆润水滴轮廓，适用场景：湿度数据展示、饮水提醒、天气降雨信息"
    },
    {
      "id": "asset.location_north_up_right_fill",
      "src": "resources/base/media/location_north_up_right_fill.svg",
      "description": "方向导航实心图标，黑色，图形为指向右上方的导航箭头，适用场景：地图导航、方向指引、路线规划"
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
    "ViewWeather",
    "GetPhoneBatteryInfo"
  ],
  "event": [
    {
      "id": "event.startNavigate",
      "call": "clickToIntent",
      "args": {
        "intentName": "StartNavigate",
        "params": {
          "dstLocation": {
            "location": "回家"
          }
        }
      }
    }
  ],
  "asset": [
    "asset.drop_1",
    "asset.location_north_up_right_fill",
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
      "capabilityId": "ViewWeather",
      "arguments": {
        "districtName": "青浦区",
        "forecastDays": 1
      },
      "writeResultTo": "/data/weather",
      "candidateOutputFields": [
        "/current/temperatureText",
        "/current/condition",
        "/current/humidityPercent"
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
      "capabilityId": "event.startNavigate",
      "action": {
        "call": "clickToIntent",
        "args": {
          "intentName": "StartNavigate",
          "params": {
            "dstLocation": {
              "location": "回家"
            }
          }
        }
      }
    }
  ],
  "candidateAssetIds": [
    "asset.drop_1",
    "asset.location_north_up_right_fill",
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
  "artifactId": "b0961398-8222-44c5-862d-50736a92fa65",
  "createdAt": 1785721158922
}
```
```designcompactdsl
["root","Column",{"width":160,"height":160,"linearGradient":{"angle":145,"colors":[["#FFFFFFFF",0.0],["#FFF0F5FF",0.44],["#FF8EB3FF",1.0]]},"borderRadius":20,"padding":12,"clip":true,"itemMargin":8},["title_area","content_area","action_area"]]
["title_area","Row",{"width":"matchParent","alignItems":"start","itemMargin":4},["title_col","title_icon"]]
["title_col","Column",{"width":"matchParent","layoutWeight":1,"flexShrink":1,"itemMargin":4},["title_main","title_sub"]]
["title_main","Text",{"content":"雨天叫车","fontSize":12,"fontWeight":700,"width":"matchParent","maxLines":1,"textOverflow":"ellipsis"}]
["title_sub","Text",{"content":"降雨提醒","fontSize":12,"fontWeight":400,"width":"matchParent","maxLines":1,"textOverflow":"ellipsis"}]
["title_icon","Image",{"src":"resources/base/media/drop_1.svg","width":20,"height":20,"borderRadius":4,"clip":true,"flexShrink":0,"fillColor":"#E5000000"}]
["content_area","Column",{"width":"matchParent","layoutWeight":1,"justifyContent":"start","itemMargin":8},["weather_row","humidity_row"]]
["weather_row","Row",{"width":"matchParent","alignItems":"center","itemMargin":8},["temp_text","condition_text"]]
["temp_text","Text",{"content":{"path":"/data/weather/current/temperatureText"},"fontSize":14,"fontWeight":700,"maxLines":1,"flexShrink":0}]
["condition_text","Text",{"content":{"path":"/data/weather/current/condition"},"design":"body-s","maxLines":1,"textOverflow":"ellipsis","layoutWeight":1,"width":"matchParent","flexShrink":1}]
["humidity_row","Row",{"width":"matchParent","alignItems":"center","itemMargin":8},["humidity_icon","humidity_value"]]
["humidity_icon","Image",{"src":"resources/base/media/drop_1.svg","width":16,"height":16,"flexShrink":0,"fillColor":"#99000000"}]
["humidity_value","Text",{"content":{"path":"/data/weather/current/humidityPercent"},"fontSize":12,"fontWeight":500,"maxLines":1,"flexShrink":0}]
["action_area","Column",{"width":"matchParent","flexShrink":0},["nav_btn"]]
["nav_btn","Button",{"label":"一键导航回家","design":"capsule","fontColor":"#FF0A59F7","onClick":[{"call":"clickToIntent","args":{"intentName":"StartNavigate","params":{"dstLocation":{"location":"回家"}}}}]},["nav_icon"]]
["nav_icon","Image",{"src":"resources/base/media/location_north_up_right_fill.svg","width":24,"height":24,"flexShrink":0,"fillColor":"#FF0A59F7"}]
["/data/weather/current/temperatureText","26℃"]
["/data/weather/current/condition","小雨"]
["/data/weather/current/humidityPercent",68]
```
