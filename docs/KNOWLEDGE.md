# 项目经验记录（Knowledge）

> 记录探索与开发中获得的、不可直接从代码静态推得的经验与坑。随项目持续补充。
> 每个条目带日期与来源，避免过期信息误导。

## mock 数据体系（2026-08-09，探索所得）

- 模型 mock 开关：`WIDGET_SERVICE_ENABLE_A2UI_MODEL_MOCK`（默认 `true`）。开启时 `A2UIModelClient.generate()` 直接读取 `cloud/custom/mock*.dat` 返回，不发起任何真实模型调用。
  - mock 文件：`mock.dat`、`mock.compact-dsl.dat`、`mock.design-compact-dsl-2x2.dat`、`mock.design-compact-dsl-2x4.dat`、`mock.terse-dsl-nested-2.dat`。
- 类似开关：`enable_ids_mock`（读 `cloud/data/mock/ids_res.json`）、`enable_artifact_download_mock`（读 workspace/mock_obs）。
- 测试注入模式（不用 unittest.mock）：`monkeypatch.setattr(A2UIModelClient, "generate", fake)` 替换类方法；`monkeypatch.setattr(ArtifactStore, "save", capture)` 捕获产物；Fake transport/websocket 注入 `ModelExecutionRuntime`。参考 `test_tool_dispatch_routes.py`、`test_model_routing.py`。
- 无 conftest.py。测试文件自行 `sys.path.insert(0, CLOUD_ROOT)`；pyproject 另有 `pythonpath=["cloud"]` 双保险。

## 模型路由与通道（2026-08-09）

- 三条物理通道：`mep`（HTTP POST /predict，CLOUDSOA-HMAC 签名）、`deepseek_platform`（WS，HMAC token，STS 取密钥）、`llmclient`（OpenAI 兼容 WS 流式）。
- 主备：`WIDGET_SERVICE_OPENAI_MASTER_CLIENT=deepseek_platform`，`WIDGET_SERVICE_OPENAI_FALLBACK_CLIENT=llmclient`，`enable_openai_fallback=true`。`UnifiedModelClient` 编排指数退避重试。
- STS 密钥目前是内存 mock（`ids.secret.key`），真正接入需替换 STS 适配。

## 三条生成路由与 DslProcessorKind

| 端点 | processor_kind | model_format | 校验策略 |
| --- | --- | --- | --- |
| `generateWidgetCard` | STANDARD_A2UI | a2ui-form | 非阻断 |
| `generateWidgetCardCompactDsl` | DESIGN_COMPACT | compact-dsl | `validation_failure_blocking=True`，`stores_design_token=True` |
| `generateWidgetCardTerseDslNested2` | TERSE_NESTED2 | terse-dsl-nested-2 | 同上 |

- compact/terse 端点构造的 `GenerationRoutePolicy.processor_kind` 可用于精确门禁（只影响某条路由）。

## 生成主流程关键阶段（widget_generation_service.generate_widget_card）

`request 归一化 → 能力 registry → 协议 profile → DeviceCapabilityResolver 裁决绑定 → CardSpec/TaskSpec → PromptBuilder 构建 prompt → A2UIModelClient.generate → DslProcessor.process → ArtifactValidator → RetryController.run → _build_artifact → ArtifactStore.save → ResponsePlanner.plan`

- `before_model_call` 回调：在模型调用前发 AIWidgetStart 指令帧，保证 WS 配对。短路模型调用时也必须保持调用该回调。

## search 模块（vendored）要点（2026-08-09）

- 真实代码在 `D:\Program\work\subagent_genui` 仓库的远程分支 `origin/search`（本地工作区只是 NotImplementedError 占位，**务必用 git 读**）。
- 字节级复制到 `widget_service/vendor_search/`（`search/` 包 + `api_schema.py`）。更新方式：重新 `git archive origin/search api_schema.py search` 覆盖，并记录新源 commit。
- 契约：`SearchRequest(query, input_data)`、`SearchResult` 三分支（structure_match → `rendered_jsonl` 直出；keyword_match → `reference_jsonl` few-shot；miss）。
- `search_template()` 入口 async，内部 SQLite/FTS/绑定全同步；高并发需在 adapter 层 `asyncio.to_thread` 卸载（当前低并发可接受）。
- DB 不存在/不可用时返回 `MissResult(miss_reason="store_unavailable")` 优雅降级，不会抛异常。
- `get_default_search_service()` 是 `lru_cache(maxsize=1)`：`SEARCH_DB_PATH` 环境变量必须在首次调用前设置，换库需 `cache_clear()`。
- 依赖：`jieba>=0.42.1`（首次加载词典约数百 ms）。
- sys.path 约束：`vendor_search/` 进 `sys.path` 后，顶层名 `search`/`api_schema` 全局可见，仓库内不得新增同名顶层模块。

## deepseek key 设置（2026-08-09）

- 开箱即用：默认 mock 模式（`WIDGET_SERVICE_ENABLE_A2UI_MODEL_MOCK=true`），无需任何 key 即可跑通测试与本地启动。
- 真实调用：复制 `widget_service/.env.example` → `widget_service/.env`，按需填入（key 值由内部基建提供，无法代申请）：
  - 平台通道：`WIDGET_SERVICE_DEEPSEEK_PLATFORM_ACCESS_KEY`、`WIDGET_SERVICE_DEEPSEEK_PLATFORM_SECRET_KEY_STS_CONFIG_KEY`、`WIDGET_SERVICE_DEEPSEEK_PLATFORM_WS_URL`、`WIDGET_SERVICE_DEEPSEEK_PLATFORM_MODEL_NAME`。
  - 直接通道：`WIDGET_SERVICE_DEEPSEEK_API_KEY`、`WIDGET_SERVICE_DEEPSEEK_MODEL`、`WIDGET_SERVICE_DEEPSEEK_WS_URL`。
  - 服务器：`WIDGET_SERVICE_SERVER_HOST`（默认 127.0.0.1）、`WIDGET_SERVICE_SERVER_PORT`（默认 8855）。

## 第 5 步验证结果（2026-08-09，dev-search 分支基线）

- 环境：Python 3.12.10，`pip install -e .[dev]`。注意本机 `C:\Python312\Scripts` 写 console-script（`.exe`）会报 `WinError 2`（.deleteme 逻辑），但不影响库代码安装，只影响带 CLI 入口的包（websockets/watchfiles 等）的 `.exe` 生成。
- 测试基线：`pytest tests/test_service_units.py tests/test_model_routing.py tests/test_multi_round_edit.py tests/test_tool_dispatch_routes.py -q` → **279 通过 / 11 失败**。11 个失败均为 dev 分支既有（与本次改动无关），集中在：
  - terse/design-compact 转换相关：`test_terse_dsl_nested2_converts_nested_tree_to_standard_a2ui`、`test_terse_dsl_nested2_generation_uses_local_prompt_and_converter`、`test_a2ui_model_client_selects_design_compact_mock_by_task_size[2x2/2x4]`、`test_a2ui_model_client_converts_design_dsl_to_standard_dsl`、`test_design_converter_expands_latest_design_tokens`、`test_design_converter_reads_protocol_file_from_selected_design_profile`、`test_compact_route_mock_converts_design_dsl_before_saving`、`test_terse_nested2_route_mock_converts_local_dsl_before_saving`
  - 覆盖/快照相关：`test_cloud_registry_covers_offline_skill_capability_inventory`、`test_card_validation_snapshot_covers_all_online_runtime_files`
  - 典型原因：转换结果 `createSurface` 含 `width` 而测试断言不含（转换器行为与断言不一致）。**尚未修**（按用户约定不改既有 bug），搜索整合时注意 compact 转换路径的行为。
- 服务启动：mock 模式 `py -3.12 cloud\start_websocket_server.py` → `/health` 返回 `{"status":"ok"}`，无需任何 key。

## 已知既有隐患（2026-08-09）

- ✅ 已修：`a2ui_model_client.py:11` `import json_repair` 缺依赖，导致全部测试 collect 失败。已在 requirements.txt / pyproject.toml 补 `json_repair>=0.25.0` 并安装（0.62.0）。此问题会阻断测试运行，直接卡住 search 整合 TDD，故按约定修复并上报。
- `DesignCompactProcessor.process` 内部会经 `repair_compact_dsl_binding_paths`/`validate_compact_dsl_context` 改写源 DSL 绑定路径。search 短路喂入 rendered_jsonl 后需验证不破坏已绑定数据（search 整合测试重点）。
- 上节 11 个既有测试失败未修，需另立任务处理。
