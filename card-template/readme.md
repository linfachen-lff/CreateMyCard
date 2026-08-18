# card-template

卡片模板素材与建库工具目录，服务于 search 模板检索缓存（见
`docs/云侧方案设计.md`「模板检索缓存」小节与
`widget_service/docs/search_cache_integration.md`）。

## 目录内容

| 路径 | 说明 |
| --- | --- |
| `cards/q01_artifact.md` … `q20_artifact.md` | 20 个卡片生成产物样本（从 subagent_genui/taskspec/md 复制留存）。每个文件含 cardspec / genui / schema / taskspec / effectivecapabilities / removedcapabilities / generationplan / meta / designcompactdsl 九个 fenced block |
| `asset-library.md` | 素材库索引（`resources/base/media` 下的图标/图片 src 清单，由 skill 读取，勿编造路径） |
| `build_db.py` | **自包含建库脚本**：解析 `cards/*.md`，降维 dataModelSchema、提取 designcompactdsl 骨架，构建 search 模板库（templates.sqlite3） |

## 建库

直接运行（无需任何参数，默认读取本目录 `cards/`，输出到
`widget_service/vendor_search/search/data/templates.sqlite3`）：

```bash
py -3.12 build_db.py            # 从任意目录均可
py -3.12 build_db.py --replace  # 覆盖已有模板
```

转换逻辑：

- `taskspec.dataModelSchema` 叶子 `{type, description, sampleValue}` → 降维为 `sampleValue` 实例（input_json）；
- `designcompactdsl` 去掉 data 行 → 无数据的 Compact DSL 骨架（reference_jsonl）；
- `structure_hash` 由完整 input 结构签名计算（`compute_shape_signature`）；
- `size` 取 `cardspec.suggestSize`；description/tags 从 cardspec.description + capabilityId + userQuery 派生；
- 每张模板经 vendored `validate_template` 校验（Button 带一个 Image 子节点由本地补丁放行），
  bind 校验失败仅告警（该模板只能走 keyword_match）。

新增卡片素材：往 `cards/` 放入同格式 `q*_artifact.md`，再跑 `build_db.py` 即可。

## 与 cloud 版本的关系

`widget_service/cloud/search_integration/build_db.py` 是打包版（供测试 `test_search_build_db.py`
导入），默认源同样指向 `card-template/cards/`、不依赖项目外路径。两处逻辑保持一致；修改其中一处时
需同步另一处，或直接运行自包含版后由测试回归校验。

## 依赖与备注

- 建库需要 `jieba` 与 vendored search 模块（`widget_service/vendor_search/`）。
- 运行时数据库 `widget_service/vendor_search/search/data/templates.sqlite3` 为构建产物，不入 git。
- vendored search 含本地记录补丁（P1 Button+Image、P2 size），见 `vendor_search/VENDORED.md`。
