```cardspec
{
  "title": "会议日程",
  "description": "2x2会议日程免打扰卡片：顶部显示会议图标和标题；中间以大字展示下一个会议名称和具体时间；下方以小字标注提前10分钟提醒；底部设置专注模式按钮，点击后进入免打扰状态以辅助开会。",
  "suggestSize": "2x2",
  "dataBindings": [
    {
      "capabilityId": "GetCalendarEvents",
      "arguments": {
        "futureDays": 7
      },
      "writeResultTo": "/data/calendar"
    }
  ]
}
```
```genui
{"version":"v0.9","createSurface":{"surfaceId":"surface_card","catalogId":"ohos.a2ui.extended.catalog.form","width":140,"height":140}}
{"version":"v0.9","updateComponents":{"surfaceId":"surface_card","root":"root","components":[{"id":"root","component":"Column","children":["title_area","content_area","action_area"],"itemMargin":8,"styles":{"width":"matchParent","height":"matchParent","linearGradient":{"angle":145,"colors":[["#FFFFFFFF",0.0],["#FFF0F5FF",0.44],["#FF8EB3FF",1.0]]},"borderRadius":20,"padding":12,"clip":true}},{"id":"title_area","component":"Row","children":["title_col","title_icon"],"itemMargin":4,"styles":{"width":"matchParent","alignItems":"start"}},{"id":"title_col","component":"Column","children":["title_main","title_sub"],"itemMargin":4,"styles":{"width":"matchParent","layoutWeight":1,"flexShrink":1}},{"id":"title_main","component":"Text","content":"会议日程","styles":{"fontSize":12,"fontWeight":700,"width":"matchParent","maxLines":1,"textOverflow":"ellipsis"}},{"id":"title_sub","component":"Text","content":"提前10分钟提醒","styles":{"fontSize":12,"fontWeight":400,"width":"matchParent","maxLines":1,"textOverflow":"ellipsis"}},{"id":"title_icon","component":"Image","src":"resources/base/media/calendar_fill.svg","styles":{"width":20,"height":20,"borderRadius":4,"clip":true,"flexShrink":0}},{"id":"content_area","component":"Column","children":["meeting_name","meeting_time"],"itemMargin":4,"styles":{"width":"matchParent","layoutWeight":1,"justifyContent":"end"}},{"id":"meeting_name","component":"Text","content":"{{ ${/data/calendar/events/0/title} }}","styles":{"fontSize":20,"fontWeight":700,"maxLines":1,"textOverflow":"ellipsis","width":"matchParent"}},{"id":"meeting_time","component":"Row","children":["time_start","time_sep","time_end"],"itemMargin":2,"styles":{"width":"matchParent","alignItems":"center"}},{"id":"time_start","component":"Text","content":"{{ ${/data/calendar/events/0/dtStart} }}","styles":{"fontSize":12,"fontWeight":500,"maxLines":1}},{"id":"time_sep","component":"Text","content":"–","styles":{"fontSize":12,"fontWeight":500,"maxLines":1}},{"id":"time_end","component":"Text","content":"{{ ${/data/calendar/events/0/dtEnd} }}","styles":{"fontSize":12,"fontWeight":500,"maxLines":1}},{"id":"action_area","component":"Column","children":["dnd_btn"],"styles":{"width":"matchParent","flexShrink":0}},{"id":"dnd_btn","component":"Button","label":"专注模式","onClick":[{"call":"clickToDeeplink","args":{"abilityName":"com.huawei.hmos.settings.MainAbility","bundleName":"com.huawei.hmos.settings","intentName":"Settings","uri":"intelligent_scene_entry"}}],"styles":{"width":"matchParent","height":36,"borderRadius":20,"padding":{"left":8,"top":0,"right":8,"bottom":0},"backgroundColor":"#0C000000","fontColor":"#FF0A59F7","fontSize":14,"fontWeight":500,"maxFontSize":14,"minFontSize":12,"maxLines":1,"flexShrink":0}}]}}
{"version":"v0.9","updateDataModel":{"surfaceId":"surface_card","path":"/","value":{"data":{"calendar":{"events":[{"title":"产品评审","dtStart":"09:30","dtEnd":"10:30"}]}}}}}
```
```schema
{
  "schemaVersion": "widget-artifact-v2"
}
```
```taskspec
{
  "userQuery": "使用2*2规格，做个会议日程免打扰卡片。卡片顶部显示会议图标和标题；中间以大字展示下一个会议名称和具体时间；下方以小字标注提前10分钟提醒；底部设置专注模式按钮，点击后进入免打扰状态以辅助开会。",
  "size": "2x2",
  "eventCandidates": [
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
      "id": "event.enter.meeting",
      "call": "clickToApi",
      "args": {
        "intentName": "EnterMeeting",
        "params": {}
      }
    }
  ],
  "dataModelSchema": {
    "data": {
      "calendar": {
        "events": [
          {
            "title": {
              "type": "string",
              "description": "日程标题，例如‘会议’、‘咪咕视频《西班牙 VS 奥地利》’。",
              "sampleValue": "产品评审"
            },
            "dtStart": {
              "type": "string",
              "description": "格式化后的日程开始时间短文本，如 '03:00'，若为全天日程可能为特殊标记。",
              "sampleValue": "09:30"
            },
            "dtEnd": {
              "type": "string",
              "description": "格式化后的日程结束时间短文本，如 '05:00'。",
              "sampleValue": "10:30"
            },
            "eventLocation": {
              "type": "string",
              "description": "日程的具体地点描述，若未填写则为空字符串。",
              "sampleValue": "A区会议室"
            },
            "startDate": {
              "type": "string",
              "description": "日程开始日期格式化文本，例如 '07-03'。",
              "sampleValue": "07-15"
            },
            "countdownDays": {
              "type": "integer",
              "description": "纯数字的倒数日天数。0代表今天发生（或已发生），正整数代表距离日程开始还有多少天。",
              "sampleValue": 0
            }
          }
        ]
      }
    }
  },
  "assetCandidates": [
    {
      "id": "asset.calendar_fill",
      "src": "resources/base/media/calendar_fill.svg",
      "description": "日历实心图标，黑色，图形为带格线的日历本造型，适用场景：日程管理、日历事件查看、当日安排"
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
    "GetCalendarEvents"
  ],
  "event": [
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
      "id": "event.enter.meeting",
      "call": "clickToApi",
      "args": {
        "intentName": "EnterMeeting",
        "params": {}
      }
    }
  ],
  "asset": [
    "asset.calendar_fill",
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
      "capabilityId": "GetCalendarEvents",
      "arguments": {
        "futureDays": 7
      },
      "writeResultTo": "/data/calendar",
      "candidateOutputFields": [
        "/events/0/title",
        "/events/0/dtStart",
        "/events/0/dtEnd",
        "/events/0/eventLocation",
        "/events/0/remindTime",
        "/events/0/startDate",
        "/events/0/countdownDays"
      ]
    }
  ],
  "candidateEventCandidates": [
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
      "capabilityId": "event.enter.meeting",
      "action": {
        "call": "clickToApi",
        "args": {
          "intentName": "EnterMeeting",
          "params": {}
        }
      }
    }
  ],
  "candidateAssetIds": [
    "asset.calendar_fill",
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
  "artifactId": "78fa4eb2-a6b7-4a76-bb12-088860be2d16",
  "createdAt": 1785721508306
}
```
```designcompactdsl
["root","Column",{"width":160,"height":160,"linearGradient":{"angle":145,"colors":[["#FFFFFFFF",0.0],["#FFF0F5FF",0.44],["#FF8EB3FF",1.0]]},"borderRadius":20,"padding":12,"clip":true,"itemMargin":8},["title_area","content_area","action_area"]]
["title_area","Row",{"width":"matchParent","alignItems":"start","itemMargin":4},["title_col","title_icon"]]
["title_col","Column",{"width":"matchParent","layoutWeight":1,"flexShrink":1,"itemMargin":4},["title_main","title_sub"]]
["title_main","Text",{"content":"会议日程","fontSize":12,"fontWeight":700,"width":"matchParent","maxLines":1,"textOverflow":"ellipsis"}]
["title_sub","Text",{"content":"提前10分钟提醒","fontSize":12,"fontWeight":400,"width":"matchParent","maxLines":1,"textOverflow":"ellipsis"}]
["title_icon","Image",{"src":"resources/base/media/calendar_fill.svg","width":20,"height":20,"borderRadius":4,"clip":true,"flexShrink":0}]
["content_area","Column",{"width":"matchParent","layoutWeight":1,"justifyContent":"end","itemMargin":4},["meeting_name","meeting_time"]]
["meeting_name","Text",{"content":{"path":"/data/calendar/events/0/title"},"design":"title-s","maxLines":1,"textOverflow":"ellipsis","width":"matchParent"}]
["meeting_time","Row",{"width":"matchParent","alignItems":"center","itemMargin":2},["time_start","time_sep","time_end"]]
["time_start","Text",{"content":{"path":"/data/calendar/events/0/dtStart"},"fontSize":12,"fontWeight":500,"maxLines":1}]
["time_sep","Text",{"content":"–","fontSize":12,"fontWeight":500,"maxLines":1}]
["time_end","Text",{"content":{"path":"/data/calendar/events/0/dtEnd"},"fontSize":12,"fontWeight":500,"maxLines":1}]
["action_area","Column",{"width":"matchParent","flexShrink":0},["dnd_btn"]]
["dnd_btn","Button",{"label":"专注模式","design":"capsule","fontColor":"#FF0A59F7","onClick":[{"call":"clickToDeeplink","args":{"abilityName":"com.huawei.hmos.settings.MainAbility","bundleName":"com.huawei.hmos.settings","intentName":"Settings","uri":"intelligent_scene_entry"}}]},["dnd_icon"]]
["dnd_icon","Image",{"src":"resources/base/media/bell_slash_fill.svg","width":24,"height":24,"flexShrink":0,"fillColor":"#FF0A59F7"}]
["/data/calendar/events/0/title","产品评审"]
["/data/calendar/events/0/dtStart","09:30"]
["/data/calendar/events/0/dtEnd","10:30"]
```
