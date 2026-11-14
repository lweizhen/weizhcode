# 计划模式需求澄清 Plan

> 状态：四份文档已统一批准；已按此设计实现。实际证据见 Task 与 Checklist，不以设计描述冒充测试结果。

## 设计

沿用现有 Registry → Scheduler → Executor → 统一事件 → TUI，不让同步工作进程等待终端输入。不引入另一套 Agent 引擎。

- models：ToolDefinition 增加 execution_kind（worker / interactive，缺省 worker）；新增不可变 QuestionRequest（question_id、问题、选项）和 TurnEvent.question。AskUserQuestion 标为 read_only=True、interactive：不修改文件，但绝不能并发。
- tools/ask_user_question.py：声明工具名称 AskUserQuestion、描述和自包含 Schema（question 必填；options 可选字符串数组）。注册为第七个工具；已有工作进程仅负责原六工具，不能执行交互工具。
- Registry：保留 definitions() 返回全部定义用于安装数量；增加 definitions_for_mode(mode)，normal 仅六工具，plan 为三读类加交互工具。保持顺序与防御性副本。当前阶段仅此一个 interactive 工具且只在 plan 允许。
- Executor：Schema 校验后、创建 worker 前，对 interactive 执行 plan 门禁并分流到 QuestionBroker。普通工具仍走原准备/执行共享预算；人类等待不进入 30 秒 timeout。没有可用消费者时返回 INTERACTION_UNAVAILABLE。
- Scheduler：只有 worker 且 read_only is True 的连续调用并发；interactive、预检失败及副作用调用都是串行屏障。等待答案期间不启动后续批。
- user_questions.py（新增）：QuestionBroker 管理单一当前请求和 Future，发布 question_request 事件，竞争答案与 cancel，确定性回收等待任务。确认答案先保存再异步收尾；取消只结束本次，不永久关闭会话交互能力。
- Runner：沿用 Executor 已注入 broker；否则创建共享 broker 接到 Executor。双重注入不一致时明确拒绝。持有交互消费者连接标记；TUI 消费开始/结束绑定和解绑，无头客户端未绑定则快速失败。工具结果仍由现有完整交换路径提交。
- TUI：使用原输入框，新增内联问题视图与“等待回答”状态，不弹权限确认框。处理选项序号/自由回答，答案成功接收后才清空输入；显示回答但不另写 Conversation 用户回合。输入和取消通过 Runner 传递，界面不直接完成 Future。

## 内部契约

- QuestionBroker.ask(slot, *, cancel, emit) → ToolResult；question_id 全局唯一，绑定当前 call.local_id；同一时刻只有一个未回答问题。
- QuestionBroker.submit(question_id, answer) → 接受/拒绝结果；answer 为 option_index（0 起）或 text 二选一。服务端校验索引和长度，不能信任 UI。
- Runner.submit_answer(run_id, question_id, answer) → 接受/拒绝结果：先验证当前任务归属，再交 broker。重复、过期、取消或异任务答案拒绝，不改新任务。
- 消费绑定采用可释放连接句柄/计数，避免旧消费者离开误解绑新消费者；没有消费者的调用不创建永久 Future。
- TurnEvent.question_request 带原有 run_id/local_id/iteration 和安全 QuestionRequest 副本。事件出口逐字段脱敏、移除控制字符，不能暴露 Future 或原始内部对象。
- 序号选择回传索引，由 broker 映射原始选项；不以 UI 脱敏后的标签作为原始答案。自由文本作为对应 ToolResult 内容回传并按现有结果出口脱敏。
- 正常回答结果包含问题、所选序号/文本与回答来源；非法模型参数沿用 INVALID_ARGUMENTS；取消沿用 TOOL_CANCELLED。问题请求只在完整成功流后产生。
- /plan 提示新增：先检查上下文，必要时询问关键需求/边界；形成计划时区分已确认条件与假设，等待 /do。回答不是执行授权。

## 生命周期与冲突规则

等待保持 busy。用户空白、越界序号、超长回答不消费问题；1～4 范围整数在有选项时视作序号，其他非命令文本视作自由回答；纯整数越界提示重试。/plan、/do 保留草稿并提示；/exit、/quit 优先退出。问题到达不清空已有草稿。

已取消/消费连接关闭/应用退出后先移除待答引用并清理 Future，再结束原任务；旧按钮或迟到输入不得唤醒新任务。答案和取消同拍：已保存的答案事实保留，但取消优先阻止后续模型或工具执行。工具交换按原槽位补齐，不造协议 ID。

## 文件范围

| 操作 | 文件（项目根 D:/STUDY/weizhcode-python） |
|---|---|
| 新增 | src/weizhcode/user_questions.py、src/weizhcode/tools/ask_user_question.py、tests/test_user_questions.py |
| 修改 | src/weizhcode/models.py、tools/__init__.py、tools/registry.py、tools/executor.py |
| 修改 | src/weizhcode/tool_scheduler.py、turn_runner.py、prompts.py、tui.py、tool_ui.py |
| 扩展测试 | tests/test_tool_registry.py、test_tool_executor.py、test_tool_scheduler.py、test_turn_runner.py、test_tool_tui.py、test_protocol_integration.py、test_redaction.py、test_cli.py |
| 回归保留 | 现有 Provider、文件/搜索/命令、配置与进程测试；只更新与七个安装工具/模式过滤有关的数量断言 |

路径均相对于上述明确项目根；旧阶段文档不修改。三协议无需新 API 格式，复用已有工具编码；技术实现若涉及新的库用法，再查对应当前文档。不新增 SDK、依赖或配置。

## 验证边界

模拟工具响应稳定覆盖所有 AC；原生进程测试和原六工具继续回归。Pilot 是无界面交互证据，不代替真实终端。真实 PowerShell 由用户观察。真实 API 仅使用已具备条件的默认服务，需能交互的测试消费者，以临时样本验证，不修改用户配置；缺条件保留待验。
