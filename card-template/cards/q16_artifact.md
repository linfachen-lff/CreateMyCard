```cardspec
{
  "title": "耳机播控",
  "description": "耳机状态与音乐播控",
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
{"version":"v0.9","updateComponents":{"surfaceId":"surface_card","root":"root","components":[{"id":"root","component":"Column","children":["title_area","content_area","action_area"],"itemMargin":8,"styles":{"width":"matchParent","height":"matchParent","linearGradient":{"angle":145,"colors":[["#FFFFFFFF",0.0],["#FFF0F5FF",0.44],["#FF8EB3FF",1.0]]},"borderRadius":20,"padding":12,"clip":true}},{"id":"title_area","component":"Row","children":["title_col","title_icon"],"itemMargin":4,"styles":{"width":"matchParent","alignItems":"start"}},{"id":"title_col","component":"Column","children":["title_main","title_sub"],"itemMargin":4,"styles":{"width":"matchParent","layoutWeight":1,"flexShrink":1}},{"id":"title_main","component":"Text","content":"耳机播控","styles":{"fontSize":12,"fontWeight":700,"width":"matchParent","maxLines":1,"textOverflow":"ellipsis"}},{"id":"title_sub","component":"Text","content":"已连接","styles":{"fontSize":12,"fontWeight":400,"width":"matchParent","maxLines":1,"textOverflow":"ellipsis"}},{"id":"title_icon","component":"Image","src":"resources/base/media/earphone_case_16644.svg","styles":{"width":20,"height":20,"borderRadius":4,"clip":true,"flexShrink":0}},{"id":"content_area","component":"Column","children":["battery_row","nav_row"],"itemMargin":8,"styles":{"width":"matchParent","layoutWeight":1,"justifyContent":"end"}},{"id":"battery_row","component":"Row","children":["battery_label","battery_values"],"itemMargin":8,"styles":{"width":"matchParent","alignItems":"center"}},{"id":"battery_label","component":"Text","content":"电量","styles":{"fontSize":12,"fontWeight":400,"layoutWeight":1,"width":"matchParent","flexShrink":1,"maxLines":1,"textOverflow":"ellipsis"}},{"id":"battery_values","component":"Row","children":["left_battery","right_battery"],"itemMargin":4,"styles":{"flexShrink":0}},{"id":"left_battery","component":"Row","children":["left_battery_value","left_battery_unit"],"itemMargin":2,"styles":{"alignItems":"center","flexShrink":0}},{"id":"left_battery_value","component":"Text","content":"{{ ${/data/earphone/leftBatteryLevel} }}","styles":{"fontSize":12,"fontWeight":500,"maxLines":1,"flexShrink":0}},{"id":"left_battery_unit","component":"Text","content":"%","styles":{"fontSize":12,"fontWeight":500,"maxLines":1,"flexShrink":0}},{"id":"right_battery","component":"Row","children":["right_battery_value","right_battery_unit"],"itemMargin":2,"styles":{"alignItems":"center","flexShrink":0}},{"id":"right_battery_value","component":"Text","content":"{{ ${/data/earphone/rightBatteryLevel} }}","styles":{"fontSize":12,"fontWeight":500,"maxLines":1,"flexShrink":0}},{"id":"right_battery_unit","component":"Text","content":"%","styles":{"fontSize":12,"fontWeight":500,"maxLines":1,"flexShrink":0}},{"id":"nav_row","component":"Row","children":["nav_text","nav_icons"],"styles":{"width":"matchParent","alignItems":"center","justifyContent":"spaceBetween"}},{"id":"nav_text","component":"Text","content":"导航到健身房","styles":{"fontSize":12,"fontWeight":400,"layoutWeight":1,"width":"matchParent","flexShrink":1,"maxLines":1,"textOverflow":"ellipsis"}},{"id":"nav_icons","component":"Row","children":["nav_icon","skip_icon","play_icon","speak_icon"],"itemMargin":4,"styles":{"flexShrink":0}},{"id":"nav_icon","component":"Image","src":"resources/base/media/music_fill.svg","styles":{"width":16,"height":16,"flexShrink":0}},{"id":"skip_icon","component":"Image","src":"resources/base/media/play_fill.svg","styles":{"width":16,"height":16,"flexShrink":0}},{"id":"play_icon","component":"Image","src":"resources/base/media/pause_fill.svg","styles":{"width":16,"height":16,"flexShrink":0}},{"id":"speak_icon","component":"Image","src":"resources/base/media/music_fill.svg","styles":{"width":16,"height":16,"flexShrink":0}},{"id":"action_area","component":"Column","children":["nav_btn"],"styles":{"width":"matchParent","flexShrink":0}},{"id":"nav_btn","component":"Button","label":"导航","onClick":[{"call":"clickToDeeplink","args":{"abilityName":"","bundleName":"","intentName":"Music","uri":"hwmusic://com.huawei.hmsapp.music/showMusicList?code=a001&type=4"}}],"styles":{"width":"matchParent","height":36,"borderRadius":20,"padding":{"left":8,"top":0,"right":8,"bottom":0},"backgroundColor":"#0C000000","fontColor":"#FF0A59F7","fontSize":14,"fontWeight":500,"maxFontSize":14,"minFontSize":12,"maxLines":1,"flexShrink":0}}]}}
{"version":"v0.9","updateDataModel":{"surfaceId":"surface_card","path":"/","value":{"data":{"earphone":{"leftBatteryLevel":76,"rightBatteryLevel":74}}}}}
```
```schema
{
  "schemaVersion": "widget-artifact-v2"
}
```
```taskspec
{
  "userQuery": "使用2*2规格，创建耳机播控卡片。左边放巨大音乐音符图标当主体，整体素净加深蓝色柔和渐变背景，右边横排跳转导航、切歌、播报图标及静态导航地址一键导航到健身房。展示耳机连接状态、左右耳电量百分比，提供音乐播放控制和导航入口。",
  "size": "2x2",
  "eventCandidates": [
    {
      "id": "event.open.music.daily",
      "call": "clickToDeeplink",
      "args": {
        "abilityName": "",
        "bundleName": "",
        "intentName": "Music",
        "uri": "hwmusic://com.huawei.hmsapp.music/showMusicList?code=a001&type=4"
      }
    },
    {
      "id": "event.open.settings.bluetooth",
      "call": "clickToDeeplink",
      "args": {
        "abilityName": "com.huawei.hmos.settings.MainAbility",
        "bundleName": "com.huawei.hmos.settings",
        "intentName": "Settings",
        "uri": "bluetooth_entry"
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
        "leftBatteryLevel": {
          "type": "integer",
          "description": "左耳机的当前电量百分比，取值范围 0-100。若未连接则为 0。",
          "sampleValue": 76
        },
        "rightBatteryLevel": {
          "type": "integer",
          "description": "右耳机的当前电量百分比，取值范围 0-100。若未连接则为 0。",
          "sampleValue": 74
        }
      }
    }
  },
  "assetCandidates": [
    {
      "id": "asset.earphone_case_16644",
      "src": "resources/base/media/earphone_case_16644.svg",
      "description": "耳机收纳盒实心图标，黑色，图形为无线耳机充电盒造型，适用场景：蓝牙耳机设备连接、音频设备管理"
    },
    {
      "id": "asset.music_fill",
      "src": "resources/base/media/music_fill.svg",
      "description": "音乐音符实心图标，黑色，图形为双音符连接造型，适用场景：音乐播放卡片、音频功能入口、歌单展示"
    },
    {
      "id": "asset.play_fill",
      "src": "resources/base/media/play_fill.svg",
      "description": "播放实心图标，黑色，图形为向右的实心三角形，适用场景：音乐/视频播放控制、媒体播放器"
    },
    {
      "id": "asset.pause_fill",
      "src": "resources/base/media/pause_fill.svg",
      "description": "暂停实心图标，黑色，图形为两条竖向平行矩形，适用场景：音乐/视频播放暂停控制"
    }
  ]
}
```
```effectivecapabilities
{
  "data": [
    "GetEarphoneInfo"
  ],
  "event": [
    {
      "id": "event.open.music.daily",
      "call": "clickToDeeplink",
      "args": {
        "abilityName": "",
        "bundleName": "",
        "intentName": "Music",
        "uri": "hwmusic://com.huawei.hmsapp.music/showMusicList?code=a001&type=4"
      }
    },
    {
      "id": "event.open.settings.bluetooth",
      "call": "clickToDeeplink",
      "args": {
        "abilityName": "com.huawei.hmos.settings.MainAbility",
        "bundleName": "com.huawei.hmos.settings",
        "intentName": "Settings",
        "uri": "bluetooth_entry"
      }
    }
  ],
  "asset": [
    "asset.earphone_case_16644",
    "asset.music_fill",
    "asset.play_fill",
    "asset.pause_fill"
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
      "capabilityId": "GetEarphoneInfo",
      "arguments": {},
      "writeResultTo": "/data/earphone",
      "candidateOutputFields": [
        "/isConnected",
        "/earphoneName",
        "/batteryLevel",
        "/leftBatteryLevel",
        "/rightBatteryLevel"
      ]
    }
  ],
  "candidateEventCandidates": [
    {
      "capabilityId": "event.open.music.daily",
      "action": {
        "call": "clickToDeeplink",
        "args": {
          "abilityName": "",
          "bundleName": "",
          "intentName": "Music",
          "uri": "hwmusic://com.huawei.hmsapp.music/showMusicList?code=a001&type=4"
        }
      }
    },
    {
      "capabilityId": "event.open.settings.bluetooth",
      "action": {
        "call": "clickToDeeplink",
        "args": {
          "abilityName": "com.huawei.hmos.settings.MainAbility",
          "bundleName": "com.huawei.hmos.settings",
          "intentName": "Settings",
          "uri": "bluetooth_entry"
        }
      }
    }
  ],
  "candidateAssetIds": [
    "asset.earphone_case_16644",
    "asset.music_fill",
    "asset.play_fill",
    "asset.pause_fill"
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
  "artifactId": "cca8fedb-d381-4094-a555-7905e1086ab6",
  "createdAt": 1785721601874
}
```
```designcompactdsl
["root","Column",{"width":160,"height":160,"linearGradient":{"angle":145,"colors":[["#FFFFFFFF",0.0],["#FFF0F5FF",0.44],["#FF8EB3FF",1.0]]},"borderRadius":20,"padding":12,"clip":true,"itemMargin":8},["title_area","content_area","action_area"]]
["title_area","Row",{"width":"matchParent","alignItems":"start","itemMargin":4},["title_col","title_icon"]]
["title_col","Column",{"width":"matchParent","layoutWeight":1,"flexShrink":1,"itemMargin":4},["title_main","title_sub"]]
["title_main","Text",{"content":"耳机播控","fontSize":12,"fontWeight":700,"width":"matchParent","maxLines":1,"textOverflow":"ellipsis"}]
["title_sub","Text",{"content":"已连接","fontSize":12,"fontWeight":400,"width":"matchParent","maxLines":1,"textOverflow":"ellipsis"}]
["title_icon","Image",{"src":"resources/base/media/earphone_case_16644.svg","width":20,"height":20,"borderRadius":4,"clip":true,"flexShrink":0}]
["content_area","Column",{"width":"matchParent","layoutWeight":1,"justifyContent":"end","itemMargin":8},["battery_row","nav_row"]]
["battery_row","Row",{"width":"matchParent","alignItems":"center","itemMargin":8},["battery_label","battery_values"]]
["battery_label","Text",{"content":"电量","design":"body-s","layoutWeight":1,"width":"matchParent","flexShrink":1,"maxLines":1,"textOverflow":"ellipsis"}]
["battery_values","Row",{"flexShrink":0,"itemMargin":4},["left_battery","right_battery"]]
["left_battery","Row",{"alignItems":"center","flexShrink":0,"itemMargin":2},["left_battery_value","left_battery_unit"]]
["left_battery_value","Text",{"content":{"path":"/data/earphone/leftBatteryLevel"},"fontSize":12,"fontWeight":500,"maxLines":1,"flexShrink":0}]
["left_battery_unit","Text",{"content":"%","fontSize":12,"fontWeight":500,"maxLines":1,"flexShrink":0}]
["right_battery","Row",{"alignItems":"center","flexShrink":0,"itemMargin":2},["right_battery_value","right_battery_unit"]]
["right_battery_value","Text",{"content":{"path":"/data/earphone/rightBatteryLevel"},"fontSize":12,"fontWeight":500,"maxLines":1,"flexShrink":0}]
["right_battery_unit","Text",{"content":"%","fontSize":12,"fontWeight":500,"maxLines":1,"flexShrink":0}]
["nav_row","Row",{"width":"matchParent","alignItems":"center","justifyContent":"spaceBetween"},["nav_text","nav_icons"]]
["nav_text","Text",{"content":"导航到健身房","design":"body-s","layoutWeight":1,"width":"matchParent","flexShrink":1,"maxLines":1,"textOverflow":"ellipsis"}]
["nav_icons","Row",{"flexShrink":0,"itemMargin":4},["nav_icon","skip_icon","play_icon","speak_icon"]]
["nav_icon","Image",{"src":"resources/base/media/music_fill.svg","width":16,"height":16,"flexShrink":0}]
["skip_icon","Image",{"src":"resources/base/media/play_fill.svg","width":16,"height":16,"flexShrink":0}]
["play_icon","Image",{"src":"resources/base/media/pause_fill.svg","width":16,"height":16,"flexShrink":0}]
["speak_icon","Image",{"src":"resources/base/media/music_fill.svg","width":16,"height":16,"flexShrink":0}]
["action_area","Column",{"width":"matchParent","flexShrink":0},["nav_btn"]]
["nav_btn","Button",{"label":"导航","design":"capsule","fontColor":"#FF0A59F7","onClick":[{"call":"clickToDeeplink","args":{"abilityName":"","bundleName":"","intentName":"Music","uri":"hwmusic://com.huawei.hmsapp.music/showMusicList?code=a001&type=4"}}]},["nav_btn_icon"]]
["nav_btn_icon","Image",{"src":"resources/base/media/music_fill.svg","width":24,"height":24,"flexShrink":0,"fillColor":"#FF0A59F7"}]
["/data/earphone/leftBatteryLevel",76]
["/data/earphone/rightBatteryLevel",74]
```
