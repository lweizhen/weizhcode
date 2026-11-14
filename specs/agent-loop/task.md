# weizhCode Agent Loop Tasks

> 状态：Spec、Plan、Task、Checklist 均已获用户明确批准，已进入开发。以下进度仅按实际验证更新，审批不等于实现或验收通过。
> 依据：[Spec](D:/STUDY/weizhcode-python/specs/agent-loop/spec.md)、[Plan](D:/STUDY/weizhcode-python/specs/agent-loop/plan.md)。
> 按用户要求，后续每阶段直接生成完整文件再统一审批，不逐节确认。Task 获批后才编写 Checklist；四份文档全部获批后才允许实现。

## 1. 使用规则与验收边界

- 本章共 66 个任务；四份文档已全部批准，按下列顺序实现与验证。真实终端、真实 API 与平台条件单独记录。
- 所有开发命令从 D:/STUDY/weizhcode-python 执行。每项先完成自身步骤和指定验证，再按真实结果更新状态；空集合、全部 deselected 或仅 skip 不算验证通过。
- 每项应是一个聚焦的小改动，目标为 2～5 分钟的实现/断言单元，验证耗时单独计算。遇到无法保持聚焦的任务，先在同一批准范围内细分准备动作，不把数个未验证变化笼统标成完成。
- T49 是跨接口机械切换点，不承担重新设计组件：T2～T48 先准备并验证可组合的新契约/组件，T49 统一切换调用方、移除过渡字段和旧路径后做全量验证。若切换仍需大量业务逻辑，应先补回对应准备任务，而非留下半套新旧接口。
- 迁移中可暂留旧入口需要的 approval/phase/requires_confirmation 字段和旧 run；它们只为保持尚未切换入口可用，不新增用户可选的双引擎/自动批准开关。最终必须在 T49 删除，不能作为交付兼容层。
- 每个任务至少自身局部测试与相关模块编译通过；新路径的局部验证不等于整个仓库新行为已接通。涉及调用方切换的 T41～T49 作为同一接线逻辑组验全量后再提交，不发布中间不一致版本。
- 旧的审批、单工具上限、第二阶段禁用工具断言按第 4 节迁移；文件/进程/Schema/脱敏/预算等安全断言必须保留。不准用删除安全测试、临时 skip、屏蔽失败命令来“留绿”。
- 新增测试筛选标签在所属任务内实际实现为测试名的一部分；验证前确认选择器收集到目标用例。任务文件中的命令是未来执行索引，不是运行记录。
- 不新增 SDK、测试插件、Ruff、mypy、tmux/WSL 或其他系统组件；不改六字段 YAML、用户端点、模型、密钥或默认供应商。
- .weizhcode-test 是用户已有手测产物；不删除、不覆盖、不提交。当前开发基线的差异和数据属于用户，T1 只读记录并保留。
- 自动副作用测试只在受控临时目录运行。真实模型提出超出验收临时范围的操作时停止该次验收，不把测试扩大到真实源码/用户数据；这不是给产品新增沙箱或路径白名单。
- 真实 PowerShell 由可用且允许的观察机制或用户完成；受当前桌面规则限制时记录待用户手测，不能用 Pilot 代替。真实 API 不自动要求新密钥、付费或改配置。
- 每组相关实现验证通过后仅本地提交；GitHub 推送必须另获用户授权。参考材料和历史测试数量都不作为本章当前证据。

## 2. 文件清单

与 Plan 的 12.1/12.2 对齐；所有路径为拟议改动，测试验证任务列在“涉及任务”中。原则保留的文件只有在本章必要修正时才编辑。

| 操作 | 绝对路径 | 职责 | 涉及任务 |
|------|----------|------|----------|
| 修改 | D:/STUDY/weizhcode-python/src/weizhcode/models.py | Mode、StopReason、Usage、RoundResponse、RunContext/ToolSlot 契约；事件扩展；read_only；取消结果；移除审批模型 | T2、T3、T4、T5、T6、T49 |
| 新建 | D:/STUDY/weizhcode-python/src/weizhcode/stream_collector.py | 流式双路收集、取消网络等待、用量快照与完整响应 | T15、T16、T17、T18 |
| 新建 | D:/STUDY/weizhcode-python/src/weizhcode/tool_scheduler.py | 调用预检、连续只读批、串行副作用、排序结果、取消补齐 | T27、T28、T29、T30、T31、T32 |
| 修改 | D:/STUDY/weizhcode-python/src/weizhcode/turn_runner.py | 循环、会话模式、用量结算、事件队列、占用与生命周期 | T19、T20、T33、T34、T35、T36、T37、T38、T39、T40、T46、T49、T50 |
| 修改 | D:/STUDY/weizhcode-python/src/weizhcode/conversation.py | 原子交换增强、真实诊断载荷、应用停止收尾 | T9、T10、T11、T34、T37 |
| 修改 | D:/STUDY/weizhcode-python/src/weizhcode/prompts.py | Loop 与 Plan 提示、执行指令、移除固定最终续答约定 | T8、T39、T49 |
| 修改 | D:/STUDY/weizhcode-python/src/weizhcode/providers/base.py | 统一 usage 契约与准确诊断序列化 | T10 |
| 修改 | D:/STUDY/weizhcode-python/src/weizhcode/providers/anthropic.py | 多调用控制、累计 usage、保持签名/完整流检查 | T12、T48 |
| 修改 | D:/STUDY/weizhcode-python/src/weizhcode/providers/openai.py | Responses 多调用、usage、完整输出回放 | T13、T48 |
| 修改 | D:/STUDY/weizhcode-python/src/weizhcode/providers/qwen.py | include_usage、空 choices、usage 去重 | T14、T48 |
| 修改 | D:/STUDY/weizhcode-python/src/weizhcode/tools/registry.py | 只读定义过滤及查询；保留 Schema 校验 | T7 |
| 修改 | D:/STUDY/weizhcode-python/src/weizhcode/tools/base.py | 工具契约随元信息同步，不放入 UI 逻辑 | T6、T49 |
| 修改 | D:/STUDY/weizhcode-python/src/weizhcode/tools/read_file.py | 显式只读元信息，文件行为不变 | T6、T49 |
| 修改 | D:/STUDY/weizhcode-python/src/weizhcode/tools/find_files.py | 显式只读元信息，搜索行为不变 | T6、T49 |
| 修改 | D:/STUDY/weizhcode-python/src/weizhcode/tools/search_content.py | 显式只读元信息，搜索行为不变 | T6、T49 |
| 修改 | D:/STUDY/weizhcode-python/src/weizhcode/tools/write_file.py | 副作用元信息；保留准备/原子写 | T6、T49 |
| 修改 | D:/STUDY/weizhcode-python/src/weizhcode/tools/edit_file.py | 副作用元信息；保留唯一替换 | T6、T49 |
| 修改 | D:/STUDY/weizhcode-python/src/weizhcode/tools/run_command.py | 副作用元信息；保持非交互 shell 与输出限制 | T6、T49 |
| 修改 | D:/STUDY/weizhcode-python/src/weizhcode/tools/executor.py | execute 新接口、plan 门禁、槽内结果、取消清理，移除审批 | T21、T22、T23、T24、T25、T26、T49 |
| 修改 | D:/STUDY/weizhcode-python/src/weizhcode/tools/process.py | 保持实际进程树清理，补齐取消/启动/并发收尾竞态 | T25 |
| 修改 | D:/STUDY/weizhcode-python/src/weizhcode/tui.py | 新事件、模式命令、优先取消、用量/轮次、退出接线、移除审批桥 | T42、T43、T44、T45、T47、T49、T50 |
| 修改 | D:/STUDY/weizhcode-python/src/weizhcode/tool_ui.py | 多工具 ID 状态、取消展示、删除审批 UI | T41、T46、T49 |
| 修改 | D:/STUDY/weizhcode-python/src/weizhcode/cli.py | Collector/Scheduler/Runner 构造接线 | T1、T47、T49 |
| 原则保留，回归检查 | D:/STUDY/weizhcode-python/src/weizhcode/tools/worker.py | 继续准备/执行协议；仅因公共模型变更作必要同步 | T25 |
| 原则保留，回归检查 | D:/STUDY/weizhcode-python/src/weizhcode/redaction.py | 原有安全出口复用；如取消出口暴露缺口只作本章必要修正 | T46 |
| 新建 | D:/STUDY/weizhcode-python/tests/test_stream_collector.py | 双路、残缺流、取消等待、usage、正文补发/去重 | T15、T16、T17、T18 |
| 新建 | D:/STUDY/weizhcode-python/tests/test_tool_scheduler.py | 并发重叠、前后批屏障、排序、重复 ID、部分取消 | T27、T28、T29、T30、T31、T32、T56 |
| 修改 | D:/STUDY/weizhcode-python/tests/test_turn_runner.py | 多轮、25 上限、3 全未知、停止、用量、会话模式、取消后复用 | T3、T8、T19、T20、T33、T34、T35、T36、T37、T38、T39、T40、T46、T49、T50、T52、T53 |
| 修改 | D:/STUDY/weizhcode-python/tests/test_tool_registry.py | 6 定义、只读集合、未知查询、read_only 显式分类 | T6、T7、T49、T51 |
| 修改 | D:/STUDY/weizhcode-python/tests/test_tool_executor.py | 新 execute 接口、无审批、plan 零副作用、结果/取消竞态、进程清理 | T5、T21、T22、T23、T24、T25、T26、T49、T50、T51、T56 |
| 修改 | D:/STUDY/weizhcode-python/tests/test_provider_events.py | 三协议 usage 快照、完成信号与请求体 | T2、T12、T13、T14 |
| 修改 | D:/STUDY/weizhcode-python/tests/test_provider_tools.py | 多轮、多调用、回放、混合诊断与字段去重 | T10、T48、T52、T53 |
| 修改 | D:/STUDY/weizhcode-python/tests/test_protocol_integration.py | 三协议同组真实工作进程 Loop、取消与后续上下文 | T49、T53 |
| 修改 | D:/STUDY/weizhcode-python/tests/test_conversation.py | 配对、数量、深复制、混合诊断事实和应用通知 | T9、T10、T11、T53 |
| 修改 | D:/STUDY/weizhcode-python/tests/test_tui.py | 模式、按键、草稿、事件、轮次/用量与正常聊天 | T4、T42、T43、T44、T49 |
| 修改 | D:/STUDY/weizhcode-python/tests/test_tool_tui.py | 多工具、取消、无审批、状态顺序与执行中退出 | T41、T42、T44、T45、T46、T49、T50、T52 |
| 修改 | D:/STUDY/weizhcode-python/tests/test_cli.py | 新接线与缺配置路径，不解析未选后端密钥 | T47、T49 |
| 修改 | D:/STUDY/weizhcode-python/tests/manual_tool_smoke.py | 手动线上脚本迁移 Loop、完整正文断言、模式/调用次数；不自动使用 API | T49、T54 |
| 保留并回归 | D:/STUDY/weizhcode-python/tests/test_file_tools.py | 编码/换行/唯一匹配/陈旧目标/原子写保护 | T51 |
| 保留并回归 | D:/STUDY/weizhcode-python/tests/test_search_tools.py | 过滤、上限、不完整检索 | T51 |
| 保留并回归 | D:/STUDY/weizhcode-python/tests/test_command_tool.py | stdout/stderr、退出码、目录、环境、输出上限 | T51 |
| 保留并回归 | D:/STUDY/weizhcode-python/tests/test_config.py | 六字段与默认供应商密钥解析 | T1、T55 |
| 保留并回归 | D:/STUDY/weizhcode-python/tests/test_redaction.py | 跨片正文、结果、错误及实际参数不篡改 | T46、T52、T55 |

流程文件仅按审批/执行事实更新：

| 文件 | 本轮状态 |
|------|----------|
| D:/STUDY/weizhcode-python/specs/agent-loop/spec.md | 已批准，不改需求 |
| D:/STUDY/weizhcode-python/specs/agent-loop/plan.md | 已批准，已记录进入Task及统一审批方式 |
| D:/STUDY/weizhcode-python/specs/agent-loop/task.md | 已批准，正在实施并记录进度 |
| D:/STUDY/weizhcode-python/specs/agent-loop/checklist.md | 已批准，逐项按实际证据验收 |

## 3. 执行分组与依赖

| 分组 | 任务区间 | 阶段完成标志 |
|------|----------|--------------|
| 基础契约与历史 | T1～T11 | 所属局部用例通过，收尾与依赖无遗漏 |
| 协议用量、收集器与事件通道 | T12～T20 | 所属局部用例通过，收尾与依赖无遗漏 |
| 执行器与保序调度 | T21～T32 | 所属局部用例通过，收尾与依赖无遗漏 |
| Loop驱动与会话状态 | T33～T40 | 所属局部用例通过，收尾与依赖无遗漏 |
| 界面、原子接线与生产路径 | T41～T50 | T49正式切换后全量通过，T50再验证生产路径 |
| 自动回归与平台验证 | T51～T56 | 所属局部用例通过，收尾与依赖无遗漏 |
| 真实PowerShell验收 | T57～T61 | 实际观察，不用无界面证据替代 |
| 各服务真实API | T62～T65 | 真实结果或缺条件明确记录 |
| 证据与交付 | T66 | 状态与证据可追溯 |

各任务下方列出直接依赖。按编号执行是合法的拓扑顺序；依赖均指向较小编号，无循环。实现可在同一职责组内细分，但不得跳过验证或跨审批门槛。

## 4. 旧行为断言的迁移清单

这不是删测试授权，而是将新 Spec 明确替换的行为改成对应的新断言；其余断言继续保留。

| 现有位置/行为 | 新断言/替换目标 | 接线任务 |
|---------------|----------------|----------|
| test_default_registry_six_order_and_permissions 使用 requires_confirmation | 六工具只读标志及精确三工具子集；不保留审批元信息 | T6、T7、T49 |
| test_executor_approval_no_early_write / missing_handler_denies | normal 无审批可执行，plan 硬门禁零worker/零副作用；取消前未启动项不执行 | T21、T22、T49、T50 |
| test_executor_approval_stale_after_wait | prepare后受控改变目标，仍 PREVIEW_STALE、不覆盖；不再依赖人工等待 | T24、T49、T51 |
| test_executor_timeout_approval_pauses_budget | 移除审批等待假设，保留准备+执行共享预算；并发许可等待另行不计工具预算 | T23、T29、T49 |
| FakeExecutor.run(...approve)、collect(...approve) | execute(slot,mode,cancel,emit) 与槽事实；所有测试助手同步 | T21、T24、T49 |
| runner_tool_round 断言第二次 allow_tools=False、phase=final | 每轮可继续工具、iteration关联、直至无调用；实际结果/顺序仍验证 | T33、T34、T49 |
| runner_limits_multiple_calls_execute_none / final_extra_call | 只读分批并发/副作用串行；25轮及全未知上限取代单工具限制 | T27～T36、T49 |
| protocol_integration 的 multiple/denied/final_limit | 多调用安全执行、plan拒绝、任务取消和真正迭代上限；仍保留错误/诊断/下一轮 | T49、T53 |
| approval_ui_write_and_decision_binding / pending_approval_shutdown | 无审批自动执行、模式门禁、取消工具及应用退出；不保留等待Future | T41～T50 |
| test_tool_tui 中点击 allow/deny 和 app._approvals | 移除按钮操作，验证正式执行/取消/清理与草稿、文件实际内容 | T49、T50 |
| test_tui 的 FakeProvider done 无完整assistant_message | 按新Collector完整契约提供消息/增量一致样本；保留普通聊天和错误不入成功历史断言 | T42、T49 |
| manual_tool_smoke 依赖 phase==final/固定两次请求 | 按迭代及StopReason验证实际最终正文，多步而非一次工具后停 | T49、T54 |
| Provider独立测试显式 allow_tools=False | 继续验证该显式参数映射；只移除Runner固定第二次强制none的假设 | T48、T49 |
| 编码/换行/匹配/过滤/进程树/密钥/结果上限 | 保留实际行为；仅因事件/调用接口迁移测试助手 | T25、T46、T51、T56 |

表中测试函数位于上述文件清单对应的现有 tests 文件；实现时根据实际函数定位，不依赖易变行号。严禁把缺凭证、原生平台skip或“参考已实测”当成通过。

## 5. 有序任务

### T1：建立本章开发基线

**文件：** `D:/STUDY/weizhcode-python/src/weizhcode/cli.py`、`D:/STUDY/weizhcode-python/tests/test_config.py`、`D:/STUDY/weizhcode-python/pyproject.toml`、`D:/STUDY/weizhcode-python/uv.lock`

**依赖：** 无；但必须先完成四份文档审批。

**步骤：**

1. 四份文档全部批准后才运行 uv sync --locked、全量 pytest 与 compileall；记录解释器、系统、数量、退出码和 skip 原因。
2. 只读记录工作区已有差异；不提交用户配置和 .weizhcode-test，不改依赖或后端。

**验证：** 从项目根运行上述命令；任何失败先定位，不能用历史的 226 passed、2 skipped 冒充本次结果。

**覆盖：** N7、N8、AC16。

### T2：增加用量快照契约

**文件：** `D:/STUDY/weizhcode-python/src/weizhcode/models.py`、`D:/STUDY/weizhcode-python/tests/test_provider_events.py`

**依赖：** T1

**步骤：**

1. 增加不可变 TokenUsage、UsageTotals 数据契约，明确 None 与真实 0、完整性和来源。
2. 新增字段复制、非法负数/布尔值与部分统计用例，不改现有 Provider 调用签名。

**验证：** 新增/保留以 usage_contract 命名的断言并运行 uv run python -m pytest D:/STUDY/weizhcode-python/tests/test_provider_events.py -k usage_contract -q；必须实际收集用例且全部通过。

**覆盖：** F8、N5、AC11。

### T3：增加任务状态与完整响应模型

**文件：** `D:/STUDY/weizhcode-python/src/weizhcode/models.py`、`D:/STUDY/weizhcode-python/tests/test_turn_runner.py`

**依赖：** T2

**步骤：**

1. 定义 AgentMode、StopReason、StreamState、RoundResponse、RunContext 及任务独立的事件/状态。
2. 验证 run_id、request_id、25/3 计数初值、模式冻结和跨任务不共享槽；不让 models 引用具体执行器或 TUI。

**验证：** 新增/保留以 run_context_contract 命名的断言并运行 uv run python -m pytest D:/STUDY/weizhcode-python/tests/test_turn_runner.py -k run_context_contract -q；必须实际收集用例且全部通过。

**覆盖：** F1、F2、F7、F10、AC3、AC4、AC9。

### T4：扩展统一事件并保留迁移兼容

**文件：** `D:/STUDY/weizhcode-python/src/weizhcode/models.py`、`D:/STUDY/weizhcode-python/tests/test_tui.py`

**依赖：** T3

**步骤：**

1. 增加 iteration、usage、mode、tool_start、notice、turn_done 原因和相关性字段；新增字段先提供兼容默认值。
2. 验证同名调用按 local_id 区分；临时 initial/final、审批字段只服务未切换的旧入口，T49 统一移除。

**验证：** 新增/保留以 loop_event_contract 命名的断言并运行 uv run python -m pytest D:/STUDY/weizhcode-python/tests/test_tui.py -k loop_event_contract -q；必须实际收集用例且全部通过。

**覆盖：** F3、F9、AC10、AC14。

### T5：增加取消结果与执行槽

**文件：** `D:/STUDY/weizhcode-python/src/weizhcode/models.py`、`D:/STUDY/weizhcode-python/tests/test_tool_executor.py`

**依赖：** T3

**步骤：**

1. 定义 ToolSlot 的 index、phase、execution_started、result、cleanup_error。
2. ToolResult 支持 cancelled/TOOL_CANCELLED，验证已确认结果不被取消覆盖、取消结果序列化仍满足预算。

**验证：** 新增/保留以 tool_slot_contract 命名的断言并运行 uv run python -m pytest D:/STUDY/weizhcode-python/tests/test_tool_executor.py -k tool_slot_contract -q；必须实际收集用例且全部通过。

**覆盖：** F6、F7、N3、N5、AC8、AC9、AC15。

### T6：引入显式只读分类

**文件：** `D:/STUDY/weizhcode-python/src/weizhcode/models.py`、`D:/STUDY/weizhcode-python/src/weizhcode/tools/base.py`、`D:/STUDY/weizhcode-python/src/weizhcode/tools/read_file.py`、`D:/STUDY/weizhcode-python/src/weizhcode/tools/find_files.py`、`D:/STUDY/weizhcode-python/src/weizhcode/tools/search_content.py`、`D:/STUDY/weizhcode-python/src/weizhcode/tools/write_file.py`、`D:/STUDY/weizhcode-python/src/weizhcode/tools/edit_file.py`、`D:/STUDY/weizhcode-python/src/weizhcode/tools/run_command.py`、`D:/STUDY/weizhcode-python/tests/test_tool_registry.py`

**依赖：** T4

**步骤：**

1. 先增 read_only=False 元信息，六工具用关键字显式设置三个 True、三个 False，不能反转旧位置参数语义。
2. 临时保留 requires_confirmation 让旧入口可运行；T49 清除。同步本任务元信息断言，不改变文件/命令执行逻辑。

**验证：** 新增/保留以 readonly_classification 命名的断言并运行 uv run python -m pytest D:/STUDY/weizhcode-python/tests/test_tool_registry.py -k readonly_classification -q；必须实际收集用例且全部通过。

**覆盖：** F5、F10、N4、AC6、AC12、AC15。

### T7：实现只读定义过滤与查询

**文件：** `D:/STUDY/weizhcode-python/src/weizhcode/tools/registry.py`、`D:/STUDY/weizhcode-python/tests/test_tool_registry.py`

**依赖：** T6

**步骤：**

1. definitions(read_only=True) 只导出 read_only is True 的工具且保留注册顺序；is_read_only 对未知返回 False。
2. 验证恰好六工具、只读集合恰好三个、真值字符串不放行、返回副本不可篡改注册表；Schema 校验不回退。

**验证：** 新增/保留以 readonly_registry 命名的断言并运行 uv run python -m pytest D:/STUDY/weizhcode-python/tests/test_tool_registry.py -k readonly_registry -q；必须实际收集用例且全部通过。

**覆盖：** F5、F10、AC6、AC12。

### T8：准备循环与计划提示词

**文件：** `D:/STUDY/weizhcode-python/src/weizhcode/prompts.py`、`D:/STUDY/weizhcode-python/tests/test_turn_runner.py`

**依赖：** T7

**步骤：**

1. 准备持续多步工具、计划只读、/do 执行指令、工具输出为数据及停止不等于成功的文案。
2. 新收集/循环路径使用新文案；旧正式入口切换前仍保留原契约，T49 统一替换 SYSTEM_PROMPT 并移除 FINAL_PROMPT 路径。

**验证：** 新增/保留以 loop_prompts 命名的断言并运行 uv run python -m pytest D:/STUDY/weizhcode-python/tests/test_turn_runner.py -k loop_prompts -q；必须实际收集用例且全部通过。

**覆盖：** F1、F10、N6、AC1、AC13。

### T9：强化原子工具交换校验

**文件：** `D:/STUDY/weizhcode-python/src/weizhcode/conversation.py`、`D:/STUDY/weizhcode-python/tests/test_conversation.py`

**依赖：** T5

**步骤：**

1. 所有交换都检查结果数量；合法原生交换按调用顺序逐 ID 配对，错误不能留下半个交换。
2. 保留深复制；为取消、未知/非法调用和真实结果准备诊断元信息保存，不依赖禁止同角色相邻。

**验证：** 新增/保留以 loop_exchange_contract 命名的断言并运行 uv run python -m pytest D:/STUDY/weizhcode-python/tests/test_conversation.py -k loop_exchange_contract -q；必须实际收集用例且全部通过。

**覆盖：** F6、N5、AC8。

### T10：修正混合诊断的真实性

**文件：** `D:/STUDY/weizhcode-python/src/weizhcode/providers/base.py`、`D:/STUDY/weizhcode-python/src/weizhcode/conversation.py`、`D:/STUDY/weizhcode-python/tests/test_conversation.py`、`D:/STUDY/weizhcode-python/tests/test_provider_tools.py`

**依赖：** T9

**步骤：**

1. 诊断按调用列出真实成功、失败、execution_started、清理状态和原始可识别 ID，删除笼统的整批未执行表述。
2. 三协议编码使用有界脱敏副本；正常交换保留原生格式，不伪造 API ID、不泄漏应用私有参数。

**验证：** 运行 uv run python -m pytest D:/STUDY/weizhcode-python/tests/test_conversation.py D:/STUDY/weizhcode-python/tests/test_provider_tools.py -k mixed_diagnostic -q；三协议样本都收集且成功/失败事实完整。

**覆盖：** F4、F6、F11、N6、AC5、AC8、AC16。

### T11：增加应用来源的停止收尾

**文件：** `D:/STUDY/weizhcode-python/src/weizhcode/conversation.py`、`D:/STUDY/weizhcode-python/tests/test_conversation.py`

**依赖：** T9

**步骤：**

1. 增加 add_stop_notice，记录应用来源、run_id/原因，明确任务可能未完成或副作用可能存在。
2. 验证取消/上限/错误消息不重复追加，不把 last_role==assistant 当作已有通知，也不虚构模型完成结论。

**验证：** 新增/保留以 application_stop_notice 命名的断言并运行 uv run python -m pytest D:/STUDY/weizhcode-python/tests/test_conversation.py -k application_stop_notice -q；必须实际收集用例且全部通过。

**覆盖：** F2、F6、AC2、AC8。

### T12：解析 Anthropic 累计用量

**文件：** `D:/STUDY/weizhcode-python/src/weizhcode/providers/anthropic.py`、`D:/STUDY/weizhcode-python/tests/test_provider_events.py`

**依赖：** T2、T4

**步骤：**

1. 从 message_start 建快照，message_delta 更新累计值，message_stop 完整终止后标完整。
2. 输入计数正确合并缓存创建/命中，输出不重复累加，缺失/真实零/重复/递减统计有独立断言；不显示思考。

**验证：** 新增/保留以 anthropic_usage 命名的断言并运行 uv run python -m pytest D:/STUDY/weizhcode-python/tests/test_provider_events.py -k anthropic_usage -q；必须实际收集用例且全部通过。

**覆盖：** F8、F11、AC11、AC16。

### T13：解析 Responses 用量

**文件：** `D:/STUDY/weizhcode-python/src/weizhcode/providers/openai.py`、`D:/STUDY/weizhcode-python/tests/test_provider_events.py`

**依赖：** T2、T4

**步骤：**

1. 从 response.completed.response.usage 取得输入/输出；failed/incomplete 的已知值保留但不标完整。
2. cached/reasoning 明细不重复加入，不给 Responses 添加 stream_options；store=False 和完整输出项回放不退化。

**验证：** 新增/保留以 responses_usage 命名的断言并运行 uv run python -m pytest D:/STUDY/weizhcode-python/tests/test_provider_events.py -k responses_usage -q；必须实际收集用例且全部通过。

**覆盖：** F8、F11、AC11、AC16。

### T14：解析千问末包用量

**文件：** `D:/STUDY/weizhcode-python/src/weizhcode/providers/qwen.py`、`D:/STUDY/weizhcode-python/tests/test_provider_events.py`

**依赖：** T2、T4

**步骤：**

1. 请求 include_usage；先读取 usage 再分派 choices，允许末包 choices=[]。
2. prompt/completion 映射输入/输出，total 不另加；重复包、缺失包和 [DONE] 成功门槛分别验证。

**验证：** 新增/保留以 qwen_usage 命名的断言并运行 uv run python -m pytest D:/STUDY/weizhcode-python/tests/test_provider_events.py -k qwen_usage -q；必须实际收集用例且全部通过。

**覆盖：** F8、F11、AC11、AC16。

### T15：实现正文双路收集

**文件：** `D:/STUDY/weizhcode-python/src/weizhcode/stream_collector.py`、`D:/STUDY/weizhcode-python/tests/test_stream_collector.py`

**依赖：** T3、T4

**步骤：**

1. 新增 StreamCollector.collect：即时发安全正文事件，同时维护本次 StreamState，不修改历史。
2. 以 done.assistant_message 为完整结果权威，tool_call 事件不再次扩展该调用列表；消息/载荷防御性复制。

**验证：** 新增/保留以 collector_dual_path 命名的断言并运行 uv run python -m pytest D:/STUDY/weizhcode-python/tests/test_stream_collector.py -k collector_dual_path -q；必须实际收集用例且全部通过。

**覆盖：** F3、F4、N6、AC5、AC10。

### T16：实现完整结束与空正文边界

**文件：** `D:/STUDY/weizhcode-python/src/weizhcode/stream_collector.py`、`D:/STUDY/weizhcode-python/tests/test_stream_collector.py`

**依赖：** T15

**步骤：**

1. 覆盖碎片 JSON、块/参数结束后 EOF、流错误/截断，确保无成功 RoundResponse 就无可执行调用。
2. 核对增量与最终正文；只在 done 提供正文时补发，不重复，出现冲突明确失败而不伪装成功。

**验证：** 新增/保留以 collector_completion_gate 命名的断言并运行 uv run python -m pytest D:/STUDY/weizhcode-python/tests/test_stream_collector.py -k collector_completion_gate -q；必须实际收集用例且全部通过。

**覆盖：** F2、F4、AC2、AC5。

### T17：让无 token 的网络等待可取消

**文件：** `D:/STUDY/weizhcode-python/src/weizhcode/stream_collector.py`、`D:/STUDY/weizhcode-python/tests/test_stream_collector.py`

**依赖：** T16

**步骤：**

1. 用 Task + FIRST_COMPLETED 监督 anext 与取消；取消时先停止并 await anext，再关闭生成器/HTTP 流。
2. 覆盖首 token 前、正文中和完成/取消同 tick，取消不等下一包，也不触发 async generator already running。

**验证：** 新增/保留以 collector_cancellation 命名的断言并运行 uv run python -m pytest D:/STUDY/weizhcode-python/tests/test_stream_collector.py -k collector_cancellation -q；必须实际收集用例且全部通过。

**覆盖：** F7、N1、N2、AC9。

### T18：合并请求内用量快照

**文件：** `D:/STUDY/weizhcode-python/src/weizhcode/stream_collector.py`、`D:/STUDY/weizhcode-python/tests/test_stream_collector.py`

**依赖：** T12、T13、T14、T17

**步骤：**

1. 收集同请求累计/重复 usage，保留最新可信字段与真实零；错误/取消时留已知部分并标不完整。
2. 非法统计不覆盖可信值，不在 Collector 跨请求加总；与 complete RoundResponse/失败 StreamState 都能取到快照。

**验证：** 新增/保留以 collector_usage_snapshot 命名的断言并运行 uv run python -m pytest D:/STUDY/weizhcode-python/tests/test_stream_collector.py -k collector_usage_snapshot -q；必须实际收集用例且全部通过。

**覆盖：** F8、N5、AC11。

### T19：实现有界安全事件通道

**文件：** `D:/STUDY/weizhcode-python/src/weizhcode/turn_runner.py`、`D:/STUDY/weizhcode-python/tests/test_turn_runner.py`

**依赖：** T4、T5

**步骤：**

1. 在未启用的新驱动路径实现容量 128 队列、受监督 producer 和独立结束信号；保留旧正式路径到 T49。
2. emit 使用可见安全副本，不修改原始执行参数；任务/请求 ID 带入所有本轮事件，内部思考不进入通道。

**验证：** 新增/保留以 bounded_event_channel 命名的断言并运行 uv run python -m pytest D:/STUDY/weizhcode-python/tests/test_turn_runner.py -k bounded_event_channel -q；必须实际收集用例且全部通过。

**覆盖：** F3、N3、N6、AC10、AC15。

### T20：验证消费者关闭不阻断收尾

**文件：** `D:/STUDY/weizhcode-python/src/weizhcode/turn_runner.py`、`D:/STUDY/weizhcode-python/tests/test_turn_runner.py`

**依赖：** T19

**步骤：**

1. 消费者离开时设置 consumer_closed 和本轮取消，取消/await queue 等待及私有驱动，观察异常。
2. 覆盖队列已满、producer 失败和提前 aclose；收尾不依赖放入 sentinel 或成功显示结束消息。

**验证：** 新增/保留以 event_channel_shutdown 命名的断言并运行 uv run python -m pytest D:/STUDY/weizhcode-python/tests/test_turn_runner.py -k event_channel_shutdown -q；必须实际收集用例且全部通过。

**覆盖：** F3、F7、N1、N5、AC9、AC10。

### T21：增加新的无审批 execute 路径

**文件：** `D:/STUDY/weizhcode-python/src/weizhcode/tools/executor.py`、`D:/STUDY/weizhcode-python/tests/test_tool_executor.py`

**依赖：** T5、T7

**步骤：**

1. 新增 Plan 定义的 execute(slot, mode, cancel, emit)，校验后经真实 start/prepare/execute，首先使用受控临时文件验证正常结果。
2. 结果先归一化写槽再收尾；旧 run 仅留给尚未切换的旧入口，T49 与全部旧调用一并移除，不添加自动批准回调。

**验证：** 新增/保留 loop_execute_basic 用例并运行 uv run python -m pytest D:/STUDY/weizhcode-python/tests/test_tool_executor.py -k loop_execute_basic -q；必须实际收集且全部通过。

**覆盖：** F1、F6、N4、AC1、AC7。

### T22：实现执行端计划模式门禁

**文件：** `D:/STUDY/weizhcode-python/src/weizhcode/tools/executor.py`、`D:/STUDY/weizhcode-python/tests/test_tool_executor.py`

**依赖：** T21

**步骤：**

1. plan 写/改/命令在创建 worker 前返回 TOOL_NOT_ALLOWED；未知、非法参数、已取消也在适当阶段短路。
2. 即使调用方直接构造副作用调用也不能绕过；断言 worker_factory 零次、父目录/文件/命令标记不变。

**验证：** 新增/保留 plan_execution_gate 用例并运行 uv run python -m pytest D:/STUDY/weizhcode-python/tests/test_tool_executor.py -k plan_execution_gate -q；必须实际收集且全部通过。

**覆盖：** F10、N6、AC12。

### T23：在新路径保留共享工具预算

**文件：** `D:/STUDY/weizhcode-python/src/weizhcode/tools/executor.py`、`D:/STUDY/weizhcode-python/tests/test_tool_executor.py`

**依赖：** T21

**步骤：**

1. 准备和执行累计一个 30 秒预算，不按阶段重置；有限输出、退出码、错误与截断逻辑不退化。
2. 内部短预算覆盖准备耗时+执行耗时；不再有审批等待计时逻辑，也不改变生产常量。

**验证：** 新增/保留 loop_tool_budget 用例并运行 uv run python -m pytest D:/STUDY/weizhcode-python/tests/test_tool_executor.py -k loop_tool_budget -q；必须实际收集且全部通过。

**覆盖：** F6、N1、N3、AC7、AC15。

### T24：保留取消时已确认的执行事实

**文件：** `D:/STUDY/weizhcode-python/src/weizhcode/tools/executor.py`、`D:/STUDY/weizhcode-python/tests/test_tool_executor.py`

**依赖：** T23

**步骤：**

1. 工具结果收到后先同步写入自己的槽，再等待 cleanup；受控取消返回已确认结果或准确取消状态。
2. 覆盖 result 到达与 cancel 同 tick、结果到达但清理阻塞、未开始/已发 execute 未得结果；不伪称无副作用或回滚。

**验证：** 新增/保留 cancel_preserves_result 用例并运行 uv run python -m pytest D:/STUDY/weizhcode-python/tests/test_tool_executor.py -k cancel_preserves_result -q；必须实际收集且全部通过。

**覆盖：** F6、F7、N5、AC8、AC9。

### T25：验证实际进程与临时资源取消清理

**文件：** `D:/STUDY/weizhcode-python/src/weizhcode/tools/process.py`、`D:/STUDY/weizhcode-python/src/weizhcode/tools/worker.py`、`D:/STUDY/weizhcode-python/src/weizhcode/tools/executor.py`、`D:/STUDY/weizhcode-python/tests/test_tool_executor.py`

**依赖：** T24

**步骤：**

1. 保持独立 Worker 的幂等关闭、Windows Job/POSIX 进程组与启动中退出保护；仅作取消场景必要修正。
2. 用临时目录实际暂停准备/命令/写入登记过程后取消，检查本轮父子进程与临时文件清理、原文件与用户预置文件保留。

**验证：** 新增/保留 loop_process_cleanup 用例并运行 uv run python -m pytest D:/STUDY/weizhcode-python/tests/test_tool_executor.py -k loop_process_cleanup -q；必须实际收集且全部通过。

**覆盖：** F7、N1、N4、AC9、AC15。

### T26：区分清理故障与普通工具失败

**文件：** `D:/STUDY/weizhcode-python/src/weizhcode/tools/executor.py`、`D:/STUDY/weizhcode-python/tests/test_tool_executor.py`

**依赖：** T24、T25

**步骤：**

1. 给槽记录 cleanup_error；成功事实不因清理故障被改写，PROCESS_CONTROL_FAILED 仍明确上报。
2. 普通文件/命令失败按结果返回；不能确认进程回收时向协调器报告基础设施故障，不伪装取消成功。

**验证：** 新增/保留 cleanup_infrastructure_failure 用例并运行 uv run python -m pytest D:/STUDY/weizhcode-python/tests/test_tool_executor.py -k cleanup_infrastructure_failure -q；必须实际收集且全部通过。

**覆盖：** F6、N1、N5、AC7、AC8、AC9。

### T27：建立调度槽与调用结构预检

**文件：** `D:/STUDY/weizhcode-python/src/weizhcode/tool_scheduler.py`、`D:/STUDY/weizhcode-python/tests/test_tool_scheduler.py`

**依赖：** T5、T7、T22

**步骤：**

1. 为全部调用按原序建立槽；受影响的重复 API ID 全部拒绝，缺失/非法 ID、名称、JSON 与未知工具各有准确结果。
2. 独立合法调用仍可执行；UI 用 local_id，不修补 API ID；预检失败项不启动 worker。

**验证：** 新增/保留 scheduler_preflight 用例并运行 uv run python -m pytest D:/STUDY/weizhcode-python/tests/test_tool_scheduler.py -k scheduler_preflight -q；必须实际收集且全部通过。

**覆盖：** F4、F5、F6、AC5、AC6、AC8。

### T28：实现连续只读批并发

**文件：** `D:/STUDY/weizhcode-python/src/weizhcode/tool_scheduler.py`、`D:/STUDY/weizhcode-python/tests/test_tool_scheduler.py`

**依赖：** T27、T21

**步骤：**

1. 识别最长连续只读区间，独立任务/槽执行；同名工具也保持独立结果。
2. 用 barrier 与并发计数证明至少两个执行窗口重叠；逆完成顺序仍按原序返回。

**验证：** 新增/保留 readonly_batch_overlap 用例并运行 uv run python -m pytest D:/STUDY/weizhcode-python/tests/test_tool_scheduler.py -k readonly_batch_overlap -q；必须实际收集且全部通过。

**覆盖：** F5、N5、AC6。

### T29：限制只读活动工具最多四个

**文件：** `D:/STUDY/weizhcode-python/src/weizhcode/tool_scheduler.py`、`D:/STUDY/weizhcode-python/tests/test_tool_scheduler.py`

**依赖：** T28

**步骤：**

1. 容量 4 的 Semaphore 在进入 Executor/创建 worker 前获取；排队不计工具计算预算。
2. 验证峰值不超过 4、等待许可时取消零启动、取消后获许可也不能迟到执行；不增加用户配置。

**验证：** 新增/保留 readonly_concurrency_limit 用例并运行 uv run python -m pytest D:/STUDY/weizhcode-python/tests/test_tool_scheduler.py -k readonly_concurrency_limit -q；必须实际收集且全部通过。

**覆盖：** F5、F7、N1、N5、AC6、AC9。

### T30：建立副作用串行屏障

**文件：** `D:/STUDY/weizhcode-python/src/weizhcode/tool_scheduler.py`、`D:/STUDY/weizhcode-python/tests/test_tool_scheduler.py`

**依赖：** T29

**步骤：**

1. 副作用、未知、受影响非法调用分别形成串行位置；不跨这些位置合并前后只读批。
2. 对 [读,读,写,读,改,命令] 记录开始/结束与实际标记，证明写后读取不会提前，写/改/命令不会重叠。

**验证：** 新增/保留 side_effect_batch_barriers 用例并运行 uv run python -m pytest D:/STUDY/weizhcode-python/tests/test_tool_scheduler.py -k side_effect_batch_barriers -q；必须实际收集且全部通过。

**覆盖：** F5、N5、AC6。

### T31：监督并发批取消并补全结果

**文件：** `D:/STUDY/weizhcode-python/src/weizhcode/tool_scheduler.py`、`D:/STUDY/weizhcode-python/tests/test_tool_scheduler.py`

**依赖：** T25、T26、T30

**步骤：**

1. 等待当前批完成或取消；取消活动任务、await 实际回收、阻止后续批，保留已写槽的结果。
2. 全部缺结果槽补 TOOL_CANCELLED，区分未开始与结果不确认；重复取消不打断 cleanup。

**验证：** 新增/保留 batch_cancellation_results 用例并运行 uv run python -m pytest D:/STUDY/weizhcode-python/tests/test_tool_scheduler.py -k batch_cancellation_results -q；必须实际收集且全部通过。

**覆盖：** F6、F7、N1、N5、AC8、AC9。

### T32：保证批事件按调用顺序展示

**文件：** `D:/STUDY/weizhcode-python/src/weizhcode/tool_scheduler.py`、`D:/STUDY/weizhcode-python/tests/test_tool_scheduler.py`

**依赖：** T31

**步骤：**

1. 批开始前按序发 tool_start，按 local_id 更新 preparing/running；批结束后按原序发 tool_result。
2. 失败与取消同样维持结果顺序；预检失败项和等待许可项都有明确状态，不制造重复记录行。

**验证：** 新增/保留 batch_event_order 用例并运行 uv run python -m pytest D:/STUDY/weizhcode-python/tests/test_tool_scheduler.py -k batch_event_order -q；必须实际收集且全部通过。

**覆盖：** F3、F5、F9、AC6、AC10、AC14。

### T33：建立新的 Loop 驱动和单任务占用

**文件：** `D:/STUDY/weizhcode-python/src/weizhcode/turn_runner.py`、`D:/STUDY/weizhcode-python/tests/test_turn_runner.py`

**依赖：** T8、T11、T18、T20、T32

**步骤：**

1. 实现新私有驱动、RunContext 拥有者与立即占用逻辑；通过 Collector/Scheduler 注入测试，不在 T49 前切换生产 UI 入口。
2. 纯文本只一次请求；无工具空回复明确占位，只有一个 turn_done；busy/closed 拒绝不误恢复活动任务或追加历史。

**验证：** 新增/保留 loop_single_flight 用例并运行 uv run python -m pytest D:/STUDY/weizhcode-python/tests/test_turn_runner.py -k loop_single_flight -q；必须实际收集且全部通过。

**覆盖：** F1、F2、F3、N5、AC2、AC10、AC14。

### T34：打通跨多轮工具与原子历史

**文件：** `D:/STUDY/weizhcode-python/src/weizhcode/turn_runner.py`、`D:/STUDY/weizhcode-python/src/weizhcode/conversation.py`、`D:/STUDY/weizhcode-python/tests/test_turn_runner.py`

**依赖：** T33、T10

**步骤：**

1. read→write→read/check→text 多轮脚本全程 allow_tools=True，准备完整结果后一次性提交交换。
2. 工具前导文本、结果、下一模型请求顺序正确；只保存实际工具级结果，不用 UI 摘要；不走旧固定 final 分支。

**验证：** 新增/保留 loop_multistep_history 用例并运行 uv run python -m pytest D:/STUDY/weizhcode-python/tests/test_turn_runner.py -k loop_multistep_history -q；必须实际收集且全部通过。

**覆盖：** F1、F6、AC1、AC8。

### T35：落实 25 轮停止口径

**文件：** `D:/STUDY/weizhcode-python/src/weizhcode/turn_runner.py`、`D:/STUDY/weizhcode-python/tests/test_turn_runner.py`

**依赖：** T34

**步骤：**

1. 恒工具脚本最多 25 次请求；第 25 轮工具处理和历史结果保留，随后应用通知，不发第 26 次总结。
2. 覆盖第 25 轮自然完成、空回复、用户取消与上限同 tick，取消优先；低上限仅从内部测试构造注入。

**验证：** 新增/保留 iteration_limit_boundary 用例并运行 uv run python -m pytest D:/STUDY/weizhcode-python/tests/test_turn_runner.py -k iteration_limit_boundary -q；必须实际收集且全部通过。

**覆盖：** F2、AC2、AC3、AC9。

### T36：落实三轮全未知的停止与重置

**文件：** `D:/STUDY/weizhcode-python/src/weizhcode/turn_runner.py`、`D:/STUDY/weizhcode-python/tests/test_turn_runner.py`

**依赖：** T35

**步骤：**

1. 整轮全部未注册才累计；包含已注册工具就重置，即使参数或执行失败，计数不跨任务。
2. 验证三轮后结果齐全且明确停止，不把只读标志、未知调用条数或单个失败误当计数条件。

**验证：** 新增/保留 unknown_round_threshold 用例并运行 uv run python -m pytest D:/STUDY/weizhcode-python/tests/test_turn_runner.py -k unknown_round_threshold -q；必须实际收集且全部通过。

**覆盖：** F2、F6、AC4、AC8。

### T37：处理流错误与普通工具失败

**文件：** `D:/STUDY/weizhcode-python/src/weizhcode/turn_runner.py`、`D:/STUDY/weizhcode-python/src/weizhcode/conversation.py`、`D:/STUDY/weizhcode-python/tests/test_turn_runner.py`

**依赖：** T34、T26

**步骤：**

1. 普通工具错误回传后允许下一轮纠正；流错误/基础设施故障停止，原先已执行的交换保留。
2. 覆盖初次残缺流、后续流失败、结果不足/内部异常；不自动重试请求或重做副作用，下一任务可继续。

**验证：** 新增/保留 loop_error_recovery 用例并运行 uv run python -m pytest D:/STUDY/weizhcode-python/tests/test_turn_runner.py -k loop_error_recovery -q；必须实际收集且全部通过。

**覆盖：** F2、F4、F6、N5、AC5、AC7、AC8。

### T38：每请求结算一次并发布累计快照

**文件：** `D:/STUDY/weizhcode-python/src/weizhcode/turn_runner.py`、`D:/STUDY/weizhcode-python/tests/test_turn_runner.py`

**依赖：** T18、T37

**步骤：**

1. 本地 request_id 去重，正常/错误/取消的已知 usage 只结算一次，跨用户任务累计、不跨进程持久化。
2. 无数据与真实零正确区分，取消保留部分用量并标不完整；UI 收到累计快照而不是待叠加 delta。

**验证：** 新增/保留 session_usage_settlement 用例并运行 uv run python -m pytest D:/STUDY/weizhcode-python/tests/test_turn_runner.py -k session_usage_settlement -q；必须实际收集且全部通过。

**覆盖：** F8、AC11。

### T39：接入模式冻结与 Plan 工具集合

**文件：** `D:/STUDY/weizhcode-python/src/weizhcode/turn_runner.py`、`D:/STUDY/weizhcode-python/src/weizhcode/prompts.py`、`D:/STUDY/weizhcode-python/tests/test_turn_runner.py`

**依赖：** T34、T7、T8

**步骤：**

1. 默认 normal；空闲 set_mode(plan) 返回事件不发请求，忙碌返回 busy 通知且模式不变。
2. 每任务固定 3/6 工具集合与系统说明；/do 的内部执行指令切回 normal，未知/缺计划不凭空执行本地预置动作。

**验证：** 新增/保留 loop_mode_control 用例并运行 uv run python -m pytest D:/STUDY/weizhcode-python/tests/test_turn_runner.py -k loop_mode_control -q；必须实际收集且全部通过。

**覆盖：** F10、AC12、AC13。

### T40：完成本轮取消和应用退出生命周期

**文件：** `D:/STUDY/weizhcode-python/src/weizhcode/turn_runner.py`、`D:/STUDY/weizhcode-python/tests/test_turn_runner.py`

**依赖：** T20、T31、T37、T38、T39

**步骤：**

1. cancel_current 只置事件、收尾后恢复 idle；aclose 停止接收、取消并等待驱动、最后永久关闭 Executor。
2. 覆盖消费者离开、首次 token 前、工具中、历史刚提交、重复取消/关闭；同一 Runner/Executor 取消后仍能跑下一任务。

**验证：** 新增/保留 loop_lifecycle_reuse 用例并运行 uv run python -m pytest D:/STUDY/weizhcode-python/tests/test_turn_runner.py -k loop_lifecycle_reuse -q；必须实际收集且全部通过。

**覆盖：** F7、N1、N5、AC8、AC9。

### T41：准备多工具和取消显示组件

**文件：** `D:/STUDY/weizhcode-python/src/weizhcode/tool_ui.py`、`D:/STUDY/weizhcode-python/tests/test_tool_tui.py`

**依赖：** T4、T5、T32

**步骤：**

1. ToolCallView 按 local_id 呈现 waiting/preparing/running/完成/失败/取消，同名调用不串位。
2. 保留 8 行/1000 字符摘要与安全文本；新路径不使用审批界面，旧按钮结构只在 T49 统一移除以维持迁移完整性。

**验证：** 新增/保留 loop_tool_view 用例并运行 uv run python -m pytest D:/STUDY/weizhcode-python/tests/test_tool_tui.py -k loop_tool_view -q；必须实际收集且全部通过。

**覆盖：** F9、N3、N6、AC10、AC14、AC15。

### T42：准备统一事件消费路径

**文件：** `D:/STUDY/weizhcode-python/src/weizhcode/tui.py`、`D:/STUDY/weizhcode-python/tests/test_tui.py`、`D:/STUDY/weizhcode-python/tests/test_tool_tui.py`

**依赖：** T41、T40

**步骤：**

1. 新增统一事件消费与显示方法，按 run_id/iteration 分正文、按 local_id 更新工具，通知/错误不冒充成功。
2. 先用 FakeRunner 驱动此路径，不提前切换旧 submit；无正文 turn_done、错误后收尾与并发结果顺序有断言。

**验证：** 运行 uv run python -m pytest D:/STUDY/weizhcode-python/tests/test_tui.py D:/STUDY/weizhcode-python/tests/test_tool_tui.py -k loop_event_ui -q，验证记录顺序和 idle 恢复。

**覆盖：** F3、F9、N2、AC10、AC14。

### T43：准备模式、进度与用量显示

**文件：** `D:/STUDY/weizhcode-python/src/weizhcode/tui.py`、`D:/STUDY/weizhcode-python/tests/test_tui.py`

**依赖：** T42、T38、T39

**步骤：**

1. 接收 mode/iteration/usage 事件，显示模式、轮次、模型等待/取消清理和累计快照，不由 UI 再累加。
2. 显示真实 6 tools/0 MCP；/plan 不发请求，/do 使用执行指令，缺统计显示未知/不完整；提交路由在 T49 统一启用。

**验证：** 新增/保留 loop_mode_usage_ui 用例并运行 uv run python -m pytest D:/STUDY/weizhcode-python/tests/test_tui.py -k loop_mode_usage_ui -q；必须实际收集且全部通过。

**覆盖：** F8、F9、F10、AC11、AC12、AC13、AC14。

### T44：准备优先取消按键和退出动作

**文件：** `D:/STUDY/weizhcode-python/src/weizhcode/tui.py`、`D:/STUDY/weizhcode-python/tests/test_tui.py`、`D:/STUDY/weizhcode-python/tests/test_tool_tui.py`

**依赖：** T42、T40

**步骤：**

1. 定义 Esc/Ctrl+C 的 priority 绑定与分离 action；运行时请求 cancel，空闲 Ctrl+C 退出，Ctrl+D 与退出命令清理整应用。
2. 用 FakeRunner 测焦点在输入框、重复取消、清理期间再次 Ctrl+C；绑定和正式入口同 T49 启用，不让旧执行路径失去退出控制。

**验证：** 运行 uv run python -m pytest D:/STUDY/weizhcode-python/tests/test_tui.py D:/STUDY/weizhcode-python/tests/test_tool_tui.py -k loop_cancel_keys -q，取消不退应用、退出会等待收尾。

**覆盖：** F7、N1、N2、AC9、AC14。

### T45：准备防重入、草稿与晚到事件隔离

**文件：** `D:/STUDY/weizhcode-python/src/weizhcode/tui.py`、`D:/STUDY/weizhcode-python/tests/test_tool_tui.py`

**依赖：** T43、T44

**步骤：**

1. 接受任务前立即建立占用；运行/清理时重复问题、/plan、/do 都不改变活动任务，也不清空草稿。
2. 旧 run_id 的 tool/usage/done 不能覆盖新任务；已结束后台任务引用及时释放，对话组件仍能回看。

**验证：** 新增/保留 loop_ui_race_isolation 用例并运行 uv run python -m pytest D:/STUDY/weizhcode-python/tests/test_tool_tui.py -k loop_ui_race_isolation -q；必须实际收集且全部通过。

**覆盖：** F7、F9、F10、N5、AC9、AC14。

### T46：验证新事件安全出口

**文件：** `D:/STUDY/weizhcode-python/src/weizhcode/turn_runner.py`、`D:/STUDY/weizhcode-python/src/weizhcode/tool_ui.py`、`D:/STUDY/weizhcode-python/src/weizhcode/redaction.py`、`D:/STUDY/weizhcode-python/tests/test_redaction.py`、`D:/STUDY/weizhcode-python/tests/test_turn_runner.py`、`D:/STUDY/weizhcode-python/tests/test_tool_tui.py`

**依赖：** T19、T41、T45

**步骤：**

1. 对文本跨片、工具名/参数、取消/错误、诊断和结果注入已知假密钥与控制字符，事件只能含安全副本。
2. 真实写入/命令参数保持原值；结果脱敏后预算仍合格，私有签名/密文不显示，不宣称识别所有秘密。

**验证：** 运行 uv run python -m pytest D:/STUDY/weizhcode-python/tests/test_redaction.py D:/STUDY/weizhcode-python/tests/test_turn_runner.py D:/STUDY/weizhcode-python/tests/test_tool_tui.py -k loop_security_pipeline -q，检查安全事件与实际字节分别正确。

**覆盖：** N3、N6、AC15。

### T47：准备唯一构造接线

**文件：** `D:/STUDY/weizhcode-python/src/weizhcode/cli.py`、`D:/STUDY/weizhcode-python/src/weizhcode/tui.py`、`D:/STUDY/weizhcode-python/tests/test_cli.py`

**依赖：** T40、T45

**步骤：**

1. 为 Collector/Scheduler/Runner 建立一致依赖，TUI 测试缺省构造与 cli 共用相同语义；不引入可绕过门禁的备用执行入口。
2. 配置失败面板、默认模型与版本/目录保留；只用已解析密钥建立 Redactor，不读取未选供应商缺失环境变量。

**验证：** 新增/保留 loop_startup_wiring 用例并运行 uv run python -m pytest D:/STUDY/weizhcode-python/tests/test_cli.py -k loop_startup_wiring -q；必须实际收集且全部通过。

**覆盖：** F11、N7、AC16。

### T48：放开协议多调用而非放开执行安全

**文件：** `D:/STUDY/weizhcode-python/src/weizhcode/providers/anthropic.py`、`D:/STUDY/weizhcode-python/src/weizhcode/providers/openai.py`、`D:/STUDY/weizhcode-python/src/weizhcode/providers/qwen.py`、`D:/STUDY/weizhcode-python/tests/test_provider_tools.py`

**依赖：** T12、T13、T14、T32

**步骤：**

1. Anthropic 去掉禁并行，Responses parallel_tool_calls=True；千问不强加未知端点参数，三者仍 tools auto。
2. 验证连续多轮可继续返回多个调用，plan 只注入三定义；原有分片、签名、加密项、store=False 和成功终止门槛保留。本任务属于 T49 同一切换组，不单独上线。

**验证：** 新增/保留 loop_provider_payload 用例并运行 uv run python -m pytest D:/STUDY/weizhcode-python/tests/test_provider_tools.py -k loop_provider_payload -q；必须实际收集且全部通过。

**覆盖：** F1、F4、F5、F11、AC1、AC5、AC6、AC16。

### T49：原子切换正式入口并删除全部过渡契约

**文件：** `D:/STUDY/weizhcode-python/src/weizhcode/models.py`、`D:/STUDY/weizhcode-python/src/weizhcode/turn_runner.py`、`D:/STUDY/weizhcode-python/src/weizhcode/tools/executor.py`、`D:/STUDY/weizhcode-python/src/weizhcode/tools/base.py`、`D:/STUDY/weizhcode-python/src/weizhcode/tools/read_file.py`、`D:/STUDY/weizhcode-python/src/weizhcode/tools/find_files.py`、`D:/STUDY/weizhcode-python/src/weizhcode/tools/search_content.py`、`D:/STUDY/weizhcode-python/src/weizhcode/tools/write_file.py`、`D:/STUDY/weizhcode-python/src/weizhcode/tools/edit_file.py`、`D:/STUDY/weizhcode-python/src/weizhcode/tools/run_command.py`、`D:/STUDY/weizhcode-python/src/weizhcode/tui.py`、`D:/STUDY/weizhcode-python/src/weizhcode/tool_ui.py`、`D:/STUDY/weizhcode-python/src/weizhcode/prompts.py`、`D:/STUDY/weizhcode-python/src/weizhcode/cli.py`、`D:/STUDY/weizhcode-python/tests/test_turn_runner.py`、`D:/STUDY/weizhcode-python/tests/test_tool_executor.py`、`D:/STUDY/weizhcode-python/tests/test_tool_registry.py`、`D:/STUDY/weizhcode-python/tests/test_tui.py`、`D:/STUDY/weizhcode-python/tests/test_tool_tui.py`、`D:/STUDY/weizhcode-python/tests/test_cli.py`、`D:/STUDY/weizhcode-python/tests/test_protocol_integration.py`、`D:/STUDY/weizhcode-python/tests/manual_tool_smoke.py`

**依赖：** T34、T35、T36、T37、T38、T39、T40、T41、T42、T43、T44、T45、T46、T47、T48

**步骤：**

1. 只做已准备组件的正式接线与调用方机械迁移：run 新接口、Executor.execute、统一事件消费及新按键/命令一起启用；所有 FakeRunner/FakeExecutor 与手动脚本同步。
2. 删除旧单工具/固定 final 分支、Executor.run、approve 回调、ApprovalRequest、requires_confirmation、approval/phase 字段、审批按钮/Future/Decision 和临时别名；按第 4 节迁移清单替换仅与新 Spec 冲突的旧断言。

**验证：** 运行 uv run python -m compileall src tests 和全量 uv run python -m pytest -q；全部已完成任务用例与保留回归通过后才完成此切换。若机械接线超出小任务，将准备工作拆回 T41～T48，不留下签名不匹配、隐藏 skip 或长期双路径。

**覆盖：** F1、F3、F5、F7、F9、F10、F11、N7、AC1、AC9、AC10、AC12、AC13、AC16。

### T50：验证正式路径无审批且取消后可复用

**文件：** `D:/STUDY/weizhcode-python/src/weizhcode/turn_runner.py`、`D:/STUDY/weizhcode-python/src/weizhcode/tui.py`、`D:/STUDY/weizhcode-python/tests/test_tool_executor.py`、`D:/STUDY/weizhcode-python/tests/test_tool_tui.py`、`D:/STUDY/weizhcode-python/tests/test_turn_runner.py`

**依赖：** T49

**步骤：**

1. 从正式入口实际写/改/命令均无需 approval handler；plan 直接强行副作用仍零 worker，取消仅关闭本轮。
2. 覆盖工具普通失败继续、结果到达后取消、应用退出永久关闭；无悬空调用，下一任务与同一 Executor 可继续。

**验证：** 运行 uv run python -m pytest D:/STUDY/weizhcode-python/tests/test_tool_executor.py D:/STUDY/weizhcode-python/tests/test_tool_tui.py D:/STUDY/weizhcode-python/tests/test_turn_runner.py -k loop_production_path -q。

**覆盖：** F6、F7、F10、N1、AC7、AC8、AC9、AC12、AC13。

### T51：回归文件、搜索、命令与预算行为

**文件：** `D:/STUDY/weizhcode-python/tests/test_file_tools.py`、`D:/STUDY/weizhcode-python/tests/test_search_tools.py`、`D:/STUDY/weizhcode-python/tests/test_command_tool.py`、`D:/STUDY/weizhcode-python/tests/test_tool_registry.py`、`D:/STUDY/weizhcode-python/tests/test_tool_executor.py`

**依赖：** T50

**步骤：**

1. 运行 UTF-8/BOM/LF/CRLF、唯一匹配/零次多次、目标变化、临时文件归属、忽略/隐藏/直接路径、二进制/长行等现有断言。
2. 验证读取200行、找文件200、搜内容100、序列化20000字符、命令双流排空/退出码/目录不继承；不为新 Loop 放宽工具约束。

**验证：** 运行上述五个文件的完整 pytest；只有与审批接口相关的调用方式可迁移，原有安全断言不得删除或静默跳过。

**覆盖：** N1、N3、N4、N6、AC7、AC15。

### T52：验证大结果与长历史的诚实反馈

**文件：** `D:/STUDY/weizhcode-python/tests/test_turn_runner.py`、`D:/STUDY/weizhcode-python/tests/test_tool_tui.py`、`D:/STUDY/weizhcode-python/tests/test_provider_tools.py`、`D:/STUDY/weizhcode-python/tests/test_redaction.py`

**依赖：** T51

**步骤：**

1. 在多轮大文件/长输出中对比工具真实结果和UI短摘要，确认截断标记与统计仍有效，正文安全副本不污染操作参数。
2. 构造后端上下文长度错误，停止且保留已执行事实，不偷偷压缩/裁剪历史、不重试副作用，也不宣称结果上限保证无限上下文。

**验证：** 运行 uv run python -m pytest D:/STUDY/weizhcode-python/tests/test_turn_runner.py D:/STUDY/weizhcode-python/tests/test_tool_tui.py D:/STUDY/weizhcode-python/tests/test_provider_tools.py D:/STUDY/weizhcode-python/tests/test_redaction.py -k loop_budget_context -q。

**覆盖：** F2、F6、N3、N6、AC8、AC15。

### T53：跑三协议同组端到端模拟集成

**文件：** `D:/STUDY/weizhcode-python/tests/test_protocol_integration.py`、`D:/STUDY/weizhcode-python/tests/test_provider_tools.py`、`D:/STUDY/weizhcode-python/tests/test_turn_runner.py`、`D:/STUDY/weizhcode-python/tests/test_conversation.py`

**依赖：** T50、T52

**步骤：**

1. 三协议参数化使用真实临时文件/工作进程，执行多步成功、错误后调整、混合诊断、全未知停止、取消和后续上下文。
2. 检查每轮 tools/模式/历史/usage 与执行次数，Responses 不套 Chat Completions，签名/加密回放不重复、不显示。

**验证：** 运行 uv run python -m pytest D:/STUDY/weizhcode-python/tests/test_protocol_integration.py -k loop_protocol_integration -q；必须收集 Anthropic、Responses、千问全部场景，不能用一种代替。

**覆盖：** F11、N8、AC1、AC5、AC8、AC11、AC16。

### T54：完善手动线上验证入口但不自动调用

**文件：** `D:/STUDY/weizhcode-python/tests/manual_tool_smoke.py`

**依赖：** T53

**步骤：**

1. 更新为Loop事件和终止原因，不再依赖 initial/final 或固定两次请求；要求确有最终正文，不只看工具成功/done。
2. 仅使用已有默认有效配置和非敏感临时样本，验证多步、失败恢复与计划/执行；增加整体等待边界并可靠收尾，不改原配置、不打印密钥，不由 pytest 自动触发。

**验证：** 开发中只运行 uv run python -m compileall tests/manual_tool_smoke.py 并检查命令入口；实际线上运行单独记在 T62～T65，不伪称本任务已做真实 API。

**覆盖：** F1、F10、F11、N6、N8、AC1、AC13、AC16。

### T55：全量自动回归与依赖检查

**文件：** `D:/STUDY/weizhcode-python/tests/test_config.py`、`D:/STUDY/weizhcode-python/tests/test_redaction.py`、`D:/STUDY/weizhcode-python/pyproject.toml`、`D:/STUDY/weizhcode-python/uv.lock`

**依赖：** T51、T52、T53、T54

**步骤：**

1. 运行 uv sync --locked、全量 pytest、compileall，记录当前结果、解释器和平台；与 T1 基线对比保留/替换断言。
2. 确认没有新增 SDK/Ruff/mypy/测试插件、没有用户配置修改、没有双入口或审批残留；文档自检不替代程序测试。

**验证：** 上述命令真实退出码0；pytest无失败，skip逐项解释；锁文件一致。未配置的 lint/type 检查标不适用，不声称通过。

**覆盖：** N7、N8、AC15、AC16。

### T56：区分原生平台与进程证据

**文件：** `D:/STUDY/weizhcode-python/tests/test_tool_executor.py`、`D:/STUDY/weizhcode-python/tests/test_tool_scheduler.py`

**依赖：** T55

**步骤：**

1. 本机原生系统实际验证进程树、并发进程归属、取消启动竞态与写入中资源清理。
2. POSIX/Windows 另一平台、目录链接权限等条件不足时明确未执行/skip；不装系统组件，不拿Mock当原生。

**验证：** 运行对应原生进程用例并记录 PID 结束/资源归属断言，报告运行与skip数量；平台不足不改变模型或系统设置。

**覆盖：** F7、N1、N8、AC9、AC15、AC16。

### T57：真实终端验证自动多步与失败纠正

**文件：** 不修改实现；仅使用受控临时样本，证据写入本章验收记录。

**依赖：** T55

**步骤：**

1. 在用户允许的真实 PowerShell 中用专用非敏感临时目录执行读→写摘要→检查，多轮自动推进且无逐次审批。
2. 观察模型等待、轮次、工具行、最终正文；再触发可恢复文件/命令错误，确认结果回传后模型可以继续调整。

**验证：** 保存脱敏截图/用户明确观察及磁盘检查；真实界面无法代操作时交由用户验证并保持待验，不能用Pilot或线上无界面脚本冒充。

**覆盖：** F1、F6、F9、N2、N8、AC1、AC7、AC10、AC14。

### T58：真实终端验证计划与执行切换

**文件：** 不修改实现；仅使用受控临时样本，证据写入本章验收记录。

**依赖：** T57

**步骤：**

1. /plan 后提交临时改动任务，只读调查并给计划后停止，无写/改/命令；后续普通问题仍保持计划模式。
2. /do 后明确切回全工具并按上文计划启动执行，无逐次审批；记录用量/模式与结果。强行模型违规的硬门禁证据复用自动测试。

**验证：** 真实终端观察3/6定义对应模式行为、计划后等待及/do立即启动；仅以临时文件核验副作用，缺凭证/观察机制保持未执行。

**覆盖：** F10、N8、AC12、AC13。

### T59：真实终端验证网络等待和输出中取消

**文件：** 不修改实现；仅使用受控临时样本，证据写入本章验收记录。

**依赖：** T57

**步骤：**

1. 分别在模型等待、流式文字期间按 Esc；另开一次任务按 Ctrl+C，确认取消本轮但不退出。
2. 取消后发送新问题，检查能接受、历史合法、旧回复不串到新任务；清理中重复取消不会误退出。

**验证：** 记录实际按键、状态提示、下一任务成功和是否停止后续迭代；不主动断开整机网络，不修改用户base_url造错误。

**覆盖：** F7、N2、N8、AC8、AC9、AC14。

### T60：真实终端验证工具取消与无审批边界

**文件：** 不修改实现；仅使用受控临时样本，证据写入本章验收记录。

**依赖：** T57、T59

**步骤：**

1. 在临时目录运行受控慢命令时取消，核对不继续后续工具、界面可响应，已发生副作用不被声称回滚。
2. 对并发只读批取消并检查待执行项不启动；实际PID/临时归属强断言复用T56，本项只记录真实终端观察，不取代自动反例。

**验证：** 真实界面显示准确取消状态并可继续使用工具，无残留受管命令/迟到标记；无法观察时保持待验。

**覆盖：** F5、F7、N1、N2、N8、AC6、AC8、AC9、AC14。

### T61：真实终端验证回看、正常退出和重启

**文件：** 不修改实现；仅使用受控临时样本，证据写入本章验收记录。

**依赖：** T58、T59、T60

**步骤：**

1. 滚动查看跨多轮前导文字、工具行、结果与最终正文，观察模式、轮次与用量显示且草稿不丢。
2. 正常退出恢复终端；运行中使用整应用退出入口清理，再启动应无旧历史/旧累计用量，默认normal。

**验证：** 记录实际终端恢复/重启与无迟到操作；Ctrl+C空闲退出单独实测，运行时Ctrl+C取消不与其混淆。

**覆盖：** F7、F8、F9、N8、AC9、AC11、AC14。

### T62：Anthropic 官方服务真实 API 验证

**文件：** 不修改实现；仅使用受控临时样本，证据写入本章验收记录。

**依赖：** T55

**步骤：**

1. 仅在已有有效 Anthropic 凭证、模型和端点时，用临时非敏感样本运行多步、用量、失败恢复与取消。
2. 记录实际协议/服务/模型；若缺凭证或模型权限，不改配置/不新建密钥，记录未执行；兼容端点不能冒充官方服务。

**验证：** 需要完整真实循环及最终正文、配对和安全日志；可复用同服务终端证据避免重复付费，不满足条件不标通过。

**覆盖：** F11、N8、AC16。

### T63：OpenAI Responses 真实 API 验证

**文件：** 不修改实现；仅使用受控临时样本，证据写入本章验收记录。

**依赖：** T55

**步骤：**

1. 仅在已有有效OpenAI凭证与Responses模型时运行受控多步、stateless回放、用量与取消。
2. 保持store=False；不用Chat Completions替代，不擅自切模型/充值/改配置；缺条件明确未执行。

**验证：** 记录真实Responses请求类型、工具结果配对与最终正文/恢复；不以模拟结果或其他协议连通替代。

**覆盖：** F11、N8、AC16。

### T64：千问兼容端点真实 API 验证

**文件：** 不修改实现；仅使用受控临时样本，证据写入本章验收记录。

**依赖：** T55

**步骤：**

1. 具备有效既定端点/模型/凭证时运行多步、末包usage、错误恢复与取消，记录兼容服务实际差异。
2. 此前403或界面显示免费额度均不能作为本章成功证据；权限/额度不足时记录失败/未执行，不擅自换模型。

**验证：** 真实请求完成多轮工具回传与最终正文，正确处理用量空choices；已有同端点终端证据可复用，缺条件保持待验。

**覆盖：** F11、N8、AC16。

### T65：已有 DeepSeek 兼容配置单独验证

**文件：** 不修改实现；仅使用受控临时样本，证据写入本章验收记录。

**依赖：** T55

**步骤：**

1. 若用户当前已有有效DeepSeek Anthropic兼容配置，复用它做多步、思考/必要块回放、用量和取消测试。
2. 单独标注DeepSeek/实际模型与兼容协议，不记作Anthropic官方服务通过；无可用凭证不新增/修改配置，不使用其他协议假替代。

**验证：** 记录兼容端点真实行为及最终正文；可与T57～T61共用一组请求，未执行或失败独立保留，不扩大成所有兼容端点都通过。

**覆盖：** F11、N6、N8、AC16。

### T66：汇总验收、差异和交付状态

**文件：** `D:/STUDY/weizhcode-python/specs/agent-loop/task.md`、`D:/STUDY/weizhcode-python/specs/agent-loop/checklist.md`

**依赖：** T55、T56、T57、T58、T59、T60、T61、T62、T63、T64、T65

**步骤：**

1. 按已批准Checklist逐项记录真实证据，区分自动、原生平台、用户手测、真实API、失败/缺条件；不把未执行标为成功。
2. 核对最终无旧审批/单工具限制、无未授权配置改动/依赖/测试产物；仅提交本章改动与真实证据，报告取消非回滚/非沙箱/上下文上限等边界，不自动推送GitHub。

**验证：** 文档勾选能逐项追溯到运行输出或用户观察；工作树保留用户数据，未完成验收明确列出；有安全可行工作未做则继续，缺新权限/凭证由用户决定。

**覆盖：** F1、F2、F3、F4、F5、F6、F7、F8、F9、F10、F11、N1、N2、N3、N4、N5、N6、N7、N8、AC1、AC2、AC3、AC4、AC5、AC6、AC7、AC8、AC9、AC10、AC11、AC12、AC13、AC14、AC15、AC16。

## 6. 执行追踪（当前没有实现或测试结果）

本表在Task生成时全部未开始；审批不等于执行通过。后续每次更新必须附安全证据位置、命令/场景、实际结果和日期，不写凭证或未经处理的请求日志。

| 任务 | 状态 | 实际证据 |
|------|------|----------|
| T1 | 已完成 | uv sync --locked；pytest：226 passed, 2 skipped（目录链接权限、POSIX 平台）；compileall 通过。Python 3.13.5 / Windows 11；原普通运行缓存拒绝访问后获准重试成功。 |
| T2 | 已完成 | usage_contract：5 passed；含负数/布尔/类型、真实零、部分已知与不可变快照。 |
| T3 | 已完成 | run_context_contract：1 passed；独立任务标识/事件/槽、冻结模式与响应副本。 |
| T4 | 已完成 | loop_event_contract：1 passed；事件相关性与参数/结果防御性副本；正式 UI 尚未切换。 |
| T5 | 已完成 | tool_slot_contract：1 passed；执行状态、同名槽隔离、取消状态与结果预算。 |
| T6 | 已完成 | readonly_classification：1 passed；六工具显式分类，暂保留旧审批字段供旧入口。 |
| T7 | 已完成 | readonly_registry：1 passed；精确三工具、保序、未知、伪真值与副本。 |
| T8 | 已完成 | loop_prompts：1 passed；新增 Loop/Plan/执行指令，旧入口待 T49 切换。 |
| T9 | 已完成 | loop_exchange_contract：1 passed；数量/顺序/名称校验、原子失败，保留既有深复制回归。 |
| T10 | 已完成 | mixed_diagnostic：3 passed（三协议）；真实成功/失败、执行事实及脱敏回放。 |
| T11 | 已完成 | application_stop_notice：1 passed；应用来源、去重与后续任务。 |
| T12 | 已完成 | anthropic_usage：累计覆盖、缓存三项相加、缺省/显式 null 和递减快照；协议回归通过。 |
| T13 | 已完成 | responses_usage：总量不叠加缓存/推理子项，失败部分统计保留；协议回归通过。 |
| T14 | 已完成 | qwen_usage：include_usage、空 choices 末包、重复包与字段缺失；协议回归通过。 |
| T15 | 已完成 | collector_dual_path：先显示正文再收齐，末尾补发、跨片脱敏与不透明载荷不展示。 |
| T16 | 已完成 | collector_completion_gate：缺 done、缺消息、正文不一致、空正文和最终调用权威去重。 |
| T17 | 已完成 | collector_cancellation：无 token 等待与同拍取消，三实际适配器源流均确定性关闭。 |
| T18 | 已完成 | collector_usage_snapshot：累计/重复报告不相加、递减不覆盖，错误保留部分统计。 |
| T19 | 已完成 | bounded_event_channel：128 容量背压、事件保序、显示副本脱敏不改原参数及结果。 |
| T20 | 已完成 | event_channel_shutdown：满队列与空等待消费者离开均收尾，无阻塞结束哨兵。 |
| T21 | 已完成 | loop_execute_basic：真实临时文件无审批写/读/失败，结果先写槽；旧入口尚未切换。 |
| T22 | 已完成 | plan_execution_gate：写/改/命令均零 worker、零副作用，正常模式不受影响。 |
| T23 | 已完成 | loop_tool_budget：准备+执行共享同一预算，实际超时收尾。 |
| T24 | 已完成 | cancel_preserves_result：清理期间与结果同拍取消保留成功；未确认区分是否已开始。 |
| T25 | 已完成 | loop_process_cleanup：原生 Windows 创建/准备/命令树/写临时资源取消；保留外部替换资源和原文件。 |
| T26 | 已完成 | cleanup_infrastructure_failure：保留成功事实，另记清理基础设施故障，不回显异常原文。 |
| T27 | 已完成 | scheduler_preflight：重复 ID 全冲突拒绝，独立合法调用仍执行，缺 ID/坏 JSON/未知结构化返回。 |
| T28 | 已完成 | readonly_batch_overlap：闸门证明两读实际重叠，逆完成仍保序。 |
| T29 | 已完成 | readonly_concurrency_limit：峰值 4，许可等待取消不迟到启动。 |
| T30 | 已完成 | side_effect_batch_barriers：读/读/写/读/改/命令及未知/非法屏障；实际文件可见性断言。 |
| T31 | 已完成 | batch_cancellation_results：保留已完成结果、补齐取消、阻止后续副作用。 |
| T32 | 已完成 | batch_event_order：开始行/结果按调用原序，状态按 local_id 更新。 |
| T33 | 已完成 | loop_single_flight：同步占用、单次自然/空回复结束；新驱动仍私有，正式入口待 T49。 |
| T34 | 已完成 | loop_multistep_history：真实文件 read→write→read→最终正文，四请求及完整配对。 |
| T35 | 已完成 | iteration_limit_boundary：精确 25 请求/50 工具结果、最后文字正常结束、同拍取消优先。 |
| T36 | 已完成 | unknown_round_threshold：三全未知停止、已注册参数/执行失败重置、新任务重置。 |
| T37 | 已完成 | loop_error_recovery：残缺流零执行、真实写入后续答失败不重做、工具失败可调整、清理故障停止。 |
| T38 | 已完成 | session_usage_settlement：同请求重复用量只记一次、跨用户保留与缺失次数。 |
| T39 | 已完成 | loop_mode_control：模式冻结、plan 三定义及真实门禁、/do 对应指令立即全工具执行。 |
| T40 | 已完成 | loop_lifecycle_reuse：重复取消后同实例可再用、消费者离开、未消费满队列应用关闭。 |
| T41 | 未开始 | 尚未执行 |
| T42 | 未开始 | 尚未执行 |
| T43 | 未开始 | 尚未执行 |
| T44 | 未开始 | 尚未执行 |
| T45 | 未开始 | 尚未执行 |
| T46 | 未开始 | 尚未执行 |
| T47 | 未开始 | 尚未执行 |
| T48 | 未开始 | 尚未执行 |
| T49 | 未开始 | 尚未执行 |
| T50 | 未开始 | 尚未执行 |
| T51 | 未开始 | 尚未执行 |
| T52 | 未开始 | 尚未执行 |
| T53 | 未开始 | 尚未执行 |
| T54 | 未开始 | 尚未执行 |
| T55 | 未开始 | 尚未执行 |
| T56 | 未开始 | 尚未执行 |
| T57 | 未开始 | 尚未执行 |
| T58 | 未开始 | 尚未执行 |
| T59 | 未开始 | 尚未执行 |
| T60 | 未开始 | 尚未执行 |
| T61 | 未开始 | 尚未执行 |
| T62 | 未开始 | 尚未执行 |
| T63 | 未开始 | 尚未执行 |
| T64 | 未开始 | 尚未执行 |
| T65 | 未开始 | 尚未执行 |
| T66 | 未开始 | 尚未执行 |

## 7. 需求覆盖

汇总任务不能替代具体功能任务的证据。下表排除 T66 的总括覆盖，以免仅凭交付汇总制造已覆盖的假象。

| 需求/验收 | 具体任务 |
|-----------|----------|
| F1 | T3、T8、T21、T33、T34、T48、T49、T54、T57 |
| F2 | T3、T11、T16、T33、T35、T36、T37、T52 |
| F3 | T4、T15、T19、T20、T32、T33、T42、T49 |
| F4 | T10、T15、T16、T27、T37、T48 |
| F5 | T6、T7、T27、T28、T29、T30、T32、T48、T49、T60 |
| F6 | T5、T9、T10、T11、T21、T23、T24、T26、T27、T31、T34、T36、T37、T50、T52、T57 |
| F7 | T3、T5、T17、T20、T24、T25、T29、T31、T40、T44、T45、T49、T50、T56、T59、T60、T61 |
| F8 | T2、T12、T13、T14、T18、T38、T43、T61 |
| F9 | T4、T32、T41、T42、T43、T45、T49、T57、T61 |
| F10 | T3、T6、T7、T8、T22、T39、T43、T45、T49、T50、T54、T58 |
| F11 | T10、T12、T13、T14、T47、T48、T49、T53、T54、T62、T63、T64、T65 |
| N1 | T17、T20、T23、T25、T26、T29、T31、T40、T44、T50、T51、T56、T60 |
| N2 | T17、T42、T44、T57、T59、T60 |
| N3 | T5、T19、T23、T41、T46、T51、T52 |
| N4 | T6、T21、T25、T51 |
| N5 | T2、T5、T9、T18、T20、T24、T26、T28、T29、T30、T31、T33、T37、T40、T45 |
| N6 | T8、T10、T15、T19、T22、T41、T46、T51、T52、T54、T65 |
| N7 | T1、T47、T49、T55 |
| N8 | T1、T53、T54、T55、T56、T57、T58、T59、T60、T61、T62、T63、T64、T65 |
| AC1 | T8、T21、T34、T48、T49、T53、T54、T57 |
| AC2 | T11、T16、T33、T35 |
| AC3 | T3、T35 |
| AC4 | T3、T36 |
| AC5 | T10、T15、T16、T27、T37、T48、T53 |
| AC6 | T6、T7、T27、T28、T29、T30、T32、T48、T60 |
| AC7 | T21、T23、T26、T37、T50、T51、T57 |
| AC8 | T5、T9、T10、T11、T24、T26、T27、T31、T34、T36、T37、T40、T50、T52、T53、T59、T60 |
| AC9 | T3、T5、T17、T20、T24、T25、T26、T29、T31、T35、T40、T44、T45、T49、T50、T56、T59、T60、T61 |
| AC10 | T4、T15、T19、T20、T32、T33、T41、T42、T49、T57 |
| AC11 | T2、T12、T13、T14、T18、T38、T43、T53、T61 |
| AC12 | T6、T7、T22、T39、T43、T49、T50、T58 |
| AC13 | T8、T39、T43、T49、T50、T54、T58 |
| AC14 | T4、T32、T33、T41、T42、T43、T44、T45、T57、T59、T60、T61 |
| AC15 | T5、T6、T19、T23、T25、T41、T46、T51、T52、T55、T56 |
| AC16 | T1、T10、T12、T13、T14、T47、T48、T49、T53、T54、T55、T56、T62、T63、T64、T65 |

## 8. 开发与验收记录

四份文档已全部批准。基础组局部命令为：uv run python -m pytest tests/test_provider_events.py tests/test_turn_runner.py tests/test_tui.py tests/test_tool_executor.py tests/test_tool_registry.py tests/test_conversation.py tests/test_provider_tools.py -k 'usage_contract or run_context_contract or loop_event_contract or tool_slot_contract or readonly_classification or readonly_registry or loop_prompts or loop_exchange_contract or mixed_diagnostic or application_stop_notice' -q，实际 16 passed、110 deselected；compileall 通过。基础组全量回归 uv run python -m pytest -q -rs：242 passed、2 skipped（与基线相同的权限/平台原因），37.18 秒。未运行真实 API，未改用户配置，未推送 GitHub。

2026-11-14，核心组 T12～T40：三协议/收集器局部 62 passed；事件通道局部 3 passed；执行器门禁/超时/结果保留初测 8 passed；取消清理与连接关闭专项修正后 12 passed；调度器 6 passed；Loop 初组 14 passed，随后补清理故障/已知失败重置/满队列退出。全量最终 uv run python -m pytest -q -rs：304 passed、2 skipped（目录链接权限和 POSIX 原生平台），43.97 秒；compileall 通过。当前正式入口仍保持旧行为，新增私有路径已验证，T41～T49 将统一接线。

一次临时资源归属测试初测失败：Windows 拒绝替换仍被子进程打开的临时文件。测试调整为实际进程结束后、资源归属校验前模拟外部替换，重新验证原文件/外部对象保护通过；未删除断言、未增加 skip。
