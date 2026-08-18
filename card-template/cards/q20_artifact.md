```cardspec
{
  "title": "深圳天气",
  "description": "深圳天气速览",
  "suggestSize": "2x2",
  "dataBindings": [
    {
      "capabilityId": "ViewWeather",
      "arguments": {
        "districtName": "深圳",
        "forecastDays": 1
      },
      "writeResultTo": "/data/weather"
    }
  ]
}
```
```genui
{"version":"v0.9","createSurface":{"surfaceId":"surface_card","catalogId":"ohos.a2ui.extended.catalog.form","width":140,"height":140}}
{"version":"v0.9","updateComponents":{"surfaceId":"surface_card","root":"root","components":[{"id":"root","component":"Column","children":["title_area","content_area","action_area"],"itemMargin":8,"styles":{"width":"matchParent","height":"matchParent","linearGradient":{"angle":145,"colors":[["#FFFFFFFF",0.0],["#FFF0F5FF",0.44],["#FF8EB3FF",1.0]]},"borderRadius":20,"padding":12,"clip":true}},{"id":"title_area","component":"Row","children":["title_col","icon"],"itemMargin":4,"styles":{"width":"matchParent","alignItems":"start"}},{"id":"title_col","component":"Column","children":["title_main","title_sub"],"itemMargin":4,"styles":{"width":"matchParent","layoutWeight":1,"flexShrink":1}},{"id":"title_main","component":"Text","content":"深圳天气","styles":{"fontSize":12,"fontWeight":700,"width":"matchParent","maxLines":1,"textOverflow":"ellipsis"}},{"id":"title_sub","component":"Text","content":"多云","styles":{"fontSize":12,"fontWeight":400,"width":"matchParent","maxLines":1,"textOverflow":"ellipsis"}},{"id":"icon","component":"Image","src":"resources/base/media/sun_max.svg","styles":{"width":20,"height":20,"borderRadius":4,"clip":true,"flexShrink":0}},{"id":"content_area","component":"Column","children":["temp_row","detail_row"],"itemMargin":4,"styles":{"width":"matchParent","layoutWeight":1,"justifyContent":"start"}},{"id":"temp_row","component":"Row","children":["temp_value","temp_unit"],"itemMargin":8,"styles":{"width":"matchParent","alignItems":"end"}},{"id":"temp_value","component":"Text","content":"{{ ${/data/weather/current/temperatureText} }}","styles":{"fontSize":30,"fontWeight":700,"height":32,"maxLines":1,"flexShrink":0}},{"id":"temp_unit","component":"Text","content":"","styles":{"fontSize":12,"fontWeight":400,"maxLines":1,"flexShrink":0}},{"id":"detail_row","component":"Row","children":["feels_like","humidity"],"styles":{"width":"matchParent","alignItems":"center","justifyContent":"spaceBetween"}},{"id":"feels_like","component":"Row","children":["feels_icon","feels_value","feels_unit"],"itemMargin":2,"styles":{"alignItems":"center","flexShrink":0}},{"id":"feels_icon","component":"Image","src":"resources/base/media/thermometer_sun_fill.svg","styles":{"width":14,"height":14,"flexShrink":0}},{"id":"feels_value","component":"Text","content":"{{ ${/data/weather/current/feelsLikeC} }}","styles":{"fontSize":12,"fontWeight":500,"maxLines":1,"flexShrink":0}},{"id":"feels_unit","component":"Text","content":"°","styles":{"fontSize":12,"fontWeight":500,"maxLines":1,"flexShrink":0}},{"id":"humidity","component":"Row","children":["humidity_icon","humidity_value","humidity_unit"],"itemMargin":2,"styles":{"alignItems":"center","flexShrink":0}},{"id":"humidity_icon","component":"Image","src":"resources/base/media/drop_1.svg","styles":{"width":14,"height":14,"flexShrink":0}},{"id":"humidity_value","component":"Text","content":"{{ ${/data/weather/current/humidityPercent} }}","styles":{"fontSize":12,"fontWeight":500,"maxLines":1,"flexShrink":0}},{"id":"humidity_unit","component":"Text","content":"%","styles":{"fontSize":12,"fontWeight":500,"maxLines":1,"flexShrink":0}},{"id":"action_area","component":"Column","children":["call_btn"],"styles":{"width":"matchParent","flexShrink":0}},{"id":"call_btn","component":"Button","label":"拨打电话","onClick":[{"call":"clickToApi","args":{"intentName":"CallPhone","params":{"phoneNumber":"","relationship":"父母"}}}],"styles":{"width":"matchParent","height":36,"borderRadius":20,"padding":{"left":8,"top":0,"right":8,"bottom":0},"backgroundColor":"#0C000000","fontColor":"#FF0A59F7","fontSize":14,"fontWeight":500,"maxFontSize":14,"minFontSize":12,"maxLines":1,"flexShrink":0}}]}}
{"version":"v0.9","updateDataModel":{"surfaceId":"surface_card","path":"/","value":{"data":{"weather":{"current":{"temperatureText":"26℃","feelsLikeC":27,"humidityPercent":68}}}}}}
```
```schema
{
  "schemaVersion": "widget-artifact-v2"
}
```
```taskspec
{
  "userQuery": "使用2*2规格，创建深圳天气卡片，展示深圳当前天气信息，包括温度、天气状况、体感温度、湿度等，极端天气时标红提醒，并集成一键打电话功能",
  "size": "2x2",
  "eventCandidates": [
    {
      "id": "event.call.phone",
      "call": "clickToApi",
      "args": {
        "intentName": "CallPhone",
        "params": {
          "phoneNumber": "",
          "relationship": "父母"
        }
      }
    }
  ],
  "dataModelSchema": {
    "data": {
      "weather": {
        "location": {
          "districtName": {
            "type": "string",
            "description": "区或县名称",
            "sampleValue": "青浦区"
          }
        },
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
          "feelsLikeC": {
            "type": "number",
            "description": "当前体感摄氏温度。",
            "sampleValue": 27
          },
          "humidityPercent": {
            "type": "number",
            "description": "当前相对湿度百分比。",
            "sampleValue": 68
          },
          "alertLevel": {
            "type": "string",
            "description": "预警信息。",
            "sampleValue": "无预警"
          },
          "airQuality": {
            "type": "string",
            "description": "当前空气质量等级，例如‘优’‘良’。",
            "sampleValue": "优"
          },
          "windDirection": {
            "type": "string",
            "description": "当前风向。",
            "sampleValue": "东南风"
          },
          "windLevel": {
            "type": "integer",
            "description": "当前风力等级。",
            "sampleValue": 2
          },
          "uvIndex": {
            "type": "string",
            "description": "当前紫外线等级，例如‘弱’‘中等’‘强’。",
            "sampleValue": "中等"
          }
        }
      }
    }
  },
  "assetCandidates": [
    {
      "id": "asset.sun_max",
      "src": "resources/base/media/sun_max.svg",
      "description": "太阳最大亮度图标，黑色，图形为圆形太阳加多条粗放射线，适用场景：天气晴朗展示、屏幕亮度最大值"
    },
    {
      "id": "asset.drop_1",
      "src": "resources/base/media/drop_1.svg",
      "description": "水滴图标，黑色，图形为圆润水滴轮廓，适用场景：湿度数据展示、饮水提醒、天气降雨信息"
    },
    {
      "id": "asset.thermometer_sun_fill",
      "src": "resources/base/media/thermometer_sun_fill.svg",
      "description": "温度计/太阳组合图标，黑色，图形为温度计右侧叠加太阳造型，适用场景：高温预警、体感指数"
    },
    {
      "id": "asset.phone_fill",
      "src": "resources/base/media/phone_fill.svg",
      "description": "电话实心图标，黑色，图形为经典听筒造型，适用场景：拨打电话、通话功能入口"
    }
  ]
}
```
```effectivecapabilities
{
  "data": [
    "ViewWeather"
  ],
  "event": [
    {
      "id": "event.call.phone",
      "call": "clickToApi",
      "args": {
        "intentName": "CallPhone",
        "params": {
          "phoneNumber": "",
          "relationship": "父母"
        }
      }
    }
  ],
  "asset": [
    "asset.sun_max",
    "asset.drop_1",
    "asset.thermometer_sun_fill",
    "asset.phone_fill"
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
        "districtName": "深圳",
        "forecastDays": 1
      },
      "writeResultTo": "/data/weather",
      "candidateOutputFields": [
        "/location/districtName",
        "/current/temperatureText",
        "/current/condition",
        "/current/feelsLikeC",
        "/current/humidityPercent",
        "/current/alertLevel",
        "/current/airQuality",
        "/current/windDirection",
        "/current/windLevel",
        "/current/uvIndex"
      ]
    }
  ],
  "candidateEventCandidates": [
    {
      "capabilityId": "event.call.phone",
      "action": {
        "call": "clickToApi",
        "args": {
          "intentName": "CallPhone",
          "params": {
            "phoneNumber": "",
            "relationship": "父母"
          }
        }
      }
    }
  ],
  "candidateAssetIds": [
    "asset.sun_max",
    "asset.drop_1",
    "asset.thermometer_sun_fill",
    "asset.phone_fill"
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
  "artifactId": "075e15b7-e980-4aab-9f6e-e2cde4b80742",
  "createdAt": 1785721798325
}
```
```designcompactdsl
["root","Column",{"width":160,"height":160,"linearGradient":{"angle":145,"colors":[["#FFFFFFFF",0.0],["#FFF0F5FF",0.44],["#FF8EB3FF",1.0]]},"borderRadius":20,"padding":12,"clip":true,"itemMargin":8},["title_area","content_area","action_area"]]
["title_area","Row",{"width":"matchParent","alignItems":"start","itemMargin":4},["title_col","icon"]]
["title_col","Column",{"width":"matchParent","layoutWeight":1,"flexShrink":1,"itemMargin":4},["title_main","title_sub"]]
["title_main","Text",{"content":"深圳天气","fontSize":12,"fontWeight":700,"width":"matchParent","maxLines":1,"textOverflow":"ellipsis"}]
["title_sub","Text",{"content":"多云","fontSize":12,"fontWeight":400,"width":"matchParent","maxLines":1,"textOverflow":"ellipsis"}]
["icon","Image",{"src":"resources/base/media/sun_max.svg","width":20,"height":20,"borderRadius":4,"clip":true,"flexShrink":0}]
["content_area","Column",{"width":"matchParent","layoutWeight":1,"justifyContent":"start","itemMargin":4},["temp_row","detail_row"]]
["temp_row","Row",{"width":"matchParent","alignItems":"end","itemMargin":8},["temp_value","temp_unit"]]
["temp_value","Text",{"content":{"path":"/data/weather/current/temperatureText"},"design":"title-l","height":32,"maxLines":1,"flexShrink":0}]
["temp_unit","Text",{"content":"","fontSize":12,"fontWeight":400,"maxLines":1,"flexShrink":0}]
["detail_row","Row",{"width":"matchParent","alignItems":"center","justifyContent":"spaceBetween"},["feels_like","humidity"]]
["feels_like","Row",{"alignItems":"center","itemMargin":2,"flexShrink":0},["feels_icon","feels_value","feels_unit"]]
["feels_icon","Image",{"src":"resources/base/media/thermometer_sun_fill.svg","width":14,"height":14,"flexShrink":0}]
["feels_value","Text",{"content":{"path":"/data/weather/current/feelsLikeC"},"fontSize":12,"fontWeight":500,"maxLines":1,"flexShrink":0}]
["feels_unit","Text",{"content":"°","fontSize":12,"fontWeight":500,"maxLines":1,"flexShrink":0}]
["humidity","Row",{"alignItems":"center","itemMargin":2,"flexShrink":0},["humidity_icon","humidity_value","humidity_unit"]]
["humidity_icon","Image",{"src":"resources/base/media/drop_1.svg","width":14,"height":14,"flexShrink":0}]
["humidity_value","Text",{"content":{"path":"/data/weather/current/humidityPercent"},"fontSize":12,"fontWeight":500,"maxLines":1,"flexShrink":0}]
["humidity_unit","Text",{"content":"%","fontSize":12,"fontWeight":500,"maxLines":1,"flexShrink":0}]
["action_area","Column",{"width":"matchParent","flexShrink":0},["call_btn"]]
["call_btn","Button",{"label":"拨打电话","design":"capsule","fontColor":"#FF0A59F7","onClick":[{"call":"clickToApi","args":{"intentName":"CallPhone","params":{"phoneNumber":"","relationship":"父母"}}}]},["call_icon"]]
["call_icon","Image",{"src":"resources/base/media/phone_fill.svg","width":24,"height":24,"flexShrink":0,"fillColor":"#FF0A59F7"}]
["/data/weather/current/temperatureText","26℃"]
["/data/weather/current/feelsLikeC",27]
["/data/weather/current/humidityPercent",68]
```
