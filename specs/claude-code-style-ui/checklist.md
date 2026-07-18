# weizhCode Claude Code 风格轻量 TUI Checklist

> 每一项通过自动测试、运行命令或观察 TUI 行为来验证，聚焦界面行为和本阶段范围边界。

## 实现完整性

- [ ] 顶部显示小型 ASCII Logo（验证：运行 `uv run weizhcode`，观察顶部左侧）
- [ ] 顶部显示 `weizhCode v版本号`（验证：运行 TUI 或 headless 测试，检查 header 文本）
- [ ] 顶部显示当前模型名（验证：使用测试 Provider 配置或真实配置启动，检查 header 文本）
- [ ] 顶部显示当前项目路径（验证：运行 TUI 或 headless 测试，检查 header 文本包含当前工作目录）
- [ ] 状态行显示 `Connected to 0 MCP server(s), 0 tools registered`（验证：运行 TUI 或 headless 测试）
- [ ] 底栏左侧显示当前配置名（验证：运行 TUI 或 headless 测试，检查 footer 左侧文本）
- [ ] 底栏右侧显示当前模型名（验证：运行 TUI 或 headless 测试，检查 footer 右侧文本）
- [ ] 输入区域视觉上是轻量输入框，不再是大型编辑器区域（验证：运行 TUI，观察输入区高度和边框）
- [ ] 消息流位于输入框上方，并能展示多轮历史（验证：发送两轮消息，观察消息按时间保留）

## 消息与输入行为

- [ ] 用户提交消息后，消息以 `>` 风格出现在消息流中（验证：输入一条消息并观察显示）
- [ ] AI 回复以简洁纯文本风格显示，不使用大卡片边框（验证：使用假 Provider 或真实 Provider 观察回复区域）
- [ ] AI 回复仍按流式增量追加到同一条回复中（验证：使用假 Provider 输出多个文本片段，观察同一条消息增长）
- [ ] `Enter` 仍能发送当前输入（验证：输入单行消息并按 `Enter`）
- [ ] `Shift+Enter` 仍能插入换行（验证：输入多行消息并提交，检查提交内容保留换行）
- [ ] 空白输入仍会被忽略（验证：提交空白输入，观察消息流不新增消息）
- [ ] `/exit` 和 `/quit` 仍能退出程序（验证：分别输入退出命令）
- [ ] 常见终端快捷键仍能退出或优雅中断（验证：手动触发快捷键）

## 视觉风格

- [ ] 整体背景为暗色，正文为灰白文字（验证：运行 TUI 观察）
- [ ] 紫色或青色只作为少量点缀出现（验证：运行 TUI 观察 header、输入提示或边界）
- [ ] 单条消息不再有大面积高对比边框（验证：发送消息后观察消息流）
- [ ] 顶部、消息流、输入框和底栏不会互相遮挡（验证：在常见 PowerShell 窗口大小中运行并观察）
- [ ] 错误弹窗在新样式下能显示标题、内容和确认按钮（验证：触发配置错误或使用测试覆盖）

## 范围边界

- [ ] 本阶段不修改 YAML 配置格式（验证：现有配置测试继续通过）
- [ ] 本阶段不修改 Provider 请求映射（验证：Provider 事件测试继续通过）
- [ ] 本阶段不修改会话历史行为（验证：会话测试和 TUI 多轮测试继续通过）
- [ ] 本阶段不新增 tool use、MCP、文件操作、代码编辑或 Shell 执行能力（验证：检查界面和测试不暴露相关入口）
- [ ] MCP/tools 状态行固定显示 0，不实现真实统计（验证：运行 TUI 观察固定状态文案）

## 编译与测试

- [ ] TUI 测试通过（验证：运行 `uv run python -m pytest tests/test_tui.py`）
- [ ] 配置测试通过（验证：运行 `uv run python -m pytest tests/test_config.py`）
- [ ] Provider 测试通过（验证：运行 `uv run python -m pytest tests/test_provider_events.py`）
- [ ] 会话历史测试通过（验证：运行 `uv run python -m pytest tests/test_conversation.py`）
- [ ] 全量自动测试通过（验证：运行 `uv run python -m pytest`）
- [ ] Python 文件语法检查通过（验证：运行 `python -m compileall src tests`）

## 端到端场景

- [ ] 场景 1：启动应用后不发送消息，能看到 Logo、版本、模型、路径、MCP 状态行、输入框和底栏（验证：运行 `uv run weizhcode` 手动观察）
- [ ] 场景 2：输入“你好”并发送，用户消息以 `>` 风格显示，AI 回复以轻量纯文本流式显示（验证：使用真实 Provider 或假 Provider 观察）
- [ ] 场景 3：连续发送两轮消息，消息流保留两轮历史且布局不乱（验证：手动运行或 headless 测试）
- [ ] 场景 4：触发错误弹窗，错误标题、内容和确认按钮可读，确认后能返回主界面或退出（验证：缺失配置或测试错误 Provider）
- [ ] 场景 5：本阶段完成后，四份流程文档被移动到 `specs/claude-code-style-ui/`，根目录不再保留本阶段流程文档（验证：检查文件树）
