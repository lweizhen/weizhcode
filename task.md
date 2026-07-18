# weizhCode 交互式纯对话阶段 Tasks

## 文件清单

| 操作 | 文件 | 职责 |
|---|---|---|
| 新建 | `pyproject.toml` | 项目元数据、依赖、`weizhcode` 命令入口、pytest 配置 |
| 新建 | `weizhcode.yaml.example` | 示例配置，展示 `default + providers` 结构和环境变量 API key |
| 新建 | `src/weizhcode/__init__.py` | 包版本与基础导出 |
| 新建 | `src/weizhcode/__main__.py` | `python -m weizhcode` 辅助入口 |
| 新建 | `src/weizhcode/cli.py` | `uv run weizhcode` 命令入口 |
| 新建 | `src/weizhcode/models.py` | `AppConfig`、`ProviderConfig`、`ChatMessage`、`ProviderEvent` |
| 新建 | `src/weizhcode/errors.py` | 面向用户的配置、Provider、流式错误类型 |
| 新建 | `src/weizhcode/config.py` | YAML 配置读取、字段校验、默认 Provider 解析、环境变量展开 |
| 新建 | `src/weizhcode/conversation.py` | 当前进程内多轮对话历史 |
| 新建 | `src/weizhcode/providers/__init__.py` | Provider 工厂导出 |
| 新建 | `src/weizhcode/providers/base.py` | Provider 协议接口和共享常量 |
| 新建 | `src/weizhcode/providers/sse.py` | 异步 HTTP SSE 流式读取和基础解析 |
| 新建 | `src/weizhcode/providers/anthropic.py` | Anthropic Claude Messages Provider |
| 新建 | `src/weizhcode/providers/openai.py` | OpenAI Responses Provider |
| 新建 | `src/weizhcode/providers/qwen.py` | 通义千问 OpenAI-compatible Provider |
| 新建 | `src/weizhcode/tui.py` | Textual 主应用、消息区、输入区、错误面板 |
| 新建 | `tests/test_config.py` | 配置解析与错误测试 |
| 新建 | `tests/test_conversation.py` | 多轮历史测试 |
| 新建 | `tests/test_provider_events.py` | Provider 工厂、假流式 Provider、事件约束测试 |
| 新建 | `tests/test_tui.py` | Textual headless TUI 交互测试 |

## T1: 创建 Python 项目骨架

**文件：** `pyproject.toml`、`src/weizhcode/__init__.py`、`src/weizhcode/__main__.py`、`src/weizhcode/cli.py`

**依赖：** 无

**步骤：**

1. 创建 `src/weizhcode` 包目录。
2. 在 `pyproject.toml` 中声明项目名称、Python 版本、运行依赖和测试依赖。
3. 配置命令入口 `weizhcode = "weizhcode.cli:main"`。
4. 在 `cli.py` 中放置可运行入口的最小壳，暂不启动完整 TUI。
5. 在 `__main__.py` 中转发到 `cli.main()`。

**验证：** 运行 `uv run weizhcode`，期望命令能进入最小入口并正常结束；运行 `uv run python -m weizhcode`，期望同样正常结束。

## T2: 定义核心模型和错误类型

**文件：** `src/weizhcode/models.py`、`src/weizhcode/errors.py`

**依赖：** T1

**步骤：**

1. 定义 `AppConfig`、`ProviderConfig`、`ChatMessage`、`ProviderEvent` 数据结构。
2. 将 `protocol`、消息角色、事件类型限制为 spec 和 plan 中的固定取值。
3. 定义面向用户的基础错误类型。
4. 为配置错误、Provider 错误和流式错误建立可区分类型。

**验证：** 运行 `uv run python -m pytest tests/test_config.py tests/test_provider_events.py`，期望相关导入和类型构造测试通过。

## T3: 实现 YAML 配置读取与校验

**文件：** `src/weizhcode/config.py`、`tests/test_config.py`

**依赖：** T2

**步骤：**

1. 实现从当前工作目录默认读取 `weizhcode.yaml`。
2. 校验顶层 `default` 和 `providers` 是否存在且形状正确。
3. 校验每个 Provider 是否包含六个必需字段。
4. 校验 `protocol` 是否为 `anthropic`、`openai` 或 `qwen`。
5. 校验每个 Provider 必须显式提供 `base_url`。
6. 实现 `${ENV_VAR}` 形式的 `api_key` 展开。
7. 当环境变量缺失时返回脱敏的可读错误。
8. 实现默认 Provider 名称解析。

**验证：** 运行 `uv run python -m pytest tests/test_config.py`，期望合法配置、缺字段、非法协议、缺默认 Provider、环境变量展开和环境变量缺失测试全部通过。

## T4: 提供示例配置文件

**文件：** `weizhcode.yaml.example`

**依赖：** T3

**步骤：**

1. 写入顶层 `default` 和 `providers` 示例。
2. 分别给出 `anthropic`、`openai`、`qwen` 三种 Provider 示例。
3. 使用环境变量形式展示 API key。
4. 保留 `thinking` 字段，并标注示例值为布尔值。
5. 不写入任何真实密钥。

**验证：** 将示例配置复制为临时测试输入并运行配置解析测试，期望可成功解析默认 Provider。

## T5: 实现当前进程内会话历史

**文件：** `src/weizhcode/conversation.py`、`tests/test_conversation.py`

**依赖：** T2

**步骤：**

1. 实现 `Conversation.add_user_message()`。
2. 实现 `Conversation.add_assistant_message()`。
3. 实现 `Conversation.messages()` 返回当前完整历史。
4. 确保返回历史不会被调用方意外改坏内部状态。
5. 不实现任何持久化逻辑。

**验证：** 运行 `uv run python -m pytest tests/test_conversation.py`，期望多轮添加、顺序保持和外部修改隔离测试通过。

## T6: 定义 Provider 基础接口和工厂

**文件：** `src/weizhcode/providers/base.py`、`src/weizhcode/providers/__init__.py`、`tests/test_provider_events.py`

**依赖：** T2

**步骤：**

1. 定义 `Provider` 协议接口。
2. 定义代码内默认最大输出长度常量。
3. 实现 `create_provider(config)` 工厂函数。
4. 将 `anthropic`、`openai`、`qwen` 分派到对应 Provider。
5. 对未知协议返回可读 Provider 错误。

**验证：** 运行 `uv run python -m pytest tests/test_provider_events.py`，期望三种协议可创建正确 Provider，未知协议返回明确错误。

## T7: 实现共享 SSE/HTTP 流读取

**文件：** `src/weizhcode/providers/sse.py`、`tests/test_provider_events.py`

**依赖：** T2

**步骤：**

1. 使用异步 HTTP 客户端发起 POST 请求。
2. 支持传入 URL、headers 和 JSON body。
3. 逐行读取 SSE 响应。
4. 解析 `event:` 与 `data:` 行。
5. 正确处理 `[DONE]`。
6. 将 HTTP 非成功状态、网络异常和 JSON 解析失败转换为流式错误。
7. 确保错误信息不包含 API key。

**验证：** 运行 `uv run python -m pytest tests/test_provider_events.py`，期望模拟 SSE 正常事件、`[DONE]`、HTTP 错误和中断测试通过。

## T8: 实现 Anthropic Provider

**文件：** `src/weizhcode/providers/anthropic.py`、`tests/test_provider_events.py`

**依赖：** T6、T7

**步骤：**

1. 将 `ChatMessage` 历史转换为 Claude Messages 请求格式。
2. 使用配置中的 `model`、`base_url` 和 `api_key`。
3. 在请求体中加入 `stream: true` 和代码内默认最大输出长度。
4. 添加 Anthropic 所需认证与版本 header。
5. 解析 Claude 流式文本增量事件并输出统一 `text_delta`。
6. 输出 `start` 与 `done` 事件。
7. 保留 `thinking` 字段但不把 extended thinking 参数加入请求。

**验证：** 运行 `uv run python -m pytest tests/test_provider_events.py`，期望 Anthropic 请求体、header、文本增量映射、`thinking` 不启用测试通过。

## T9: 实现 OpenAI Provider

**文件：** `src/weizhcode/providers/openai.py`、`tests/test_provider_events.py`

**依赖：** T6、T7

**步骤：**

1. 将 `ChatMessage` 历史转换为 Responses API `input`。
2. 使用配置中的 `model`、`base_url` 和 `api_key`。
3. 在请求体中加入 `stream: true`、`store: false` 和代码内默认最大输出长度。
4. 添加 Bearer token 认证 header。
5. 解析 `response.output_text.delta` 并输出统一 `text_delta`。
6. 解析完成与错误事件并转换为 `done` 或 `error`。

**验证：** 运行 `uv run python -m pytest tests/test_provider_events.py`，期望 OpenAI 请求体、header、文本增量映射和错误事件测试通过。

## T10: 实现 Qwen Provider

**文件：** `src/weizhcode/providers/qwen.py`、`tests/test_provider_events.py`

**依赖：** T6、T7

**步骤：**

1. 将 `ChatMessage` 历史转换为 OpenAI-compatible Chat Completions `messages`。
2. 使用配置中的 `model`、`base_url` 和 `api_key`。
3. 在请求体中加入 `stream: true` 和代码内默认最大输出长度。
4. 添加 Bearer token 认证 header。
5. 解析 compatible chunk 中的文本 delta 并输出统一 `text_delta`。
6. 正确处理 `[DONE]` 完成事件。

**验证：** 运行 `uv run python -m pytest tests/test_provider_events.py`，期望 Qwen 请求体、header、文本增量映射和完成事件测试通过。

## T11: 搭建 Textual 主界面布局

**文件：** `src/weizhcode/tui.py`、`tests/test_tui.py`

**依赖：** T2、T5、T6

**步骤：**

1. 创建 `WeizhCodeApp`。
2. 添加可滚动消息区域。
3. 添加基于 Textual `TextArea` 的输入区域。
4. 添加基础标题或状态区域，显示当前 Provider 名称。
5. 设置初始焦点到输入区域。
6. 建立基础样式，保证消息区和输入区在终端内稳定布局。

**验证：** 运行 `uv run python -m pytest tests/test_tui.py`，期望 Textual headless 启动后能找到消息区域、输入区域和当前 Provider 信息。

## T12: 实现 TUI 输入提交和退出

**文件：** `src/weizhcode/tui.py`、`tests/test_tui.py`

**依赖：** T11

**步骤：**

1. 实现 `Enter` 提交当前输入。
2. 实现 `Shift+Enter` 在输入区域插入换行。
3. 忽略空白输入。
4. 输入 `/exit` 或 `/quit` 时退出应用。
5. 支持常见终端快捷键退出或优雅中断。
6. 提交后清空输入区域。

**验证：** 运行 `uv run python -m pytest tests/test_tui.py`，期望单行提交、多行提交、空输入忽略、命令退出测试通过。

## T13: 实现流式回复追加

**文件：** `src/weizhcode/tui.py`、`tests/test_tui.py`

**依赖：** T5、T6、T11、T12

**步骤：**

1. 提交用户消息后在消息区新增用户消息。
2. 创建当前 AI 消息占位。
3. 异步消费 Provider 的统一事件流。
4. 收到 `text_delta` 时实时追加到当前 AI 消息。
5. 收到 `done` 时把完整 AI 回复写入 `Conversation`。
6. 生成期间防止重复提交导致状态混乱。
7. 生成完成后恢复输入焦点。

**验证：** 运行 `uv run python -m pytest tests/test_tui.py`，期望假 Provider 的多个文本增量会按顺序追加到同一条 AI 消息，并写入会话历史。

## T14: 实现 TUI 错误面板

**文件：** `src/weizhcode/tui.py`、`tests/test_tui.py`

**依赖：** T11、T13

**步骤：**

1. 创建模态错误面板。
2. Provider 输出 `error` 时展示错误面板。
3. Provider 抛出异常时展示错误面板。
4. 用户确认错误面板后回到主界面。
5. 出错时不把未完成 AI 文本写入会话历史。
6. 确保错误面板内容不包含 API key。

**验证：** 运行 `uv run python -m pytest tests/test_tui.py`，期望错误事件、异常路径、确认返回和密钥脱敏测试通过。

## T15: 串联 CLI 启动完整应用

**文件：** `src/weizhcode/cli.py`、`src/weizhcode/__main__.py`、`src/weizhcode/tui.py`

**依赖：** T3、T6、T11

**步骤：**

1. 在 `cli.main()` 中加载当前目录配置。
2. 解析默认 Provider。
3. 创建具体 Provider。
4. 创建 `Conversation`。
5. 启动 `WeizhCodeApp`。
6. 配置加载失败时以用户可读方式展示错误。

**验证：** 准备有效示例配置后运行 `uv run weizhcode`，期望进入完整 TUI；准备缺字段配置后运行，期望显示可读配置错误。

## T16: 完成自动测试覆盖

**文件：** `tests/test_config.py`、`tests/test_conversation.py`、`tests/test_provider_events.py`、`tests/test_tui.py`

**依赖：** T3、T5、T8、T9、T10、T14、T15

**步骤：**

1. 补齐配置成功与失败路径测试。
2. 补齐多轮历史测试。
3. 补齐三个 Provider 的请求映射与事件映射测试。
4. 补齐 TUI 提交、流式追加、错误面板和退出测试。
5. 确保测试不访问真实 API。

**验证：** 运行 `uv run python -m pytest`，期望全部自动测试通过且不需要真实 API key。

## T17: 执行本地端到端手动验收

**文件：** `weizhcode.yaml.example`、`src/weizhcode/*`

**依赖：** T16

**步骤：**

1. 基于示例配置创建本地 `weizhcode.yaml`，使用环境变量引用 API key。
2. 至少使用一个真实可用 Provider 运行 `uv run weizhcode`。
3. 在 TUI 中发送单轮问题，观察流式追加。
4. 发送第二轮问题，观察是否参考前文。
5. 输入 `/exit` 或 `/quit`，确认正常退出。
6. 如具备三家真实密钥，再分别手动切换 `default` 验证三家协议。

**验证：** 观察 TUI 行为符合 spec 验收标准；真实 API 失败时记录错误面板内容，不影响自动测试通过结论。

## 执行顺序

```text
T1 -> T2 -> T3 -> T4 -> T5 -> T6 -> T7 -> T8 -> T9 -> T10 -> T11 -> T12 -> T13 -> T14 -> T15 -> T16 -> T17
```

## 阶段性验证命令

```text
uv run python -m pytest tests/test_config.py
uv run python -m pytest tests/test_conversation.py
uv run python -m pytest tests/test_provider_events.py
uv run python -m pytest tests/test_tui.py
uv run python -m pytest
uv run weizhcode
```
