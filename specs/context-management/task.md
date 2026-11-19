# weizhCode 上下文管理 Tasks

> 状态：开发与本机离线验证已完成，待用户审核。Windows控制台PTY已观察；POSIX、部分原生符号链接及收费模型验证单列，不宣称全面跨平台/真实服务验收。
> 日期：2026-11-18 创建、获批并实施。实际证据见第10节；第7–9节为此前批次的历史记录。
> 依据：[spec.md](D:/STUDY/weizhcode-python/specs/context-management/spec.md)、[plan.md](D:/STUDY/weizhcode-python/specs/context-management/plan.md)。
> 任务中的命令是验证入口；只有第10节及Checklist记录的实际输出才是执行证据。四处测试入口按实际集成用例位置补充，需求/生产范围不变。

## 1. 执行约束

- 四份文档全部批准后才能实施；本次批准 Task 后只生成 Checklist，再等审批。若发现必须改变已批准需求或技术决策，先说明差异并重新确认。
- 使用项目既有 Python 3.11+ 环境；以下命令工作目录均为 D:/STUDY/weizhcode-python/。不新增 SDK、tokenizer、数据库或命令框架，不临时安装 Ruff/mypy 来宣称已有检查通过。
- 只允许下列48个生产文件范围；实现中发现范围外生产改动先说明原因。测试可在本清单所列文件内扩展；不借此重构整个权限、MCP、Provider系统。
- 不读取/修改用户的真实 weizhcode.yaml、.weizhcode/mcp.yaml、权限/信任文件、密钥、.weizhcode-test/、hello.txt，不清理或覆盖用户既有改动；测试仅用自有临时project/home及假配置。
- 每项先实现其测试用例，再完成代码并运行验证；相同文件后续任务继续增补而非覆盖先前实现。每步保持既有测试可运行；工作量超出一个聚焦单元时再拆分子步骤，不能跳过验证。
- 常规任务在所列测试文件中新增以 `test_ctx_tNN_` 开头的用例（NN为两位任务号），对应命令 `-k ctx_tNN`。必须实际收集到该任务用例且全部通过；0收集、选择器未命中、仅跳过不能算通过。测试文件/用例目前尚未创建。
- 所有自动验证离线；真实工具仅在临时目录，MCP只用已有本地/回环夹具。不得接触真实Server、真实模型或凭据。真实模型收费验证单独授权，不能用fake结果冒充。
- 每任务完成记录命令、用例数、结果和必要行为证据；未通过不得标完成。平台跳过、真实终端和真实模型未验分开记录。
- 原权限门禁、PLAN边界、并发上限4、副作用屏障、提问/批准、普通流式、原生协议配对均为回归约束，不以BYPASS默认化或删除断言换绿。
- 资料落盘与历史替换不是同一个事务：已提交资料可能保留，取消/失败不得虚称完整回滚；不递归清理不属于本操作的对象。不自动提交或推送Git。

## 2. 文件清单

### 2.1 生产文件（18新增、30修改）

P编号唯一对应下列完整路径；各任务“文件”引用这些编号，即引用其具体文件及受限职责。

| 编号 | 操作 | 完整路径 | 职责/受限改动 |
|---|---|---|---|
| P01 | 新建 | D:/STUDY/weizhcode-python/src/weizhcode/compact/__init__.py | 轻量公共导出，不做I/O |
| P02 | 新建 | D:/STUDY/weizhcode-python/src/weizhcode/compact/contracts.py | 身份、来源、引用、结果、请求帧等只读契约 |
| P03 | 新建 | D:/STUDY/weizhcode-python/src/weizhcode/compact/limits.py | Spec常量与内部处理预算 |
| P04 | 新建 | D:/STUDY/weizhcode-python/src/weizhcode/compact/state.py | SessionRuntime、账本、快照与自动计数 |
| P05 | 新建 | D:/STUDY/weizhcode-python/src/weizhcode/compact/capture.py | 可信内部CaptureSink/Hub与worker捕获上下文 |
| P06 | 新建 | D:/STUDY/weizhcode-python/src/weizhcode/compact/archive.py | SessionStore、固定进程、提交状态及引用登记 |
| P07 | 新建 | D:/STUDY/weizhcode-python/src/weizhcode/compact/archive_worker.py | 固定归档白名单与有界IPC，不执行模型工具 |
| P08 | 新建 | D:/STUDY/weizhcode-python/src/weizhcode/compact/archive_fs.py | 根/重定向/身份校验、独占保存、核验及索引事务 |
| P09 | 新建 | D:/STUDY/weizhcode-python/src/weizhcode/compact/history.py | 原子历史候选、用户/工具分组、近期边界 |
| P10 | 新建 | D:/STUDY/weizhcode-python/src/weizhcode/compact/estimator.py | 实际协议投影、usage锚点与失效规则 |
| P11 | 新建 | D:/STUDY/weizhcode-python/src/weizhcode/compact/layer1.py | 单项/聚合归档和稳定预览 |
| P12 | 新建 | D:/STUDY/weizhcode-python/src/weizhcode/compact/summary.py | 独立摘要收集、解析、有界长度退让 |
| P13 | 新建 | D:/STUDY/weizhcode-python/src/weizhcode/compact/prompts.py | 摘要九部分与固定边界文本 |
| P14 | 新建 | D:/STUDY/weizhcode-python/src/weizhcode/compact/recovery.py | 单轮文件/工具/边界恢复及预算精简 |
| P15 | 新建 | D:/STUDY/weizhcode-python/src/weizhcode/compact/manager.py | 正常/手动/紧急编排、预算、CAS提交 |
| P16 | 新建 | D:/STUDY/weizhcode-python/src/weizhcode/compact/factory.py | 生产Runtime装配，接收已选窗口/真实根 |
| P17 | 新建 | D:/STUDY/weizhcode-python/src/weizhcode/providers/request.py | RequestOptions/PreparedRequest纯准备通用契约 |
| P18 | 新建 | D:/STUDY/weizhcode-python/src/weizhcode/commands.py | 空闲命令注册与分派，不引入命令框架 |
| P19 | 修改 | D:/STUDY/weizhcode-python/src/weizhcode/models.py | 末尾追加可选事件/状态字段，内部slot关联捕获；不将捕获混入模型结果序列化 |
| P20 | 修改 | D:/STUDY/weizhcode-python/src/weizhcode/conversation.py | entries/revision、快照与条件替换；旧公开消息语义保持 |
| P21 | 修改 | D:/STUDY/weizhcode-python/src/weizhcode/config.py | context_window读取/严格校验/应用默认，不增加其他配置 |
| P22 | 修改 | D:/STUDY/weizhcode-python/src/weizhcode/errors.py | 安全结构化ProviderFault/请求错误，兼容旧错误基类 |
| P23 | 修改 | D:/STUDY/weizhcode-python/src/weizhcode/providers/base.py | 新准备/发送协议与旧接口包装，原usage归一化不改口径 |
| P24 | 修改 | D:/STUDY/weizhcode-python/src/weizhcode/providers/anthropic.py | 纯prepare、摘要目的、长度/结束分类；保留原生块 |
| P25 | 修改 | D:/STUDY/weizhcode-python/src/weizhcode/providers/openai.py | 纯prepare、禁自动truncation、长度/结束分类；保留原生items |
| P26 | 修改 | D:/STUDY/weizhcode-python/src/weizhcode/providers/qwen.py | 纯prepare、摘要目的、严格长度/结束分类 |
| P27 | 修改 | D:/STUDY/weizhcode-python/src/weizhcode/providers/sse.py | 有界错误正文与结构化错误，不记录认证信息 |
| P28 | 修改 | D:/STUDY/weizhcode-python/src/weizhcode/providers/prompt_adapter.py | 动态恢复/摘要目的适配，稳定缓存分段保持 |
| P29 | 修改 | D:/STUDY/weizhcode-python/src/weizhcode/prompting/contracts.py | 新应用来源恢复补充的白名单，保持来源校验 |
| P30 | 修改 | D:/STUDY/weizhcode-python/src/weizhcode/prompting/builder.py | 接纳应用恢复补充，不拼入稳定七模块 |
| P31 | 修改 | D:/STUDY/weizhcode-python/src/weizhcode/stream_collector.py | 使用同一PreparedRequest、保留fault/结束事实；普通正文流保持 |
| P32 | 修改 | D:/STUDY/weizhcode-python/src/weizhcode/turn_runner.py | 会话状态、前置管理、一次紧急重试、手动事件通道与结算 |
| P33 | 修改 | D:/STUDY/weizhcode-python/src/weizhcode/user_questions.py | 可信已接纳答案来源，禁止摘要产生伪答案/授权 |
| P34 | 修改 | D:/STUDY/weizhcode-python/src/weizhcode/tools/base.py | ExternalTool新增可选capture_sink，不改内置Schema |
| P35 | 修改 | D:/STUDY/weizhcode-python/src/weizhcode/tools/read_file.py | 同次获准读取的纯净快照、已登记归档核验 |
| P36 | 修改 | D:/STUDY/weizhcode-python/src/weizhcode/tools/worker.py | 有界捕获帧、归档读取proof及合法操作绑定 |
| P37 | 修改 | D:/STUDY/weizhcode-python/src/weizhcode/tools/process.py | 接收/核验内部捕获，不提高原IPC与结果预算 |
| P38 | 修改 | D:/STUDY/weizhcode-python/src/weizhcode/tools/executor.py | 原门禁后接入sink，保存原结果与内部来源 |
| P39 | 修改 | D:/STUDY/weizhcode-python/src/weizhcode/tool_scheduler.py | 传递本批捕获上下文、来源接纳/配对；预留由Executor在原门禁之后申请，原并发4与屏障保持 |
| P40 | 修改 | D:/STUDY/weizhcode-python/src/weizhcode/mcp/host_worker.py | 实际调用后、最终截断前发捕获帧，不扩展Server能力 |
| P41 | 修改 | D:/STUDY/weizhcode-python/src/weizhcode/mcp/manager.py | 私有捕获帧绑定当前调用，原失效/取消/不重放保持 |
| P42 | 修改 | D:/STUDY/weizhcode-python/src/weizhcode/mcp/tool.py | 捕获原投影后保持旧结果上限与文本/非文本语义 |
| P43 | 修改 | D:/STUDY/weizhcode-python/src/weizhcode/mcp/process.py | 仅扩充受管进程的私有帧白名单，保持所有权/有限关闭；各用途独立校验 |
| P44 | 修改 | D:/STUDY/weizhcode-python/src/weizhcode/cli.py | 普通/MCP两装配分支统一注入生产Runtime |
| P45 | 修改 | D:/STUDY/weizhcode-python/src/weizhcode/tui.py | 手动命令、phase显示、草稿/焦点/取消及后备构造 |
| P46 | 修改 | D:/STUDY/weizhcode-python/weizhcode.yaml.example | 可选context_window示例；不改真实weizhcode.yaml |
| P47 | 修改 | D:/STUDY/weizhcode-python/.gitignore | 仅追加本系统sessions资料路径 |
| P48 | 修改 | D:/STUDY/weizhcode-python/README.md | 新命令、费用、窗口默认、归档隐私与实际边界 |

### 2.2 测试文件

下表只声明将要新建或扩展的测试；原tests全套在T67回归，不以这个局部列表替代旧能力验证。

| 操作 | 完整路径 |
|---|---|
| 新建 | D:/STUDY/weizhcode-python/tests/compact/conftest.py |
| 新建 | D:/STUDY/weizhcode-python/tests/compact/test_archive.py |
| 新建 | D:/STUDY/weizhcode-python/tests/compact/test_archive_process.py |
| 新建 | D:/STUDY/weizhcode-python/tests/compact/test_capture.py |
| 新建 | D:/STUDY/weizhcode-python/tests/compact/test_estimator.py |
| 新建 | D:/STUDY/weizhcode-python/tests/compact/test_history.py |
| 新建 | D:/STUDY/weizhcode-python/tests/compact/test_layer1.py |
| 新建 | D:/STUDY/weizhcode-python/tests/compact/test_manager.py |
| 新建 | D:/STUDY/weizhcode-python/tests/compact/test_recovery.py |
| 新建 | D:/STUDY/weizhcode-python/tests/compact/test_state.py |
| 新建 | D:/STUDY/weizhcode-python/tests/compact/test_summary.py |
| 新建 | D:/STUDY/weizhcode-python/tests/manual_context_smoke.py |
| 扩展 | D:/STUDY/weizhcode-python/tests/test_cache_usage.py |
| 扩展 | D:/STUDY/weizhcode-python/tests/test_cli.py |
| 扩展 | D:/STUDY/weizhcode-python/tests/test_config.py |
| 新建 | D:/STUDY/weizhcode-python/tests/test_context_integration.py |
| 新建 | D:/STUDY/weizhcode-python/tests/test_context_protocols.py |
| 新建 | D:/STUDY/weizhcode-python/tests/test_context_tui.py |
| 扩展 | D:/STUDY/weizhcode-python/tests/test_conversation.py |
| 扩展 | D:/STUDY/weizhcode-python/tests/test_mcp_bootstrap.py |
| 扩展 | D:/STUDY/weizhcode-python/tests/test_mcp_tool.py |
| 扩展 | D:/STUDY/weizhcode-python/tests/test_protocol_integration.py |
| 扩展 | D:/STUDY/weizhcode-python/tests/test_provider_events.py |
| 扩展 | D:/STUDY/weizhcode-python/tests/test_tool_executor.py |
| 扩展 | D:/STUDY/weizhcode-python/tests/test_tool_scheduler.py |
| 扩展 | D:/STUDY/weizhcode-python/tests/test_tui.py |
| 扩展 | D:/STUDY/weizhcode-python/tests/test_turn_runner.py |
| 扩展 | D:/STUDY/weizhcode-python/tests/test_user_questions.py |

### 2.3 流程文档

- D:/STUDY/weizhcode-python/specs/context-management/task.md：实施阶段逐项记录状态与证据；当前所有任务待实施。
- D:/STUDY/weizhcode-python/specs/context-management/checklist.md：仅在本 Task 获批后的下一阶段生成；实施后按批准版本登记验收，不提前勾选。
- D:/STUDY/weizhcode-python/specs/context-management/plan.md：本轮仅更新审批元信息，不变更技术设计。

## 3. 有序任务

### T01：建立隔离测试基线

**状态：** 已实现并通过本项离线验证（证据见末尾）。  **依赖：** 无。  **覆盖：** AC29。

**文件：** D:/STUDY/weizhcode-python/tests/compact/conftest.py；D:/STUDY/weizhcode-python/tests/compact/test_state.py。

**步骤：**

1. 记录工作区既有改动及旧测试基线；建立临时project/home、固定时钟、fake模型/流、禁止外网与真实配置读取的夹具。
2. 为后续场景提供受控usage、错误、慢I/O、取消与真实本地工具样本；不执行用户文件中的命令。

**验证：** 无压缩时应用行为不变；隔离夹具不读取真实密钥、用户权限或MCP配置。

```text
python -m pytest -q
python -m pytest tests/compact/test_state.py -k ctx_t01 -q
```

### T02：定义内部只读契约

**状态：** 已实现并通过本项离线验证（证据见末尾）。  **依赖：** T01。  **覆盖：** AC01、AC28、AC29。

**文件：** P01；P02；P19；P22；D:/STUDY/weizhcode-python/tests/compact/test_state.py。

**步骤：**

1. 按Plan定义HistoryEntry/Snapshot、ArchiveRef、ToolSource、FileReadCapture、CompactOutcome、CompactionBudget及安全ProviderFault。
2. 事件末尾添加可选字段，敏感正文repr=False；内部捕获不进入ToolResult公开序列化；导入compact不创建目录或进程。

**验证：** 旧位置参数兼容；敏感正文不出现在repr/事件；公共包可无副作用导入。

```text
python -m pytest tests/compact/test_state.py -k ctx_t02 -q
```

### T03：集中固定预算与窗口配置

**状态：** 已实现并通过本项离线验证（证据见末尾）。  **依赖：** T02。  **覆盖：** AC25。

**文件：** P03；P21；D:/STUDY/weizhcode-python/tests/test_config.py；D:/STUDY/weizhcode-python/tests/compact/test_state.py。

**步骤：**

1. 集中Plan列明的字节、token、捕获、归档、请求及时间预算，不将字节与字符混用。
2. ProviderConfig末尾追加context_window=0；仅接受非布尔整数0或>33000，按协议应用200000/128000/128000默认，不把默认宣称为模型能力。

**验证：** 缺省/0/33001正确；33000、负数、布尔、字符串拒绝；窗口不进入API请求字段。

```text
python -m pytest tests/test_config.py tests/compact/test_state.py -k ctx_t03 -q
```

### T04：建立会话长状态与操作代次

**状态：** 已实现并通过本项离线验证（证据见末尾）。  **依赖：** T02、T03。  **覆盖：** AC01、AC06、AC23、AC27。

**文件：** P04；D:/STUDY/weizhcode-python/tests/compact/test_state.py。

**步骤：**

1. 建立SessionRuntime、来源/替换账本、human索引、文件读取缓存、usage锚点与auto_failures；持有真实root身份。
2. 提供事件循环内快照及受锁接纳，操作generation抵御迟到回包；会话跨用户任务保持、重启不恢复。

**验证：** 多轮状态不重置；两会话身份不同；冻结快照不可被调用者改写；迟到操作不能修改新一代。

```text
python -m pytest tests/compact/test_state.py -k ctx_t04 -q
```

### T05：为Conversation增加来源与条件替换

**状态：** 已实现并通过本项离线验证（证据见末尾）。  **依赖：** T02、T04。  **覆盖：** AC02、AC13、AC27、AC29。

**文件：** P20；P09；D:/STUDY/weizhcode-python/tests/test_conversation.py；D:/STUDY/weizhcode-python/tests/compact/test_history.py。

**步骤：**

1. 保持既有公开消息与深拷贝语义，追加稳定entry_id、turn_id、origin和revision。
2. 实现snapshot/replace_if_current及完整工具配对校验，失败不清空旧历史，不允许以None表示清空。

**验证：** 旧Conversation测试通过；旧revision拒绝；工具调用/结果不可被拆散；失败前后快照一致。

```text
python -m pytest tests/test_conversation.py tests/compact/test_history.py -k ctx_t05 -q
```

### T06：接纳真实用户回答与应用来源

**状态：** 已实现并通过本项离线验证（证据见末尾）。  **依赖：** T05。  **覆盖：** AC02、AC18、AC28。

**文件：** P33；P04；D:/STUDY/weizhcode-python/tests/test_user_questions.py；D:/STUDY/weizhcode-python/tests/compact/test_state.py。

**步骤：**

1. 普通输入和已接纳AskUserQuestion答案记录可信human来源/顺序；应用/do补充与摘要不因role=user冒充原话。
2. 取消、未提交草稿、模型伪造答案或提示标签不得产生用户归档记录或授权。

**验证：** 重复回包只接纳一次；原用户回答原文保留；应用补充、模型内容与真实human可明确区分。

```text
python -m pytest tests/test_user_questions.py tests/compact/test_state.py -k ctx_t06 -q
```

### T07：定义纯请求准备契约

**状态：** 已实现并通过本项离线验证（证据见末尾）。  **依赖：** T02、T03。  **覆盖：** AC08、AC09、AC29。

**文件：** P17；P23；D:/STUDY/weizhcode-python/tests/test_context_protocols.py。

**步骤：**

1. 实现RequestOptions、不可变PreparedRequest及实际body/message/fixed投影、digest、request_id、purpose与输出预留。
2. Provider新增prepare_request/stream_prepared，保留stream_chat包装与既有stream_func注入；准备不得联网或改变Conversation。

**验证：** 准备两次不修改输入；估算投影与实际发送同源；序列化不含认证头/内部来源。

```text
python -m pytest tests/test_context_protocols.py -k ctx_t07 -q
```

### T08：接入Anthropic请求准备

**状态：** 已实现并通过本项离线验证（证据见末尾）。  **依赖：** T07。  **覆盖：** AC04、AC11、AC13、AC15、AC29。

**文件：** P24；P28；D:/STUDY/weizhcode-python/tests/test_context_protocols.py；D:/STUDY/weizhcode-python/tests/test_protocol_integration.py。

**步骤：**

1. 从现有构造流程提取纯prepare，保留稳定缓存分段、thinking签名、tool_use/tool_result与原生内容。
2. 摘要purpose不沿用Agent工具指令，tools为空且禁止调用；发送直接使用准备后的body，不临时追加不同补充。

**验证：** 抓取出站body与PreparedRequest一致；普通原生块不改写；摘要0工具且不污染稳定缓存。

```text
python -m pytest tests/test_context_protocols.py tests/test_protocol_integration.py -k ctx_t08 -q
```

### T09：接入OpenAI Responses请求准备

**状态：** 已实现并通过本项离线验证（证据见末尾）。  **依赖：** T07。  **覆盖：** AC04、AC11、AC13、AC15、AC29。

**文件：** P25；P28；D:/STUDY/weizhcode-python/tests/test_context_protocols.py；D:/STUDY/weizhcode-python/tests/test_protocol_integration.py。

**步骤：**

1. 提取Responses纯prepare/发送，保留原有原生items及需重放的opaque数据。
2. 显式禁自动输入截断并保持store=False；摘要空工具，不切换其他API、不因兼容端点拒绝安全字段而静默降级重试。

**验证：** 实际body包含既定安全设置；普通items保持；摘要不发送工具；无自动吞历史行为。

```text
python -m pytest tests/test_context_protocols.py tests/test_protocol_integration.py -k ctx_t09 -q
```

### T10：接入Qwen兼容请求准备

**状态：** 已实现并通过本项离线验证（证据见末尾）。  **依赖：** T07。  **覆盖：** AC04、AC11、AC13、AC15、AC29。

**文件：** P26；P28；D:/STUDY/weizhcode-python/tests/test_context_protocols.py；D:/STUDY/weizhcode-python/tests/test_protocol_integration.py。

**步骤：**

1. 提取兼容Chat纯prepare/发送，保留tool_calls及结果、提示与cache usage口径。
2. 摘要purpose空工具，普通/摘要共用实际出站投影但保持各自指令边界。

**验证：** 普通工具配对与既有接口兼容；摘要body无可调用工具；同一准备对象发送一致。

```text
python -m pytest tests/test_context_protocols.py tests/test_protocol_integration.py -k ctx_t10 -q
```

### T11：让普通流收集器使用已准备请求

**状态：** 已实现并通过本项离线验证（证据见末尾）。  **依赖：** T08、T09、T10。  **覆盖：** AC19、AC20、AC29。

**文件：** P31；P19；D:/STUDY/weizhcode-python/tests/test_provider_events.py；D:/STUDY/weizhcode-python/tests/test_context_protocols.py。

**步骤：**

1. StreamCollector使用同一PreparedRequest，实时文本/工具收集双路保持，状态保留fault与finish_reason。
2. 保留旧注入接口的适配；失败流不提交不完整assistant，不把未确认工具请求送去执行。

**验证：** 流式正文仍实时到UI；完整响应供判断；错误和结束事实未被压成一段丢失分类的文字。

```text
python -m pytest tests/test_provider_events.py tests/test_context_protocols.py -k ctx_t11 -q
```

### T12：有界读取HTTP错误与安全分类入口

**状态：** 已实现并通过本项离线验证（证据见末尾）。  **依赖：** T02、T11。  **覆盖：** AC20、AC28。

**文件：** P22；P27；P23；D:/STUDY/weizhcode-python/tests/test_provider_events.py；D:/STUDY/weizhcode-python/tests/test_context_protocols.py。

**步骤：**

1. 错误正文读取限64KiB，解析已认可结构化error后仅输出安全字段；超量/畸形按普通错误。
2. 先排除认证、权限、限流、5xx和传输异常；禁止把响应全文或认证头塞入fault/日志。

**验证：** 401/403/429/500、坏JSON、恶意关键字正文均不触发紧急压缩；错误正文不泄漏已知密钥。

```text
python -m pytest tests/test_provider_events.py tests/test_context_protocols.py -k ctx_t12 -q
```

### T13：分类Anthropic长度与结束状态

**状态：** 已实现并通过本项离线验证（证据见末尾）。  **依赖：** T12。  **覆盖：** AC19、AC20。

**文件：** P24；D:/STUDY/weizhcode-python/tests/test_context_protocols.py。

**步骤：**

1. 仅认可Plan定义的HTTP400/流内invalid_request_error严格prompt-too-long信号及明确model_context_window_exceeded。
2. 区分正常完整、输出截断、refusal、pause_turn和泛参数错误；摘要拒绝非合法完整结束。

**验证：** HTTP/流两路正例触发长度分类；输出max_tokens、泛invalid_request_error等反例不触发。

```text
python -m pytest tests/test_context_protocols.py -k ctx_t13 -q
```

### T14：分类Responses长度与结束状态

**状态：** 已实现并通过本项离线验证（证据见末尾）。  **依赖：** T12。  **覆盖：** AC19、AC20。

**文件：** P25；D:/STUDY/weizhcode-python/tests/test_context_protocols.py。

**步骤：**

1. 仅明确context_length_exceeded分类为输入长度；保留completed/incomplete/failed及原因。
2. max_output_tokens/content_filter/invalid_prompt不当作输入长度；摘要仅完整completed可进入解析提交。

**验证：** HTTP/流内明确代码正确；恶意普通正文与输出限制无紧急重试；不完整摘要不成功。

```text
python -m pytest tests/test_context_protocols.py -k ctx_t14 -q
```

### T15：分类Qwen长度与结束状态

**状态：** 已实现并通过本项离线验证（证据见末尾）。  **依赖：** T12。  **覆盖：** AC19、AC20。

**文件：** P26；D:/STUDY/weizhcode-python/tests/test_context_protocols.py。

**步骤：**

1. 明确context_length_exceeded或受认可HTTP400参数类型+严格输入长度格式才触发。
2. finish_reason=length、max_tokens范围、激活/额度/内容类型错误不触发；正常终止与截断分开。

**验证：** 正反例参数化通过；未知兼容错误保留unknown而非模糊匹配long/length。

```text
python -m pytest tests/test_context_protocols.py -k ctx_t15 -q
```

### T16：建立请求级用量结算

**状态：** 已实现并通过本项离线验证（证据见末尾）。  **依赖：** T11、T13、T14、T15。  **覆盖：** AC08、AC24。

**文件：** P23；P31；P19；D:/STUDY/weizhcode-python/tests/test_cache_usage.py；D:/STUDY/weizhcode-python/tests/test_context_protocols.py。

**步骤：**

1. 请求区分request_id/purpose并按累计usage快照只settle一次，失败/取消接纳已报告部分。
2. 归一化input已含缓存，锚点/会话总量不再加缓存子项；missing保持未知，摘要不更新主锚点。

**验证：** 三协议缓存口径一致；重复结束事件不重计；摘要成本计入会话且主锚点不被覆盖。

```text
python -m pytest tests/test_cache_usage.py tests/test_context_protocols.py -k ctx_t16 -q
```

### T17：实现归档根与路径身份检查

**状态：** 已实现；本机22 passed、2 skipped，POSIX/符号链接未验项见末尾。  **依赖：** T02、T03。  **覆盖：** AC01、AC07、AC27、AC28。

**文件：** P08；D:/STUDY/weizhcode-python/tests/compact/test_archive.py。

**步骤：**

1. 仅使用实际项目根与应用生成32位安全hex会话/记录身份；不可用根或随机源失败时受控不可用。
2. 实现POSIX无跟随/dirfd与Windows reparse/句柄身份校验，拒绝链接替换、越界和不支持安全语义的存储。

**验证：** 恶意call_id不进入路径；链接/重定向与TOCTOU测试按原生平台验证；失败不使用预测ID或其他目录兜底。

```text
python -m pytest tests/compact/test_archive.py -k ctx_t17 -q
```

### T18：保存不可覆盖的正文与记录

**状态：** 独占写入/无覆盖发布及完整记录编排已集成，通过本机离线验证；证据见第10节。  **依赖：** T17。  **覆盖：** AC03、AC06、AC07、AC28。

**文件：** P08；D:/STUDY/weizhcode-python/tests/compact/test_archive.py。

**步骤：**

1. 实现pending独占写、UTF-8正文、sha256、flush/fsync、根复核、不可覆盖发布及最后元数据。
2. 工具归档遵守2MiB捕获上限，用户正文8MiB，metadata64KiB；脱敏后正文hash为唯一核验依据。

**验证：** 逐字安全正文一致；冲突不覆盖；中途失败只返回事实，不能虚称完整保存或历史回滚。

```text
python -m pytest tests/compact/test_archive.py -k ctx_t18 -q
```

### T19：生成可分页视图与用户索引

**状态：** 已实现并通过对应离线测试；实际命令与证据见第10节。  **依赖：** T18。  **覆盖：** AC02、AC07、AC26。

**文件：** P08；P07；D:/STUDY/weizhcode-python/tests/compact/test_archive.py。

**步骤：**

1. views按每1024字符分段JSONL，保留换行/BOM数据；用户索引每页最多256条且256KiB。
2. 提供独立view hash与≤2048字符索引摘要，包含序号范围、路径和分页方式，不逐条展开全部旧用户。

**验证：** 长单行可经普通read_file分段取回；中文/BOM/换行复原一致；大量原话索引保持有界。

```text
python -m pytest tests/compact/test_archive.py -k ctx_t19 -q
```

### T20：检查资料Git忽略与存储前置条件

**状态：** 已实现并通过对应离线测试；实际命令与证据见第10节。  **依赖：** T17。  **覆盖：** AC03、AC28。

**文件：** P08；P47；D:/STUDY/weizhcode-python/tests/compact/test_archive.py。

**步骤：**

1. 本仓库.gitignore只追加sessions资料路径；写入前检查原文/视图/临时产物均未跟踪且已忽略。
2. 其他Git项目不自动改忽略配置；已跟踪或不忽略时停止资料保存、保留对话原文；非Git根按Plan允许。

**验证：** 模拟Git项目三种状态正确；不跟踪资料、不修改测试外仓库、不接触真实配置。

```text
python -m pytest tests/compact/test_archive.py -k ctx_t20 -q
```

### T21：实现固定归档进程协议

**状态：** 已实现并通过对应离线测试；实际命令与证据见第10节。  **依赖：** T18、T19、T20。  **覆盖：** AC27、AC28、AC29。

**文件：** P07；P08；P43；D:/STUDY/weizhcode-python/tests/compact/test_archive_process.py。

**步骤：**

1. archive_worker仅接纳save_record/verify_records/publish_index/inspect_commit固定动作，路径由应用安全身份推导。
2. 复用OwnedProcess所有权原语，仅扩私有帧白名单；按用途验证，不引入MCP管理器、网络、密钥、任意shell/工具执行。

**验证：** 非法动作/路径/代次/帧拒绝；归档进程不具备执行模型工具的入口；原MCP进程测试仍通过。

```text
python -m pytest tests/compact/test_archive_process.py -k ctx_t21 -q
```

### T22：封装SessionStore与登记引用

**状态：** 已实现并通过对应离线测试；实际命令与证据见第10节。  **依赖：** T21、T04。  **覆盖：** AC01、AC03、AC06、AC27。

**文件：** P06；P07；D:/STUDY/weizhcode-python/tests/compact/test_archive.py；D:/STUDY/weizhcode-python/tests/compact/test_archive_process.py。

**步骤：**

1. 实现save_text/verify_refs/publish_user_index/proof_for_registered_path/aclose，首次需要时才创建目录/进程。
2. StoreResult区分saved/known_failed/uncertain/conflict；登记引用前必须确认文件身份/hash与索引提交。

**验证：** 空会话不产生资料目录；跨任务复用同一store；仅已确认记录公开引用，故障不删除历史。

```text
python -m pytest tests/compact/test_archive.py tests/compact/test_archive_process.py -k ctx_t22 -q
```

### T23：约束资料I/O超时与不确定提交

**状态：** 已实现并通过对应离线测试；实际命令与证据见第10节。  **依赖：** T22。  **覆盖：** AC03、AC22、AC27、AC28。

**文件：** P06；P07；P08；D:/STUDY/weizhcode-python/tests/compact/test_archive_process.py。

**步骤：**

1. 每次I/O≤5秒且不超过操作剩余预算，预留最后2秒清理；取消/超时终止仅本应用拥有的进程。
2. inspect_commit按记录ID/hash核实迟到发布，不能仅凭exists认为成功；无法确认返回uncertain并阻止历史提交。

**验证：** 慢磁盘、挂起进程、取消及提交后丢回包均有界结束；不会无限等后台线程或杀用户进程。

```text
python -m pytest tests/compact/test_archive_process.py -k ctx_t23 -q
```

### T24：保证脱敏与拥有对象清理

**状态：** 已实现并通过对应离线测试；实际命令与证据见第10节。  **依赖：** T23。  **覆盖：** AC28。

**文件：** P06；P07；P08；D:/STUDY/weizhcode-python/tests/compact/test_archive.py；D:/STUDY/weizhcode-python/tests/compact/test_archive_process.py。

**步骤：**

1. 写盘前使用合并redactor，已知密钥不进入原文/视图/元数据/日志；不声称可识别任意秘密或加密。
2. 失败仅清理经身份确认的自有pending对象；已提交文件可保留，未知对象不递归删除。

**验证：** 注入密钥在所有产物均不出现；邻近用户文件不变；取消后报告真实残留而非虚称全回滚。

```text
python -m pytest tests/compact/test_archive.py tests/compact/test_archive_process.py -k ctx_t24 -q
```

### T25：让归档重读沿用原权限与hash证明

**状态：** 已实现并通过对应离线测试；实际命令与证据见第10节。  **依赖：** T22、T24。  **覆盖：** AC26、AC28、AC29。

**文件：** P35；P36；P37；P38；P06；D:/STUDY/weizhcode-python/tests/compact/test_archive.py；D:/STUDY/weizhcode-python/tests/test_tool_executor.py。

**步骤：**

1. 父进程只为已登记归档构造ArchiveReadProof；普通read_file经原门禁批准后核对root/身份/hash。
2. 原文改变返回ARCHIVE_CHANGED，删除返回不可用；旁置metadata不能自证，不通过bash或裸read_bytes绕过权限。

**验证：** 严格/PLAN/deny仍生效；读分页视图可取全文；篡改内容不能标为核验原文；普通文件不误贴归档标签。

```text
python -m pytest tests/test_context_integration.py tests/compact/test_archive.py tests/test_tool_executor.py -k ctx_t25 -q
```

### T26：建立有界捕获Hub与预留机制

**状态：** 已实现并通过对应离线测试；实际命令与证据见第10节。  **依赖：** T02、T03、T04。  **覆盖：** AC04、AC14、AC27。

**文件：** P05；P02；D:/STUDY/weizhcode-python/tests/compact/test_capture.py。

**步骤：**

1. 实现可信CaptureSink/Hub，绑定operation generation与execution_key；16KiB文本块、编码帧≤128KiB、每工具额外≤2MiB。
2. pending总预算32MiB、每调用先预留2MiB后释放未用额度、队列最多8；不足返回CONTEXT_CAPTURE_LIMIT而不执行工具。

**验证：** 大于上限明确标记incomplete；UTF-8分片安全；并发不超预算；迟到/伪造/重复帧不污染来源。

```text
python -m pytest tests/compact/test_capture.py -k ctx_t26 -q
```

### T27：在普通worker首次最终截断前捕获

**状态：** 已实现并通过对应离线测试；实际命令与证据见第10节。  **依赖：** T26。  **覆盖：** AC04、AC27、AC29。

**文件：** P36；P19；D:/STUDY/weizhcode-python/tests/compact/test_capture.py。

**步骤：**

1. 工具返回后、最终to_model_text/结果DTO截断前发送begin/chunk/end，再发送原有有界公开结果。
2. 保持原始call_id/name外层配对与操作身份绑定；Tool.execute接口/Schema不变，捕获不得混入metadata。

**验证：** 80KB返回保有内部原文而公开结果仍受旧上限；异常/进程中断的partial来源不冒充完整。

```text
python -m pytest tests/compact/test_capture.py -k ctx_t27 -q
```

### T28：核验父进程捕获帧

**状态：** 已实现并通过对应离线测试；实际命令与证据见第10节。  **依赖：** T27。  **覆盖：** AC04、AC27、AC29。

**文件：** P37；D:/STUDY/weizhcode-python/tests/compact/test_capture.py；D:/STUDY/weizhcode-python/tests/test_tool_executor.py。

**步骤：**

1. ManagedWorker按顺序、调用ID、代次、大小和结束状态校验帧，将完整/部分来源交给内部slot。
2. 沿用原IPC256KiB上限及公开结果预算，捕获解析失败产生结构化错误且保留真实已执行事实。

**验证：** 越序、错ID、超量、缺end拒绝；旧worker结果与原超时/退出流程兼容。

```text
python -m pytest tests/compact/test_capture.py tests/test_tool_executor.py -k ctx_t28 -q
```

### T29：将捕获预留放在既有门禁之后

**状态：** 已实现并通过对应离线测试；实际命令与证据见第10节。  **依赖：** T25、T26、T28。  **覆盖：** AC04、AC15、AC27、AC29。

**文件：** P38；P19；D:/STUDY/weizhcode-python/tests/test_tool_executor.py；D:/STUDY/weizhcode-python/tests/compact/test_capture.py。

**步骤：**

1. 原参数校验、模式、权限、用户批准及复检通过后才预留捕获预算并开始执行；提问工具不预留2MiB。
2. Executor在自身截断前接纳来源并释放余额；额度拒绝不重放副作用，不隐瞒此前成功的调用。

**验证：** deny/PLAN拦截不预留不执行；预算不足无副作用；已执行工具只执行一次；公开输出预算保持。

```text
python -m pytest tests/test_context_integration.py tests/test_tool_executor.py tests/compact/test_capture.py -k ctx_t29 -q
```

### T30：记录同次获准read_file纯净快照

**状态：** 已实现并通过对应离线测试；实际命令与证据见第10节。  **依赖：** T25、T29。  **覆盖：** AC14、AC26。

**文件：** P35；P36；P05；P04；D:/STUDY/weizhcode-python/tests/compact/test_capture.py；D:/STUDY/weizhcode-python/tests/test_tool_executor.py。

**步骤：**

1. 成功读取的同一I/O同时记录无行号原文、规范路径、返回行范围、换行/BOM、truncated及接纳序号。
2. 会话最多保留5次成功读取，每份头部≤17500字符；失败/权限拒绝/MCP读结果不伪造本地文件快照。

**验证：** 改动文件后恢复仍用已读片段而非重新读盘；部分范围准确；第6次淘汰最旧成功记录。

```text
python -m pytest tests/test_context_integration.py tests/compact/test_capture.py tests/test_tool_executor.py -k ctx_t30 -q
```

### T31：扩展ExternalTool捕获入口

**状态：** 已实现并通过对应离线测试；实际命令与证据见第10节。  **依赖：** T26。  **覆盖：** AC04、AC27、AC29。

**文件：** P34；P42；D:/STUDY/weizhcode-python/tests/test_mcp_tool.py；D:/STUDY/weizhcode-python/tests/compact/test_capture.py。

**步骤：**

1. 仅新增可选capture_sink内部参数，传递want_capture及执行身份；保持旧ExternalTool调用兼容。
2. 捕获MCP结果原投影后仍走旧文本/非文本适配和公开输出上限，不把MCP能力扩成资源/采样。

**验证：** 无sink旧用法不变；捕获文本与公开结果分离；非文本降级含义不变且不制造本地文件快照。

```text
python -m pytest tests/test_mcp_tool.py tests/compact/test_capture.py -k ctx_t31 -q
```

### T32：在MCP host执行后采集结果

**状态：** 已实现并通过对应离线测试；实际命令与证据见第10节。  **依赖：** T31。  **覆盖：** AC04、AC27、AC29。

**文件：** P40；P43；D:/STUDY/weizhcode-python/tests/test_mcp_tool.py；D:/STUDY/weizhcode-python/tests/compact/test_capture.py。

**步骤：**

1. 仅对当前获准want_capture调用，在最终adapt_result.to_model_text前生成有界捕获帧。
2. 沿用受管进程帧限制与所有权，各用途独立验证；Server自身工具描述/结果均不具备父进程可信来源。

**验证：** 本地回环MCP返回80KB可捕获；伪造帧/大结果有界；不重新调用远端工具取原文。

```text
python -m pytest tests/test_mcp_tool.py tests/compact/test_capture.py -k ctx_t32 -q
```

### T33：由MCP Manager绑定捕获生命周期

**状态：** 已实现并通过对应离线测试；实际命令与证据见第10节。  **依赖：** T32、T29。  **覆盖：** AC04、AC27、AC29。

**文件：** P41；P42；D:/STUDY/weizhcode-python/tests/test_mcp_tool.py；D:/STUDY/weizhcode-python/tests/compact/test_capture.py。

**步骤：**

1. 按请求ID+operation generation+execution身份接纳私有捕获帧，结束后回收预留。
2. 保持单Server失败隔离、取消失效、不自动重连/不重放；普通结果与capture错误分别保留事实。

**验证：** 交错Server回包不串线；迟到响应无污染；断线/取消不会重复执行远端副作用。

```text
python -m pytest tests/test_mcp_tool.py tests/compact/test_capture.py -k ctx_t33 -q
```

### T34：让调度器传递捕获上下文并保持屏障

**状态：** 已实现并通过对应离线测试；实际命令与证据见第10节。  **依赖：** T29、T30、T33。  **覆盖：** AC13、AC27、AC29。

**文件：** P39；D:/STUDY/weizhcode-python/tests/test_tool_scheduler.py；D:/STUDY/weizhcode-python/tests/compact/test_capture.py。

**步骤：**

1. 每批传递私有上下文与固定工具快照；来源接纳跟随实际调用结果，执行预留仍由Executor门禁之后申请。
2. 保持原并发上限4、读类并行/有副作用串行屏障、取消配对及已成功结果顺序。

**验证：** 四路读调用来源独立；写/命令不越屏障；捕获失败或取消后无悬空call/result。

```text
python -m pytest tests/test_context_integration.py tests/test_tool_scheduler.py tests/compact/test_capture.py -k ctx_t34 -q
```

### T35：实现单工具超阈值归档与预览

**状态：** 已实现并通过对应离线测试；实际命令与证据见第10节。  **依赖：** T22、T26、T34。  **覆盖：** AC04、AC07。

**文件：** P11；P03；D:/STUDY/weizhcode-python/tests/compact/test_layer1.py。

**步骤：**

1. 按安全UTF-8字节判定>50000才归档，来源优先内部捕获；遗留无来源只标记现存partial，不补执行。
2. 预览同时≤20行且≤2048字节，包含固定资料路径/截断事实并保留调用ID与成功/失败语义。

**验证：** 50000不触发、50001触发；中文边界不破码；80KB原文入档且模型实际body只见预览。

```text
python -m pytest tests/compact/test_layer1.py -k ctx_t35 -q
```

### T36：实现同一工具结果消息聚合上限

**状态：** 已实现并通过对应离线测试；实际命令与证据见第10节。  **依赖：** T35。  **覆盖：** AC05。

**文件：** P11；D:/STUDY/weizhcode-python/tests/compact/test_layer1.py。

**步骤：**

1. 先处理所有单项>50000，再计算同一结果消息聚合>200000；按体积降序、原序号升序选择未冻结项归档。
2. 按实际保留体积反复判断直到满足或无法保存；失败项留原文，不能把多个消息混成一个阈值。

**验证：** 六条40KB触发聚合、三条80KB均单项触发；200000不触发、200001触发；结果顺序与配对不变。

```text
python -m pytest tests/compact/test_layer1.py -k ctx_t36 -q
```

### T37：冻结轻量替换决策并验证幂等

**状态：** 已实现并通过对应离线测试；实际命令与证据见第10节。  **依赖：** T35、T36、T04。  **覆盖：** AC06、AC27。

**文件：** P11；P04；D:/STUDY/weizhcode-python/tests/compact/test_layer1.py。

**步骤：**

1. 按应用execution_key维护原文/预览/hash/ref整体账本，已冻结原文或预览重复请求不改变、不重复写盘。
2. 保存失败不标已处理，后续可重试；冲突不覆盖；重型归档旧资料不反改已冻结轻量决定。

**验证：** 重试、remote call_id复用、冲突、并发重复处理均稳定；失败后可恢复且无错误seen状态。

```text
python -m pytest tests/compact/test_layer1.py -k ctx_t37 -q
```

### T38：估算实际出站请求全体积

**状态：** 已实现并通过对应离线测试；实际命令与证据见第10节。  **依赖：** T07、T08、T09、T10。  **覆盖：** AC08、AC09、AC16。

**文件：** P10；D:/STUDY/weizhcode-python/tests/compact/test_estimator.py。

**步骤：**

1. 按实际PreparedRequest固定/消息投影计算ceil(chars/3.5)，覆盖稳定/动态提示、工具Schema及协议原生字段。
2. 估算不含认证/内部捕获；硬门禁含实际output4096+3000；不通过计数伪造服务器错误。

**验证：** 同正文不同工具/动态补充使估算变化；原生body字段计入；小窗口超硬预算受控停止而非发送。

```text
python -m pytest tests/compact/test_estimator.py -k ctx_t38 -q
```

### T39：实现usage锚定与增量失效规则

**状态：** 已实现并通过对应离线测试；实际命令与证据见第10节。  **依赖：** T16、T38。  **覆盖：** AC08、AC09。

**文件：** P10；P04；D:/STUDY/weizhcode-python/tests/compact/test_estimator.py；D:/STUDY/weizhcode-python/tests/test_cache_usage.py。

**步骤：**

1. 仅完整可信主请求用归一化input+output建立锚点，绑定已覆盖entry IDs/digest、固定投影与完整assistant。
2. 只估算新增部分；轻量替换、摘要、删改、模式/工具/固定补充改变时失效并全量重估；缺失usage不用伪零。

**验证：** 缓存不重复加；工具80KB降预览后估算下降；相同消息数不同内容不能复用旧锚点。

```text
python -m pytest tests/compact/test_estimator.py tests/test_cache_usage.py -k ctx_t39 -q
```

### T40：构造完整消息组与近期保护边界

**状态：** 已实现并通过对应离线测试；实际命令与证据见第10节。  **依赖：** T05、T06、T38。  **覆盖：** AC13、AC21、AC30。

**文件：** P09；D:/STUDY/weizhcode-python/tests/compact/test_history.py。

**步骤：**

1. 按可信turn/source构组，不用表面user角色代替来源；从尾部回数至至少10000估算token且至少5消息。
2. 边界扩展保全tool_use/result与原生配对；短历史全留，最新任务/近期组不可被退让删除。

**验证：** token足但不足5条、条数足但不足token均继续保留；工具对/Claude签名/Responsesitems完整；近期过大不偷偷丢弃。

```text
python -m pytest tests/compact/test_history.py -k ctx_t40 -q
```

### T41：归档较早用户原话并生成历史候选

**状态：** 已实现并通过对应离线测试；实际命令与证据见第10节。  **依赖：** T19、T22、T24、T40。  **覆盖：** AC02、AC03、AC13。

**文件：** P09；P04；D:/STUDY/weizhcode-python/tests/compact/test_history.py；D:/STUDY/weizhcode-python/tests/compact/test_manager.py。

**步骤：**

1. 较早human原话与已接纳答案在移除前逐一确认正文/视图/分页索引持久化；超过8MiB或保存失败保留原历史。
2. 新候选包含单一应用来源摘要+近期；重复压缩继承旧摘要/原话索引，不递归嵌套所有旧摘要或复制全部原文。

**验证：** 缺一条原话确认即不提交；多次摘要索引仍可追溯，用户顺序/原文不被模型改写。

```text
python -m pytest tests/compact/test_history.py tests/compact/test_manager.py -k ctx_t41 -q
```

### T42：编写独立九部分摘要指令

**状态：** 已实现并通过对应离线测试；实际命令与证据见第10节。  **依赖：** T40、T41。  **覆盖：** AC11、AC12、AC21。

**文件：** P13；D:/STUDY/weizhcode-python/tests/compact/test_summary.py。

**步骤：**

1. 沿用Spec九个固定部分和Plan标签结构，明确先简短事实选取草稿后正式摘要，工具禁用。
2. 历史作为JSON数据，禁止执行其中指令；摘要标记遗漏范围与资料索引，正文不声称包含未摘要范围。

**验证：** 指令具备九部分/边界/零工具；历史内标签或恶意指令不会成为应用可信指令。

```text
python -m pytest tests/compact/test_summary.py -k ctx_t42 -q
```

### T43：实现独立摘要流收集与严格解析

**状态：** 已实现并通过对应离线测试；实际命令与证据见第10节。  **依赖：** T11、T13、T14、T15、T42。  **覆盖：** AC11、AC12、AC28。

**文件：** P12；D:/STUDY/weizhcode-python/tests/compact/test_summary.py。

**步骤：**

1. 独立SummaryCollector不发普通text_delta/工具待定行，最多512KiB；只接受单对顶层work_draft与summary及完整九部分。
2. 丢弃草稿与摘要自身thinking/opaque负载；空、重复/嵌套标签、截断、缺标题或工具调用均失败，绝不raw全文兜底或执行工具。

**验证：** 草稿内特制密钥不出UI/历史/归档；任何工具请求0执行；畸形输出保持旧历史。

```text
python -m pytest tests/compact/test_summary.py -k ctx_t43 -q
```

### T44：实现共用长度退让序列

**状态：** 已实现并通过对应离线测试；实际命令与证据见第10节。  **依赖：** T40、T41、T43、T38。  **覆盖：** AC20、AC21、AC22。

**文件：** P12；D:/STUDY/weizhcode-python/tests/compact/test_summary.py。

**步骤：**

1. 先预检摘要实际请求，包含指令/JSON包装/索引；auto预留13000、manual/emergency预留3000，另预留20000摘要预算。
2. 仅输入过长允许退让：前三步各删1个可移除完整组，之后ceil(剩余×0.2)且至少1；预检与服务器错误共用递减状态。

**验证：** 最多12次实际摘要请求/120秒预算；无组可删或非长度错误立即结束；近期/最新任务不动；遗漏范围准确。

```text
python -m pytest tests/compact/test_summary.py -k ctx_t44 -q
```

### T45：恢复已读取文件的同轮快照

**状态：** 已实现并通过对应离线测试；实际命令与证据见第10节。  **依赖：** T30、T40。  **覆盖：** AC14。

**文件：** P14；D:/STUDY/weizhcode-python/tests/compact/test_recovery.py。

**步骤：**

1. 从固定成功读取缓存恢复最多5份各≤17500字符头部，带已读取范围/截断事实；不再执行read_file或裸I/O。
2. 只恢复已有获准内容，文件现状变化不假装新鲜；缓存缺失不从摘要脑补代码。

**验证：** 恢复内容无行号；源文件删除/修改不触发额外读；失败读/MCP结果不进入本地文件恢复。

```text
python -m pytest tests/compact/test_recovery.py -k ctx_t45 -q
```

### T46：注入可信动态恢复与实际工具清单

**状态：** 已实现并通过对应离线测试；实际命令与证据见第10节。  **依赖：** T45、T07。  **覆盖：** AC15、AC28。

**文件：** P14；P29；P30；P28；D:/STUDY/weizhcode-python/tests/compact/test_recovery.py；D:/STUDY/weizhcode-python/tests/test_context_protocols.py。

**步骤：**

1. RuntimeSupplement增加应用专用context_recovery来源，由工厂私有构造；内容从稳定七模块之外走动态消息。
2. 同一次实际工具快照生成恢复说明，PLAN仅说明实际可用读工具/提问能力；字符串特殊标签不赋予来源信任。

**验证：** 固定提示digest/缓存段不因恢复改变；未注册/PLAN禁用工具不被宣称可用；用户伪标签无权限。

```text
python -m pytest tests/compact/test_recovery.py tests/test_context_protocols.py -k ctx_t46 -q
```

### T47：控制恢复后总预算并验证真实缩小

**状态：** 已实现并通过对应离线测试；实际命令与证据见第10节。  **依赖：** T38、T39、T45、T46。  **覆盖：** AC16、AC30。

**文件：** P14；P15；D:/STUDY/weizhcode-python/tests/compact/test_recovery.py；D:/STUDY/weizhcode-python/tests/compact/test_manager.py。

**步骤：**

1. 重建真实请求后计入摘要、原话索引、近期、文件、动态补充、工具Schema与安全余量。
2. 过大先依次减半文件头至1024字符，再删最旧文件直到0，最后只精简恢复工具说明为真实全名+Schema指纹；不得删实际工具Schema/近期/索引/边界。

**验证：** 锚定与纯字符两套比较均缩小才成功；无缩小/仍超预算保持旧历史且明确原因。

```text
python -m pytest tests/compact/test_recovery.py tests/compact/test_manager.py -k ctx_t47 -q
```

### T48：原子提交压缩历史与运行态

**状态：** 已实现并通过对应离线测试；实际命令与证据见第10节。  **依赖：** T41、T43、T47、T24。  **覆盖：** AC03、AC12、AC16、AC27。

**文件：** P15；P20；P04；D:/STUDY/weizhcode-python/tests/compact/test_manager.py。

**步骤：**

1. 提交前检查generation/取消/deadline、原话/索引引用、摘要结构/配对、budget/shrink与revision/mode/tools快照。
2. 父事件循环无await完成Conversation CAS与对应runtime更新/清锚点；失败不改旧历史，诚实保留已落盘资料和已完成Layer1。

**验证：** 旧revision、模式变化、取消和迟到回包均不得部分提交；无效摘要不能替换原文。

```text
python -m pytest tests/compact/test_manager.py -k ctx_t48 -q
```

### T49：编排正常请求前两层处理

**状态：** 已实现并通过对应离线测试；实际命令与证据见第10节。  **依赖：** T37、T39、T44、T48。  **覆盖：** AC09、AC10、AC16、AC30。

**文件：** P15；D:/STUDY/weizhcode-python/tests/compact/test_manager.py。

**步骤：**

1. before_request先Layer1再估算，达到window−33000且未熔断才发auto摘要开始；每个请求前最多一次重型操作。
2. auto失败后仅硬预算仍可容纳才继续普通请求，否则受控停止；轻量成功不能假发正在摘要。

**验证：** window100000时66999不触发、67000触发；轻量足以降阈值时不摘要；不会为凑失败数发送超大请求。

```text
python -m pytest tests/compact/test_manager.py -k ctx_t49 -q
```

### T50：实现仅自动路径的三次熔断

**状态：** 已实现并通过对应离线测试；实际命令与证据见第10节。  **依赖：** T49、T04。  **覆盖：** AC23。

**文件：** P15；P04；D:/STUDY/weizhcode-python/tests/compact/test_manager.py。

**步骤：**

1. 一次最终auto成功清零，失败/无缩小/长度耗尽加1，取消不变；达到3后跨用户任务停止自动重型。
2. 手动/紧急绕过且不读写自动计数，成功也不复位已熔断；Layer1继续可用。

**验证：** 内部多次摘要退让只计一次失败；第三次后不再auto；manual/emergency成功后仍维持原计数。

```text
python -m pytest tests/compact/test_manager.py -k ctx_t50 -q
```

### T51：增加独立手动压缩编排

**状态：** 已实现并通过对应离线测试；实际命令与证据见第10节。  **依赖：** T48、T50。  **覆盖：** AC17、AC23。

**文件：** P15；D:/STUDY/weizhcode-python/tests/compact/test_manager.py。

**步骤：**

1. manual非空跳过额外Layer1/阈值/熔断判断，保持已有冻结预览，仍执行必要原话归档与同套提交规则。
2. 空历史no-op，无缩小不报成功；所有结果返回有区分的CompactOutcome。

**验证：** 短会话/已熔断可手动尝试；空历史0摘要请求；成功/失败/无缩小不会篡改自动计数。

```text
python -m pytest tests/compact/test_manager.py -k ctx_t51 -q
```

### T52：统一操作预算、取消与事件阶段

**状态：** 已实现并通过对应离线测试；实际命令与证据见第10节。  **依赖：** T44、T48、T49、T51。  **覆盖：** AC22、AC24、AC27、AC28。

**文件：** P15；P02；D:/STUDY/weizhcode-python/tests/compact/test_manager.py；D:/STUDY/weizhcode-python/tests/compact/test_archive_process.py。

**步骤：**

1. 所有存储/摘要/恢复/清理共享绝对120秒与12实际请求预算，最后2秒留清理，阶段间不重新计时。
2. CompactionNotice携带operation_id、触发原因、阶段和可选估算；取消关闭当前流/自有进程并禁止迟到历史更新。

**验证：** 先到次数/时限均结束；事件开始与终结对应；未知数字不造0；OS清理不确定如实说明。

```text
python -m pytest tests/compact/test_manager.py tests/compact/test_archive_process.py -k ctx_t52 -q
```

### T53：接入Agent每次普通请求前的管理

**状态：** 已实现并通过对应离线测试；实际命令与证据见第10节。  **依赖：** T34、T49、T52。  **覆盖：** AC10、AC24、AC29、AC30。

**文件：** P32；P31；D:/STUDY/weizhcode-python/tests/test_context_integration.py；D:/STUDY/weizhcode-python/tests/test_turn_runner.py。

**步骤：**

1. Runner持有同一SessionRuntime，用户输入只接纳一次；固定模式/工具/提示快照后调用before_request，再发送返回的PreparedRequest。
2. 每次工具结果回写后的下一请求同样走管理；压缩不重置Agent迭代上限、不重排已完成工具对。

**验证：** 多轮长任务自动触发后继续；同批工具结果不重复；压缩请求不计普通迭代。

```text
python -m pytest tests/test_context_integration.py tests/test_turn_runner.py -k ctx_t53 -q
```

### T54：增加输入长度错误的一次紧急重试

**状态：** 已实现并通过对应离线测试；实际命令与证据见第10节。  **依赖：** T53、T13、T14、T15、T44。  **覆盖：** AC19、AC20、AC24。

**文件：** P32；P15；D:/STUDY/weizhcode-python/tests/test_context_integration.py；D:/STUDY/weizhcode-python/tests/test_turn_runner.py。

**步骤：**

1. 当前普通请求明确context_length时，同一迭代只进入一次emergency，先确保Layer1再强制摘要，使用manual/emergency安全余量。
2. 成功后重新prepare/硬预检，用新request_id重试原请求；失败/再次长度错结束本轮，不重复用户输入、历史或已完成工具。

**验证：** 输出截断/额度/网络不触发；失败流工具0执行；已执行工具计数不变；二次长度错无再次压缩。

```text
python -m pytest tests/test_context_integration.py tests/test_turn_runner.py -k ctx_t54 -q
```

### T55：提供Runner手动事件入口与忙碌互斥

**状态：** 已实现并通过对应离线测试；实际命令与证据见第10节。  **依赖：** T51、T52、T53。  **覆盖：** AC17、AC18、AC27。

**文件：** P32；D:/STUDY/weizhcode-python/tests/test_context_integration.py；D:/STUDY/weizhcode-python/tests/test_turn_runner.py。

**步骤：**

1. force_compact同步认领busy并创建独立操作上下文/事件通道，不走run、不入用户消息、不排队等待主任务。
2. 与普通任务共享取消/结算/结束门禁，空闲后释放；并发run/manual只能一方成功。

**验证：** busy请求立即拒绝无摘要调用；空历史no-op；手动任务不增加普通迭代或改用户草稿。

```text
python -m pytest tests/test_context_integration.py tests/test_turn_runner.py -k ctx_t55 -q
```

### T56：接入用量、失败流与关闭生命周期

**状态：** 已实现并通过对应离线测试；实际命令与证据见第10节。  **依赖：** T16、T53、T54、T55。  **覆盖：** AC22、AC24、AC28、AC29。

**文件：** P32；P15；P06；D:/STUDY/weizhcode-python/tests/test_context_integration.py；D:/STUDY/weizhcode-python/tests/test_turn_runner.py。

**步骤：**

1. 普通/摘要/紧急重试按请求结算，事件带purpose/触发原因；摘要部分usage也可入会话总量但不作主锚点。
2. aclose先冻结新任务/取消当前操作/补配对和结算，再关Context/Store，再原Executor/MCP/权限；共享幂等Future避免等待自身。

**验证：** 重复close无死锁；取消后无迟到历史；旧工具配对完整，主请求与摘要成本不混计/漏计。

```text
python -m pytest tests/test_context_integration.py tests/test_turn_runner.py -k ctx_t56 -q
```

### T57：集中空闲斜杠命令注册

**状态：** 已实现并通过对应离线测试；实际命令与证据见第10节。  **依赖：** T55。  **覆盖：** AC18、AC29。

**文件：** P18；D:/STUDY/weizhcode-python/tests/test_context_tui.py。

**步骤：**

1. 登记/exit、/quit、/plan、/do、/compact；保留退出别名和旧模式行为，未知空闲斜杠命令不发送模型。
2. 命令模块只负责空闲分派，不引入CLI框架，也不绕过审批/提问通道。

**验证：** 五命令和未知命令分派正确；/compact不变成普通用户问题；/do来源仍是应用指令。

```text
python -m pytest tests/test_context_tui.py -k ctx_t57 -q
```

### T58：显示压缩阶段与恢复输入状态

**状态：** 已实现并通过对应离线测试；实际命令与证据见第10节。  **依赖：** T55、T56、T57。  **覆盖：** AC11、AC17、AC24、AC28。

**文件：** P45；D:/STUDY/weizhcode-python/tests/test_context_tui.py；D:/STUDY/weizhcode-python/tests/test_tui.py。

**步骤：**

1. TUI消费CompactionNotice显示auto/manual/emergency、阶段、可用前后估算及失败/无缩小/取消原因。
2. 按operation_id匹配终结，保留scrollback与草稿、恢复焦点；不展示摘要草稿、不以假0说明成功，不销毁已展示工具历史。

**验证：** 旧事件不能清新操作菜单；成功/失败/取消均可继续输入；文本中无work_draft内容。

```text
python -m pytest tests/test_context_tui.py tests/test_tui.py -k ctx_t58 -q
```

### T59：回归提问、批准、模式与忙碌路由

**状态：** 已实现并通过对应离线测试；实际命令与证据见第10节。  **依赖：** T06、T57、T58。  **覆盖：** AC18、AC28、AC29。

**文件：** P45；P33；D:/STUDY/weizhcode-python/tests/test_context_tui.py；D:/STUDY/weizhcode-python/tests/test_user_questions.py。

**步骤：**

1. 按Plan顺序保留退出/取消、原提问/批准通道、busy门禁，最后空闲命令；压缩时拒绝模式切换/Shift+Tab。
2. 已有AskUserQuestion答案不被数字或斜杠命令分派吞掉；审批交互不被摘要产生的内容伪造。

**验证：** 用户真实答案和批准按原路径提交；busy无排队；/exit与/quit仍能安全取消关闭。

```text
python -m pytest tests/test_context_tui.py tests/test_user_questions.py -k ctx_t59 -q
```

### T60：建立显式生产Runtime工厂

**状态：** 已实现并通过对应离线测试；实际命令与证据见第10节。  **依赖：** T03、T04、T22、T26、T52。  **覆盖：** AC01、AC25、AC29。

**文件：** P16；P01；D:/STUDY/weizhcode-python/tests/test_cli.py；D:/STUDY/weizhcode-python/tests/test_config.py。

**步骤：**

1. build_context_runtime接收root_identity、effective window、合并redactor与store_factory，装配同一runtime的捕获/归档/manager。
2. Noop仅显式测试注入；根不可用时仅归档受控不可用，不让生产静默禁用整套管理。

**验证：** 纯聊天仍可估算；正常factory非Noop；两runtime不共享账本；构造不提前建会话资料。

```text
python -m pytest tests/test_cli.py tests/test_config.py -k ctx_t60 -q
```

### T61：统一CLI、MCP启动与TUI后备装配

**状态：** 已实现并通过对应离线测试；实际命令与证据见第10节。  **依赖：** T60、T56、T58。  **覆盖：** AC25、AC28、AC29。

**文件：** P44；P45；D:/STUDY/weizhcode-python/tests/test_cli.py；D:/STUDY/weizhcode-python/tests/test_mcp_bootstrap.py；D:/STUDY/weizhcode-python/tests/test_context_integration.py。

**步骤：**

1. MCP Bootstrap.prepare先完成以合并秘密，再创建Runtime并同时注入Executor/Runner；普通CLI与后备TUI路径同样生产注入。
2. 保持Server失败隔离、原权限/模式/关闭行为；只读临时测试配置，不读取用户真实模型/MCP配置。

**验证：** MCP开/关与后备构造均启用管理；共享redactor涵盖MCP秘密；启动/退出和旧配置均兼容。

```text
python -m pytest tests/test_cli.py tests/test_mcp_bootstrap.py tests/test_context_integration.py -k ctx_t61 -q
```

### T62：补充示例与用户说明

**状态：** 已实现并通过对应离线测试；实际命令与证据见第10节。  **依赖：** T03、T20、T57、T61。  **覆盖：** AC25、AC28、AC29。

**文件：** P46；P48；D:/STUDY/weizhcode-python/tests/test_config.py。

**步骤：**

1. 仅示例YAML加入可选context_window及应用默认说明，真实配置不动；README解释/compact、两层策略、费用与熔断。
2. 说明资料原文/预览/分页路径、已知密钥脱敏但不加密、文件恢复非重新读取、重启不恢复与平台未验边界。

**验证：** 示例在临时环境可解析且窗口正确；README不暗示免费/精确token/全量保密/自动恢复。

```text
python -m pytest tests/test_config.py -k ctx_t62 -q
```

### T63：完成三协议实际请求体矩阵

**状态：** 已实现并通过对应离线测试；实际命令与证据见第10节。  **依赖：** T08、T09、T10、T13、T14、T15、T39、T43、T46、T54。  **覆盖：** AC04、AC08、AC11、AC13、AC15、AC19、AC20、AC24、AC29。

**文件：** P24；P25；P26；P28；D:/STUDY/weizhcode-python/tests/test_context_protocols.py；D:/STUDY/weizhcode-python/tests/test_protocol_integration.py。

**步骤：**

1. 使用拦截传输逐协议比较PreparedRequest与实际body，覆盖普通工具、摘要0工具、动态恢复、固定缓存、native配对。
2. 参数化HTTP/流错误正反例、输出结束与usage；不使用真实域名请求或以fake替代收费验证。

**验证：** 三协议完整矩阵均通过；所有AC中的请求字段和长度反例有断言，不只检查抽象mock调用。

```text
python -m pytest tests/test_context_protocols.py tests/test_protocol_integration.py -k ctx_t63 -q
```

### T64：离线跑通长任务与两层压缩

**状态：** 已实现并通过对应离线测试；实际命令与证据见第10节。  **依赖：** T53、T54、T55、T61。  **覆盖：** AC01、AC02、AC04、AC05、AC19、AC26、AC30。

**文件：** P32；P15；D:/STUDY/weizhcode-python/tests/test_context_integration.py。

**步骤：**

1. fake模型+真实临时本地工具/回环MCP构造80KB结果、六条40KB、连续多轮、旧用户原话与至少两次摘要。
2. 覆盖自动、手动、紧急、超大近期受控停止及经原权限重读分页归档，统计模型请求/执行次数与迭代。

**验证：** 历史中只保留预览/摘要+近期，原话资料可核验，长任务继续且无重复副作用；近期超预算明确停止。

```text
python -m pytest tests/test_context_integration.py -k ctx_t64 -q
```

### T65：故障注入验证有界与事务

**状态：** 已实现并通过对应离线测试；实际命令与证据见第10节。  **依赖：** T23、T24、T37、T48、T50、T52、T56。  **覆盖：** AC03、AC06、AC12、AC16、AC21、AC22、AC23、AC27、AC28。

**文件：** P15；P06；P05；D:/STUDY/weizhcode-python/tests/compact/test_manager.py；D:/STUDY/weizhcode-python/tests/compact/test_archive_process.py；D:/STUDY/weizhcode-python/tests/test_context_integration.py。

**步骤：**

1. 逐点注入归档失败/不确定提交、hash冲突、坏摘要、取消、慢磁盘、迟到响应、模式/revision变化和捕获额度耗尽。
2. 用受控时钟验证12次/120秒与清理预算；并发读仍原上限4；失败不靠删断言或默认BYPASS变绿。

**验证：** 无部分历史提交、悬空工具对、无限等待或重复执行；熔断边界准确，失败后会话可继续或受控停止。

```text
python -m pytest tests/compact/test_manager.py tests/compact/test_archive_process.py tests/test_context_integration.py -k ctx_t65 -q
```

### T66：验证隐私、来源与恶意内容隔离

**状态：** 已实现并通过对应离线测试；实际命令与证据见第10节。  **依赖：** T25、T43、T46、T59、T61。  **覆盖：** AC07、AC11、AC26、AC28、AC29。

**文件：** P06；P12；P29；P45；D:/STUDY/weizhcode-python/tests/test_context_integration.py；D:/STUDY/weizhcode-python/tests/test_context_tui.py；D:/STUDY/weizhcode-python/tests/compact/test_archive.py。

**步骤：**

1. 注入已知密钥、恶意工具结果/标签、伪造metadata/call_id、summary工具请求与假用户答案。
2. 检查出站副本、UI/事件/repr、归档/视图/索引与残留pending；归档/原话hash按脱敏后正文核验。

**验证：** 已知密钥无回显，草稿无外泄；模型数据不取得应用信任或权限；用户邻近文件未改，安全能力不夸大。

```text
python -m pytest tests/test_context_integration.py tests/test_context_tui.py tests/compact/test_archive.py -k ctx_t66 -q
```

### T67：执行完整离线回归与编译检查

**状态：** 最终统一完整回归932 passed、6 skipped，273.02秒；编译与差异检查通过，详见第10节。  **依赖：** T62、T63、T64、T65、T66。  **覆盖：** AC29。

**文件：** D:/STUDY/weizhcode-python/tests/compact/test_state.py。

**步骤：**

1. 运行所有新增/扩展测试及原tests全套，记录pass/fail/skip原因和现有基线差异；确认生产文件仅Plan48项范围。
2. 执行编译与差异空白检查，复核真实配置/用户样本未改；不临时装Ruff/mypy冒充项目已有检查。

**验证：** 编译/全量测试/空白检查无新增失败；平台跳过逐项列出，不将skip算通过。

```text
python -m compileall -q src/weizhcode tests
python -m pytest -q
git diff --check
```

### T68：提供可控手动验证入口

**状态：** 观察入口与默认安全门禁已完成并验证。  **依赖：** T64、T65、T66。  **覆盖：** AC18、AC28、AC30。

**文件：** D:/STUDY/weizhcode-python/tests/manual_context_smoke.py；D:/STUDY/weizhcode-python/tests/test_context_integration.py。

**步骤：**

1. 实现默认/--help仅离线说明；--terminal用临时root/home+fake模型+真实本地工具/回环MCP，明确自有临时资料保留/清理方式。
2. --live与terminal互斥，先列域名/协议/模型、临时操作、摘要/重试上限和费用再要求真实确认；未确认不加载凭据或调用模型。

**验证：** 默认及help零真实配置/网络/资料副作用；非法选项组合拒绝；live确认门禁不可绕过。

```text
python -m pytest tests/test_context_integration.py -k ctx_t68 -q
```

### T69：记录原生平台与真实终端证据

**状态：** 已记录本机Windows原生专项及控制台PTY观察；POSIX/部分原生链接待环境。  **依赖：** T67、T68。  **覆盖：** AC18、AC22、AC27、AC28、AC29、AC30。

**文件：** D:/STUDY/weizhcode-python/tests/manual_context_smoke.py。

**步骤：**

1. 在可用原生平台运行链接/reparse/进程所有权专项；当前Windows结果与未运行POSIX分开，不拿一个平台推断另一个。
2. 真实终端手动跑--terminal观察流式、scrollback、/compact、提问/批准、取消/退出与草稿焦点；无可用终端则记录待验证，不用Pilot代替。

**验证：** 平台/终端逐项保留命令与观察结果；不可用项明确待验且不擅自标通过。

```text
python -m pytest tests/compact/test_archive.py tests/compact/test_archive_process.py -q
python tests/manual_context_smoke.py --terminal
```

### T70：整理验收证据并单列收费验证

**状态：** 证据与未验项已整理，待用户审核；收费调用未授权、未执行。  **依赖：** T67、T68、T69。  **覆盖：** AC29、AC30。

**文件：** D:/STUDY/weizhcode-python/specs/context-management/task.md；D:/STUDY/weizhcode-python/specs/context-management/checklist.md。

**步骤：**

1. 按批准后的Checklist逐条链接测试/观察证据，记录未通过、未验及原因；不把全量测试数字当成全部协议/平台真实验证。
2. 真实模型验证另列待授权，只有用户明确同意费用/临时范围后才运行--live；本任务默认不启动收费调用，不自动commit/push。

**验证：** 全部任务状态与证据一致；离线、原生平台、真实终端、真实模型分层清楚；仍有必需未验项不得宣称全面验收完成。

人工核对：人工逐条核对本章已批准Checklist、测试输出与工作区差异；记录真实模型验证为待授权，或附获得明确授权后的实际结果。

## 4. 顺序与阶段门禁

依赖均指向前序任务；默认按T01至T70顺序执行，不要求并行代理。下列阶段只归并进度，不代替各任务验证。

| 阶段 | 任务 | 阶段结束必须具备 | 当前状态 |
|---|---|---|---|
| G1 基础与协议 | T01–T16 | 隔离夹具、来源/历史契约、配置、真实准备请求与严格错误/usage口径 | 基础实现及本项验证完成；完整功能尚未验收 |
| G2 归档安全 | T17–T25 | 原文/视图/索引、固定进程、有界I/O、核验重读及失败保留 | 已实现、本机离线通过；原生跳过单列 |
| G3 捕获接入 | T26–T34 | 首次最终截断前双通道捕获，内置/MCP/调度器不绕原门禁 | 已实现、本地工具/本地MCP/屏障测试通过 |
| G4 压缩算法 | T35–T48 | 稳定轻量预览、估算、原话/近期、严格摘要、恢复与CAS提交 | 已实现、离线边界与故障测试通过 |
| G5 Agent编排 | T49–T56 | 自动/手动/紧急、熔断、一次重试、取消/用量/关闭 | 已实现、离线闭环与用量测试通过 |
| G6 UI与生产装配 | T57–T62 | 命令/交互、阶段显示、各入口同一生产Runtime与使用说明 | 已实现、生产入口与界面测试通过 |
| G7 验证交付 | T63–T70 | 请求矩阵、长任务、故障/隐私回归、平台/终端证据与未验清单 | 本机证据已整理；其他平台/收费验证未冒充通过 |

- G2未通过不能对模型公开资料引用；G3未通过不能声称保有被旧截断移除的原文。
- G4未通过不能替换生产历史；G5/G6未通过不能把局部压缩算法宣称为可用的用户功能。
- T67是开发离线回归；T69仅在实际可用平台/终端执行，缺少环境要记录待验。T70中的收费测试不是默认执行步骤，不把收费授权当作实现授权。
- 不用人为超大真实用户任务测试边界；阈值、时限、次数和巨大结果用受控离线样本验证。

## 5. Spec逐条验收对应

同一AC可由多个任务共同提供证据；映射不是通过声明。下阶段Checklist将据此逐条落成行为检查。

| 验收标准 | 任务 |
|---|---|
| AC01 | T02、T04、T17、T22、T60、T64 |
| AC02 | T05、T06、T19、T41、T64 |
| AC03 | T18、T20、T22、T23、T41、T48、T65 |
| AC04 | T08、T09、T10、T26、T27、T28、T29、T31、T32、T33、T35、T63、T64 |
| AC05 | T36、T64 |
| AC06 | T04、T18、T22、T37、T65 |
| AC07 | T17、T18、T19、T35、T66 |
| AC08 | T07、T16、T38、T39、T63 |
| AC09 | T07、T38、T39、T49 |
| AC10 | T49、T53 |
| AC11 | T08、T09、T10、T42、T43、T58、T63、T66 |
| AC12 | T42、T43、T48、T65 |
| AC13 | T05、T08、T09、T10、T34、T40、T41、T63 |
| AC14 | T26、T30、T45 |
| AC15 | T08、T09、T10、T29、T46、T63 |
| AC16 | T38、T47、T48、T49、T65 |
| AC17 | T51、T55、T58 |
| AC18 | T06、T55、T57、T59、T68、T69 |
| AC19 | T11、T13、T14、T15、T54、T63、T64 |
| AC20 | T11、T12、T13、T14、T15、T44、T54、T63 |
| AC21 | T40、T42、T44、T65 |
| AC22 | T23、T44、T52、T56、T65、T69 |
| AC23 | T04、T50、T51、T65 |
| AC24 | T16、T52、T53、T54、T56、T58、T63 |
| AC25 | T03、T60、T61、T62 |
| AC26 | T19、T25、T30、T64、T66 |
| AC27 | T04、T05、T17、T21、T22、T23、T26、T27、T28、T29、T31、T32、T33、T34、T37、T48、T52、T55、T65、T69 |
| AC28 | T02、T06、T12、T17、T18、T20、T21、T23、T24、T25、T43、T46、T52、T56、T58、T59、T61、T62、T65、T66、T68、T69 |
| AC29 | T01、T02、T05、T07、T08、T09、T10、T11、T21、T25、T27、T28、T29、T31、T32、T33、T34、T53、T56、T57、T59、T60、T61、T62、T63、T66、T67、T69、T70 |
| AC30 | T40、T47、T49、T53、T64、T68、T69、T70 |

## 6. 本轮交付与审批

本轮仅交付任务拆解：70项、48个生产文件范围、30条AC映射；尚未编写实现代码、建立会话资料目录、运行本章实现测试或调用真实模型。

本 Task 已获整份批准；当前只生成 Checklist。Checklist也获批后，才按上述任务进入开发与验证。

## 7. 实施进度记录（2026-11-18，第一批）

第一批完成T01–T11基础与请求层。尚未提供/compact、归档、两层压缩或紧急恢复功能，不能宣称本章完成；第二批进度见下一节。

验证使用本项目.venv的Python3.13.5、pytest9.1.1、Windows原生环境；每项命令文件范围沿用Task，前缀为 `python -m pytest`，使用以下选择器及 `-q`。所有样本离线/临时，未读取真实供应商/MCP配置。

| 任务 | 选择器 | 实际结果 |
|---|---|---|
| T01 | ctx_t01 | 3 passed；旧基线加此3项为726 passed/4 skipped |
| T02 | ctx_t02 | 2 passed |
| T03 | ctx_t03 | 21 passed |
| T04 | ctx_t04 | 4 passed |
| T05 | ctx_t05 | 3 passed |
| T06 | ctx_t06 | 3 passed |
| T07 | ctx_t07 | 7 passed |
| T08–T10 | ctx_t08 or ctx_t09 or ctx_t10 | 合并9 passed（各协议3项） |
| T11 | ctx_t11 | 1 passed |

- 第一批相关回归141 passed；请求/原生负载专项修复后111 passed。曾发现原生加密负载重放回归，修复实现并保留旧断言重跑通过。
- 初始受限环境Windows asyncio创建回环连接卡住，核实调用栈后只停止本项目自有测试进程；授权本机回环运行后测试正常。未把卡住报通过。
- 编译 `python -m compileall -q src/weizhcode tests` 与差异空白检查通过；另查10个新增源码/测试文件，无行尾空白。第一批完整离线回归：776 passed、4 skipped，耗时147.42秒；这是本批回归，不是整章功能验收。
- 下一项T12有界HTTP错误与安全分类，其后T13–T16。后续资料/捕获/压缩/UI集成未实施；现有生产入口尚未自动执行上下文压缩。
- 未commit/push；原有.weizhcode-test/、.weizhcode/mcp.yaml、hello.txt未改动。真实终端、POSIX与真实模型专项未运行。

## 8. 实施进度记录（2026-11-18，基础与协议阶段）

T12–T16已完成，G1的T01–T16均通过各自离线验证。T06提供可信答案/应用来源的内部通道，生产/do来源路由仍在T59接入；T16提供去重分账契约，摘要/紧急用量UI仍在T56接入。不能将这些基础测试解释为完整用户功能已上线。

命令沿用Task对应文件与项目.venv，以下选择器已逐项实际运行：

| 任务 | 选择器 | 实际结果 |
|---|---|---|
| T12 | ctx_t12 | 18 passed |
| T13 | ctx_t13 | 12 passed |
| T14 | ctx_t14 | 10 passed |
| T15 | ctx_t15 | 13 passed |
| T16 | ctx_t16 | 1 passed |

- 请求层、用量、三协议错误/HTTP与SSE路径、既有流式/原生负载回归：193 passed。
- Context7核对HTTPX流式错误读取/关闭方式及百炼严格输入长度格式；普通max_tokens范围错误不当输入过长，未知兼容错误不猜测。
- G1最终完整回归：830 passed、4 skipped，147.88秒。跳过为两个POSIX专项及两个无原生目录链接权限专项；不是本章全部验收通过。
- 下一项T17归档根与路径身份检查，随后T18–T25资料提交/分页/权限重读；当前没有创建真实会话资料，也没有/compact或自动压缩。

## 9. 实施进度记录（2026-11-18，归档路径与写入基础）

- T17：应用生成安全记录ID；未知根/身份失败时拒绝；归档路径组件拒绝越界、设备名与重定向；固定现有目录/文件句柄，复核根与文件身份，保护结束后验证凭据失效。
- 原生Windows测试发现仅READ_ATTRIBUTES不足以阻止目录替换，改为同时申请读数据/目录列表并禁止删除共享，保留原断言后通过；junction拒绝与目录重命名阻止已实际验证。
- T17实际命令：`.\.venv\Scripts\python.exe -m pytest tests/compact/test_archive.py -k ctx_t17 -q -rs`；22 passed、2 skipped。跳过是当前不能创建原生符号链接，以及POSIX原生目录句柄分支；不推断POSIX已通过。
- T18：安全UTF-8精确写入、O_EXCL独占创建、fsync、来源身份/体量/hash核验、同文件系统硬链接无覆盖发布。冲突不覆盖；失败可保留自有暂存，发布后核验失败返回ARCHIVE_COMMIT_UNCERTAIN。
- T18实际命令：`.\.venv\Scripts\python.exe -m pytest tests/compact/test_archive.py -k ctx_t18 -q`；6 passed。覆盖BOM/CRLF/控制字符原样保留、8MiB/2MiB/64KiB恰好与超限、磁盘失败、内容篡改与发布后未确认。
- 归档本批合计28 passed、2 skipped；相关离线回归163 passed、2 skipped（新增发布不确定用例之前），编译与差异空白检查通过。新增文件空白另外检查。
- 本批完整离线回归：858 passed、6 skipped，143.99秒。6项跳过为3个POSIX专项、3个原生符号链接权限不足专项；Windows junction及句柄固定测试已通过。归档服务、分页索引、固定I/O进程、权限重读与上下文压缩仍未接入生产入口；下项T19。
- 未创建真实会话资料，未读取/修改真实配置或用户样本，未提交/推送。所有文件操作测试均为自有临时目录。

## 10. 实施完成与审核证据（2026-11-18）

开发范围已接通生产：工具原文私有捕获、懒归档/分页/核验重读、轻量替换、实际请求估算与usage锚点、九部分摘要、近期保护/原话归档、文件快照恢复、CAS提交、自动/手动/紧急编排、三次自动熔断、`/compact`、TUI阶段与CLI/MCP装配。真实配置和用户样本未读写，未commit/push。没有新增依赖或临时安装检查工具。

### 10.1 任务与测试入口

命令均在本项目根目录，使用 `.venv/Scripts/python.exe -m pytest`，后接下列文件与选择器。每个ctx_t01–ctx_t66及ctx_t68均实际有收集；T67是全量/编译入口，T69/T70为观察与证据整理，不伪造用例。T25/T29/T30/T34的集成断言实际放在test_context_integration.py，已在原验证命令中补充此文件，未删除原测试入口或修改需求。

| 任务 | 证据归属 |
|---|---|
| T01–T18 | 第7–9节记录及最终回归；原有断言保留 |
| T19–T24 | tests/compact/test_archive.py、test_archive_process.py；分页、Git门禁、固定进程、取消/丢回复核验、已知密钥脱敏与自有清理 |
| T25 | tests/test_context_integration.py -k ctx_t25；普通权限重读、显式deny、内容篡改、同文异身份替换、删除拒绝 |
| T26–T28 | tests/compact/test_capture.py；32MiB预留/队列8/旧代际拒绝、80KB首次最终截断前捕获、2MiB超限不完整 |
| T29–T30 | tests/test_context_integration.py -k 'ctx_t29 or ctx_t30'；授权后预留、额度不足不执行、deny先于额度、同次纯原文/BOM/CRLF快照 |
| T31–T33 | tests/compact/test_capture.py及tests/test_context_integration.py；真实本地stdio MCP返回80KB、私有帧/公开DTO分开、Agent下一请求仅预览、不伪造本地文件快照 |
| T34 | tests/test_context_integration.py -k ctx_t34；真实四路读来源独立、峰值4、副作用写屏障与后续读顺序 |
| T35–T37 | tests/compact/test_layer1.py；50000/50001、200000/200001字节边界、六条40KB只归档一条、排序/唯一身份、保存失败不冻结与并发重试幂等 |
| T38–T39 | tests/compact/test_estimator.py、tests/test_cache_usage.py；实际body投影、连续三次usage覆盖、不重复加缓存、内容/固定补充变化失效 |
| T40–T41 | tests/compact/test_history.py、test_manager.py、tests/test_context_integration.py；近期双下界/完整任务组、两次摘要与用户原话/提问答案索引 |
| T42–T44 | tests/compact/test_summary.py；严格标签/九标题/空节拒绝、工具0执行、草稿隔离、512KiB边界、预检与API长度错误共用退让序列、12次上限及非长度不重试 |
| T45–T48 | tests/compact/test_recovery.py、test_manager.py；不读盘的最多5份历史片段、逐级减半/移除/Schema指纹、真实缩小、revision/mode/索引篡改/取消/坏摘要/保存失败不半提交 |
| T49–T52 | tests/compact/test_manager.py；66999/67000阈值、自动最终三次失败、手动不改计数、取消及绝对deadline路径；I/O进程专项补充覆盖 |
| T53–T56 | tests/test_context_integration.py；固定100000窗口两次自动压缩、手动空历史0调用、紧急同迭代只重试一次、已执行写工具不重放、第二次长度错误停止后仍可继续 |
| T57–T59 | tests/test_context_tui.py、tests/test_user_questions.py、tests/test_tui.py；草稿/焦点/scrollback保留、旧operation_id不清新状态、busy不排队、原答案/审批路由与/do应用来源 |
| T60–T62 | tests/test_cli.py、test_mcp_bootstrap.py、test_config.py；普通CLI/MCP/后备TUI共享生产运行态、懒创建、示例应用窗口 |
| T63–T66 | tests/test_context_protocols.py、test_context_integration.py及compact各组；真实三协议适配器抓实际body、缓存/恢复分离、全链路、故障与已知秘密/草稿隔离 |
| T67–T70 | 下列完整回归、原生/终端记录及Checklist逐项状态 |

### 10.2 实际运行结果

| 命令/范围 | 实际结果 |
|---|---|
| tools执行/当前捕获接入相关回归 | 46 passed、1 skipped，29.03秒 |
| compact目录（首批完整算法） | 65 passed、2 skipped，18.10秒 |
| tests/test_turn_runner.py、test_user_questions.py、test_context_integration.py | 61 passed，14.14秒（当时收集版本） |
| tests/test_tui.py、test_cli.py、test_turn_runner.py、test_mcp_bootstrap.py | 62 passed，17.74秒（当时收集版本） |
| tests/test_context_tui.py与test_layer1.py | 4 passed，7.78秒（当时收集版本） |
| 全部上下文专项合并 | 168 passed、2 skipped，95.08秒（当时收集版本） |
| 原生归档/进程专项 -q -rs | 39 passed、2 skipped，5.61秒 |
| 三协议实际wire/cache/summary矩阵 -k ctx_t63 | 3 passed，0.45秒；此前因组合命名选择器未命中为0收集，已修正并重跑，不把0收集算通过 |
| 上一轮全量 pytest -q -rs | 917 passed、6 skipped，268.57秒 |
| 锚点复核之前的阶段完整回归 pytest -q -rs | 921 passed、6 skipped，275.10秒 |
| 后补阈值/固定100000长任务/锚点专项 | 5 passed，26.24秒；其中两条阈值为全量收集后新增，其余为更新/重跑 |
| 后补512KiB/2MiB恰好与超限 | 3 passed，1.57秒 |
| 后补deny先于捕获额度 | 1 passed，1.21秒 |
| 后补同名替换/删除归档 | 1 passed，4.03秒 |
| 两次摘要后经普通权限读取原话索引/视图 | 1 passed，17.23秒 |
| Windows原生archive/tools/MCP收尾及旁侧对照进程 | 3 passed，2.95秒 |
| 收尾统一回归（锚点复用复核之前） | 929 passed、6 skipped，280.84秒 |
| 三协议动态提醒移动/请求体/原生回放专项 | 122 passed，29.27秒 |
| 锚点修正后的manager/完整上下文闭环/三协议 | 99 passed，87.65秒 |
| 候选估算纯检查与失败usage降级 | 1 passed，1.51秒 |

以上不同运行不能相加伪造某一次pytest输出；最终新增/更新用例均有单独执行证据。编译 `python -m compileall -q src/weizhcode tests` 已通过；`git diff --check`退出0，只有LF/CRLF提示，不是空白错误；新增文件另用rg检查，无行尾空白。Ruff/mypy未配置、未安装、未宣称通过。

6个全量skip：本章归档原生符号链接不可创建、归档POSIX目录句柄、旧MCP POSIX权限、旧沙箱原生目录链接权限、旧搜索目录链接权限、旧工具POSIX进程组；其中3个POSIX、3个原生链接权限限制。Windows junction和句柄固定测试实际通过，不以其代替POSIX分支。

### 10.3 真实Windows控制台PTY观察

入口：`.venv/Scripts/python.exe tests/manual_context_smoke.py --terminal`。本机无tmux，采用原生Windows控制台PTY，**不是headless Pilot冒充真实终端**；字体/鼠标滚动等具体桌面外观仍可由用户复核。

- 临时project/home、本地stdio MCP和fake模型启动：显示1个MCP、8个注册工具；DEFAULT可见7个，PLAN可见4个且无MCP。未加载真实配置、密钥或生产MCP。
- /compact显示archiving/summarizing，观察到completed（估算57941→15937），返回Ready并显示合成usage。过程中未出现内部草稿。
- 实际read_file完成后逐字显示续答；写入临时sample.txt出现原四选审批，按1只批准本次后完成。PLAN提问正常，输入/compact作为该问题的文本答案接纳，没有排队手动摘要。
- 旧版本观察中发现提交/compact后命令自身仍留在输入框，已修正为只清除命令本身，不清除不同的未提交草稿；headless草稿/焦点断言及后续新PTY样本通过。
- Esc取消摘要后显示COMPACTION_CANCELLED并恢复Ready，随后普通对话仍可完成。Ctrl+C在慢摘要期间同样观察到cancelled且恢复Ready；/exit可在摘要期间退出，/quit空闲退出，Ctrl+D与空闲Ctrl+C也已退出。
- 4个自有临时样本均保留资料并明确提示，不自动恢复/清理。后两次退出报告自有MCP收尾“已确认”，Host退出码1（受管回收），应用退出码0；不称为服务主动正常退出或副作用回滚。
- 未操作用户原有终端会话或删除用户资料；工具/摘要成功、取消、已发生用量是不同事实。

### 10.4 审核边界

开发交付可审核，不把审批当作收费授权。真实模型/真实供应商摘要与续跑**未运行、待单独费用授权**；POSIX、当前不能创建的原生符号链接及用户桌面具体外观保留待验。Checklist对应行不冒充全面通过。真实模型--live入口默认不加载凭据，必须明确域名/协议/模型/上限并输入YES后才可能读取选定配置；没有使用此入口发真实请求。

### 10.5 收尾复核修正

收尾发现：动态提醒虽然内容不变，在实际wire中会从最后一条用户消息移动至新尾部，使直接匹配整个wire前缀的锚点过早失效。已在PreparedRequest保存**脱敏后的纯历史投影**用于前缀核验，实际固定/消息完整投影仍用于全部体积计数；增量取完整实际投影字符差额，因此不漏计或重加动态提醒。稳定/环境/提醒/工具变化仍由fixed_digest失效，历史变化仍使前缀核验失败。

普通完整工具响应同样可建立锚点；不完整/失败主请求退回全投影，摘要用量不影响主锚点。未提交候选的预算估算使用纯检查，不提前修改当前锚点。三协议分别验证“提醒只移动可复用、提醒内容改变失效”，现有实际body与原生负载回放断言保留。此修正不增加配置或依赖，仍在原批准生产范围；共实际使用45个批准生产文件，无范围外生产修改。

修正后统一完整回归已完成，最终数字见下一节；不是将前面分组计数相加。

### 10.6 最终交付快照

- 最后一次统一命令：`.venv/Scripts/python.exe -m pytest -q -rs`。**932 passed、6 skipped，273.02秒（4分33秒）**，938个用例全部在本次收集。无失败，无新依赖，无真实服务/模型费用；skip原因同10.2，不计通过。
- 最终生产代码及所有新增测试均已纳入本次。此前每次单项修复的数字只作为历史证据，不与最终数字累加。
- 最终 `python -m compileall -q src/weizhcode tests`、`git -c core.safecrlf=false diff --check`均退出0；新增源码/测试/文档用rg查行尾空白无命中。
- Checklist本机可验证项61/67已登记；剩余6项P01、P03、U02、L01–L03明确待环境/桌面复核/费用授权。这6项不是pytest的6个skip清单，两者不要混淆。
- 生产范围45个文件，均在批准的48项内。未读取/修改真实模型/MCP/权限/信任配置、.weizhcode-test/或hello.txt，未清理用户数据；未commit/push。
- 开发与本机验证完成，交给用户审核；不声称POSIX、不可创建的原生符号链接、具体桌面视觉及真实供应商收费场景已验证。
