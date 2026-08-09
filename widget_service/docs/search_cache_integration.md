# Search Cache 整合设计（模板检索缓存）

> 生成服务接入 vendored search 模块的实现说明。方案总览见根目录
> `docs/云侧方案设计.md` 的「模板检索缓存（Search Cache）」小节。

## 目标

访问 `generateWidgetCardCompactDsl` 家族端点生成卡片前，先查模板检索库：

- `structure_match`（结构化 JSON 结构 Hash 唯一命中）→ 直接出卡，跳过模型重生成；
- `keyword_match`（用户 query 关键词命中）→ 把 `reference_jsonl` 作为 few-shot 注入 prompt；
- `miss`（未命中或检索不可用）→ 按原流程生成，无 few-shot。

## 代码布局

```text
widget_service/
  vendor_search/                          # vendored search 模块（字节级拷贝，可整体替换）
    api_schema.py                         # SearchRequest/SearchResult + DeepSeek chat 类型
    search/                               # 完整 search 包（retriever/repository/service/...）
    VENDORED.md                           # 来源分支/commit 与更新命令
  cloud/search_integration/
    __init__.py                           # 导出 SearchDecision / SearchIntegrationAdapter
    vendored_loader.py                    # sys.path 注入 + import guard（优雅降级）
    adapter.py                            # 请求映射 + SearchDecision 路由
```

### vendored 来源与更新

- 来源仓库 `D:\Program\work\subagent_genui`，分支 `origin/search`，源 commit
  `a505129c46a1bb986d4e191976b5e8fe089a70ee`。
- 拷贝命令与字节校验见 `vendor_search/VENDORED.md`。**被拷贝文件不得手改**；
  对 search 的本地适配一律放在 `cloud/search_integration/`。

### 导入机制

`vendored_loader` 在模块加载时把 `widget_service/vendor_search/` 插入 `sys.path`
（插到 `cloud` 之后），再 `import search` / `import api_schema`。任何导入失败
（如 jieba 缺失、文件缺失）记录到 `_IMPORT_ERROR`，`search_available()` 返回 False，
adapter 一律返回 `miss("vendored_unavailable")`，不阻断服务启动。

**约束**：`vendor_search/` 进 `sys.path` 后，顶层名 `search`/`api_schema` 全局可见，
仓库内不得新增同名顶层模块。

## Adapter

`SearchIntegrationAdapter`（`cloud/search_integration/adapter.py`）：

- `build_search_request(request)`：`userQuery → query`，`input_data` 由可配置
  `input_data_mapper` 生成（默认序列化 `candidateDataBindings` 为 `{"dataBindings": [...]}`）。
- `lookup(request, *, service=None, enabled=True)`：执行检索并返回 `SearchDecision`。
  - `enabled=False` → `outcome="disabled"`；
  - vendored 不可用 → `miss("vendored_unavailable")`；
  - 检索异常 → `miss("search_error")`（双保险优雅降级）；
  - 否则按 `outcome` 投影为 `SearchDecision`。
- `_configure_default_db_path()`：首次用默认服务前，把 `settings.search_db_path`
  写入 `SEARCH_DB_PATH`（`get_default_search_service` 是 `lru_cache(maxsize=1)`，
  env 必须先于首次调用）。

`SearchDecision` 是 vendored `SearchResult` 的本地投影：
`outcome` ∈ {structure_match, keyword_match, miss, disabled}，
`cached_dsl`（structure_match 的 rendered_jsonl）、`few_shot`（keyword_match 的 reference_jsonl）。

## 生成服务拦截

`WidgetGenerationService.generate_widget_card` 在 prompt 构建前（TaskSpec 之后）：

```python
search_decision = await _search_adapter.lookup(
    request,
    enabled=bool(
        settings.enable_search_cache
        and policy.processor_kind == DslProcessorKind.DESIGN_COMPACT
        and generation_mode != "edit"
    ),
)
use_cached_dsl = search_decision.outcome == "structure_match" and bool(
    search_decision.rendered_jsonl
)
few_shot = search_decision.few_shot
```

- **structure_match**：`generate_source_dsl` 闭包直接返回 `rendered_jsonl`（不调模型，
  仍先发 `before_model_call` 指令保持 AIWidgetStart/End 配对）。`rendered_jsonl` 是
  Compact DSL，直接进入既有 `DesignCompactProcessor.process` → 校验 → artifact → 保存。
- **失败回退**：若缓存 DSL 转换/校验失败，`fallback_generation` 作为
  `RetryController.run` 的 repair 回调执行**一次无 few-shot 的模型生成**
  （`max_repair_attempts=1`、`retry_on_quality_failure=(原值 or use_cached_dsl)`）。
  不回退修复缓存模板；回退输出若仍有错，按 compact 的 `validation_failure_blocking`
  返回 `VALIDATION_FAILED`。
- **keyword_match**：`reference_jsonl` 传入 `PromptBuilder.build_design_token`
  的 `reference_jsonl` 参数，user 消息含 `referenceExamples` 字段（仅新建模式）。

## 配置

| 环境变量 | 默认 | 说明 |
| --- | --- | --- |
| `WIDGET_SERVICE_ENABLE_SEARCH_CACHE` | `false` | 总开关 |
| `WIDGET_SERVICE_SEARCH_DB_PATH` | 空 | 运行时数据库路径；为空用 vendored 默认（`SEARCH_DB_PATH` 优先） |

## 建库与真实数据（步骤 7）

用 `cloud/search_integration/build_db.py` 从 `subagent_genui/taskspec/md` 的 20 个
`q*_artifact.md` 构建模板库：

```bash
cd widget_service
PYTHONPATH=cloud py -3.12 -m cloud.search_integration.build_db \
  --source D:/Program/work/subagent_genui/taskspec/md \
  --db vendor_search/search/data/templates.sqlite3 --replace
```

- 转换逻辑：`taskspec.dataModelSchema` 经 `deflate.py` 降维为 sampleValue 实例 → `input_json`；
  `designcompactdsl` 去掉 data 行 → `reference_jsonl`；`structure_hash` 由 `input_json` 计算；
  description/tags 从 cardspec.description + capabilityId + userQuery 派生。
- 结果：**20/20 张模板入库**。3 张（q04/q09/q15）`Progress.value` 绑定字符串路径，bind 校验失败，
  只能走 keyword_match（structure_match 会回退模型）。
- 运行库在 `vendor_search/search/data/templates.sqlite3`（gitignore，不提交）。

真实检索三通路已验证：q01 结构命中（structure_match）、「电量 卡片」关键词命中 q09、
无关 query → miss。

## 尺寸敏感限制（重要）

缓存命中的模板是**按尺寸建库**的。`DesignCompactProcessor` 会校验 root 尺寸与请求 size
一致（如 2x4 需 320x160）。因此 2x4 请求不会命中 2x2 模板——structure_match 命中后转换失败
→ 走无 few-shot 模型回退，产物仍正确但丢失缓存收益。这是当前设计（search 不感知尺寸）的固有
限制；后续 search 更新时可考虑把 size 纳入模板键。

## 测试（全部 MOCK DATA）

| 文件 | 覆盖 |
| --- | --- |
| `tests/test_search_vendored_loader.py` | vendored 导入 + 真实检索三条通路（内存 SQLite）、ambiguous、store_unavailable 降级、Button+Image 补丁 |
| `tests/test_search_integration_adapter.py` | adapter 映射/开关/三分支/异常降级/自定义 mapper/显式 input_data |
| `tests/test_search_build_db.py` | deflate/parse/build_record/临时库可检索（内嵌夹具） |
| `tests/test_search_cache_integration.py` | route 级：短路、回退、few-shot 注入、miss、默认关闭、a2ui-form 忽略、**真实全通路 structure_match（临时库）** |

## 已知风险与限制

- vendored 模板（来自 MCP 卡片 prompt）的属性名可能与 widget 的 design-compact-dsl
  profile 不完全一致；由「缓存 DSL 失败 → 无 few-shot 正常生成回退」兜底，命中率/误用
  由此吸收。后续靠可配置 `input_data_mapper` 与真实模板库对齐。
- `search_template` 内部 SQLite/FTS/绑定全同步，入口 async；高并发时需在 adapter 内
  `asyncio.to_thread` 卸载（当前低并发可接受）。
- `get_default_search_service` 的 `lru_cache`：`SEARCH_DB_PATH` 必须在首次调用前设置；
  测试用注入 service 绕过。
- wheel 打包 `packages=["cloud"]` 不含 `vendor_search`：目录部署无碍；若 wheel 部署需
  在 `[tool.hatch.build.targets.wheel].force-include` 补 `vendor_search`。
