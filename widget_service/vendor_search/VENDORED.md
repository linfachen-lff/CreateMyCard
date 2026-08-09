# vendored search 模块

本目录是 `subagent_genui` 仓库 `search` 模块的**字节级拷贝**，用于 CreateMyCard 生成服务的模板检索缓存整合。

## 来源

- 仓库：`D:\Program\work\subagent_genui`
- 分支：`origin/search`
- 源 commit：`a505129c46a1bb986d4e191976b5e8fe089a70ee`（2026-08-03）
- 拷贝命令：
  ```bash
  cd /d/Program/work/subagent_genui
  git archive --format=tar origin/search api_schema.py search \
    | tar -x -C /d/Program/work/CreateMyCard/widget_service/vendor_search
  ```

## 更新方式

search 模块更新后，重新执行上面的拷贝命令覆盖本目录，并更新本文件的源 commit。
被拷贝文件**不得手改**；如需对 search 行为做本地适配，一律放在
`widget_service/cloud/search_integration/` 适配层。

## 导入方式

本目录无 `__init__.py`，不是 Python 包。`cloud/search_integration/vendored_loader.py`
会把本目录插入 `sys.path`（插到 `cloud` 之后），再 `import search` / `import api_schema`。

## 运行时数据库

`search/data/templates.sqlite3` 是运行时产物（由 `search/manage.py` 构建），
不提交，已在 `.gitignore` 忽略。路径可用环境变量 `SEARCH_DB_PATH` 覆盖。
