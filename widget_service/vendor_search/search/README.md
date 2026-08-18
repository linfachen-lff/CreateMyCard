# Search 模块

Search 先对完整 `input_data` 计算可观察载荷结构 Hash；唯一命中时绑定模板并返回
`structure_match`。结构未命中且有非空 query 时，使用去除首尾空白、小写、Jieba 搜索分词、
SQLite FTS5/BM25 和覆盖率过滤返回无数据的 `keyword_match.reference_jsonl`。

## 初始化运行时数据库

```bash
python -m search.manage --db search/data/templates.sqlite3 init
python -m search.manage --db search/data/templates.sqlite3 import-cards \
  --cards cards \
  --description-db /path/to/templates.sqlite3 \
  --replace
python -m search.manage --db search/data/templates.sqlite3 count
```

签名算法升级后执行：

```bash
python -m search.manage --db search/data/templates.sqlite3 rebuild-signatures
```

数据库是运行时产物，不提交 Git。可通过 `SEARCH_DB_PATH` 指向其他数据库。导入器从
`cards/prompts/*.json` 的完整 `input` 计算签名，并从已有 `templates.sqlite3` 读取
LLM 生成的 `description + tags`，生成无业务样例值的标准 Compact 骨架。源描述库和
运行库均只通过 DAO 访问，SQL 值全部参数化。空数组、异构数组、重复 key、非标准 JSON
或不安全模板会被拒绝；报告包含模板 ID、原因和准确 JSON Pointer。

当前工作区运行库已用现有描述库刷新：61 张模板入库，11 张异构数组模板按设计拒绝。

## Web Demo

Demo 直接调用现有 Search 服务，用流程节点展示结构 Hash 优先、关键词回退以及三种
outcome 的上层去向，不调用真实模型：

```bash
source .venv/bin/activate
python -m search.demo
```

浏览器打开 <http://127.0.0.1:8020>。可只输入 query 验证关键词检索，也可粘贴完整
MCP JSON 验证结构匹配；两者同时存在时仍遵循 Hash 优先规则。可用
`SEARCH_DB_PATH=/path/to/templates.sqlite3` 切换运行时模板库。命中模板时，页面还会展示
素材库中的原始 `description` 和 `tags`；它们只是 Demo 元数据，不进入 SearchResult，
也不参与 outcome 路由。

## 类型契约

Search 接受的逻辑请求为：

```json
{"query":"商品列表","inputData":{"name":"耳机"}}
```

两者不能同时为空，空白 query 按未提供处理。`api_schema.py` 中的 `SearchRequest` 和
`SearchResult` 用于和未来调用方对齐类型。`SearchResult` 是以 `outcome` 为判别字段的
三分支联合类型，调用方判断 outcome 后可获得对应的非空 JSONL 静态类型。请求载荷和
诊断字段统一使用递归 JSON 类型，不接受任意 Python 对象。

并发语义：`search_template()` 目前保留 async 调用形式，但内部 SQLite、FTS 和模板绑定
仍为同步执行。未来接入高并发异步调用方时，应在上层 adapter 中卸载到工作线程，不能
把当前接口理解为非阻塞数据库实现。

## 验证

```bash
python -m pytest tests/test_search_*.py -q
ruff check search/ tests/test_search_*.py api_schema.py
ruff format --check search/ tests/test_search_*.py api_schema.py
mypy search/ api_schema.py --ignore-missing-imports
```
