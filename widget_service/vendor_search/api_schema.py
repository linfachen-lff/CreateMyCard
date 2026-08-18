"""
DeepSeek Chat Completions API 的 Python 数据结构。

使用 Python 标准库 dataclass（零外部依赖），提供：
- 类型安全的请求/响应构造
- 序列化（.to_dict() → JSON body）
- IDE 自动补全
"""

from __future__ import annotations

from copy import deepcopy
from collections.abc import Sequence
from dataclasses import asdict, dataclass, field
from typing import Any, Literal, TypeAlias

# ═══════════════════════════════════════════════════════════════
# 消息类型
# ═══════════════════════════════════════════════════════════════


@dataclass
class ToolCallFunction:
    """工具调用的 function 部分。"""

    name: str
    arguments: str  # JSON string


@dataclass
class ToolCall:
    """工具调用。"""

    id: str
    type: str = "function"
    function: ToolCallFunction | None = None


@dataclass
class ChatMessage:
    """对话消息。role 决定消息结构。"""

    role: str  # system | user | assistant | tool
    content: str | None = None
    name: str | None = None

    # assistant 特有
    reasoning_content: str | None = None
    prefix: bool | None = None
    tool_calls: list[ToolCall] | None = None

    # tool 特有
    tool_call_id: str | None = None

    @staticmethod
    def system(content: str, **kw: Any) -> ChatMessage:
        return ChatMessage(role="system", content=content, **kw)

    @staticmethod
    def user(content: str, **kw: Any) -> ChatMessage:
        return ChatMessage(role="user", content=content, **kw)

    @staticmethod
    def assistant(
        content: str | None = None,
        reasoning_content: str | None = None,
        tool_calls: list[ToolCall] | None = None,
        **kw: Any,
    ) -> ChatMessage:
        return ChatMessage(
            role="assistant",
            content=content,
            reasoning_content=reasoning_content,
            tool_calls=tool_calls,
            **kw,
        )

    @staticmethod
    def tool(content: str, tool_call_id: str, **kw: Any) -> ChatMessage:
        return ChatMessage(
            role="tool", content=content, tool_call_id=tool_call_id, **kw
        )


# ═══════════════════════════════════════════════════════════════
# 工具定义
# ═══════════════════════════════════════════════════════════════


@dataclass
class FunctionDefinition:
    """工具定义中的 function 描述。"""

    name: str
    description: str | None = None
    parameters: dict[str, Any] | None = None  # JSON Schema
    strict: bool | None = None


@dataclass
class ToolDefinition:
    """可调用工具定义。"""

    type: str = "function"
    function: FunctionDefinition | None = None


# ═══════════════════════════════════════════════════════════════
# 请求
# ═══════════════════════════════════════════════════════════════


@dataclass
class ThinkingConfig:
    """思考模式配置。"""

    type: str = "enabled"  # enabled | disabled


@dataclass
class StreamOptions:
    """流式选项。"""

    include_usage: bool | None = None


@dataclass
class ResponseFormat:
    """输出格式配置。"""

    type: str = "text"  # text | json_object


@dataclass
class ToolChoice:
    """工具选择控制。

    注意：思考模式（thinking enabled）下不兼容 `required` 和指定函数名称的方式，
    只能用 `"auto"` 或 `"none"`。使用不兼容的值会返回 400 错误。
    """

    type: str = "function"
    function: dict[str, str] | None = None  # {"name": "xxx"}


@dataclass
class ChatCompletionRequest:
    """
    对话补全请求。

    用法：
        req = ChatCompletionRequest(
            model="deepseek-v4-flash",
            messages=[ChatMessage.system("你是一个助手"), ChatMessage.user("你好")],
            stream=True,
        )
        body = req.to_dict()
    """

    model: str
    messages: Sequence[ChatMessage | dict]

    # 流式
    stream: bool | None = None
    stream_options: StreamOptions | None = None

    # 思考模式
    thinking: ThinkingConfig | None = None
    reasoning_effort: str | None = None

    # 采样
    temperature: float | None = None
    top_p: float | None = None
    max_tokens: int | None = None
    stop: str | list[str] | None = None

    # 输出
    response_format: ResponseFormat | None = None

    # 工具
    tools: list[ToolDefinition] | None = None
    tool_choice: str | ToolChoice | None = (
        None  # "auto"/"none" ✅ "required"/指定函数 ❌ 思考模式
    )

    # 日志概率
    logprobs: bool | None = None
    top_logprobs: int | None = None

    # 用户标识
    user_id: str | None = None

    # 已弃用（传入不报错）
    presence_penalty: float | None = None
    frequency_penalty: float | None = None

    def to_dict(self, *, exclude_none: bool = True) -> dict[str, Any]:
        """序列化为 API 请求体的 JSON dict。

        Args:
            exclude_none: 为 True 时排除值为 None 的字段（推荐）
        """
        raw = asdict(self)
        if exclude_none:
            return _strip_none(raw)
        return raw


# ═══════════════════════════════════════════════════════════════
# 非流式响应
# ═══════════════════════════════════════════════════════════════


@dataclass
class CompletionTokensDetails:
    """输出 token 详情。"""

    reasoning_tokens: int | None = None


@dataclass
class Usage:
    """Token 用量。"""

    prompt_tokens: int = 0
    completion_tokens: int = 0
    total_tokens: int = 0
    prompt_cache_hit_tokens: int | None = None
    prompt_cache_miss_tokens: int | None = None
    completion_tokens_details: CompletionTokensDetails | None = None


@dataclass
class ChoiceMessage:
    """非流式响应的消息。"""

    role: str = "assistant"
    content: str | None = None
    reasoning_content: str | None = None
    tool_calls: list[ToolCall] | None = None


@dataclass
class Choice:
    """非流式响应的 choice。"""

    index: int = 0
    finish_reason: str = "stop"
    message: ChoiceMessage | None = None


@dataclass
class ChatCompletionResponse:
    """非流式响应。"""

    id: str = ""
    object: str = "chat.completion"
    created: int = 0
    model: str = ""
    system_fingerprint: str | None = None
    choices: list[Choice] = field(default_factory=list)
    usage: Usage | None = None


# ═══════════════════════════════════════════════════════════════
# 流式响应（SSE chunk）
# ═══════════════════════════════════════════════════════════════


@dataclass
class StreamingDelta:
    """流式响应的 delta 增量。"""

    content: str | None = None
    reasoning_content: str | None = None
    role: str | None = None
    tool_calls: list[ToolCall] | None = None


@dataclass
class StreamingChoice:
    """流式响应的 choice。"""

    index: int = 0
    delta: StreamingDelta | None = None
    finish_reason: str | None = None


@dataclass
class StreamingChunk:
    """SSE 流式数据行。"""

    id: str = ""
    object: str = "chat.completion.chunk"
    created: int = 0
    model: str = ""
    system_fingerprint: str | None = None
    choices: list[StreamingChoice] = field(default_factory=list)
    usage: Usage | None = None


# ═══════════════════════════════════════════════════════════════
# 工具函数
# ═══════════════════════════════════════════════════════════════


def _strip_none(obj: Any) -> Any:
    """递归删除 dict 中值为 None 的键。"""
    if isinstance(obj, dict):
        return {k: _strip_none(v) for k, v in obj.items() if v is not None}
    if isinstance(obj, list):
        return [_strip_none(v) for v in obj]
    return obj


# ═══════════════════════════════════════════════════════════════
# Search 请求与结果契约
# ═══════════════════════════════════════════════════════════════

JSONScalar: TypeAlias = None | bool | int | float | str
JSONValue: TypeAlias = JSONScalar | list["JSONValue"] | dict[str, "JSONValue"]
JSONArray: TypeAlias = list[JSONValue]
JSONObject: TypeAlias = dict[str, JSONValue]

SearchOutcome = Literal["structure_match", "keyword_match", "miss"]


@dataclass(frozen=True)
class SearchRequest:
    """Search 内部请求；HTTP 的 ``inputData`` 映射为 ``input_data``。"""

    query: str | None = None
    input_data: JSONObject | None = None
    # LOCAL PATCH: 卡片尺寸（如 "2x2"），structure 命中后按尺寸过滤（见 VENDORED.md P2）
    size: str | None = None

    def __post_init__(self) -> None:
        if self.input_data is not None:
            object.__setattr__(self, "input_data", deepcopy(self.input_data))

    def normalized(self) -> SearchRequest:
        query = self.query.strip() if self.query is not None else None
        return SearchRequest(
            query=query or None, input_data=self.input_data, size=self.size
        )


@dataclass(frozen=True)
class StructureMatchResult:
    """A unique structure match with directly renderable Compact JSONL."""

    rendered_jsonl: str
    template_id: str
    structure_hash: str
    diagnostics: JSONObject = field(default_factory=dict)
    outcome: Literal["structure_match"] = field(default="structure_match", init=False)
    reference_jsonl: None = field(default=None, init=False)
    miss_reason: None = field(default=None, init=False)

    def __post_init__(self) -> None:
        if not all(
            value.strip()
            for value in (self.rendered_jsonl, self.template_id, self.structure_hash)
        ):
            raise ValueError("structure_match fields must be non-empty")
        object.__setattr__(self, "diagnostics", deepcopy(self.diagnostics))

    def to_dict(self) -> JSONObject:
        return {
            "outcome": self.outcome,
            "rendered_jsonl": self.rendered_jsonl,
            "reference_jsonl": self.reference_jsonl,
            "template_id": self.template_id,
            "structure_hash": self.structure_hash,
            "miss_reason": self.miss_reason,
            "diagnostics": deepcopy(self.diagnostics),
        }


@dataclass(frozen=True)
class KeywordMatchResult:
    """A keyword match containing a data-free reference template."""

    reference_jsonl: str
    template_id: str
    structure_hash: str | None = None
    diagnostics: JSONObject = field(default_factory=dict)
    outcome: Literal["keyword_match"] = field(default="keyword_match", init=False)
    rendered_jsonl: None = field(default=None, init=False)
    miss_reason: None = field(default=None, init=False)

    def __post_init__(self) -> None:
        if not self.reference_jsonl.strip() or not self.template_id.strip():
            raise ValueError("keyword_match fields must be non-empty")
        if self.structure_hash is not None and not self.structure_hash.strip():
            raise ValueError("structure_hash must be non-empty when provided")
        object.__setattr__(self, "diagnostics", deepcopy(self.diagnostics))

    def to_dict(self) -> JSONObject:
        return {
            "outcome": self.outcome,
            "rendered_jsonl": self.rendered_jsonl,
            "reference_jsonl": self.reference_jsonl,
            "template_id": self.template_id,
            "structure_hash": self.structure_hash,
            "miss_reason": self.miss_reason,
            "diagnostics": deepcopy(self.diagnostics),
        }


@dataclass(frozen=True)
class MissResult:
    """A safe miss with neither rendered nor reference JSONL."""

    miss_reason: str
    structure_hash: str | None = None
    diagnostics: JSONObject = field(default_factory=dict)
    outcome: Literal["miss"] = field(default="miss", init=False)
    rendered_jsonl: None = field(default=None, init=False)
    reference_jsonl: None = field(default=None, init=False)
    template_id: None = field(default=None, init=False)

    def __post_init__(self) -> None:
        if not self.miss_reason.strip():
            raise ValueError("miss_reason must be non-empty")
        if self.structure_hash is not None and not self.structure_hash.strip():
            raise ValueError("structure_hash must be non-empty when provided")
        object.__setattr__(self, "diagnostics", deepcopy(self.diagnostics))

    def to_dict(self) -> JSONObject:
        return {
            "outcome": self.outcome,
            "rendered_jsonl": self.rendered_jsonl,
            "reference_jsonl": self.reference_jsonl,
            "template_id": self.template_id,
            "structure_hash": self.structure_hash,
            "miss_reason": self.miss_reason,
            "diagnostics": deepcopy(self.diagnostics),
        }


SearchResult: TypeAlias = StructureMatchResult | KeywordMatchResult | MissResult


def parse_chat_completion(data: dict) -> ChatCompletionResponse:
    """将 API 非流式响应 dict 解析为 ChatCompletionResponse。"""
    choices_raw = data.get("choices", [])
    choices = []
    for c in choices_raw:
        msg = c.get("message", {})
        tool_calls_raw = msg.get("tool_calls", [])
        tool_calls = (
            [
                ToolCall(
                    id=tc["id"],
                    type=tc.get("type", "function"),
                    function=ToolCallFunction(
                        name=tc["function"]["name"],
                        arguments=tc["function"]["arguments"],
                    )
                    if tc.get("function")
                    else None,
                )
                for tc in (tool_calls_raw or [])
            ]
            if tool_calls_raw
            else None
        )

        choices.append(
            Choice(
                index=c.get("index", 0),
                finish_reason=c.get("finish_reason", "stop"),
                message=ChoiceMessage(
                    role=msg.get("role", "assistant"),
                    content=msg.get("content"),
                    reasoning_content=msg.get("reasoning_content"),
                    tool_calls=tool_calls or None,
                ),
            )
        )

    usage_raw = data.get("usage")
    usage = None
    if usage_raw:
        details_raw = usage_raw.get("completion_tokens_details")
        usage = Usage(
            prompt_tokens=usage_raw.get("prompt_tokens", 0),
            completion_tokens=usage_raw.get("completion_tokens", 0),
            total_tokens=usage_raw.get("total_tokens", 0),
            prompt_cache_hit_tokens=usage_raw.get("prompt_cache_hit_tokens"),
            prompt_cache_miss_tokens=usage_raw.get("prompt_cache_miss_tokens"),
            completion_tokens_details=CompletionTokensDetails(
                reasoning_tokens=details_raw.get("reasoning_tokens"),
            )
            if details_raw
            else None,
        )

    return ChatCompletionResponse(
        id=data.get("id", ""),
        object=data.get("object", "chat.completion"),
        created=data.get("created", 0),
        model=data.get("model", ""),
        system_fingerprint=data.get("system_fingerprint"),
        choices=choices,
        usage=usage,
    )
