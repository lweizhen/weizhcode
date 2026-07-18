# weizhCode Claude Code 风格轻量 TUI Plan

## 架构概览

本阶段只改造 TUI 展示层，不改配置、Provider、HTTP/SSE、会话历史或 CLI 启动流程。现有 `WeizhCodeApp` 继续作为主应用入口，但内部布局从“顶部状态条 + 满屏消息区 + 大输入框”调整为“启动信息区 + 状态行 + 简洁消息流 + 轻量输入框 + 底栏”。

布局使用 Textual 的 `Vertical` 和 `Horizontal` 容器组合：顶部信息区固定高度，消息流占据中间可滚动区域，输入框保持较小高度，底栏固定在底部。消息组件从带边框卡片改为纯文本行块，用户消息使用 `>` 提示符，AI 回复使用低对比文本缩进。

为满足顶部和底栏展示需求，TUI 应用需要从 CLI 获得当前配置名、模型名和当前项目路径。Provider 行为不变，流式事件消费逻辑不变，只改变事件如何渲染到消息流。

## 核心数据结构

### `UiContext`

字段：

- `provider_name: str`：当前配置名，用于底栏左侧展示。
- `model: str`：当前模型名，用于顶部和底栏右侧展示。
- `project_path: str`：当前项目路径，用于顶部展示。
- `version: str`：当前 weizhCode 版本号，用于顶部展示。

用途：把界面展示所需的元信息集中传入 TUI，避免 TUI 从配置模块或文件系统中反向读取。

### `MessageView`

字段：

- `role: str`：消息角色，仍使用 `user` 或 `assistant`。
- `message_content: str`：消息文本内容。

接口：

```python
def append_text(self, text: str) -> None: ...
```

用途：承载消息流中的单条消息。格式从卡片式 `You:\n...` / `weizhCode:\n...` 改为轻量纯文本格式。

### `ChatInput`

职责保持不变：

- `Enter` 提交。
- `Shift+Enter` 换行。
- 提交后清空。

视觉变化：

- 固定为较小高度。
- 使用细线或轻量边框。
- 显示类似 `› Send a message...` 的轻量输入提示。

## 模块设计

### `tui.py`：主布局

**职责：**

- 构建 Claude Code 风格的轻量界面。
- 显示顶部 ASCII Logo、名称版本、模型和路径。
- 显示固定 MCP 状态行。
- 显示简洁可滚动消息流。
- 显示轻量输入框。
- 显示底栏配置名和模型名。

**对外接口：**

```python
class WeizhCodeApp(App[None]):
    def __init__(
        self,
        provider: Provider,
        conversation: Conversation,
        *,
        provider_name: str,
        model: str,
        project_path: str,
        version: str,
    ) -> None: ...
```

**依赖：** Textual、Conversation、Provider、当前包版本。

### `tui.py`：顶部启动信息区

**职责：**

- 左侧显示 3 行左右的小型 ASCII Logo。
- 右侧显示三行信息：`weizhCode vX.Y.Z`、当前模型、当前项目路径。
- 使用暗色背景、灰白文字和紫色点缀。

**对外接口：** 作为 `WeizhCodeApp.compose()` 内部布局组件，不单独暴露公共 API。

**依赖：** Textual `Horizontal`、`Vertical`、`Static`。

### `tui.py`：状态行

**职责：**

- 固定显示 `Connected to 0 MCP server(s), 0 tools registered`。
- 位于顶部信息区下方，输入框上方。
- 使用低对比灰色文本。

**对外接口：** 作为布局内 `Static`。

**依赖：** Textual `Static`。

### `tui.py`：消息流

**职责：**

- 保留当前进程内多轮消息显示。
- 去掉单条消息的大边框、padding 和卡片感。
- 用户消息显示为 `> 用户内容`。
- AI 消息显示为缩进或淡色文本。
- 流式 `text_delta` 继续追加到同一条 AI 消息。

**对外接口：** `MessageView.append_text()`。

**依赖：** Textual `Static`、`VerticalScroll`。

### `tui.py`：输入区

**职责：**

- 保留 `TextArea` 多行能力和现有按键行为。
- 视觉上压缩为一条简洁输入框。
- 使用紫色或青色的小提示符点缀。

**对外接口：** `ChatInput.Submitted` 消息保持不变。

**依赖：** Textual `TextArea` 和键盘事件。

### `tui.py`：底栏

**职责：**

- 左侧显示当前配置名。
- 右侧显示当前模型名。
- 固定在界面底部或主布局末尾。
- 颜色低调，不抢消息流注意力。

**对外接口：** 作为布局内 `Horizontal`。

**依赖：** Textual `Horizontal`、`Static`。

### `cli.py`

**职责：**

- 继续加载配置、解析默认 Provider、创建 Provider 和 Conversation。
- 将当前配置名、模型名、项目路径和版本传给 `WeizhCodeApp`。

**对外接口：** `main() -> None` 保持不变。

**依赖：** `Path.cwd()`、`weizhcode.__version__`。

### `tests/test_tui.py`

**职责：**

- 更新原有 TUI 测试对 UI 文本和组件结构的断言。
- 增加顶部 Logo、版本、模型、路径、状态行、底栏的覆盖。
- 保留提交、流式追加、错误弹窗和退出测试。

**依赖：** Textual `run_test()`。

## 模块交互

```text
cli.main()
  -> load_config()
  -> resolve_default_provider()
  -> create_provider()
  -> WeizhCodeApp(
       provider,
       conversation,
       provider_name=provider_config.name,
       model=provider_config.model,
       project_path=Path.cwd(),
       version=__version__,
     )
  -> Textual compose()
  -> header/status/messages/input/footer
  -> 用户提交消息
  -> Provider.stream_chat()
  -> MessageView 以轻量纯文本样式实时追加
```

错误弹窗仍沿用当前 `ErrorDialog` 机制，只调整必要样式，保证新暗色风格下可读。

## 文件组织

```text
weizhcode-python/
├── spec.md                         — 本阶段已批准需求
├── plan.md                         — 本阶段技术设计
├── task.md                         — 后续生成的任务拆解
├── checklist.md                    — 后续生成的验收清单
├── src/
│   └── weizhcode/
│       ├── __init__.py             — 提供版本号
│       ├── cli.py                  — 传入模型、配置名、路径和版本
│       └── tui.py                  — Claude Code 风格轻量 TUI 改造
└── tests/
    └── test_tui.py                 — 新布局和原有交互测试
```

本阶段完成并验收后，将根目录四份流程文档移动到：

```text
specs/claude-code-style-ui/
├── spec.md
├── plan.md
├── task.md
└── checklist.md
```

## 技术决策

| 决策点 | 选择 | 理由 |
|---|---|---|
| 改造范围 | 只改 `tui.py`、`cli.py` 和 TUI 测试 | 与 spec 一致，不碰 Provider/API/配置行为 |
| 布局方式 | Textual `Vertical` + `Horizontal` | 官方文档支持，适合顶部信息、主体和底栏组合 |
| 顶部高度 | 固定小高度 | 保持类似 Claude Code 的轻量启动区 |
| 消息样式 | `Static` 纯文本块 | 保留流式追加能力，同时去掉卡片感 |
| 输入组件 | 继续使用 `TextArea` | 保留现有多行输入和按键行为，降低回归风险 |
| 底栏 | `Horizontal` 左右分布 | 满足左配置名、右模型名的视觉要求 |
| 状态行 | 固定文案 | 本阶段不实现 MCP/tool 统计，避免引入假能力 |
| 颜色 | 暗色 + 灰白 + 紫/青点缀 | 贴近参考图，同时保证终端可读性 |
| 测试方式 | Textual `run_test()` | 沿用现有 headless 测试，覆盖布局和行为 |

## Spec 覆盖关系

| Spec 需求 | 设计归属 |
|---|---|
| F1-F5 | 顶部启动信息区、状态行 |
| F6-F10 | 消息流、MessageView、Provider 事件消费 |
| F11-F13 | ChatInput 样式和按键行为 |
| F14-F15 | 底栏 |
| F16 | Textual CSS |
| F17 | ErrorDialog 样式保留与测试 |
| F18 | 现有退出逻辑与测试 |
| N1 | 文件范围和技术决策约束 |
| N2-N5 | 布局和 CSS 设计 |
| N6 | TUI 自动测试 |
| N7 | 后续任务归档步骤 |
