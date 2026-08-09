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
    }
  ]
}
```
```genui
{"version":"v0.9","createSurface":{"surfaceId":"surface_card","catalogId":"ohos.a2ui.extended.catalog.form","width":140,"height":140}}
{"version":"v0.9","updateComponents":{"surfaceId":"surface_card","root":"root","components":[{"id":"root","component":"Column","children":["title_area","content_area","action_area"],"itemMargin":8,"styles":{"width":"matchParent","height":"matchParent","linearGradient":{"angle":145,"colors":[["#FFFFFFFF",0.0],["#FFF0F5FF",0.44],["#FF8EB3FF",1.0]]},"borderRadius":20,"padding":12,"clip":true}},{"id":"title_area","component":"Row","children":["title_col","icon"],"itemMargin":4,"styles":{"width":"matchParent","alignItems":"start"}},{"id":"title_col","component":"Column","children":["title_main","title_sub"],"itemMargin":4,"styles":{"width":"matchParent","layoutWeight":1,"flexShrink":1}},{"id":"title_main","component":"Text","content":"雨天叫车","styles":{"fontSize":12,"fontWeight":700,"width":"matchParent","maxLines":1,"textOverflow":"ellipsis"}},{"id":"title_sub","component":"Text","content":"青浦区","styles":{"fontSize":12,"fontWeight":400,"width":"matchParent","maxLines":1,"textOverflow":"ellipsis"}},{"id":"icon","component":"Image","src":"resources/base/media/drop_1.svg","styles":{"width":20,"height":20,"borderRadius":4,"clip":true,"flexShrink":0,"fillColor":"#E5000000"}},{"id":"content_area","component":"Column","children":["weather_row","prob_row"],"itemMargin":8,"styles":{"width":"matchParent","layoutWeight":1,"justifyContent":"end"}},{"id":"weather_row","component":"Row","children":["weather_icon","weather_text"],"itemMargin":8,"styles":{"width":"matchParent","alignItems":"center"}},{"id":"weather_icon","component":"Image","src":"resources/base/media/drop_1.svg","styles":{"width":16,"height":16,"flexShrink":0,"fillColor":"#99000000"}},{"id":"weather_text","component":"Text","content":"{{ ${/data/weather/current/condition} }}","styles":{"fontSize":12,"fontWeight":500,"maxLines":1,"textOverflow":"ellipsis","flexShrink":1}},{"id":"prob_row","component":"Row","children":["prob_label","prob_value","prob_unit"],"itemMargin":8,"styles":{"width":"matchParent","alignItems":"center"}},{"id":"prob_label","component":"Text","content":"降雨概率","styles":{"fontSize":12,"fontWeight":400,"maxLines":1,"textOverflow":"ellipsis","flexShrink":1}},{"id":"prob_value","component":"Text","content":"75","styles":{"fontSize":12,"fontWeight":700,"flexShrink":0}},{"id":"prob_unit","component":"Text","content":"%","styles":{"fontSize":12,"fontWeight":700,"flexShrink":0}},{"id":"action_area","component":"Column","children":["nav_btn"],"styles":{"width":"matchParent","flexShrink":0}},{"id":"nav_btn","component":"Button","label":"导航回家","onClick":[{"call":"clickToIntent","args":{"intentName":"StartNavigate","params":{"dstLocation":{"location":"回家"}}}}],"styles":{"width":"matchParent","height":36,"borderRadius":20,"padding":{"left":8,"top":0,"right":8,"bottom":0},"backgroundColor":"#0C000000","fontColor":"#FF0A59F7","fontSize":14,"fontWeight":500,"maxFontSize":14,"minFontSize":12,"maxLines":1,"flexShrink":0}}]}}
{"version":"v0.9","updateDataModel":{"surfaceId":"surface_card","path":"/","value":{"data":{"weather":{"current":{"condition":"小雨"}}}}}}
```
```schema
{
  "schemaVersion": "widget-artifact-v2"
}
```
```taskspec
{
  "userQuery": "使用2*2规格，生成雨天叫车小组件。展示当前天气状况和降雨概率，雨天时提醒叫车出行，提供一键导航回家的快捷入口。用户当前位置在上海市青浦区。",
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
          "condition": {
            "type": "string",
            "description": "当前天气现象，例如‘阴’‘多云’‘小雨’。",
            "sampleValue": "多云"
          },
          "temperatureText": {
            "type": "string",
            "description": "适合直接显示的温度文本，例如‘29°C’。",
            "sampleValue": "26℃"
          }
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
      "id": "asset.bus_fill",
      "src": "resources/base/media/bus_fill.svg",
      "description": "公交车实心图标，黑色，图形为正面视角公共汽车轮廓，适用场景：公共交通出行、路线导航、公交到站提醒"
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
    "asset.bus_fill"
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
        "/current/condition",
        "/current/temperatureText",
        "/current/rainProbabilityPercent"
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
    "asset.bus_fill"
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
  "artifactId": "6dd8d6b4-85c7-4d80-8a4e-46a7414a7f7d",
  "createdAt": 1785721690775
}
```
```designcompactdsl
["root","Column",{"width":160,"height":160,"linearGradient":{"angle":145,"colors":[["#FFFFFFFF",0.0],["#FFF0F5FF",0.44],["#FF8EB3FF",1.0]]},"borderRadius":20,"padding":12,"clip":true,"itemMargin":8},["title_area","content_area","action_area"]]
["title_area","Row",{"width":"matchParent","alignItems":"start","itemMargin":4},["title_col","icon"]]
["title_col","Column",{"width":"matchParent","layoutWeight":1,"flexShrink":1,"itemMargin":4},["title_main","title_sub"]]
["title_main","Text",{"content":"雨天叫车","fontSize":12,"fontWeight":700,"width":"matchParent","maxLines":1,"textOverflow":"ellipsis"}]
["title_sub","Text",{"content":"青浦区","fontSize":12,"fontWeight":400,"width":"matchParent","maxLines":1,"textOverflow":"ellipsis"}]
["icon","Image",{"src":"resources/base/media/drop_1.svg","width":20,"height":20,"borderRadius":4,"clip":true,"flexShrink":0,"fillColor":"#E5000000"}]
["content_area","Column",{"width":"matchParent","layoutWeight":1,"justifyContent":"end","itemMargin":8},["weather_row","prob_row"]]
["weather_row","Row",{"width":"matchParent","alignItems":"center","itemMargin":8},["weather_icon","weather_text"]]
["weather_icon","Image",{"src":"resources/base/media/drop_1.svg","width":16,"height":16,"flexShrink":0,"fillColor":"#99000000"}]
["weather_text","Text",{"content":{"path":"/data/weather/current/condition"},"fontSize":12,"fontWeight":500,"maxLines":1,"textOverflow":"ellipsis","flexShrink":1}]
["prob_row","Row",{"width":"matchParent","alignItems":"center","itemMargin":8},["prob_label","prob_value","prob_unit"]]
["prob_label","Text",{"content":"降雨概率","fontSize":12,"fontWeight":400,"maxLines":1,"textOverflow":"ellipsis","flexShrink":1}]
["prob_value","Text",{"content":"75","fontSize":12,"fontWeight":700,"flexShrink":0}]
["prob_unit","Text",{"content":"%","fontSize":12,"fontWeight":700,"flexShrink":0}]
["action_area","Column",{"width":"matchParent","flexShrink":0},["nav_btn"]]
["nav_btn","Button",{"label":"导航回家","design":"capsule","fontColor":"#FF0A59F7","onClick":[{"call":"clickToIntent","args":{"intentName":"StartNavigate","params":{"dstLocation":{"location":"回家"}}}}]},["nav_icon"]]
["nav_icon","Image",{"src":"resources/base/media/location_north_up_right_fill.svg","width":24,"height":24,"flexShrink":0,"fillColor":"#FF0A59F7"}]
["/data/weather/current/condition","小雨"]
```
