# Nested-2 卡片批跑端到端修复 Wiki

> 适用范围：`generateWidgetCardTerseDslNested2`、`genui_evaluation` 批量用例页、2×2/2×4 卡片真机验证。
>
> 最终验收时间：2026-08-12；最终批次：`nested2-2x2-1786503987707`。

## 1. 最终结论

- 2×2 的 20 条用例在真机批量页全部生成并显示：服务端摘要 `20/20`，失败 `0`。
- 端侧日志记录了 q1 到 q20 共 20 个 `rendered messages=3`，没有 `schemaWarning`、`Surface 2001`、`DSL root must be an object` 或渲染失败。
- 最终服务镜像为 `widget-service:20260812T1120Z-ux-color-v17`，镜像摘要为 `sha256:316c9e4a75e24e42c14a63e43f105d4810b60f46c145721eb4c7ba9b6e8bc566`。
- 回滚容器为 `widget-service-backup-20260812T1120Z-ux-color-v17-predeploy`，对应 v16 镜像。
- 端侧直接访问公网 WebSocket `ws://47.98.140.54:2832/...`，没有使用 HDC 反向映射。
- 2×2 卡片为 160×160 vp；2×4 已按要求调整为宽 320、高 160 vp。

最终批次中 19 条为 `success`，q10 为 `degraded`。q10 的降级仅表示三个未注册的可选素材被能力裁决移除；`GetEarphoneInfo` 和蓝牙设置事件仍有效，A2UI 已生成，左右耳 76%/74% 两个 Ring 均在真机正常显示。因此批次汇总将其计入 passed。

## 2. 批跑与混合方案边界

当前部署关闭旧的 Advanced Whole-card Template 路径，Nested-2 使用两步混合方案：

1. 第一步 LLM 选择主题和高级业务组件。
2. 第二步 LLM 输出受约束的 UX Layout、业务组件和 Action。
3. 服务端 Compiler 将其确定性降级为标准 A2UI v0.9，并做数据、素材、事件、布局和可见性校验。

批量模式本身没有再额外“屏蔽模板”。它只在请求作用域内开启测试数据准入和完整 schema sample；不会修改普通线上请求的准入规则。Registry 声明为本地 Template 的可信组件仍可展开 Template；本次新增的业务组件采用直接 Terse DSL lowering，所以主要走混合路径。

每个 case 的结果目录都保存：

- 原始接口输入 `input.json`；
- 第一步输入/输出 `llm-step-01-*-input.jsonl`、`llm-step-01-*.txt`；
- 第二步输入/输出 `llm-step-02-*-input.jsonl`、`llm-step-02-*.txt`；
- 如发生修复，继续保存 step 03/04 的输入输出；
- 最终 `output.a2ui.jsonl`、`response.json`、`diagnostics.json`、`metrics.json`。

## 3. 问题、原因与修复

| 阶段/现象 | 根因 | 修复 |
| --- | --- | --- |
| 初始 20 条仅 3 条成功 | 批量测试数据与正式准入 schema 的嵌套路径不同；多个业务 selector 只识别旧路径 | 增加 `/data/<writeResultTo>` 等真实路径选择；批量请求作用域内提供完整 schema sample，禁止用全局环境变量泄漏到普通请求 |
| 高级组件被误判为数据不足 | batch 的模拟值没有进入业务组件 admission | 增加 request-scoped batch admission context；离开当前请求立即恢复严格模式 |
| 第二步选择了业务组件但 Compiler 拒绝 | Framer 只保留旧 Template 子树，直接业务组件被丢弃或布局被强制改写 | Framer 保留直接业务子节点；只有满足允许条件时才升级布局 |
| q4/q8 省电 Action 失败 | LLM 选择的素材描述包含“叶片/节能”，语义标签没有映射到 power-saving | 扩展 leaf/节能/绿叶/叶片/叶子语义；仅当存在唯一可信匹配时，把省电 Action 归一化到该素材 |
| Weather 图标位置和来源不正确 | 天气图标曾依赖内置资源，且 Action 角落留白作用到整块内容 | Weather 图标改由第二步 LLM 从可信素材输入中选择；仅对可能与右下 Action 重叠的天气子区预留空间 |
| `2004 DSL root must be an object`，批量页全部渲染失败 | 本地 HAR 的 `handleMessage` 一次只接受一个 JSON object；旧调用把消息数组整体传入，且 dataModel 早于组件更新 | `handleGenuiFormMessage` 对数组逐对象发送；批处理顺序固定为 createSurface → updateComponents → updateDataModel |
| 在线 OHPM 的 margin/padding 能力不完整 | 批量页仍引用线上 `@arkui-genius/genui_form` | `entry/oh-package.json5` 改为 `file:libs/genui_form.har`，所有页面统一使用本地 HAR，而不是只改单页 |
| 2×4 方向错误、Grid 不可纵向浏览 | 尺寸仍是 160×320，外层 Scroll 配置为 Horizontal | 改为 320×160；Grid 外层改为 Vertical，保留每行 4 个 2×2 或 2 个 2×4 |
| q6 内存容量文字与电量区域重叠 | capacity 文本横排宽度不足；LLM 还可能显式给 `orientation:"rows"` 造成 160 vp 内纵向堆叠 | capacity 改为 9fp 纵向两行；2×2 ResourceUsage+Battery 强制横向 50/50，忽略不适合紧凑卡的 rows 请求 |
| q7 天气+电量辅助区被裁切 | 2×2 support 高度 28 vp，且仍使用完整 Ring 结构 | 使用无 Ring 的两行电量摘要，support 高度提高到 36 vp；天气字号同步压缩 |
| q12/q17 “7 天”挤压且橙底对比度不足 | 数值与单位 Text 都占满父宽；文字仍使用橙色 accent | 数值/单位使用自然宽度并放入底对齐 Row；文字统一使用高对比黑色 |
| q10/q16 仅显示一个耳机 Ring | 两个子 Column 在 Row 中都按 matchParent 布局，发生重叠 | 两个耳机指标 Column 增加 `layoutWeight:1`，最终显示 76% 和 74% 两栏 |
| q10/q12/q16/q17 下方出现 `Surface 2001` | Row 误用了 Column 的 `alignItems:start/end` 枚举 | 蓝牙标题行改为 `top`，倒计时数值行改为 `bottom`；真机日志确认 warning 为 0 |
| q14 偶发四次修复后仍失败 | LLM 把唯一日历素材复用到 `timeIcon/locationIcon`，与素材语义不匹配 | 对可选的时间/地点图标做安全删除；`sourceIcon` 仍保持严格语义校验，避免错误图标进入 UI |
| q19 颜色版批跑 19/20 | LLM 把仅具 clean/home 语义的清理动作素材同时填入可选 `ResourceUsageOverview.icon`，四次输出都无法满足 memory/resource 内容图标语义 | 在严格校验前删除这个可选错配内容图标；末尾一键清理 Action 的同一图标仍保留并独立校验，非白名单素材继续硬拒绝 |
| q1/q3/q7 强背景前景对比错误 | 整卡天气点击被误当作 Action 按钮，导致 q1 正文未转白；Weather 子树又一律保留图标原色，导致雨滴为黑色 | 仅真正 Action Stack 保留按钮文字色；整卡点击正文继续按 text-on-accent 转白；晴天/雨滴等按素材语义分别使用黄色/白色，未知多彩图标保留原色 |
| 最终颜色批跑 q4/q19 偶发失败 | q4 模型连续输出一个 Layout 和一个 Layout 外 sibling；q19 最终修复虽给出合法 Layout，却在单业务上误写 `showTitle:false` | sibling 中恰好只有一个批准 Layout 时保留该 Layout 并严格校验其子树；单 Resource 业务确定性恢复必需标题，多业务标题规则不放宽 |
| 后续批跑 q8 偶发失败 | 模型把唯一批准 HeroActionLayout 作为 BatteryOverview 的 child，连续修复仍重复相同结构 | 仅对“一个已注册 direct-business 配置 + 唯一批准 Layout”执行确定性 reparent，恢复业务叶子并保留 Layout Action；其它嵌套仍拒绝 |
| q8 下一次仍 19/20 | 模型改为把 BatteryOverview 与 Layout 输出成 sibling，但 Layout 内仅有冗余标准 Column；旧 sibling 修复保留 Layout 时丢失了业务 leaf | 当唯一批准 Layout 内无业务高级组件、顶层又恰有一个 direct-business sibling 时，将该业务 leaf 放回 Layout 并丢弃冗余标准块；Scope 契约继续验证业务身份 |
| 整体颜色与 UX 规范不一致 | Theme Registry 沿用旧品牌色，多个高级组件内部 Ring、轨道、图标和文字仍有散落硬编码；跨领域 Scope 还会把天气/内存主视觉改成通用白色 | 按 `UX设计/卡片颜色风格.md` 重建场景色矩阵；Compiler 统一黑色文字层级、绿色正常态、橙色预警态和 10% 黑轨道；强背景普通文字/单色图标统一白色，保留天气多彩图标；跨领域主题按主业务的首个非 generic 场景归一化 |
| q20 太阳图标为黑色 | 第二步已选择 `sun_max.svg`，但云侧仅在天气文字含“晴”时应用黄色；“多云”状态使明确的 sun 语义素材未着色 | 以第二步选择的素材语义为准，`sun/sunny` 图标固定使用 `#FFFFC300`；不再依赖天气字符串重复推断 |
| q1 彩色多云图标变成白色方块 | `icon_weather1.svg` 是多层渐变 SVG，但同时带 cloud 语义，被通用单色云规则强制染白 | 识别内置彩色天气素材族并保留原始渐变；单色雨滴/云/风暴/雪继续按强背景白色规则处理 |

## 4. 端侧改动要点

- 批量页用 Grid 展示结果，并为每个 case 使用独立 `SurfaceController`。
- 每次运行重新创建渲染 generation key，避免旧 Surface 复用。
- 失败信息按 Surface 初始化、服务连接/生成、产物下载、A2UI 解析/渲染分阶段显示。
- 2×2 与 2×4 分别保存 batchId，切换尺寸不会覆盖另一批的结果。
- `genui_form` 统一切到本地 HAR；消息数组拆分、Catalog ID 归一化和三类消息时序集中在 `GenuiFormRuntime.ets`。

## 5. 最终验证证据

| 检查项 | 结果 |
| --- | --- |
| 服务端批次 | `nested2-2x2-1786503987707` |
| 批次摘要 | passed 20 / failed 0 / total 20 |
| 状态细分 | success 19 / degraded 1 / failed 0 |
| 单 case 耗时 | min 1793.13 ms / median 2522.80 ms / p95 5160.72 ms / max 6472.93 ms |
| 服务测试 | 1013 passed / 17 skipped / 22 subtests passed |
| 端侧渲染 | q1–q20 各 `rendered messages=3` |
| 端侧 schema warning | 0 |
| 端侧渲染失败 | 0 |
| 服务健康检查 | healthy |
| 未授权批次 API | HTTP 401 |

本地完整证据目录：`/Users/yansf/workspace/GenerateUI/result/nested2-2x2-1786503987707`。

其中：

- `batch-summary.json`、`server-result/manifest.json`：服务端批次清单和逐 case 状态；
- `server-result.zip`、`server-result/`：输入、各 LLM 阶段、A2UI、诊断和耗时；
- `device-widget-batch-hilog.txt`：纯净批跑日志；
- `device-screenshots/`：q1–q8、q9–q16、q13–q20 的真机截图。

## 6. 回归规则

后续修改需要至少满足：

1. 全量 pytest 通过；
2. 20 条服务端批次 failed=0；
3. 真机日志包含 20 个 rendered，且 schemaWarning/render failure 均为 0；
4. 人工复核 q6、q7、q10、q12、q16、q17；
5. 批量模式的准入放宽必须保持 request-scoped，禁止改成全局开关逻辑；
6. 可选素材允许安全删除，但禁止把语义不匹配素材带入最终 A2UI。
7. Theme Registry 必须保持 UX 颜色矩阵测试通过；高级组件不得重新引入未登记的状态色或旧品牌渐变。

## 7. 2026-08-12 高级组件标题顶部对齐复查

本轮逐项复查了 17 个高级业务组件。卡片 shell 继续统一负责 12 vp 安全内边距；组件内部不再
重复增加卡片级 padding。修复重点是标题自身的布局盒，而不是字体墨迹边界：带 20/24/32 vp
图标标题行的 `alignItems` 改为 `top`，标题型 support/peer 区域改为从顶部开始布局。

直接构造组件中，Weather、Sleep、Schedule、AppUsage、BluetoothDevice、Activity、Workout、
HeartRate、Battery 与 ResourceUsage 的标题路径已复查；Date 的 hero 数值属于主指标而非业务标题，
仍保持居中。Task、Memo、Call、Location、SystemMode、Settings 六个本地模板的根节点均保持
`Column + justifyContent:start`，首个可见 Text 从 shell 的 12 vp 内容起点开始。

同时修复 q19 的两类模型不稳定输出：

- 可选 `ResourceUsageOverview.icon` 错用清理动作图标时，只删除内容组件的可选图标，动作图标和事件保留；
- 在唯一允许 `ResourceUsageOverview` 和 `event.clean.memory` 的闭合 scope 中，如果模型把唯一合法
  `HeroActionLayout` 放到组件之后，服务重建该批准布局根，随后仍执行完整的布局、数据、素材和事件校验。

最终真机验收批次为 `nested2-2x2-1786501710268`：passed 20、failed 0，q19 成功耗时
4345.39 ms。验收后检测到并行任务部署的 UX 颜色 v12，已保留其全部颜色改动并只叠加 q19 的单根结构
归一化；当前服务镜像为 `widget-service:20260812T1038Z-ux-color-title-v13`，健康检查通过。端侧仍直接
访问公网 WebSocket，没有使用 HDC 反向映射。

完整证据目录：`/Users/yansf/workspace/GenerateUI/result/nested2-2x2-1786501710268`。目录包含 20 条输入、
每一步 LLM 输入输出、最终 A2UI、耗时、诊断、响应、真机 hilog，以及 q1–q8、q9–q16、q13–q20
三张真机截图。此前 q19 失败诊断分别保留在 `nested2-2x2-1786500996599`、
`nested2-2x2-1786501244038` 和 `nested2-2x2-1786501457806`。
