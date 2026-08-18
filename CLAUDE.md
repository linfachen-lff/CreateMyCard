# CLAUDE.md

面向参与本仓库开发的 AI 编码助手的工作手册。项目背景、协作规范与静态检查约束以 `AGENTS.md` 为准，本文件只维护「如何在此仓库高效工作」的简明约定。

## 项目定位

小艺 App 的 AI 桌面卡片生成云侧微服务（`widget_service/`，FastAPI + WebSocket，Python 3.12）。用户输入自然语言需求后，云侧调用 DeepSeek 模型生成 HarmonyOS A2UI Form 卡片，返回给端侧预览与上桌。

## 文档优先级

1. `docs/云侧方案设计.md` —— 方案设计的唯一权威来源，方案变更先同步它
2. `AGENTS.md` —— 项目背景、CodeCheck 约束、协作规范
3. `docs/CODEBASE_INDEX.md` —— 代码库分类索引（第 3 步建立）
4. `docs/KNOWLEDGE.md` —— 项目经验/踩坑记录（第 4 步建立）
5. `widget_service/README.md` / `widget_service/docs/method_usage.md` —— 运行与接口用法

## 关键入口文件

- 服务入口：`widget_service/cloud/start_websocket_server.py`（`create_app()`，默认 `127.0.0.1:8855`）
- WS 路由：`widget_service/cloud/api/routes.py`（`/api/v1/ws/tools/*`）
- 生成编排：`widget_service/cloud/services/widget_generation_service.py`（`generate_widget_card` 主流程）
- 提示词构建：`widget_service/cloud/services/prompt_builder.py`
- 配置：`widget_service/cloud/config/config.py`（pydantic-settings，`WIDGET_SERVICE_` 前缀环境变量，`.env.example` 为样例）
- 模型客户端：`widget_service/cloud/custom/`（a2ui_model_client / unified_model_client / model_runtime / deepseek_platform_client / llmclient / mep_model_transport）
- 测试：`widget_service/tests/`（pytest + pytest-asyncio，`pythonpath=["cloud"]`）

## 本次工作全局约定（dev-search 分支，search 模块整合）

- **语言**：文档、回复、面向用户的说明一律使用简体中文（沿用 AGENTS.md）。
- **开发方式**：TDD 小步快跑。每个修改要么落入既有测试用例，要么新增最小测试用例（不要滥发测试）；先落测试（预期红），再实现（转绿）。
- **mock 数据**：测试若原本需要真实 DeepSeek API，一律先用 mock 数据，并在测试脚本中打印 `MOCK DATA` 标记提醒自己。
- **提交**：每个修改一个 commit，提交信息用中文/英文均可但要清晰。
- **文档**：每个有影响的修改后及时更新相关文档（方案、索引、knowledge）。
- **代码改动**：尽量少改动现有代码；不主动修既有 bug；发现影响 search 模块的 bug 必须向用户上报。

## vendored search 模块指针

- search 模块从 `D:\Program\work\subagent_genui` 仓库的 `origin/search` 分支按字节复制到 `widget_service/vendor_search/`（低耦合、可整体替换）。
- 集成适配层在 `widget_service/cloud/search_integration/`（`vendored_loader.py` + `adapter.py`），由 `SearchIntegrationAdapter` 把生成请求映射成 `SearchRequest` 并路由 `SearchDecision`。
- 契约与设计：`widget_service/docs/search_cache_integration.md`、`docs/云侧方案设计.md` 的「模板检索缓存」小节。
- 注意：`vendor_search/` 内的 `search` 与 `api_schema` 顶层名会进入进程 `sys.path`，仓库内不得新增同名顶层模块。
