# weizhCode 系统提示工程化 Plan

> 依据：本目录已批准的 spec.md；四文档已批准，实现与离线验证已完成，真实终端/API及人工观察待验，详见Checklist第13节。
> 流程：本次只生成 Plan。批准后生成 Task，再单独生成 Checklist；四份文档全部批准后才实现。
> 工程约束：Python 3.11+、HTTPX/原始 SSE、现有三协议与六字段 YAML 不变。本设计不代表代码、真实缓存命中或人工场景已验证。

## 1. 设计基线与改动范围

当前 `prompts.py` 保存固定系统文本与完整计划提醒；`TurnRunner` 每个请求把提醒拼到系统字符串尾部，经 `StreamCollector` 传给 Provider。三个 Provider 分别使用 Anthropic Messages、OpenAI Responses 和千问兼容 Chat Completions。`UsageAccumulator` 已累计部分统计，但 Anthropic 缓存字段缺失时补零、输出模型不保留缓存分项，Collector 也只合并输入/输出两项。

本章围绕上述链路做局部扩展，不重写 Agent Loop，不将参考材料中的 SDK、Chat Completions 双协议方案替换进本工程。保留现有完整流门槛、工具执行/提交、并发屏障、问答生命周期、脱敏、取消及退出收尾。

改动分为五层：

1. 提示装配：七个固定模块、三个空槽、确定性装配和兼容导出。
2. 任务上下文：每任务一次的有限环境快照，以及每请求重新生成的计划提醒。
3. 请求适配：三种协议合法承载稳定内容、环境和补充消息，按明确能力选择缓存参数。
4. 用量数据：缓存读写、可用性、异常与部分统计，从 Provider 一直保留到结算和调试输出。
5. 验证入口：离线结构测试、显式启用的真实缓存观察、人工同条件对比，不建立自动评分器。

## 2. 架构与依赖

```text
固定模块/空槽 ───────────────→ PromptAssembler ──→ stable_text
ToolContext + 当前模型/版本 ─→ EnvironmentCollector ─→ task snapshot
冻结模式 + 请求轮次 ────────→ ReminderPolicy ─────→ request reminders
                                           ↓
Conversation.messages() 副本 + PromptContext + 当前模式工具定义
                                           ↓
TurnRunner → StreamCollector → Provider 请求适配 + CachePolicy
                                           ↓
             HTTPX/SSE → UsageAccumulator → TokenUsage
                                           ↓
             Collector 快照合并 → request_id 单次结算
                                           ↓
               既有事件流 / UsageTotals / 手动调试入口
```

提示装配层不依赖 TUI、Conversation 或具体 Provider；环境层不读取供应商配置文件；Provider 不决定提醒节奏、不执行 Git。协议适配只消费已经构造好的上下文，不从用户文本或工具输出解析应用指令。

新增 `prompting/` 包，与现有 `prompts.py` 并存；后者作为兼容入口，不创建同名包覆盖模块。提示数据契约置于 `prompting/contracts.py`，只依赖标准库；用量契约继续放在 `models.py`。避免提示包反向导入 Runner 或 UI。

## 3. 核心数据结构与接口

以下是设计接口，审批阶段不编写实现文件。

### 3.1 提示契约

| 类型 | 字段 | 不变量 |
|---|---|---|
| `PromptModule` | `key: str`、`priority: int`、`content: str` | 冻结对象；key 唯一；正文不含运行时插值 |
| `EnvironmentSnapshot` | `project_root`、`platform`、`local_date`、`git`、`app_version`、`model` | 所有展示字段有限长；明确为任务开始快照；不可用有状态，不冒充空/干净 |
| `GitSummary` | `status`、`staged`、`unstaged`、`untracked`、`conflicted`、`truncated` | 计数可未知；状态包括 available/not_repository/unavailable/timeout；计数按路径条目，分类可重叠 |
| `RuntimeSupplement` | `kind`、`text`、私有 `origin` | 仅内置工厂创建；本章 kind 仅 plan；来源不从字符串标签推导 |
| `PromptContext` | `stable_text: str`、`environment_text: str`、`supplements: tuple[RuntimeSupplement, ...]` | 冻结；静态/动态明确分开；不持有 Conversation 或可变原生载荷 |

`assemble_modules(modules: Sequence[PromptModule]) -> str`：校验重复 key，稳定按 priority 升序排序，对各正文去除首尾空白，跳过空正文，以 `\n\n` 连接。相同优先级保留输入顺序，不对正文做依赖平台的换行转换。

`plan_reminder(mode: AgentMode, iteration: int) -> RuntimeSupplement | None`：普通模式返回 None；计划模式中 `(iteration - 1) % 4 == 0` 返回完整版，其余返回精简版；非法轮次为内部契约错误。

`build_prompt_context(stable_text, snapshot, *, mode, iteration, redactor) -> PromptContext`：渲染环境数据并生成本轮补充项，不读取或修改历史，不再次采集环境。

### 3.2 Provider 与 Collector 接口

保留现有参数，并增加可选的结构化上下文：

```python
Provider.stream_chat(
    messages: list[ChatMessage], *,
    tools: Sequence[ToolDefinition] = (),
    system_prompt: str = "",
    allow_tools: bool = True,
    prompt_context: PromptContext | None = None,
) -> AsyncIterator[ProviderEvent]

StreamCollector.collect(
    messages, *, tools, system_prompt, context, state, emit,
    prompt_context: PromptContext | None = None,
) -> RoundResponse | None
```

约定：

- Runner 的新链路传 `system_prompt=""` 与 `prompt_context`，保证只有一个权威系统来源。
- 无 `prompt_context` 时，原 `system_prompt` 单字符串调用行为继续可用，不隐式采集环境或添加提醒。
- 同时传非空 `system_prompt` 和 `prompt_context` 属于调用错误，明确拒绝，不能悄悄选择一方或重复拼接。
- Collector 仅在上下文不为空时传新关键字，保留原独立调用兼容；内部 FakeProvider/FakeCollector 的新链路签名同步适配。
- `TurnRunner(system_prompt=...)` 保留为稳定正文覆盖入口，环境和提醒仍走结构化动态通道；不把覆盖字符串理解为完整请求。
- 工具列表来自冻结模式下的 `definitions_for_mode`，不从提示词推断。

不引入参考材料中的整套 Request/Client 重写，也不新增公开的 `system` 消息到 `ChatMessage` 角色枚举。

### 3.3 缓存能力契约

`CachePolicy` 保存 `strategy`、`reason` 和规则版本，strategy 为：

- `anthropic_explicit`：官方 Anthropic 的稳定 system 块边界。
- `openai_explicit`：已核对的官方 Responses 模型，使用 developer 内容块显式边界。
- `prefix_only`：保留稳定前缀，不发送未经确认的缓存专用参数。

`select_cache_policy(config: ProviderConfig) -> CachePolicy` 为纯函数：读取协议、解析后的 URL 和模型，不试探网络、不读取密钥内容、不根据一次 400 自动降级重发。能力规则详见第 7 节。

### 3.4 用量契约

新增冻结的 `UsageCounter`：

| 字段 | 含义 |
|---|---|
| `value: int | None` | 最近可信非负整数；0 是真实上报的零，不等同 None |
| `availability: reported / missing / not_applicable` | 有实际字段、未提供、当前策略有文档依据不适用 |
| `invalid: bool` | 本请求该字段是否遇到坏类型、负数、倒退或相互冲突的统计；坏值不抹去之前的 value |

reported 必须有 value，其他 availability 不携带伪造零。出现坏值但从未见到可信值时为 missing + invalid；已有可信值则保留 reported/value 并标记 invalid。not_applicable 仅由明确适配规则设定；不能因为一包没有字段就认定服务不支持。后续收到合法真实字段时以真实值为准。

`TokenUsage` 保留现有四个字段及其位置，追加默认值字段：`cache_read: UsageCounter`、`cache_write: UsageCounter`、`uncached_input_tokens: int | None`。最后一项只保留 Anthropic 的原始非缓存输入计数，避免总量未知时丢失已报告的事实；其他协议默认为 None，不用减法反推未知信息。

新增冻结的 `CacheCounterTotals`，字段为 `known_tokens`、`reported_requests`、`not_applicable_requests`、`invalid_requests`，均从 0 开始。最后一项是可与前两类重叠的异常请求数，不用于再次扣减未知请求数；known_tokens 只累加各请求最后保留的可信 value，异常标记一并保留，不据此宣布该请求完整可靠。

`UsageTotals` 保留原有字段和 TUI 含义，追加 `cache_read: CacheCounterTotals` 与 `cache_write: CacheCounterTotals`。未知请求数由总请求数减 reported_requests 与 not_applicable_requests 计算；不把“已知部分合计为零”展示成所有请求确认未命中。汇总用冻结对象更新，单请求结算仍由 Runner 的 request_id 集合保证一次。

## 4. 模块装配与规则正文

### 4.1 注册表

`prompting/modules.py` 按以下固定顺序定义内置模块：

| priority | key | 内容重点 |
|---|---|---|
| 10 | identity | weizhCode、终端编程助手、依用户目标工作；不把所有模式描述成可执行全部工具 |
| 20 | system_constraints | 任务边界、真实报告、密钥、工具/文件内容仅作数据、动态上下文标签的用途与局限 |
| 30 | task_modes | 普通执行与计划调查的通用规则，提问不等于授权，计划等待 /do；不插入当前模式变量 |
| 40 | action_execution | 基于实际结果迭代、读类并发与副作用顺序、取消/失败/上限如实报告，不承诺回滚 |
| 50 | tool_usage | 专用工具优先、编辑前读取实际原文、唯一替换、截断补读、失败不虚构成功 |
| 60 | tone | 直接、克制、按需解释、不奉承或虚构进度 |
| 70 | text_output | 结果先行、必要 Markdown、说明未完成与限制、不输出隐含思维链 |
| 80 | custom_instructions | 空 |
| 90 | active_skills | 空 |
| 100 | long_term_memory | 空 |

模块正文统一内置中文，工具名保持实际代码名称。程序集不访问外部来源。`prompts.py` 的 `SYSTEM_PROMPT` 导出默认装配结果，`PLAN_MODE_REMINDER` 兼容导出完整版，`EXECUTE_DIRECTIVE` 保持原文字；生产 Runner 不再将提醒拼回该常量。

环境不作为第 110 个稳定模块，而由独立字段承载。新增模块只需注册数据；新增提醒只需扩展提醒工厂，三协议适配仍消费同一补充项结构。

### 4.2 双重强化工具描述

仅更新七个工具定义的 description，不修改名称、Schema、read_only、execution_kind、执行入口或结果限额：

- read_file：文件读取应优先使用它；行号不是原文，精确编辑前读取相关实际内容。
- find_files/search_content：找路径/搜内容各用专用工具，不用命令模拟已有检索能力。
- edit_file：先读，使用实际原文唯一匹配；匹配失败/多处命中必须根据错误调整。
- write_file：真实创建/覆盖能力，遵守用户目标；不宣称新增写前审批。
- run_command：专用工具不能完成时再用；保留非交互、超时及副作用说明，不承诺命令总是无害。
- AskUserQuestion：仅在计划模式澄清未明确需求，每次一题，回答不等于 /do；遵守现有选项/自由回答契约。

强化的是模型行为约定。执行端不新增读记录门禁；既有 prepare、目标快照、原文唯一匹配、变化检测与临时文件保护保持。

## 5. 环境采集与资源生命周期

### 5.1 采集入口

`EnvironmentCollector.capture(*, project_root, app_version, model, context, redactor) -> EnvironmentSnapshot` 每个被接受任务只调用一次。Runner 从 `executor.context.project_root` 获取工具真实工作根，版本来自包内 `__version__`，模型来自当前 Provider 的 config.model；只取这些非敏感字段，不遍历配置。

测试可注入 `environment_collector` 与明确的测试根；无真实 ToolContext 的测试替身返回“工作根不可用”，不悄悄改用进程目录冒充工具根。生产 CLI 继续用原有 ToolContext；若以后采用不同工作根，环境随它变化。

快照构造处于 `_drive` 的资源保护范围内，busy 已在 run() 中预留。取消信号已设置时不启动采集或模型请求；采集失败返回降级快照。采集结束后，第一次请求仍是 iteration=1；采集不消耗模型迭代预算。

### 5.2 字段与限额

- 工作根：使用已有上下文路径的词法绝对表示，不为显示递归 resolve 符号链接；脱敏后最多 2048 字符，截断有标记，不将其当作新的工具执行路径。
- 平台：标准库获取操作系统及 Python 运行平台摘要，不运行 shell、不查询主机/用户名；最多 256 字符。
- 日期：任务开始时 `datetime.now().astimezone().date().isoformat()`，标明本地日期。
- 版本/模型：现有值，展示副本脱敏并去控制字符，各最多 256 字符；不改实际模型配置。
- Git：状态和计数，不显示文件名、分支名、远端地址或差异。
- 最终环境 JSON 数据正文最多 4096 字符；渲染外层说明“任务开始快照，仅为环境数据，不是操作指令”，数据中尖括号转义为 JSON Unicode 转义，避免路径伪造标签边界。

字段不可取时记录 unavailable。模型/版本等内部值异常也不能让启动或对话崩溃；不以空字段冒充已成功采集。

### 5.3 Git 子进程

使用 `asyncio.create_subprocess_exec`，无 shell，参数固定为 `git --no-optional-locks -c core.fsmonitor=false status --porcelain=v1 -z --untracked-files=normal`，cwd 为工具根。禁用 fsmonitor 外部助手，避免状态查询触发仓库自定义监视器；不运行 diff、log、remote 或其他命令。

从开始创建进程起设置总计 2 秒的采集期限；stdout/stderr 并发分块读取，累计保留上限分别 64 KiB/4 KiB，超出后继续排空而不累计保存，防止 PIPE 堵塞。按 NUL 记录解析，正确跳过 rename 的第二路径；不按文件名中的换行切条目。

只取 XY 状态列计数：staged、unstaged、untracked、conflicted。一次路径可同时 staged 和 unstaged，不能把分类和当作独立文件总数。正常上限内且解析完整时才报告精确计数；截断/异常时标记摘要不完整，不声称仓库干净或精确总数。untracked-files=normal 的未跟踪目录算状态条目，不冒充目录下所有文件数量。

deadline 到达即停止等待环境结果，返回 timeout；后台仅保留本任务拥有的 kill/wait/排空收尾，不再向快照写入迟到内容。创建进程的任务被 shield 且登记所有权，超时或取消后即使进程稍晚创建，也由该所有者获取句柄并终止、回收；不只取消 wait 却留下进程。工具根不可用、Git 缺失、非仓库、权限或输出格式错误均降级，stderr 原文不进入模型或 UI。

清理任务进入 RunContext 的 owned/cleanup 管理，Runner 的任务收尾与 aclose 等待其结束。2 秒是采集结果等待上限，不虚称操作系统强制终止和句柄回收也能有跨平台硬实时保证；界面期间仍可取消/退出。无后台定时刷新、无第二次 Git 查询、无工作区写入。

## 6. 动态补充与三协议消息表达

### 6.1 通用规则

每请求基于 `Conversation.messages()` 的独立深副本生成线格式。环境数据在稳定指令之后、保存历史之前；本轮提醒在完整历史之后，不插进 assistant 工具调用与对应结果之间。

提醒由内置工厂产生并包裹为 `<system-reminder>…</system-reminder>`，origin 不从文本提取，也不发送为服务端新权限字段。用户/文件/工具里出现同标签仍只是原来源的数据，程序不扫描、提升或移除它们。静态模块解释提醒无需单独回答；不能承诺模型不会受伪造标签干扰。

三种协议均不往 Conversation 添加提醒或环境消息。原始 tool 参数、问答答案、thinking/signature/encrypted 载荷不经字符串拼接来装提醒；仅使用现有适配器的深副本回放路径。

### 6.2 Anthropic Messages

- 有结构化上下文时，body.system 改为 text block 列表：第一块 stable_text；第二块 environment_text（非空才添加）。
- 仅在 `anthropic_explicit` 策略下，第一块带 `cache_control: {"type": "ephemeral"}`；环境块不带标记。不启用顶层 automatic cache_control，也不给历史标记。
- 先走现有 `_messages_payload` 形成合法工具结果与原生回放。若末尾为 user，在其内容块列表尾追加提醒 text 块；若末尾不是 user，则追加一个应用补充用 user text 消息，不伪造真实用户回答。
- 工具结果块必须完整在前；不重排工具 id，不触碰 thinking/signature 块。不以通用角色交替规则重写历史，保留现有合法相邻角色处理。
- prefix_only 的兼容服务仍使用标准 system 文本块，不带任何缓存专用字段；没有结构化上下文的旧调用继续原字符串形态。

### 6.3 OpenAI Responses

- `openai_explicit`：不再同时发送相同的 instructions。input 第一项为 developer 消息，content 内一个 input_text 放 stable_text，并设置 `prompt_cache_breakpoint: {"mode": "explicit"}`；顶层设置 `prompt_cache_options: {"mode": "explicit"}`。
- 该策略的环境作为随后独立的 developer input_text 消息，以明确的数据外壳承载；没有 breakpoint。随后追加现有 `_input_payload` 的历史项。
- `prefix_only`：stable_text 仍用既有 instructions 字符串；环境以一条应用上下文 user input_text 消息放在 input 历史之前，避免要求未知兼容服务支持新的 developer/cache 扩展；稳定正文解释其不是待回答的问题。
- 两种策略都在全部历史项之后添加本轮提醒 user input_text 项，不插到 function_call 与 function_call_output 中间。此项仅在请求副本存在，不是 conversation 新任务。
- store=False、reasoning.encrypted_content 包含/回放、工具 Schema、strict=False、parallel_tool_calls、原始 output items 验证及完整结束门槛维持现状。

当前官方显式缓存文档要求把可标记的指令放进 developer 内容块，顶层 instructions 无法承载该 breakpoint。本设计据此区分显式与旧格式，而不是把新参数强塞进 instructions。[OpenAI 缓存说明](https://developers.openai.com/api/docs/guides/prompt-caching)

### 6.4 千问兼容 Chat Completions

- 保留第一条 system 消息仅放 stable_text，不把环境/计划提醒拼入其中。
- system 之后加独立的应用环境 user 数据消息，再接现有 `_messages_payload` 历史；该消息不要求模型回答，内容外壳与其他协议相同。
- 历史的全部 role=tool 结果之后才加本轮提醒 user 消息。允许合法相邻 user，不为“交替”伪造 assistant 回复。
- 本章采用不增加请求字段的稳定前缀策略，不引入千问显式缓存专用参数；保留 stream_options.include_usage 和空 choices 用量末包处理。

选择消息通道而不是给所有兼容服务加第二条 system，是为了不扩大对兼容端点的系统角色格式假设。它只是传递应用补充数据的方式，不表示给字符串创建了系统权限。

## 7. 缓存能力、稳定性与错误策略

### 7.1 保守能力表

仅 HTTPS、标准端口、无 userinfo、规范 API 根路径的已知官方端点可启用显式扩展；URL 用 urlsplit 后按 hostname 精确比较，不能用子串或 endswith 放行伪装主机。

| 协议/端点条件 | 模型条件 | 本章策略 |
|---|---|---|
| anthropic，api.anthropic.com，根路径 /v1 | Claude 模型标识（claude- 前缀） | anthropic_explicit；官方支持范围为活动 Claude 模型，已退役/无权限模型仍由服务报告错误 |
| openai，api.openai.com，根路径 /v1 | 内置精确 allowlist：gpt-5.6、gpt-6.1-sol、gpt-6.1-terra | openai_explicit |
| openai 官方端点的其他模型/快照/别名 | 未纳入上述精确表 | prefix_only，不推断数字更大就支持 |
| qwen 的现有端点 | 任意配置模型 | prefix_only，观察服务实际上报的缓存用量 |
| 任意其他兼容端点，包括 DeepSeek、网关及本地端点 | 任意 | prefix_only，不套用官方扩展 |

OpenAI 的表是本章保守启用名单，不是“只有这几个模型有缓存”的声明。表内标识依据当前官方文档核对；未来增加精确模型/快照需局部更新能力规则及测试，不自动联网拉模型表，不新增 YAML 字段，不将用户切换到这些模型。未知模型保留正常请求，是否隐式命中以实际字段为准。

Anthropic 标记仅选稳定 system 块末端，服务的前缀次序为 tools → system → messages，因此可覆盖前置工具定义。活动模型支持、长度与有效期约束由服务决定，不因本地选中策略就认为创建成功。[Anthropic 缓存说明](https://platform.claude.com/docs/en/build-with-claude/prompt-caching)

千问当前文档区分显式/隐式缓存及模型/地域支持；本章只采用无额外参数的前缀策略，读取兼容响应的实际命中字段，不把 HTTP 原生 DashScope 字段混入兼容 Chat Completions。[千问上下文缓存](https://help.aliyun.com/zh/model-studio/context-cache)

### 7.2 稳定序列化

工具注册顺序及模式过滤顺序保持既有实现；Schema/描述拷贝后按固定结构转协议，禁止集合决定输出顺序。Provider 的请求构造函数可单独测试，在线请求也使用同一构造结果，不能另写一个只供测试的近似序列化器。

调试的 stable_prefix_digest 用 SHA-256，对实际稳定线格式投影做固定 JSON 序列化：规范化的服务端点作用域（scheme/host/port/API路径，不含 userinfo/query/fragment）、协议/模型/能力策略与规则版本、稳定系统块、当前有序工具定义以及会影响前缀的既有工具/模型设置。鉴权头、API key、环境、历史、轮次、run_id/request_id 不进入投影。

投影序列化采用 UTF-8、ensure_ascii=False、固定分隔符和键排序；列表不排序。digest 是应用前缀的一致性证据，不是服务缓存 key，也不能证明服务隐藏上下文相同或实际命中。测试同时检查实际构造的稳定块与有序工具定义字节，不仅比较 digest。

normal 六个 worker 工具，plan 三读类加 AskUserQuestion，切换后允许 digest 改变。系统模块本身不因模式改变；禁止通过暴露全七工具、allowed_tools 新机制或取消执行门禁追求命中。

### 7.3 不支持或失败时

- 未知能力在发请求前选 prefix_only，reason 为明确的端点/模型未确认原因；不称为“确认不支持缓存”。
- 选中显式策略后若服务返回参数、模型、权限、网络或流错误，沿用 provider_error 路径，明确本次失败，不静默删参数重试、不换模型/协议。
- prefix_only 没有命中/没有字段不算功能崩溃，也不算缓存验收通过。
- 不增加缓存预热请求、TTL 字段、缓存长度填充、后台收费实验或动态历史边界。
- 默认 TTL 交给对应 API 的默认行为，不跨服务写死同一个时长。缓存写入也可能收费，不保证本章必然省钱或更快。

## 8. 缓存统计解析与合并

### 8.1 字段映射及输入总量

| 协议 | 输入/输出基础字段 | 缓存读 | 缓存写 | 总输入口径 |
|---|---|---|---|---|
| Anthropic | input_tokens / output_tokens | cache_read_input_tokens | cache_creation_input_tokens | 非缓存 input + read + write；三项可信时才得到精确总量 |
| OpenAI Responses | input_tokens / output_tokens | input_tokens_details.cached_tokens | input_tokens_details.cache_write_tokens（服务有返回才确认） | input_tokens 已包含缓存子项，不再相加 |
| 千问兼容 Chat Completions | prompt_tokens / completion_tokens | prompt_tokens_details.cached_tokens | 本章不主动创建显式缓存；缺失仍为未提供，不硬置 0 | prompt_tokens 已包含缓存读，不再相加 |

OpenAI 的写入字段不是所有模型都有；仅在精确的旧模型适配有官方“不适用”证据时才能标 not_applicable，本章默认缺失为 missing。未知兼容服务返回字段时按对应协议的已知路径校验，不自行尝试其他协议路径或从 total_tokens 反算。

Anthropic 的原始 input_tokens 单独保存在 uncached_input_tokens。若缓存字段未提供，总输入仍未知；显示已知非缓存输入和分项，不能以之前补零的方法伪装完整。message_delta 省略先前字段时保留已有值，不回退到未知。

只接收 type(value) is int 且非负；布尔值不算整数。details 不是对象、指定键坏值、累计数倒退均标记对应 invalid，保留最近可信值。不能让缓存字段的异常覆盖 OpenAI/千问已经可信的基础输入计数；overall complete 可以因此为 False。

对于明确已包含子项的协议，若同一完整快照显示缓存读/写超过输入总量，或两项之和在服务文档定义为互斥分类时超过总量，标记统计冲突、不将异常分项计作可靠命中。只在完整可比快照检查，不拿前一包输入与后一包缓存瞬时比较制造误报。

### 8.2 三层去重

1. Provider 的 UsageAccumulator 对同一请求只覆盖累计快照，不累加 message_start/message_delta/完成包；无字段不清零；非法值的标记在请求内保持。
2. Collector 合并所有 TokenUsage 字段，不能继续用只传 input/output/source 的构造丢掉缓存。公共 `merge_usage_snapshot(previous, current)` 按字段保留可信值及异常状态，既防 Provider 坏快照，也支持测试替身；完成状态需完整流与统计检查同时满足。
3. Runner 仍按本地 StreamState.request_id 只结算一次；usage 事件重复、收尾与 done 交错不会重复加总。新任务、新模型请求各有新 id。

complete 继续描述本请求输入/输出统计：完整流结束、两项总量已知且无统计异常才为 True；单纯缓存子项 missing 不让 OpenAI/千问的已知基础总量变成未知。缓存分项是否提供仍单独看 availability；Anthropic 缺失子项导致总输入未知时 complete=False。

流失败/取消时保留已收到的值，并令 complete=False；未实际开始的模型请求不虚增请求数。没有任何统计的已发请求可以记录缺失与不完整，不能伪造零用量。AskUserQuestion 等待不结算一个额外模型请求。

### 8.3 调试输出边界

现有 usage 事件携带扩展的 TokenUsage/UsageTotals，不新增 TUI 缓存行。调试入口消费同一真实事件或 Provider 结果，输出结构化 JSON：服务 host（不含认证/URL 查询）、协议、模型、模式、策略与原因、规则版本、前缀 digest、本地请求 id/轮次、基础用量、读写值/availability/invalid、complete 及停止原因。

默认不输出完整 system、环境路径、历史、工具正文或原始响应/异常对象；确有必要观察样本时只展示临时非敏感样本的受限摘要。所有输出经过既有 redactor/display；不解析非激活配置的环境密钥、不改变实际参数、答案或原生回放数据。

## 9. 任务级与请求级执行顺序

### 9.1 新用户任务

1. run() 按现有机制检查并预留 busy，冻结模式，创建 RunContext 与事件流。
2. 私有 _drive 在 try/finally 内保存用户输入、处理取消并采集一次环境；采集失败降级。
3. 从默认模块或显式覆盖获得 stable_text，按冻结模式取得本任务工具定义副本。
4. 每轮先检查 cancel，再建立 StreamState/iteration；生成该轮 PromptContext。
5. Collector 将历史副本、工具及上下文交 Provider；Provider 选择能力策略、构造请求、持续处理 SSE。
6. 完整流且响应合法才进入原有工具调度；结果按原有原子配对路径写回历史。下一轮复用本任务环境，只更新提醒。
7. 无工具完成、上限、连续未知工具、取消或错误均沿用原有停止路径；结算真实用量并收尾所有拥有的资源。

环境采集不额外向模型发请求；未来新用户任务刷新环境。同任务工具改变文件后，不回写快照或暗中重新运行 Git。

### 9.2 计划与提问

第 1/5/9/13/17/21/25 请求使用完整计划提醒，其余精简。完整版包含三读类工具、AskUserQuestion、只读调查、每次一题、确认/假设区分与等待 /do；精简版明确只读、可以澄清、禁止写/改/命令、等待 /do。

QuestionBroker 等待用户时不增加 iteration，不刷新环境、不增加缓存请求。用户回答作为真实工具结果完成既有交换后，下一次请求正常加一并按该轮提醒；取消问题或断开 UI 按现有生命周期终止，不制造假答案。

/plan 只切模式，无模型请求；/do 在任务空闲时切 normal 并使用原有 EXECUTE_DIRECTIVE 启动新任务，新采集环境，不再带计划提醒。已有用户明确的条件不得因为提醒精简而被代码丢弃；保持完整 Conversation。

## 10. 文件组织与修改边界

以下均以 `D:/STUDY/weizhcode-python/` 为根，属于未来实现清单，本次不创建实现文件。

| 操作 | 文件 | 职责 |
|---|---|---|
| 新增 | src/weizhcode/prompting/__init__.py | 提示构造公共导出 |
| 新增 | src/weizhcode/prompting/contracts.py | 模块、环境、补充项、PromptContext 冻结契约 |
| 新增 | src/weizhcode/prompting/modules.py | 七固定模块、三个空槽、稳定装配 |
| 新增 | src/weizhcode/prompting/environment.py | 有界环境/Git采集、取消和子进程收尾 |
| 新增 | src/weizhcode/prompting/reminders.py | 本应用来源与 full/brief 节奏 |
| 新增 | src/weizhcode/prompting/builder.py | 快照安全渲染、每请求上下文构造 |
| 新增 | src/weizhcode/providers/prompt_adapter.py | 三协议纯请求构造辅助、动态项注入、稳定投影 |
| 新增 | src/weizhcode/providers/cache_policy.py | 精确端点/模型能力选择及规则版本 |
| 修改 | src/weizhcode/prompts.py | 兼容常量导出，保留执行指令 |
| 修改 | src/weizhcode/models.py | 缓存计数及汇总契约，保留原字段兼容 |
| 修改 | src/weizhcode/providers/base.py | Provider 协议、UsageAccumulator、统一快照合并 |
| 修改 | src/weizhcode/providers/anthropic.py | 结构化系统块、提醒注入、统计 |
| 修改 | src/weizhcode/providers/openai.py | Responses 显式/前缀两路、原生项回放保持 |
| 修改 | src/weizhcode/providers/qwen.py | 独立动态消息、嵌套缓存统计、空候选末包保持 |
| 修改 | src/weizhcode/stream_collector.py | 传递上下文、完整字段合并与部分统计 |
| 修改 | src/weizhcode/turn_runner.py | 任务快照、每请求提醒、生命周期及结算 |
| 修改 | src/weizhcode/tools/read_file.py、write_file.py、edit_file.py | 仅 definition.description |
| 修改 | src/weizhcode/tools/find_files.py、search_content.py、run_command.py、ask_user_question.py | 仅 definition.description |
| 新增 | tests/test_prompting.py | 模块、空槽、数据契约、提醒、渲染与来源 |
| 新增 | tests/test_environment.py | 真实/替身子进程、期限、输出限额、降级与取消竞争 |
| 新增 | tests/test_prompt_protocols.py | 三协议捕获请求、稳定字节、配对/原生载荷、能力矩阵 |
| 新增 | tests/test_cache_usage.py | 读写/缺失/异常/累计/部分/汇总矩阵 |
| 修改 | tests/test_stream_collector.py、test_turn_runner.py、test_user_questions.py | 新参数、任务/轮次、等待、取消、单次结算 |
| 修改 | tests/test_provider_events.py、test_provider_tools.py、test_protocol_integration.py | 新请求结构与用量回归，安全断言保留 |
| 修改 | tests/test_tool_registry.py、test_tui.py | 描述变化、模式工具集与状态栏不增缓存字段 |
| 新增 | tests/manual_prompt_smoke.py | 默认离线预览；显式 live 的缓存/人工对比入口 |
| 新增 | tests/fixtures/prompt_baseline.json | 本章改动前的非敏感提示与工具描述基线，不含配置/历史 |
| 修改 | README.md | 提示结构、已支持缓存策略、调试入口与限制 |
| 后续文档阶段新增 | specs/system-prompt-engineering/checklist.md | 独立审批后才执行并记录本章实际证据，不预填通过 |

不改变 pyproject.toml/uv.lock 的依赖或 Python 最低版本；验证锁文件不等于需要更新它。CLI/TUI 生产启动方式、配置解析与 Conversation 持久结构不需要改造。若测试替身的签名位于其他既有测试中，仅机械适配新可选参数，不削减原行为断言。

不修改其他阶段四份文档；不读取、覆盖或提交用户的 `.weizhcode-test/` 手工验收数据。

## 11. 关键技术决策

| 决策 | 选择与理由 |
|---|---|
| 装配与传输分层 | 提示包只产出确定性内容；Provider 决定合法线格式，避免每协议复制行为规则 |
| 兼容原接口 | 可选 PromptContext，不重写整套 Request API；旧单字符串调用继续运行 |
| 环境粒度 | 每被接受任务一次，既减少 Git 开销，又不宣称工具执行后仍实时准确 |
| 环境来源 | ToolContext 的实际根，不以 TUI 显示或进程 cwd 替代 |
| 提醒来源 | 内置工厂+私有元数据，不依据文本标签授予信任；标签不是防注入安全机制 |
| 消息插入 | 在协议副本中追加到完整结果之后，不污染保存历史、不伪造工具和答案 |
| 能力探测 | 纯本地保守规则，不发送探测请求、不解析一次错误后暗中重试 |
| OpenAI 分路 | 已确认模型用 explicit developer 块，其他保持前缀，不将 Chat Completions 字段套入 Responses |
| 千问/兼容服务 | 无额外缓存参数的稳定前缀，真实字段才算证据，不用官方 Anthropic 成功代替 DeepSeek |
| 用量完整性 | value、availability、invalid 分离，宁可总量未知也不把缺失猜为 0 |
| 汇总 | 每请求累计覆盖、每 id 单次结算；缓存是输入分类，不是额外再加一遍的 Token |
| 规则强化 | 系统与描述双处约定，不顺带新增权限、编辑门禁或沙箱 |
| 验证 | 结构正确、真实命中、真实终端和人工行为分别记录，缺条件保留待验 |

## 12. 需求归属与验收设计

### 12.1 覆盖映射

| Spec | 设计归属 | 主要验证 |
|---|---|---|
| F1、F2；AC1、AC2 | 第3/4节模块与空槽 | 顺序、并列保序、空内容、新模块注册，无外部来源读取 |
| F3；AC3、AC4 | 第5/9节环境快照 | 实际根、新任务刷新、一次采集、非仓库/失败/超时/取消/退出/输出限额 |
| F4；AC5、AC6 | 第6/7节线格式与投影 | 同工具集稳定块字节相等；环境/提醒变化不改静态；模式精确过滤 |
| F5；AC7、AC8 | 第7节能力表、显式边界 | 捕获实际请求；未知端点不带扩展；真实条件下观察命中，其他待验 |
| F6；AC9 | 第4.2节双重强化 | 系统/描述规则一致，Schema与执行保护不变；人工工具选择和先读再改 |
| F7；AC10、AC11 | 第3/6节来源与请求副本 | 伪造标签不触发应用注入；历史深相等；工具配对/签名/加密载荷不变 |
| F8；AC12 | 第4/9节提醒策略 | 1/5/9等完整、其他精简、任务重置、问题等待不计轮、/do无提醒 |
| F9；AC13、AC14 | 第3.4/8节统计 | 零/正数/缺失/不适用/异常、重复/倒退、取消/失败、单次结算、UI不扩张 |
| F10；AC8、AC14、AC15 | 第12.2/12.3节手动入口 | 默认零请求、显式live、同前缀重复、人工受控对比与限制记录 |
| F11；AC16 | 第6/9节与既有完整门槛 | 三协议回放、Loop、问答、取消/恢复、并发/顺序与25轮上限回归 |
| N1、N2 | 第3/5/7节 | 确定性、局部挂载、子进程期限/排空/竞争清理与响应性 |
| N3、N4；AC17 | 第5/6/8节 | 密钥/控制字符、环境数据转义、实际参数与答案/原生载荷未被改写 |
| N5、N8 | 第7/8节 | 统计缺失诚实、输入口径、不把格式/digest或低延迟当命中/费用证明 |
| N6、N7；AC18 | 第10/12节 | 既有依赖锁、编译、全量测试及平台/线上/终端证据分层 |

### 12.2 离线验证矩阵

- 使用可注入 stream_func 捕获真实 Provider 构造的 body，不发 HTTP。矩阵覆盖 normal/plan、官方已确认模型/未知模型/兼容端点、环境变化、完整/精简提醒、空环境和旧字符串调用。
- Anthropic 用包含 tool_use/tool_result/thinking/signature 的历史；Responses 用 function_call/function_call_output/reasoning.encrypted_content；千问用 assistant.tool_calls 和全部 tool 消息。注入前后保存历史深相等，回放载荷逐项保留。
- 对用户/路径/文件/工具中伪造的提醒标签验证“不被应用识别为私有补充项”；不将模型遵守程度误写成可单测证明的权限。
- 统计分别覆盖真实零、正数、缺失details/子字段、None、字符串、布尔、负数、倒退、重复快照、部分后错误/取消、末包空choices、缺失后补齐。示例：Anthropic 100+20+30=150；Responses 输入150/读30/写20仍为150；千问输入150/读30仍为150。
- 环境测试包含 Git 带换行/重命名路径、超长输出、未跟踪目录条目、非仓库、命令缺失、cwd错误、权限异常、创建进程和取消竞争；真实平台能力不足必须说明，不以替身测试冒充系统进程已验证。
- 运行既有问答、工具、命令进程、红线/脱敏、预算、并发顺序与恢复测试。仅迁移本章取代的系统字符串/请求形态断言，不删除安全用例。

实现后预定验证命令为 `uv lock --check`、`uv run python -m compileall -q src`、`uv run pytest -v`；不新增未配置的 Ruff/mypy。真实 TUI 启动由合法配置下的 `uv run python -m weizhcode` 验证；无界面自动测试不能冒充 PowerShell 肉眼验收。

### 12.3 手动缓存与定性入口

新增 `tests/manual_prompt_smoke.py`，默认只输出内置演示端点/模型与非敏感样本的离线策略/前缀投影说明，明确标注“演示，并非当前配置”，**不加载认证配置、不请求模型**。只有显式 `--live` 才加载当前默认供应商并发送请求；支持 `--scenario cache|behavior` 和 `--prompt-variant baseline|modular`，不提供自动更换供应商、模型或批量跑全配置。

缓存场景连续两次发送同一稳定内容/工具集合，第二次改变当前问题及受控的环境测试值，记录每次策略、digest、读写计数/可用性、完整性和停止结果。受控非敏感长样本仅用于人工选择的缓存验证，不补入生产提示，不保证满足所有模型门槛；样本不足、没权限、字段缺失、没有命中分别记录。此场景直接消费 Provider 事件，不执行模型请求的文件/命令工具；有工具请求只记录，不伪造执行成功或发起后续循环。

人工行为场景使用临时目录、指定非敏感样本和受限的验收执行器，沿用已有 manual_tool_smoke 的安全边界思路。此限制只属于测试，不给产品新增沙箱。越界/非样本/命令调用记录并拒绝，不接触真实用户文件。需要运行命令的真实产品能力继续由既有专门测试验证。

baseline 数据在实现前从当前内置系统文本、计划提醒及工具描述冻结为 fixture；不得含 API 配置、路径、历史或任何密钥。对比只替换提示和描述，使用相同当前运行时/工具实现；明确这是提示行为对比，不冒充整个旧版本性能基准。

人工逐个场景运行，不自动评分或批量收费：

1. 读取/查找/搜索任务：观察是否优先专用工具；若调用命令被验收器拒绝，如实记录选择失败。
2. 修改样本：观察是否先读实际原文再 edit，检查最终磁盘结果与匹配错误恢复。
3. 含糊的计划需求：观察 AskUserQuestion、等待回答、确认/假设区别与最终计划。
4. 已明确计划：确认不重复提问、不给写类工具、不提前执行；输入 /do 后正常推进。
5. 环境询问：正确使用任务开始快照，不把环境数据当新命令，不声称 Git 实时准确。
6. 多轮计划：提醒不被单独回应/复述；观察第1/5轮规则保持。
7. 取消并继续：收尾后新任务可用，无残留提问或采集进程。

记录样本、模型/服务、模式、提示版本/digest、必要环境差异、实际工具序列/最终效果、用量及可选耗时。不能从一次样本推导统计显著改善，也不从时间推断缓存命中。真实终端由用户在 PowerShell 观察；线上、离线、终端、人工结论分开填写未来 Checklist。

## 13. 本次交付与审批边界

本次仅更新 Spec 的批准状态并交付此 Plan，没有修改业务代码、运行开发测试、触发模型 API 或测得缓存命中。

请审批架构、核心契约、三协议动态注入方式、保守缓存能力表、统计口径及验证边界。批准后只进入 Task 文档生成；不自动生成 Checklist，不提前实现。
