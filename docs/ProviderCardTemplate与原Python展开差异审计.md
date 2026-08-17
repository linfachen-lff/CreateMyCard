# Provider CardTemplate 与原 Python 展开等价审计

> 更新日期：2026-08-17
> 适用范围：`CreateMyCard/widget_service` 的 Provider Bundle、CardTemplate、UX Mixed Prompt、
> 可信编译器与最终扩展 A2UI。
> 结论：代码级迁移已完成。所有 Provider-backed 业务高级组件的生产默认路径均为 CardTemplate；
> 原 Python 构造仅保留为测试 Shadow Oracle，不再是生产生成回退路径。

## 1. 验收原则

本轮迁移按以下规则验收：

1. 模板必须保持原 Python 的组件树、关键样式、尺寸、角色、组合布局和业务状态分支；“能展开”为 A2UI
   不能代替视觉与逻辑等价。
2. 反引号 `${...}` 和 `Expr(...)` 输出一个占满 `Text.content` 的端侧动态表达式，例如：

   ```text
   {{ ${/data/ViewWeather/current/condition} + '｜' +
      ${/data/ViewWeather/current/airQuality} }}
   ```

   模板展开期不读取样例值拼接字符串，也不拆成多个 `Text`。表达式语法以
   [genui_form 表达式语言](https://gitcode.com/GenerativeUI/genui_form/blob/develop/docs/genui-form-docs/har-capabilities/03-expression-language.md#表达式语法)
   为端侧契约。
3. 上游字段、CardSpec `writeResultTo`、模板 Binding 和最终 A2UI JSON Pointer 必须形成闭环；不存在的绑定
   不能通过样例值或空字符串伪造。
4. Python 构造只作为迁移基线参加 Golden 比较，不能在模板失败时替换生产结果。

## 2. 最终生产路由

`advanced-component-ux-registry.json` 中所有 Provider-backed 业务组件均为
`implementation: "template"`，不存在 `implementation: "terse-dsl"` 的临时项。

| 业务组件 | Provider Template | 迁移结果 |
| --- | --- | --- |
| WeatherOverview | `WeatherOverview@1` | 完整天气树、动态组合表达式、天气图标和组合角色已接通 |
| DateOverview | `DateOverview@1` | 日期/星期派生、2×2 Compact 与 Hero 结构已接通 |
| ScheduleOverview | `ScheduleOverview@1` | 时间线、地点、来源/时间/地点图标、Hero/Support 与尺寸分支已接通 |
| BatteryOverview | `BatteryOverview@1` | normal/charging/low、Ring、图标、Peer/Phone/Weather/Wide 已接通 |
| ResourceUsageOverview | `ResourceUsageOverview@1` | Ring、中心百分比、详情、图标和 Peer 结构已接通 |
| AppUsageOverview | `AppUsageOverview@1` | 时长分段、次数详情、图标和宽卡重排已接通 |
| ActivityOverview | `ActivityOverview@1` | 步数、热量、距离、三类图标和宽卡重排已接通 |
| WorkoutOverview | `WorkoutOverview@1` | 最近运动主指标、来源/热量图标已接通 |
| WorkoutOverview/countdown | `WorkoutCountdown@1` | 倒计时数值/单位、来源图标已接通 |
| HeartRateOverview | `HeartRateOverview@1` | Hero/Support、更新时间和图标已接通 |
| SleepOverview | `SleepOverview@1` | 时长分段、状态、睡眠窗口、Hero/Support 和来源图标已接通 |
| BluetoothDeviceOverview | `BluetoothDeviceOverview@1` | 连接态、Ring、素材、缺字段矩阵和手机组合已接通 |

Provider 的 `provider.json` 仍保持最小三字段能力关联：

```json
{
  "capabilityId": "ViewWeather",
  "dataSchema": {
    "path": "capabilities/app-11.7.5.205_rom-6.0/data_capabilities.json",
    "version": "app-11.7.5.205_rom-6.0"
  },
  "templates": ["WeatherOverview@1"]
}
```

上游 schema 可用时读取 `data_root` 下的正式路径；没有正式路径的 Provider 才使用 Bundle 内本地 schema。
Provider manifest 不复制正式能力注册表，也不要求修改其它团队维护的注册内容。

## 3. 已闭合的原差异项

### 3.1 动态字符串

CardTemplate 支持两种受限动态文本：

- ``Text(`${a}｜${b}`, ...)``：只允许字符串 Binding 与静态字符串，编译成单个 A2UI 表达式；
- ``Text(Expr(`${percent} <= 20 ? ...`), ...)``：允许经过语法白名单验证的运算、比较和三元表达式。

编译器拒绝表达式前后混入普通文本、非法 JSON Pointer、任意函数调用、属性访问和未声明 Binding。
最终 A2UI 保留动态表达式，不在生成期投影具体值。

### 3.2 Ring/图表

Battery、Resource 和 Bluetooth 的模板现已显式声明与 Python 相同的：

- `Progress.type = "ring"`；
- `value/total/color/backgroundColor/width/height/strokeWidth`；
- `Stack("overlay")`；
- 环中图标或环外百分比文本；
- 低电告警色、正常色、轨道色和各尺寸 Ring 大小。

A2UI Adapter 不再需要猜测或补默认图表属性。

### 3.3 可选素材和可选数据字段

模板语言提供两组声明式结构守卫：

- `IfParam/IfMissingParam`：根据模型是否传入已批准素材参数决定结构；
- `IfBind/IfMissingBind`：根据 TaskSpec schema 是否声明可选 Provider 字段决定结构。

守卫在可信服务端展开，最终 A2UI 不包含这些伪节点。静态编译要求：

- 可选 `Param/Asset` 必须位于对应 `IfParam` 分支；
- 可选 `Bind` 必须位于对应 `IfBind` 分支；
- 守卫名必须在 Template header 中声明；
- 素材必须属于本轮 TaskSpec，且 sceneTags 满足参数语义。

这使蓝牙无需为每种缺字段组合复制整份模板，同时仍严格复现 Python：左右耳、充电盒 7 种字段组合，
分别覆盖 2×2/2×4、单设备和手机组合。

### 3.4 状态、尺寸和组合角色

Compiler 不只依赖模型选择 Variant，还会使用可信事实再次约束：

- Battery Variant 前缀必须与 normal/charging/low 状态一致；
- 手机 + 耳机组合必须使用对应 `*Phone` 结构；
- Bluetooth disconnected/connected 必须与 `isConnected` 一致；
- Bluetooth 单设备、宽卡和手机组合 Variant 必须与实际字段形态一致；
- Provider Variant 的 size/role 必须与 Layout 推导出的 Hero/Support/Peer 位置一致；
- Date + Schedule 等组合必须满足固定顺序和尺寸专用结构。

错误 Variant 在模板实例化前失败，不会生成一个“数据正确但视觉结构错误”的 A2UI。

### 3.5 可信派生展示参数

日期日/星期、日程 `timeText`、App/Sleep 时长分段等原 Python 依赖的展示结构由受类型和来源约束的
确定性投影生成。它只负责上游协议没有直接提供的展示分段，不负责把 `${...}` 动态拼接提前求值。
动态 Provider 值仍通过 Binding 进入端侧 DataModel。

## 4. Python Shadow Golden 门禁

测试中的原 Python 构造继续保留，原因是它是这次“视觉和逻辑不变”要求的可执行基线。Golden 比较会：

1. 用同一个 TaskSpec 分别编译 Provider Template 和原 Python 构造；
2. 去掉运行时内容值、节点 ID 等允许差异；
3. 对组件顺序、父子数量、全部关键样式和结构属性做全等比较；
4. 要求 Provider 侧确实记录 Template ID，Python 侧不得记录 Template；
5. 要求最终 A2UI 不泄漏 `Template`、`_advancedComponent` 或任一结构守卫伪节点。

当前 Golden 覆盖：

- 11 个业务组件及 Workout Countdown；
- 2×2/2×4 和关键 Hero/Support/Peer 分支；
- Battery、Resource、Schedule、App、Activity、Workout、Countdown、Sleep、Bluetooth 可选素材；
- Sleep 状态/时间窗口分支；
- 手机 + 耳机正常、断连组合；
- Bluetooth 7 种可选电量字段 × 2 种尺寸 × 单设备/手机组合。

Provider Bundle 测试还会逐个实例化所有 Variant，验证 digest、schema、参数、绑定、节点/深度预算及最终
A2UI 可达性。状态负向测试确认错误电量状态、错误蓝牙连接态和错误蓝牙字段形态均会被拒绝。

## 5. 允许的实现差异

迁移后的 Template 与 Python 只保留两类有意差异：

1. Python Shadow 使用当前 TaskSpec 样例值生成静态内容；Provider Template 使用正式运行时表达式，因此
   `Text.content` 的具体值不同。Golden 将两者统一标记为 runtime expression 后比较结构。
2. Python 构造仍存在于代码中，但只供测试与显式 Shadow 工具使用，不在生产 Prompt、生产 Contract 或
   模板失败回退链路中出现。

除此之外没有视觉豁免清单。

## 6. 端侧联调检查项

代码级迁移完成后，端侧验证应继续确认：

- 端侧加载的是支持表达式语言的扩展 Form Catalog；
- CardSpec `writeResultTo` 与 A2UI 表达式 JSON Pointer 一致；
- `updateDataModel` 注入目标 Surface 与组件 Surface 相同；
- Ring `Progress`、动态图标和表达式文本在首次数据与刷新数据下均可见；
- 断连、低电、字段缺失和 2×2/2×4 切换不会复用旧 Surface 数据。

端侧运行环境问题不得通过恢复 Python 生产回退或在云侧投影样例值规避。
