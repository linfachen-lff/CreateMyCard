# 运行时模板说明

这里不保存带样例业务数据的手写 JSONL。运行时模板由 `search.cards_import` 从
`cards/prompts` 的完整输入结构生成并写入 SQLite：

- `reference_jsonl` 只有组件、静态标签和标准 `path`；
- 实际值仅在结构唯一命中后由绑定器写入 `rendered_jsonl` 数据行；
- 动态对象数组使用标准 List `componentId + path`；
- 未批准的标量数组自身绑定和嵌套动态数组不会被私有语法模拟，但仍参与完整结构 Hash；
- 任意层级空数组或异构数组会拒绝整份模板。

历史 `cards/dsl` 文件是视觉参考素材，不直接作为 Search 运行时模板。
