# CardPlan Template 融合服务化说明

## 目标与路由

本实现将 `generateWidgetCardTerseDslNested2` 的 create 主链路固定为 UX 混合模式，不增加第三次模型调用：

1. 第一次模型调用走独立 `advanced-component-scope` 入口，只输出 `themeId` 和
   `advancedComponentIds`，不接触旧 UI Brief/Template 候选。
2. 服务端根据版本化 UX Registry 校验业务组件范围，并解析可用的布局高级组件和局部 Template。
3. 第二次模型调用直接以批准的布局高级组件为根，在业务区使用局部 Template 和标准组件，并把 Action
   放在布局规定的末尾槽位；不再生成 `card@1`。
4. 服务端静态展开布局、Action 与 Template，并在可信端补齐 CardFrame，复用现有 Terse Nested2 到 A2UI
   Adapter，端侧只接收标准 A2UI。
5. Artifact 的 `designcompactdsl` 保存可编辑的有效标准 Terse；原始 Hybrid 仅用于受控评估，不进入生产产物。

旧 `generate()`、旧 `UIBrief`、整卡置信度评分、整卡参数映射和整卡插件代码不删除，继续单独测试并可随
制品回滚，但第五接口 create 不调用。edit 路径保持既有完整 Design Token 编辑协议。

## 代码与 TypeScript 基线映射

| TypeScript 基线能力 | Python 正式服务 |
| --- | --- |
| card-plan-template 模型和 Contract | `cloud/services/cardplan_template/models.py` |
| terse-template-registry | `registry.py` 和 `cloud/data/cardplan_template/source` |
| advanced-component-registry | `advanced_component_pipeline/composition.py` 和机械导出的 `advanced-component-registry.json` |
| UX Scope Planner | `advanced_component_pipeline/scope_planner.py` |
| UX layout/business registry | `advanced-component-ux-registry.json` 和 `registry.py` |
| UX mixed prompt | `advanced_component_pipeline/ux_mixed_prompt.py` |
| hybrid-fragment / Nested-2 Parser | `parser.py`、`framer.py` |
| template-expander / composition | `compiler.py` |
| prompt-runtime | `prompt.py`、`generated/prompts.py` |
| generation-runner | `advanced_component_pipeline/pipeline.py` |
| UI IR / A2UI Adapter | 复用 `services/terse_dsl_nested2_a2ui_converter.py`，输出 `v0.9` / `ohos.a2ui.extended.catalog` |
| Manifest / SHA gate | `scripts/build_cardplan_bundle.py` 与两个 TS export 脚本 |

生产代码不读取 Golden。`tests/fixtures/cardplan_golden_scenarios.json` 仅由测试脚本机械导出，用于跨语言回归。

## 高级组件补齐

新 `advanced-component-ux-registry/1` 根据 UX 设计注册 10 个布局高级组件、17 个业务高级组件、Palette
Scene、2x2/2x4 内容预算和 `radius=20/safeInset=12/moduleGap=8/pillActionHeight=36` 等 Token。第一层
Scope Planner 根据 Query 与 TaskSpec Schema 最多下发 8 个候选，只接受版本化的 Theme 与业务组件范围。

布局高级组件声明几何、业务槽位、每种尺寸的业务/Action 数量和闭合参数 Schema；业务高级组件只声明领域
语义、角色、variant、隐私、Action/Chart 能力，以及版本化局部 Template。当前
`WeatherOverview`、`DateOverview`、`ScheduleOverview`、`BatteryOverview`、`ResourceUsageOverview`、
`AppUsageOverview`、`ActivityOverview`、`WorkoutOverview`、`HeartRateOverview`、`SleepOverview` 与
`BluetoothDeviceOverview` 均使用 CLI Provider 交付的版本化 CardTemplate。原受限直接构造仅保留为
影子测试基线，不进入默认 Prompt、UX Contract 或生产失败回退。
其中 Schedule 模型侧只输出
`ScheduleOverview@1` 已批准的 nextEvent/meeting/Source Variant，不得输出业务事实或样式；服务端按唯一
CardSpec 根绑定同一可信首项日程的 title、timeText 和可选 location，来源/时间/地点素材只能通过对应
Variant 签名传入。Action 只能由布局引用本轮批准的 `eventCandidates`。其余视觉树、样式和 2x2/2x4
尺寸重排由 CardTemplate 可信展开完成。
第二轮根必须恰好是一个允许
布局。布局配置可省略；需要覆盖默认重排时，只允许一个位于业务 child 前的 Schema 对象。Action 必须是
连续的末尾直接 children；除 `ActionMatrixLayout` 可使用 2～4 个不重复 `ActionTile` 外，其它布局最多一个
`PillAction`、`IconAction` 或 `ActionTile`。标签和事件由可信服务端绑定。独立 Header 为可选能力且默认
省略，业务标题由业务区负责。服务端展开后出现 `Template` 或任何高级组件名即失败。

`SleepOverview` 只在 `GetHealthAndSportSummary` 同一记录含可无损解析的
`nightSleepDurationText` 时进入候选；状态和严格 `HH:mm` 入睡/醒来时刻按字段分别可选。批量效果测试阶段，
得分、阶段、午睡、目标、趋势和建议等睡眠请求允许进入候选，但只降级展示 `duration`；状态或作息字段缺失
时同样降级，不补造数据。`insufficient` 只由明确可信不足状态启用，不能由时长推断。第二层只输出
`SleepOverview@1` 本轮 Prompt 实际开放的 duration/insufficient/schedule 及 Detailed/Support/Status
组合 Variant；2x4 且入睡/醒来字段完整时才开放 schedule 系列。无批准
`event.open.clock.alarm` 时不得生成动作。

`WeatherOverview` 的第一层候选和模型输出后复核都要求 `ViewWeather` 提供五个完整事实：城市取
`districtName` 或 `prefectureName`，其余依次取 `temperatureText`、`condition`、`airQuality` 和
`temperatureRangeText`；字段必须声明为字符串且样例值非空。小时预报、日出日落、气压、能见度、AQI、
体感、湿度、风、紫外线、预警、降雨概率和未来预报等未支持请求会在进入 Scope 前被拒绝。2x2 的
Weather + Location 仍归一化为单一
Weather 原子组件。Weather 内部标题 Row、内容区和布局承载容器统一用 `matchParent` 填充父区域；不能用
渲染器会按 100vp 处理的 `"100%"`。2x2 单业务使用顺序 Column：标题 Row 的地点在 leading、32vp 天气图标在 trailing，之后是 38fp 温度和底部天气/空气质量/高低温，禁止 Overlay 重叠。晴天且素材具有 `sun` 语义时注入黄色 `fillColor`，其它图标保留原色。`event.open.weather` 天气详情动作绑定到 CardFrame 整卡 `onClick`，不渲染 PillAction/IconAction；其它天气场景动作仍按布局 Action 处理。没有独立 forecast 业务组件时不允许 `WeatherNowForecastLayout`。
`ViewWeather.location.districtName` 的展示样例优先使用本轮绑定参数中的非空 `districtName`，避免请求城市
与注册表静态样例城市不一致。

`ResourceUsageOverview@1` 只开放 `memory`，要求 `GetSystemMemInfo` 的 `usagePercent` 为 0..100 的有限
number，且 `availableMemText/totalMemText` 为可信非空 string；投影和 Provider Template 只使用这三项。
存储/磁盘、缓存、进程、CPU/GPU、swap、趋势、历史和 freeMemText-only 请求均在第一层及模型返回后禁选。
不得从百分比推断压力状态。清理动作只允许批准的 `event.clean.memory`，并位于布局末尾。
受控批测开启时，每个模型步骤额外保存 `*-input.jsonl` 与原始输出，并在 `diagnostics.json` 保存投影后的
TaskSpec、编译前 DSL 及 Weather requested/renderable/visible 字段覆盖率；这些内容不进入工具响应或生产
日志。

### 布局规范映射

下表是《2X2卡片布局规范》《2X4卡片布局规范》和高级组件详细设计第 5 章在可信编译器中的落地，不依赖
Golden 场景、Fixture ID 或业务名称：

| 布局 | 2×2 | 2×4 | 受限配置 |
| --- | --- | --- | --- |
| `SingleFocusLayout` | 单区，可选底部 Pill/右下 Icon 预留区 | 单区填充 | `contentAlign` |
| `HeroActionLayout` | Hero 占剩余高度，Action 固定底部 | 底部或 60:40 末端动作区 | `actionPlacement` |
| `HeroSupportLayout` | 文本默认上下、图像/图表默认左右 | 默认左右，支持 50:50、56:44、44:56；文本 Support 使用中性底托 | `ratio`、`direction` |
| `HeroSupportActionLayout` | Hero + 最多两行紧凑 Support + 36vp Action；空间不足先删除非必需 Support，必需事实无法容纳则拒绝 | 56:44 或 50:50，右侧 Support/Action 上下分区 | `heroRatio` |
| `PeerPairLayout` | 文本上下、视觉对象左右；有全宽动作时内容左右 | 默认左右等分 | `orientation` |
| `SequentialSummaryLayout` | 主摘要在上，最多两个详情在下 | 主摘要在上，详情按 1～4 列等分 | `detailColumns` |
| `EqualItemsLayout` | 恰好两项，行/网格等分 | 3 项横排；4 项横排或 2×2 网格 | `arrangement` |
| `ListActionLayout` | 列表 + 可选底部 Action | Action 可在底部或 60:40 末端区域 | `actionPlacement` |
| `ActionMatrixLayout` | 可选摘要 + 恰好 2 个紧凑 ActionTile | 可选摘要 + 2～4 个 ActionTile；3 项为主 1 + 次 2，4 项为 2×2 | `primaryActionIndex` |
| `WeatherNowForecastLayout` | 只允许当前天气；Action 使用右下安全槽 | 当前天气主区 + 最多 3 个等宽预报/支持项 | 无 |

所有区域固定使用 8vp 模块间距，等分模块使用 8vp 内边距和 8vp 圆角，紧密层级使用 4vp。固定区域写入
`constraintSize.minWidth/minHeight=0` 和 `clip=true`，避免长文本或图片反向撑破分区。根 CardFrame 统一
使用 12vp 安全边距和 20vp 圆角；PillAction 为 36vp、IconAction 为 30vp 且内容预留 38vp 不覆盖区。

`scope_planner.py` 负责候选排序、组件兼容、Theme/Palette 和可用布局；
`domain_rules.py` 负责日程、待办、通话、电量、App 使用、运动、睡眠、位置、系统模式与蓝牙等确定性派生。
位置、电话、日程正文、睡眠窗口等默认使用 `masked`，真实 `0` 不能按空值裁掉。Validator 拒绝候选外
组件、无共同布局、布局子项越界、布局嵌套、Action 不在末尾、缺失布局必需 Action 和所有超预算输入。

旧 `advanced-component-registry/1` 的 15 个组件族和 8 个自适应模板仍由 `composition.py` 及旧
`generate()` 使用，只服务兼容测试和代码级回滚，不参与第五接口 create 主链路。

## 安全边界

- Parser 使用 Python AST 解析声明式调用和字面量，不使用 `eval` 或 `exec`。
- 新 UX 主链路只允许本次批准的布局根、三个 Action 高级组件、Registry 中的版本化 Template、Catalog
  标准组件及白名单字段。全部 Provider-backed 数据型业务组件已经通过 Python-vs-Template 等价门禁，
  Registry 默认实现统一为 `template`，不存在生产 `terse-dsl` 回退。保留的可信 Python 构造只作为测试
  Shadow Oracle；`card@1` 仍只由隔离的兼容入口接受。
- Template 展开前后分别校验 variant、参数 Schema、父组件、Action、素材、字面量、节点、深度和空间预算。
- 反引号插值与 `Expr` 编译为单个端侧 A2UI 表达式；可选素材必须受 `IfParam` 守卫，可选 Provider
  字段必须受 `IfBind` 守卫。所有守卫在可信展开阶段消除，不进入最终 A2UI。
- Template 只在可信服务端展开；编译后 A2UI 出现 `Template` 即失败。
- 模型只能引用本次 Contract 暴露的数据路径、素材和 Action。Template 的占位 Action 在展开后绑定回
  TaskSpec 中已批准的完整 `call/args`。
- CardTemplate UX 测试页可在候选数据能力中携带受限 `previewData`，用于构造与真实数据同形的 TaskSpec
  样例；服务端限制其类型、深度、节点数、数组/字符串和编码大小，并从 Pydantic 序列化及生产日志中排除。
- 生产日志不记录业务正文、Prompt、原始输出或密钥。评估证据只写入忽略目录并设置为 `0600`。

## bypass

请求中的测试参数为：

```json
{
  "options": {
    "forceHybridTemplate": true,
    "testAuthorization": "由测试环境注入的短期 token"
  }
}
```

四项条件必须同时成立：

- `WIDGET_SERVICE_ENABLE_HYBRID_TEST_BYPASS=true`；
- `WIDGET_SERVICE_ENV=local` 或 `test`；
- 服务端配置了非空 `WIDGET_SERVICE_HYBRID_TEST_BYPASS_TOKEN`；
- 请求 token 常量时间比较通过。

生产默认关闭。`testAuthorization` 从 Pydantic 序列化中排除，并由日志清洗器无条件移除。任何条件不满足都
返回未授权错误。create 本身已固定进入新混合路线，该兼容参数不会切换路由。

### 临时批跑数据准入旁路

为批量观察高级组件视觉效果，可临时同时设置：

- `WIDGET_SERVICE_ENABLE_WIDGET_BATCH_RECORDING=true`；
- `WIDGET_SERVICE_ENABLE_ADVANCED_COMPONENT_DATA_ADMISSION_BYPASS_FOR_BATCH=true`。

两项同时开启时，第一层候选和 Scope 输出复核暂不执行各业务组件的 Query 细分、字段完整性及动作闭环
适配判断，Template 候选也不再因参数数据匹配不完整而提前剔除，并在 Prompt、invocation 和批测证据中记录
`temporaryDataAdmissionBypass=true`。Provider、尺寸、
Registry 组合、布局约束、第二层可信事实投影、Provider Template、Action/素材白名单和最终编译校验仍然
保留；服务端不会补造缺失字段、状态、事件或图标。因此批跑样例仍需提供目标组件最终展示所需的真实事实。

批跑结束后关闭任一开关并重启服务即可恢复严格准入；该旁路不得用于生产流量。

## DeepSeek 硬预算

`cloud/custom/deepseek_call_budget.py` 使用 SQLite `BEGIN IMMEDIATE` 在每次真实
`deepseek_platform`/`llmclient` 调用前预留。请求发送失败仍计数；达到 400 后抛出
`DeepSeekCallBudgetExceeded`，该异常不会进入重试、fallback 或旧 Terse 路线。

配置：

```dotenv
WIDGET_SERVICE_DEEPSEEK_CALL_BUDGET_LIMIT=400
WIDGET_SERVICE_DEEPSEEK_CALL_BUDGET_PATH=workspace/runtime/deepseek_call_budget.sqlite3
```

生产默认值仍为 `400`。经明确授权的隔离评估任务可在单次进程环境中设置
`WIDGET_SERVICE_DEEPSEEK_CALL_BUDGET_LIMIT=0` 进入无限模式；该模式只取消拒绝门槛，仍会在每次调用前
原子增加同一计数器，因此不会丢失或重置既有历史。不得把 `0` 写入生产部署配置。预算数据库属于运行状态，
不提交、不删除、不重置。多进程可共享
同一 SQLite 文件；多主机部署前必须提供具有可靠文件锁的共享持久卷，或迁移到等价的共享原子计数服务。

使用直连 DeepSeek 的本地真实评估时，把凭据写入 `widget_service/.env`（已被 Git 忽略），不要写入 Shell
历史、测试 Fixture、报告或提交：

```dotenv
WIDGET_SERVICE_OPENAI_MASTER_CLIENT=llmclient
WIDGET_SERVICE_OPENAI_FALLBACK_CLIENT=deepseek_platform
WIDGET_SERVICE_ENABLE_OPENAI_FALLBACK=false
WIDGET_SERVICE_DEEPSEEK_API_KEY=替换为本地密钥
WIDGET_SERVICE_DEEPSEEK_API_URL=https://api.deepseek.com
WIDGET_SERVICE_DEEPSEEK_MODEL=deepseek-v4-flash
WIDGET_SERVICE_DEEPSEEK_ENABLE_THINKING=false
```

直连 HTTP 请求按 DeepSeek OpenAI 兼容协议显式发送
`"thinking":{"type":"disabled"}`；不能只依赖本地布尔配置，因为 V4 默认启用 thinking。HTTP 流在应用
事件循环中执行，达到 `WIDGET_SERVICE_MODEL_REQUEST_TIMEOUT_SECONDS` 后会关闭连接；内部 WebSocket 和测试
注入的同步 Transport 继续持有并发令牌直到物理调用结束。路由单测必须把
`WIDGET_SERVICE_DEEPSEEK_CALL_BUDGET_PATH` 指向测试临时目录，不能污染生产/真实评估预算。

## 生成物和 SHA 门禁

在 `intermediate_expression` 执行：

```bash
pnpm exec tsx ../CreateMyCard/widget_service/scripts/export_cardplan_baseline.ts --check
pnpm exec tsx ../CreateMyCard/widget_service/scripts/export_cardplan_golden_fixture.ts --check
```

在 `widget_service` 执行：

```bash
python scripts/build_cardplan_bundle.py --check
```

需要接受上游 TS 变更时，先不带 `--check` 重新导出，再审查 Registry、Prompt 和 Manifest diff。Prompt
Manifest 对每个源片段和生成常量保存 SHA-256；任何未重新生成的漂移都会使门禁失败。

## 测试与评估

确定性评估不调用模型：

```bash
PYTHONPATH=cloud python scripts/evaluate_cardplan_golden.py \
  --mode deterministic \
  --output workspace/runtime/cardplan_template_evaluation/deterministic-latest.json
```

真实评估只在全部确定性门禁通过后执行：

```bash
PYTHONPATH=cloud python scripts/evaluate_cardplan_golden.py \
  --mode live --confirm-live \
  --output workspace/runtime/cardplan_template_evaluation/live-latest.json
```

真实命令强制关闭模型 mock、模型 fallback 和模型失败重试。报告保存每轮原始 Prompt/输出，并在供应商
协议提供时保存原始 usage 和 finish reason；供应商未返回的字段保持 `null`，同时单独提供标记为
`char-estimate` 的估算 Token。任一场景原始协议失败、最终未 ready 或使用 fallback 时命令返回非零。

编译器或评估器修正后可对保存的真实证据零调用重分析：

```bash
PYTHONPATH=cloud python scripts/reanalyze_cardplan_golden.py \
  --input workspace/runtime/cardplan_template_evaluation/live-latest.json \
  --input workspace/runtime/cardplan_template_evaluation/live-low-power.json \
  --input workspace/runtime/cardplan_template_evaluation/live-family-care-weather.json \
  --output workspace/runtime/cardplan_template_evaluation/live-final-reanalyzed.json
```

同一场景在后一个输入报告中出现时覆盖前一个证据，但不会修改原始模型调用内容，也不会预留预算。

按 `/UX设计/2X2卡片案例` 当前九个场景重新导出标准 A2UI 基线后，最终确定性结果为：9/9
`finalReady`、0 fallback、9/9 通过严格 Golden 对齐。该结果由机械导出的 Hybrid Source 经过正式 Parser、
Registry、Compiler 和 A2UI Adapter 得到，没有以 Golden A2UI 覆盖结果。

关闭 thinking、保持模型失败 fallback 关闭，并允许最多两次只针对第二层的严格校正后，2026-08-11 线上
最终镜像的真实 DeepSeek 结果为：8/9 首轮原始协议成功、9/9 `finalReady`、0 fallback、9/9 严格 Golden
对齐。`race-countdown` 的首次混合体不满足严格协议，经一次受限二层校正后成功；第一层 Scope 没有重跑。
总 Token 为 52,759，场景累计模型时延 22,819.01ms。报告中所有模型调用的 finish reason 均为 `stop`。
评估命令仍按“首次原始协议必须全通过”的更严格发布门禁返回非零；这不能被 9/9 最终 ready 覆盖或隐藏。
逐场结果如下：

| 场景 | Template | 展开组件 | Token | 时延 ms | 语义文本覆盖 | 严格对齐 |
| --- | --- | ---: | ---: | ---: | --- | --- |
| current-meeting | `ux-meeting-metadata@1` | 16 | 5,649 | 2,972.76 | 1.0000 | pass |
| family-care-weather | `weather-summary@1` | 18 | 5,241 | 2,551.41 | 1.0000 | pass |
| focus-mode | `ux-calendar-content@1` | 14 | 5,274 | 1,888.42 | 1.0000 | pass |
| device-clean | `ux-device-metric@1` | 23 | 5,614 | 2,452.52 | 1.0000 | pass |
| rainy-commute | `ux-weather-hero@1` | 17 | 5,367 | 1,919.76 | 1.0000 | pass |
| low-power | `ux-battery-status@1` | 18 | 5,279 | 1,872.46 | 1.0000 | pass |
| sleep | `ux-sleep-metric@1` | 14 | 5,437 | 2,429.19 | 1.0000 | pass |
| race-countdown | `ux-countdown@1` | 17 | 9,513 | 4,292.51 | 1.0000 | pass after repair |
| digital-wellbeing | `ux-segmented-limit@1` | 22 | 5,385 | 2,439.98 | 1.0000 | pass |

最终九场景报告的持久计数快照为 819→838；两个最终场景复测和 gate-final 切换后的真机 smoke 把全局
计数推进到 845。本轮经明确授权
使用无限评估模式，因此 limit/remaining 为 null，生产默认仍为 400。原始 Prompt/输出报告位于忽略目录并
保持 `0600`，不提交。若部署环境未提供 DeepSeek
凭据或网络不可达，评估必须保持失败且 `fallback=false`，不得用确定性结果替代真模型结论。预算状态以
评估报告中的原子预留快照为准，不在版本库文档中持续更新运行时数据库计数。

## 上线、观测与回滚

仓库根目录的 `.dockerignore` 与 `widget_service/Dockerfile` 用于构建 Python 3.12 运行镜像。运行时将
`cloud/workspace` 挂载为持久卷，以保留预算 SQLite 与 mock artifact；环境文件必须位于宿主机受限权限路径，
不得打入镜像。对 CardTemplate UX 替换旧 TS 服务时，先在旁路端口验证 `GET /health`、未授权连接以 1008
拒绝、带 Token 的 `/ws` `card.generate` 返回 `card.generate.delta/result` 且最终消息为 ready A2UI，再切换
原端口。`createSurface.catalogId` 必须为 `ohos.a2ui.extended.catalog`；带 `.form` 的历史值会被端侧扩展
渲染器拒绝。切换前记录旧容器镜像 ID 与端口映射，回滚仅恢复旧容器，不删除 Python 持久卷。

公网部署必须设置 `WIDGET_SERVICE_WEBSOCKET_BEARER_TOKEN`；该 Token 同时保护 `/ws` 与全部工具 WebSocket。
端侧本地配置可用独立的 `cardTemplateWebSocketUrl` 指向旁路端口，未设置时兼容回退到 `webSocketUrl`。
测试环境经明确授权可将预算上限设为 `0`，但必须保留已有计数数据库；正式生产仍不得使用无限预算。

本次内容高级组件逐项对齐后的运行镜像为 `widget-service:20260811T0730Z-content-compat-final`（镜像 ID
`sha256:1bd85384690000939c22a8428d4521b4b8807eddd374967c2b827308cff530f8`），对外端口为 `2832`，
容器健康检查与公网 `/health` 均通过。直接回滚目标保留为
`widget-service-rollback-20260811T0730Z-pre-compat`；回滚时不得删除 `/var/lib/widget-service` 持久卷。
镜像名和回滚容器是本次部署证据，不应写入生成路由或测试断言。

最终 HAP 在设备 `3AX0224A14000098` 逐场验证九个 UX 场景，全部为 Template=1、repair=0、
`fallback=false`；六个 Provider 字段完整的场景逐字段通过，另外三个场景明确保留 Provider 输入缺口：
设备清理缺少第二指标，数字健康缺少限额/超限字段，赛事倒计时缺少完整训练计划。服务端不会为通过 Golden
校验而编造这些字段。AppUsage 与 Sleep 的复合时长已由可信 Selector 拆为主/次数值和单位，长赛事标题由
可信 Registry 按长度选择单行字号，最终 A2UI 不含 Template 节点。

上线顺序：

1. 在预发执行生成物 SHA、Ruff、mypy、全量 pytest、wheel build 和当前九场景真实评估。
2. 确认预算数据库位于持久卷、进程用户可写，且当前 used/remaining 已记录。
3. 保持 bypass 关闭；以小流量灰度第五接口 create 请求。
4. 观测 Scope Theme/业务组件、允许布局、`whole_card_scoring_bypassed=true`、`raw/effective` 长度、
   `fallback_used`、Template 调用/展开组件数、编译失败类别、ready 率、Token 和时延。
5. 以旧制品整卡路径和其它四个工具接口作为对照组，确认成功率和延迟后再扩大流量。

回滚不删除预算数据库、不改 Golden，也不把失败输出保存为 artifact：将服务回滚到前一制品即可恢复旧
整卡路由；如果仅需阻止测试入口，保持或恢复
`WIDGET_SERVICE_ENABLE_HYBRID_TEST_BYPASS=false`。回滚后继续保留预算和评估报告用于审计。

`WIDGET_SERVICE_ENABLE_ADVANCED_WHOLE_CARD_TEMPLATE` 和整卡置信度阈值仅保留给旧 `generate()` 的兼容
测试与代码级回滚；它们不改变当前第五接口 create 路由。新混合生成或校验失败直接返回失败，不会回退旧
整卡或旧 TerseDSL-Nested-2。要恢复旧主链路必须回滚服务制品，不能依赖普通外部请求或运行时开关。

## 已知限制

- 独立 Header 尚未开放给模型；默认不生成卡片级标题，语义标题由业务内容承担。需要 Header 时必须先补齐
  版本化 Contract、UX Token 和防重复标题校验。
- `ResourceUsageOverview.storage` 仅保留 Registry 声明，尚无正式 Provider；freeMemText、压力状态、趋势和
  历史曲线均未开放。
- 新增布局、Action 或 Template 必须先更新 source Registry/Prompt，再通过生成物 SHA 门禁。
- 空间估算是服务端保守预算，超过推荐高度会标记 `space_constrained`，硬节点/深度限制仍会拒绝。
- 共享 SQLite 预算依赖文件锁；跨不共享文件系统的多副本不能宣称全局 400 次保证。
- 真实 DeepSeek 的 usage/finish reason 是否可得取决于上游协议是否在 final 消息中返回这些字段。
