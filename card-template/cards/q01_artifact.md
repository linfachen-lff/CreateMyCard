```cardspec
{
  "title": "上海天气",
  "description": "上海今日天气",
  "suggestSize": "2x2",
  "dataBindings": [
    {
      "capabilityId": "ViewWeather",
      "arguments": {
        "districtName": "上海",
        "forecastDays": 1
      },
      "writeResultTo": "/data/weather"
    }
  ]
}
```
```genui
{"version":"v0.9","createSurface":{"surfaceId":"surface_card","catalogId":"ohos.a2ui.extended.catalog.form","width":140,"height":140}}
{"version":"v0.9","updateComponents":{"surfaceId":"surface_card","root":"root","components":[{"id":"root","component":"Column","children":["title_area","content_area","action_area"],"itemMargin":8,"styles":{"width":"matchParent","height":"matchParent","linearGradient":{"angle":145,"colors":[["#FFFFFFFF",0.0],["#FFF0F5FF",0.44],["#FF8EB3FF",1.0]]},"borderRadius":20,"padding":12,"clip":true}},{"id":"title_area","component":"Row","children":["title_col"],"itemMargin":4,"styles":{"width":"matchParent","alignItems":"start"}},{"id":"title_col","component":"Column","children":["title_main","title_sub"],"itemMargin":4,"styles":{"width":"matchParent","layoutWeight":1,"flexShrink":1}},{"id":"title_main","component":"Text","content":"上海天气","styles":{"fontSize":12,"fontWeight":700,"width":"matchParent","maxLines":1,"textOverflow":"ellipsis"}},{"id":"title_sub","component":"Text","content":"今日","styles":{"fontSize":12,"fontWeight":400,"width":"matchParent","maxLines":1,"textOverflow":"ellipsis"}},{"id":"content_area","component":"Column","children":["kv_row_1","kv_row_2"],"itemMargin":8,"styles":{"width":"matchParent","layoutWeight":1,"justifyContent":"start"}},{"id":"kv_row_1","component":"Row","children":["label_1","value_1"],"itemMargin":8,"styles":{"width":"matchParent","alignItems":"center"}},{"id":"label_1","component":"Text","content":"当前","styles":{"fontSize":12,"fontWeight":400,"layoutWeight":1,"width":"matchParent","flexShrink":1,"maxLines":1,"textOverflow":"ellipsis"}},{"id":"value_1","component":"Text","content":"{{ ${/data/weather/current/temperatureText} }}","styles":{"fontSize":12,"fontWeight":500,"flexShrink":0,"textAlign":"end","maxLines":1}},{"id":"kv_row_2","component":"Row","children":["label_2","value_2"],"itemMargin":8,"styles":{"width":"matchParent","alignItems":"center"}},{"id":"label_2","component":"Text","content":"体感","styles":{"fontSize":12,"fontWeight":400,"layoutWeight":1,"width":"matchParent","flexShrink":1,"maxLines":1,"textOverflow":"ellipsis"}},{"id":"value_2","component":"Row","children":["value_2_num","value_2_unit"],"itemMargin":0,"styles":{"flexShrink":0,"alignItems":"center"}},{"id":"value_2_num","component":"Text","content":"{{ ${/data/weather/current/feelsLikeC} }}","styles":{"fontSize":12,"fontWeight":500,"maxLines":1}},{"id":"value_2_unit","component":"Text","content":"°C","styles":{"fontSize":12,"fontWeight":500,"maxLines":1}},{"id":"action_area","component":"Column","children":["detail_btn"],"styles":{"width":"matchParent","flexShrink":0}},{"id":"detail_btn","component":"Button","label":"查看详情","onClick":[{"call":"clickToDeeplink","args":{"abilityName":"","bundleName":"","intentName":"Weather_CityCode","uri":"hww://www.huawei.com/totemweather?enterType=share&cityCode="}}],"styles":{"width":"matchParent","height":36,"borderRadius":20,"padding":{"left":8,"top":0,"right":8,"bottom":0},"backgroundColor":"#0C000000","fontColor":"#FF0A59F7","fontSize":14,"fontWeight":500,"maxFontSize":14,"minFontSize":12,"maxLines":1,"flexShrink":0}}]}}
{"version":"v0.9","updateDataModel":{"surfaceId":"surface_card","path":"/","value":{"data":{"weather":{"current":{"temperatureText":"26℃","feelsLikeC":27}}}}}}
```
```schema
{
  "schemaVersion": "widget-artifact-v2"
}
```
```taskspec
{
  "userQuery": "使用2*2规格，创建一张包含上海今日天气信息的小卡片，展示上海当前温度、天气状况、体感温度、湿度、空气质量、风力、紫外线、预警信息，以及今日温度范围和降雨概率。极端天气时预警信息标红提醒。点击可跳转到天气App查看详情。",
  "size": "2x2",
  "eventCandidates": [
    {
      "id": "event.open.weather",
      "call": "clickToDeeplink",
      "args": {
        "abilityName": "",
        "bundleName": "",
        "intentName": "Weather_CityCode",
        "uri": "hww://www.huawei.com/totemweather?enterType=share&cityCode="
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
          },
          "prefectureName": {
            "type": "string",
            "description": "城市名称",
            "sampleValue": "上海市"
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
          },
          "alertLevel": {
            "type": "string",
            "description": "预警信息。",
            "sampleValue": "无预警"
          },
          "coldLevel": {
            "type": "string",
            "description": "感冒指数。",
            "sampleValue": "较低"
          }
        },
        "daily": [
          {
            "date": {
              "type": "string",
              "description": "预报日期，来源于 day_time。",
              "sampleValue": "2026-07-15"
            },
            "weekday": {
              "type": "string",
              "description": "星期文本，例如‘星期日’。",
              "sampleValue": "星期三"
            },
            "condition": {
              "type": "string",
              "description": "白天天气现象，来源于weather_icon。",
              "sampleValue": "多云"
            },
            "temperatureRangeText": {
              "type": "string",
              "description": "适合直接显示的温度范围，例如‘24° / 32°’。",
              "sampleValue": "24℃ / 31℃"
            },
            "rainProbabilityPercent": {
              "type": "string",
              "description": "白天降雨概率百分比。如：73%",
              "sampleValue": "20%"
            },
            "airQuality": {
              "type": "string",
              "description": "当天空气质量等级。",
              "sampleValue": "良"
            },
            "uvIndex": {
              "type": "string",
              "description": "当天紫外线等级。",
              "sampleValue": "中等"
            }
          }
        ]
      }
    }
  },
  "assetCandidates": []
}
```
```effectivecapabilities
{
  "data": [
    "ViewWeather"
  ],
  "event": [
    {
      "id": "event.open.weather",
      "call": "clickToDeeplink",
      "args": {
        "abilityName": "",
        "bundleName": "",
        "intentName": "Weather_CityCode",
        "uri": "hww://www.huawei.com/totemweather?enterType=share&cityCode="
      }
    }
  ],
  "asset": []
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
        "districtName": "上海",
        "forecastDays": 1
      },
      "writeResultTo": "/data/weather",
      "candidateOutputFields": [
        "/location/districtName",
        "/location/prefectureName",
        "/current/temperatureText",
        "/current/condition",
        "/current/feelsLikeC",
        "/current/humidityPercent",
        "/current/airQuality",
        "/current/windDirection",
        "/current/windLevel",
        "/current/uvIndex",
        "/current/alertLevel",
        "/current/coldLevel",
        "/daily/0/date",
        "/daily/0/weekday",
        "/daily/0/condition",
        "/daily/0/temperatureRangeText",
        "/daily/0/rainProbabilityPercent",
        "/daily/0/airQuality",
        "/daily/0/uvIndex"
      ]
    }
  ],
  "candidateEventCandidates": [
    {
      "capabilityId": "event.open.weather",
      "action": {
        "call": "clickToDeeplink",
        "args": {
          "abilityName": "",
          "bundleName": "",
          "intentName": "Weather_CityCode",
          "uri": "hww://www.huawei.com/totemweather?enterType=share&cityCode="
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
  "artifactId": "b606267b-ca50-4ae8-ae99-a959f67b1d99",
  "createdAt": 1785720865058
}
```
```designcompactdsl
["root","Column",{"width":160,"height":160,"linearGradient":{"angle":145,"colors":[["#FFFFFFFF",0.0],["#FFF0F5FF",0.44],["#FF8EB3FF",1.0]]},"borderRadius":20,"padding":12,"clip":true,"itemMargin":8},["title_area","content_area","action_area"]]
["title_area","Row",{"width":"matchParent","alignItems":"start","itemMargin":4},["title_col"]]
["title_col","Column",{"width":"matchParent","layoutWeight":1,"flexShrink":1,"itemMargin":4},["title_main","title_sub"]]
["title_main","Text",{"content":"上海天气","fontSize":12,"fontWeight":700,"width":"matchParent","maxLines":1,"textOverflow":"ellipsis"}]
["title_sub","Text",{"content":"今日","fontSize":12,"fontWeight":400,"width":"matchParent","maxLines":1,"textOverflow":"ellipsis"}]
["content_area","Column",{"width":"matchParent","layoutWeight":1,"justifyContent":"start","itemMargin":8},["kv_row_1","kv_row_2"]]
["kv_row_1","Row",{"width":"matchParent","alignItems":"center","itemMargin":8},["label_1","value_1"]]
["label_1","Text",{"content":"当前","design":"body-s","layoutWeight":1,"width":"matchParent","flexShrink":1,"maxLines":1,"textOverflow":"ellipsis"}]
["value_1","Text",{"content":{"path":"/data/weather/current/temperatureText"},"fontSize":12,"fontWeight":500,"flexShrink":0,"textAlign":"end","maxLines":1}]
["kv_row_2","Row",{"width":"matchParent","alignItems":"center","itemMargin":8},["label_2","value_2"]]
["label_2","Text",{"content":"体感","design":"body-s","layoutWeight":1,"width":"matchParent","flexShrink":1,"maxLines":1,"textOverflow":"ellipsis"}]
["value_2","Row",{"flexShrink":0,"alignItems":"center","itemMargin":0},["value_2_num","value_2_unit"]]
["value_2_num","Text",{"content":{"path":"/data/weather/current/feelsLikeC"},"fontSize":12,"fontWeight":500,"maxLines":1}]
["value_2_unit","Text",{"content":"°C","fontSize":12,"fontWeight":500,"maxLines":1}]
["action_area","Column",{"width":"matchParent","flexShrink":0},["detail_btn"]]
["detail_btn","Button",{"label":"查看详情","design":"capsule","onClick":[{"call":"clickToDeeplink","args":{"abilityName":"","bundleName":"","intentName":"Weather_CityCode","uri":"hww://www.huawei.com/totemweather?enterType=share&cityCode="}}]}]
["/data/weather/current/temperatureText","26℃"]
["/data/weather/current/feelsLikeC",27]
```
