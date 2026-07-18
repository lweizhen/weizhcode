# weizhCode 交互式纯对话阶段 Plan

## 架构概览

本阶段实现一个 Python 包形式的终端 TUI 应用，通过 `uv run weizhcode` 启动。应用启动后读取当前工作目录下的 `weizhcode.yaml`，解析默认 Provider 配置，创建统一 Provider 实例，然后由 Textual TUI 驱动用户输入、流式回复展示和错误面板。

整体分为五层：入口层、配置层、会话层、Provider 层和 TUI 层。入口层负责启动应用；配置层负责读取与校验 YAML；会话层保存当前进程内的多轮消息；Provider 层屏蔽 Anthropic、OpenAI 和通义千问协议差异；TUI 层只消费统一事件并更新界面。

HTTP 流式请求采用异步客户端和 SSE 事件解析。每个具体 Provider 负责把所属协议的流式事件转换成统一的 `ProviderEvent`，TUI 不直接感知 `response.output_text.delta`、`content_block_delta` 或 OpenAI-compatible chunk 等原始事件名。

## 核心数据结构

### `AppConfig`

字段：

- `default: str`：默认供应商配置名。
- `providers: list[ProviderConfig]`：供应商配置列表。

用途：表示 `weizhcode.yaml` 的完整配置。

### `ProviderConfig`

字段：

- `name: str`：供应商标识名。
- `protocol: Literal["anthropic", "openai", "qwen"]`：协议类型。
- `model: str`：模型名称。
- `base_url: str`：请求地址根路径。
- `api_key: str`：解析后的 API key，支持从 `${ENV_VAR}` 展开。
- `thinking: bool | None`：是否启用扩展思考；第一版只解析和保留，不实际启用请求能力。

用途：创建具体 Provider 的配置输入。

### `ChatMessage`

字段：

- `role: Literal["user", "assistant"]`：消息角色。
- `content: str`：消息文本。

用途：保存当前进程内的对话历史，并作为 Provider 请求输入。

### `ProviderEvent`

字段：

- `type: Literal["start", "text_delta", "done", "error"]`：统一事件类型。
- `text: str = ""`：文本增量，仅 `text_delta` 使用。
- `message: str = ""`：错误说明，仅 `error` 使用。

用途：Provider 向 TUI 输出的唯一事件协议。

### `Provider`

接口：

```python
class Provider(Protocol):
    async def stream_chat(
        self,
        messages: list[ChatMessage],
    ) -> AsyncIterator[ProviderEvent]:
        ...
```

用途：所有模型后端共同实现的统一流式对话接口。

### `Conversation`

接口：

```python
class Conversation:
    def add_user_message(self, content: str) -> None: ...
    def add_assistant_message(self, content: str) -> None: ...
    def messages(self) -> list[ChatMessage]: ...
```

用途：保存当前进程内完整多轮历史。程序退出后不持久化。

## 模块设计

### 入口模块

**职责：** 提供 `weizhcode` 命令入口，读取配置，创建 Provider、Conversation 和 Textual App，并启动 TUI。

**对外接口：** `main() -> None`

**依赖：** 配置模块、Provider 工厂、TUI 应用。

### 配置模块

**职责：** 从当前工作目录读取 `weizhcode.yaml`，解析 YAML，校验 `default`、`providers` 和每个 Provider 的六个字段，展开 `${ENV_VAR}` 形式的 API key，并确保默认配置存在。

**对外接口：**

```python
def load_config(path: Path = Path("weizhcode.yaml")) -> AppConfig: ...
def resolve_default_provider(config: AppConfig) -> ProviderConfig: ...
```

**依赖：** `PyYAML`、标准库环境变量读取。

### 会话模块

**职责：** 保存当前进程内的用户和 AI 消息历史，为每次 Provider 请求提供完整上下文，并在流式完成后写入完整 AI 回复。

**对外接口：** `Conversation`

**依赖：** 核心数据结构。

### Provider 工厂模块

**职责：** 根据 `ProviderConfig.protocol` 创建具体 Provider。非法协议在配置阶段或工厂阶段转换成用户可理解的错误。

**对外接口：**

```python
def create_provider(config: ProviderConfig) -> Provider: ...
```

**依赖：** 三个具体 Provider 实现。

### Anthropic Provider

**职责：** 使用 Claude Messages API 发起 SSE 流式请求，把 Claude 文本增量事件转换为 `text_delta`。第一版解析 `thinking` 字段但不向请求中加入 extended thinking 参数。

**对外接口：** 实现 `Provider.stream_chat`

**请求策略：** 向 Anthropic Messages 端点发送 `model`、固定代码内 `max_tokens`、`messages` 和 `stream: true`。认证使用 API key header，版本 header 使用当前 Claude Messages API 版本。

### OpenAI Provider

**职责：** 使用 OpenAI 官方 Responses API 发起流式请求，把 `response.output_text.delta` 转换为 `text_delta`，把完成和错误事件转换为统一事件。

**对外接口：** 实现 `Provider.stream_chat`

**请求策略：** 向 Responses 端点发送 `model`、`input`、`stream: true`、`store: false` 和代码内默认最大输出长度。认证使用 Bearer token。

### Qwen Provider

**职责：** 使用通义千问 OpenAI-compatible Chat Completions 协议发起流式请求，把 compatible chunk 中的文本 delta 转换为 `text_delta`。

**对外接口：** 实现 `Provider.stream_chat`

**请求策略：** 向 `base_url` 下的 Chat Completions 端点发送 `model`、`messages`、`stream: true` 和代码内默认最大输出长度。认证使用 Bearer token。

### SSE/HTTP 模块

**职责：** 统一执行异步 POST 流式请求，读取 SSE 行事件，处理 `[DONE]`、JSON 事件体、HTTP 状态错误、网络异常和流式中断。

**对外接口：**

```python
async def stream_sse(
    method: str,
    url: str,
    headers: dict[str, str],
    json_body: dict[str, Any],
) -> AsyncIterator[SSEEvent]:
    ...
```

**依赖：** `httpx`。

### TUI 应用模块

**职责：** 使用 Textual 构建主界面。消息区展示用户消息和 AI 消息，输入区支持多行编辑，提交后启动异步流式生成任务，收到 `text_delta` 时实时追加到当前 AI 消息。错误事件或异常通过模态错误面板显示，用户确认后继续。

**对外接口：** `WeizhCodeApp`

**依赖：** Textual、Conversation、Provider。

### 测试辅助 Provider

**职责：** 为自动测试提供可控的假流式事件，覆盖正常流式、多轮历史和错误路径，不访问真实 API。

**对外接口：** 实现 `Provider.stream_chat`

**依赖：** 核心数据结构。

## 模块交互

```text
uv run weizhcode
  -> main()
  -> load_config("weizhcode.yaml")
  -> resolve_default_provider()
  -> create_provider()
  -> WeizhCodeApp.run()
  -> 用户提交消息
  -> Conversation.add_user_message()
  -> Provider.stream_chat(Conversation.messages())
  -> start/text_delta/done/error
  -> TUI 实时追加 AI 消息或显示错误面板
  -> done 后 Conversation.add_assistant_message()
```

当 Provider 输出 `error` 或抛出异常时，TUI 显示错误面板，不把未完成的 AI 文本加入会话历史。用户确认后可以继续输入或退出。

## 文件组织

```text
weizhcode-python/
├── pyproject.toml                    — 项目元数据、依赖、命令入口和测试配置
├── weizhcode.yaml.example            — 示例配置，不包含真实 API key
├── src/
│   └── weizhcode/
│       ├── __init__.py               — 包版本与公共导出
│       ├── __main__.py               — python -m 入口辅助
│       ├── cli.py                    — `weizhcode` 命令入口
│       ├── config.py                 — YAML 配置读取、校验和环境变量展开
│       ├── conversation.py           — 当前进程内会话历史
│       ├── errors.py                 — 面向用户的错误类型
│       ├── models.py                 — ChatMessage、ProviderConfig、ProviderEvent 等结构
│       ├── tui.py                    — Textual 应用、消息区、输入区、错误面板
│       └── providers/
│           ├── __init__.py           — Provider 工厂导出
│           ├── base.py               — Provider 协议接口
│           ├── anthropic.py          — Claude Messages Provider
│           ├── openai.py             — OpenAI Responses Provider
│           ├── qwen.py               — Qwen compatible Provider
│           └── sse.py                — 共享 SSE/HTTP 流式读取
└── tests/
    ├── test_config.py                — 配置解析、字段校验、环境变量展开
    ├── test_conversation.py          — 多轮历史保存
    ├── test_provider_events.py       — 假 Provider 和统一事件约束
    └── test_tui.py                   — Textual headless 交互测试
```

## 技术决策

| 决策点 | 选择 | 理由 |
|---|---|---|
| 项目布局 | `src/weizhcode` | 标准 Python 包布局，避免测试时误导入当前目录散落文件 |
| 依赖管理 | `pyproject.toml` + `uv` | 符合用户确认的启动与依赖方式，便于后续 CLI 化 |
| TUI 框架 | Textual | 支持完整终端应用、TextArea、多屏幕/模态框和 headless 测试 |
| 输入组件 | Textual `TextArea` 派生输入框 | 满足多行输入，并可自定义 `Enter` 提交、`Shift+Enter` 换行 |
| 消息展示 | 可滚动消息容器 + 动态消息组件 | 能实时追加当前 AI 消息，并保留本轮界面历史 |
| Provider 输出 | `start/text_delta/done/error` | 足够支撑第一版流式 UI，又给后续 thinking/tool 事件留扩展空间 |
| HTTP 实现 | `httpx` 异步流式请求 | 三家协议都可走 HTTP/SSE，减少 SDK 差异对统一接口的影响 |
| 最大输出长度 | 代码内默认值 | 保持 YAML 六字段不扩张，同时满足多数 API 的必填或常用参数要求 |
| Anthropic thinking | 解析但不启用 | 与已批准 spec 一致，保留字段边界但不实现真实 extended thinking |
| OpenAI 协议 | Responses API | 与用户确认一致，采用 OpenAI 官方当前主推对话生成接口 |
| 通义千问协议 | OpenAI-compatible Chat Completions | 与用户确认一致，便于复用 compatible 流式事件解析 |
| 自动测试 | 假 Provider + Textual `run_test()` | 避免线上 API、额度和网络影响核心行为验证 |
| 密钥处理 | 环境变量展开 + 错误脱敏 | 降低把真实 API key 写进仓库或错误输出的风险 |

## Spec 覆盖关系

| Spec 需求 | 设计归属 |
|---|---|
| F1-F5 | 入口模块、TUI 应用模块 |
| F6-F11 | 配置模块、ProviderConfig |
| F12-F14 | 三个具体 Provider |
| F15-F17 | Provider 事件、SSE/HTTP 模块、TUI 应用模块 |
| F18-F19 | Conversation |
| F20 | 配置模块、Anthropic Provider |
| F21 | TUI 错误面板、错误类型 |
| F22-F23 | 测试辅助 Provider、测试文件 |
