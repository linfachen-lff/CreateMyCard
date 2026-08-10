# Widget Service 蓝区 / 绿区开发方式

项目采用“共享代码 Module + 区内 Adapter”结构，不需要构建交付包，也不维护两份业务代码：

```text
widget_service/
├─ cloud/
│  ├─ start_websocket_server.py     # 固定启动入口，连接 shared 与当前 zone
│  ├─ shared/                     # 蓝区整体复制到绿区的唯一代码目录
│  │  ├─ api/
│  │  ├─ app/                     # application.py 只负责创建 FastAPI 应用
│  │  ├─ custom/
│  │  ├─ data/
│  │  ├─ models/
│  │  ├─ runtime_settings/        # 共享配置字段契约和 Provider interface
│  │  ├─ services/
│  │  └─ prompts/                 # 运行时 Prompt，随 shared 一起复制
│  └─ zone/                       # 当前区域本地保留，替换 shared 时绝不覆盖
│     ├─ config.py                # 蓝区或绿区自己的取值 Adapter
│     ├─ .env                     # 可选区内环境变量，Git 已忽略
│     └─ runtime/                 # 日志、缓存和生成产物，Git 已忽略
├─ docs/                          # 开发文档和接口 schema
├─ tests/
├─ test_reports/
├─ pyproject.toml
└─ requirements.txt
```

## 绿区首次接入（只做一次）

1. 在绿区创建 `widget_service/cloud/zone`。
2. 复制通用的 `cloud/start_websocket_server.py` 和 `cloud/zone/__init__.py`。
3. 不复制蓝区的 `zone/config.py`；在绿区创建同名文件，实现 `create_settings()` 和
   `read_secret()`，把绿区原有配置函数接进去。
4. 把绿区原有日志和工作目录放到 `cloud/zone/runtime`。
5. 放入一份完整的 `cloud/shared` 并执行启动冒烟验证。

以后 `zone` 长期留在各自区域，日常业务交付只替换 `cloud/shared`。

## 日常搬运

蓝区开发和测试完成后：

1. 停止绿区服务。
2. 把绿区旧 `cloud/shared` 改名备份，例如 `shared_20260809`。
3. 把蓝区完整的 `widget_service/cloud/shared` 复制到绿区 `widget_service/cloud` 下。
4. 不复制、不覆盖绿区的 `cloud/zone`。
5. 从 `widget_service` 执行 `py -3.12 -m cloud.start_websocket_server`。

不要把新文件合并覆盖到旧 `shared`。蓝区已经删除的文件会残留在绿区，可能继续被 Python 导入；
“备份旧目录 + 放入完整新目录”才能保证两区共享代码一致。整个过程没有额外构建步骤。

## 新增配置项

共享字段契约只放在 `cloud/shared/runtime_settings/schema.py`，每个区如何取值只放在自己的
`cloud/zone/config.py`。例如新增必须由区内提供的配置 `a`：

```python
# cloud/shared/runtime_settings/schema.py
class Settings(BaseSettings):
    a: str
```

蓝区 Adapter 提供蓝区值。复制整个 `shared` 后，绿区旧 Adapter 会在应用加载前明确报告
`a / Field required`。绿区只需在本地接入自己的函数：

```python
def create_settings() -> Settings:
    return ZoneSettings(
        a=get_a_from_green_platform(),
        _env_file=ZONE_ROOT / ".env",
    )
```

普通公共开关可以在共享契约中提供默认值；必须让绿区显式适配的字段不要提供默认值。密钥同理由
`cloud/zone/config.py` 的 `read_secret()` 获取，共享代码不保存区内密钥或取值函数。

首次初始化某个区域时，可以把 `.env.example` 复制为 `cloud/zone/.env`。示例文件只保留字段名，
不会携带蓝区值；后续替换 `shared` 也不会覆盖它。

## 安装、启动与测试

```powershell
cd widget_service
py -3.12 -m venv .venv
.\.venv\Scripts\python -m pip install -e ".[dev]"
.\.venv\Scripts\python -m cloud.start_websocket_server
```

```powershell
cd widget_service
.\.venv\Scripts\python -m pytest tests -q
.\.venv\Scripts\python -m ruff check cloud\shared tests cloud\zone
```

启动入口会先安装当前区的配置和安全配置读取函数，再导入共享应用。未安装 Adapter、漏掉必填字段，
或者把日志/工作目录错误地指进可替换的 `cloud/shared`，都会直接启动失败。

## PyCharm 导入解析

请把 `widget_service/cloud/shared` 标记为 **Sources Root**，不要把外层 `cloud` 标记为 Sources Root。
`cloud` 是部署容器，`shared` 才是 Python 源码根，因此共享代码使用 `from api.schemas import ...`、
`from services...` 等导入。运行、pytest 和 IDE 统一以 `cloud/shared` 作为源码根。
