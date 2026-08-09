# 代码库索引

> 按模块分类的代码库地图。每条给出文件路径、一句话职责与关键符号，便于快速定位。
> 方案设计细节以 `docs/云侧方案设计.md` 为准；运行方式见 `widget_service/README.md`。

## 1. 服务入口与运行

| 文件 | 职责 | 关键符号 |
| --- | --- | --- |
| `widget_service/cloud/start_websocket_server.py` | 服务入口，FastAPI 应用组装与 uvicorn 启动 | `create_app()`、`run_local_server()`、模块级 `app`、`/health` |
| `widget_service/README.md` | 安装、运行、联调说明 | 启动命令 `py -3.12 cloud\start_websocket_server.py` |
| `widget_service/pyproject.toml` | PEP 621 项目元数据、依赖、pytest/ruff 配置 | `packages=["cloud"]`、`testpaths=["tests"]`、`pythonpath=["cloud"]` |
| `widget_service/requirements.txt` | 扁平依赖清单（含 dev 工具） | |

## 2. 路由与 API

| 文件 | 职责 | 关键符号 |
| --- | --- | --- |
| `widget_service/cloud/api/routes.py` | WebSocket 工具路由与统一 WS 协议编排 | `APIRouter(prefix="/api/v1")`、`_serve_operation_websocket()`、`getWidgetCapabilityOverview` / `getDataCapabilitySchemas` / `generateWidgetCard` / `generateWidgetCardCompactDsl` / `generateWidgetCardCompactDslWithDirective`（临时）/ `generateWidgetCardTerseDslNested2` |
| `widget_service/cloud/api/schemas.py` | 请求/响应 Pydantic 模型 | `GenerateWidgetCardRequest`、`CapabilityOverviewRequest/Response`、`DataCapabilitySchemasRequest/Response` |

## 3. 生成编排（核心）

| 文件 | 职责 | 关键符号 |
| --- | --- | --- |
| `widget_service/cloud/services/widget_generation_service.py` | 卡片生成主编排 | `WidgetGenerationService.generate_widget_card`（:251 主流程）、`generate_widget_card_a2ui_form`（:1028）、`generate_widget_card_compact_dsl`（:1053）、`generate_widget_card_terse_dsl_nested2`（:1093）、`_generate_widget_card_with_policy`（:1134） |
| `widget_service/cloud/services/generation_pipeline.py` | 生成路由策略与 DSL Processor | `GenerationRoutePolicy`、`DslProcessorKind`（STANDARD_A2UI / DESIGN_COMPACT / TERSE_NESTED2）、`StandardA2UIProcessor` / `DesignCompactProcessor` / `TerseNested2Processor`、`get_dsl_processor()` |
| `widget_service/cloud/services/prompt_builder.py` | 构造 LLM 输入消息 | `PromptBuilder.build`、`build_design_token`、`build_terse_dsl_nested2`、`build_repair` |
| `widget_service/cloud/services/card_spec_builder.py` | 组装端侧刷新契约 CardSpec | `CardSpecBuilder.build` |
| `widget_service/cloud/services/task_spec_builder.py` | 组装模型任务输入 TaskSpec | `TaskSpecBuilder.build` |
| `widget_service/cloud/services/retry_controller.py` | 模型失败/校验失败的重试与 repair 编排 | `RetryController.run` |
| `widget_service/cloud/services/response_planner.py` | 生成面向主 Agent 的状态响应 | `ResponsePlanner.plan` |
| `widget_service/cloud/services/artifact_store.py` | 保存生成产物 | `ArtifactStore.save` |
| `widget_service/cloud/services/edit_request_normalizer.py` | 编辑模式请求归一化 | `EditRequestNormalizer.normalize_create/normalize_edit` |
| `widget_service/cloud/services/source_artifact_repository.py` | 读取上一版 artifact | `SourceArtifactRepository.load` |

### 3.5 模板检索缓存（Search）

| 文件 | 职责 | 关键符号 |
| --- | --- | --- |
| `widget_service/cloud/search_integration/vendored_loader.py` | vendored search 导入（sys.path 注入 + guard） | `search_available()`、`search_template` |
| `widget_service/cloud/search_integration/adapter.py` | 请求映射 + SearchDecision 路由 | `SearchIntegrationAdapter.lookup`、`SearchDecision`、`default_input_data_mapper` |
| `widget_service/vendor_search/` | vendored search 模块（字节级拷贝，勿手改） | `search/` 包 + `api_schema.py`；来源见 `VENDORED.md` |
| `widget_service/docs/search_cache_integration.md` | 整合设计文档 | |

## 4. 数据模型与协议

| 文件 | 职责 | 关键符号 |
| --- | --- | --- |
| `widget_service/cloud/models/generation.py` | 生成相关数据模型 | `CandidateDataBinding`、`CardSpec`、`TaskSpec`、`GenerationOptions`、`DeviceContext` |
| `widget_service/cloud/models/artifact.py` | 产物模型 | `WidgetArtifact` |
| `widget_service/cloud/models/capability.py` | 能力模型 | `DataCapability`、`EventCapability`、`AssetCapability` |
| `widget_service/cloud/models/service.py` | 服务响应包络与重试结果 | `GenerateWidgetCardResponse`、`RetryResult` |
| `widget_service/cloud/services/compact_dsl_protocol.py` | Compact DSL 协议规则（组件/属性白名单） | |
| `widget_service/cloud/services/compact_dsl_a2ui_converter.py` | Compact DSL → 标准 A2UI 转换 | `convert_compact_dsl_to_a2ui` |
| `widget_service/cloud/services/terse_dsl_nested2_converter.py` | TerseDSL-Nested-2 → A2UI 转换 | `convert_terse_dsl_nested2_to_a2ui` |
| `widget_service/cloud/services/protocol_registry.py` | A2UI/设计协议 profile 注册与读取 | `A2UIProtocolRegistry`、`read_design_prompt` |
| `widget_service/cloud/convert_compact_dsl_to_a2ui.py` | 命令行小入口 | `main()` |

## 5. 模型客户端与提供商

| 文件 | 职责 | 关键符号 |
| --- | --- | --- |
| `widget_service/cloud/custom/a2ui_model_client.py` | 业务侧统一模型入口（含 mock 开关） | `A2UIModelClient.generate`、`generate_repair`、`_load_mock_data`（读 `cloud/custom/mock*.dat`） |
| `widget_service/cloud/custom/model_runtime.py` | 应用生命周期共享的模型运行时（并发/超时） | `ModelExecutionRuntime` |
| `widget_service/cloud/custom/unified_model_client.py` | 主备路由/重试编排 | `UnifiedModelClient`（master=deepseek_platform，fallback=llmclient） |
| `widget_service/cloud/custom/deepseek_platform_client.py` | DeepSeek Platform WS 通道（HMAC 签名） | `DeepSeekPlatformClient.generate`、`_build_token` |
| `widget_service/cloud/custom/llmclient.py` | OpenAI 兼容 WS 流式客户端 | `stream_genui()` |
| `widget_service/cloud/custom/mep_model_transport.py` | MEP HTTP 通道 | `MepModelTransport` |
| `widget_service/cloud/custom/model_transport.py` | 通道类型定义 | `ModelBackend`（mep/openai）、`ModelProvider` |

## 6. 能力注册与裁决

| 文件 | 职责 | 关键符号 |
| --- | --- | --- |
| `widget_service/cloud/services/capability_registry.py` | 按 App/ROM 版本加载能力目录（含缓存） | `CapabilityRegistry`、`resolve` |
| `widget_service/cloud/services/device_capability_resolver.py` | 裁决数据/事件/素材候选 | `DeviceCapabilityResolver.resolve_generation_data_bindings` |
| `widget_service/cloud/services/ids_client.py` | IDS 客户端（设备能力查询） | `enable_ids_mock` 开关 |

## 7. 校验器

| 文件 | 职责 | 关键符号 |
| --- | --- | --- |
| `widget_service/cloud/services/card_validator.py` | 统一校验入口 | `ArtifactValidator` |
| `widget_service/cloud/services/validator.py` | 基础校验 | |
| `widget_service/cloud/services/widget_directive.py` | 端侧指令帧 | |
| `widget_service/cloud/services/card_validation/` | 校验规则集（从 skills 批量同步，CodeCheck 后落微服务侧） | `pipeline.py`、`protocol_validator.py`、`binding_validator.py`、`component_validator.py`、`source_parser.py`、`effective_capability_validator.py` 等 |

## 8. 配置与环境变量

| 文件 | 职责 | 关键符号 |
| --- | --- | --- |
| `widget_service/cloud/config/config.py` | pydantic-settings 配置（`WIDGET_SERVICE_` 前缀） | `Settings`、`get_settings()`（lru_cache 单例） |
| `widget_service/.env.example` | 环境变量样例 | `WIDGET_SERVICE_DEEPSEEK_*`、`WIDGET_SERVICE_ENABLE_*_MOCK`、`WIDGET_SERVICE_SERVER_HOST/PORT` |
| `widget_service/cloud/app/logger.py` | 日志配置 | `logger` |

## 9. 工具类

| 文件 | 职责 | 关键符号 |
| --- | --- | --- |
| `widget_service/cloud/utils/base_utils.py` | 通用工具与 STS 适配 | `STSConfig` |
| `widget_service/cloud/utils/download_file_from_url.py` | URL 下载 | |
| `widget_service/cloud/utils/upload_file_obs.py` | OBS 上传 | |
| `widget_service/cloud/utils/file.py` | 文件工具 | |
| `widget_service/cloud/core/json_pointer.py` | RFC 6901 JSON Pointer | |

## 10. 错误码

| 文件 | 职责 | 关键符号 |
| --- | --- | --- |
| `widget_service/cloud/errors/codes.py` | 错误码枚举 | `ErrorCode` |
| `widget_service/cloud/errors/errors.py` | 异常类型 | `SourceArtifactError` 等 |
| `widget_service/cloud/errors/status_mapping.py` | 错误码→状态映射 | |

## 11. 测试

| 文件 | 类型 | 说明 |
| --- | --- | --- |
| `widget_service/tests/test_service_units.py` | 单元 | 最大的单测集合（settings/IDS/能力注册表/协议/请求模型/日志等） |
| `widget_service/tests/test_model_routing.py` | 单元 | 模型路由、DeepSeek Platform 签名、Fake transport/websocket |
| `widget_service/tests/test_tool_dispatch_routes.py` | 路由集成 | TestClient + mock 模型 + 断言 artifact 保存 |
| `widget_service/tests/test_multi_round_edit.py` | 路由集成 | 编辑模式多轮，`editable_artifact_storage` fixture |
| `widget_service/tests/test_compact_dsl_protocol.py` / `test_compact_dsl_a2ui_converter.py` | 单元 | Compact DSL 协议与转换 |
| `widget_service/tests/test_widget_directive.py` / `test_websocket_metrics.py` | 单元 | 指令帧 / WS 指标 |
| `widget_service/tests/test_running_ws_server.py` / `test_running_ws_features.py` / `test_running_ws_multi_round.py` | 联调 | 需先启动服务；未启动时 skip |
| `widget_service/tests/pressure_test_ws.py` / `ws_response_parser.py` | 工具 | 压测脚本 / 响应解析 |

## 12. 文档（根 docs/）

| 文件 | 说明 |
| --- | --- |
| `docs/云侧方案设计.md` | 唯一权威方案文档（端到端流程、接口、能力注册表、校验、降级） |
| `docs/generateWidgetCard数据流.md` / `generateWidgetCardCompactDsl数据流.md` / `generateWidgetCardTerseDslNested2数据流.md` | 各接口真实方法调用链 |
| `docs/第一二四接口内部流程图.md`、`docs/多轮卡片编辑开发方案.md`、`docs/系统深浅色自适应云侧改造方案.md` | 专项设计 |
| `docs/鸿蒙桌面卡片A2UI协议完整规范.md` | A2UI 协议规范 |
| `docs/system_prompt.txt` / `edit_system_prompt.txt` / `repair_system_prompt.txt` | 模型提示词（配置引用） |
| `widget_service/docs/method_usage.md` | 接口/方法详细用法 |
| `widget_service/docs/schemas/` | 各接口 JSON schema |

## 13. Skills 目录

| 目录 | 说明 |
| --- | --- |
| `skills/harmony-card-generation-online/` | 在线云侧编排 Skill（目标链路） |
| `skills/harmony-card-generation-offline/` | 离线直出 Skill（兜底/调试/历史视觉参考） |
| `skills/harmony-card-generation-compact-dsl-online/` / `skills/harmony-card-generation-design-compact-dsl-online/` | Compact DSL 在线 Skill |
| `skills/harmony-card-generation-online-directive/` | 指令化在线 Skill |
| `skills/harmony-card-template-generation/` | 模板驱动生成 Skill |
| `skills/harmony-card-design-generation/` | 设计生成 Skill |

## 14. 根目录其他文件

| 文件/目录 | 说明 |
| --- | --- |
| `AGENTS.md` | 项目背景、CodeCheck 约束、协作规范 |
| `CLAUDE.md` | AI 助手工作手册（本仓库约定） |
| `docs/CODEBASE_INDEX.md`（本文件） | 代码库索引 |
| `docs/KNOWLEDGE.md` | 项目经验记录 |
| `harmony-card-dsl-validation/` | DSL 校验相关 |
| `template/` / `testdata/` / `resources/` | 模板/测试数据/资源 |
| `release.sh` | skills 打包发布脚本 |
| `widget_service/vendor_search/` | vendored search 模块（字节级复制自 subagent_genui@origin/search） |
