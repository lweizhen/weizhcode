# weizhCode 工具系统 Plan

> 状态：技术方案已逐段确认，本文已获用户明确批准。
> 依据：[已批准的 spec.md](D:/STUDY/weizhcode-python/specs/tool-system/spec.md)。本文是实现设计，不代表代码已经完成或测试已经通过。
> 用户已明确允许：本阶段使用 Windows PowerShell 真实终端测试替代仓库要求的 tmux 测试，不为此安装额外系统组件。

## 1. 设计基线与范围

- 延续现有 Python 项目，保持 Python >=3.11、uv、Textual、HTTPX 与 SSE，不照搬参考项目的包名、SDK 或目录结构。
- Anthropic 使用 Messages API，OpenAI 使用 Responses API，通义千问使用 OpenAI-compatible Chat Completions。
- 固定六个工具；每次用户提问最多执行一个工具，工具结果之后至多再请求一次最终文字答复，不实现 Agent Loop。
- 读文件、找文件、搜内容自动执行；写文件、改文件、执行命令逐次审批。
- 工具在可终止的独立工作进程运行；这不是执行沙箱，不新增路径白名单。
- 工具实际计算采用统一 30 秒累计预算，审批等待不计时；结果文本上限为 20,000 字符。
- 保持现有 YAML 配置字段、启动方式和无需工具的聊天体验，不新增工具或超时配置。
- 借鉴参考材料的任务依赖、逐项验证和需求映射组织方式，不采纳其多工具执行、免审批、仅两个协议或与当前项目不同的数值上限。

## 2. 架构概览

### 2.1 组件职责

| 组件 | 职责 | 不负责的事情 |
|------|------|--------------|
| TUI | 消费单轮事件，展示文字、工具行、预览、审批按钮和错误 | 不拼接协议请求、不直接执行工具 |
| TurnRunner | 编排首次模型请求、单工具处理、历史提交和最终续答 | 不包含工具文件操作、不管理操作系统细节 |
| Provider | 序列化工具定义与历史、解析 SSE、保留协议必需回放数据 | 不审批、不执行工具 |
| ToolRegistry | 固定顺序登记六个工具、按名查找、提供统一工具定义 | 不持有 UI、不负责进程超时 |
| ToolExecutor | 参数校验、准备操作、审批衔接、预算、执行与统一结果 | 不直接处理任一模型协议 |
| 工具工作进程 | 执行具体工具的 prepare/execute，持有待审批操作的私有状态 | 不调用模型 API、不修改会话历史 |
| Conversation | 保留文字、调用、结果及 Provider 私有回放信息 | 不依赖 TUI、不执行工具 |
| Redactor | 对展示与回传内容进行已知密钥脱敏，处理跨片段文字 | 不改变实际操作参数或磁盘内容 |

### 2.2 依赖方向

统一数据类型位于 models，工具只依赖统一数据而不依赖 Provider。依赖关系为：

- providers → models、errors、redaction、现有 SSE 传输。
- conversation → models。
- tools → models、文件/搜索辅助逻辑、进程管理。
- turn_runner → providers 的统一接口、conversation、tools 执行接口、prompts、redaction。
- tool_ui → models、Textual。
- tui → turn_runner、tool_ui、现有消息与布局组件。
- cli 负责创建并连接上述组件。

模块不反向导入 TUI；模型协议转换留在三个 Provider 中，避免循环依赖。

## 3. 核心数据结构

延续现有 dataclass 风格。字段中的集合在传入、存储和返回时防御性复制，不因共享字典或列表使历史被外部修改。

### 3.1 ToolDefinition

| 字段 | 类型 | 含义 |
|------|------|------|
| name | str | 稳定的工具标识 |
| description | str | 面向模型的中文用途与约束说明 |
| parameters | dict[str, object] | 本地校验与协议导出的参数 Schema |
| requires_confirmation | bool | 是否需要逐次审批；write_file、edit_file、run_command 为真 |

权限由工具定义显式声明，不按注册顺序推断；未知工具不能绕过审批。

### 3.2 ToolCall

| 字段 | 类型 | 含义 |
|------|------|------|
| local_id | str | 本轮 UI 和本地追踪使用的标识，不冒充协议调用 ID |
| call_id | str 或 None | 后端返回的调用 ID；缺失时不可执行 |
| name | str | 拼接完成的工具名称 |
| raw_arguments | str | 原始参数 JSON，便于诊断，未解析成功不能执行 |
| arguments | dict[str, object] 或 None | 成功解析的参数对象；None 表示尚未得到合法对象 |

调用完整不等于参数合法。执行器仍要校验 JSON 顶层类型、字段和工具业务约束。

### 3.3 ToolContext、FileSnapshot 与 PreparedOperation

- ToolContext：保存启动目录 project_root；其值在进程启动时确定，不随 shell 命令改变，不包含 API 密钥。
- FileSnapshot：保存原始路径对应的解析目标、是否存在、文件身份信息、内容 SHA-256、UTF-8 BOM 和换行信息；仅文件修改工具需要完整快照。
- PreparedOperation：保存 operation_id、ToolCall、规范化参数、解析后的目标或执行目录、审批预览、快照和工具执行所需私有状态。
- 准备好的实际内容保留在工作进程中，父进程只接收审批及状态所需的数据；不为了生成 UI 摘要丢弃实际执行参数。
- 审批绑定 operation_id 和本次具体操作。禁止收到任意一个允许按钮事件就批准其他待执行调用。

### 3.4 ToolResult

| 字段 | 类型 | 含义 |
|------|------|------|
| call_id | str 或 None | 对应协议调用；异常缺失时走诊断回灌，不伪造 ID |
| tool_name | str | 工具名称 |
| status | success / error / denied / timeout | 可区分的结果状态 |
| content | str | 实际结果正文，不是 UI 摘要 |
| error_code | str 或 None | 稳定的错误分类 |
| metadata | dict[str, object] | 路径、匹配数、退出码、跳过数量等有限元数据 |
| truncated | bool | 是否因体量限制截断 |

is_error 为派生语义：status 不为 success 时为真。搜索正常空结果仍为 success。

错误分类至少包括 INVALID_JSON、INVALID_ARGUMENTS、UNKNOWN_TOOL、TOO_MANY_TOOL_CALLS、TOOL_ROUND_LIMIT、USER_DENIED、TOOL_TIMEOUT、PREVIEW_STALE、MATCH_COUNT_ERROR、FILE_NOT_FOUND、NOT_A_FILE、BINARY_FILE、UNSUPPORTED_ENCODING、INVALID_REGEX、COMMAND_FAILED、PROCESS_CONTROL_FAILED、IO_ERROR、SEARCH_INCOMPLETE 和 INTERNAL_ERROR。

to_model_text() 将结果序列化为可供模型阅读的 JSON 文本，包含状态、错误代码、正文、截断标记与必要元数据。序列化文本受 20,000 字符总预算约束；优先压缩或截断正文和冗长诊断，保留状态、退出码、实际匹配数等关键信息。

### 3.5 ChatMessage

在现有 role、content 基础上扩展：

- role 支持 user、assistant、tool。
- content 保持文字内容，默认空字符串，继续兼容普通用户和助手消息。
- tool_calls 保存助手本次请求的调用集合。
- tool_results 保存与调用对应的结果集合。
- provider_payload 保存 Provider 私有的协议回放信息，例如 Responses 返回的完整可回放输出项。

模型正文与工具历史不使用 UI 的截断摘要。协议私有数据不交给工具解释，也不在界面展示。历史仅存在于当前进程，不新增持久化。

### 3.6 ProviderEvent

保留 start、text_delta、done、error，新增 tool_call_start、tool_call：

- tool_call_start：仅通知界面已发现工具调用，可显示“接收参数中”，不可据此审批或执行。
- tool_call：携带已经组装的 ToolCall，仍须等待整个响应成功结束。
- done：携带完整 assistant_message 和完成原因；只有收到后端有效成功终止信号才产生。
- error：携带安全错误信息；本次响应不再产生成功 done。

统一事件至少包含 type，以及按事件类型使用的 text、message、tool_call、assistant_message。不可把 SSE 连接 EOF 一律视为成功。

### 3.7 TurnEvent 与 ApprovalRequest

- TurnEvent 类型为 text_delta、tool_pending、tool_preparing、approval_required、tool_running、tool_result、turn_done、error。
- text_delta 标记 initial 或 final 阶段，便于在工具行前后创建正确的助手文字区域。
- 工具事件携带 local_id、必要的调用/操作信息或 ToolResult；发送到 TUI 的可见文字必须已经脱敏。
- ApprovalRequest 保存 request_id、operation_id、local_id、工具名称、实际路径或完整命令与目录、内容变更预览和预览截断标记。
- 原始 PreparedOperation 不发送给模型；审批预览不承担会话结果的职责。

## 4. 核心接口

以下是接口契约，不是本阶段提前实现的业务代码。

### 4.1 Tool

```text
definition: ToolDefinition
prepare(call: ToolCall, context: ToolContext) -> PreparedOperation
execute(operation: PreparedOperation, context: ToolContext) -> ToolResult
```

prepare 和 execute 是工作进程内的同步操作，由外部工作进程生命周期提供超时和非阻塞保证。

- prepare 只进行参数业务校验、读取、路径解析、匹配计数及预览准备，不创建目录、不写文件、不启动命令。
- execute 只接受该工具准备的具体操作，不重新从模型获取或替换参数。
- 工具的预期失败返回统一错误；工作进程与执行器兜底捕获其他异常并转换，不让异常堆栈进入 UI 或模型结果。

### 4.2 ToolRegistry

```text
register(tool: Tool) -> None
get(name: str) -> Tool | None
definitions() -> list[ToolDefinition]
create_default_registry() -> ToolRegistry
```

- 使用稳定的注册顺序导出定义：read_file、write_file、edit_file、run_command、find_files、search_content。
- 重复名称立即报错，不静默覆盖。
- 注册时检查工具 Schema；参数 Schema 为本地自包含定义，不接受远程引用，不因参数校验访问网络。
- Registry 提供统一定义，Provider 将其转换为当前 API 的工具列表；Registry 不直接执行工具。

### 4.3 ToolExecutor 与工作进程管理

```text
ToolExecutor.run(call: ToolCall, *, approve: ApprovalHandler) -> AsyncIterator[TurnEvent]
ToolExecutor.aclose() -> None（异步）
ManagedWorker.start(context: ToolContext) -> None（异步）
ManagedWorker.prepare(call: ToolCall) -> PreparedOperationPreview（异步）
ManagedWorker.execute(operation_id: str) -> ToolResult（异步）
ManagedWorker.aclose() -> None（异步）
ApprovalHandler(request: ApprovalRequest) -> bool（异步）
```

PreparedOperationPreview 是 PreparedOperation 的安全跨进程投影，包含 operation_id、可审批内容与有限元数据，不携带整个原文件副本。

ToolExecutor.run 依次输出状态事件，最后输出包含 ToolResult 的 tool_result。需要审批时先输出 approval_required，再等待 approve(request)；TUI 在处理该事件时建立对应 Future 和按钮，审批回调等待这个 Future。

无 UI 测试可注入立即批准或拒绝的 ApprovalHandler，但生产入口不能借此跳过必要审批。没有可用审批处理器时按拒绝处理。

### 4.4 Provider

```text
stream_chat(
    messages: list[ChatMessage],
    *,
    tools: Sequence[ToolDefinition] = (),
    system_prompt: str = 空字符串,
    allow_tools: bool = True
) -> AsyncIterator[ProviderEvent]
```

保留现有方法名称，扩展关键字参数。首次请求 allow_tools=True；最终续答 allow_tools=False，仍可保留工具定义以便正确解释历史。Provider 负责映射当前协议的工具控制参数，执行次数限制始终由 TurnRunner 再次保障。

### 4.5 Conversation 与 TurnRunner

```text
Conversation.add_user_message(content: str) -> None
Conversation.add_assistant_message(content: str) -> None
Conversation.add_assistant_turn(message: ChatMessage) -> None
Conversation.add_tool_exchange(assistant: ChatMessage, results: Sequence[ToolResult]) -> None
Conversation.messages() -> list[ChatMessage]

TurnRunner.run(user_text: str, *, approve: ApprovalHandler) -> AsyncIterator[TurnEvent]
TurnRunner.aclose() -> None（异步）
```

- 保留已有普通消息追加方法。
- add_tool_exchange 一次提交助手调用和对应结果，验证 ID 配对，不留下正常调用没有结果的半套历史。
- messages 返回防御性副本，包括新增嵌套数据。
- TurnRunner 持有 Provider、Conversation、Registry、Executor、系统说明与 Redactor；TUI 不再直接调用 Provider。
- 同一 TurnRunner 只运行一轮；忙碌状态在接收提交时立即建立，早于启动后台任务，避免连续提交竞态。

## 5. 六个工具的参数与行为

所有 Schema 都要求 JSON 顶层为对象，拒绝未知字段；不将错误类型静默转换为字符串或布尔值。可选字段未提供时由 prepare 填充默认值。

| 工具 | 必填参数 | 可选参数及默认值 | 关键约束 |
|------|----------|------------------|----------|
| read_file | path: string | start_line: integer=1；line_count: integer=200 | start_line >=1，line_count 为 1～200；返回带原始行号的文本 |
| write_file | path: string；content: string | 无 | 可写空内容；自动创建缺失父目录仅发生在批准后的执行阶段 |
| edit_file | path: string；old_text: string；new_text: string | 无 | old_text 非空且精确匹配一次；new_text 可空 |
| run_command | command: string | cwd: string=启动目录 | command 非空；cwd 必须为有效目录；命令和目录须完整展示后批准 |
| find_files | pattern: string | path: string=启动目录；include_hidden: boolean=False；include_ignored: boolean=False | glob 模式查文件，最多 200 条 |
| search_content | pattern: string | path: string=启动目录；is_regex: boolean=False；include_hidden: boolean=False；include_ignored: boolean=False | 默认普通文本、区分大小写；最多 100 条 |

path、command、pattern 等必填标识字符串不能为空；写入内容和 new_text 不适用该限制。整数校验不接受布尔值；通过 JSON Schema 校验的整数值在准备阶段规范化为实际整数。

### 5.1 路径与读取

- 所有相对路径相对于不可变的启动目录解析；允许绝对路径及工作目录外目标，不擅自添加沙箱约束。
- 实际目标和执行目录在 prepare 中解析；审批展示真实目标，必要时同时说明用户提供的原始路径。
- 目录不能作为普通文件读取或修改；文件不存在、权限不足等分别给出原因。
- UTF-8 严格解码，识别并移除文件开头的 BOM 供文本处理，BOM 作为独立格式信息保存；不使用替换字符掩盖解码错误。
- 带行号的读取内容中，行号为应用附加信息，不属于文件原文；结果元数据说明 BOM 和换行风格。
- 起始行超过文件末尾时正常返回空片段；超过读取范围或字符预算时标记截断及下一起始行，不把 200 行上限误作整个文件只有 200 行。
- 大文件和超长行使用分块读取与受限内容缓冲，不能先读完整文件再为输出截断。

### 5.2 写入与精确替换

- 新文件为 UTF-8 无 BOM、LF 换行；已有文件保留 BOM，新增文本沿用原换行风格。
- 混合换行不重新格式化未修改部分；新增文本采用出现次数最多的换行符，并列时采用最先出现的类型；无换行记录时采用 LF。
- old_text 按实际原文精确匹配，不自动忽略空白、大小写或 CRLF/LF 差异；新增文本的格式处理不改变原文匹配规则。
- 匹配次数必须完整统计：0 次和多次均返回 MATCH_COUNT_ERROR，metadata.match_count 保存实际次数；不能把“至少两次”冒充实际计数。
- 对大文件采用分块扫描、增量 UTF-8 校验和内容指纹计算，处理跨块匹配，不要求把整个文件复制到主进程。
- prepare 记录匹配位置、快照与有界预览；execute 再次核对路径解析结果、存在状态、文件身份和内容指纹，不一致返回 PREVIEW_STALE。
- 批准后才创建目录与本轮临时文件。临时文件位于目标同一目录，完整写入后替换目标，尽量避免直接覆盖导致部分内容落地。
- 修改保留未改动文本，不将脱敏文本写回磁盘；原文件权限信息在可保留的平台上随替换维护。
- 临时文件路径登记给父进程用于异常收尾，仅清理本轮创建的临时文件，不删除用户其他文件。
- 替换文件和创建父目录不是跨文件事务；执行失败、超时或系统故障不承诺回滚已经发生的所有副作用，结果不能把部分失败报告为成功。

### 5.3 命令执行

- Windows 优先使用可用的 PowerShell 7（pwsh），否则使用 Windows PowerShell（powershell）；找不到时返回明确错误，不静默改为 cmd。
- Windows 启动为无配置脚本、非交互模式，避免加载个人 profile 改变执行语义；后台工作进程和 shell 不额外弹出可见窗口。
- Linux/macOS 使用 /bin/sh；不启动持久交互 shell。
- cwd 在 prepare 校验，每次单独传给 shell 子进程，不修改 weizhCode 主进程的工作目录。
- 标准输入关闭，不提供交互式命令输入界面；需要交互的命令收到 EOF 或受统一超时约束。
- stdout、stderr 同时消费，使用增量解码和共享文本预算，保留两种来源标签；超限后继续排空但不累计保存内容，直至结束或超时。
- metadata.exit_code 保留实际退出码；非零退出返回 COMMAND_FAILED。超时与进程管理失败采用不同错误代码。
- 超时返回已安全收集的有限输出及状态，不声称命令副作用已回滚。

### 5.4 搜索与忽略规则

- 使用应用控制的目录遍历，pathspec 处理忽略模式，wcmatch 处理 glob 匹配；不要求外部 rg 或 Git 可执行文件。
- 维护各级 .gitignore 的相对作用域、顺序、否定规则及目录剪枝；指定项目子目录时保留相关祖先 .gitignore 的作用域，向上不越过所属仓库边界；非仓库搜索以指定根为边界。
- 不读取或修改 Git 全局配置；include_ignored=True 跳过 .gitignore 过滤，但不自动取消隐藏过滤。
- 默认跳过点号隐藏项和操作系统标记的隐藏项；include_hidden=True 不自动取消 .gitignore 过滤。读取忽略规则文件本身不受“搜索结果不包含隐藏项”的限制。
- 默认不跟随目录符号链接以防递归环；直接指定其目标目录仍可搜索，不将该策略描述为路径白名单。
- glob 按相对搜索根的路径匹配，支持 ** 跨目录，并覆盖根目录文件场景；内部规范化分隔符，Windows 文件名匹配沿用 Windows 大小写逻辑，POSIX 区分大小写。
- 内容搜索使用普通文本包含判断，显式 is_regex=True 时编译标准库正则；内容默认始终区分大小写。
- 文件内容分块解码、逐行搜索。二进制或非 UTF-8 文件跳过并累计数量；超长行不能无界缓冲，无法完整检查时明确标记未完整搜索。
- 搜索根不存在或无法进入时返回错误；中途权限等问题返回 SEARCH_INCOMPLETE 并携带已取得的有限结果及原因，不当作完整空结果。
- 无匹配项且检索完整时为 success；达到数量或字符预算时停止继续检索并标记截断；超时为 timeout，不伪装成正常无匹配。

## 6. 执行器、审批与进程生命周期

### 6.1 执行流水线

1. 取得完整 ToolCall，验证调用 ID、名称、JSON 对象及注册工具 Schema。
2. 无效调用产生结构化结果，不启动实际工具操作。
3. 建立 ManagedWorker，先完成操作系统进程管理，再释放启动握手；未建立管理时工作进程不能接收可执行指令。
4. 工作进程运行 prepare，返回 operation_id 和预览；prepare 的文件访问和扫描同样受时间预算约束。
5. 无需审批时继续执行；需要审批时输出 approval_required，暂停预算，等待本次对应的批准或拒绝。
6. 拒绝时生成 USER_DENIED，结束工作进程；不执行 mkdir、写入或 shell 启动。
7. 批准后恢复剩余预算，工作进程核对操作与文件快照后 execute。
8. 收集 ToolResult，统一脱敏及限制体量，输出 tool_result；正常、异常、拒绝或超时均进入收尾。

预算为准备与执行累计 30 秒，不按阶段重置为两个 30 秒。等待审批的时间单独排除；进程启动、准备与执行的计时采用单调时钟，不受系统时间调整影响。

### 6.2 工作进程通信

- 使用当前项目解释器启动内部 worker 模块，避免另一个系统 Python 缺少依赖。
- 参数通过私有管道发送，不把文件内容或密钥放进进程命令行。
- 工作进程标准输出仅承载应用内部的结构化通信；shell 输出由独立管道收集，不可混入通信协议。
- 消息含操作类型、operation_id 和相应数据；仅支持 prepare、execute、abort，状态不匹配或重复 execute 直接拒绝。
- 父进程不接受工作进程返回的新工具名、新目标或新命令来替换已批准操作。
- 预览和结果传输均使用有限内容；异常 stderr 只形成经过脱敏及截断的诊断，不展示原始堆栈。
- 同一调用的工作进程可在审批期间等待，但不能继续工具操作；审批一旦结束只消费一次决定。

### 6.3 Windows 与 POSIX 进程管理

- Windows 使用独立 Job Object，并设置 KILL_ON_JOB_CLOSE。工作进程启动后先等待握手，在加入 Job 成功后才允许 prepare/execute；由其创建的 shell 和普通后代纳入 Job，不允许 breakaway。
- Job 设置或分配失败时返回 PROCESS_CONTROL_FAILED，终止待命工作进程，不启动用户命令。
- Windows 原生调用封装在 process 模块，使用标准库 ctypes，不新增 Windows 专用第三方依赖。
- POSIX 启动独立会话/进程组，超时向该组发送终止信号，必要时强制结束并等待回收。
- 超时不是只取消等待协程；必须停止本轮受管进程，再关闭管道、回收进程，并清理登记的本轮临时文件。
- 正常收尾也关闭本轮管理对象，不将后台 shell 作为持久会话留存；退出应用时执行同样清理。
- 进程组和 Job 用于生命周期管理，不是安全沙箱；不承诺约束主动脱离 POSIX 进程组或经外部服务启动的独立任务。该限制不能被表述为已经提供进程沙箱。
- 强制终止不回滚文件写入、网络请求或命令已经产生的其他外部影响。

## 7. 后端适配与会话历史

### 7.1 请求与结果格式

| 后端 | 工具定义 | 流式调用组装 | 结果回灌 | 最终续答控制 |
|------|----------|--------------|----------|--------------|
| Anthropic | name、description、input_schema | 按 content block index 收集 tool_use 与 input_json_delta | assistant tool_use 后，下一条 user 消息放对应 tool_result，通过 tool_use_id 配对；失败设置 is_error | tool_choice.type=none |
| OpenAI Responses | type=function，名称与 parameters 位于工具对象顶层，显式 strict=False | 按 output_index/item 标识累积 function_call 及 arguments delta | 保留可回放 output items，追加 function_call_output，使用 call_id | tool_choice=none |
| 千问 Chat Completions | type=function，name、description、parameters 位于 function 内 | 按 delta.tool_calls.index 分别拼接 ID、名称及 arguments | 先保留 assistant.tool_calls，再追加 role=tool、tool_call_id、content | tool_choice=none |

- Anthropic 系统说明使用 system；OpenAI 使用 instructions；千问使用 system 消息，不把系统约定显示成用户提问。
- 初次请求工具选择为 auto；Anthropic 设置 disable_parallel_tool_use=True，OpenAI 设置 parallel_tool_calls=False。
- 千问不依赖额外并行参数是否被兼容端点接受；TurnRunner 始终检查实际调用数量，作为三种后端统一的硬限制。
- OpenAI 保持 store=False；显式请求 reasoning.encrypted_content 兼容 stateless 回放，保存返回的必要输出与不透明加密数据，不启用新的 reasoning 参数或思考展示功能。
- optional 参数继续保持可选；不为 OpenAI 自动严格化而把默认值字段强制要求模型提供。工具安全校验始终以本地 Schema 和业务校验为准。
- 不引入 Anthropic/OpenAI SDK，不将 OpenAI Responses 改成 Chat Completions。

### 7.2 完成判定与缓冲

- SSE 传输继续复用现有实现；每个 Provider 单独维护本次响应的调用缓冲，不在多个调用之间共享参数字符串。
- 名称仅在协议实际返回增量时追加；最终完整对象用于校对，不把最终整段参数再次追加到已有碎片上。
- Anthropic 必须等 message_stop，并检查最终 stop_reason；工具调用须以 tool_use 正常结束，不能仅因 content_block_stop 或局部 JSON 完整就执行。
- OpenAI 必须等 response.completed 且状态完成；response.output_item.done 或 arguments.done 本身不表示整个请求成功。response.failed、response.incomplete、error 不允许执行缓冲中的工具。
- 千问检查选定 choice 的 finish_reason 以及流结束标记；tool_calls 才进入工具流程，stop 为正常文字，length/content_filter 等不视为可执行的完整工具回复。缺少有效完成信号的 EOF 作为流中断处理。
- 缺失或重复调用 ID、无效 JSON、参数不是对象等不能执行；界面可以提前显示接收状态，但实际审批和执行必须等整个响应成功结束。
- 思考文字不展示；协议要求保留的不透明回放信息与可见思考增量区分处理，不随意改写签名或密文。

### 7.3 固定两阶段协调

TurnRunner.run 的顺序如下，不使用持续循环：

1. 建立忙碌状态，保存本次用户消息，发起允许工具的请求 #1。
2. 转发安全正文增量和工具接收状态，等待完整成功 done；失败时标记本次显示未完成，不执行工具，不提交残缺助手调用。
3. 没有调用时，提交完整助手消息并结束，只有一次模型请求。
4. 恰好一个调用时，通过 ToolExecutor 取得成功、失败、拒绝或超时结果。
5. 多个调用时，不启动任何 prepare 或 execute；为每个可识别调用分别生成 TOO_MANY_TOOL_CALLS 结果，避免只执行前一个或遗漏结果。
6. 原子提交助手调用及对应结果，发起 allow_tools=False 的请求 #2。
7. 转发最终安全文字。没有新调用时提交完整最终助手消息并结束。
8. 若最终续答仍返回调用，则全部不执行，补记对应 TOOL_ROUND_LIMIT 结果以使下轮历史合法，显示单轮上限提示并结束，不发起请求 #3。
9. 任何退出路径均恢复状态并清理本轮资源；用户退出时只清理，不为了总结或修复历史额外请求模型。

工具执行失败不自动重试。请求 #2 网络失败时保留已经提交的真实调用与结果，用户下一次提问可以参考它们，程序不能悄悄重复之前有副作用的工具。

### 7.4 无法形成合法协议调用的诊断回灌

- 参数是合法 JSON 对象但不符合工具 Schema 时，保留真实调用 ID，按协议返回 INVALID_ARGUMENTS。
- 流已正常结束，但调用 ID 缺失、JSON 无效或调用结构无法合法编码时，不编造 ID，也不发送无法配对的 tool_result。
- 此类调用仍以 ToolCall 和结构化错误保留在本地历史；Provider 将该异常交换降级为明确标注的诊断文本，包含有限、脱敏的调用信息和错误结果，再进入禁用工具的最终续答。
- 诊断文本不能宣称工具执行过，不能伪装成正常工具调用成功；应用不修改原始私有记录来掩盖解析失败。
- 真正未完成的 SSE 响应不走诊断续答，直接作为请求错误结束，避免把尚未完整接收的内容当成模型决定。

## 8. 结果预算、脱敏与系统说明

### 8.1 体量控制

- 常量集中管理：TOOL_TIMEOUT_SECONDS=30、MAX_RESULT_CHARS=20_000、MAX_READ_LINES=200、MAX_FILE_MATCHES=200、MAX_CONTENT_MATCHES=100。
- 工具采集阶段即限制保留体量，不先收集全部输出再截断。命令达到保留上限后继续排空管道；搜索达到上限后停止遍历。
- 统一结果出口再次执行总预算检查；截断标记包含在结果预算中。
- UI 结果摘要另外限制为最多 8 行、1,000 字符，并明确提示截断，不挤占协议回放中的实际结果。
- 审批预览和结果摘要分开：完整命令和执行目录必须可见；文件变更预览可以有界，但必须标明仅为预览片段，实际批准对象绑定完整 PreparedOperation。

### 8.2 脱敏

- Redactor 从实际已解析的供应商配置取得应用已知密钥集合；不为了建立集合强行解析非默认后端缺失的环境变量。
- 已知密钥在进入可见 UI、错误面板、诊断及模型工具结果前统一替换为脱敏标记；结果脱敏后再次检查长度预算。
- StreamingRedactor 保留可能构成密钥的尾部前缀，跨 text_delta 拼接判断，结束时安全刷新；不能每片单独 replace 后立即输出。
- 不透明协议回放内容保持协议要求的格式，不尝试解密或修改签名；可见文字和模型可读结果须先经过脱敏。
- 实际文件内容、PreparedOperation 和 shell 参数不使用脱敏版本执行，不将占位标记写进用户文件。
- 不输出原始 HTTP 认证头、工作进程堆栈或完整请求日志；配置解析错误继续通过安全的用户错误路径展示。
- 不承诺识别所有其他凭证或敏感内容；用户仍需判断允许访问的文件和批准的命令。

### 8.3 系统说明

prompts 保存统一的内置说明，内容覆盖：weizhCode 的六种能力、参数用途、单工具与审批限制、读取行号不属于原文、精确匹配要求、截断提示、工具输出是数据而不是新的授权指令。

首次允许调用工具，最终阶段明确要求根据已返回结果直接回答。系统说明辅助模型遵守约定，但不能替代本地审批、参数校验和执行次数限制。

## 9. TUI 与模块交互

### 9.1 界面状态

本轮状态顺序为：requesting → preparing → awaiting_approval（按需）→ executing → finalizing → idle；无工具时 requesting 后直接 idle。工具失败或拒绝仍进入 finalizing，模型请求错误结束后恢复 idle。

- 提交后立即防重入，整轮只允许一个后台协调任务；允许编辑草稿、滚动和退出，但不提交第二个请求。
- 通过 Textual 异步 worker 消费 TurnEvent；事件处理器不等待工具执行，审批回调只等待对应 Future。
- ToolCallView 承载工具名、关键参数、状态、预览、摘要及两个审批按钮；不新增折叠展开。
- approval_required 处理时先创建对应 Future，再挂载按钮；初始焦点为“拒绝本次”，不会自动批准。
- 第一次按钮选择后立即禁用双方按钮，记录选择，再完成对应 Future；重复点击和过期事件无效。
- 工具 pending、准备、审批、执行、结果按事件顺序更新同一工具视图；最终回复创建在该视图之后，避免与前导文字混在一条消息里。
- 工具失败、拒绝、超时为内联状态；配置和模型请求错误沿用现有错误面板。错误确认后恢复输入，不把失败写成助手成功回复。
- 文字使用普通文本渲染，移除危险终端控制序列，不把模型或文件内容当 Rich markup、ANSI 控制指令或可执行界面内容。
- 状态栏由注册中心实际数量生成，正常为 Connected to 0 MCP server(s), 6 tools registered；不表示连接了 MCP。
- 退出时先使待审批 Future 失效、终止本轮任务、关闭模型流和 Executor；保留现有退出命令和快捷键，不新增“只取消当前操作”能力。

### 9.2 接线

cli 创建配置、Provider、Conversation、固定 Registry、Redactor、ToolExecutor、TurnRunner，并将协调器和现有供应商/模型/目录/版本展示信息传给 TUI。

TUI 提交 → TurnRunner 请求 Provider → Provider 返回统一事件 → TurnRunner 判断数量 → ToolExecutor 准备/审批/执行 → Conversation 提交交换 → Provider 最终续答 → TUI 展示结束。

审批结果只沿 UI Future → ApprovalHandler → ToolExecutor 回传；工具结果只沿工作进程 → Executor → TurnRunner → Conversation/Provider 回传，不能由按钮事件绕过执行器直接写入成功历史。

## 10. 文件组织

以下均为计划中的变更，不代表文件已经生成。项目根目录为 D:/STUDY/weizhcode-python。

### 10.1 新增实现文件

| 文件 | 职责 |
|------|------|
| [src/weizhcode/turn_runner.py](D:/STUDY/weizhcode-python/src/weizhcode/turn_runner.py) | 固定两阶段单轮编排、执行次数约束和历史提交 |
| [src/weizhcode/prompts.py](D:/STUDY/weizhcode-python/src/weizhcode/prompts.py) | 内置工具使用说明和最终续答要求 |
| [src/weizhcode/tool_ui.py](D:/STUDY/weizhcode-python/src/weizhcode/tool_ui.py) | ToolCallView、审批消息和安全摘要显示 |
| [src/weizhcode/redaction.py](D:/STUDY/weizhcode-python/src/weizhcode/redaction.py) | 批量及跨流式片段脱敏、安全显示文本 |
| [src/weizhcode/tools/__init__.py](D:/STUDY/weizhcode-python/src/weizhcode/tools/__init__.py) | 默认六工具注册工厂与包出口 |
| [src/weizhcode/tools/base.py](D:/STUDY/weizhcode-python/src/weizhcode/tools/base.py) | Tool 契约与工具准备/执行共用上下文 |
| [src/weizhcode/tools/registry.py](D:/STUDY/weizhcode-python/src/weizhcode/tools/registry.py) | 有序注册、按名查找和定义校验 |
| [src/weizhcode/tools/executor.py](D:/STUDY/weizhcode-python/src/weizhcode/tools/executor.py) | 参数校验、审批衔接、预算及结果归一 |
| [src/weizhcode/tools/process.py](D:/STUDY/weizhcode-python/src/weizhcode/tools/process.py) | ManagedWorker、管道、Job/进程组及清理 |
| [src/weizhcode/tools/worker.py](D:/STUDY/weizhcode-python/src/weizhcode/tools/worker.py) | 内部工作进程入口与 prepare/execute 握手 |
| [src/weizhcode/tools/limits.py](D:/STUDY/weizhcode-python/src/weizhcode/tools/limits.py) | 超时、条数、字符常量与预算处理 |
| [src/weizhcode/tools/file_utils.py](D:/STUDY/weizhcode-python/src/weizhcode/tools/file_utils.py) | UTF-8/BOM、换行、指纹、精确扫描和临时替换 |
| [src/weizhcode/tools/search_utils.py](D:/STUDY/weizhcode-python/src/weizhcode/tools/search_utils.py) | 忽略作用域、隐藏项、目录遍历及 glob 匹配 |
| [src/weizhcode/tools/read_file.py](D:/STUDY/weizhcode-python/src/weizhcode/tools/read_file.py) | 分段带行号读取 |
| [src/weizhcode/tools/write_file.py](D:/STUDY/weizhcode-python/src/weizhcode/tools/write_file.py) | 创建/覆盖的准备与执行 |
| [src/weizhcode/tools/edit_file.py](D:/STUDY/weizhcode-python/src/weizhcode/tools/edit_file.py) | 原文唯一匹配、预览和修改 |
| [src/weizhcode/tools/run_command.py](D:/STUDY/weizhcode-python/src/weizhcode/tools/run_command.py) | 跨系统 shell 选择及受限输出收集 |
| [src/weizhcode/tools/find_files.py](D:/STUDY/weizhcode-python/src/weizhcode/tools/find_files.py) | glob 文件查找 |
| [src/weizhcode/tools/search_content.py](D:/STUDY/weizhcode-python/src/weizhcode/tools/search_content.py) | 普通文本/正则内容搜索 |

### 10.2 修改现有文件

| 文件 | 改动 |
|------|------|
| [src/weizhcode/models.py](D:/STUDY/weizhcode-python/src/weizhcode/models.py) | 扩展统一工具数据、消息、事件与审批结构 |
| [src/weizhcode/conversation.py](D:/STUDY/weizhcode-python/src/weizhcode/conversation.py) | 完整助手回合、原子工具交换、防御性历史副本 |
| [src/weizhcode/errors.py](D:/STUDY/weizhcode-python/src/weizhcode/errors.py) | 接入统一脱敏，保留原错误入口的兼容性 |
| [src/weizhcode/providers/base.py](D:/STUDY/weizhcode-python/src/weizhcode/providers/base.py) | 扩展 stream_chat 关键字接口 |
| [src/weizhcode/providers/anthropic.py](D:/STUDY/weizhcode-python/src/weizhcode/providers/anthropic.py) | Messages 工具请求、流式组装、完成判定与回灌 |
| [src/weizhcode/providers/openai.py](D:/STUDY/weizhcode-python/src/weizhcode/providers/openai.py) | Responses 函数调用、可回放输出、完成判定与回灌 |
| [src/weizhcode/providers/qwen.py](D:/STUDY/weizhcode-python/src/weizhcode/providers/qwen.py) | Chat Completions 调用碎片、完成判定与回灌 |
| [src/weizhcode/tui.py](D:/STUDY/weizhcode-python/src/weizhcode/tui.py) | 消费 TurnEvent、审批 Future、忙碌保护、状态栏和退出清理 |
| [src/weizhcode/cli.py](D:/STUDY/weizhcode-python/src/weizhcode/cli.py) | 创建并注入新增组件，保留启动错误处理 |
| [pyproject.toml](D:/STUDY/weizhcode-python/pyproject.toml) | 增加 jsonschema、pathspec、wcmatch |
| [uv.lock](D:/STUDY/weizhcode-python/uv.lock) | 在允许开发后通过 uv 解析并锁定实际兼容版本 |

不预先重组现有 TUI 目录，不修改配置字段或用户本地配置，不新增 Agent Loop、MCP、SDK、高级工具运行器或系统安装脚本。

### 10.3 测试文件

| 文件 | 验证重点 |
|------|----------|
| [tests/test_tool_registry.py](D:/STUDY/weizhcode-python/tests/test_tool_registry.py) | 六条有序定义、重复名称、查询和 Schema |
| [tests/test_file_tools.py](D:/STUDY/weizhcode-python/tests/test_file_tools.py) | 读写改、0/1/多匹配、空文本、编码、BOM/换行、失效预览 |
| [tests/test_search_tools.py](D:/STUDY/weizhcode-python/tests/test_search_tools.py) | glob、普通/正则、嵌套忽略与否定、隐藏项、空结果和上限 |
| [tests/test_command_tool.py](D:/STUDY/weizhcode-python/tests/test_command_tool.py) | shell/cwd、输出来源、非零退出、进程树和体量 |
| [tests/test_tool_executor.py](D:/STUDY/weizhcode-python/tests/test_tool_executor.py) | 未批准无副作用、拒绝、审批计时暂停、超时、进程建立失败和清理 |
| [tests/test_turn_runner.py](D:/STUDY/weizhcode-python/tests/test_turn_runner.py) | 一次/两次请求、多个全部拒绝、续答禁用、错误和历史恢复 |
| [tests/test_redaction.py](D:/STUDY/weizhcode-python/tests/test_redaction.py) | 已知密钥、多次出现、跨片段、错误与工具结果脱敏、实际参数不被篡改 |
| [tests/test_provider_events.py](D:/STUDY/weizhcode-python/tests/test_provider_events.py) | 扩展现有三协议模拟流、请求体、终止信号、配对和诊断回灌 |
| [tests/test_conversation.py](D:/STUDY/weizhcode-python/tests/test_conversation.py) | 扩展工具交换、回放数据、防御性复制 |
| [tests/test_tui.py](D:/STUDY/weizhcode-python/tests/test_tui.py) | 扩展审批点击、状态、顺序、草稿、防重入、滚动、错误恢复和退出 |
| [tests/test_config.py](D:/STUDY/weizhcode-python/tests/test_config.py) | 保留原配置回归测试，包括只解析默认供应商密钥 |

## 11. 验证设计与证据边界

### 11.1 自动测试

- 使用 pytest、pytest-asyncio、临时目录、受控子进程与模拟 Provider，不依赖真实密钥。
- 三种协议均测试参数分片、正文混合、调用 ID、请求工具定义、系统说明、工具控制、结果配对、失败/未完成终止信号和后续历史。
- 对多个调用，断言 prepare 和 execute 均为零次；对最终阶段额外调用，断言不再执行、不发送第三个请求。
- 对审批，分别测试等待期间磁盘不变、拒绝后不变、批准后正确变化、双击不重复执行、等待超过短测试预算仍不自动超时。
- 超时测试可通过内部构造参数或测试替身缩短预算，生产常量仍为 30 秒，不增加用户配置项。
- 对进程树，在本机实际启动受控的父子进程并验证终止；Windows Job 与 POSIX 进程组分别在对应平台验证。被跳过的平台测试明确记录为未执行，不能据此声称跨系统实测通过。
- UI 使用 Textual run_test/Pilot 验证按钮和消息交互；无界面测试不代替真实终端外观验收。
- 全量命令为 uv run python -m pytest，以及 uv run python -m compileall src tests；暂不引入 Ruff 或 mypy，不填写未配置检查已通过。

### 11.2 Windows PowerShell 真实终端

- 按用户对本阶段的明确选择，使用 PowerShell 启动 uv run weizhcode，代替 tmux；不修改仓库通用说明，不安装 WSL/tmux。
- 验证读取测试文件并总结、审批写入、审批修改、命令批准/拒绝、工具错误恢复、工具行顺序、滚动、正文流式展示及退出后资源清理。
- 所有有副作用验证在专用临时测试目录进行，不拿真实项目源码做写入或覆盖实验。
- 写文件后再执行命令需要两次用户提交；首次请求同批提出两工具的专门场景应全部拒绝，不照搬参考材料的同轮顺序执行验收。
- 截图和记录须经过密钥检查；终端内可滚动历史与退出后的外部终端状态分别观察，不混淆两种 scrollback。

### 11.3 真实 API

- 按可用凭证分别记录 Anthropic、OpenAI、通义千问的真实工具闭环、错误反馈与最终续答，不输出或提交密钥。
- 自动模拟通过不代表线上端点已验证；缺少凭证、模型不支持工具或端点不完整兼容时，记录实际原因与未执行/失败状态。
- 不为验证而擅自更换模型、改写用户配置或安装服务；需要额外凭证或环境改动时先询问用户。
- 最终验收报告区分自动测试、真实 PowerShell 界面和真实 API，逐项列出证据，不将未运行项打勾。

## 12. 需求覆盖

| 需求 | 架构归属及设计位置 | 对应验收 |
|------|------------------|----------|
| F1 | Tool、Registry、Provider 定义转换；第 3～5、7 节 | AC1 |
| F2 | read_file、file_utils、预算；第 5.1 节 | AC2 |
| F3 | write_file、预览、审批和临时替换；第 5.2、6 节 | AC3 |
| F4 | edit_file、完整匹配计数、失效快照；第 5.2 节 | AC4 |
| F5 | run_command、process、cwd 与输出；第 5.3、6 节 | AC5 |
| F6 | find_files、glob 与搜索预算；第 5.4 节 | AC6 |
| F7 | search_content、文本/正则与命中位置；第 5.4 节 | AC6 |
| F8 | search_utils、作用域、隐藏与忽略规则；第 5.4 节 | AC6 |
| F9 | prompts、Provider 关键字参数、纯文字分支；第 7、8 节 | AC1 |
| F10 | Provider 调用缓冲、完成门槛、错误诊断；第 7 节 | AC7 |
| F11 | TurnRunner 固定两阶段、本地执行计数；第 7.3 节 | AC8、AC9 |
| F12 | PreparedOperation、ApprovalRequest、Executor 与 TUI；第 6、9 节 | AC3、AC4、AC5、AC10 |
| F13 | ToolResult、统一错误分类及异常收尾；第 3、6、7 节 | AC7、AC10 |
| F14 | 三个 Provider 保持原协议并适配统一行为；第 7 节 | AC1、AC12 |
| F15 | TurnEvent、ToolCallView、安全摘要与状态；第 8、9 节 | AC11 |
| F16 | Conversation 原子交换、回放及失败恢复；第 4、7 节 | AC8 |
| N1 | 共享 30 秒预算、Job/进程组和真实终止；第 6 节 | AC5、AC10 |
| N2 | 工作进程、Textual worker 和非阻塞审批；第 6、9 节 | AC11 |
| N3 | 工具采集预算、结果序列化预算、UI 摘要；第 8.1 节 | AC11 |
| N4 | UTF-8 严格处理、BOM/换行和精确修改；第 5.1、5.2 节 | AC2、AC13 |
| N5 | 统一调用/结果/事件和三协议同组测试；第 7、11 节 | AC12 |
| N6 | Redactor、StreamingRedactor 及安全出口；第 8.2 节 | AC13 |
| N7 | 不增加配置字段、保留纯文字分支与原测试；第 1、7、10 节 | AC13 |
| N8 | 模拟测试与真实终端/API 证据分层；第 11 节 | AC12 |

## 13. 关键技术决策

| 决策 | 选择与理由 |
|------|------------|
| 编排位置 | 独立 TurnRunner，使界面只展示，且可在没有 UI 的情况下验证固定执行次数 |
| 工具与执行器 | Tool 只准备和执行；Registry 只登记；Executor 承担校验、审批、预算和收尾 |
| 超时机制 | 独立工作进程加进程生命周期管理，不把协程超时当成已终止外部命令 |
| 参数校验 | jsonschema 的本地自包含 Schema，统一拒绝类型与字段错误，不让六个工具各自宽松解析 |
| 搜索依赖 | pathspec 处理忽略语义，wcmatch 处理 glob，标准库正则处理内容匹配；不要求外部搜索程序 |
| 模型客户端 | 沿用 HTTPX + SSE，三种后端不改协议、不引入专用 SDK |
| 最终续答 | 请求禁用工具并保留本地硬限制；意外再次调用补齐限制历史后停止 |
| 历史 | 统一消息加 Provider 私有回放信息；不为抽象统一而丢掉 Responses 必需输出 |
| 文件修改 | 先预览与快照、后批准与复核，完整临时写入后替换，不做模糊替换 |
| 脱敏 | 展示/回传统一处理，流式跨片段处理；实际操作保留原参数 |
| 验证环境 | 用户批准本阶段用 PowerShell 代替 tmux；不添加系统组件或擅自改变通用仓库说明 |
| 开发依赖与范围 | 只增加已确认的三个运行依赖，由 uv.lock 固定实际兼容版本；不顺带加入 lint、类型检查或项目重构 |

## 14. 文档核对来源

协议与依赖设计已通过 Context7 查询官方维护资料；千问相关索引未命中时补查阿里云官方文档。下列来源是设计依据，不代表本项目已经实测相应功能。

- [Anthropic SSE 与工具参数碎片](https://platform.claude.com/docs/en/build-with-claude/streaming)
- [Anthropic 调用 ID 配对及并行限制](https://platform.claude.com/docs/en/agents-and-tools/tool-use/parallel-tool-use)
- [OpenAI 官方 Function calling](https://developers.openai.com/api/docs/guides/function-calling)
- [OpenAI 官方 reasoning 与 stateless 回放](https://developers.openai.com/api/docs/guides/reasoning)
- [通义千问 Function calling](https://docs.modelstudio.console.alibabacloud.com/en/model-studio/qwen-function-calling)
- [Python asyncio 子进程、管道缓冲与超时收尾](https://github.com/python/cpython/blob/main/Doc/library/asyncio-subprocess.rst)
- [Windows Job Object 生命周期标志](https://learn.microsoft.com/en-us/windows/win32/api/winnt/ns-winnt-jobobject_basic_limit_information)
- [Textual 后台 Worker](https://textual.textualize.io/guide/workers)
- [Textual 无界面测试接口](https://textual.textualize.io/api/app)
- [jsonschema 验证接口](https://github.com/python-jsonschema/jsonschema/blob/main/docs/validate.rst)
- [pathspec 的 GitIgnoreSpec](https://github.com/cpburnz/python-pathspec/blob/master/README-dist.rst)
- [wcmatch glob](https://github.com/facelessuser/wcmatch/blob/main/docs/src/markdown/glob.md)

## 15. 当前交付状态与下一步

本次只生成 plan 文档；实现文件、运行依赖和测试尚未因本文而修改或执行。用户整体批准本文后，才进入 task 文档拆解；task 与 checklist 继续分别审批，四份文档全部批准后才能开始实现。
