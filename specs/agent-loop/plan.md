# weizhCode Agent Loop Plan

> 状态：基于已批准的 Spec 编写，完整 Plan 已获用户明确批准，进入 Task 拆解。遵照用户要求，后续每阶段直接生成完整文件后统一审批，不逐节请求确认。
> 依据：[Agent Loop Spec](D:/STUDY/weizhcode-python/specs/agent-loop/spec.md)。
> 本文为设计文档，不代表已修改实现、运行测试或完成线上验证。Plan、Task、Checklist 全部获批前不进入实现。

## 1. 现状与技术约束

现有入口通过 cli 构造 Provider、Conversation、Registry、ToolExecutor 和 TurnRunner，再注入 Textual TUI。TurnRunner 当前执行固定两阶段单工具闭环；Executor 负责独立工作进程、准备与执行预算、逐次审批和结果归一化。工作进程通过 Windows Job / POSIX 进程组实现实际进程树收尾。

本章在这些组件上扩展，不引入新 Agent 框架、不迁移 SDK、不拆分整个 TUI 包、不新增依赖。继续兼容项目声明的 Python 3.11+，使用 HTTPX 与原始 SSE；三种协议分别保持 Anthropic Messages、OpenAI Responses、千问 Chat Completions 兼容格式。六字段 YAML 不变，默认后端选择、启动目录和环境变量解析规则不变。

用户手测产生的 .weizhcode-test 目录与用户配置不属于本章待改实现，不删除、不覆盖，也不纳入提交。旧章节文档不被覆盖。

### 1.1 相对参考材料的必要适配

- 扩展现有 TurnRunner，而非照搬 MewCode 的模块和 SDK 接口。
- 现有三个 Provider 全部适配；OpenAI 仍走 Responses，不替换成 Chat Completions。
- 不使用 SDK tool runner，不添加 server tools、子 Agent、权限组件或历史压缩。
- 移除逐次审批，但继续执行完整的 prepare / execute；准备阶段的唯一匹配、编码、目标快照与临时资源保护不能绕过。
- 不照搬“取消 asyncio 等待即可”“所有历史都必须同角色交替”“诊断交换都未执行”等不适合当前实现的假设。
- 三协议用量分别解析，尤其不将 Anthropic 的累计更新当作增量相加，也不把 Responses 套进 Chat Completions 的 usage 处理。
- 参考材料的 Ruff/mypy、额外测试插件和 Python 3.12+ 要求不加入本项目；测试继续使用现有依赖。

## 2. 架构概览

| 组件 | 职责 | 不负责 |
|------|------|--------|
| TurnRunner | 模式、运行占用、25 轮循环、停止条件、用量汇总、历史提交和任务生命周期 | 协议碎片解析、文件操作、界面组件 |
| StreamCollector（新模块） | 双路收集：即时正文事件 + 完整 RoundResponse；屏蔽内部思考，观察取消 | 执行工具、直接修改历史 |
| ToolScheduler（新模块） | 调用结构预检、保序分批、并发监督、结果排序和取消补齐 | 具体文件读写、协议序列化 |
| ToolExecutor + ManagedWorker | 模式执行门禁、参数校验、准备、执行、超时、真实进程清理、结果脱敏与预算 | 审批按钮、继续请求模型 |
| Provider | 原始 SSE、工具参数拼接、协议回放、用量快照、完整结束门槛 | 循环、模式策略、执行次数 |
| Conversation | 防御性副本、原子工具交换、准确的诊断交换与系统收尾消息 | 工具并发、界面状态 |
| TUI + ToolCallView | 用户输入/取消/模式请求、消费统一事件、草稿/滚动/工具行/进度/用量展示 | 判断下一轮、直接执行工具或补写成功历史 |

依赖方向：

- models 只提供公共数据与契约，不引用 Provider、TUI 或具体工具。
- providers → models、redaction、errors、SSE；不引用协调器或界面。
- tools → models、redaction 和工具内部组件；不引用 TUI。
- conversation → models；不反向依赖 Provider。
- stream_collector → Provider 统一接口、models、redaction。
- tool_scheduler → Registry / Executor 统一执行接口、models。
- turn_runner → collector、scheduler、conversation、prompts、models。
- tui → runner 的统一接口、公共事件、显示组件；cli 负责接线。

不让并发任务直接修改 Conversation。模式由 Runner 的会话状态持有；TUI 只能请求切换，并从事件读取当前模式。每个任务冻结 mode，运行中不切换工具能力。

## 3. 核心数据结构

以下均为拟议接口，尚未写入实现。共享消息继续使用现有 ChatMessage、ToolCall、ToolResult，并保留原始私有参数与协议回放载荷的防御性副本。

### 3.1 Mode、StopReason 与循环常量

- AgentMode = normal / plan。
- StopReason = completed / empty_response / max_iterations / unknown_tools / cancelled / provider_error / internal_error。
- MAX_ITERATIONS = 25；MAX_UNKNOWN_RUN = 3；均为内置常量，不进入 YAML。
- MAX_CONCURRENT_READ_TOOLS = 4；仅为内部工作进程资源上限，不新增用户配置。同一只读批内允许排队，但不能越过下一副作用调用。
- 每个任务的 iteration 从 1 计数；unknown_run 从 0 开始，不跨任务继承。
- 每次进入模型请求阶段占一个 iteration；普通文字结束也占一轮。取消信号已生效时不再创建下一次请求。

internal_error 仅用于未预期的执行基础设施/协调错误，不将普通工具失败归入其中。尤其清理失败不能伪装成取消成功或继续安全运行。

### 3.2 TokenUsage 与 UsageTotals

TokenUsage 为不可变快照：

| 字段 | 类型/含义 |
|------|-----------|
| input_tokens | int 或 None；已知请求输入总量，不包含凭空估算 |
| output_tokens | int 或 None；已知请求输出总量 |
| complete | bool；此请求的统计是否完整可信 |
| source | 协议来源标识，不含认证数据 |

None 与真实 0 不等价。缓存输入与推理输出的计数按协议归一化；保存必要原始计数用于测试，但不重复加入总数。

UsageTotals 保存已知输入/输出累计、已知字段覆盖情况、统计不完整的请求数。Runner 对每个本地 request_id 最多结算一次，不由 TUI 再累加。每次 usage 事件带本次请求统计与累计快照，TUI 只显示快照，防止重复消费导致重复计费量展示。

重复或累计 usage 报告在 Collector 内合并为同一次请求的最新有效快照，不逐条相加。递减、负数、布尔伪整数等异常计数不覆盖可信值，并标记不完整。取消/失败时保留已经收到的真实数值，但 complete=False。无数据时显示缺失，不用 0 冒充完整统计。

不计算价格、不实现 Token 预算停止，不把累计请求用量误称为当前上下文大小。

### 3.3 ProviderEvent 与 StreamState / RoundResponse

ProviderEvent 保留 start、text_delta、tool_call_start、tool_call、done、error，增加 usage 快照。done 中的 assistant_message 是本轮完整助手消息的权威来源，不能再与 tool_call 事件拼接一遍导致重复执行。

StreamState 是单次请求的私有收集状态，包含：

- request_id、iteration；
- 收集到的完整 assistant_message、completed 标记；
- 最新用量快照；
- 接收中的工具本地标识及顺序；
- 脱敏正文缓冲与流错误；
- 取消/关闭状态。

RoundResponse 是成功收集后的不可变结果：request_id、iteration、assistant_message、usage。只有 completed=True 且通过 Provider 完整结束检查才能产生。没有成功 done 的 EOF、截断、流错误均不能产生可执行 RoundResponse。

usage 是观察数据，不是执行授权：收到 usage 或工具块结束不放行工具。

### 3.4 ToolDefinition 与 ToolSlot

ToolDefinition 移除 requires_confirmation，新增 read_only: bool，默认 False；六个工具全部改为显式关键字赋值，不能机械把旧第四个位置参数改名：

| 工具 | read_only |
|------|-----------|
| read_file | True |
| find_files | True |
| search_content | True |
| write_file | False |
| edit_file | False |
| run_command | False |

ToolSlot 是单次调用私有执行槽，保存 index、完整 ToolCall、本地 local_id、phase、execution_started、result、cleanup_error。phase 为 pending / preparing / running / finished。每个执行任务只写自己的槽，不写其他槽、不改 Conversation。

ToolResult 增加 cancelled 状态与 TOOL_CANCELLED 错误；Plan 模式拒绝使用 error + TOOL_NOT_ALLOWED。保留既有结果字段和序列化预算；旧 denied 值可以继续解析，但不再存在用户审批执行分支。

execution_started=False 可以明确表述“未执行”；已经发送 execute 但无确认结果时只能表述“已停止/结果未确认，副作用可能保留”。成功结果一旦从工作进程被接收并归一化，立即写入自己的槽，再进行可等待的资源收尾，避免取消时覆盖已确认事实。

### 3.5 TurnEvent（Agent → UI）

扩展现有事件，去掉 approval 和 initial/final 两阶段假设，统一使用：

| 事件 | 必要信息 |
|------|----------|
| mode_changed | mode |
| iteration_started | run_id、iteration、mode、max_iterations |
| text_delta | run_id、request_id、iteration、text |
| tool_pending | 上述运行信息、local_id、接收态工具信息 |
| tool_start | local_id、调用序号、完整但仅供安全展示的 ToolCall |
| tool_preparing / tool_running | local_id、状态 |
| tool_result | local_id、调用序号、实际归一化 ToolResult |
| usage | request_id、本次 TokenUsage、累计 UsageTotals |
| notice | 结构化原因和脱敏提示 |
| error | 分类原因和脱敏消息，不传原始异常对象/堆栈 |
| turn_done | run_id、StopReason、最终模式和用量累计快照 |

每个已接受任务在资源/历史收尾后只有一个 turn_done；error/notice 不代替最终结束事件。工具结果在 UI 出口独立生成摘要，不能用摘要替代会话结果。内部模型思考、签名、密文不放进可见事件。

### 3.6 RunContext

每次接受任务新建 RunContext：run_id、冻结 mode、cancel_event、consumer_closed、iteration、unknown_run、当前 StreamState、当前轮 ToolSlots、exchange_committed，以及本任务拥有的子任务和收尾任务引用。

RunContext 不能被下一用户任务复用。所有晚到回调必须带 run_id，不能更新新任务的界面或状态。模式和 UsageTotals 属于 Runner 会话，任务槽与未知计数仅属于本次任务。

## 4. 对外接口与签名迁移

### 4.1 Runner 与流式收集器

~~~python
TurnRunner.run(user_text: str, *, mode: AgentMode | None = None) -> AsyncIterator[TurnEvent]
TurnRunner.set_mode(mode: AgentMode) -> TurnEvent
TurnRunner.cancel_current() -> bool
async TurnRunner.aclose() -> None

async StreamCollector.collect(
    messages: list[ChatMessage], *,
    tools: Sequence[ToolDefinition],
    system_prompt: str,
    context: RunContext,
    state: StreamState,
    emit: Callable[[TurnEvent], Awaitable[None]],
) -> RoundResponse | None
~~~

run 保留“普通方法立即占用 + 返回异步迭代器”的模式：在 TUI 挂载用户消息或启动后台消费前建立 busy，防止连续提交竞态。忙碌/已关闭时返回明确拒绝，不追加历史、不清空草稿、不创建第二任务。mode 参数仅在空闲接收任务时生效，任务内冻结。

set_mode 只允许空闲切换，返回统一 mode_changed 事件；忙碌时返回 notice(reason=busy)，模式不变，不抛未处理异常、不私自切换正在运行的模式。run 的忙碌/关闭拒绝也只提供未接受任务的通知，不发送会令当前任务误恢复空闲的 turn_done。

cancel_current 只设置当前任务的取消事件，幂等且立即返回；不直接取消 Textual 消费 worker，不永久关闭 Executor。aclose 是应用级关闭：先停止接收任务，取消并等待当前运行收尾，再永久关闭 Executor；重复关闭安全。

构造契约：StreamCollector(provider, redactor)、ToolScheduler(registry, executor)；TurnRunner 保留现有 provider / conversation / registry / executor / redactor 构造参数，增加可选关键字 collector、scheduler、max_iterations=25、max_unknown_run=3。缺省辅助组件统一在 Runner 内按相同依赖构造；cli 可以显式注入，测试可以注入受控替身和低上限。这些参数不是新的 CLI/YAML 设置。Executor 继续使用现有 registry、ToolContext、Redactor 与内部 timeout / worker_factory 构造契约。

### 4.2 调度器与执行器

~~~python
async ToolScheduler.execute(
    assistant: ChatMessage, *,
    context: RunContext,
    emit: Callable[[TurnEvent], Awaitable[None]],
) -> list[ToolResult]

async ToolExecutor.execute(
    slot: ToolSlot, *,
    mode: AgentMode,
    cancel: asyncio.Event,
    emit: Callable[[TurnEvent], Awaitable[None]],
) -> ToolResult

ToolRegistry.definitions(*, read_only: bool = False) -> list[ToolDefinition]
ToolRegistry.is_read_only(name: str) -> bool
async ToolExecutor.aclose() -> None
~~~

调度返回结果与 assistant.tool_calls 一一按下标对应，包括未知、非法、取消和模式拒绝项。Executor.execute 替代旧 run 异步生成器；所有生产与测试调用方同组迁移，删除 approve 回调，不通过“自动批准回调”保留旧审批链。

Registry 只将 read_only is True 的已注册工具视作只读，不能因真值字符串或未知工具被误放行。只读定义过滤返回副本，并保留注册顺序。

ManagedWorker 的 start / prepare / execute / aclose 协议继续使用；每次 execute 启动独立工作进程和进程管理对象。工作进程不变成长期共享的并发执行池。

### 4.3 Provider 与 Conversation

Provider.stream_chat 保留现有 messages、tools、system_prompt、allow_tools 关键字签名，扩展事件而非另建 SDK 类型。循环正常请求均 allow_tools=True，工具集合由 mode 决定；废除“第二次请求一定 allow_tools=False”的规则。参数保留用于统一接口和既有独立 Provider 测试，不用它代替模式执行门禁。

Conversation 保留 messages、add_user_message、add_assistant_turn、add_tool_exchange，增强交换校验与诊断文本的真实性；增加 add_stop_notice(text, reason) 用于带应用来源标记的助手收尾文本，不把停止提示伪装成模型声称已完成任务。

不使用“无条件补一个 assistant 就能修复任何历史”的做法。规范协议交换必须逐调用匹配；原始调用不合法时使用明确诊断降级，而不是造调用 ID。

## 5. 循环与流式双路流程

### 5.1 事件传输与所有权

run 的异步迭代器包装一个受监督的私有驱动任务。内部使用容量 128 的 asyncio.Queue 传输事件，以背压避免界面消费慢时无限累计正文片段。它不是公开配置项，不裁剪历史。

- 收集器和调度器通过 emit 发事件；TUI 不直接消费 Provider。
- emit 只接收/发送用于显示的防御性副本：工具名、参数摘要、错误和结果中的已知密钥及危险控制字符须先处理；原始 ToolCall、ToolSlot、协议私有载荷不能因发事件而被修改或整份暴露。任何会话外消费者也不能取得原始认证信息。
- Producer 的结束使用独立完成信号，不在 finally 中永久等待往满队列塞 sentinel。
- 消费者关闭时设置 consumer_closed，emit 中止 UI 排队但不阻止历史/工具清理；设置取消并等待私有驱动收尾。
- 每个 queue.put、queue.get 的辅助等待均有明确拥有者；关闭时取消并 await，不留下挂起任务。
- 使用 task done + 队列空来终结消费；正常情况下必须先收到一次 turn_done。
- 必须持有驱动任务的强引用并观察异常，不能靠异步生成器垃圾回收清理。

### 5.2 主循环

1. 接受任务、冻结模式、建立占用和 RunContext；添加用户消息。/do 采用内置执行指令作为用户消息，见第 10 节。
2. 按当前 mode 取得 6 个或 3 个工具定义，构造系统说明。
3. 对 iteration = 1…25：
   - 先检查取消，再发 iteration_started。
   - 创建本地 request_id 与 StreamState，调用 Collector。
   - 无论成功、失败或取消，对这次请求的已知 usage 结算一次；没有请求阶段的不造用量。
   - 若取消，进入统一取消收尾；若流错误，显示 error 并以 provider_error 收尾，不执行缓冲调用。
   - 成功且无调用：保存完整助手回合。可见正文为空时发“模型未返回正文”提示并记 empty_response；否则 completed。均不继续请求。
   - 成功且有调用：将完整助手回合暂存在本轮状态，先计算 all_unknown，交调度器处理；执行时暂不暴露缺结果的半个历史交换。
   - 调度器收尾后取得完整排序结果，原子提交 add_tool_exchange；不能在各并发任务里逐个改历史。
   - 优先检查取消，其次基础设施错误，再检查 unknown_run >= 3，最后判断是否已是第 25 轮。
   - 若未停止，进入下一轮；所有已注册工具即使校验/执行失败，也使 unknown_run 重置。
4. 上限与未知停止写明确应用通知；第 25 轮允许的工具处理和结果回传完成后停止，不请求第 26 轮。
5. 所有路径在完成资源与历史收尾后发一个 turn_done，清空本任务引用并恢复 busy=False；保留会话模式及累计用量。

all_unknown 只按注册表存在性判断，不用 read_only=False 代替“未知”，也不按一次回复中未知调用数量计轮。

### 5.3 单次收集与完整结束门槛

Collector 使用 anext(provider_stream) 的任务与 cancel_event.wait() 的任务进行 FIRST_COMPLETED 等待，因此没有新 SSE 数据时也能及时响应取消。不能只在每次收到 token 后才检查事件。

- text_delta 经 StreamingRedactor 和安全显示过滤后 emit；原始协议必要载荷留在完整消息，不进入 UI。
- tool_call_start 仅发接收态，保留稳定 local_id；完整调用仍以 done.assistant_message 为准。
- usage 只更新 StreamState 的同请求快照。
- error 记录安全错误，不产生可执行 RoundResponse。
- done 验证完整助手消息和后端成功终止条件；返回 RoundResponse。检测到实际正文仅在完整消息出现但未提供增量时，补发尚未展示的正文，不重复已展示内容；不一致的已展示正文不能静默改写为成功。
- EOF 没有 done 为请求失败，不能把已累计 calls 当作完成。

同一事件循环中取消与一个网络读取同时完成：先接收已经完成的 usage/完整结果供记账，但取消优先阻止新执行。对可见未完成正文加“本次回复未完成/已取消”状态；不能把部分文本保存成成功助手答复。

关闭时先 cancel 并 await 正在运行的 anext，再用 aclosing/aclose 关闭 Provider 和 HTTPX 流，避免对正在运行的异步生成器同时调用 aclose。没有显式后台取消等待的 asyncio.wait 不会替调用方取消 pending 任务，必须自行回收。[Python asyncio 文档](https://docs.python.org/3/library/asyncio-task.html)、[异步生成器确定性关闭](https://docs.python.org/3/library/contextlib.html#contextlib.aclosing)

## 6. 保序分批与执行门禁

### 6.1 结构预检

为全部调用先按原始序号建立 ToolSlot，并确认每个本地 local_id 唯一。协议 call_id 缺失、过长、重复、名称/JSON 结构非法均不能执行受影响调用：

- 重复 call_id 的所有冲突调用返回 DUPLICATE_CALL_ID，不执行其中任一个，避免重复副作用。
- 其他独立且可识别的调用仍按原顺序处理；不因一个坏调用丢失合法调用。
- 未知工具返回 UNKNOWN_TOOL；参数对象/Schema 错误沿用 INVALID_JSON / INVALID_ARGUMENTS。
- 原始 call_id 不能被修补或替换成假 API ID；UI 及私有槽用 local_id 区分。

### 6.2 调度规则与事件顺序

按照原调用列表逐段扫描。仅已知 read_only=True 的相邻调用组成最长只读批；副作用、未知和受影响非法调用均形成独立串行位置，不跨越它们合并前后只读批。

每批：

1. 按下标发 tool_start，确保对应工具行已按模型顺序建立。
2. 只读批为各槽创建执行任务，以容量 4 的 Semaphore 限制同批实际执行器/工作进程数量；获取许可后才进入 Executor、创建 worker。副作用批只创建一个任务。每个活动执行任务拥有自己的 ToolSlot 和 ManagedWorker；等待许可的槽显示待执行。
3. preparing/running 状态可按实际时刻更新各自 local_id，不新增错序记录行。
4. 执行结果写槽，但 tool_result 暂存；全批结束后按原序逐个 emit，再开始下一批。
5. 取消时阻止下一批/尚未启动项，停止运行任务并等待清理；已得到结果不覆盖，缺结果位置补 TOOL_CANCELLED，结果事件也按原序输出。

取消发生前只出现了 tool_pending、没有成功完整响应的接收行，显示“未执行：响应未完成/已取消”，不伪造实际工具结果回灌。

批内并发利用独立工作进程，不把同步文件工具直接放在事件循环中执行。并发任务只更新自己的槽和带 ID 的状态，历史由 Runner 汇合后提交；不新增跨批重排或并发写操作。

并发许可等待不属于工具准备/执行耗时，30 秒预算在获许可、进入 Executor 时开始。等待许可时取消必须返回未开始的取消结果，不能在取消后获许可再启动 worker；只有前一整个批处理完毕才进入下一批。

### 6.3 模式门禁与无审批执行

Executor 在任何 worker 创建前执行：

- 已关闭 / cancel 已设置 → 取消/应用关闭结果；
- 未知 / 非法调用 → 对应结构化错误；
- plan 且工具不是 read_only=True → TOOL_NOT_ALLOWED，execution_started=False，零 worker、零命令、零目录创建；
- 校验通过 → worker.start → prepare → 无条件检查 prepare.error → 剩余预算内 execute。

在发送 execute 指令前再次检查取消。模式已冻结，不从 UI 可变状态读取。普通模式不用 approve=None 的旧“默认拒绝”路径，也不注入自动批准回调。

prepare 的完整 PreparedOperation、真实目标、快照、唯一匹配和临时路径仍留在子进程；不使用 UI 脱敏文本执行，不因移除预览按钮而改成未经准备的直接覆盖。

### 6.4 工具结果与资源收尾

每个工具保留启动/准备/执行累计 30 秒预算，取消/模式校验不使预算重新开始。超时先停止实际工作进程/受管后代，再返回 TOOL_TIMEOUT；有限 stdout/stderr 沿用当前采集逻辑，不做流式工具结果。

收到成功/失败结果后先归一化、写 ToolSlot.result，再等待 worker.aclose。取消不能将槽内已确认结果改成取消。若未收到结果，TOOL_CANCELLED 文案按 execution_started 区分“未开始”与“副作用可能存在”。

调度器针对本轮任务发出的 Task.cancel 在 Executor 内专门捕获：执行实际收尾后，返回槽内已有结果或归一化的取消结果，不直接跳过排序/历史提交。未预期的外层应用取消仍按第 9 节在完成必要清理后传播，不能用捕获取消来让原操作继续执行。

沿用 Windows Job、POSIX 进程组、启动退出竞态防护和临时文件 inode/归属检查。关闭任务必须强引用、幂等，并等待完成；shield 不是免等待，也不意味着命令自动被终止。反复 Esc 只设置同一个事件，不反复打断收尾任务。[Python 取消与 shield](https://docs.python.org/3/library/asyncio-task.html#shielding-from-cancellation)

PROCESS_CONTROL_FAILED 或无法确认实际进程清理完成时，明确报基础设施错误、停止本任务，不发下一轮模型请求，不伪装成安全成功。实际已知结果保留，清理错误另行记录，用户不会看到虚假回滚声明。

## 7. 历史提交与提前终止

### 7.1 完整交换的提交

Runner 持有完整 assistant 和所有槽，正常批执行后或取消收尾后一次性提交 assistant + 全部对应结果。这样并发执行过程中不会出现其他请求读取半个交换。

add_tool_exchange 必须始终检查结果数量与调用数量相等；合法原生交换还须逐 ID 一一对应。不能因为进入 diagnostic 分支而放弃基本完整性检查。结果按调用序保存，保留防御性深复制。

### 7.2 混合成功与诊断交换

现有 diagnostic_text 会将异常交换笼统描述成“未执行”。本章允许同轮合法工具执行、未知工具失败，因此必须修改：

- 每个调用按序记录 local_id、原始可识别 call_id、名称、实际 ToolResult、是否已发送执行；必要状态放在有界、脱敏的诊断载荷中。
- 成功就是成功、超时就是超时；不能把一轮所有调用统一写成“未执行”。
- 对不能合法原生回放的交换使用明确应用诊断文本；不输出伪造 tool_result ID。
- 可合法原生回放的完整交换继续使用正确协议格式，不能为了省事一律退化为纯文字。
- 三 Provider 的诊断序列化测试检查同一混合交换中真实成功和失败都可见，且没有虚构的统一未执行声明。
- 诊断不截掉整项结果；调用参数仅取有限安全摘要，工具结果各自继续遵守 20,000 字符预算。不会以整批一个总截断掩盖调用与结果配对。

Runner 在 add_tool_exchange 前，将按原调用顺序的 local_id / execution_started / cleanup_error 等事实作为应用专用元信息写入助手消息的 provider_payload 副本；Conversation 校验后保存。Provider 仅在诊断降级时按需使用其安全副本，原生序列化不得把这些应用字段传成未知协议参数。这样无需更改 ToolResult 的调用相关性字段，也能描述缺失/重复 ID 情形中的实际执行状态。

### 7.3 取消与错误时的历史

| 停止位置 | 历史处理 |
|----------|----------|
| 初次网络等待/未完整响应 | 保留用户消息，不保存部分助手调用；补应用来源的取消/错误收尾 |
| 完整响应已收齐、工具未启动 | 保留完整调用，全部补取消结果，再原子提交 |
| 部分工具已完成 | 保留已确认结果，未完成/未开始补取消结果，再原子提交 |
| 工具交换已提交、下一次流失败 | 保留该交换；不重做副作用，只补本任务错误收尾 |
| 25 轮/未知工具阈值 | 保留最后一轮所有结果，加应用停止通知，不额外生成总结 |
| 应用退出 | 同样清理资源；只处理进程内状态，不请求模型或落盘历史 |

add_stop_notice 写入 provider_payload 的应用来源标记与原因，文案如“已取消，已有修改可能保留”“已达到 25 轮上限，任务可能未完成”。若自然回复为空，保存明确空回复占位及原因，不添加虚构模型结论。

若最后已有一个足够明确的本任务应用收尾消息，不重复追加；不能凭 last_role == assistant 就认为取消信息已经写过，也不以相邻同角色作为统一错误标准。各 Provider 继续按各自格式合并/编码。

## 8. 三协议适配与用量归一化

所有 Provider 仍使用原始 HTTPX/SSE。不启用网络自动重试；流错误停止本任务。HTTPX 上下文及 anext 的取消与关闭须可打断等待，即使没有新 token。保持现有输出 Token 参数，不在本章新增模型参数或强行关闭服务端思考。

### 8.1 Anthropic Messages

- 保持 /messages、现有认证头、正文/工具/思考块拼接和 message_stop 成功门槛。
- 循环请求 tool_choice 使用 auto，移除 disable_parallel_tool_use=True，让模型能返回多个调用；本地 Scheduler 决定安全执行顺序。
- 从 message_start.message.usage 建立输入/输出计数；message_delta.usage 为累计快照，更新字段而不是相加；最后 message_stop 才能标记该次流完整。[官方流式事件](https://platform.claude.com/docs/en/build-with-claude/streaming)
- 规范输入总量为 input_tokens + cache_creation_input_tokens + cache_read_input_tokens；缓存可选字段按协议缺省处理，显式 null/语义不确定的缺失不冒充完整统计。缓存分项只加一次，不再叠加嵌套 TTL 分项。[官方 usage 定义](https://platform.claude.com/docs/en/api/http/beta/messages/create)
- 思考/签名及协议必要块继续无损回放但不显示。工具结果必须紧随对应助手调用并逐 ID 匹配；保留现有严格完成验证。
- DeepSeek 等 Anthropic 兼容端点以实际 SSE/usage 行为验证，不假设其缓存字段与 Claude 完全相同，不修改用户模型/地址。

### 8.2 OpenAI Responses

- 保持 /responses、store=False、stateless 输出项回放及 function_call_output；不引入 previous_response_id、服务器会话或 Chat Completions。
- 使用 auto 和 parallel_tool_calls=True，支持一次多个函数调用。只提供本地已有 function tools，不添加 programmatic/server tools。
- 从 response.completed.response.usage 读取 input_tokens / output_tokens；cached_tokens 与 reasoning_tokens 是各总量的明细，不能再加一次。failed/incomplete 若提供真实统计，可保留但标不完整；缺失即未知。[Responses API 参考](https://developers.openai.com/api/reference/resources/responses/methods/create)
- 不给 Responses 请求添加 stream_options.include_usage；该参数方案属于 Chat Completions。
- 继续保存完整可回放输出项与必要 reasoning/encrypted 项，避免反复回放时重复助手正文。只有 response.completed 且状态 completed 才放行工具，item.done / arguments.done 不替代成功终止。[OpenAI 官方工具调用文档](https://developers.openai.com/api/docs/guides/function-calling)

### 8.3 千问兼容 Chat Completions

- 保持 /chat/completions、嵌套 function 定义、assistant.tool_calls 与 role=tool 的回传格式。
- 使用 auto，不依赖兼容端点是否接受额外并行控制字段；本地调度检查实际调用。
- 请求增加 stream_options: {include_usage: true}；先解析 usage，再处理 choices，允许 choices=[] 的末尾统计包；不能把它当成无效正文提前丢弃。[千问官方流式说明](https://help.aliyun.com/zh/model-studio/stream)
- prompt_tokens → input_tokens，completion_tokens → output_tokens；不再叠加 total_tokens。重复末包只更新同请求快照，最终只结算一次。
- finish_reason + [DONE] 的完成门槛保持；usage 包或单独 finish_reason 不自动放行工具。
- 不新增思考开关映射，不把丢弃思考文本的当前千问适配器宣传成任意思考型第三方模型通用适配器。已支持协议回放能力不退化；若新增端点需要新字段/协议，按范围边界另行确认。

### 8.4 用量缺失和冲突

每次请求无论正常、错误或取消，Collector 都将“已知数据 + 是否完整”交给 Runner 一次。Runner 用本地 request_id 去重，不能只依赖服务端 response.id（兼容端点可能缺失/重复）。

事件带当前累计快照；尚无统计显示“↑— ↓—”，有部分数据则显示已知累计并附“统计不完整（N 次请求）”。取消时未收到完整统计不能因此宣称实际费用为零。不同请求重复传入历史产生的输入量正常逐请求累计。

## 9. 取消、生命周期与竞态

- 普通取消仅设置 RunContext.cancel_event；私有驱动负责停止网络读取/执行任务并收尾，不取消事件消费者来跳过 finally。
- Scheduler 显式等待“当前批任务组完成”与取消信号；取消发生时 cancel 仍在运行的本批任务，再 gather(return_exceptions=True) 等待全部实际收尾，未开始批不启动。
- 收集与执行的取消辅助 task、queue 等待都在各自 finally 中取消并 await。asyncio.wait 使用 Task 对象，不传裸协程。
- cleanup 不依赖新事件成功入队。消费者已退出、队列满或 TUI 正在卸载时，照样清理与提交有限进程内事实。
- run_id 隔离、同步占用建立、幂等取消、进程启动中关闭防护沿用并加强测试；第二个任务只能在前一任务完成收尾后被接受。
- 执行器 execute 在实际结果收到后先写槽，取消收尾之后优先取槽中事实。取消与结果同时发生不得把成功事实覆盖为“未执行”。
- 最外层外部 CancelledError（例如应用框架强制结束 worker）也转入同一私有驱动的取消/清理路径；完成必要清理后再传播外部取消。不能吞掉系统退出、留下后台任务。
- Runner.aclose 停止新任务、取消当前、await 私有驱动、最后 Executor.aclose。不要在单轮取消时设置全局 Executor._closed=True。
- 命令不回滚，不试图杀死用户已有进程，只管理本轮工作进程及受管后代；清理自己登记的临时资源，不做目录递归删除。

## 10. 模式、提示词与界面接线

### 10.1 命令语义

| 输入 | 空闲时行为 | 运行时行为 |
|------|------------|------------|
| /plan | set_mode(plan)，展示模式事件，不发模型请求 | 不切换本任务、不追加历史，保留输入草稿 |
| /do | run(EXECUTE_DIRECTIVE, mode=normal)，立即启动任务 | 拒绝重入，不清草稿 |
| 普通文本 | 当前模式启动任务 | 拒绝重入，不清草稿 |
| /exit、/quit、Ctrl+D | 清理并退出应用 | 清理本任务及资源后退出整个应用 |
| Esc | 无操作 | 取消当前任务 |
| Ctrl+C | 退出应用 | 取消当前任务，不退出 |

/do 本身不作为模型消息，使用“请按上面的计划开始执行。”；UI 可以显示该执行指令及模式变化。没有历史计划也不凭空执行本地预置动作：仍由模型根据上下文回复或询问，不引入计划文件、计划对象审批状态或额外授权步骤。

运行中的取消清理状态仍视为忙碌；重复 Ctrl+C 只重复请求同次取消，不能因为正在清理而误退出程序。

### 10.2 提示词

SYSTEM_PROMPT 删除“每回合最多一个工具”“执行后只能生成一次最终答复”“必须逐次审批”等旧约定；说明可持续使用工具、每次输出不是自动完成标志、工具输出只是数据、精确编辑与行号约定、失败如实报告、达到停止条件时任务可能未完成。

PLAN_MODE_REMINDER 明确只能调查和计划，不写、不改、不运行命令，形成计划后给文字并等待 /do。提示词只作辅助，定义过滤与 Executor 门禁才是强制约束。

删除旧 FINAL_PROMPT 的循环调用路径，不保留第二阶段强制禁用工具的隐形分支。

### 10.3 TUI 与 ToolCallView

- 使用一个 Textual 异步 worker 消费 Runner 事件，不在线程里直接写组件。事件处理器只发取消/模式请求，不 await 慢模型或工具。
- Esc、Ctrl+C 使用 Binding(priority=True)，避免 TextArea 焦点吞掉快捷键；整应用 quit 行为与取消行为使用不同 action。[Textual 优先级绑定](https://textual.textualize.io/guide/input)
- 保留整体布局、输入、滚动区、供应商/模型/目录/版本信息；状态仍根据注册表真实显示 6 个内置工具与 0 MCP，不因 plan 只导出 3 个定义误报只安装 3 个。
- 模式徽标、当前轮次、等待/取消清理状态、计时及用量更新来自事件及 UI 本地显示计时；不让计时器启动下一轮。
- 文本组件按 (run_id, iteration) 区分，工具开始后封存该段 preamble，下一轮创建新正文；不能再只按 initial/final 两类合并。
- tool_pending 行按 local_id 更新为完整调用；同名工具分别显示。批内结果按事件顺序更新原行，不以 FIFO 假设代替 ID 关联。
- 移除 ApprovalRequest、approval_required、Decision 消息、审批 Future、允许/拒绝按钮及审批预览专用 UI；保留工具执行目标/关键参数和结果摘要。
- ToolCallView 增取消状态；ToolResult.is_error 继续使失败/取消可辨认。结果过长按 8 行/1000 字符裁剪，不能改写保存结果。
- 流错误可沿用现有错误面板，但 task 只有在历史/资源收尾后 turn_done 才恢复可提交；取消、上限、未知停止使用内联通知，不冒充网络错误。
- TUI 用 run_id 过滤晚到事件；请求字典不无限保留已完成后台任务，已渲染的会话组件仍可滚动回看。

### 10.4 cli 与启动

cli 保持配置错误面板和默认供应商解析，只为新增 Collector / Scheduler 与 Runner 完成构造接线。Redactor 只使用已解析密钥，不强行解析未选择后端的环境变量。TUI 的测试兼容构造也使用同一接线逻辑，不能保留一个无门禁的替代执行路径。

不改用户配置、模型或密钥，不在 Plan 阶段启动程序或发付费测试请求。

## 11. 安全、体量与错误分类

### 11.1 分层保护

- 注册/Schema 校验、执行端 plan 门禁、完整流门槛与结果序列化预算是不同层，互相不能替代。
- 原始 ToolCall / PreparedOperation / shell 参数不脱敏后执行；仅 UI、模型可读结果和诊断副本脱敏。
- 已知密钥先递归脱敏再做最终长度校验；同样保护跨正文分片、取消/错误提示和新的模式/进度消息。
- 不透明签名/加密数据按协议保留、不显示，不尝试修改它们；可见文本独立脱敏。
- 不放宽 .gitignore、隐藏项、直接路径、严格 UTF-8、BOM、换行、唯一匹配、目标验证和临时文件归属。
- 不新增沙箱/路径白名单；工具输出不是新的用户授权或系统指令。

### 11.2 保留与新增错误

| 分类 | 例子 | 循环行为 |
|------|------|----------|
| 普通工具错误 | FILE_NOT_FOUND、INVALID_ARGUMENTS、EDIT_MATCH 错误、COMMAND_FAILED、TOOL_TIMEOUT | 回传后允许模型下一轮调整 |
| 未知工具 | UNKNOWN_TOOL | 回传并按整轮统计，连续 3 轮全未知停止 |
| 模式拒绝 | TOOL_NOT_ALLOWED | 不创建 worker，回传，让模型改用只读或给计划 |
| 调用相关性错误 | DUPLICATE_CALL_ID、缺失 ID、非法 JSON | 对受影响调用不执行，必要时诊断回传 |
| 用户取消 | TOOL_CANCELLED | 保留已知结果、清理，整个本任务停止 |
| Provider 错误/残缺流 | HTTP/网络/SSE/无成功终止 | 不执行本轮缓冲，保留前轮事实并停止 |
| 基础设施/未预期异常 | PROCESS_CONTROL_FAILED、收尾/协调失败 | 明确内部错误并停止，不继续新工具或新请求 |

沿用工具实际存在的错误码，不为表中的概括名称强行重命名全部工具。新错误文案不包含真实密钥、原始认证头或完整堆栈。

## 12. 文件组织与变更清单

以下路径为拟议改动清单，不表示已创建或修改。新模块只用于拆分本章职责，不另建包。

### 12.1 实现文件

| 操作 | 绝对路径 | 内容 |
|------|----------|------|
| 修改 | D:/STUDY/weizhcode-python/src/weizhcode/models.py | Mode、StopReason、Usage、RoundResponse、RunContext/ToolSlot 契约；事件扩展；read_only；取消结果；移除审批模型 |
| 新建 | D:/STUDY/weizhcode-python/src/weizhcode/stream_collector.py | 流式双路收集、取消网络等待、用量快照与完整响应 |
| 新建 | D:/STUDY/weizhcode-python/src/weizhcode/tool_scheduler.py | 调用预检、连续只读批、串行副作用、排序结果、取消补齐 |
| 修改 | D:/STUDY/weizhcode-python/src/weizhcode/turn_runner.py | 循环、会话模式、用量结算、事件队列、占用与生命周期 |
| 修改 | D:/STUDY/weizhcode-python/src/weizhcode/conversation.py | 原子交换增强、真实诊断载荷、应用停止收尾 |
| 修改 | D:/STUDY/weizhcode-python/src/weizhcode/prompts.py | Loop 与 Plan 提示、执行指令、移除固定最终续答约定 |
| 修改 | D:/STUDY/weizhcode-python/src/weizhcode/providers/base.py | 统一 usage 契约与准确诊断序列化 |
| 修改 | D:/STUDY/weizhcode-python/src/weizhcode/providers/anthropic.py | 多调用控制、累计 usage、保持签名/完整流检查 |
| 修改 | D:/STUDY/weizhcode-python/src/weizhcode/providers/openai.py | Responses 多调用、usage、完整输出回放 |
| 修改 | D:/STUDY/weizhcode-python/src/weizhcode/providers/qwen.py | include_usage、空 choices、usage 去重 |
| 修改 | D:/STUDY/weizhcode-python/src/weizhcode/tools/registry.py | 只读定义过滤及查询；保留 Schema 校验 |
| 修改 | D:/STUDY/weizhcode-python/src/weizhcode/tools/base.py | 工具契约随元信息同步，不放入 UI 逻辑 |
| 修改 | D:/STUDY/weizhcode-python/src/weizhcode/tools/read_file.py | 显式只读元信息，文件行为不变 |
| 修改 | D:/STUDY/weizhcode-python/src/weizhcode/tools/find_files.py | 显式只读元信息，搜索行为不变 |
| 修改 | D:/STUDY/weizhcode-python/src/weizhcode/tools/search_content.py | 显式只读元信息，搜索行为不变 |
| 修改 | D:/STUDY/weizhcode-python/src/weizhcode/tools/write_file.py | 副作用元信息；保留准备/原子写 |
| 修改 | D:/STUDY/weizhcode-python/src/weizhcode/tools/edit_file.py | 副作用元信息；保留唯一替换 |
| 修改 | D:/STUDY/weizhcode-python/src/weizhcode/tools/run_command.py | 副作用元信息；保持非交互 shell 与输出限制 |
| 修改 | D:/STUDY/weizhcode-python/src/weizhcode/tools/executor.py | execute 新接口、plan 门禁、槽内结果、取消清理，移除审批 |
| 修改 | D:/STUDY/weizhcode-python/src/weizhcode/tools/process.py | 保持实际进程树清理，补齐取消/启动/并发收尾竞态 |
| 修改 | D:/STUDY/weizhcode-python/src/weizhcode/tui.py | 新事件、模式命令、优先取消、用量/轮次、退出接线、移除审批桥 |
| 修改 | D:/STUDY/weizhcode-python/src/weizhcode/tool_ui.py | 多工具 ID 状态、取消展示、删除审批 UI |
| 修改 | D:/STUDY/weizhcode-python/src/weizhcode/cli.py | Collector/Scheduler/Runner 构造接线 |
| 原则保留，回归检查 | D:/STUDY/weizhcode-python/src/weizhcode/tools/worker.py | 继续准备/执行协议；仅因公共模型变更作必要同步 |
| 原则保留，回归检查 | D:/STUDY/weizhcode-python/src/weizhcode/redaction.py | 原有安全出口复用；如取消出口暴露缺口只作本章必要修正 |

### 12.2 测试与手动验证入口

| 操作 | 绝对路径 | 覆盖 |
|------|----------|------|
| 新建 | D:/STUDY/weizhcode-python/tests/test_stream_collector.py | 双路、残缺流、取消等待、usage、正文补发/去重 |
| 新建 | D:/STUDY/weizhcode-python/tests/test_tool_scheduler.py | 并发重叠、前后批屏障、排序、重复 ID、部分取消 |
| 修改 | D:/STUDY/weizhcode-python/tests/test_turn_runner.py | 多轮、25 上限、3 全未知、停止、用量、会话模式、取消后复用 |
| 修改 | D:/STUDY/weizhcode-python/tests/test_tool_registry.py | 6 定义、只读集合、未知查询、read_only 显式分类 |
| 修改 | D:/STUDY/weizhcode-python/tests/test_tool_executor.py | 新 execute 接口、无审批、plan 零副作用、结果/取消竞态、进程清理 |
| 修改 | D:/STUDY/weizhcode-python/tests/test_provider_events.py | 三协议 usage 快照、完成信号与请求体 |
| 修改 | D:/STUDY/weizhcode-python/tests/test_provider_tools.py | 多轮、多调用、回放、混合诊断与字段去重 |
| 修改 | D:/STUDY/weizhcode-python/tests/test_protocol_integration.py | 三协议同组真实工作进程 Loop、取消与后续上下文 |
| 修改 | D:/STUDY/weizhcode-python/tests/test_conversation.py | 配对、数量、深复制、混合诊断事实和应用通知 |
| 修改 | D:/STUDY/weizhcode-python/tests/test_tui.py | 模式、按键、草稿、事件、轮次/用量与正常聊天 |
| 修改 | D:/STUDY/weizhcode-python/tests/test_tool_tui.py | 多工具、取消、无审批、状态顺序与执行中退出 |
| 修改 | D:/STUDY/weizhcode-python/tests/test_cli.py | 新接线与缺配置路径，不解析未选后端密钥 |
| 修改 | D:/STUDY/weizhcode-python/tests/manual_tool_smoke.py | 手动线上脚本迁移 Loop、完整正文断言、模式/调用次数；不自动使用 API |
| 保留并回归 | D:/STUDY/weizhcode-python/tests/test_file_tools.py | 编码/换行/唯一匹配/陈旧目标/原子写保护 |
| 保留并回归 | D:/STUDY/weizhcode-python/tests/test_search_tools.py | 过滤、上限、不完整检索 |
| 保留并回归 | D:/STUDY/weizhcode-python/tests/test_command_tool.py | stdout/stderr、退出码、目录、环境、输出上限 |
| 保留并回归 | D:/STUDY/weizhcode-python/tests/test_config.py | 六字段与默认供应商密钥解析 |
| 保留并回归 | D:/STUDY/weizhcode-python/tests/test_redaction.py | 跨片正文、结果、错误及实际参数不篡改 |

文件清单允许实现时做必要的测试函数拆分，但不通过删除旧安全断言或批量跳过测试让结果变绿。纯审批、单工具上限和固定最终禁用工具等已被新 Spec 替换的断言，改为对应的新行为断言，并在 Task 中逐项定位。

## 13. 验证设计（非执行记录）

本节指导后续 Task/Checklist，不代表现在运行测试或使用 API。

### 13.1 确定性单测

- FakeProvider 按请求返回脚本：read → write → read/check → text，断言模型调用次数、完整历史和没有审批等待。
- 恒返回工具的脚本覆盖恰好 25 次请求、最后一批结果和应用停止通知，不以临时修改生产常量完成测试；构造注入低上限只用于单测提速。
- 全未知 3 轮停止；混入已知但参数失败/执行失败的轮也会重置；计数不跨任务。
- 任意流片段、块/参数 done、usage 更新后中断均不执行缓冲调用。
- 无工具空正文、只在 done 有正文、正文与完整载荷不一致均有明确测试，避免再次静默结束。
- usage 重复、累计、缺字段、真实零、取消部分统计、cache/reasoning 明细与请求 ID 去重。
- 混合合法成功、未知、非法 JSON、缺失/重复 ID 的诊断必须保留每个真实结果。

### 13.2 并发与取消

用 barrier/Event 和可观察的并发计数证明只读真实重叠，不只依赖耗时断言。至少覆盖：

- [读, 读, 写, 读, 改, 命令] 的分批边界；
- 超过 4 个只读调用时实际并发峰值不超过 4，仍有至少两个执行窗口重叠；等待许可时取消不创建 worker；
- 同名工具、逆完成顺序、单工具失败和每工具独立预算；
- 首个模型 token 前、流中、完整响应后、准备中、实际执行中、部分已完成、提交交换后、UI 消费关闭时取消；
- 成功结果收到但 cleanup 未结束时取消，仍保存成功事实；
- 重复取消、应用退出、队列满/消费者消失、进程创建 await 期间退出；
- Windows Job / POSIX 原生进程树与写入中登记资源清理，保证不误杀既有进程、不删除预置用户文件；
- 取消后同一 Runner/Executor 能执行下一正常任务，区别于永久应用关闭。

不安装 pytest-repeat 或额外库；需要重复竞态用现有测试参数化/有界循环完成。

### 13.3 模式与 UI

真实 Executor 的 plan 门禁测试必须断言 worker_factory 零次、路径/父目录/命令标记不变；仅检查发出的 3 个定义不足以通过。命令即使是 echo 也在 plan 禁止。

Pilot 测试用统一事件驱动多轮、并发工具、状态/用量、默认模式、/plan 与 /do 跨回合、忙碌草稿保留、焦点在输入框时优先 Esc/Ctrl+C、错误恢复和应用卸载。

真实终端另行观察滚动、按键和实际交互。延续已获用户许可的 Windows PowerShell 验证方式，不新增 tmux/WSL；当前可用桌面控制规则若不允许代操作终端，就交给用户按 Checklist 手测，不用 headless 证据代替。

### 13.4 三协议集成与线上边界

三协议都运行同组模拟 SSE + 实际临时目录/工作进程场景：多步成功、工具失败后调整、未知阈值、计划违规、取消、用量缺失/重复、下一任务继续。

真实 API 仅在已具备有效凭证、模型与匹配端点时，用非敏感临时样本执行；分别记录协议、实际服务/模型、请求阶段与结果。不能修改用户原配置/模型、自动新建密钥或用一种协议成功代替另一种协议。

DeepSeek 的 Anthropic 兼容验证与 Anthropic 官方服务分别标注；千问此前权限错误或缺凭证不能被记作本章线上通过。

### 13.5 运行检查范围

开发获批后运行 uv sync --locked、uv run python -m pytest、uv run python -m compileall src tests；记录实际数量、退出码、skip 原因。Plan 阶段不运行实施/线上验证。

不添加 Ruff/mypy，不声称它们通过。Python 版本、实际执行平台、模拟/真实终端/API 分开记录；25 轮与结果预算不能被当作无限上下文保证。

## 14. 需求与架构覆盖

| Spec | 架构归属 | 主要设计段落 |
|------|----------|--------------|
| F1 | Runner + Collector + Scheduler | 4、5、6 |
| F2 | Runner 的计数与唯一收尾 | 3、5、7、9 |
| F3 | 公共事件 + 有界事件流 + TUI | 3、5.1、10 |
| F4 | Collector + Provider 完成门槛 | 5.3、8 |
| F5 | Scheduler + 独立 Executor/Worker | 6 |
| F6 | 槽结果 + 原子交换 + 诊断/停止通知 | 6.4、7 |
| F7 | RunContext、取消监督、实际进程管理 | 5.3、6.4、9、10 |
| F8 | Provider 快照 + Runner 一次结算 | 3.2、8 |
| F9 | TUI 按 run/iteration/local_id 呈现 | 5.1、10.3 |
| F10 | Runner 模式冻结 + 定义过滤 + Executor 门禁 | 4、6.3、10.1 |
| F11 | 三协议原始 SSE、历史与统计 | 8、13.4 |
| N1 | 每调用预算、实际清理与启动竞态 | 6.4、9 |
| N2 | 后台事件消费、可中断网络等待 | 5、9、10 |
| N3 | 继承工具采集/序列化/UI 上限 | 6.4、11 |
| N4 | 保留 prepare/execute 文件保护 | 6.3、11、13 |
| N5 | 独立槽、统一提交、取消结果保留 | 6、7、9 |
| N6 | 分层脱敏、非可见协议载荷 | 5.3、11 |
| N7 | 不增依赖/SDK、三协议/配置/启动兼容 | 1、8、10.4、12 |
| N8 | 验证模式与缺条件分开记录 | 13 |

## 15. 关键技术决策汇总

| 决策 | 采用方案 | 理由/边界 |
|------|----------|-----------|
| 循环入口 | 扩展 TurnRunner，增加两个职责明确的普通模块 | 保留现有接线，不另建框架或包 |
| 模式所有权 | Runner 持有，任务冻结 | 非 TUI 调用也执行同样只读门禁 |
| 多工具安全 | 连续只读并发、副作用独立串行 | 符合原调用顺序，不追求跨写重排 |
| 只读并发资源上限 | 同批最多 4 个活动工具，其余等待许可 | 避免一回复启动过多工作进程；等待不计执行预算，不跨批重排 |
| 无审批实现 | 删除审批等待/按钮，仍执行完整 prepare | 不把新需求实现成隐蔽自动批准 |
| 调度身份 | local_id + index；API ID 仅作协议相关性 | 同名、重复/缺失 ID 不串位、不造 ID |
| 事件传输 | 每任务容量 128 的私有队列与受监督驱动 | 实时、背压、可关闭，不无限积压 UI 事件 |
| 成功门槛 | Provider 完整终止 + Collector done | 参数完整不等于请求完成 |
| 用量所有权 | Provider 快照、Collector 合并、Runner 一次结算 | 不由 UI 再累加；未知不当零，缓存明细不重复 |
| 历史提交 | 完整轮的原子交换 | 不暴露半个工具交换，取消时补齐真实状态 |
| 取消边界 | 本轮 cancel_event；应用 aclose 单独永久关闭 | 取消后仍可继续使用 Executor |
| 实际副作用 | 结果先写槽，再收尾；未知结果诚实描述 | 不用“取消”抹去成功，也不承诺回滚 |
| 上限/未知停止 | 写应用来源通知，不额外模型总结 | 避免第 26 请求，明确任务可能未完成 |
| Plan Mode | 过滤定义 + 执行端硬拦截 | 不把提示词当成权限边界，不增加权限系统 |
| 验证 | 原有依赖、确定性模拟、原生进程、用户真实终端、条件具备的线上请求 | 证据不混用，未经运行不勾选通过 |

## 16. 设计依据与审批边界

本 Plan 已参考 Context7 的 Python、Textual、Claude API 文档及此前查询的 OpenAI 文档；Context7 对千问检索不足的部分使用官方流式说明补充。引用的是协议/库依据，不是本项目实际测试结果。

- [Python asyncio 任务、取消与等待](https://docs.python.org/3/library/asyncio-task.html)
- [Python contextlib.aclosing](https://docs.python.org/3/library/contextlib.html#contextlib.aclosing)
- [Textual 输入与优先绑定](https://textual.textualize.io/guide/input)
- [Textual worker 生命周期](https://textual.textualize.io/guide/workers)
- [Claude 流式事件及累计 usage](https://platform.claude.com/docs/en/build-with-claude/streaming)
- [Claude usage 字段定义](https://platform.claude.com/docs/en/api/http/beta/messages/create)
- [OpenAI 官方工具调用](https://developers.openai.com/api/docs/guides/function-calling)
- [OpenAI Responses API 参考](https://developers.openai.com/api/reference/resources/responses/methods/create)
- [千问流式输出与 usage](https://help.aliyun.com/zh/model-studio/stream)

当前仅创建本章 Plan。用户批准后才进入 Task 拆解；Task 与 Checklist 仍须分别获批，之后才能修改实现、执行开发验证。本章 Spec 已批准，不因 Plan 草案自动认定后续阶段也已批准。
