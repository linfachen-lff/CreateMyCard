# 内容高级组件 UX 与生产契约对齐

## 1. 目的与结论

本文是内容业务高级组件进入 Python 正式服务前的实现门禁。布局高级组件已经先行完成；内容组件必须先同时对齐：

1. `advanced-components-detailed-design.md` 的 ViewModel、变体、字段裁剪、字号、图标和配色；
2. `2X2卡片布局规范.pdf`、`2X4卡片布局规范.pdf` 的尺寸和信息预算；
3. 正式服务 `data_capabilities.json` 的真实输出 Schema；
4. Template 静态展开、安全校验和最终 A2UI 不含 Template 的运行约束。

当前结论：16 个既有业务组件中，8 个数据域可以由正式能力直接或经可信 Selector 生成；6 个组件没有正式
数据能力，只能保留注册和编译能力但不得由第五接口自动候选；Date 可从 Calendar 派生；Workout 的倒计时
变体只能显示能力真实提供的天数。新增 UX 中的“内存清理”不属于 Battery，必须作为独立
`ResourceUsageOverview` 适配，不能继续用 `BatteryOverview.resourceUsage` 混用语义。

## 2. 统一实现边界

### 2.1 标题、内容和动作归属

- 业务标题属于内容组件，例如“下一个日程”“睡眠不足”“设备电量”。不得由通用外壳根据 Query 猜测。
- 独立 Card 标题区是可选 Chrome。业务组件已有明确标题时不得重复渲染同义标题。
- Golden 基线没有独立标题时，允许省略标题区；这不影响业务组件内部 mustShow 字段。
- `PillAction`、`IconAction`、`ActionTile` 只由布局高级组件持有。内容组件只暴露动作可用性和语义，不嵌套按钮。
- 动作存在必须由可信字段决定，例如 `canJoin=true`、有效 URI 或已声明的事件能力；不能仅凭文案生成。

### 2.2 数据和派生值

- 正式输入先由 Python Selector 转为严格 ViewModel，LLM 只选择允许的组件、变体和字段绑定。
- 时间差、比例、状态、号码脱敏、过期判断、天气映射均由 Selector 计算。
- `0` 是合法值，只有 `null`、字段缺失或明确的 availability 状态才表示不可用。
- Fixture 的附加字段不是生产契约。Schema 未声明的限制、超时、距离、标题和第二个设备指标不得进入生产绑定。
- 内容组件必须统一处理 `available/empty/permissionDenied/unsupported/stale/error`，不得用伪值填充空态。

### 2.3 排版和视觉

- 2×2 通常 1～2 个业务组件、最多 1 个主动作、最多 1 个主图表、列表最多 2 项。
- 2×4 通常 2～3 个业务组件、列表最多 3 项；设置矩阵之外通常最多 1 个主动作。
- 普通标题 14fp，可降到 12fp；正文 14fp，可降到 12fp；辅助信息不低于 10fp。
- 单值 Hero 38fp；双值 Hero 30fp；单位 12fp。旧 Template 中的 8/9/11/15/17/19fp 不作为新变体基线。
- 内容组件不能设置根面尺寸、绝对坐标或根面渐变；主业务决定 Palette Scene，支持组件只能使用局部状态色。

### 2.4 兼容策略

- 已存在的 `@1` Template 保留，避免高置信度整卡路径和旧回归用例受影响。
- 第五接口混合路径使用新的版本化业务 Template；注册表显式限定可选变体和真实字段。
- Python 在可信端展开 Template 为基础组件/UI IR/A2UI；端侧协议不得出现 Template 节点。
- 没有正式数据能力的组件可以有确定性编译测试，但自动 Scope Planner 必须对其做 provider gate。

## 3. 逐组件对齐清单

### 3.1 WeatherOverview

- UX 变体：`conditionOnly/current/alert/commute/forecastItem`。
- 正式输入：`ViewWeather.location/current/daily/updatedAt`。
- Selector：映射 condition、风险等级、城市、当前温度；拆分 `daily[0].temperatureRangeText` 为高低温，仅在格式
  可验证时使用；空气质量作为 current 支持字段，不伪装成告警。
- 2×2 current：城市/位置、48/56vp 天气图标、38fp 温度、天气+空气、温度范围组成一个原子内容组件。
- 动作：电话/打车属于布局；饱和天气根面使用白色圆形底托和绿色/橙色主题图标。
- 当前差距：`ux-weather-hero@1` 与 `ux-condition-index@1` 会拆散并重复同一事实，字号也不满足新规范。
- 实现决策：新增 current/commute 版本化 Template；保留 `weather-summary@1` 仅做旧路径兼容。

### 3.2 DateOverview

- UX 变体：`compactDate/dateHero/calendarContext`。
- 正式输入：没有独立 Date provider；只允许从 `GetCalendarEvents.events[].startDate` 派生。完整日期只接受
  `YYYY-MM-DD` / `YYYY/MM/DD`；`MM-DD` 只有在同一 Calendar 输出的 `updatedAt` 含合法四位年份时可用。
- Selector：只输出非空且格式合法的 `date`、`weekday`；不输出 month、year、农历、相对日期或节日。
- 第一层准入：必须有 GetCalendarEvents、可解析的首个事件日期和事件/日程日期意图；2×4 日程组合可把日期
  作为上下文。系统当前日期、月/年/农历/相对日期请求，以及 2×2 未明确请求日期的纯日程请求均不候选。
- 排版：单业务 2×2/2×4 使用 30fp 日期、14fp 星期；多业务 2×2 使用 14fp 日期、12fp 星期的顶部
  紧凑行；多业务 2×4 左侧日期 Hero、右侧日程、底部动作。会议临近时会议时间优先于日期主视觉。
- 实现决策：DateOverview 是受限直接 TerseDSL 节点，只接收 variant/role；可信编译器从 Selector 事实展开，
  不依赖 JSON Template。缺失、空值、类型错误或格式非法时在第一层前关闭候选，并在模型返回后再次拒绝。

### 3.3 ScheduleOverview

- 当前变体：`nextEvent/meetingCompact/meetingExpanded`；`focusContext` 仅在批准专注 Action 存在时启用，
  `agendaList/countdown` 保持禁用。
- 正式输入：只消费 `GetCalendarEvents` 同一个可信首项事件的非空 string `title/dtStart`；非空 string
  `dtEnd` 可拼接 `timeText`，非空 `eventLocation` 为可选 location。不得投影实时状态、分钟倒计时、
  会议号、备注、邀请人、一键服务字段或多条 agenda。
- 第一层准入：provider、首项事实、用户摘要意图和 2x2/2x4 尺寸必须同时成立；明确地点需要 location，
  明确入会/查看/专注需要语义闭环的 TaskSpec 事件候选。模型返回后复用同一确定性校验。
- 排版：会议正文使用 8vp 红橙空心圆点与只覆盖正文的 1vp Divider；Hero 为 20/14/10fp，2x2 Support
  为 14/12/10fp，2x4 Support 为 16/14/10fp。meetingExpanded 缺 location 时降为 meetingCompact。
- 动作与素材：业务组件不持有 Action；布局从批准事件候选注入。来源/时间/地点/Action 图标只能从本轮
  assetCandidates 按语义标签选择，缺失则省略可选图标。
- 实现决策：ScheduleOverview 是受限直接 TerseDSL 节点，可信编译器确定性展开为标准 Terse/A2UI；
  `ux-schedule-overview` JSON 视图树已移除。

### 3.4 TaskOverview

- UX 变体：`summary/nextTask/list/completed/progress`。
- 正式输入：当前正式能力目录没有 Task provider。
- 排版：2×2 优先 summary/nextTask，列表最多 2 项；2×4 最多 3 项。标题 12fp，Metadata 10fp。
- 状态：pending/completed/overdue 必须由可信时间和状态字段得到，完成态不得使用大面积绿色。
- 当前差距：映射到通用 text/status/metric Template，不能保证 mustShow、状态或列表上限。
- 实现决策：建立专用严格契约和确定性编译测试，但 provider 缺失时自动候选关闭。

### 3.5 MemoPreview

- UX 变体：`plain/reminder/updated`。
- 正式输入：当前正式能力目录没有 Memo provider。
- 排版：2×2 标题 1 行、正文 2～3 行、时间 1 行；有动作时正文最多 2 行。Memo 不显示待办勾选态。
- 当前差距：通用 text-stack 无法表达正文裁剪、提醒 Metadata 和 Memo/Task 的语义隔离。
- 实现决策：新增专用 strict Template；provider 缺失时自动候选关闭。

### 3.6 CallOverview

- UX 变体：`missed/latest/log/contactAction`。
- 正式输入：当前正式能力目录没有 Call provider。
- Selector：必须先做号码脱敏、通话时长格式化和 `canCallBack` 判定。
- 排版：2×2 单条通话，右下 IconAction；2×4 最多 3 条。
- 当前差距：通用 action/text Template 会让 LLM 直接生成联系人、号码和回拨可用性。
- 实现决策：新增专用 strict Template；无 provider 时不进入候选。

### 3.7 BatteryOverview

- UX 变体：当前只启用 `normal/charging/low`；`runtime/multiBattery/resourceUsage` 均不属于本组件。
- 正式输入：`GetPhoneBatteryInfo` 同一数据树中的 batterySOC、batterySOCText、
  batteryCapacityLevelDesc、chargingStatusDesc 四字段；SOC 数值与百分比文本必须一致，0% 合法。
- Selector：两项描述必须为非空字符串；只请求健康度、温度、电压、电流、充电器类型、续航、预计充满
  时间或外设电量时禁选。投影不保留其它字段。
- 排版：2×2 单业务为标题—建议—52vp Ring—可选 IconAction；2×4 为左 Ring 右文本；手机+耳机通过
  BluetoothDeviceOverview 组成 PeerPairLayout 的两个对等 Ring。
- 当前差距：`ux-battery-status@1` 字号 8/17fp 且依赖 tipLine1/2/3 这种 fixture 字段。
- 实现决策：使用受限 `BatteryOverview({variant, role, batteryIcon?})` 直接 TerseDSL 构造，由可信编译器
  展开；旧 JSON Template 不进入新选择链。所有图标来自 TaskSpec 素材，省电动作必须有批准事件闭环。

### 3.8 AppUsageOverview

- UX 变体：Registry 声明 `singleApp/dailyLimit/overLimit/topApps`，当前 capability 只启用 `singleApp`。
- 正式输入：同一 `GetAppUsageDuration` 数据树中的非空 string `appUsage.appName`、
  `appUsage.durationText` 和同级 `updatedAt`；用户必须明确指定该应用和当日时长意图。
- Selector：只无损解析小时/分钟，`0分钟` 合法；纯秒或含秒禁选。投影只保留三项原始事实与确定性
  数值/单位片段。总量、多应用、排行、限额、超限、剩余、比例/进度、趋势/历史、分类汇总全部禁选。
- 排版：2×2/2×4 使用同行 30fp 数值与 12fp 单位、12fp 标题、10fp 更新时间；没有可信总量时禁止
  Progress。2×4 使用 Hero+Support，2×2 使用单 Hero。
- 当前差距：新 Golden fixture 的 safeValue/warningValue/total/overtime 不属于正式 Schema。
- 实现决策：`AppUsageOverview({variant, role, appIcon?})` 由可信编译器直接展开，不依赖 JSON Template；
  管控动作只接受用户请求且正式注册的 `event.open.settings.parentControl`，否则使用无动作布局。应用与动作
  图标只从 TaskSpec 素材选择。SystemMode 没有可信状态能力时禁止组合和占位。

### 3.9 ActivityOverview

- UX 变体：`steps/calories/exercise/dailySummary`。
- 正式输入：`GetHealthAndSportSummary` 的 dailySteps、dailyTotalCaloriesText、dailyDistanceText。
- Selector：选择 primaryMetric，只有目标存在时才计算 goalRatio；文本单位不重复拼接。
- 排版：2×2 只能有一个 Hero，其他 1～2 项降为 Support；2×4 Hero+两个 Support，禁止三个大 Ring。
- 当前差距：通用 metric-cluster 不能强制一个主指标，也不能区分目标缺失。
- 实现决策：新增 Activity strict Template，按尺寸限制支持字段数量。

### 3.10 WorkoutOverview

- UX 变体：`planned/ongoing/latest/countdown`。
- 正式输入：健康能力提供最近运动类型、起止时间、时长、热量、心率；`GetCountdownDays` 只提供 countdownDays。
- Selector：健康字段可生成 latest；countdown 只有天数是真值。赛事标题、距离、训练计划必须由另一个正式契约提供。
- 排版：2×2 训练类型或倒计时为唯一 Hero，只保留一个 Support；2×4 最多两个支持项。
- 当前差距：Golden fixture 中 race title、30km 计划不属于 GetCountdownDays Schema。
- 实现决策：实现 latest 和纯天数 countdown；完整赛事卡在能力 Schema 扩展前不得由模型补全。

### 3.11 HeartRateOverview

- UX 变体：`current/average/attention`。
- 正式输入：健康能力只提供最近运动期间 avg/max/min 心率，不是当前静息心率。
- Selector：只能映射为 average/support；没有当前测量值时不得使用 current，状态阈值由可信规则计算。
- 排版：只有真正主对象才使用 38fp bpm；健康组合中为紧凑 Support，测量时间 10fp。
- 当前差距：通用 metric-ring 可能把运动平均心率误标为当前心率。
- 实现决策：先开放 average；current/attention 等待对应实时 provider。

### 3.12 SleepOverview

- UX 变体：`duration/insufficient/schedule/stages`。
- 正式输入：`GetHealthAndSportSummary` 的 `nightSleepDurationText`；可信 `sleepStatus`、严格 `HH:mm`
  入睡/醒来时刻为分别可选的元数据。
- Selector：总时长必须可按小时/分钟无损解析并由服务端归一化，`0分钟` 有效；`insufficient` 只认明确
  不足状态，不按时长推断；`schedule` 仅在 2×4 且两个时刻完整时开放。
- 排版：2×2 双值 30fp/12fp，数值与各自单位 0vp、两组 2vp并底部对齐；2×4 为时长 Hero + 8vp
  圆角的入睡/醒来 Support。无目标/阶段数据时不生成 Ring、Progress、时间轴或阶段条。
- 当前差距：得分、深睡/浅睡/REM、午睡、目标完成率、趋势与建议虽可能存在于 Provider Schema，但未进入
  当前 Sleep 投影；批量效果测试阶段只要总时长准入成立，相关请求可进入候选并降级为 `duration`，不展示或
  补造这些额外指标。状态或作息字段缺失时也只降级，不再整体拒绝。
- 实现决策：使用 `SleepOverview({variant, role, sourceIcon?})` 直接 TerseDSL 构造和确定性 lowering；新链路
  不请求 `ux-sleep-overview@2`，最终 A2UI 不保留高级节点。提醒只使用本轮批准的闹钟 Action。

### 3.13 LocationOverview

- UX 变体：`current/home/pair/commuteContext`。
- 正式输入：没有独立 Location provider；Weather.location 只能作为天气上下文，不能推导当前位置精确坐标。
- Selector：优先人类可读地址；stale 时必须显示“上次位置”；无地址才允许经纬度回退。
- 排版：2×2 通常是 Weather/Schedule Support，不独占 Hero；2×4 pair 才能并列。
- 当前差距：通用 context Template 无法验证坐标、地址来源和 stale。
- 实现决策：实现 strict Template，但仅 Weather 的 city/district 可用于 commuteContext；其他变体关闭自动候选。

### 3.14 SystemModeOverview

- UX 变体：`focus/dnd/audio/combined`。
- 正式输入：当前正式能力目录没有系统模式 provider。
- Selector：audioMode 必须是 ring/vibrate/silent 互斥枚举；focus 和 DND 状态由端侧真实绑定。
- 排版：2×2 一个主要模式+一个动作；2×4 才使用 2～4 项 ActionMatrix。
- 当前差距：通用 status/action Template 容许 LLM 生成默认开关状态。
- 实现决策：建立严格契约和编译测试；provider 缺失时自动候选关闭。

### 3.15 BluetoothDeviceOverview

- UX 变体：`singleDevice/earbuds/multiDevice/mediaControl`。
- 正式输入：`GetEarphoneInfo` 含连接状态、设备名、左右耳/盒电量和充电状态。
- Selector：先检查 isConnected；断开时的 0 不是有效部件电量。连接时真实 0% 仍必须显示。
- 排版：2×2 左右耳最多两个同级微型 Ring，盒子为 Support；2×4 可展示左/右/盒三项。
- 当前差距：`ux-audio-device-status@1` 使用 9/15fp，且多个通用模板可能重复电量。
- 实现决策：新增 earbuds strict Template，把三部件作为同一原子组件；动作仍由布局持有。

### 3.16 SettingsOverview

- UX 变体：`singleToggle/singleValue/group/quickActions`。
- 正式输入：当前正式能力目录没有 Settings provider。
- 数据：Toggle/Radio 的值、enabled、selected 必须来自端侧绑定，LLM 不生成默认值。
- 排版：2×2 一个主设置或两个极简控制；2×4 2～4 项矩阵，同级结构完全一致。
- 当前差距：通用 status/action Template 不具备状态绑定和同组一致性校验。
- 实现决策：建立严格契约和编译测试；provider 缺失时自动候选关闭。

### 3.17 ResourceUsageOverview（Python 适配扩展）

- 设计原因：`GetSystemMemInfo` 和新“内存清理”案例存在真实需求，但 16 个原始组件没有资源使用语义。
- 禁止方案：不得继续把 `resourceUsage` 塞入 BatteryOverview；内存百分比不是电量。
- 正式输入：当前只允许 `memory`，必须从同一 `GetSystemMemInfo` 数据树取得 0..100 的有限 number
  `usagePercent`（0% 合法）及两个可信非空 string `availableMemText/totalMemText`；三项任一不合法即禁选。
- 投影边界：只保留上述三项。`freeMemText` 不可展示；不得生成 used/state/updatedAt，也不得据百分比推断
  内存不足、正常或告警。
- 意图门禁：存储/磁盘、缓存、进程明细、CPU/GPU、swap、趋势、历史曲线以及 freeMemText-only 请求禁选；
  Registry 中的 `storage` 仅为未启用声明。
- 排版：单业务使用 52vp 主 Ring；2×2 与 Battery 使用 PeerPair 的两个 44vp 等权 Ring；2×4 使用
  56:44 的内存 Hero + 电量 Support。Ring 描边 6vp，中心素材 24vp，根圆角 20vp、安全边距 12vp。
- 新 Golden 中的 storageValue=87 和 memoryValue=72 超出当前 Schema，不能作为生产数据来源。
- 实现决策：使用 `ResourceUsageOverview({variant:"memory", role:"hero|peer", icon?})` 直接 TerseDSL 构造，
  不新增或依赖 JSON Template。清理动作只接受批准的 `event.clean.memory`；没有事件即回退无动作布局。

## 4. Provider Gate 汇总

| 组件 | 正式来源 | 首期开放变体 | 暂停变体/原因 |
|---|---|---|---|
| Weather | ViewWeather | current/commute | conditionOnly/alert/forecastItem 尚无独立严格模板 |
| Date | Calendar + 可信时钟 | compactDate/dateHero | calendarContext 的农历/相对日期无来源 |
| Schedule | GetCalendarEvents | nextEvent/meetingCompact/meetingExpanded/focusContext | agendaList/countdown 尚无列表/倒计时严格模板；canJoin 无有效链接时关闭动作 |
| Task | 无 | 无自动候选 | 全部等待 provider |
| Memo | 无 | 无自动候选 | 全部等待 provider |
| Call | 无 | 无自动候选 | 全部等待 provider |
| Battery | GetPhoneBatteryInfo | normal/charging/low | runtime 无可信时长；resourceUsage 删除 |
| AppUsage | GetAppUsageDuration | singleApp | limit/overLimit/topApps 缺字段 |
| Activity | GetHealthAndSportSummary | steps/dailySummary | calories/exercise 尚无独立 Hero；goalRatio 无目标时不生成 |
| Workout | Health / CountdownDays | latest/纯天数 countdown | 赛事详情缺字段 |
| HeartRate | GetHealthAndSportSummary | average | current/attention 缺实时来源 |
| Sleep | GetHealthAndSportSummary | duration/insufficient/schedule | stages 缺阶段列表 |
| Location | Weather.location | commuteContext | current/home/pair 缺独立来源 |
| SystemMode | 无 | 无自动候选 | 全部等待 provider |
| Bluetooth | GetEarphoneInfo | earbuds | singleDevice 尚无独立模板；mediaControl 缺媒体来源 |
| Settings | 无 | 无自动候选 | 全部等待 provider |
| ResourceUsage | GetSystemMemInfo | memory（严格三字段） | storage 及非内存明细/趋势请求禁选 |

## 5. 新 UX Golden 的契约边界

`UX设计/2X2卡片案例` 当前实际包含 9 个场景，不是 10 个。可直接作为生产契约回归的事实包括会议、专注、
手机电量、睡眠、天气和健康/设备字段；以下内容只能作为视觉目标，不能反向写入生产 Schema：

- Digital Wellbeing 的 safeValue/warningValue/total/overtime；
- Race 的赛事名称、训练距离和计划；
- Device Clean 的 storageValue 和第二个内存指标。

这三类场景在真机视觉对齐时必须标注“视觉基线可对比、生产协议字段未满足”，不能用 fixture ID、场景名或
Golden 数据写死 Selector、组件次数或 Template 次数。

## 6. 实现顺序与验收门禁

1. 先实现 Provider Gate 和严格 ViewModel/Selector，保证不可用组件不会进入 Prompt。
2. 第一批实现真实数据覆盖的 Weather、Date、Schedule、Battery、AppUsage(singleApp)、Activity、Workout、
   HeartRate(average)、Sleep、Bluetooth、ResourceUsage(memory)。
3. 第二批实现无 provider 组件的确定性 Template/Compiler，但保持生产自动候选关闭。
4. 每个组件分别增加：合法输入、缺字段、0/null、非法枚举、尺寸裁剪、动作归属、字体/图标和 Template 消失测试。
5. 协议层与 Golden 大致一致后再做 HAP/云服务真机校验；不得使用 fallback 冒充内容组件成功。

任一组件若无法容纳 mustShow，应由 Composer 改选布局或不兼容，而不是把关键字号继续缩小。

## 7. 实现状态

首轮实现已按本文门禁完成，旧 `@1` Template 全部保留：

| 内容组件 | 新 Template | 生产 Scope |
|---|---|---|
| Weather | `ux-weather-overview@2` | ViewWeather 开放 |
| Date | 直接 TerseDSL（旧 `ux-date-overview@2` 仅兼容保留） | GetCalendarEvents 严格日期准入后开放 |
| Schedule | 直接 TerseDSL（无 Schedule JSON 视图树） | GetCalendarEvents 严格首项准入后开放 |
| Task | `ux-task-overview@2` | 无 provider，关闭 |
| Memo | `ux-memo-preview@2` | 无 provider，关闭 |
| Call | `ux-call-overview@2` | 无 provider，关闭；号码必须含脱敏字符 |
| Battery | `ux-battery-overview@2` | GetPhoneBatteryInfo 开放 |
| ResourceUsage | 直接 TerseDSL（不使用 Resource JSON Template） | GetSystemMemInfo 严格三字段后开放 memory |
| AppUsage | `ux-app-usage-overview@2` | 只开放 singleApp |
| Activity | `ux-activity-overview@2` | Health 开放 steps/dailySummary |
| Workout | `ux-workout-overview@2` | Health latest、CountdownDays countdown |
| HeartRate | `ux-heart-rate-overview@2` | 只开放运动 average |
| Sleep | `ux-sleep-overview@2` | 开放 duration/insufficient/schedule |
| Location | `ux-location-overview@2` | 只开放 Weather commuteContext |
| SystemMode | `ux-system-mode-overview@2` | 无 provider，关闭 |
| Bluetooth | `ux-bluetooth-overview@2` | 开放 earbuds |
| Settings | `ux-settings-overview@2` | 无 provider，关闭 |
| ResourceUsage | `ux-resource-usage-overview@2` | 只开放 GetSystemMemInfo memory |

注册表通过 `dataCapabilityIds` 和 `enabledVariantsByCapability` 做 fail-closed 门禁。CardSpec 中的有效能力 ID
优先于 Query 和字段名；无 provider 时第一层 LLM 请求之前即停止。模板内数值用于 Text 时由可信编译器转为
字符串，Progress 仍保留数值，因此 `0` 不会被误判为空值。所有新 Template 只展开为标准基础组件，最终
A2UI 不含 Template。

## 8. 第二层事实投影与 9 场景确定性结果

第一层 Scope Planner 继续读取完整 provider Schema，用于判断主题和内容高级组件范围。第一层完成后，服务端按
`advancedComponentIds` 生成第二层事实投影：只保留所选严格内容组件能够显示的 mustShow/Support 字段，
更新时间、服务链接和其他传输元数据不再自动进入 `mustKeep`。这一步是可信 Python Selector，不增加 LLM 调用，
也不修改原始 TaskSpec。

以下 9 场景表是 Schedule 直接 TerseDSL 迁移前的历史基线，旧 Template 标识不代表当前注册表仍保留对应
JSON 视图树：

| 场景 | 正式契约 | 使用的新内容 Template | ready | Golden 语义 | 空间裁剪 |
|---|---|---|---:|---:|---:|
| current-meeting | 完整兼容 | `ux-schedule-overview@2` | 是 | 通过 | 否 |
| focus-mode | 完整兼容 | `ux-schedule-overview@2` | 是 | 通过 | 否 |
| low-power | 完整兼容 | `ux-battery-overview@2` | 是 | 通过 | 否 |
| sleep | 完整兼容 | `ux-sleep-overview@2` | 是 | 通过 | 否 |
| family-care-weather | 完整兼容 | `ux-weather-overview@2` | 是 | 通过 | 否 |
| rainy-commute | 完整兼容 | `ux-weather-overview@2` | 是 | 通过 | 否 |
| device-clean | 部分兼容 | `ux-resource-usage-overview@2` | 是 | 未通过，缺 storage/第二指标 | 否 |
| digital-wellbeing | 部分兼容 | `ux-app-usage-overview@2` | 是 | 未通过，缺限额/超时量 | 否 |
| race-countdown | 部分兼容 | `ux-workout-overview@2` | 是 | 未通过，缺赛事/训练计划 | 否 |

汇总：9/9 `finalReady=true`，9/9 `fallback=false`，9/9 静态展开后不含 Template；6 个正式契约完整兼容
场景 6/6 通过 Golden 语义门禁。3 个部分兼容场景保留为可解释的 provider Schema 缺口，不以 fixture 字段或
fallback 冒充生产成功。本轮为纯确定性验证，真实模型调用数和 Token 均为 0。

## 9. DeepSeek V4 Flash 真实生成结果

以下真实评估是同一迁移前历史结果。评估使用 `deepseek-v4-flash`、llmclient 直连，显式
`thinking=false`，不启用模型 fallback。首次全量运行
发现 2×2 的 Weather+Location、Schedule+Date 重复 Scope 会诱导模型选择无法容纳全部 mustKeep 的
`HeroSupportActionLayout`。服务端随后增加通用 Scope 归一化：Weather 已拥有 city 时不再重复选择 Location；
Schedule+Date 在用户未明确询问日期时由 Schedule 原子拥有，明确询问日期时仍保留 Date。该规则不读取
Fixture ID、Golden 场景名或业务专名。

最终报告由首轮已成功的 5 个场景与修复后重跑成功的 4 个场景离线合并，没有为合并额外调用模型：

| 场景 | Scope | Template | 原始协议成功 | ready | fallback | Golden | Token | 时延 ms |
|---|---|---|---:|---:|---:|---:|---:|---:|
| current-meeting | Schedule | `ux-schedule-overview@2` | 是 | 是 | 否 | 通过 | 5,177 | 2,498.09 |
| focus-mode | Schedule | `ux-schedule-overview@2` | 是 | 是 | 否 | 通过 | 4,812 | 2,509.08 |
| low-power | Battery | `ux-battery-overview@2` | 是 | 是 | 否 | 通过 | 4,216 | 2,303.24 |
| sleep | Sleep | `ux-sleep-overview@2` | 是 | 是 | 否 | 通过 | 3,955 | 2,502.70 |
| family-care-weather | Weather | `ux-weather-overview@2` | 是 | 是 | 否 | 通过 | 5,159 | 2,838.26 |
| rainy-commute | Weather | `ux-weather-overview@2` | 是 | 是 | 否 | 通过 | 5,047 | 3,276.77 |
| device-clean | ResourceUsage | `ux-resource-usage-overview@2` | 是 | 是 | 否 | 部分，缺 72% 第二指标 | 4,695 | 2,676.21 |
| digital-wellbeing | AppUsage | `ux-app-usage-overview@2` | 是 | 是 | 否 | 部分，缺已超15分 | 3,961 | 2,116.87 |
| race-countdown | Workout | `ux-workout-overview@2` | 是 | 是 | 否 | 部分，缺赛事/训练信息 | 3,797 | 2,048.90 |

最终选定证据为 18 次真实调用、40,819 tokens、场景时延合计 22,770.12ms；9/9 原始协议成功、9/9 ready、
0 fallback，正式契约完整兼容的 6 个场景 6/6 Golden 通过。三个部分兼容场景的 Action 均正确，缺失文本与
第 5 节记录的 provider Schema 缺口完全一致。

本轮内容组件阶段开始前持久化预算累计值为 612；一次错误 provider 路由烟测、一次成功烟测、首轮全量和
4 场景定向重跑后累计为 649，共原子预留 37 次。评估进程按用户授权临时设置 unlimited（remaining 为
`null`），没有删除、重置或改写历史计数；生产默认上限仍保持 400。原始 Prompt、输出、usage 和 finish reason
保存在权限为 0600 的忽略目录 `workspace/runtime/cardplan_template_evaluation/`，不进入 Git。

## 10. 最终真机逐组件校正

2026-08-11 在公网 `widget-service:20260811T0720Z-content-final` 与设备
`3AX0224A14000098` 上逐个触发九个场景。所有场景都满足
`scope_component_count=1`、`template_call_count=1`、`validation_repair_count=0`、
`fallback_used=false`；最终展开组件数依次为 12、16、11、19、16、17、17、13、17。

内容排版以 UX 详细设计而非截图像素为准：AppUsage 与 Sleep 的可信格式化时长在服务端确定性拆为
`30fp 数值 + 12fp 单位` 两组，真机完整显示 `3 小时 45 分钟` 与 `5 小时 45 分钟`。原始
`durationText/nightSleepDurationText` 仍保留在 provider 契约中，拆分字段只存在于第二层事实投影；
无法解析的格式不会由模型补造。mustKeep 校验按连续可见语义片段识别这类静态展开，避免再附加整串重复文本。

长业务标题由布局外壳按归一化文本长度确定性选择 14fp 或 10fp，保持单行和完整业务语义；赛事场景真机显示
`距离香H100越野赛`，Action 仍由批准的 `PillAction` 降级并绑定原事件。三个部分兼容场景仍只报告真实
provider 缺口：内存缺第二指标、数字健康缺限额/超时量、赛事倒计时缺完整训练计划数据；不以 Fixture 或
Golden 字段注入生产输出。
