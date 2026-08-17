# 模板路由与双协议产物设计

## 设计目标

模板是 `generateWidgetCardCompactDsl` create 场景的内部生成方式，不新增外部协议，也不改变原始 dev
失败、降级、OBS 或多轮编辑契约。原始入口只负责构造既有 `GenerationRoutePolicy`，随后调用模板路由门面。

## 路由状态机

```text
generateWidgetCardCompactDsl
  └─ route_compact_generation
       ├─ edit
       │    └─ 原始 Compact 流程
       └─ create
            ├─ 准备 dev 能力裁决、CardSpec、TaskSpec
            ├─ 第一层 LLM：选择 Theme 和一个或多个业务模板
            ├─ 服务端完整覆盖校验
            │    ├─ 未覆盖任一 candidateOutputField → 原始 Compact 流程
            │    └─ 全部覆盖 → 锁定模板路由
            ├─ 第二层 LLM：只生成受限布局和模板调用
            ├─ 服务端解析、参数校验、模板展开
            ├─ 内部 A2UI 适配当前 dev Form profile
            ├─ A2UI → A2UI-Compact
            ├─ dev Compact Processor → 最终 A2UI
            ├─ dev ArtifactValidator
            └─ ArtifactStore 保存 genui + designcompactdsl
```

## 为什么先归档 Compact 再确定最终 A2UI

模板编译器先产生内部 A2UI，但 artifact 中的 A2UI-Compact 会在后续 edit 中由原始 dev Processor 读取。
如果首次展示直接保存模板编译器输出，后续 Processor 的规范化可能造成视觉或逻辑漂移。

因此本模块执行以下闭环：

1. 模板内部 A2UI 仅作为中间结果。
2. 适配当前 dev 的 `catalogId`、root 尺寸、圆角和裁剪约束。
3. 确定性生成 A2UI-Compact。
4. 使用原始 dev Compact Processor 将该 Token 转回标准 A2UI。
5. 将回转结果作为首次展示的最终 A2UI，并将同一个 Token 写入 `designcompactdsl`。

这样首次展示和二次更新共享同一条 Compact 转换链。

## 失败与回退边界

| 阶段 | 行为 | 原因 |
|---|---|---|
| edit 请求 | 原始流程 | 二次更新不重新选择模板 |
| 无真实模型运行时 | 原始流程 | 保持 dev mock 和既有测试行为 |
| 第一层拒绝或异常 | 原始流程 | 尚未承诺模板可完整表达 |
| 确定性覆盖失败 | 原始流程 | 任一用户选定字段无法由模板表达 |
| 第二层或模板编译失败 | 返回 failed | 模板路由已经锁定，禁止静默换实现 |
| Compact 归档或 Validator 失败 | 返回 failed | 禁止保存无法稳定编辑的半成品 |

`before_model_call` 由门面包装为单次通知。第一层已经触发通知时，即使回退原始模型，也不会重复下发开始事件。

## 对原始 dev 的修改边界

`widget_generation_service.py` 只增加公共入口 import，并把 Compact 路由末尾的原始调用替换成一次
`route_compact_generation(...)` 调用。A2UI Form、TerseDSL-Nested-2、能力注册、API、配置、日志和批量接口
均不需要为模板功能修改。
