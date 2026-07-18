# weizhCode 交互式纯对话阶段 Spec

## 背景

weizhCode 是一个从零开始构建的命令行 AI 助手，长期目标是成为类似 Claude Code 的 Coding Agent。本阶段只实现最小可用的纯对话能力：用户在终端启动 weizhCode 后进入交互式 TUI，对 AI 提问，并看到模型回复以流式方式实时出现在界面中。

本阶段的重点是打通终端交互、配置驱动的模型后端切换、统一 Provider 边界、流式输出和当前进程内的多轮上下文。Tool use、文件操作、代码编辑、Shell 执行等 agent 能力全部留到后续阶段。

## 目标

- 用户可以在项目内通过启动命令进入 weizhCode 的终端 TUI。
- 用户可以在 TUI 中输入单行或多行问题，并提交给 AI。
- 系统根据当前目录下的 YAML 配置选择默认模型后端。
- 系统支持 Anthropic Claude、OpenAI 和通义千问三种后端。
- AI 回复以流式文本增量实时追加到消息区域。
- 同一运行进程内支持多轮对话，AI 能参考本次会话前文。
- Provider 层对 TUI 暴露统一事件，使后续新增后端时不需要改动 TUI 的核心对话逻辑。

## 功能需求

- F1：用户在项目内运行启动命令后，系统进入终端 TUI，而不是一次性命令输出模式。
- F2：TUI 至少包含可滚动的对话消息区域和可输入多行内容的输入区域。
- F3：用户按 `Enter` 提交当前输入内容，按 `Shift+Enter` 在输入区域内换行。
- F4：用户输入 `/exit` 或 `/quit` 后，系统正常退出当前会话。
- F5：用户可以通过常见终端快捷键退出当前会话。
- F6：系统默认读取当前工作目录下的 YAML 配置文件。
- F7：配置文件使用顶层默认配置名加供应商列表的结构，系统启动时自动选择默认配置对应的供应商。
- F8：每个供应商配置包含且只要求以下字段：`name`、`protocol`、`model`、`base_url`、`api_key`、`thinking`。
- F9：`protocol` 字段支持固定取值：`anthropic`、`openai`、`qwen`。
- F10：`api_key` 字段支持直接值，也支持通过环境变量引用。
- F11：每个供应商配置都必须显式提供 `base_url`。
- F12：当默认供应商为 Anthropic Claude 时，系统按 Claude 对话协议发起流式请求。
- F13：当默认供应商为 OpenAI 时，系统按 OpenAI 官方 Responses API 发起流式请求。
- F14：当默认供应商为通义千问时，系统按通义千问 OpenAI-compatible Chat Completions 协议发起流式请求。
- F15：模型回复必须以流式增量展示，收到新增文本后实时追加到当前 AI 消息中。
- F16：Provider 层对外输出统一事件，事件类型至少包括 `start`、`text_delta`、`done`、`error`。
- F17：TUI 只消费统一 Provider 事件，不直接处理任一供应商的原始流式事件。
- F18：同一进程内的多轮对话保留完整用户消息和 AI 消息，后续请求会携带前文上下文。
- F19：会话历史只在当前进程内保存，程序退出后不需要恢复历史。
- F20：配置中的 `thinking` 字段在第一版中保留并被解析，但暂不真正启用 Claude extended thinking 请求能力。
- F21：当发生配置错误、认证错误、网络错误、模型错误或流式中断时，TUI 通过错误面板展示问题，用户确认后可以继续操作或退出。
- F22：自动测试使用假的流式 Provider 验证 TUI 和对话流程，不要求真实调用三家线上 API。
- F23：真实 API 连通性作为手动验收内容，不作为自动测试的强制前置条件。

## 非功能需求

- N1：本阶段使用 Python 开发，并通过项目内命令启动。
- N2：依赖管理采用 `pyproject.toml` 与 `uv`。
- N3：TUI 使用 Textual 构建，可使用 Rich 作为底层或辅助渲染能力。
- N4：启动命令为 `uv run weizhcode`。
- N5：流式展示应尽量低延迟，避免等待完整响应结束后再显示文本。
- N6：供应商切换必须通过配置完成，不要求用户修改代码。
- N7：API key 不应出现在普通输出、错误面板或测试输出中。
- N8：配置解析失败时应说明具体缺失字段、非法字段或无法解析的环境变量。
- N9：Provider 抽象应便于后续新增模型后端。
- N10：第一版应能在常见 Windows PowerShell 终端环境中运行。

## 不做的事

- 不实现 tool use、函数调用、MCP 或插件系统。
- 不实现文件读取、文件写入、代码编辑、补丁生成或项目索引。
- 不执行 Shell 命令，也不让模型控制本地环境。
- 不实现长期记忆、会话持久化、历史记录导出或多会话管理。
- 不实现模型路由、多模型并发、自动降级、用量统计或成本统计。
- 不实现系统提示词配置或内置系统提示词。
- 不实现 Claude extended thinking 的真实请求启用，只保留配置字段和后续扩展边界。
- 不实现发布安装流程，不要求支持 `pipx install` 或 wheel 安装后的全局命令。
- 不强制自动测试真实访问 Anthropic、OpenAI 或通义千问线上 API。

## 验收标准

- AC1：在项目内运行 `uv run weizhcode` 后，用户能进入终端 TUI。
- AC2：TUI 显示对话消息区域和输入区域，用户可以输入内容。
- AC3：用户输入单行问题并按 `Enter` 后，问题出现在对话区域并被提交给当前默认 Provider。
- AC4：用户在输入区域中可以通过 `Shift+Enter` 输入多行内容，并能提交完整多行消息。
- AC5：使用合法 YAML 配置时，系统能读取默认供应商配置并选择对应后端。
- AC6：当配置缺少 `default`、`providers` 或供应商六个必需字段之一时，系统显示明确错误面板。
- AC7：当 `api_key` 使用环境变量引用且变量不存在时，系统显示明确错误面板，并且不泄露密钥文本。
- AC8：使用 `protocol: anthropic` 的有效配置时，系统能通过 Claude 协议完成一次流式对话。
- AC9：使用 `protocol: openai` 的有效配置时，系统能通过 OpenAI Responses API 完成一次流式对话。
- AC10：使用 `protocol: qwen` 的有效配置时，系统能通过通义千问 OpenAI-compatible Chat Completions 完成一次流式对话。
- AC11：AI 回复在生成过程中逐步追加到同一条 AI 消息中，而不是等完整生成后一次性显示。
- AC12：连续进行两轮对话时，第二轮请求携带第一轮用户消息和 AI 回复，模型能参考前文回答。
- AC13：Provider 层产生 `start`、`text_delta`、`done`、`error` 统一事件，TUI 基于这些事件更新界面。
- AC14：配置中 `thinking: true` 或 `thinking: false` 都能被正常解析，但第一版不会向 Claude 请求真实 extended thinking。
- AC15：API、网络或流式中断错误会以 TUI 错误面板展示，用户确认后程序不崩溃。
- AC16：输入 `/exit` 或 `/quit` 后，程序正常退出并返回终端。
- AC17：通过常见终端快捷键退出时，程序能正常结束或优雅中断。
- AC18：自动测试可以使用假的流式 Provider 验证流式追加、多轮历史和错误面板行为。
- AC19：本阶段交付内容不包含 tool use、文件操作、代码编辑或 Shell 执行能力。
