# weizhCode 系统提示工程化 Tasks

> 依据：Spec、Plan、Task、Checklist 均已获用户明确批准，开始实现；进度与证据见文末，未验证不标完成。
> 本次只生成 Task 并更新 Plan 批准状态；Task 批准后单独生成 Checklist。四份文档全部批准后才允许实现、运行开发测试和验收。
> 不迁移 SDK，不增加依赖、配置字段、工具权限系统、自动评分或 TUI 缓存状态栏；不自动切换模型/供应商或发起收费验证。

## 1. 路径、执行与证据约定

项目根为 `D:/STUDY/weizhcode-python/`。下列文件清单给出完整路径；各任务引用清单编号以避免重复长路径，编号精确指向文件，不代表目录通配或允许顺带修改其他文件。

每项是聚焦工作单元，按列出的步骤逐步验证；复杂任务分成可独立核对的小步骤，不把预计耗时当实际耗时或完成证据。所有验证命令均为**未来实现阶段执行**，本次仅文档检查，不运行这些命令。

- 在项目根运行验证。测试文件尚未创建时不得把未运行写成通过；新测试的名称/参数 id 应包含任务列出的 `-k` 关键词。
- 每项完成须记录实际命令、退出结果、失败/跳过与原因。自动结构测试、原生进程、无界面真实 API、真实终端、人工定性结论分开。
- 实现时按逻辑组在定向验证通过后本地提交，只暂存本章文件；不自动推送 GitHub，不提交用户手工数据或密钥配置。
- 用户的 `.weizhcode-test/`、其他章节文档、忽略的供应商配置和已有无关改动全部保留，不读取原始密钥来做文档或测试样本。
- 若实现需要改变已批准的范围、接口或缓存策略，停止相应任务，先说明差异并重新审批相关文档，不以实现细节名义扩大范围。

## 2. 文件清单

### 2.1 生产代码

| 编号 | 操作 | 完整路径 | 职责 |
|---|---|---|---|
| P01 | 新增 | D:/STUDY/weizhcode-python/src/weizhcode/prompting/__init__.py | 公共导出 |
| P02 | 新增 | D:/STUDY/weizhcode-python/src/weizhcode/prompting/contracts.py | 冻结提示/环境/补充项契约 |
| P03 | 新增 | D:/STUDY/weizhcode-python/src/weizhcode/prompting/modules.py | 七模块、空槽与确定性装配 |
| P04 | 新增 | D:/STUDY/weizhcode-python/src/weizhcode/prompting/environment.py | 环境与 Git 有界异步采集、清理 |
| P05 | 新增 | D:/STUDY/weizhcode-python/src/weizhcode/prompting/reminders.py | 来源工厂、完整/精简节奏 |
| P06 | 新增 | D:/STUDY/weizhcode-python/src/weizhcode/prompting/builder.py | 环境安全渲染与 PromptContext 构造 |
| P07 | 新增 | D:/STUDY/weizhcode-python/src/weizhcode/providers/prompt_adapter.py | 协议线格式与稳定投影 |
| P08 | 新增 | D:/STUDY/weizhcode-python/src/weizhcode/providers/cache_policy.py | 保守能力表与原因 |
| P09 | 修改 | D:/STUDY/weizhcode-python/src/weizhcode/prompts.py | 兼容常量、保留 EXECUTE_DIRECTIVE |
| P10 | 修改 | D:/STUDY/weizhcode-python/src/weizhcode/models.py | UsageCounter/CacheCounterTotals 与兼容扩展 |
| P11 | 修改 | D:/STUDY/weizhcode-python/src/weizhcode/providers/base.py | Provider 接口、累计/合并统计 |
| P12 | 修改 | D:/STUDY/weizhcode-python/src/weizhcode/providers/anthropic.py | Messages 注入与缓存统计 |
| P13 | 修改 | D:/STUDY/weizhcode-python/src/weizhcode/providers/openai.py | Responses 显式/前缀两路 |
| P14 | 修改 | D:/STUDY/weizhcode-python/src/weizhcode/providers/qwen.py | 兼容 Chat Completions 动态消息/统计 |
| P15 | 修改 | D:/STUDY/weizhcode-python/src/weizhcode/stream_collector.py | 上下文透传、全字段快照合并 |
| P16 | 修改 | D:/STUDY/weizhcode-python/src/weizhcode/turn_runner.py | 任务快照、请求提醒、结算/收尾 |
| P17 | 修改 | D:/STUDY/weizhcode-python/src/weizhcode/tools/read_file.py | 仅工具描述 |
| P18 | 修改 | D:/STUDY/weizhcode-python/src/weizhcode/tools/write_file.py | 仅工具描述 |
| P19 | 修改 | D:/STUDY/weizhcode-python/src/weizhcode/tools/edit_file.py | 仅工具描述 |
| P20 | 修改 | D:/STUDY/weizhcode-python/src/weizhcode/tools/find_files.py | 仅工具描述 |
| P21 | 修改 | D:/STUDY/weizhcode-python/src/weizhcode/tools/search_content.py | 仅工具描述 |
| P22 | 修改 | D:/STUDY/weizhcode-python/src/weizhcode/tools/run_command.py | 仅工具描述 |
| P23 | 修改 | D:/STUDY/weizhcode-python/src/weizhcode/tools/ask_user_question.py | 仅工具描述 |

### 2.2 测试、验证入口与说明

| 编号 | 操作 | 完整路径 | 职责 |
|---|---|---|---|
| V01 | 新增 | D:/STUDY/weizhcode-python/tests/test_prompting.py | 装配、契约、提醒、渲染/来源 |
| V02 | 新增 | D:/STUDY/weizhcode-python/tests/test_environment.py | Git 解析、期限、降级、竞争/原生清理 |
| V03 | 新增 | D:/STUDY/weizhcode-python/tests/test_prompt_protocols.py | 捕获实际请求、缓存能力、字节与原生回放 |
| V04 | 新增 | D:/STUDY/weizhcode-python/tests/test_cache_usage.py | 缓存契约、累计、合并与汇总 |
| V05 | 修改 | D:/STUDY/weizhcode-python/tests/test_stream_collector.py | 透传、统计、取消与关闭 |
| V06 | 修改 | D:/STUDY/weizhcode-python/tests/test_turn_runner.py | 快照、节奏、任务恢复、单次结算 |
| V07 | 修改 | D:/STUDY/weizhcode-python/tests/test_user_questions.py | 等待/回答/取消与计划提醒 |
| V08 | 修改 | D:/STUDY/weizhcode-python/tests/test_provider_events.py | 流事件/统计回归 |
| V09 | 修改 | D:/STUDY/weizhcode-python/tests/test_provider_tools.py | 工具请求与原生回放回归 |
| V10 | 修改 | D:/STUDY/weizhcode-python/tests/test_protocol_integration.py | 三协议 Loop 集成 |
| V11 | 修改 | D:/STUDY/weizhcode-python/tests/test_tool_registry.py | 描述与精确模式工具集 |
| V12 | 修改 | D:/STUDY/weizhcode-python/tests/test_tui.py | UI 响应与不新增缓存栏 |
| V13 | 新增 | D:/STUDY/weizhcode-python/tests/manual_prompt_smoke.py | 默认离线、显式 live 缓存/行为观察 |
| V14 | 新增 | D:/STUDY/weizhcode-python/tests/fixtures/prompt_baseline.json | 修改前内置提示/描述的非敏感基线 |
| D01 | 修改 | D:/STUDY/weizhcode-python/README.md | 提示结构、验证入口与限制 |
| D02 | 后续独立生成 | D:/STUDY/weizhcode-python/specs/system-prompt-engineering/checklist.md | 待审批的行为验收及未来实际证据 |

本章无需改动启动、配置解析、Conversation 持久结构、依赖与锁文件。测试替身若在其他测试文件中使用精确旧签名，仅在必要时机械适配新可选参数并记录原因，不删减原断言。

## 3. 任务清单

### T01：保存改动前基线

**文件：** V14、V01；只读 P09、P17～P23。
**依赖：** 四文档全部批准。
**步骤：**

1. 在任何提示/描述改动前，冻结当前 SYSTEM_PROMPT、PLAN_MODE_REMINDER、EXECUTE_DIRECTIVE 及七个工具描述为静态 JSON。
2. 仅保存内置数据和工具名称；不得读取配置、密钥、历史、用户样本或环境路径。
3. 加离线 fixture 完整性用例，保留来源提交标识供人工对比，不以运行时重新生成替代基线。

**验证：** `uv run pytest tests/test_prompting.py -k baseline -v`；断言六/七工具语义及所有基线字段完整，fixture 无认证/运行时信息。

### T02：建立提示数据契约

**文件：** P01、P02、V01。
**依赖：** T01。
**步骤：**

1. 定义 PromptModule、GitSummary、EnvironmentSnapshot、RuntimeSupplement、PromptContext，与 Plan 字段一致。
2. 使用冻结对象、元组与明确状态；禁止持有可变历史或原生协议载荷引用。
3. 为补充项预留私有来源验证入口，不从标签字符串创建信任。

**验证：** `uv run pytest tests/test_prompting.py -k contract -v`；验证冻结、默认值、独立对象、非法状态及来源约束。

### T03：实现七模块与空槽装配

**文件：** P03、V01。
**依赖：** T02。
**步骤：**

1. 写入 Plan priority 10～70 的七模块正文，以及 80～100 的三个空槽；不插入模式值、日期或路径。
2. 实现 assemble_modules，校验重复 key、稳定排序、跳过空白、以一个空行分隔。
3. 加新模块挂载测试，以及外部来源未被读取的断言。

**验证：** `uv run pytest tests/test_prompting.py -k modules -v`；检查七模块顺序、相同优先级保序、空槽无输出、重复 key 报错和多次结果相同。

### T04：实现提醒工厂与节奏

**文件：** P05、V01。
**依赖：** T02。
**步骤：**

1. 实现 plan_reminder，完整提醒保留 AskUserQuestion 与等待 /do，精简提醒保留只读、可澄清和禁止提前执行。
2. 仅工厂生成带有效 origin 的补充项；标签只在渲染请求时包裹。
3. 覆盖 1～25 轮、normal 与非法轮次，不用工具数量或 SSE 片段计轮。

**验证：** `uv run pytest tests/test_prompting.py -k reminder -v`；完整轮次精确为 1/5/9/13/17/21/25，其他为精简，normal 为 None，两版规则不冲突。

### T05：环境渲染与每请求构造

**文件：** P06、P01、V01。
**依赖：** T03、T04。
**步骤：**

1. 实现 build_prompt_context，分别传递 stable_text、environment_text、supplements，不读写 Conversation。
2. 按 Plan 限额渲染快照，使用 JSON 数据外壳、尖括号转义、已知密钥脱敏和控制字符清理。
3. 生成明确“任务开始快照”说明；缺失字段有状态；展示路径不反向修改工具根。

**验证：** `uv run pytest tests/test_prompting.py -k render -v`；覆盖超长/缺失字段、伪造标签/ANSI/已知密钥、4096 字符正文上限及静态内容不变。

### T06：Git 状态解析与摘要限额

**文件：** P04、V02。
**依赖：** T02。
**步骤：**

1. 写独立解析函数，按 porcelain v1 的 NUL 记录及 XY 状态计数，处理 rename 第二路径与冲突。
2. 记录分类可重叠、未跟踪目录是条目；只输出计数/状态，不输出文件名。
3. 截断/不完整/格式异常不得返回精确总数或 clean。

**验证：** `uv run pytest tests/test_environment.py -k parse -v`；输入带换行/空格路径、rename、冲突、同时 staged/unstaged、未跟踪目录、截断记录，检查摘要事实。

### T07：实现有限环境采集

**文件：** P04、V02。
**依赖：** T06。
**步骤：**

1. 实现 EnvironmentCollector.capture，使用传入 ToolContext 根、版本/模型和本地日期；平台信息不包含主机/用户名。
2. 用 Plan 固定无 shell Git 参数；从创建进程起计 2 秒，stdout/stderr 并发排空，分别最多保留 64 KiB/4 KiB。
3. 非仓库、缺 Git、权限/cwd/输出错误和超时均产生降级快照；不输出 stderr 原文。

**验证：** `uv run pytest tests/test_environment.py -k capture -v`；替身验证固定 argv/cwd、总期限、超量排空、所有降级分支；事件循环心跳继续运行。

### T08：环境取消竞争与原生进程回收

**文件：** P04、V02。
**依赖：** T07。
**步骤：**

1. 为创建进程、读取、wait、kill/reap 建立明确任务所有权，处理取消/超时后迟到的进程句柄。
2. 截止后不再改快照，清理登记到 RunContext owned/cleanup；关闭调用幂等。
3. 加取消前/创建中/读取中/已完成竞争用例，以及原生可控慢进程与大输出测试；测试不依赖真实付费 API。

**验证：** `uv run pytest tests/test_environment.py -k cleanup -v`；确认无活子进程、挂起读任务或迟到修改。原生平台缺能力标跳过及原因，替身成功不冒充原生通过。

### T09：更新兼容常量与工具描述

**文件：** P09、P17～P23、V01、V11。
**依赖：** T01、T03、T04。
**步骤：**

1. SYSTEM_PROMPT 改导出装配结果，PLAN_MODE_REMINDER 导出完整版，EXECUTE_DIRECTIVE 原文不变。
2. 按 Plan 对七工具双重强化专用工具优先、真实读取后唯一替换、澄清不等于执行授权。
3. 对照基线/既有测试锁定 Schema、名称、read_only、execution_kind、限额与保护行为不变。

**验证：** `uv run pytest tests/test_prompting.py tests/test_tool_registry.py tests/test_file_tools.py -v`；normal 恰为原六工具，plan 恰为三读类加 AskUserQuestion，无新审批或编辑运行时门禁。

### T10：扩展用量与汇总数据契约

**文件：** P10、V04。
**依赖：** T01。
**步骤：**

1. 新增 UsageCounter 与 CacheCounterTotals，区分 reported/missing/not_applicable、value 与 invalid。
2. 在 TokenUsage 原四字段之后追加缓存分项与 uncached_input_tokens 默认字段；UsageTotals 追加分项汇总。
3. 保留旧位置参数/构造及输入输出语义；实现统计覆盖数和非法计数契约。

**验证：** `uv run pytest tests/test_cache_usage.py -k contract -v`；区分零/未知/不适用/异常，拒绝布尔伪整数和负数，旧构造兼容，冻结默认对象不共享可变数据。

### T11：实现全字段快照合并

**文件：** P11、V04。
**依赖：** T10。
**步骤：**

1. 实现 merge_usage_snapshot，对 input/output、缓存读写及 Anthropic 原始输入保留可信值。
2. 缺失不清零，倒退不覆盖，invalid 在请求内保持；保留 reported/not_applicable 语义。
3. complete 不把缺缓存子项等同基础统计未知；流失败/取消另按现有收尾置为 False。

**验证：** `uv run pytest tests/test_cache_usage.py -k merge -v`；覆盖缺失后补齐、重复/倒退、坏值前后、来源与全部扩展字段未丢失。

### T12：Anthropic 累计统计适配

**文件：** P11、V04、V08。
**依赖：** T11。
**步骤：**

1. UsageAccumulator 不再把未提供的缓存读/写初始化成已确认 0。
2. 保留原始非缓存输入，三项都可信时才按 input+read+write 生成精确总量。
3. message_start/delta/final 累计只覆盖快照；坏值保留可信项并标不完整。

**验证：** `uv run pytest tests/test_cache_usage.py -k anthropic -v`；100+20+30=150，缺任一缓存项总输入未知，显式零有效，重复 delta 不加倍。

### T13：Responses 与千问统计适配

**文件：** P11、V04、V08。
**依赖：** T11。
**步骤：**

1. Responses 读取 Plan 的 input_tokens_details 两个子字段，千问读取 prompt_tokens_details.cached_tokens。
2. 不跨协议猜路径、不从 total_tokens 反推，不把缺失写计数硬置 0。
3. 对完整可比快照检查子项与包含它们的输入总量冲突；不比较跨包暂态值造成误报。

**验证：** `uv run pytest tests/test_cache_usage.py -k 'openai or qwen' -v`；输入150/读30/写20仍为150，覆盖空details、坏类型、异常大分项、完整/部分快照。

### T14：单次统计汇总与覆盖率

**文件：** P10、V04。
**依赖：** T12、T13。
**步骤：**

1. 扩展 UsageTotals.add，逐请求只加入最后可信值，保留 reported/not_applicable/invalid 覆盖数。
2. 缺失不当作确认零；异常覆盖可重叠，不再从未知数中重复扣减。
3. 保留原输入/输出覆盖和 incomplete_requests 行为，不把缓存再加到输入。

**验证：** `uv run pytest tests/test_cache_usage.py -k totals -v`；构造多请求零/正数/缺失/不适用/部分/异常混合，逐项校验总量与覆盖数。

### T15：实现缓存能力纯函数

**文件：** P08、V03。
**依赖：** T02。
**步骤：**

1. 按批准 Plan 的端点/精确模型表实现 select_cache_policy 与规则版本；未知一律 prefix_only。
2. 精确验证 HTTPS、主机、端口、userinfo、API 根路径，保留清楚的 reason，不使用子串放行。
3. 不增加网络探测、配置开关、通用重试、TTL 或模型迁移。

**验证：** `uv run pytest tests/test_prompt_protocols.py -k policy -v`；覆盖官方已确认/未知模型、兼容服务、伪装域名、端口/路径变化及畸形 URL 安全降级，无网络调用。

### T16：扩展协议签名和参数冲突契约

**文件：** P11～P15、V03、V05、V08、V09。
**依赖：** T02、T15。
**步骤：**

1. 为 Provider 协议、三个实现与 Collector 增加可选 prompt_context 参数。
2. 无上下文时保持旧调用；非空 system_prompt 与结构化上下文同时传入明确拒绝，且不发送请求。
3. 此时 Runner 尚不切换新链路；只完成签名和合法输入检查，已有假 Provider 不必盲目接收新参数。

**验证：** `uv run pytest tests/test_prompt_protocols.py tests/test_provider_tools.py tests/test_stream_collector.py -v`；旧单字符串可运行，冲突不产生 HTTP/工具副作用。

### T17：Anthropic 请求副本注入

**文件：** P07、P12、V03、V09。
**依赖：** T05、T15、T16。
**步骤：**

1. 构造稳定 system 第一块、环境第二块；仅已选显式策略给第一块加 ephemeral 标记。
2. 对现有合法 _messages_payload 的末尾 user 内容追加提醒，或在没有末尾 user 时加补充消息；不插断结果块。
3. 保留原生 thinking/signature、工具 id、诊断降级和完整 SSE 门槛；旧调用不强制改形态。

**验证：** `uv run pytest tests/test_prompt_protocols.py -k anthropic -v`；捕获真实 body，检查唯一稳定边界、环境在外、兼容服务无缓存扩展、调用/结果及原生载荷不变。

### T18：Responses 两路请求注入

**文件：** P07、P13、V03、V09。
**依赖：** T05、T15、T16。
**步骤：**

1. 已确认策略用 developer input_text 显式边界，环境随后独立承载；不重复 instructions。
2. prefix_only 保留 instructions，环境走应用上下文 user 项，历史后再放本轮提醒。
3. 原 function_call/output、reasoning.encrypted_content、store=False 和完整流校验保持，不改成 Chat Completions。

**验证：** `uv run pytest tests/test_prompt_protocols.py -k openai -v`；显式和兼容两路捕获请求，确认扩展字段准确分流、工具配对、加密载荷逐项保留。

### T19：千问请求注入

**文件：** P07、P14、V03、V08、V09。
**依赖：** T05、T15、T16。
**步骤：**

1. 第一条 system 只放稳定正文，环境 user 数据消息在历史之前，提醒在所有 role=tool 结果之后。
2. 不为角色交替伪造 assistant；不增加未批准的显式缓存字段。
3. 保留 stream_options.include_usage、空 choices 用量末包和 finish+[DONE] 完整门槛。

**验证：** `uv run pytest tests/test_prompt_protocols.py -k qwen -v`；检查相邻 user 合法表达、工具配对、动态位置、尾包统计及普通文本流。

### T20：稳定前缀投影与字节测试

**文件：** P07、V03。
**依赖：** T09、T17、T18、T19。
**步骤：**

1. 从生产实际构造的稳定线格式生成规范投影及 SHA-256；纳入服务作用域、模型、策略/规则版本、工具顺序/设置。
2. 排除认证、动态环境、历史、轮次/请求 id；不另建近似测试版构造器。
3. 测试环境/问题/提醒变化不改稳定字节；模式改变工具集时 digest 可变，系统模块不变。

**验证：** `uv run pytest tests/test_prompt_protocols.py -k stable -v`；同时比较实际稳定块/工具序列字节和 digest，确认 normal六工具、plan四工具，绝不以 digest 当命中。

### T21：Collector 透传与完整统计保留

**文件：** P15、V05、V04。
**依赖：** T11、T14、T16～T19。
**步骤：**

1. 有上下文才传新关键字，空上下文旧调用仍可用；不让 Collector 装配规则或采集环境。
2. 用 merge_usage_snapshot 替换只构造 input/output 的逻辑，原样保留缓存分项和原始非缓存输入。
3. 验证异常/取消保留部分值、complete=False，aclose/双路文本与完整响应门槛不回退。

**验证：** `uv run pytest tests/test_stream_collector.py tests/test_cache_usage.py -v`；含流失败、取消、重复用量、原生完整响应与正文一致性用例。

### T22：Runner 接入每任务快照

**文件：** P16、V06。
**依赖：** T05、T08、T21。
**步骤：**

1. 注入可替换 EnvironmentCollector；生产从 executor.context.project_root 及当前模型/版本取值。
2. 在 _drive try/finally 资源范围内只采集一次；busy 拒绝、任务开始即取消不得新增采集/模型请求。
3. 接通 owned/cleanup 清理与 aclose；替身无工具根则标不可用，不回退伪造 cwd。

**验证：** `uv run pytest tests/test_turn_runner.py -k environment -v`；同任务多轮一次、新任务更新、采集失败继续、创建竞争/取消/退出释放 busy 且无遗留采集资源。

### T23：Runner 切换每请求结构化提示

**文件：** P16、V06。
**依赖：** T09、T20、T22。
**步骤：**

1. 按冻结模式取工具定义，用任务快照和真实 iteration 构造 PromptContext；传 system_prompt=""。
2. 删除每轮把完整计划提醒拼回系统字符串的路径，保留 system_prompt 覆盖稳定正文的兼容入口。
3. 保持 25 请求上限、未知工具阈值、完整响应后才执行、并发保序及原子历史提交。

**验证：** `uv run pytest tests/test_turn_runner.py -v`；验证 1/5/9节奏、新任务重置、normal无提醒、覆盖入口、模式工具集及所有既有停止/历史用例。

### T24：问答等待、/do 与恢复回归

**文件：** V07、V06、V10。
**依赖：** T23。
**步骤：**

1. 用 fake 流计划任务触发 AskUserQuestion，等候期间请求数/iteration/快照次数不变。
2. 提交真实答案后完成配对，下一请求正确计轮；回答不自动切 normal 或授权写入。
3. 覆盖 /plan 不请求、/do 新任务无计划提醒、取消问题/断连/流错误后下一任务可继续。

**验证：** `uv run pytest tests/test_user_questions.py tests/test_turn_runner.py tests/test_protocol_integration.py -v`；确认无假答案、无遗留等待或重复提交、计划模式硬门禁仍有效。

### T25：用量结算与 UI 安全回归

**文件：** P16、V06、V12、V04。
**依赖：** T14、T21、T23。
**步骤：**

1. 核对 usage 事件安全副本保留扩展字段，Runner 每 request_id 最多结算一次。
2. 覆盖 done/usage 重复、取消/失败部分统计、未开始模型请求不虚增统计。
3. UI 沿用原输入/输出显示，不增缓存栏；慢环境采集期间界面可响应，取消后可继续输入。

**验证：** `uv run pytest tests/test_cache_usage.py tests/test_turn_runner.py tests/test_tui.py -v`；断言汇总覆盖数正确、无已知密钥/ANSI污染、缓存分项不会丢失或重复加到输入。

### T26：三协议注入与原始数据安全矩阵

**文件：** V01、V03、V09、V10。
**依赖：** T20、T24、T25。
**步骤：**

1. 参数化 normal/plan、工具/无工具、末尾角色、原生/诊断回放、full/brief/空提醒场景。
2. 请求前后深比较保存历史；检查真实参数、答案、调用 id、thinking/签名/加密载荷未被注入逻辑改写。
3. 注入用户/文件/工具/环境伪造标签和已知密钥，验证程序不将数据识别为私有补充指令，显示副本安全。

**验证：** `uv run pytest tests/test_prompting.py tests/test_prompt_protocols.py tests/test_provider_tools.py tests/test_protocol_integration.py tests/test_redaction.py -v`；角色合法性按各协议，不增加通用交替断言。

### T27：离线调试入口与安全报告

**文件：** V13、V03、V04。
**依赖：** T20、T25。
**步骤：**

1. 实现 argparse 入口及 Plan 的 scenario/prompt-variant 参数，默认仅内置离线演示，明确不是当前配置。
2. 实现 JSON 结果报告：服务 host/协议/模型、策略原因、digest、轮次/id、统计值/可用性/异常/完整性与停止结果。
3. 默认路径不加载认证配置、不请求模型、不输出完整历史/原始异常或路径；用替身测试守住零网络和脱敏。

**验证：** `uv run python tests/manual_prompt_smoke.py` 及 `uv run pytest tests/test_prompt_protocols.py -k manual -v`；默认演示有明确标记，断言配置解析/HTTP 未被调用。

### T28：显式 live 缓存观察场景

**文件：** V13、V03。
**依赖：** T27。
**步骤：**

1. 只有 --live 才加载当前默认配置；同稳定前缀连续两次请求，第二次改变受控动态值。
2. 仅消费 Provider 事件，不执行模型提出的工具、不伪造成功或自动继续循环；不自动改配置/服务或预热。
3. 记录缺条件/缺字段/未命中/统计异常；非敏感长样本只在该手动场景中使用，不填充生产指令。

**验证：** `uv run pytest tests/test_prompt_protocols.py -k live_guard -v` 用替身验证显式开关、恰当请求次数、无工具执行与清理；真实命中留 T33，不因替身数值通过而标实测。

### T29：人工提示对比与样本限制

**文件：** V13、V14、V03。
**依赖：** T01、T24、T27。
**步骤：**

1. 实现 baseline/modular 的提示及描述切换，只影响验证运行，不改生产配置；相同运行时比较，不称旧版本性能基准。
2. 临时目录受限验收器只允许样本操作与明确的计划提问；命令/越界/非样本请求拒绝并如实记录。
3. 准备专用工具、先读再改、含糊澄清、明确计划等待/do、环境、提醒不被回应、取消恢复七类人工场景；逐个选择，不自动评分/批跑收费实验。

**验证：** `uv run pytest tests/test_prompt_protocols.py -k behavior_guard -v`；替身断言样本范围、命令拒绝、原始答案保存、提示版本可区分，所有临时资源在失败/取消后回收。

### T30：更新使用说明

**文件：** D01。
**依赖：** T27～T29。
**步骤：**

1. 说明七模块/空槽、每任务快照、提醒节奏与三协议缓存策略，保持六字段 YAML 不变。
2. 给出默认离线入口、显式 live 的费用/权限提示、当前默认服务原则及真实字段的判断口径。
3. 说明字段缺失不是零、digest不是命中、写缓存也可收费、服务缓存/数据保留不受本地分段全面控制；不声称始终省钱或提示百分百有效。

**验证：** 对照入口 --help、离线输出与批准 Plan 逐项检查说明一致，检索无原始密钥/无虚构线上成功；不为检查文档示例发真实请求。

### T31：完整离线工程回归

**文件：** V01～V12；只读检查依赖与锁文件；必要修复仅限本章生产文件。
**依赖：** T26、T28～T30。
**步骤：**

1. 执行 uv lock --check 和 compileall；确认依赖/Python要求未变，无未配置的 Ruff/mypy 检查。
2. 执行全量 pytest，保留工具/进程/脱敏/预算/问答安全断言；新测试不得默认触发线上入口。
3. 对失败修复后重跑相关组及全量；按实际平台记录跳过，不沿用旧章节通过数。

**验证：** `uv lock --check`、`uv run python -m compileall -q src`、`uv run pytest -v`；记录真实退出码、通过/失败/跳过及原因。本任务不表示真实服务缓存或 PowerShell 观察通过。

### T32：真实终端流程观察

**文件：** D02 未来验收记录；不修改用户配置。
**依赖：** T31；合法当前配置及用户可操作 PowerShell。
**步骤：**

1. 由用户运行 uv run python -m weizhcode，观察启动、流式、环境采集期间响应及状态栏未新增缓存项。
2. 在非敏感样本中运行计划澄清、回答后继续、计划等待 /do、切执行及取消/恢复。
3. 退出后确认终端恢复、无遗留问题/采集进程；无法现场观察就保留待验，不用无界面测试代替。

**验证：** 记录实际操作、模型/协议、截图或用户确认及异常；不将截图包含的密钥或私密文件写入验收记录。

### T33：有条件的真实缓存与定性验证

**文件：** V13 执行入口、D02 未来记录。
**依赖：** T28、T29、T31；用户明确同意本次真实请求且当前服务凭证/权限可用。
**步骤：**

1. 先告知当前服务/模型、场景及会产生真实请求；无明确许可不运行。缓存使用 --live --scenario cache，读取真实计数和可用性。
2. 人工按 --live --scenario behavior 逐项选择基线/新提示相同样本，记录实际工具顺序/结果及必要条件差异；不自动跑完整收费矩阵。
3. 协议真实覆盖不足逐项待验，不自动切回千问或购买额度；缺字段、未命中、坏统计均不冒充命中或改善。

**验证：** 只有可信的实际 cache_read 正值才是读取命中证据；写入与读取分开记录。相同 digest仅证明应用稳定部分一致，人工行为不作统计显著或费用保证。

### T34：证据汇总与本章收尾

**文件：** D02；只读检查本章差异与工作区状态。
**依赖：** T31；T32/T33 已完成或明确记录未运行条件。
**步骤：**

1. 按未来已批准 Checklist 对 AC1～AC18逐项附证据，区分通过、失败、缺条件/未运行，不预先勾选线上项。
2. 核对改动仅本章文件，忽略配置及用户 .weizhcode-test/未提交，必要逻辑提交完成后报告。
3. 报告实现状态、自动验证和仍待用户手测/授权项，不因代码完成就宣称全部验收通过。

**验证：** 清单每项均能追溯到真实命令或人工记录，无跨章节借用结果；未运行项目有明确下一步，未执行自动推送。

## 4. 依赖与执行顺序

推荐按 T01→T34 编号顺序执行，合法且便于逐步留绿；每项明确依赖是最低前置要求。没有要求并行代理或跨线程修改。

逻辑提交组建议：

| 组 | 任务 | 提交前检查 |
|---|---|---|
| A | T01～T09 | 模块/提醒/环境及原生清理定向测试，原工具保护回归 |
| B | T10～T14 | 缓存契约、三协议统计、合并/汇总矩阵 |
| C | T15～T20 | 接口兼容、三协议实际请求、稳定边界/字节 |
| D | T21～T26 | Collector/Runner/问答/UI及三协议完整集成 |
| E | T27～T31 | 手动入口离线保护、说明与完整工程回归 |
| F | T32～T34 | 只提交允许保存的验收记录；缺条件项保持待验 |

提交组不是跳过任务验证的理由。组内失败先修复，不把半成品标为通过；线上或终端缺条件不阻止完成离线实现和诚实交付，但也不能把那些条目标通过。

## 5. 需求与任务覆盖

| Spec / 验收 | 对应任务 |
|---|---|
| F1/F2、N1；AC1/AC2 | T02、T03、T05、T09 |
| F3、N2；AC3/AC4 | T05～T08、T22、T32 |
| F4；AC5/AC6 | T09、T15～T20、T23、T26 |
| F5、N8；AC7/AC8 | T15、T17～T20、T28、T33 |
| F6；AC9/AC15 | T01、T03、T09、T29、T33 |
| F7、N3/N4；AC10/AC11/AC17 | T02、T04、T05、T17～T19、T26 |
| F8；AC12 | T04、T23、T24、T32 |
| F9、N5；AC13 | T10～T14、T21、T25 |
| F10；AC8/AC14/AC15 | T27～T30、T33、T34 |
| F11；AC16 | T16～T19、T21～T26、T31、T32 |
| N6/N7；AC18 | T30～T34及各任务实际证据 |

## 6. 审批

共 34 个有序任务，覆盖已批准 Plan 的组件、文件及验证边界。请审批任务粒度、依赖与验证安排。

批准后只生成 Checklist 并再次等待审批；本次未创建实现文件、未运行开发测试、未发模型请求、未提交或推送 Git。

## 7. 实现进度（审批后记录）

| 任务 | 状态 | 证据 |
|---|---|---|
| T01 | 已完成（定向验证） | 项目 .venv Python：prompting/environment/registry/file_tools 共100通过；原生Windows检查在正常本机环境执行 |
| T02 | 已完成（定向验证） | 项目 .venv Python：prompting/environment/registry/file_tools 共100通过；原生Windows检查在正常本机环境执行 |
| T03 | 已完成（定向验证） | 项目 .venv Python：prompting/environment/registry/file_tools 共100通过；原生Windows检查在正常本机环境执行 |
| T04 | 已完成（定向验证） | 项目 .venv Python：prompting/environment/registry/file_tools 共100通过；原生Windows检查在正常本机环境执行 |
| T05 | 已完成（定向验证） | 项目 .venv Python：prompting/environment/registry/file_tools 共100通过；原生Windows检查在正常本机环境执行 |
| T06 | 已完成（定向验证） | 项目 .venv Python：prompting/environment/registry/file_tools 共100通过；原生Windows检查在正常本机环境执行 |
| T07 | 已完成（定向验证） | 项目 .venv Python：prompting/environment/registry/file_tools 共100通过；原生Windows检查在正常本机环境执行 |
| T08 | 已完成（定向验证） | 项目 .venv Python：prompting/environment/registry/file_tools 共100通过；原生Windows检查在正常本机环境执行 |
| T09 | 已完成（定向验证） | 项目 .venv Python：prompting/environment/registry/file_tools 共100通过；原生Windows检查在正常本机环境执行 |
| T10 | 已完成（定向验证） | cache_usage/provider_events/protocol_integration 共82通过，17.60秒；全量待验 |
| T11 | 已完成（定向验证） | cache_usage/provider_events/protocol_integration 共82通过，17.60秒；全量待验 |
| T12 | 已完成（定向验证） | cache_usage/provider_events/protocol_integration 共82通过，17.60秒；全量待验 |
| T13 | 已完成（定向验证） | cache_usage/provider_events/protocol_integration 共82通过，17.60秒；全量待验 |
| T14 | 已完成（定向验证） | cache_usage/provider_events/protocol_integration 共82通过，17.60秒；全量待验 |
| T15 | 未开始 | 尚无通过结论 |
| T16 | 未开始 | 尚无通过结论 |
| T17 | 未开始 | 尚无通过结论 |
| T18 | 未开始 | 尚无通过结论 |
| T19 | 未开始 | 尚无通过结论 |
| T20 | 未开始 | 尚无通过结论 |
| T21 | 未开始 | 尚无通过结论 |
| T22 | 未开始 | 尚无通过结论 |
| T23 | 未开始 | 尚无通过结论 |
| T24 | 未开始 | 尚无通过结论 |
| T25 | 未开始 | 尚无通过结论 |
| T26 | 未开始 | 尚无通过结论 |
| T27 | 未开始 | 尚无通过结论 |
| T28 | 未开始 | 尚无通过结论 |
| T29 | 未开始 | 尚无通过结论 |
| T30 | 未开始 | 尚无通过结论 |
| T31 | 未开始 | 尚无通过结论 |
| T32 | 未开始 | 尚无通过结论 |
| T33 | 未开始 | 尚无通过结论 |
| T34 | 未开始 | 尚无通过结论 |
