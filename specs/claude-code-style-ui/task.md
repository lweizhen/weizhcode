# weizhCode Claude Code 风格轻量 TUI Tasks

## 文件清单

| 操作 | 文件 | 职责 |
|---|---|---|
| 修改 | `src/weizhcode/cli.py` | 向 TUI 传入当前模型、配置名、项目路径和版本号 |
| 修改 | `src/weizhcode/tui.py` | 改造 Claude Code 风格轻量布局、消息流、输入框、底栏和错误弹窗样式 |
| 修改 | `tests/test_tui.py` | 更新并补充新布局、消息样式、输入行为和错误弹窗测试 |
| 新建 | `checklist.md` | 后续生成的验收清单 |
| 后续移动 | `spec.md`、`plan.md`、`task.md`、`checklist.md` | 完成后归档到 `specs/claude-code-style-ui/` |

## T1: 向 TUI 传入界面上下文

**文件：** `src/weizhcode/cli.py`、`src/weizhcode/tui.py`、`tests/test_tui.py`

**依赖：** 已批准 `plan.md`

**步骤：**

1. 在 `WeizhCodeApp` 初始化参数中加入 `model`、`project_path`、`version`。
2. 保留现有 `provider_name` 参数，用作底栏左侧显示。
3. 在 `cli.main()` 中从默认 Provider 配置读取模型名。
4. 在 `cli.main()` 中读取当前工作目录路径。
5. 在 `cli.main()` 中读取包版本号。
6. 更新测试中的 `WeizhCodeApp` 构造参数。

**验证：** 运行 `uv run python -m pytest tests/test_tui.py`，期望现有 TUI 测试仍能启动应用。

## T2: 实现顶部启动信息区和状态行

**文件：** `src/weizhcode/tui.py`、`tests/test_tui.py`

**依赖：** T1

**步骤：**

1. 在主布局顶部新增轻量 header 区域。
2. 左侧显示 3 行左右的小型 ASCII Logo。
3. 右侧显示 `weizhCode v版本号`。
4. 右侧显示当前模型名。
5. 右侧显示当前项目路径。
6. 在 header 下方新增固定状态行。
7. 状态行显示 `Connected to 0 MCP server(s), 0 tools registered`。
8. 为顶部区域和状态行增加暗色、灰白、紫/青点缀样式。
9. 补充测试断言 header、版本、模型、路径、状态行存在。

**验证：** 运行 `uv run python -m pytest tests/test_tui.py`，期望新布局元素断言通过。

## T3: 改造消息流为轻量纯文本风格

**文件：** `src/weizhcode/tui.py`、`tests/test_tui.py`

**依赖：** T2

**步骤：**

1. 移除 `MessageView` 的大卡片边框和明显 padding。
2. 将用户消息格式改为 `> 用户内容`。
3. 将 AI 消息格式改为缩进或淡色纯文本。
4. 保留 `MessageView.append_text()` 的流式追加行为。
5. 保留消息流的可滚动能力。
6. 更新流式回复测试，断言消息内容仍按顺序追加到同一条 AI 消息。
7. 增加测试，确认用户消息文本包含 `>` 风格提示符。

**验证：** 运行 `uv run python -m pytest tests/test_tui.py`，期望消息展示和流式追加测试通过。

## T4: 改造轻量输入框和底栏

**文件：** `src/weizhcode/tui.py`、`tests/test_tui.py`

**依赖：** T3

**步骤：**

1. 将 `ChatInput` 视觉高度压缩为简洁输入框。
2. 使用轻量边框或左侧提示符点缀输入区域。
3. 保留 `Enter` 提交行为。
4. 保留 `Shift+Enter` 换行行为。
5. 新增底栏布局。
6. 底栏左侧显示当前配置名。
7. 底栏右侧显示当前模型名。
8. 补充测试断言底栏左右内容存在。
9. 保留空输入忽略、退出命令测试。

**验证：** 运行 `uv run python -m pytest tests/test_tui.py`，期望输入、退出和底栏测试通过。

## T5: 调整错误弹窗与整体配色

**文件：** `src/weizhcode/tui.py`、`tests/test_tui.py`

**依赖：** T4

**步骤：**

1. 调整全局背景为暗色。
2. 调整正文为灰白文字。
3. 将紫色或青色作为小面积点缀。
4. 确保错误弹窗在新背景下仍能显示标题、内容和按钮。
5. 避免大面积高对比边框。
6. 保留错误事件和异常路径测试。

**验证：** 运行 `uv run python -m pytest tests/test_tui.py`，期望错误弹窗和交互测试全部通过。

## T6: 全量验证和流程文档归档

**文件：** `spec.md`、`plan.md`、`task.md`、`checklist.md`、`specs/claude-code-style-ui/*`

**依赖：** T5、已批准的 `checklist.md`

**步骤：**

1. 运行全量自动测试。
2. 手动启动 `uv run weizhcode` 观察新界面。
3. 对照 `checklist.md` 记录验收结果。
4. 创建 `specs/claude-code-style-ui/`。
5. 将根目录四份流程文档移动到归档目录。
6. 确认根目录不再保留本阶段四份流程文档。
7. 创建本阶段提交。

**验证：** 运行 `uv run python -m pytest`，期望全部测试通过；检查 `specs/claude-code-style-ui/` 中包含四份文档。

## 执行顺序

```text
T1 -> T2 -> T3 -> T4 -> T5 -> T6
```

## 阶段性验证命令

```text
uv run python -m pytest tests/test_tui.py
uv run python -m pytest
uv run weizhcode
```
