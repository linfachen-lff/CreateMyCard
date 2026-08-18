# -*- coding: utf-8 -*-
"""search 模板库构建脚本测试。

MOCK DATA: 使用内嵌的精简 artifact md 夹具与内存 SQLite，不依赖真实
subagent_genui/taskspec/md 数据，也不调用 DeepSeek API。
"""

import json
import sys
from pathlib import Path

import pytest

CLOUD_ROOT = Path(__file__).resolve().parents[1] / "cloud"
sys.path.insert(0, str(CLOUD_ROOT))

from cloud.search_integration import vendored_loader  # noqa: E402
from cloud.search_integration.deflate import deflate_data_model_schema  # noqa: E402

# 精简的 q*_artifact.md 夹具（结构同真实文件：含四个 fenced block）
SAMPLE_MD = """```cardspec
{
  "title": "上海天气",
  "description": "上海今日天气小卡片",
  "suggestSize": "2x2",
  "dataBindings": []
}
```
```taskspec
{
  "userQuery": "创建上海今日天气小卡片",
  "size": "2x2",
  "eventCandidates": [],
  "dataModelSchema": {
    "data": {
      "weather": {
        "current": {
          "temperatureText": {"type": "string", "description": "温度", "sampleValue": "26℃"},
          "feelsLikeC": {"type": "number", "description": "体感", "sampleValue": 27}
        }
      }
    }
  },
  "assetCandidates": []
}
```
```generationplan
{
  "candidateDataBindings": [
    {"capabilityId": "ViewWeather", "arguments": {}, "writeResultTo": "weather",
     "candidateOutputFields": ["temperatureText", "feelsLikeC"]}
  ],
  "candidateEventCandidates": [],
  "candidateAssetIds": []
}
```
```designcompactdsl
["root","Column",{"width":160,"height":160},["title","btn"]]
["title","Text",{"content":{"path":"/data/weather/current/temperatureText"}}]
["btn","Button",{"label":"查看详情"},["btn_icon"]]
["btn_icon","Image",{"src":"asset://weather.png"}]
["/data/weather/current/temperatureText","26℃"]
```
"""


def _write_sample(tmp_path: Path) -> Path:
    sample = tmp_path / "q01_artifact.md"
    sample.write_text(SAMPLE_MD, encoding="utf-8")
    return sample


def test_deflate_data_model_schema():
    """叶子 {type, description, sampleValue} → sampleValue 实例。"""
    schema = {
        "data": {
            "weather": {
                "current": {
                    "temperatureText": {
                        "type": "string",
                        "description": "温度",
                        "sampleValue": "26℃",
                    },
                    "feelsLikeC": {
                        "type": "number",
                        "description": "体感",
                        "sampleValue": 27,
                    },
                    "daily": [
                        {
                            "date": {
                                "type": "string",
                                "description": "日期",
                                "sampleValue": "2026-07-15",
                            }
                        }
                    ],
                }
            }
        }
    }
    result = deflate_data_model_schema(schema)
    assert result == {
        "data": {
            "weather": {
                "current": {
                    "temperatureText": "26℃",
                    "feelsLikeC": 27,
                    "daily": [{"date": "2026-07-15"}],
                }
            }
        }
    }


def test_parse_artifact_md(tmp_path):
    """按 fenced block 解析出各块。"""
    from cloud.search_integration.build_db import parse_artifact_md

    blocks = parse_artifact_md(_write_sample(tmp_path))
    assert set(blocks) >= {"cardspec", "taskspec", "generationplan", "designcompactdsl"}
    cardspec = json.loads(blocks["cardspec"])
    assert cardspec["title"] == "上海天气"
    design = blocks["designcompactdsl"]
    assert design.splitlines()[0].startswith('["root"')


def test_build_template_record_deflates_and_validates(tmp_path):
    """构建的 TemplateRecord：input_json 已降维、reference 无 data 行、可结构命中。"""
    from cloud.search_integration.build_db import build_template_record, parse_artifact_md

    parsed = parse_artifact_md(_write_sample(tmp_path))
    record = build_template_record(parsed, template_id="q01")
    assert record.template_id == "q01"
    assert record.size == "2x2"
    input_payload = json.loads(record.input_json)
    assert input_payload["data"]["weather"]["current"]["temperatureText"] == "26℃"
    # reference 骨架不含 data 行
    for line in record.reference_jsonl.splitlines():
        assert not line.strip().startswith('["/"')
    # 结构签名可复算
    assert record.structure_hash == vendored_loader.search.compute_shape_signature(
        input_payload
    ).signature
    # description/tags 从产物派生
    assert record.description == "上海今日天气小卡片"
    assert "ViewWeather" in record.tags


@pytest.mark.asyncio
async def test_built_db_searchable(tmp_path):
    """构建出的库可被 search 命中 structure_match 与 keyword_match。"""
    from cloud.search_integration.build_db import build_template_record, parse_artifact_md

    dao = vendored_loader.search.SQLiteTemplateDAO(":memory:")
    dao.initialize()
    parsed = parse_artifact_md(_write_sample(tmp_path))
    dao.upsert(build_template_record(parsed, template_id="q01"))
    service = vendored_loader.search.SearchService(dao)

    # structure_match：同结构、不同 sampleValue
    result = await vendored_loader.search.search_template(
        vendored_loader.search.SearchRequest(
            query="天气",
            input_data={
                "data": {
                    "weather": {
                        "current": {
                            "temperatureText": "31℃",
                            "feelsLikeC": 32,
                        }
                    }
                }
            },
        ),
        service=service,
    )
    assert result.outcome == "structure_match"
    assert '"31℃"' in result.rendered_jsonl
    assert "btn_icon" in result.rendered_jsonl

    # keyword_match：query 命中
    kw = await vendored_loader.search.search_template(
        vendored_loader.search.SearchRequest(query="上海天气", input_data=None),
        service=service,
    )
    assert kw.outcome == "keyword_match"
    assert "/data/weather/current/temperatureText" in kw.reference_jsonl
