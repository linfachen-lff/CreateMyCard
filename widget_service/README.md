# Widget Service

Python 3.12 FastAPI microservice for AI widget card generation.

The service follows `docs/AGENTS.md`:

- Main Agent selects candidate capabilities.
- The first interface applies IDS installed-app matching only to dependency package names listed in `WIDGET_SERVICE_IDS_INSTALLATION_FILTER_PACKAGE_NAMES`; the default list contains only `com.huawei.hmos.health.core`. The generation interface consumes the available list, builds final `CardSpec`, constructs `TaskSpec`, calls the A2UI model client, validates artifact, and returns structured status.
- Data capabilities, event capabilities, and assets are selected by App/ROM left-closed,
  right-open ranges in `cloud/data/capabilities/registry_ranges.json`.
- `TaskSpec.dataModelSchema` is projected directly from each capability `outputSchema`: the service reads `type`, `description`, and `sampleValue` from the selected leaf and writes it at `writeResultTo + candidateOutputFields` path. There is no separate data-model mapping file or runtime field-renaming layer.
- `romVersion` is the only accepted ROM field name. A full value such as `CLS-AL30 6.0.0.328` is normalized to the major/minor version `6.0`.
- All five interfaces currently map App `[11.7.5.205, 12.0.0.0)` and ROM `[6.0, 7.0)` to `app-11.7.5.205_rom-6.0`. An unmatched version falls back to this default when `WIDGET_SERVICE_ENABLE_DEFAULT_CAPABILITY_REGISTRY_FALLBACK=true`.
- `generateWidgetCard` selects `mep` or the composite `openai` route through
  `WIDGET_SERVICE_A2UI_FORM_MODEL_BACKEND`.
  `generateWidgetCardCompactDsl` selects its backend through `WIDGET_SERVICE_DESIGN_COMPACT_MODEL_BACKEND`, loads
  the Design profile from `data/protocol_profiles/registry_ranges.json`, and converts Design Compact DSL with that
  profile's `protocol.json` before validation and storage. The three generation routes share one policy-driven
  generation pipeline and the same model-failure, quality-repair, and validation switches. Tool callers cannot
  select or override either backend.
- `generateWidgetCardTerseDslNested2` keeps two model calls but bypasses the legacy whole-card flow from the first
  request. The new `advanced-component-scope` phase returns only a versioned Theme and business-component scope; the
  `advanced-mixed-body` phase emits one trusted UX layout component as the root and mixes versioned local Templates,
  standard components, and one layout-owned Action. The service lowers the layout, Action, and Templates before A2UI,
  so none can reach the client. Legacy `card@1`, UI Brief, confidence scoring, argument mapping, and whole-card
  compilation remain in code for compatibility tests and artifact-level rollback but are not called by the fifth
  create route.
- The legacy hybrid bypass parameter is test-only and disabled by default. It still requires the enable switch, a
  local/test environment, and constant-time verification of a separate token, but it no longer changes the already
  fixed mixed route. Every real DeepSeek physical attempt reserves one slot in the persistent concurrency-safe budget.
- Temporary route `generateWidgetCardCompactDslWithDirective` directly reuses the fourth route's generation service
  and schema, but always emits widget directive command frames even when the global directive switch is disabled.
  Its forced behavior is isolated in the router so the route can be removed without changing the generation pipeline.
- `WIDGET_SERVICE_ENABLE_IDS_MOCK=true` by default. In this mode the service reads only `WIDGET_SERVICE_MOCK_IDS_RESPONSE_PATH`, whose default path is the service-internal `cloud/data/mock/ids_res.json`; a missing or invalid mock produces an empty IDS result and never falls back to remote IDS. When set to `false`, the service ignores the mock and queries only the real remote IDS; remote failure produces an empty result and never falls back to mock.
- `WIDGET_SERVICE_ENABLE_VALIDATION_FAILURE_RETRY=false` by default. It controls targeted repair for both source
  DSL conversion errors and Validator errors. `WIDGET_SERVICE_VALIDATION_FAILURE_MAX_REPAIR_ATTEMPTS=1` limits
  repair to 1-10 attempts, and processing stops early when all errors disappear. Warnings never trigger repair.
  Conversion remains mandatory when Validator is disabled. Unconverted Design/Terse output is never saved;
  remaining Validator errors are non-blocking only for the standard third interface.
- `WIDGET_SERVICE_ENABLE_ADVANCED_WHOLE_CARD_TEMPLATE` and the confidence threshold remain available to legacy
  `AdvancedComponentPipeline.generate()` compatibility tests only. They do not select the fifth create route;
  restoring the legacy whole-card main path requires an explicit service artifact rollback. Strict mixed failures do
  not fall back to the legacy entry or generic TerseDSL-Nested-2 generation.
- `WIDGET_SERVICE_ENABLE_MODEL_FAILURE_RETRY=false` by default. Model transport errors,
  explicit model errors, and empty DSL output return `failed/A2UI_GENERATION_FAILED`;
  when disabled, the selected route calls only its master once and does not use fallback. When enabled, every initial
  or repair call retries its master with asynchronous exponential backoff and jitter, then switches to the configured
  fallback after the master budget is exhausted. Set `WIDGET_SERVICE_ENABLE_OPENAI_FALLBACK=false` to keep master
  retries but disable fallback calls. Configure the master and fallback additional retry counts with
  `WIDGET_SERVICE_MODEL_FAILURE_MAX_RETRY_ATTEMPTS` and
  `WIDGET_SERVICE_FALLBACK_MODEL_FAILURE_MAX_RETRY_ATTEMPTS` (1-10), and tune their shared delay with the
  `WIDGET_SERVICE_MODEL_FAILURE_RETRY_INITIAL_DELAY_SECONDS`, `WIDGET_SERVICE_MODEL_FAILURE_RETRY_MAX_DELAY_SECONDS`,
  `WIDGET_SERVICE_MODEL_FAILURE_RETRY_BACKOFF_MULTIPLIER`, and
  `WIDGET_SERVICE_MODEL_FAILURE_RETRY_JITTER_RATIO` settings. Backoff does not hold a worker thread or model permit.
  Conversion and Validator errors still trigger immediate targeted repair through the separate validation retry switch.
  Final model failures never enter validation or artifact persistence.
- With model mock disabled, all three generation routes use `A2UIModelClient.generate()` and the internal
  `UnifiedModelClient.generate()` entry. The `openai` route uses DeepSeek Platform as master and the existing
  `cloud/custom/llmclient.py` as fallback by default. Configure them with `WIDGET_SERVICE_OPENAI_MASTER_CLIENT` and
  `WIDGET_SERVICE_OPENAI_FALLBACK_CLIENT`, and control fallback with `WIDGET_SERVICE_ENABLE_OPENAI_FALLBACK`; tool
  callers cannot select a backend or physical client directly.
- DeepSeek Platform reads its SK only from the STS key configured by
  `WIDGET_SERVICE_DEEPSEEK_PLATFORM_SECRET_KEY_STS_CONFIG_KEY`, whose default is
  `genui.deepseek.platform.secret.key`. Its remaining static request fields use the
  `WIDGET_SERVICE_DEEPSEEK_PLATFORM_*` settings; session, interaction, device, country, App version, and App name
  prefer the current WebSocket request context.
- The llmclient WebSocket request is configured by the `WIDGET_SERVICE_DEEPSEEK_*` settings in `.env.example`,
  covering credentials, endpoint, model/user/request identifiers, sampling, maximum tokens, thinking/usage flags,
  and receive timeout. These fields have defaults matching the client behavior before configuration extraction.
- All real model calls share one application-lifetime runtime and one process-level concurrency limit. MEP uses a
  shared async `httpx.AsyncClient`, DeepSeek Platform uses async WebSocket, and the unchanged synchronous llmclient
  runs in a dedicated executor. Configure the
  shared limit with `WIDGET_SERVICE_MODEL_MAX_CONCURRENCY`, queue timeout with
  `WIDGET_SERVICE_MODEL_QUEUE_TIMEOUT_SECONDS`, and execution timeout with
  `WIDGET_SERVICE_MODEL_REQUEST_TIMEOUT_SECONDS`. Queue waits are coroutine waits and do not occupy worker threads.
  A timed-out llmclient call retains its permit until the underlying synchronous call actually finishes.
- If MEP ends a Design request with `6241/Early stop due to aborted` after emitting a non-empty candidate, the
  candidate continues through the strict Design converter and validation flow. Empty output and non-Design requests
  remain model failures.
- Standard create, edit, and repair prompts are loaded from `WIDGET_SERVICE_SYSTEM_PROMPT_FILE`,
  `WIDGET_SERVICE_EDIT_SYSTEM_PROMPT_FILE`, and `WIDGET_SERVICE_REPAIR_SYSTEM_PROMPT_FILE`. The Design and Terse
  routes keep their selected profile's `PROMPT.md` as the system message. Their edit user message contains the
  current query, TaskSpec, and the previous raw model output read from the artifact `designcompactdsl` block.
  Repair appends the same repair constraints when enabled. Prompt logs never write the full messages;
  `WIDGET_SERVICE_MODEL_PROMPT_LOG_PREVIEW_CHARS=30` limits the logged system-prompt prefix, and `0` disables prompt
  text while retaining message and character counts.
- `WIDGET_SERVICE_ENABLE_ARTIFACT_DOWNLOAD_MOCK=true` by default. Multi-round source artifacts are read only from `cloud/workspace/mock_obs`; missing mock files do not fall back to the network. Set it to `false` to download from the validated HTTPS artifact URL.
- The WebSocket router logs each received request object as compact standard JSON before protocol normalization. Structured values embedded in other log messages use the same double-quoted JSON format. Sensitive `uid`/`userId`/`callingUid` and `odid` are recursively omitted; `sourceArtifactUrl` is retained in the raw request log.
- Nested-2 batch evaluation persistence is opt-in through
  `WIDGET_SERVICE_ENABLE_WIDGET_BATCH_RECORDING`. A client supplies `batchId`, `caseId`, and `size` together as
  WebSocket query parameters. The service atomically stores the raw input, structured response, exact final plugin
  frame, A2UI JSONL, and server latency before sending the final frame. Query/download endpoints reuse
  `WIDGET_SERVICE_WEBSOCKET_BEARER_TOKEN`; ordinary calls without batch parameters retain their previous behavior.
  Batch runs may temporarily relax first-layer data admission, Query-to-variant adaptation, and
  Template candidate data matching through
  `WIDGET_SERVICE_ENABLE_ADVANCED_COMPONENT_DATA_ADMISSION_BYPASS_FOR_BATCH`. Capability, Registry, trusted fact
  projection, compiler, event, asset, and final protocol validation remain enforced.
- The server logs process-wide WebSocket `active_connections`, cumulative `total_connections`, and `running_tasks` every 10 seconds.
- Starlette synchronous handlers use the AnyIO worker pool with 80 concurrent tokens by default.
  Override it with `WIDGET_SERVICE_ANYIO_THREAD_POOL_TOKENS` when deployment capacity requires a different limit.
  The three generation WebSocket handlers directly await the async generation service; heartbeat send failure does
  not cancel generation, repair, or artifact persistence.
- Package filtering emits exactly one summary result per capability-overview request; per-capability dependency-check logs are not emitted.
- OBS upload is intentionally left as a TODO hook in `ArtifactStore`; remote source artifact reads reuse `utils/download_file_from_url.py`.

See `docs/cardplan_template_production.md` for the CardPlan Registry/Compiler mapping, SHA drift checks, bypass security,
Golden evaluation commands, deployment, observability, and rollback guidance.

The fifth create route's first response is `advanced-scope-brief/1` with only `themeId` and
`advancedComponentIds`. The second response is rooted directly at an approved UX layout. The layout owns its final
Action slot, while the trusted service injects the approved label, event, and UX dimensions. A separate header is
optional and omitted by default; business content owns its semantic title. Business advanced components own variants
and local Template capability. The trusted service validates Theme/palette compatibility, layout compatibility,
action limits, and Chinese phrase-level candidates before the second model call.

## Run

```bash
cd widget_service
python -m venv .venv
.venv\Scripts\activate
pip install -e .[dev]
# or:
pip install -r requirements.txt
py -3.12 cloud\start_websocket_server.py
```

本地验证最新校验 API 和“校验失败不阻断保存”时，建议显式开启校验并关闭重试：

```powershell
$env:WIDGET_SERVICE_ENABLE_ARTIFACT_VALIDATION="true"
$env:WIDGET_SERVICE_ENABLE_VALIDATION_FAILURE_RETRY="false"
py -3.12 cloud\start_websocket_server.py
```

服务启动后，在另一个终端执行真实 WebSocket 联调脚本：

```powershell
cd widget_service
py -3.12 tests\test_running_ws_server.py
```

该脚本会调用真实 `generateWidgetCard`，读取服务保存的 artifact，通过
`cloud/services/card_validation/` Python API 再校验一次并打印诊断。当前 mock 输出包含
确定的校验问题，因此脚本还会断言接口依然成功返回 artifact，用于证明校验失败不会阻塞主流程。

需要像单元测试一样逐项调试本地服务时，使用单功能真实 WS 测试：

```powershell
cd widget_service
# 运行全部单功能用例
py -3.12 -m pytest tests\test_running_ws_features.py -s -q
# 只测能力概述
py -3.12 -m pytest tests\test_running_ws_features.py::test_live_widget_capability_overview -s -q
# 只测一个数据能力 schema
py -3.12 -m pytest "tests\test_running_ws_features.py::test_live_each_data_capability_schema[ViewWeather]" -s -q
# 只测 A2UI Form 或 Compact DSL 生成
py -3.12 -m pytest tests\test_running_ws_features.py::test_live_generate_widget_card -s -q
py -3.12 -m pytest tests\test_running_ws_features.py::test_live_generate_widget_card_compact_dsl -s -q
```

该文件中的健康检查、四个 WS 接口、八个数据能力 schema、缺失能力和参数异常都是独立
pytest 节点。默认等待模型响应 180 秒，可通过 `WIDGET_SERVICE_TEST_RESPONSE_TIMEOUT`
调整；服务未启动时整组用例会明确跳过。

本地多轮编辑联调需要先开启开关：

```powershell
$env:WIDGET_SERVICE_ENABLE_WIDGET_EDIT="true"
py -3.12 cloud\start_websocket_server.py
```

服务启动后，在另一个终端执行真实 WebSocket 多轮测试：

```powershell
cd widget_service
py -3.12 tests\test_running_ws_multi_round.py
# 或显示每轮响应：
py -3.12 -m pytest tests\test_running_ws_multi_round.py -s -q
```

测试会依次执行首次生成、纯视觉继承编辑和显式清空数据三轮，并断言每轮返回新的 artifact URL。

Pytest 默认捕获 stdout/stderr，因此测试通过时通常看不到 `print` 和控制台日志。需要实时显示时使用：

```powershell
py -3.12 -m pytest tests\test_service_units.py -s -q
```

真实 WebSocket 联调时，业务日志由单独运行的 `cloud/start_websocket_server.py` 进程输出，应在服务终端查看；
本地文件日志位于 `cloud/logs/agent_YYYYMMDD.log`。客户端测试终端只显示请求响应和脚本打印的校验报告。

## API

```text
GET  /health
WS   /ws  (Bearer-protected CardTemplate UX `card.generate` compatibility endpoint)
GET  /api/v1/widget-batches
GET  /api/v1/widget-batches/{batchId}
GET  /api/v1/widget-batches/{batchId}/download
WS   /api/v1/ws/tools/getWidgetCapabilityOverview
WS   /api/v1/ws/tools/getDataCapabilitySchemas
WS   /api/v1/ws/tools/generateWidgetCard
WS   /api/v1/ws/tools/generateWidgetCardCompactDsl
WS   /api/v1/ws/tools/generateWidgetCardTerseDslNested2
```

When `WIDGET_SERVICE_WEBSOCKET_BEARER_TOKEN` is configured, the same static Bearer token protects
the compatibility endpoint and all `/api/v1/ws/tools/*` endpoints. The compatibility endpoint only
accepts `card.generate` with `pipeline=card-plan-template`; it expands the trusted Provider
CardTemplate result to standard A2UI messages and never sends Template or conditional guard nodes
to the client. The retained Python business constructors are test-only Shadow Oracles.

批量评测部署时，需要显式开启记录并把结果目录挂到持久卷：

```text
WIDGET_SERVICE_ENABLE_WIDGET_BATCH_RECORDING=true
WIDGET_SERVICE_ENABLE_ADVANCED_COMPONENT_DATA_ADMISSION_BYPASS_FOR_BATCH=true
WIDGET_SERVICE_WIDGET_BATCH_RESULTS_PATH=/data/widget_batch_runs
```

批测临时开关默认为 `false`：仅在批次记录与本开关同时开启时，第一层高级组件候选会跳过确定性数据适配准入，
Activity/Workout 的投影会忽略 Query 到可渲染变体的严格映射，Template 候选也不再因参数数据匹配不完整而提前
剔除，以便观察模型选择与视觉效果；普通生成、可信事实投影和最终编译校验不受影响。完成批测后将开关设为
`false` 即恢复完整准入。

端侧对每条 Nested-2 用例连接
`...?batchId=nested2-2x2-1720000000000&caseId=2x2-q1&size=2x2`。批次完成后可下载：

```bash
curl -H "Authorization: Bearer ${WIDGET_BATCH_TOKEN}" \
  -o nested2-2x2.zip \
  http://127.0.0.1:8855/api/v1/widget-batches/nested2-2x2-1720000000000/download
```

ZIP 内含 `manifest.json` 和每条用例的 `input.json`、`response.json`、
`output.a2ui.jsonl`、`metrics.json`。完整约束见 `docs/云侧方案设计.md` 的
“Nested-2 批量用例评测持久化”。

The Docker image installs `requirements-runtime.txt`; `requirements.txt` additionally contains local
test, lint, and type-check tooling and is intentionally not installed in the production image.

Example request:

```json
{
  "requestId": "overview-1",
  "arguments": {
    "uid": "test-user-001",
    "device": {
      "deviceId": "5e64f3e9-0a80-d719-d689-3c36eca5eeb6",
      "deviceType": "ALN-AL00",
      "romVersion": "CLS-AL30 6.0.0.328"
    },
    "locale": "zh-CN"
  }
}
```

Schema files:

- `docs/schemas/getWidgetCapabilityOverview.schema.json`
- `docs/schemas/getDataCapabilitySchemas.schema.json`
- `docs/schemas/generateWidgetCard.schema.json`
- `docs/schemas/generateWidgetCardCompactDsl.schema.json`
- `docs/schemas/generateWidgetCardTerseDslNested2.schema.json`

See `docs/method_usage.md` for detailed method and API usage.
