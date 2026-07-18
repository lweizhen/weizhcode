# weizhCode 交互式纯对话阶段 Checklist

> 每一项都通过运行代码、自动测试或观察 TUI 行为来验证，聚焦系统行为，不依赖具体实现细节。

## 实现完整性

- [ ] 项目可通过 `uv run weizhcode` 启动进入终端 TUI（验证：在项目根目录运行启动命令，观察进入 TUI 而不是一次性输出后退出）
- [ ] TUI 显示可滚动对话消息区域和多行输入区域（验证：启动应用后观察界面结构）
- [ ] 输入单行消息并按 `Enter` 后，用户消息显示在对话区域并触发 AI 回复（验证：使用假 Provider 或真实 Provider 运行一次对话）
- [ ] 输入多行消息时，`Shift+Enter` 能在输入区域插入换行，`Enter` 能提交完整消息（验证：通过 Textual headless 测试或手动输入多行内容）
- [ ] 空白输入不会触发 Provider 请求（验证：提交空白输入后观察消息区和 Provider 调用记录）
- [ ] AI 回复在生成过程中逐步追加到同一条 AI 消息中（验证：使用假 Provider 输出多个文本片段，观察消息按片段增长）
- [ ] 同一进程内连续两轮对话会保留完整前文（验证：第二轮 Provider 收到第一轮用户消息和 AI 回复）
- [ ] 会话退出后不恢复上一轮历史（验证：重启应用后对话区域不加载旧会话）
- [ ] 输入 `/exit` 或 `/quit` 后程序正常退出（验证：在 TUI 中输入退出命令，观察返回终端）
- [ ] 常见终端快捷键可以让程序正常结束或优雅中断（验证：手动触发快捷键，观察程序不留下失控界面）

## 配置

- [ ] 默认读取当前工作目录下的 `weizhcode.yaml`（验证：在项目根目录提供配置后启动，观察使用该配置）
- [ ] 合法的 `default + providers` YAML 能被成功解析（验证：运行配置解析测试）
- [ ] 默认配置名能正确匹配 `providers` 列表中的供应商（验证：配置多个 Provider，切换 `default` 后观察选择结果）
- [ ] 每个 Provider 必须包含 `name`、`protocol`、`model`、`base_url`、`api_key`、`thinking` 六个字段（验证：分别删除字段运行配置测试，观察明确错误）
- [ ] `protocol` 只接受 `anthropic`、`openai`、`qwen`（验证：使用非法协议运行配置测试，观察明确错误）
- [ ] 每个 Provider 必须显式填写 `base_url`（验证：删除 `base_url` 后启动或测试，观察明确错误）
- [ ] `api_key` 支持 `${ENV_VAR}` 环境变量引用（验证：设置环境变量后解析配置，观察 API key 被正确展开）
- [ ] 环境变量不存在时显示明确错误且不泄露密钥（验证：引用不存在变量，观察错误信息只包含变量名或安全描述）
- [ ] 示例配置文件不包含真实 API key（验证：检查 `weizhcode.yaml.example` 内容）
- [ ] `thinking: true` 与 `thinking: false` 都能解析成功（验证：分别运行配置解析测试）

## Provider

- [ ] Provider 层统一输出 `start`、`text_delta`、`done`、`error` 事件（验证：运行 Provider 事件测试）
- [ ] TUI 不依赖供应商原始流式事件名（验证：使用假 Provider 驱动 TUI 测试，TUI 只消费统一事件）
- [ ] Anthropic 配置会创建 Claude Provider（验证：使用 `protocol: anthropic` 运行 Provider 工厂测试）
- [ ] OpenAI 配置会创建 OpenAI Provider（验证：使用 `protocol: openai` 运行 Provider 工厂测试）
- [ ] Qwen 配置会创建 Qwen Provider（验证：使用 `protocol: qwen` 运行 Provider 工厂测试）
- [ ] Anthropic Provider 请求体包含模型、消息、流式标记和代码内默认最大输出长度（验证：运行请求映射测试）
- [ ] Anthropic Provider 不会因 `thinking: true` 启用真实 extended thinking 参数（验证：运行请求映射测试，确认请求中没有 thinking 配置）
- [ ] OpenAI Provider 使用 Responses API 形状发送历史输入和流式标记（验证：运行请求映射测试）
- [ ] Qwen Provider 使用 OpenAI-compatible Chat Completions 形状发送消息和流式标记（验证：运行请求映射测试）
- [ ] 三个 Provider 的文本增量都能归一为 `text_delta`（验证：运行模拟流式事件测试）
- [ ] HTTP、认证、网络、JSON 解析和流式中断错误会转换为可展示错误（验证：运行错误路径测试）
- [ ] Provider 错误内容不会包含 API key（验证：运行密钥脱敏测试）

## TUI 行为

- [ ] 生成开始后当前 AI 消息占位出现（验证：使用假 Provider 的 `start` 事件观察消息区）
- [ ] 多个文本增量按顺序追加，不创建多条零碎 AI 消息（验证：使用假 Provider 输出三个片段并观察最终消息）
- [ ] 生成完成后完整 AI 回复写入会话历史（验证：运行 TUI 流式完成测试）
- [ ] 生成期间不会因为重复提交导致消息历史错乱（验证：在假 Provider 慢速输出时尝试重复提交）
- [ ] 生成完成后输入区域恢复可用并保持焦点（验证：运行 headless 测试或手动观察）
- [ ] Provider 返回 `error` 时弹出错误面板（验证：使用假 Provider 输出错误事件）
- [ ] Provider 抛出异常时弹出错误面板（验证：使用假 Provider 抛出异常）
- [ ] 用户确认错误面板后能回到主界面继续输入（验证：关闭错误面板后再次提交消息）
- [ ] 出错时未完成 AI 回复不会写入会话历史（验证：运行错误路径会话历史测试）
- [ ] 错误面板不会展示明文 API key（验证：构造包含密钥的底层错误，观察展示内容已脱敏）

## 编译与测试

- [ ] 项目依赖可通过 `uv` 安装和运行（验证：运行 `uv run python -m pytest`）
- [ ] 配置测试通过（验证：运行 `uv run python -m pytest tests/test_config.py`）
- [ ] 会话历史测试通过（验证：运行 `uv run python -m pytest tests/test_conversation.py`）
- [ ] Provider 事件与协议映射测试通过（验证：运行 `uv run python -m pytest tests/test_provider_events.py`）
- [ ] Textual TUI headless 测试通过（验证：运行 `uv run python -m pytest tests/test_tui.py`）
- [ ] 全部自动测试不访问真实 Anthropic、OpenAI 或通义千问 API（验证：测试在没有真实 API key 时仍通过）
- [ ] 全部自动测试通过（验证：运行 `uv run python -m pytest`）

## 端到端场景

- [ ] 场景 1：使用假 Provider 启动 TUI，输入“你好”，AI 消息分片显示为完整回复，随后输入第二轮问题，Provider 收到完整历史（验证：Textual headless 端到端测试通过）
- [ ] 场景 2：提供合法 `weizhcode.yaml`，运行 `uv run weizhcode`，进入 TUI 后输入问题并看到流式回复（验证：手动运行并观察界面）
- [ ] 场景 3：提供缺少必填字段的配置，启动应用后看到错误面板或可读错误，不出现崩溃堆栈（验证：手动运行或自动测试）
- [ ] 场景 4：配置引用不存在的 API key 环境变量，启动后显示明确错误且不泄露密钥（验证：手动运行或自动测试）
- [ ] 场景 5：如果本机具备真实 Anthropic API key，使用 `protocol: anthropic` 手动完成一次流式对话（验证：观察 Claude 流式文本进入消息区）
- [ ] 场景 6：如果本机具备真实 OpenAI API key，使用 `protocol: openai` 手动完成一次流式对话（验证：观察 OpenAI Responses API 流式文本进入消息区）
- [ ] 场景 7：如果本机具备真实通义千问 API key，使用 `protocol: qwen` 手动完成一次流式对话（验证：观察 Qwen compatible 流式文本进入消息区）

## 范围边界

- [ ] 本阶段没有 tool use、函数调用、MCP 或插件系统入口（验证：检查用户界面、配置和测试均不暴露相关能力）
- [ ] 本阶段不会让模型读取或修改本地文件（验证：检查端到端场景和 Provider 请求只包含对话历史）
- [ ] 本阶段不会让模型执行 Shell 命令（验证：检查用户界面和代码行为没有命令执行能力）
- [ ] 本阶段不实现长期记忆或会话持久化（验证：退出重启后历史不恢复）
- [ ] 本阶段不要求发布安装流程（验证：只使用项目内 `uv run weizhcode` 验收）
