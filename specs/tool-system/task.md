# weizhCode 工具系统 Tasks

> 状态：四份文档全部获批，已进入开发。下方执行记录以真实验证为准。
> 依据：[specs/tool-system/spec.md](D:/STUDY/weizhcode-python/specs/tool-system/spec.md)、[specs/tool-system/plan.md](D:/STUDY/weizhcode-python/specs/tool-system/plan.md)。
> 四份文档现已全部获批。批准不等于任务已执行，完成情况以文末执行记录为准。

## 执行记录

最近验证：2026-11-13，Windows，Python 3.13.5；原基线 27 passed，依赖加入后仍 27 passed，基础组完成后全量 66 passed。

| 任务 | 状态 | 证据/说明 |
|------|------|-----------|
| T1 | 通过 | 基线 27 passed；compileall 通过 |
| T2 | 通过 | uv sync；新增依赖后原有 27 passed |
| T3 | 通过 | 基础组全量 66 passed（2026-11-13，Windows/Python 3.13.5） |
| T4 | 通过 | 基础组全量 66 passed（2026-11-13，Windows/Python 3.13.5） |
| T5 | 通过 | 基础组全量 66 passed（2026-11-13，Windows/Python 3.13.5） |
| T6 | 通过 | 基础组全量 66 passed（2026-11-13，Windows/Python 3.13.5） |
| T7 | 通过 | 基础组全量 66 passed（2026-11-13，Windows/Python 3.13.5） |
| T8 | 通过 | 基础组全量 66 passed（2026-11-13，Windows/Python 3.13.5） |
| T9 | 通过 | 基础组全量 66 passed（2026-11-13，Windows/Python 3.13.5） |
| T10 | 通过 | 六工具组全量 117 passed、1 skipped（Windows，2026-11-13） |
| T11 | 通过 | 六工具组全量 117 passed、1 skipped（Windows，2026-11-13） |
| T12 | 通过 | 六工具组全量 117 passed、1 skipped（Windows，2026-11-13） |
| T13 | 通过 | 六工具组全量 117 passed、1 skipped（Windows，2026-11-13） |
| T14 | 通过 | 六工具组全量 117 passed、1 skipped（Windows，2026-11-13） |
| T15 | 通过 | 六工具组全量 117 passed、1 skipped（Windows，2026-11-13） |
| T16 | 通过 | 六工具组全量 117 passed、1 skipped（Windows，2026-11-13） |
| T17 | 通过 | 六工具组全量 117 passed、1 skipped（Windows，2026-11-13） |
| T18 | 通过 | 六工具组全量 117 passed、1 skipped（Windows，2026-11-13） |
| T19 | 已验证（含平台跳过） | 搜索组通过；目录链接权限样本 skip，未冒充已验证 |
| T20 | 通过 | 六工具组全量 117 passed、1 skipped（Windows，2026-11-13） |
| T21 | 通过 | 六工具组全量 117 passed、1 skipped（Windows，2026-11-13） |
| T22 | 通过 | 六工具组全量 117 passed、1 skipped（Windows，2026-11-13） |
| T23 | 通过 | 六工具组全量 117 passed、1 skipped（Windows，2026-11-13） |
| T24 | 通过 | 六工具组全量 117 passed、1 skipped（Windows，2026-11-13） |
| T25 | 通过 | 六工具组全量 117 passed、1 skipped（Windows，2026-11-13） |
| T26 | 通过 | 六工具组全量 117 passed、1 skipped（Windows，2026-11-13） |
| T27 | 进行中 | 进程管理与审批生命周期实现中 |
| T28 | 未开始 | 尚未执行 |
| T29 | 未开始 | 尚未执行 |
| T30 | 未开始 | 尚未执行 |
| T31 | 未开始 | 尚未执行 |
| T32 | 未开始 | 尚未执行 |
| T33 | 未开始 | 尚未执行 |
| T34 | 未开始 | 尚未执行 |
| T35 | 未开始 | 尚未执行 |
| T36 | 未开始 | 尚未执行 |
| T37 | 未开始 | 尚未执行 |
| T38 | 未开始 | 尚未执行 |
| T39 | 未开始 | 尚未执行 |
| T40 | 未开始 | 尚未执行 |
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

## 执行约束

- 共 66 个有序任务，以聚焦、可验证的小工作单元拆分；任务涉及同一文件时按依赖追加，不覆盖前面已验证的改动。
- 所有命令均从项目根目录 D:/STUDY/weizhcode-python 执行。涉及真实写入的验证只使用受控临时目录，不编辑用户实际源码、密钥文件或原配置作为测试样本。
- 下列测试选择器是开发时应新增的测试命名约定，不表示当前已存在。每条验证必须确实收集并执行目标用例；0 tests collected 或全部 deselected 不算通过。
- 测试随对应功能一起添加，不提前导入尚未实现的组件制造无关失败。每项通过后再标记完成，未通过先修复和重跑。
- 新接口沿用 Plan 的名称与数据结构；不改为参考项目的 SDK、两协议、多工具或免审批实现。
- 生产工具预算固定 30 秒，审批等待不计入；自动测试可注入内部短预算，但不增加配置字段。
- 自动测试、真实 PowerShell 界面、真实 API 分别留证。缺凭证、平台不具备或场景未运行时标注未执行，不等同通过。
- 用户已允许本阶段以 Windows PowerShell 真实终端代替 tmux；不安装额外系统组件，不修改通用仓库说明。
- 每组逻辑相关任务验证通过后按流程本地提交，只纳入本阶段文件，不自动推送 GitHub。不将未通过任务通过删除断言、静默 skip 或扩大权限绕过。
- 遇到需要新凭证、系统安装、模型替换、原配置修改或超出已批准范围的情况，先报告并请求用户决定。

## 任务分组

| 组 | 编号 | 内容 |
|----|------|------|
| 1 | T1～T9 | 基础、数据契约与安全出口 |
| 2 | T10～T26 | 文件、搜索与命令六工具 |
| 3 | T27～T35 | 工作进程、逐次审批与真实终止 |
| 4 | T36～T44 | 会话历史、三协议适配与系统说明 |
| 5 | T45～T48 | 固定单工具闭环 |
| 6 | T49～T56 | 界面、入口与跨层集成 |
| 7 | T57～T66 | 回归、PowerShell 与真实 API 验收 |

## 文件清单

以下清单覆盖 Plan 的全部 41 个实现/测试/依赖文件；状态指计划操作，非完成状态。现有配置文件仅回归验证，不改写。

| 操作 | 文件 | 职责 | 对应任务 |
|------|------|------|----------|
| 新建 | [src/weizhcode/turn_runner.py](D:/STUDY/weizhcode-python/src/weizhcode/turn_runner.py) | 固定两阶段单轮编排、执行次数约束和历史提交 | T45、T46、T47、T48、T54 |
| 新建 | [src/weizhcode/prompts.py](D:/STUDY/weizhcode-python/src/weizhcode/prompts.py) | 内置工具使用说明和最终续答要求 | T44 |
| 新建 | [src/weizhcode/tool_ui.py](D:/STUDY/weizhcode-python/src/weizhcode/tool_ui.py) | ToolCallView、审批消息和安全摘要显示 | T49、T50、T52 |
| 新建 | [src/weizhcode/redaction.py](D:/STUDY/weizhcode-python/src/weizhcode/redaction.py) | 批量及跨流式片段脱敏、安全显示文本 | T7、T8、T52 |
| 新建 | [src/weizhcode/tools/__init__.py](D:/STUDY/weizhcode-python/src/weizhcode/tools/__init__.py) | 默认六工具注册工厂与包出口 | T6、T26 |
| 新建 | [src/weizhcode/tools/base.py](D:/STUDY/weizhcode-python/src/weizhcode/tools/base.py) | Tool 契约与工具准备/执行共用上下文 | T4 |
| 新建 | [src/weizhcode/tools/registry.py](D:/STUDY/weizhcode-python/src/weizhcode/tools/registry.py) | 有序注册、按名查找和定义校验 | T9 |
| 新建 | [src/weizhcode/tools/executor.py](D:/STUDY/weizhcode-python/src/weizhcode/tools/executor.py) | 参数校验、审批衔接、预算及结果归一 | T31、T32、T33、T34、T54 |
| 新建 | [src/weizhcode/tools/process.py](D:/STUDY/weizhcode-python/src/weizhcode/tools/process.py) | ManagedWorker、管道、Job/进程组及清理 | T27、T28、T30、T34、T35 |
| 新建 | [src/weizhcode/tools/worker.py](D:/STUDY/weizhcode-python/src/weizhcode/tools/worker.py) | 内部工作进程入口与 prepare/execute 握手 | T29、T30 |
| 新建 | [src/weizhcode/tools/limits.py](D:/STUDY/weizhcode-python/src/weizhcode/tools/limits.py) | 超时、条数、字符常量与预算处理 | T6、T25 |
| 新建 | [src/weizhcode/tools/file_utils.py](D:/STUDY/weizhcode-python/src/weizhcode/tools/file_utils.py) | UTF-8/BOM、换行、指纹、精确扫描和临时替换 | T10、T12、T13、T16、T18 |
| 新建 | [src/weizhcode/tools/search_utils.py](D:/STUDY/weizhcode-python/src/weizhcode/tools/search_utils.py) | 忽略作用域、隐藏项、目录遍历及 glob 匹配 | T19、T20、T21、T22、T23 |
| 新建 | [src/weizhcode/tools/read_file.py](D:/STUDY/weizhcode-python/src/weizhcode/tools/read_file.py) | 分段带行号读取 | T11 |
| 新建 | [src/weizhcode/tools/write_file.py](D:/STUDY/weizhcode-python/src/weizhcode/tools/write_file.py) | 创建/覆盖的准备与执行 | T14、T15 |
| 新建 | [src/weizhcode/tools/edit_file.py](D:/STUDY/weizhcode-python/src/weizhcode/tools/edit_file.py) | 原文唯一匹配、预览和修改 | T17、T18 |
| 新建 | [src/weizhcode/tools/run_command.py](D:/STUDY/weizhcode-python/src/weizhcode/tools/run_command.py) | 跨系统 shell 选择及受限输出收集 | T24、T25、T35 |
| 新建 | [src/weizhcode/tools/find_files.py](D:/STUDY/weizhcode-python/src/weizhcode/tools/find_files.py) | glob 文件查找 | T21 |
| 新建 | [src/weizhcode/tools/search_content.py](D:/STUDY/weizhcode-python/src/weizhcode/tools/search_content.py) | 普通文本/正则内容搜索 | T22、T23 |
| 修改 | [src/weizhcode/models.py](D:/STUDY/weizhcode-python/src/weizhcode/models.py) | 扩展统一工具数据、消息、事件与审批结构 | T3、T4、T5、T6 |
| 修改 | [src/weizhcode/conversation.py](D:/STUDY/weizhcode-python/src/weizhcode/conversation.py) | 完整助手回合、原子工具交换、防御性历史副本 | T36、T48 |
| 修改 | [src/weizhcode/errors.py](D:/STUDY/weizhcode-python/src/weizhcode/errors.py) | 接入统一脱敏，保留原错误入口的兼容性 | T8 |
| 修改 | [src/weizhcode/providers/base.py](D:/STUDY/weizhcode-python/src/weizhcode/providers/base.py) | 扩展 stream_chat 关键字接口 | T37 |
| 修改 | [src/weizhcode/providers/anthropic.py](D:/STUDY/weizhcode-python/src/weizhcode/providers/anthropic.py) | Messages 工具请求、流式组装、完成判定与回灌 | T37、T38、T39 |
| 修改 | [src/weizhcode/providers/openai.py](D:/STUDY/weizhcode-python/src/weizhcode/providers/openai.py) | Responses 函数调用、可回放输出、完成判定与回灌 | T37、T40、T41 |
| 修改 | [src/weizhcode/providers/qwen.py](D:/STUDY/weizhcode-python/src/weizhcode/providers/qwen.py) | Chat Completions 调用碎片、完成判定与回灌 | T37、T42、T43 |
| 修改 | [src/weizhcode/tui.py](D:/STUDY/weizhcode-python/src/weizhcode/tui.py) | 消费 TurnEvent、审批 Future、忙碌保护、状态栏和退出清理 | T50、T51、T52、T53、T54 |
| 修改 | [src/weizhcode/cli.py](D:/STUDY/weizhcode-python/src/weizhcode/cli.py) | 创建并注入新增组件，保留启动错误处理 | T51、T53 |
| 修改 | [pyproject.toml](D:/STUDY/weizhcode-python/pyproject.toml) | 增加 jsonschema、pathspec、wcmatch | T2 |
| 修改 | [uv.lock](D:/STUDY/weizhcode-python/uv.lock) | 在允许开发后通过 uv 解析并锁定实际兼容版本 | T2 |
| 新建 | [tests/test_tool_registry.py](D:/STUDY/weizhcode-python/tests/test_tool_registry.py) | 六条有序定义、重复名称、查询和 Schema | T3、T6、T9、T26、T57 |
| 新建 | [tests/test_file_tools.py](D:/STUDY/weizhcode-python/tests/test_file_tools.py) | 读写改、0/1/多匹配、空文本、编码、BOM/换行、失效预览 | T10、T11、T12、T13、T14、T15、T16、T17、T18、T57 |
| 新建 | [tests/test_search_tools.py](D:/STUDY/weizhcode-python/tests/test_search_tools.py) | glob、普通/正则、嵌套忽略与否定、隐藏项、空结果和上限 | T19、T20、T21、T22、T23、T57 |
| 新建 | [tests/test_command_tool.py](D:/STUDY/weizhcode-python/tests/test_command_tool.py) | shell/cwd、输出来源、非零退出、进程树和体量 | T24、T25、T35、T57 |
| 新建 | [tests/test_tool_executor.py](D:/STUDY/weizhcode-python/tests/test_tool_executor.py) | 未批准无副作用、拒绝、审批计时暂停、超时、进程建立失败和清理 | T4、T27、T28、T29、T30、T31、T32、T33、T34、T35、T54、T55、T57 |
| 新建 | [tests/test_turn_runner.py](D:/STUDY/weizhcode-python/tests/test_turn_runner.py) | 一次/两次请求、多个全部拒绝、续答禁用、错误和历史恢复 | T44、T45、T46、T47、T48、T55、T56、T57 |
| 新建 | [tests/test_redaction.py](D:/STUDY/weizhcode-python/tests/test_redaction.py) | 已知密钥、多次出现、跨片段、错误与工具结果脱敏、实际参数不被篡改 | T7、T8、T55、T57 |
| 修改 | [tests/test_provider_events.py](D:/STUDY/weizhcode-python/tests/test_provider_events.py) | 扩展现有三协议模拟流、请求体、终止信号、配对和诊断回灌 | T1、T8、T37、T38、T39、T40、T41、T42、T43、T55、T56、T57 |
| 修改 | [tests/test_conversation.py](D:/STUDY/weizhcode-python/tests/test_conversation.py) | 扩展工具交换、回放数据、防御性复制 | T1、T5、T36、T56、T57 |
| 修改 | [tests/test_tui.py](D:/STUDY/weizhcode-python/tests/test_tui.py) | 扩展审批点击、状态、顺序、草稿、防重入、滚动、错误恢复和退出 | T1、T5、T37、T49、T50、T51、T52、T53、T54、T55、T57 |
| 保留并回归验证 | [tests/test_config.py](D:/STUDY/weizhcode-python/tests/test_config.py) | 保留原配置回归测试，包括只解析默认供应商密钥 | T1、T53、T57 |

流程记录文件：[specs/tool-system/task.md](D:/STUDY/weizhcode-python/specs/tool-system/task.md) 在执行后更新真实任务状态；[specs/tool-system/checklist.md](D:/STUDY/weizhcode-python/specs/tool-system/checklist.md) 将在 task 批准后生成并单独审批，验收时记录实际结果。本次不提前创建 checklist。

## 1. 基础、数据契约与安全出口

### T1: 记录开发前基线

**文件：** [tests/test_config.py](D:/STUDY/weizhcode-python/tests/test_config.py)、[tests/test_conversation.py](D:/STUDY/weizhcode-python/tests/test_conversation.py)、[tests/test_provider_events.py](D:/STUDY/weizhcode-python/tests/test_provider_events.py)、[tests/test_tui.py](D:/STUDY/weizhcode-python/tests/test_tui.py)

**依赖：** 无；仅在四份文档全部批准后执行。

**步骤：**

1. 在四份文档全部批准后，记录当前工作区改动和实际运行环境，不覆盖用户已有修改。
2. 运行现有全量测试和编译检查，记录退出码及测试数量；已有失败先识别归属，不把新功能失败混入基线。

**验证：** 运行 uv run python -m pytest 与 uv run python -m compileall src tests，保存实际结果；本任务不要求新增工具功能已存在。

**覆盖：** N7、N8、AC13。

### T2: 加入已确认的运行依赖

**文件：** [pyproject.toml](D:/STUDY/weizhcode-python/pyproject.toml)、[uv.lock](D:/STUDY/weizhcode-python/uv.lock)

**依赖：** T1

**步骤：**

1. 仅加入 jsonschema、pathspec、wcmatch，保持 Python >=3.11 和现有开发依赖。
2. 通过 uv 解析并锁定兼容版本、同步环境；不加入 SDK、Ruff、mypy 或系统组件，不修改 YAML 配置。

**验证：** 运行 uv sync 和现有全量测试；确认三项依赖可导入，版本由 uv.lock 记录且没有其他主动增加的依赖。

**覆盖：** F1、N7。

### T3: 扩展工具调用与结果数据

**文件：** [src/weizhcode/models.py](D:/STUDY/weizhcode-python/src/weizhcode/models.py)、[tests/test_tool_registry.py](D:/STUDY/weizhcode-python/tests/test_tool_registry.py)

**依赖：** T1

**步骤：**

1. 新增 ToolDefinition、ToolCall、ToolResult 及稳定状态/错误分类，字段与 plan 第 3 节一致。
2. 保留现有普通消息构造的兼容性；为嵌套集合定义防御性复制边界。
3. 新增名称包含 model_contract 的测试，验证调用 ID、原始参数、解析状态、空结果成功及非成功状态的 is_error 语义。

**验证：** 运行 uv run python -m pytest tests/test_tool_registry.py -k "model_contract" -v；原有配置和消息测试不回归。

**覆盖：** F1、F13、AC1、AC10。

### T4: 定义准备记录与审批数据

**文件：** [src/weizhcode/models.py](D:/STUDY/weizhcode-python/src/weizhcode/models.py)、[src/weizhcode/tools/base.py](D:/STUDY/weizhcode-python/src/weizhcode/tools/base.py)、[tests/test_tool_executor.py](D:/STUDY/weizhcode-python/tests/test_tool_executor.py)

**依赖：** T3

**步骤：**

1. 定义 ToolContext、FileSnapshot、PreparedOperation、PreparedOperationPreview、ApprovalRequest 和 Tool 的 definition/prepare/execute 契约。
2. 明确准备成功与准备失败的记录：失败携带 ToolResult，不能形成可执行的有效操作；成功记录包含不可替换的 operation_id 与规范化参数。
3. 新增 operation_contract 测试，验证上下文不携带密钥、预览不含原文件完整副本、实际参数与展示文本分离。

**验证：** 运行 uv run python -m pytest tests/test_tool_executor.py -k "operation_contract" -v，验证失败准备记录不能作为有效执行指令。

**覆盖：** F12、F13、AC3、AC10。

### T5: 扩展历史消息和两层事件

**文件：** [src/weizhcode/models.py](D:/STUDY/weizhcode-python/src/weizhcode/models.py)、[tests/test_conversation.py](D:/STUDY/weizhcode-python/tests/test_conversation.py)、[tests/test_tui.py](D:/STUDY/weizhcode-python/tests/test_tui.py)

**依赖：** T3、T4

**步骤：**

1. 给 ChatMessage 增加 tool 角色、调用、结果及 provider_payload，默认值继续支持普通文字消息。
2. 扩展 ProviderEvent，增加完整助手消息及工具事件；定义 TurnEvent 和 initial/final 文字阶段。
3. 新增 event_contract 测试，区分工具发现、完整调用、响应成功和本轮结束，防止 pending 被解释为允许执行。

**验证：** 运行 uv run python -m pytest tests/test_conversation.py tests/test_tui.py -k "event_contract" -v，再运行已有消息构造测试。

**覆盖：** F10、F15、F16、AC7、AC8。

### T6: 实现结果预算和序列化

**文件：** [src/weizhcode/models.py](D:/STUDY/weizhcode-python/src/weizhcode/models.py)、[src/weizhcode/tools/__init__.py](D:/STUDY/weizhcode-python/src/weizhcode/tools/__init__.py)、[src/weizhcode/tools/limits.py](D:/STUDY/weizhcode-python/src/weizhcode/tools/limits.py)、[tests/test_tool_registry.py](D:/STUDY/weizhcode-python/tests/test_tool_registry.py)

**依赖：** T3

**步骤：**

1. 建立不触发具体工具导入的包入口；集中定义 30 秒、20,000 字符、200 行、200 文件和 100 命中的常量。
2. 实现 ToolResult.to_model_text 和预算处理；通过参数传入预算，避免 models 反向依赖工具实现产生循环。
3. 新增 result_budget 测试，覆盖中文、转义、超长诊断及必要元数据，截断标记也计入序列化文本预算。

**验证：** 运行 uv run python -m pytest tests/test_tool_registry.py -k "result_budget" -v；每份模型结果不超过 20,000 字符且状态、退出码、匹配数仍存在。

**覆盖：** F13、N3、AC11。

### T7: 实现批量脱敏和安全显示文本

**文件：** [src/weizhcode/redaction.py](D:/STUDY/weizhcode-python/src/weizhcode/redaction.py)、[tests/test_redaction.py](D:/STUDY/weizhcode-python/tests/test_redaction.py)

**依赖：** T3

**步骤：**

1. 实现已知密钥集合的 Redactor，对预览、正文、结构化结果中的可读文本统一脱敏。
2. 提供普通文本显示清理，阻止终端控制序列和界面标记被作为指令解释；不修改实际操作参数。
3. 新增 redact_batch 测试，覆盖密钥多次出现、嵌套结果、错误、空密钥集合和原始操作内容保持不变。

**验证：** 运行 uv run python -m pytest tests/test_redaction.py -k "redact_batch" -v，断言安全出口无受控密钥而原参数未被替换。

**覆盖：** N6、AC13。

### T8: 实现跨分片脱敏并兼容原错误入口

**文件：** [src/weizhcode/redaction.py](D:/STUDY/weizhcode-python/src/weizhcode/redaction.py)、[src/weizhcode/errors.py](D:/STUDY/weizhcode-python/src/weizhcode/errors.py)、[tests/test_redaction.py](D:/STUDY/weizhcode-python/tests/test_redaction.py)、[tests/test_provider_events.py](D:/STUDY/weizhcode-python/tests/test_provider_events.py)

**依赖：** T7

**步骤：**

1. 实现 StreamingRedactor 的尾部前缀缓冲、结束刷新及错误终止处理。
2. 原 redact_secret 错误入口接入统一处理，保留现有可用调用方式。
3. 新增 redact_stream 测试，将受控密钥在每个可能位置拆分，验证已发出的累计文字从未泄漏完整密钥。

**验证：** 运行 uv run python -m pytest tests/test_redaction.py tests/test_provider_events.py -v，覆盖多片段、正常结束和中断收尾。

**覆盖：** N6、AC13。

### T9: 实现注册中心与 Schema 检查

**文件：** [src/weizhcode/tools/registry.py](D:/STUDY/weizhcode-python/src/weizhcode/tools/registry.py)、[tests/test_tool_registry.py](D:/STUDY/weizhcode-python/tests/test_tool_registry.py)

**依赖：** T2、T3、T4

**步骤：**

1. 实现 ToolRegistry.register/get/definitions，保持顺序，重复名称报错，定义返回防御性副本。
2. 注册时检查自包含 Schema，拒绝远程引用；完整参数校验拒绝多余字段、布尔伪整数和错误类型。
3. 新增 registry 测试，使用无副作用的测试工具验证查询、重复名称、Schema 错误和无网络校验。

**验证：** 运行 uv run python -m pytest tests/test_tool_registry.py -k "registry" -v；未知名称不返回其他工具，重复注册不覆盖旧定义。

**覆盖：** F1、F13、AC1、AC7。

## 2. 文件、搜索与命令六工具

### T10: 实现有界文本读取和格式识别

**文件：** [src/weizhcode/tools/file_utils.py](D:/STUDY/weizhcode-python/src/weizhcode/tools/file_utils.py)、[tests/test_file_tools.py](D:/STUDY/weizhcode-python/tests/test_file_tools.py)

**依赖：** T4、T6

**步骤：**

1. 实现分块严格 UTF-8 解码、BOM 与换行识别，区分文件、目录、二进制和解码失败。
2. 实现有界行片段读取，保留原换行信息，不对超长行先无界读入。
3. 新增 text_format 测试，覆盖 BOM、多字节字符跨块、LF/CRLF/混合换行、二进制、错误编码和超长行。

**验证：** 运行 uv run python -m pytest tests/test_file_tools.py -k "text_format" -v，解码失败不以替换字符伪装成功。

**覆盖：** F2、N4、AC2、AC13。

### T11: 实现 read_file

**文件：** [src/weizhcode/tools/read_file.py](D:/STUDY/weizhcode-python/src/weizhcode/tools/read_file.py)、[tests/test_file_tools.py](D:/STUDY/weizhcode-python/tests/test_file_tools.py)

**依赖：** T9、T10

**步骤：**

1. 声明 path、start_line、line_count 的 Schema，按启动目录解析路径，不应用搜索忽略规则。
2. 输出带原始行号的受限文本、格式元数据、截断与下一起始行；超出 EOF 正常返回空片段。
3. 新增 read_file 测试，覆盖默认 200 行、指定片段、非法范围、缺失/目录/不可读目标及工作目录外的受控临时文件。

**验证：** 运行 uv run python -m pytest tests/test_file_tools.py -k "read_file" -v；验证行号、内容、200 行上限及 20,000 字符预算。

**覆盖：** F2、AC2、N3、AC11。

### T12: 实现文件快照与预览失效检查

**文件：** [src/weizhcode/tools/file_utils.py](D:/STUDY/weizhcode-python/src/weizhcode/tools/file_utils.py)、[tests/test_file_tools.py](D:/STUDY/weizhcode-python/tests/test_file_tools.py)

**依赖：** T10

**步骤：**

1. 生成解析目标、存在状态、身份信息和流式内容指纹，记录 BOM 与换行策略。
2. 复核文件内容变化、目标重定向、被替换及原本不存在的目标已被创建。
3. 新增 file_snapshot 测试，分别改变内容和目标状态，确认失效结果不产生写入。

**验证：** 运行 uv run python -m pytest tests/test_file_tools.py -k "file_snapshot" -v；有效快照通过，变化场景返回 PREVIEW_STALE。

**覆盖：** F3、F4、F12、AC3、AC4。

### T13: 实现受控临时写入与替换

**文件：** [src/weizhcode/tools/file_utils.py](D:/STUDY/weizhcode-python/src/weizhcode/tools/file_utils.py)、[tests/test_file_tools.py](D:/STUDY/weizhcode-python/tests/test_file_tools.py)

**依赖：** T12

**步骤：**

1. 实现仅在执行阶段创建父目录和同目录临时文件、完整写入后替换目标的辅助逻辑。
2. 准备本轮临时路径登记信息，维护可保留的文件权限；失败清理仅属于本轮的临时文件。
3. 新增 atomic_write 测试，注入写入/替换失败，验证不会把部分输出当成功，不删除用户已有临时文件。

**验证：** 运行 uv run python -m pytest tests/test_file_tools.py -k "atomic_write" -v；检查实际字节、失败状态和临时文件归属。

**覆盖：** F3、F4、F13、AC3、AC4。

### T14: 实现 write_file 准备和预览

**文件：** [src/weizhcode/tools/write_file.py](D:/STUDY/weizhcode-python/src/weizhcode/tools/write_file.py)、[tests/test_file_tools.py](D:/STUDY/weizhcode-python/tests/test_file_tools.py)

**依赖：** T9、T12

**步骤：**

1. 定义 path/content 必填 Schema，允许空内容，requires_confirmation=True。
2. prepare 保存完整内容和目标快照，生成脱敏前的有界预览及预览截断标记，不 mkdir、不创建文件。
3. 新增 write_prepare 测试，覆盖新文件、覆盖、空文件、不支持编码及嵌套目标。

**验证：** 运行 uv run python -m pytest tests/test_file_tools.py -k "write_prepare" -v；准备前后目录树和文件字节完全一致。

**覆盖：** F3、F12、AC3。

### T15: 实现 write_file 执行

**文件：** [src/weizhcode/tools/write_file.py](D:/STUDY/weizhcode-python/src/weizhcode/tools/write_file.py)、[tests/test_file_tools.py](D:/STUDY/weizhcode-python/tests/test_file_tools.py)

**依赖：** T13、T14

**步骤：**

1. execute 只接受本次 PreparedOperation，先复核快照，再调用受控写入辅助逻辑。
2. 新文件采用 UTF-8 无 BOM/LF，已有文件保留 BOM 和换行规则；返回路径、字节数或明确错误。
3. 新增 write_execute 测试，验证创建/覆盖/嵌套/空内容及 PREVIEW_STALE 不覆盖外部变化。

**验证：** 运行 uv run python -m pytest tests/test_file_tools.py -k "write_execute" -v，检查磁盘字节和结构化状态；生产审批接线由执行器任务验证。

**覆盖：** F3、N4、AC3、AC13。

### T16: 实现跨块精确匹配扫描

**文件：** [src/weizhcode/tools/file_utils.py](D:/STUDY/weizhcode-python/src/weizhcode/tools/file_utils.py)、[tests/test_file_tools.py](D:/STUDY/weizhcode-python/tests/test_file_tools.py)

**依赖：** T10、T12

**步骤：**

1. 实现跨块原文扫描，保存唯一候选位置并完整累计匹配次数，不因缓冲边界重复计数。
2. 空原文直接返回参数错误，原文匹配不做空白、大小写或换行归一化。
3. 新增 exact_scan 测试，覆盖 0/1/多处、跨块、多字节、长片段和 CRLF/LF 不一致。

**验证：** 运行 uv run python -m pytest tests/test_file_tools.py -k "exact_scan" -v；实际计数正确，失败样本字节不变。

**覆盖：** F4、AC4。

### T17: 实现 edit_file 准备和差异预览

**文件：** [src/weizhcode/tools/edit_file.py](D:/STUDY/weizhcode-python/src/weizhcode/tools/edit_file.py)、[tests/test_file_tools.py](D:/STUDY/weizhcode-python/tests/test_file_tools.py)

**依赖：** T9、T12、T16

**步骤：**

1. 定义 path/old_text/new_text Schema 和需要审批标志，允许 new_text 为空。
2. 只在原文唯一匹配时形成可执行操作；0 次或多次返回实际计数和 MATCH_COUNT_ERROR。
3. 生成有界变更预览、唯一位置与文件快照；新增 edit_prepare 测试，确认所有准备路径不修改目标。

**验证：** 运行 uv run python -m pytest tests/test_file_tools.py -k "edit_prepare" -v，分别断言 0/1/多处计数、空原文错误和空新文的可准备性。

**覆盖：** F4、F12、AC4。

### T18: 实现 edit_file 执行与格式保留

**文件：** [src/weizhcode/tools/edit_file.py](D:/STUDY/weizhcode-python/src/weizhcode/tools/edit_file.py)、[src/weizhcode/tools/file_utils.py](D:/STUDY/weizhcode-python/src/weizhcode/tools/file_utils.py)、[tests/test_file_tools.py](D:/STUDY/weizhcode-python/tests/test_file_tools.py)

**依赖：** T13、T17

**步骤：**

1. 复核快照，使用已定位的唯一匹配完成替换或删除，并通过临时文件完整写入后替换。
2. 未修改部分保持原样，新增文本沿用已确认的换行策略，保留 BOM。
3. 新增 edit_execute 测试，覆盖批准后正确内容、删除、BOM、混合换行、目标已变化及写入失败。

**验证：** 运行 uv run python -m pytest tests/test_file_tools.py -k "edit_execute" -v，验证原始字节、匹配次数和失败时不覆盖新内容。

**覆盖：** F4、N4、AC4、AC13。

### T19: 实现搜索目录遍历和隐藏项处理

**文件：** [src/weizhcode/tools/search_utils.py](D:/STUDY/weizhcode-python/src/weizhcode/tools/search_utils.py)、[tests/test_search_tools.py](D:/STUDY/weizhcode-python/tests/test_search_tools.py)

**依赖：** T2、T4、T6

**步骤：**

1. 实现以指定根目录为范围的受控遍历，区分不存在、无法进入和中途访问失败。
2. 默认跳过点号隐藏项及系统隐藏属性，不跟随目录符号链接；显式目标和隐藏开关按 plan 处理。
3. 新增 search_walk 测试，覆盖隐藏开关、受控符号链接环、根目录错误和中途权限错误；平台不支持的样本明确 skip。

**验证：** 运行 uv run python -m pytest tests/test_search_tools.py -k "search_walk" -v，失败不能被报告成完整空结果。

**覆盖：** F8、AC6。

### T20: 实现分层 .gitignore 匹配

**文件：** [src/weizhcode/tools/search_utils.py](D:/STUDY/weizhcode-python/src/weizhcode/tools/search_utils.py)、[tests/test_search_tools.py](D:/STUDY/weizhcode-python/tests/test_search_tools.py)

**依赖：** T19

**步骤：**

1. 使用 GitIgnoreSpec 管理规则作用域、相对路径、先后顺序、否定规则及目录剪枝。
2. 从仓库边界到指定搜索子目录加载相关祖先规则，遍历时加载子目录规则；不读取 Git 全局配置。
3. 新增 gitignore_scope 测试，覆盖嵌套规则、重新包含、被排除父目录、从子目录搜索，以及 ignored/hidden 开关互不代替。

**验证：** 运行 uv run python -m pytest tests/test_search_tools.py -k "gitignore_scope" -v，无需安装或调用 Git。

**覆盖：** F8、AC6。

### T21: 实现 find_files

**文件：** [src/weizhcode/tools/find_files.py](D:/STUDY/weizhcode-python/src/weizhcode/tools/find_files.py)、[src/weizhcode/tools/search_utils.py](D:/STUDY/weizhcode-python/src/weizhcode/tools/search_utils.py)、[tests/test_search_tools.py](D:/STUDY/weizhcode-python/tests/test_search_tools.py)

**依赖：** T9、T20

**步骤：**

1. 定义 pattern/path/两个包含开关，使用 wcmatch 的 glob 匹配与已有受控遍历。
2. 处理 ** 根目录和跨层级文件、分隔符及平台大小写；结果最多 200 条且遵守字符预算。
3. 新增 find_files 测试，覆盖普通 glob、根目录 .py、嵌套、隐藏忽略开关、空结果、无效根及截断。

**验证：** 运行 uv run python -m pytest tests/test_search_tools.py -k "find_files" -v；无匹配为 success，超限有明确标记。

**覆盖：** F6、F8、N3、AC6、AC11。

### T22: 实现普通文本内容搜索

**文件：** [src/weizhcode/tools/search_content.py](D:/STUDY/weizhcode-python/src/weizhcode/tools/search_content.py)、[src/weizhcode/tools/search_utils.py](D:/STUDY/weizhcode-python/src/weizhcode/tools/search_utils.py)、[tests/test_search_tools.py](D:/STUDY/weizhcode-python/tests/test_search_tools.py)

**依赖：** T9、T10、T20

**步骤：**

1. 定义 pattern/path/is_regex/包含开关，默认普通文本且区分大小写。
2. 逐行输出文件、行号、命中内容，二进制及非 UTF-8 文件跳过并记录数量；读取使用受限缓冲。
3. 新增 search_literal 测试，验证点号和括号被按原文处理、行号正确、空结果与过滤范围正确。

**验证：** 运行 uv run python -m pytest tests/test_search_tools.py -k "search_literal" -v，无效路径与正常无命中状态不同。

**覆盖：** F7、F8、AC6。

### T23: 补齐正则搜索与不完整检索反馈

**文件：** [src/weizhcode/tools/search_content.py](D:/STUDY/weizhcode-python/src/weizhcode/tools/search_content.py)、[src/weizhcode/tools/search_utils.py](D:/STUDY/weizhcode-python/src/weizhcode/tools/search_utils.py)、[tests/test_search_tools.py](D:/STUDY/weizhcode-python/tests/test_search_tools.py)

**依赖：** T22

**步骤：**

1. 显式正则模式才编译表达式，非法表达式返回 INVALID_REGEX。
2. 加入 100 条/20,000 字符限制、超长行与访问失败的不完整提示，保留有限部分结果及原因。
3. 新增 search_limits 测试，覆盖正则命中、非法模式、海量命中、超长行、编码跳过数量和权限中断。

**验证：** 运行 uv run python -m pytest tests/test_search_tools.py -k "search_limits" -v，超限和未完整搜索均不得伪装为完整无命中。

**覆盖：** F7、F13、N3、AC6、AC10、AC11。

### T24: 实现命令准备和 shell 选择

**文件：** [src/weizhcode/tools/run_command.py](D:/STUDY/weizhcode-python/src/weizhcode/tools/run_command.py)、[tests/test_command_tool.py](D:/STUDY/weizhcode-python/tests/test_command_tool.py)

**依赖：** T9、T12

**步骤：**

1. 定义 command/cwd Schema 和需要审批标志，准备时展示完整命令、实际目录和所选 shell。
2. Windows 选 pwsh 或 powershell，POSIX 选 /bin/sh；校验 cwd，准备阶段不启动命令，不修改主进程 cwd。
3. 新增 command_prepare 测试，覆盖默认/指定目录、缺失 shell、空命令、无效目录与准备阶段无进程副作用。

**验证：** 运行 uv run python -m pytest tests/test_command_tool.py -k "command_prepare" -v，校验目标目录和原始命令完全保留。

**覆盖：** F5、F12、AC5。

### T25: 实现命令输出收集与结果

**文件：** [src/weizhcode/tools/run_command.py](D:/STUDY/weizhcode-python/src/weizhcode/tools/run_command.py)、[src/weizhcode/tools/limits.py](D:/STUDY/weizhcode-python/src/weizhcode/tools/limits.py)、[tests/test_command_tool.py](D:/STUDY/weizhcode-python/tests/test_command_tool.py)

**依赖：** T6、T24

**步骤：**

1. 执行准备好的非交互 shell，关闭 stdin，在 Windows 使用后台隐藏窗口设置，不加载个人 profile。
2. 同时消费 stdout/stderr，增量解码并共享有限保留预算；达到上限后继续排空，退出码单独保留。
3. 新增 command_output 测试，仅执行短小受控命令，覆盖输出来源、中文、非零退出、长输出截断与目录/环境不持久。

**验证：** 运行 uv run python -m pytest tests/test_command_tool.py -k "command_output" -v，非零退出为 COMMAND_FAILED，stdout/stderr 不相互冒充；长时终止在进程管理任务验证。

**覆盖：** F5、F13、N3、AC5、AC10、AC11。

### T26: 组装默认六工具注册表

**文件：** [src/weizhcode/tools/__init__.py](D:/STUDY/weizhcode-python/src/weizhcode/tools/__init__.py)、[tests/test_tool_registry.py](D:/STUDY/weizhcode-python/tests/test_tool_registry.py)

**依赖：** T11、T15、T18、T21、T23、T25

**步骤：**

1. 实现 create_default_registry，按已批准顺序注册六个真实工具。
2. 包入口避免导入循环；权限仅 write_file/edit_file/run_command 为真，不按位置推断。
3. 新增 default_registry 测试，检查六条稳定定义、每项参数、审批标志和 get 查询。

**验证：** 运行 uv run python -m pytest tests/test_tool_registry.py -k "default_registry" -v，definitions 数量恰为 6，名称顺序和权限标志准确。

**覆盖：** F1、F12、AC1。

## 3. 工作进程、逐次审批与真实终止

### T27: 实现 POSIX 进程组生命周期

**文件：** [src/weizhcode/tools/process.py](D:/STUDY/weizhcode-python/src/weizhcode/tools/process.py)、[tests/test_tool_executor.py](D:/STUDY/weizhcode-python/tests/test_tool_executor.py)

**依赖：** T4、T6

**步骤：**

1. 封装独立会话/进程组启动、终止、必要时强杀和回收，接口不导入 TUI 或 Provider。
2. 清理操作保持幂等；普通成功、超时和应用退出共用收尾路径，关闭管道。
3. 新增 posix_process 测试；在 POSIX 实测受控进程，在 Windows 仅验证分支调用与平台隔离并明确记录 skip。

**验证：** 运行 uv run python -m pytest tests/test_tool_executor.py -k "posix_process" -v；区分真实平台测试和模拟测试，不把 skip 算成 POSIX 实测通过。

**覆盖：** N1、AC5。

### T28: 实现 Windows Job 生命周期

**文件：** [src/weizhcode/tools/process.py](D:/STUDY/weizhcode-python/src/weizhcode/tools/process.py)、[tests/test_tool_executor.py](D:/STUDY/weizhcode-python/tests/test_tool_executor.py)

**依赖：** T4、T6

**步骤：**

1. 以 ctypes 封装 Job 创建、KILL_ON_JOB_CLOSE、分配工作进程、终止和句柄关闭，不启用 breakaway。
2. Job 建立/分配失败时拒绝释放启动握手，清理待命进程并返回 PROCESS_CONTROL_FAILED。
3. 新增 windows_job 测试，验证句柄清理、失败路径及本机受控进程关联；非 Windows 分支隔离并明确 skip。

**验证：** 运行 uv run python -m pytest tests/test_tool_executor.py -k "windows_job" -v；本机能证明关联进程在关闭 Job 后结束，分配失败不会启动用户命令。

**覆盖：** N1、F13、AC5、AC10。

### T29: 实现工作进程通信状态机

**文件：** [src/weizhcode/tools/worker.py](D:/STUDY/weizhcode-python/src/weizhcode/tools/worker.py)、[tests/test_tool_executor.py](D:/STUDY/weizhcode-python/tests/test_tool_executor.py)

**依赖：** T26

**步骤：**

1. 实现内部模块入口，只接受 prepare/execute/abort；启动后先等待父进程允许的握手。
2. 准备记录留在子进程，只回传有界预览和 operation_id；准备失败直接形成结构化结果，不开放 execute。
3. stdout 仅写内部协议；未知指令、错误 operation_id、重复执行和 abort 后执行一律拒绝，预期错误不输出堆栈。

**验证：** 新增 worker_protocol 测试并运行 uv run python -m pytest tests/test_tool_executor.py -k "worker_protocol" -v；使用受控管道与临时目录，验证状态不匹配无副作用。

**覆盖：** F12、F13、AC3、AC10。

### T30: 实现 ManagedWorker 启动与安全传输

**文件：** [src/weizhcode/tools/process.py](D:/STUDY/weizhcode-python/src/weizhcode/tools/process.py)、[src/weizhcode/tools/worker.py](D:/STUDY/weizhcode-python/src/weizhcode/tools/worker.py)、[tests/test_tool_executor.py](D:/STUDY/weizhcode-python/tests/test_tool_executor.py)

**依赖：** T27、T28、T29

**步骤：**

1. 使用当前解释器启动 worker，通过私有管道传参，命令行中不含文件正文或密钥。
2. 先建立 Job/进程组管理，再释放握手；实现 prepare/execute/aclose，并分离 shell 输出和协议流。
3. 登记本轮临时文件清理信息，限定清理归属；新增 managed_worker 测试，验证正常读取、错误、重复关闭和通信损坏。

**验证：** 运行 uv run python -m pytest tests/test_tool_executor.py -k "managed_worker" -v；通信损坏和控制建立失败时不执行模型命令，进程及本轮临时文件被正确收尾。

**覆盖：** F13、N1、AC5、AC10。

### T31: 实现执行器参数校验出口

**文件：** [src/weizhcode/tools/executor.py](D:/STUDY/weizhcode-python/src/weizhcode/tools/executor.py)、[tests/test_tool_executor.py](D:/STUDY/weizhcode-python/tests/test_tool_executor.py)

**依赖：** T6、T7、T9、T26

**步骤：**

1. 验证调用 ID、名称、原始 JSON、顶层对象和对应工具 Schema，不信任预填的 arguments 绕过原始校验。
2. 未知工具、无效 JSON、缺失/多余字段、布尔伪整数等生成统一 ToolResult，流程不启动工作进程。
3. 新增 executor_validation 测试，断言各错误代码及零次 worker 启动。

**验证：** 运行 uv run python -m pytest tests/test_tool_executor.py -k "executor_validation" -v，全部无效调用均无磁盘或命令副作用。

**覆盖：** F10、F13、AC7、AC10。

### T32: 实现执行器自动工具路径

**文件：** [src/weizhcode/tools/executor.py](D:/STUDY/weizhcode-python/src/weizhcode/tools/executor.py)、[tests/test_tool_executor.py](D:/STUDY/weizhcode-python/tests/test_tool_executor.py)

**依赖：** T30、T31

**步骤：**

1. 实现 ToolExecutor.run 的准备、执行、结果事件，读取类工具不发审批请求。
2. 对结果统一脱敏和预算处理，再向上输出 tool_result；准备失败直接输出失败结果。
3. 新增 executor_readonly 测试，使用临时文件验证三种自动工具、状态顺序、错误转换和正常清理。

**验证：** 运行 uv run python -m pytest tests/test_tool_executor.py -k "executor_readonly" -v；事件能看到准备/执行/结果，成功与空结果均不会误报错误。

**覆盖：** F2、F6、F7、F13、AC2、AC6、AC10。

### T33: 实现执行器逐次审批路径

**文件：** [src/weizhcode/tools/executor.py](D:/STUDY/weizhcode-python/src/weizhcode/tools/executor.py)、[tests/test_tool_executor.py](D:/STUDY/weizhcode-python/tests/test_tool_executor.py)

**依赖：** T32

**步骤：**

1. 对有副作用工具先输出 approval_required，再等待绑定该 request_id/operation_id 的审批回调。
2. 拒绝或缺少审批处理器时返回 USER_DENIED；批准后仅发送该 operation_id 的 execute，不重新取模型参数。
3. 新增 executor_approval 测试，覆盖等待磁盘不变、拒绝不 mkdir/不写/不启动命令、批准正确执行及陈旧操作拒绝。

**验证：** 运行 uv run python -m pytest tests/test_tool_executor.py -k "executor_approval" -v；分别以文件字节、目录存在性和受控命令标记验证零副作用边界。

**覆盖：** F12、AC3、AC4、AC5、AC10。

### T34: 实现共享超时预算和异常收尾

**文件：** [src/weizhcode/tools/executor.py](D:/STUDY/weizhcode-python/src/weizhcode/tools/executor.py)、[src/weizhcode/tools/process.py](D:/STUDY/weizhcode-python/src/weizhcode/tools/process.py)、[tests/test_tool_executor.py](D:/STUDY/weizhcode-python/tests/test_tool_executor.py)

**依赖：** T33

**步骤：**

1. 准备与执行累计使用单调时钟预算，等待审批暂停，批准后恢复剩余预算而非重置 30 秒。
2. 超时、通信失败、外部退出和异常都先终止受管进程，再回收管道和本轮登记临时文件；aclose 幂等。
3. 新增 executor_timeout 测试，使用内部短预算验证准备超时、执行超时、长审批等待不超时、异常清理和保留有限输出。

**验证：** 运行 uv run python -m pytest tests/test_tool_executor.py -k "executor_timeout" -v；生产常量仍为 30 秒，未增加用户配置字段。

**覆盖：** N1、F13、AC5、AC10。

### T35: 验证命令后代终止与输出压力

**文件：** [tests/test_command_tool.py](D:/STUDY/weizhcode-python/tests/test_command_tool.py)、[tests/test_tool_executor.py](D:/STUDY/weizhcode-python/tests/test_tool_executor.py)、[src/weizhcode/tools/process.py](D:/STUDY/weizhcode-python/src/weizhcode/tools/process.py)、[src/weizhcode/tools/run_command.py](D:/STUDY/weizhcode-python/src/weizhcode/tools/run_command.py)

**依赖：** T25、T34

**步骤：**

1. 通过真实执行器启动受控父子进程，记录进程身份，在超时后确认父子均结束，而非只看到界面错误。
2. 构造 stdout/stderr 同时大量输出，验证保留有界、退出码保留、管道不死锁。
3. 新增 process_tree 与 output_pressure 测试；仅在实际支持的平台执行原生断言，不为测试安装其他系统环境。

**验证：** 运行 uv run python -m pytest tests/test_command_tool.py tests/test_tool_executor.py -k "process_tree or output_pressure" -v；保存本机证据和被跳过的平台。

**覆盖：** F5、N1、N3、AC5、AC11。

## 4. 会话历史、三协议适配与系统说明

### T36: 实现完整历史交换与防御性副本

**文件：** [src/weizhcode/conversation.py](D:/STUDY/weizhcode-python/src/weizhcode/conversation.py)、[tests/test_conversation.py](D:/STUDY/weizhcode-python/tests/test_conversation.py)

**依赖：** T3、T5

**步骤：**

1. 实现 add_assistant_turn 和 add_tool_exchange，正常调用必须与结果按 ID 对应，一次提交完整交换。
2. 保留原文字追加方法，messages 对嵌套调用、结果和 provider_payload 进行防御性复制。
3. 新增 tool_history 测试，验证文字/调用/结果/续答顺序、全部 ID 配对、外部修改不影响内部历史，以及异常诊断交换可追踪。

**验证：** 运行 uv run python -m pytest tests/test_conversation.py -v，原有普通对话测试继续通过。

**覆盖：** F16、AC8。

### T37: 扩展 Provider 接口并保留纯聊天

**文件：** [src/weizhcode/providers/base.py](D:/STUDY/weizhcode-python/src/weizhcode/providers/base.py)、[src/weizhcode/providers/anthropic.py](D:/STUDY/weizhcode-python/src/weizhcode/providers/anthropic.py)、[src/weizhcode/providers/openai.py](D:/STUDY/weizhcode-python/src/weizhcode/providers/openai.py)、[src/weizhcode/providers/qwen.py](D:/STUDY/weizhcode-python/src/weizhcode/providers/qwen.py)、[tests/test_provider_events.py](D:/STUDY/weizhcode-python/tests/test_provider_events.py)、[tests/test_tui.py](D:/STUDY/weizhcode-python/tests/test_tui.py)

**依赖：** T3、T5

**步骤：**

1. stream_chat 增加 tools/system_prompt/allow_tools 关键字参数，默认值兼容现有无工具调用。
2. 同步修改三个适配器和测试 FakeProvider 的签名，不让工具执行或 UI 类型进入 Provider。
3. 新增 provider_interface 测试，验证统一参数可传递、普通文字和旧入口仍可使用。

**验证：** 运行 uv run python -m pytest tests/test_provider_events.py tests/test_tui.py -v；本任务只扩展接口，不把尚未接入的工具能力报告为可用。

**覆盖：** F9、F14、N7、AC1、AC13。

### T38: 实现 Anthropic 请求与历史编码

**文件：** [src/weizhcode/providers/anthropic.py](D:/STUDY/weizhcode-python/src/weizhcode/providers/anthropic.py)、[tests/test_provider_events.py](D:/STUDY/weizhcode-python/tests/test_provider_events.py)

**依赖：** T8、T26、T36、T37

**步骤：**

1. 注入 system 与 input_schema 工具定义；首次 auto 禁用并行，最终请求 type=none。
2. 编码助手 tool_use 和紧随其后的 user/tool_result，保留真实 ID，失败设置 is_error，全部结果置于文字之前。
3. 新增 anthropic_payload 测试，验证普通/成功/失败/多个拒绝的请求体，以及缺 ID/无效 JSON 的明确诊断文本回灌、不伪造 ID。

**验证：** 运行 uv run python -m pytest tests/test_provider_events.py -k "anthropic_payload" -v，逐项断言六定义、控制字段、结果顺序和诊断脱敏。

**覆盖：** F9、F14、F16、AC1、AC8、AC12。

### T39: 实现 Anthropic 工具 SSE 组装

**文件：** [src/weizhcode/providers/anthropic.py](D:/STUDY/weizhcode-python/src/weizhcode/providers/anthropic.py)、[tests/test_provider_events.py](D:/STUDY/weizhcode-python/tests/test_provider_events.py)

**依赖：** T38

**步骤：**

1. 按 block index 组装 tool_use/input_json_delta，正文独立输出，最终完整对象不能重复追加到碎片。
2. 必须等 message_stop 和有效 stop_reason 才输出成功 done；中断、错误和 max_tokens 等不得允许执行缓冲调用。
3. 新增 anthropic_tool_stream 测试，覆盖中文/转义参数碎片、多个块、空输入对象、混合正文、局部块结束但整轮未结束及思考不展示。

**验证：** 运行 uv run python -m pytest tests/test_provider_events.py -k "anthropic_tool_stream" -v，断言正确拼接和失败无成功 done。

**覆盖：** F10、F14、AC7、AC12。

### T40: 实现 OpenAI Responses 请求与回放

**文件：** [src/weizhcode/providers/openai.py](D:/STUDY/weizhcode-python/src/weizhcode/providers/openai.py)、[tests/test_provider_events.py](D:/STUDY/weizhcode-python/tests/test_provider_events.py)

**依赖：** T8、T26、T36、T37

**步骤：**

1. 使用扁平 function 定义、strict=False、instructions、store=False、首次 parallel_tool_calls=False，最终 tool_choice=none。
2. 保留必要 output items 及 stateless 加密回放内容，按 call_id 编码 function_call_output，不重复构造已经保留的助手项。
3. 新增 openai_payload 测试，验证六工具、可选参数、完整回放、失败结果、异常诊断和不透明数据不被展示或改写；不引入 Chat Completions 或 SDK。

**验证：** 运行 uv run python -m pytest tests/test_provider_events.py -k "openai_payload" -v，断言请求仍走 /responses 且回放和结果顺序准确。

**覆盖：** F9、F14、F16、AC1、AC8、AC12。

### T41: 实现 OpenAI Responses 工具 SSE 组装

**文件：** [src/weizhcode/providers/openai.py](D:/STUDY/weizhcode-python/src/weizhcode/providers/openai.py)、[tests/test_provider_events.py](D:/STUDY/weizhcode-python/tests/test_provider_events.py)

**依赖：** T40

**步骤：**

1. 按 output_index/item 标识收集 function_call 及 arguments delta，最终项用于校对而非重复追加。
2. 只接受 response.completed 的完整成功响应；arguments.done/item.done 不能独自放行，failed/incomplete/error/意外 EOF 均为错误。
3. 新增 openai_tool_stream 测试，覆盖交错分片、正文、调用 ID、回放项、重复最终参数与各类提前终止。

**验证：** 运行 uv run python -m pytest tests/test_provider_events.py -k "openai_tool_stream" -v，校验完整 raw_arguments 及失败不产生可执行成功回合。

**覆盖：** F10、F14、AC7、AC12。

### T42: 实现千问请求与历史编码

**文件：** [src/weizhcode/providers/qwen.py](D:/STUDY/weizhcode-python/src/weizhcode/providers/qwen.py)、[tests/test_provider_events.py](D:/STUDY/weizhcode-python/tests/test_provider_events.py)

**依赖：** T8、T26、T36、T37

**步骤：**

1. 注入 system 消息与 function 内嵌定义，首次 auto、最终 none，不依赖兼容端点一定支持并行控制参数。
2. 保留 assistant.tool_calls，随后每个 tool_call_id 对应一条 role=tool 结果；异常调用走明确诊断文本，不留下孤立结果。
3. 新增 qwen_payload 测试，验证六定义、普通/失败/拒绝结果、多个限制结果、最终禁用与诊断脱敏。

**验证：** 运行 uv run python -m pytest tests/test_provider_events.py -k "qwen_payload" -v，断言仍走 /chat/completions 且每个正常调用结果均对应真实 ID。

**覆盖：** F9、F14、F16、AC1、AC8、AC12。

### T43: 实现千问工具 SSE 组装

**文件：** [src/weizhcode/providers/qwen.py](D:/STUDY/weizhcode-python/src/weizhcode/providers/qwen.py)、[tests/test_provider_events.py](D:/STUDY/weizhcode-python/tests/test_provider_events.py)

**依赖：** T42

**步骤：**

1. 按 delta.tool_calls.index 分别收集名称、ID 和参数，区分正文与思考，处理空 choices/空增量。
2. 检查 finish_reason 与流终止标记；tool_calls 为工具完成，stop 为文字完成，截断/过滤/异常 EOF 不允许执行。
3. 新增 qwen_tool_stream 测试，覆盖混合正文、交错参数、多个请求、缺 ID、重复 ID、无效参数与不完整结束。

**验证：** 运行 uv run python -m pytest tests/test_provider_events.py -k "qwen_tool_stream" -v，确认没有跨工具混参或将 EOF 直接当成功。

**覆盖：** F10、F14、AC7、AC12。

### T44: 加入内置工具使用说明

**文件：** [src/weizhcode/prompts.py](D:/STUDY/weizhcode-python/src/weizhcode/prompts.py)、[tests/test_turn_runner.py](D:/STUDY/weizhcode-python/tests/test_turn_runner.py)

**依赖：** T26

**步骤：**

1. 定义统一系统说明，涵盖六工具、审批、单工具上限、行号非原文、精确替换、截断及工具输出作为数据。
2. 定义最终续答要求，要求基于结果直接回答，不伪造执行成功，不依赖提示词代替本地硬限制。
3. 新增 prompts 测试，验证名称与实际注册表一致、无凭证及项目私密内容，首轮/最终阶段约定明确。

**验证：** 运行 uv run python -m pytest tests/test_turn_runner.py -k "prompts" -v，所有六个工具名称均能与注册表对应。

**覆盖：** F9、AC1。

## 5. 固定单工具闭环

### T45: 实现单轮协调器的纯文字分支

**文件：** [src/weizhcode/turn_runner.py](D:/STUDY/weizhcode-python/src/weizhcode/turn_runner.py)、[tests/test_turn_runner.py](D:/STUDY/weizhcode-python/tests/test_turn_runner.py)

**依赖：** T8、T34、T36、T39、T41、T43、T44

**步骤：**

1. 构造 TurnRunner，接收统一 Provider、Conversation、Registry、Executor、系统说明和 Redactor，不导入具体后端实现。
2. 建立单轮占用，保存用户消息，转发 initial 文字；无工具时只提交完整助手消息并结束。
3. 新增 runner_text 测试，验证仅一次请求、系统说明/六定义传入、未收到成功 done 不提交残缺回复及输入防重入。

**验证：** 运行 uv run python -m pytest tests/test_turn_runner.py -k "runner_text" -v；FakeProvider 记录一次调用，Executor 零次执行。

**覆盖：** F9、F11、N7、AC1、AC13。

### T46: 实现一个工具后的最终续答

**文件：** [src/weizhcode/turn_runner.py](D:/STUDY/weizhcode-python/src/weizhcode/turn_runner.py)、[tests/test_turn_runner.py](D:/STUDY/weizhcode-python/tests/test_turn_runner.py)

**依赖：** T45

**步骤：**

1. 只在整个初次响应成功结束且恰好一个调用时进入 ToolExecutor，按序转发准备/审批/执行/结果事件。
2. 取得结果后原子提交调用和结果，发起 allow_tools=False 的最终请求，转发 final 文字并保存完整回复。
3. 新增 runner_tool_round 测试，覆盖成功、拒绝、失败和超时均只进行一次最终续答，并检查第二次请求携带实际结果而非 UI 摘要。

**验证：** 运行 uv run python -m pytest tests/test_turn_runner.py -k "runner_tool_round" -v；模型调用至多两次，工具执行至多一次，历史顺序和 ID 正确。

**覆盖：** F11、F12、F13、F16、AC8、AC10。

### T47: 实现多个调用和最终阶段硬限制

**文件：** [src/weizhcode/turn_runner.py](D:/STUDY/weizhcode-python/src/weizhcode/turn_runner.py)、[tests/test_turn_runner.py](D:/STUDY/weizhcode-python/tests/test_turn_runner.py)

**依赖：** T46

**步骤：**

1. 初次回复多个调用时全部拒绝，prepare/execute 均不调用，为各可识别 ID 生成 TOO_MANY_TOOL_CALLS。
2. 最终续答仍请求工具时全部禁止，补记 TOOL_ROUND_LIMIT 结果并显示提示，不请求第三次模型。
3. 新增 runner_limits 测试，覆盖两个读工具、两个副作用工具、混合调用和最终阶段再次调用，确认不部分执行。

**验证：** 运行 uv run python -m pytest tests/test_turn_runner.py -k "runner_limits" -v，分别断言零次准备/执行或仅首次执行，以及模型请求数不超过两次。

**覆盖：** F11、AC9。

### T48: 补齐协调器错误历史和退出收尾

**文件：** [src/weizhcode/turn_runner.py](D:/STUDY/weizhcode-python/src/weizhcode/turn_runner.py)、[src/weizhcode/conversation.py](D:/STUDY/weizhcode-python/src/weizhcode/conversation.py)、[tests/test_turn_runner.py](D:/STUDY/weizhcode-python/tests/test_turn_runner.py)

**依赖：** T47

**步骤：**

1. 区分完整但无效的调用与未完成响应；前者保存诊断结果后文字续答，后者直接结束且不执行。
2. 最终请求失败时保留已发生的真实工具交换，不自动重试或重做副作用；所有路径恢复状态。
3. 新增 runner_recovery 测试，覆盖无效 JSON/缺 ID、初次中断、最终网络失败、异常关闭及下一次提问继续工作。

**验证：** 运行 uv run python -m pytest tests/test_turn_runner.py -k "runner_recovery" -v；验证后续历史合法、工具不重复执行、资源关闭不触发额外 API。

**覆盖：** F10、F13、F16、AC7、AC8、AC10。

## 6. 界面、入口与跨层集成

### T49: 实现工具视图的状态与安全摘要

**文件：** [src/weizhcode/tool_ui.py](D:/STUDY/weizhcode-python/src/weizhcode/tool_ui.py)、[tests/test_tui.py](D:/STUDY/weizhcode-python/tests/test_tui.py)

**依赖：** T5、T6、T7

**步骤：**

1. 新增 ToolCallView，显示工具名、关键参数、pending/preparing/running/成功/失败/拒绝状态和有界结果摘要。
2. 正文作为普通安全文本，不执行 ANSI/Rich 标记；结果摘要最多 8 行/1,000 字符，截断有提示。
3. 新增 tool_view 测试，使用局部测试 App 验证同一视图更新、格式文本安全及摘要不替代原 ToolResult。

**验证：** 运行 uv run python -m pytest tests/test_tui.py -k "tool_view" -v，检查 displayed text、状态和摘要上限。

**覆盖：** F15、N3、AC11。

### T50: 实现审批按钮与 Future 桥接

**文件：** [src/weizhcode/tool_ui.py](D:/STUDY/weizhcode-python/src/weizhcode/tool_ui.py)、[src/weizhcode/tui.py](D:/STUDY/weizhcode-python/src/weizhcode/tui.py)、[tests/test_tui.py](D:/STUDY/weizhcode-python/tests/test_tui.py)

**依赖：** T33、T49

**步骤：**

1. 显示实际目标/变更预览或完整命令/cwd，创建绑定 request_id 和 operation_id 的等待 Future。
2. 提供允许本次/拒绝本次，默认焦点拒绝；选择后立即禁用两按钮、保留决定，再完成 Future。
3. 新增 approval_ui 测试，用 Pilot 点击批准/拒绝、重复点击及过期消息；等待过程中界面能处理其他消息。

**验证：** 运行 uv run python -m pytest tests/test_tui.py -k "approval_ui" -v，确认无自动批准、双击不重复决定、按钮能解除等待且不阻塞消息循环。

**覆盖：** F12、N2、AC3、AC10、AC11。

### T51: 接入 TurnEvent 并完成入口接线

**文件：** [src/weizhcode/tui.py](D:/STUDY/weizhcode-python/src/weizhcode/tui.py)、[src/weizhcode/cli.py](D:/STUDY/weizhcode-python/src/weizhcode/cli.py)、[tests/test_tui.py](D:/STUDY/weizhcode-python/tests/test_tui.py)

**依赖：** T48、T50

**步骤：**

1. TUI 提交改为通过后台 worker 消费 TurnRunner；提交时立即防重入，等待期间允许草稿与滚动但不提交新问题。
2. 按 initial 文字、工具视图、结果、final 文字顺序创建或更新组件，不交错或重复提交历史。
3. 同一任务更新 cli 的组件构造与 TUI 注入，避免入口参数短暂不匹配；同步更新测试工厂和 FakeRunner/FakeProvider。

**验证：** 新增 turn_event_ui 测试并运行 uv run python -m pytest tests/test_tui.py -k "turn_event_ui" -v，验证事件顺序、两次连续提交只产生一轮、草稿保留及 cli 构造契约。

**覆盖：** F11、F15、N2、AC8、AC9、AC11。

### T52: 接入分层错误与统一安全显示

**文件：** [src/weizhcode/tui.py](D:/STUDY/weizhcode-python/src/weizhcode/tui.py)、[src/weizhcode/tool_ui.py](D:/STUDY/weizhcode-python/src/weizhcode/tool_ui.py)、[src/weizhcode/redaction.py](D:/STUDY/weizhcode-python/src/weizhcode/redaction.py)、[tests/test_tui.py](D:/STUDY/weizhcode-python/tests/test_tui.py)

**依赖：** T51

**步骤：**

1. 工具失败、拒绝和超时在工具行内联展示；配置/模型请求错误沿用错误面板。
2. 接入跨分片安全正文与预览脱敏，错误确认后恢复可用状态；未完成文字不能显示为成功结果。
3. 新增 tui_recovery 测试，触发工具错误、模型错误、受控密钥和控制字符，再发普通问题验证恢复。

**验证：** 运行 uv run python -m pytest tests/test_tui.py -k "tui_recovery" -v，确认安全文本、正确错误位置、无崩溃且新请求可以提交。

**覆盖：** F13、F15、N6、AC10、AC11、AC13。

### T53: 验证启动元信息与配置兼容

**文件：** [src/weizhcode/cli.py](D:/STUDY/weizhcode-python/src/weizhcode/cli.py)、[src/weizhcode/tui.py](D:/STUDY/weizhcode-python/src/weizhcode/tui.py)、[tests/test_tui.py](D:/STUDY/weizhcode-python/tests/test_tui.py)、[tests/test_config.py](D:/STUDY/weizhcode-python/tests/test_config.py)

**依赖：** T51

**步骤：**

1. 状态栏根据真实 Registry 数量显示 6 tools、0 MCP，保留版本、模型、目录和供应商信息。
2. 构造 Redactor 时只使用已解析的密钥，不强行解析非默认供应商环境变量，不修改原配置格式。
3. 新增 startup_tools 测试，覆盖 cli 正常构造、配置失败面板、状态栏、默认后端密钥可用而其他后端未设置的情况。

**验证：** 运行 uv run python -m pytest tests/test_tui.py tests/test_config.py -v；原有 YAML 字段和默认选择规则不变。

**覆盖：** F1、F14、N7、AC1、AC13。

### T54: 实现应用退出与待审批失效

**文件：** [src/weizhcode/tui.py](D:/STUDY/weizhcode-python/src/weizhcode/tui.py)、[src/weizhcode/turn_runner.py](D:/STUDY/weizhcode-python/src/weizhcode/turn_runner.py)、[src/weizhcode/tools/executor.py](D:/STUDY/weizhcode-python/src/weizhcode/tools/executor.py)、[tests/test_tui.py](D:/STUDY/weizhcode-python/tests/test_tui.py)、[tests/test_tool_executor.py](D:/STUDY/weizhcode-python/tests/test_tool_executor.py)

**依赖：** T34、T51、T52

**步骤：**

1. 退出整个应用时先使待审批失效，关闭协调器与模型流，终止受管工作进程并等待回收。
2. 保证空闲、等待审批、工具执行和最终生成阶段均能退出；仍不提供单独取消当前操作的功能。
3. 新增 app_shutdown 测试，覆盖退出命令/快捷键、等待中的 Future、重复关闭和退出后无新 API 请求或晚到写入。

**验证：** 运行 uv run python -m pytest tests/test_tui.py tests/test_tool_executor.py -k "app_shutdown" -v；进程清理和待审批拒绝有实际断言。

**覆盖：** N1、N2、F12、AC5、AC11、AC13。

### T55: 验证安全与体量跨层出口

**文件：** [tests/test_redaction.py](D:/STUDY/weizhcode-python/tests/test_redaction.py)、[tests/test_tool_executor.py](D:/STUDY/weizhcode-python/tests/test_tool_executor.py)、[tests/test_turn_runner.py](D:/STUDY/weizhcode-python/tests/test_turn_runner.py)、[tests/test_tui.py](D:/STUDY/weizhcode-python/tests/test_tui.py)、[tests/test_provider_events.py](D:/STUDY/weizhcode-python/tests/test_provider_events.py)

**依赖：** T52、T54

**步骤：**

1. 将受控假密钥分别置于文件内容、命令输出、工具错误、审批预览和拆分正文中，检查所有可见与模型结果出口。
2. 验证脱敏不更改实际写入内容/执行参数，回传结果经脱敏后仍满足总预算并保留必要元数据。
3. 新增 security_pipeline 测试，覆盖 UI 摘要截断与实际结果分离，以及已知密钥之外的信息不被宣称为自动保护。

**验证：** 运行 uv run python -m pytest tests/test_redaction.py tests/test_tool_executor.py tests/test_turn_runner.py tests/test_tui.py tests/test_provider_events.py -k "security_pipeline" -v，不使用任何真实密钥作为测试数据。

**覆盖：** N3、N6、AC11、AC13。

### T56: 验证三后端同组闭环

**文件：** [tests/test_provider_events.py](D:/STUDY/weizhcode-python/tests/test_provider_events.py)、[tests/test_turn_runner.py](D:/STUDY/weizhcode-python/tests/test_turn_runner.py)、[tests/test_conversation.py](D:/STUDY/weizhcode-python/tests/test_conversation.py)

**依赖：** T39、T41、T43、T48、T55

**步骤：**

1. 以同组模拟流驱动 Anthropic、OpenAI Responses、千问 Provider，结合临时文件和真实执行器完成读取、回灌、最终回复。
2. 逐项验证正常/拒绝/失败、多个全部拒绝、最终额外调用、异常诊断及下一轮历史，不把聊天兼容格式误当 Responses 格式。
3. 新增 protocol_integration 测试，记录每种协议的两次请求体、执行计数和回放；测试内容不依赖线上 API。

**验证：** 运行 uv run python -m pytest tests/test_provider_events.py tests/test_turn_runner.py tests/test_conversation.py -k "protocol_integration" -v，三个后端参数化场景均被实际执行。

**覆盖：** F14、N5、N8、AC8、AC9、AC10、AC12。

## 7. 回归、PowerShell 与真实 API 验收

### T57: 执行全量自动回归与编译检查

**文件：** [tests/test_config.py](D:/STUDY/weizhcode-python/tests/test_config.py)、[tests/test_conversation.py](D:/STUDY/weizhcode-python/tests/test_conversation.py)、[tests/test_provider_events.py](D:/STUDY/weizhcode-python/tests/test_provider_events.py)、[tests/test_tui.py](D:/STUDY/weizhcode-python/tests/test_tui.py)、[tests/test_tool_registry.py](D:/STUDY/weizhcode-python/tests/test_tool_registry.py)、[tests/test_file_tools.py](D:/STUDY/weizhcode-python/tests/test_file_tools.py)、[tests/test_search_tools.py](D:/STUDY/weizhcode-python/tests/test_search_tools.py)、[tests/test_command_tool.py](D:/STUDY/weizhcode-python/tests/test_command_tool.py)、[tests/test_tool_executor.py](D:/STUDY/weizhcode-python/tests/test_tool_executor.py)、[tests/test_turn_runner.py](D:/STUDY/weizhcode-python/tests/test_turn_runner.py)、[tests/test_redaction.py](D:/STUDY/weizhcode-python/tests/test_redaction.py)

**依赖：** T35、T53、T54、T56

**步骤：**

1. 运行全部自动测试与编译检查，记录通过、失败、跳过数量和实际平台。
2. 任何失败先修复对应实现和回归用例再重跑；不通过缩减断言、静默跳过或放宽单工具/审批约束来变绿。
3. 确认依赖只包含已批准的变更，Ruff/mypy 未配置则不声明其通过。

**验证：** 运行 uv run python -m pytest -v 与 uv run python -m compileall src tests；保存实际输出，确认无失败并逐项说明平台 skip。

**覆盖：** N7、N8、AC12、AC13。

### T58: PowerShell 验证启动与读取总结

**文件：** 无实现改动；使用受控临时目录，证据归入验收记录。

**依赖：** T57

**步骤：**

1. 在 Windows PowerShell 真实终端用 uv run weizhcode 启动，观察版本、模型、路径、6 tools 和输入框。
2. 在专用临时目录准备无敏感内容的测试文件，提交读取并一句话总结；观察流式文字、工具行、实际结果体现与下一轮追问。
3. 记录截图/观察和所用后端；没有可用凭证时记录未执行及原因，不能用无界面测试冒充本任务通过。

**验证：** 在真实 PowerShell 中观察一次完整读取闭环和追问；答复引用测试文件实际信息，记录正文增量、工具前后顺序与上下文。

**覆盖：** F2、F11、F15、F16、AC2、AC8、AC11。

### T59: PowerShell 验证写入审批

**文件：** 无实现改动；使用受控临时目录，证据归入验收记录。

**依赖：** T58

**步骤：**

1. 让模型在专用临时目录创建嵌套文本文件，等待审批时从另一个只读检查入口确认文件和父目录未创建。
2. 先拒绝一次，确认无写入且模型解释拒绝；另起一轮批准，检查落地内容和审批记录。
3. 不在真实项目源码或用户配置上做覆盖实验；记录操作路径、批准/拒绝和结果，不记录密钥。

**验证：** 真实终端可见预览、两按钮及结果；拒绝前后磁盘不变，批准后嵌套文件内容正确，会话继续可用。

**覆盖：** F3、F12、AC3、AC10。

### T60: PowerShell 验证精确修改

**文件：** 无实现改动；使用受控临时目录，证据归入验收记录。

**依赖：** T59

**步骤：**

1. 使用已创建的临时文件，提交一次唯一匹配修改，核对预览后批准，并检查实际内容与换行/BOM。
2. 再提交不存在片段的修改，确认明确错误且文件不变；另起一轮正常对话确认恢复。
3. 需要验证审批期间外部变化时，仅修改临时文件，确认旧预览被拒绝而不是覆盖新内容。

**验证：** 真实终端的唯一替换成功，匹配不到或预览失效时给出不同原因，测试文件字节符合对应操作。

**覆盖：** F4、F12、AC4、AC10、AC13。

### T61: PowerShell 验证命令审批与超时

**文件：** 无实现改动；使用受控临时目录，证据归入验收记录。

**依赖：** T58

**步骤：**

1. 使用只输出受控文本的 PowerShell 命令，确认完整命令和 cwd 可见；分别拒绝和在新一轮批准。
2. 执行受控非零退出与超时命令，期间观察界面可响应；验证错误结果和本轮收尾，不触及真实服务。
3. 不得将写文件和执行命令合并为同轮两工具成功场景；若模型提出多个工具，应观察全部拒绝。

**验证：** 真实终端确认批准/拒绝语义、输出和退出码、30 秒超时提示及后续会话可用；进程树强断言复用自动测试实际证据。

**覆盖：** F5、F12、N1、N2、AC5、AC9、AC10、AC11。

### T62: PowerShell 验证滚动与退出清理

**文件：** 无实现改动；使用受控临时目录，证据归入验收记录。

**依赖：** T58、T59、T60、T61

**步骤：**

1. 利用前述场景的工具行和回复，回滚检查前导文字、工具、摘要、最终答复的顺序与截断提示。
2. 在等待审批以及受控工具运行时分别退出整个程序，确认终端恢复、审批失效、受管进程结束。
3. 将终端内可滚动记录与退出后的外部终端状态分别记录；本阶段不安装 tmux/WSL，不把二者混为一个验收结论。

**验证：** 保存经过密钥检查的真实终端证据，确认界面不冻结、记录可回看、退出无晚到副作用；该任务依据用户允许替代 tmux 的决定执行。

**覆盖：** F15、N1、N2、AC11、AC13。

### T63: 记录 Anthropic 真实 API 验证

**文件：** 无实现改动；使用受控临时目录，证据归入验收记录。

**依赖：** T57

**步骤：**

1. 检查是否已有用户提供的有效 Anthropic 凭证、支持工具的模型及可用端点，不输出密钥，不擅自改写原配置。
2. 具备条件时，用临时非敏感文件执行读取总结及一个受控错误，记录实际工具配对、最终文字和恢复。
3. 缺凭证或需要额外配置授权时明确记录未执行并询问；不靠模拟测试或参考文档中的已实测声明代替。

**验证：** 记录 Anthropic Messages 的真实场景、模型/协议和成功或失败原因；如与前述终端验证使用同一后端，可复用同一证据，避免重复调用。

**覆盖：** F14、N5、N8、AC12。

### T64: 记录 OpenAI Responses 真实 API 验证

**文件：** 无实现改动；使用受控临时目录，证据归入验收记录。

**依赖：** T57

**步骤：**

1. 检查已有有效 OpenAI 凭证与 Responses 工具能力，保持原协议，不用 Chat Completions 测试代替。
2. 具备条件时，在不改写用户原配置的前提下验证读取总结和受控错误；检查 store=False 的结果回灌及续答。
3. 记录实际执行、失败或未执行原因；需要新凭证、模型更换或配置改动时先询问，不自行扩大范围。

**验证：** 记录 OpenAI Responses 的实际请求类型和工具闭环结果；缺少条件时保留未执行状态，不能打勾为真实 API 通过。

**覆盖：** F14、N5、N8、AC12。

### T65: 记录千问真实 API 验证

**文件：** 无实现改动；使用受控临时目录，证据归入验收记录。

**依赖：** T57

**步骤：**

1. 检查已有有效千问凭证与兼容端点，使用用户既定模型，不擅自替换模型或修改原配置。
2. 具备条件时验证读取总结、受控错误与最终禁用工具；观察兼容端点对流式工具调用和历史的实际支持。
3. 可复用 T58～T62 已取得的千问证据，避免重复付费请求；未具备条件的场景明确记录未执行。

**验证：** 记录千问 Chat Completions 真实配对、模型答复及错误恢复；成功、失败和未执行分别列示。

**覆盖：** F14、N5、N8、AC12。

### T66: 汇总验收证据与交付状态

**文件：** [specs/tool-system/task.md](D:/STUDY/weizhcode-python/specs/tool-system/task.md)、[specs/tool-system/checklist.md](D:/STUDY/weizhcode-python/specs/tool-system/checklist.md)

**依赖：** T57、T58、T59、T60、T61、T62、T63、T64、T65

**步骤：**

1. 在四份文档全部批准且进入验收后，按 checklist 逐项写入实际证据，区分自动、真实终端、真实 API 和未执行平台。
2. 仅将真正完成且验证通过的任务与检查项标记通过；缺凭证/平台、失败或未观察的场景保留明确状态，不因其他组通过而补勾。
3. 汇总改动文件、测试结果、剩余限制和待用户配合事项；分组验证后按工作流进行本地提交，不自动推送 GitHub。

**验证：** 检查每条验收结论均有运行输出或真实观察，需求覆盖完整；最终报告不包含密钥，也不把未执行项描述为已通过。

**覆盖：** N8、AC1、AC2、AC3、AC4、AC5、AC6、AC7、AC8、AC9、AC10、AC11、AC12、AC13。

## 执行顺序与提交边界

按 T1 至 T66 的编号顺序执行即可满足全部显式依赖；不需要并行开发或额外代理。跨文件接线在同一任务内完成并运行回归，避免入口和构造签名不一致。

- T1～T9：先建立基线、依赖、数据和校验/脱敏边界。
- T10～T26：先文件与搜索辅助，再形成六个真实工具的固定注册表。
- T27～T35：先实现平台进程控制和 worker，再接入执行器、审批与共享预算，最后验证真实后代终止。
- T36～T44：历史契约先于协议回灌；每个后端先请求编码、后流式组装。
- T45～T48：纯文字、一工具、上限、错误恢复依次接入。
- T49～T56：工具视图、审批、入口接线、安全与跨协议集成依次验证。
- T57～T66：先自动回归，再做受控真实终端与线上验证，最后按 checklist 汇总证据。

分组本地提交以前提验证确实通过为准；条件性真实 API 任务只能在实际运行后标为通过，缺条件时保留未执行与具体原因。T66 可以汇总不完整验收状态，但不得因此将未执行项目改成通过。

## 需求与验收覆盖

| 需求/验收 | 对应任务 |
|-----------|----------|
| F1 | T2、T3、T9、T26、T53 |
| F2 | T10、T11、T32、T58 |
| F3 | T12、T13、T14、T15、T59 |
| F4 | T12、T13、T16、T17、T18、T60 |
| F5 | T24、T25、T35、T61 |
| F6 | T21、T32 |
| F7 | T22、T23、T32 |
| F8 | T19、T20、T21、T22 |
| F9 | T37、T38、T40、T42、T44、T45 |
| F10 | T5、T31、T39、T41、T43、T48 |
| F11 | T45、T46、T47、T51、T58 |
| F12 | T4、T12、T14、T17、T24、T26、T29、T33、T46、T50、T54、T59、T60、T61 |
| F13 | T3、T4、T6、T9、T13、T23、T25、T28、T29、T30、T31、T32、T34、T46、T48、T52 |
| F14 | T37、T38、T39、T40、T41、T42、T43、T53、T56、T63、T64、T65 |
| F15 | T5、T49、T51、T52、T58、T62 |
| F16 | T5、T36、T38、T40、T42、T46、T48、T58 |
| N1 | T27、T28、T30、T34、T35、T54、T61、T62 |
| N2 | T50、T51、T54、T61、T62 |
| N3 | T6、T11、T21、T23、T25、T35、T49、T55 |
| N4 | T10、T15、T18 |
| N5 | T56、T63、T64、T65 |
| N6 | T7、T8、T52、T55 |
| N7 | T1、T2、T37、T45、T53、T57 |
| N8 | T1、T56、T57、T63、T64、T65、T66 |
| AC1 | T3、T9、T26、T37、T38、T40、T42、T44、T45、T53、T66 |
| AC2 | T10、T11、T32、T58、T66 |
| AC3 | T4、T12、T13、T14、T15、T29、T33、T50、T59、T66 |
| AC4 | T12、T13、T16、T17、T18、T33、T60、T66 |
| AC5 | T24、T25、T27、T28、T30、T33、T34、T35、T54、T61、T66 |
| AC6 | T19、T20、T21、T22、T23、T32、T66 |
| AC7 | T5、T9、T31、T39、T41、T43、T48、T66 |
| AC8 | T5、T36、T38、T40、T42、T46、T48、T51、T56、T58、T66 |
| AC9 | T47、T51、T56、T61、T66 |
| AC10 | T3、T4、T23、T25、T28、T29、T30、T31、T32、T33、T34、T46、T48、T50、T52、T56、T59、T60、T61、T66 |
| AC11 | T6、T11、T21、T23、T25、T35、T49、T50、T51、T52、T54、T55、T58、T61、T62、T66 |
| AC12 | T38、T39、T40、T41、T42、T43、T56、T57、T63、T64、T65、T66 |
| AC13 | T1、T7、T8、T10、T15、T18、T37、T45、T52、T53、T54、T55、T57、T60、T62、T66 |

## 文档自检与审批

- 每项具备具体文件或明确的只读/受控验收范围、显式依赖、步骤和验证方式。
- 编号依赖只指向已列出的前序任务，按编号执行无循环。
- 覆盖 Plan 的全部文件、Spec 的 F1～F16、N1～N8 与 AC1～AC13。
- 本次仅生成 task 并记录 Plan 已获批准，不提前修改实现、安装依赖、运行本任务清单或生成 checklist。
- 用户批准 task 后进入 checklist 验收设计；checklist 也获批准后才开始实施。

