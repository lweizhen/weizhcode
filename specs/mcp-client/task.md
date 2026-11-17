# weizhCode MCP 客户端 Tasks

> 状态：四份文档均已获用户明确批准；按Task实现中，首批基础代码与定向回归已完成。完整MCP尚未接入。
> 日期：2026-11-17。Task 批准后下一步仅生成 Checklist；四份文档全部批准后才进入实现。
> 以下命令、用例名和通过条件是未来实施安排，不是已执行证据。

## 1. 执行与证据约定

项目根为 D:/STUDY/weizhcode-python/。文件编号在第 2 节精确映射至完整路径，不代表目录通配授权；V01～V24 仅指表中24个明确文件。任务标题、依赖、步骤、验证与需求映射均需一起执行，不能只完成代码而忽略验证。

- 按编号顺序执行是合法拓扑顺序；依赖列是完整的直接前置约束，不能仅凭分组概览跳过。T15/T16 是不同平台实现，两者实现完毕后 T17 可继续，当前平台不能执行的原生验证另记缺口。
- 每一步以约2～5分钟的局部修改/核对为目标，不把估时当证据。某一步明显更大时拆成同一任务下的 a/b/c 小步骤并登记验证；不得因此删去设计或增加未批准行为。
- 实施前先记录基线；每项新增测试必须能被所列 -k 选择器收集。若最终组织改名，同步记录真实命令，收集0项、skip或仅导入成功都不能冒充对应行为通过。
- 中间验证以定向测试为准，过渡阶段不虚称全量始终留绿；接入后再跑完整回归。发现真实失败先修后重跑，不能删旧断言、把未知工具放行或默认BYPASS来换通过。
- 测试仅使用临时root/home、合成秘密、fake模型、本地最小stdio/回环HTTP Server。所有控制/Server进程、日志、样本和信任记录均归测试拥有并受管收尾。
- 不读取、编辑、清理或暂存用户 .weizhcode-test/、hello.txt、真实 weizhcode.yaml、真实用户权限/MCP/信任文件。实际实现时重新检查工作区，不凭本次观察假定文件始终未变。
- 不调用生产MCP端点或收费LLM，不自动下载/安装Server，不把危险命令交shell。SDK依赖安装属于四文档批准后的实施步骤，若主机权限/网络需额外批准则按实际请求，不静默绕过。
- SDK契约、纯逻辑、原生进程/传输、Pilot、真实PowerShell、真实模型分列证据。Windows原生通过不等于POSIX通过；上一章未验项不被本章追认为通过。
- 逻辑相关且验证通过的组作本地提交，只暂存明确本章文件；不使用全量暂存掺入用户数据，不自动推送GitHub。若阶段文档尚未跟踪，只在明确本章提交中包含它们。
- 本章核心承诺不变：官方固定SDK、每Server受管Host、两层配置、持久启动信任防伪、默认工具审批、PLAN禁MCP、无自动重连/重放；若实施无法满足，报告差异并重批相关文档。

## 2. 文件清单

### 2.1 生产代码与依赖

| 编号 | 操作 | 完整路径 | 职责 |
|---|---|---|---|
| P01 | 修改 | D:/STUDY/weizhcode-python/pyproject.toml | 固定SDK依赖，保留Python最低版本 |
| P02 | 更新锁 | D:/STUDY/weizhcode-python/uv.lock | 只更新新增SDK所需依赖 |
| P03 | 新增 | D:/STUDY/weizhcode-python/src/weizhcode/mcp/__init__.py | 轻量公共入口 |
| P04 | 新增 | D:/STUDY/weizhcode-python/src/weizhcode/mcp/contracts.py | 来源、身份、信任、状态、发现与关闭契约 |
| P05 | 新增 | D:/STUDY/weizhcode-python/src/weizhcode/mcp/limits.py | 固定阈值与期限 |
| P06 | 新增 | D:/STUDY/weizhcode-python/src/weizhcode/mcp/config.py | 安全加载、覆盖、展开与校验 |
| P07 | 新增 | D:/STUDY/weizhcode-python/src/weizhcode/mcp/control.py | 固定控制进程客户端/取消 |
| P08 | 新增 | D:/STUDY/weizhcode-python/src/weizhcode/mcp/control_worker.py | 仅配置与信任操作 |
| P09 | 新增 | D:/STUDY/weizhcode-python/src/weizhcode/mcp/trust.py | 认证指纹、私有key与事务保存 |
| P10 | 新增 | D:/STUDY/weizhcode-python/src/weizhcode/mcp/startup.py | 真实启动选择与票据 |
| P12 | 新增 | D:/STUDY/weizhcode-python/src/weizhcode/mcp/process.py | 受管Host、内部协议与所有权 |
| P13 | 新增 | D:/STUDY/weizhcode-python/src/weizhcode/mcp/host_worker.py | 单owner官方SDK会话 |
| P14 | 新增 | D:/STUDY/weizhcode-python/src/weizhcode/mcp/http.py | HTTP来源/重放/流预算门禁 |
| P15 | 新增 | D:/STUDY/weizhcode-python/src/weizhcode/mcp/diagnostics.py | 匿名stderr管道、分片脱敏、限流 |
| P16 | 新增 | D:/STUDY/weizhcode-python/src/weizhcode/mcp/manager.py | 并发启动、快照、复用与关闭 |
| P17 | 新增 | D:/STUDY/weizhcode-python/src/weizhcode/mcp/tool.py | 工具和结果适配 |
| P18 | 新增 | D:/STUDY/weizhcode-python/src/weizhcode/bootstrap.py | 统一应用装配及生命周期 |
| P20 | 修改 | D:/STUDY/weizhcode-python/src/weizhcode/models.py | external类型及必要通用契约 |
| P21 | 修改 | D:/STUDY/weizhcode-python/src/weizhcode/tools/base.py | 兼容原Tool的外部异步扩展 |
| P22 | 修改 | D:/STUDY/weizhcode-python/src/weizhcode/tools/registry.py | 可信身份登记及模式可见性 |
| P23 | 修改 | D:/STUDY/weizhcode-python/src/weizhcode/tools/executor.py | 原门禁之后的外部执行/结果保存 |
| P24 | 修改 | D:/STUDY/weizhcode-python/src/weizhcode/tools/process.py | WindowsJob查询与有限复用 |
| P25 | 修改 | D:/STUDY/weizhcode-python/src/weizhcode/permissions/types.py | 外部身份、规则kind与默认兼容 |
| P26 | 修改 | D:/STUDY/weizhcode-python/src/weizhcode/permissions/rules.py | MCP精确/Server规则 |
| P27 | 修改 | D:/STUDY/weizhcode-python/src/weizhcode/permissions/engine.py | 外部EXEC身份与复核 |
| P28 | 修改 | D:/STUDY/weizhcode-python/src/weizhcode/permissions/settings.py | 通用安全加载复用与新规则往返 |
| P29 | 修改 | D:/STUDY/weizhcode-python/src/weizhcode/permissions/persist.py | 精确MCP许可合并/安全往返 |
| P30 | 修改 | D:/STUDY/weizhcode-python/src/weizhcode/permissions/worker_ops.py | 固定操作中外部target严格重建 |
| P31 | 修改 | D:/STUDY/weizhcode-python/src/weizhcode/permissions/io.py | 外部target与结果校验 |
| P32 | 修改 | D:/STUDY/weizhcode-python/src/weizhcode/approvals.py | 外部工具来源与完整授权范围 |
| P33 | 修改 | D:/STUDY/weizhcode-python/src/weizhcode/cli.py | 启动选择、同loop装配和finally |
| P34 | 修改 | D:/STUDY/weizhcode-python/src/weizhcode/redaction.py | 组合秘密集合，原行为保持 |
| P35 | 新增 | D:/STUDY/weizhcode-python/src/weizhcode/yaml_utils.py | Plan已要求提取的通用安全YAML辅助 |
| P36 | 修改 | D:/STUDY/weizhcode-python/src/weizhcode/turn_runner.py | 外部资源生命周期，原Loop保持 |
| P37 | 修改 | D:/STUDY/weizhcode-python/src/weizhcode/tui.py | 真实状态、审批及关闭接线 |

### 2.2 测试、fixture与观察入口

| 编号 | 操作 | 完整路径 | 职责 |
|---|---|---|---|
| V01 | 新增 | D:/STUDY/weizhcode-python/tests/test_mcp_process.py | SDK契约、控制/Host/原生进程 |
| V02 | 新增 | D:/STUDY/weizhcode-python/tests/test_mcp_config.py | 配置/变量/覆盖/预算 |
| V03 | 新增 | D:/STUDY/weizhcode-python/tests/test_mcp_tool.py | 工具契约、Schema、内容 |
| V04 | 新增 | D:/STUDY/weizhcode-python/tests/test_mcp_permissions.py | 规则/模式/真实许可 |
| V05 | 扩展 | D:/STUDY/weizhcode-python/tests/test_permission_settings.py | 原安全配置回归 |
| V06 | 扩展 | D:/STUDY/weizhcode-python/tests/test_redaction.py | 原分片脱敏/组合秘密回归 |
| V07 | 新增 | D:/STUDY/weizhcode-python/tests/test_mcp_trust.py | key/签名/保存/启动选择 |
| V08 | 新增 | D:/STUDY/weizhcode-python/tests/test_mcp_integration.py | 应用/Loop/三协议/入口保护 |
| V09 | 新增 | D:/STUDY/weizhcode-python/tests/test_mcp_http.py | 本地HTTP和来源/恢复策略 |
| V10 | 新增 | D:/STUDY/weizhcode-python/tests/fixtures/mcp_stdio_server.py | 临时最小stdio协议fixture |
| V11 | 新增 | D:/STUDY/weizhcode-python/tests/fixtures/mcp_http_server.py | 回环HTTP/SSE协议fixture |
| V12 | 新增 | D:/STUDY/weizhcode-python/tests/test_mcp_manager.py | 启动/快照/调用/清理 |
| V13 | 扩展 | D:/STUDY/weizhcode-python/tests/test_tool_registry.py | 原工具注册回归 |
| V14 | 扩展 | D:/STUDY/weizhcode-python/tests/test_permission_rules.py | 原规则语义回归 |
| V15 | 扩展 | D:/STUDY/weizhcode-python/tests/test_permission_persist.py | 原权限事务回归 |
| V16 | 新增 | D:/STUDY/weizhcode-python/tests/test_mcp_tui.py | 自动按键/状态/审批 |
| V17 | 扩展 | D:/STUDY/weizhcode-python/tests/test_tool_executor.py | 原工具执行和回收回归 |
| V18 | 扩展 | D:/STUDY/weizhcode-python/tests/test_tool_scheduler.py | 原读并发/混合屏障 |
| V19 | 扩展 | D:/STUDY/weizhcode-python/tests/test_cli.py | 无MCP及统一装配回归 |
| V20 | 扩展 | D:/STUDY/weizhcode-python/tests/test_turn_runner.py | 原Loop/历史/停止/取消回归 |
| V21 | 扩展 | D:/STUDY/weizhcode-python/tests/test_prompt_protocols.py | 三协议补充/前缀回归 |
| V22 | 扩展 | D:/STUDY/weizhcode-python/tests/test_cache_usage.py | 原缓存/用量回归 |
| V23 | 扩展 | D:/STUDY/weizhcode-python/tests/test_provider_events.py | 原流式事件与用量回归 |
| V24 | 新增 | D:/STUDY/weizhcode-python/tests/manual_mcp_smoke.py | 离线默认、终端观察、单独授权live |

既有未列作修改的测试仍运行全套回归，包括配置、会话、内置文件/命令/搜索、权限沙箱/黑名单/I/O、需求提问、TUI及协议测试。上述清单不授权重写Provider或改动未列旧测试来掩盖失败；若确有额外必要变更，先说明具体文件与原因。

### 2.3 示例、使用说明与阶段记录

| 编号 | 操作 | 完整路径 | 职责 |
|---|---|---|---|
| D01 | 新增 | D:/STUDY/weizhcode-python/docs/mcp/mcp-servers.example.yaml | 不含凭据的占位配置 |
| D02 | 修改 | D:/STUDY/weizhcode-python/.gitignore | 本系统local/key/固定临时名忽略 |
| D03 | 修改 | D:/STUDY/weizhcode-python/README.md | 使用方法与实际安全边界 |
| D04 | 登记状态 | D:/STUDY/weizhcode-python/specs/mcp-client/spec.md | 仅审批/阶段状态，需求不偷改 |
| D05 | 登记状态 | D:/STUDY/weizhcode-python/specs/mcp-client/plan.md | 仅审批状态，变更设计须重批 |
| D06 | 登记进度 | D:/STUDY/weizhcode-python/specs/mcp-client/task.md | 本文与实际证据 |
| D07 | 后续单独生成 | D:/STUDY/weizhcode-python/specs/mcp-client/checklist.md | Task批准后生成；实现后才勾选 |

通用 YAML 辅助的具体新文件 P35 是落实已批准 Plan 的安全加载提取要求，不改变权限文件语法。其余新增生产目录/文件均来自 Plan；SDK和第三方源码不直接修改。

## 3. 有序任务

### T01：记录基线与隔离边界

**文件：** D06。
**依赖：** 无；须在四份文档全部批准后执行。
**步骤：**

1. 记录实际 HEAD、工作区和依赖状态；用户未跟踪文件不读取、不暂存。
2. 在临时项目/home边界内运行既有离线测试，登记失败与平台跳过，禁止加载真实MCP配置。

**验证：** uv lock --check；uv run pytest -q -ra。
**通过条件：** 记录实际退出码/计数；不能复制上一阶段607项结果。
**对应需求：** AC24。

### T02：固定SDK依赖与兼容契约

**文件：** P01,P02,V01。
**依赖：** T01。
**步骤：**

1. 仅新增 mcp==1.30.0，保留 Python>=3.11 和其他直接依赖约束，记录锁中必要传递变化。
2. 核对已安装包元数据、ClientSession/两种传输入口、参数签名和握手式协议集合；不安装CLI extras，不联网Server。

**验证：** uv sync；uv lock --check；uv run pytest -q tests/test_mcp_process.py -k sdk_contract。
**通过条件：** SDK可导入、接口与Plan一致；不一致停止并报告，不能自行改大版本。
**对应需求：** AC07、AC08、AC24。

### T03：MCP不可变契约与预算

**文件：** P03,P04,P05,V01,V02。
**依赖：** T02。
**步骤：**

1. 定义配置/来源/警告/身份/generation/信任请求与票据/发现/状态/关闭DTO，完成深层可变隔离和敏感字段 repr 隐藏。
2. 将Plan 4.2每个阈值及协议兼容集合固定为具名常量；公共包轻量导出，禁止循环依赖。

**验证：** uv run pytest -q tests/test_mcp_process.py tests/test_mcp_config.py -k contract。
**通过条件：** DTO隔离、非法状态/值拒绝、预算边界和导入均有断言。
**对应需求：** AC03、AC11、AC25。

### T04：统一工具和权限扩展契约

**文件：** P20,P21,P25,V03,V04。
**依赖：** T03。
**步骤：**

1. ToolDefinition追加external类型、PermissionTarget追加外部身份、Rule追加kind默认值，原字段顺序/默认不变。
2. 定义外部异步执行扩展Protocol，保持原同步Tool可用；外部同步execute不得隐式建loop或发送请求。

**验证：** uv run pytest -q tests/test_mcp_tool.py tests/test_mcp_permissions.py -k contract。
**通过条件：** 原位置参数/内置模式兼容，序列化隔离，伪造外部身份不构成许可。
**对应需求：** AC12、AC24。

### T05：安全YAML读取与通用辅助

**文件：** P06,P35,P28,V02,V05。
**依赖：** T03。
**步骤：**

1. 将重复键/深度/节点/基本数据验证提取到yaml_utils，权限文件原结构与报错语义保持。
2. MCP配置有界读取常规文件，拒绝设备/FIFO/不明重定向；坏整层返回固定来源告警，不回显源码行。

**验证：** uv run pytest -q tests/test_mcp_config.py tests/test_permission_settings.py -k safe_load。
**通过条件：** 重复键、循环、复杂类型、超限及旧权限坏文件处理一致；原生链接缺口单列。
**对应需求：** AC02、AC25。

### T06：两层覆盖与来源遮蔽

**文件：** P06,V02。
**依赖：** T05。
**步骤：**

1. 构造用户/项目两个map，先按名称完整覆盖，保留来源；不做字段合并。
2. 文件缺失/null/空map为空；项目同名无效定义保留遮蔽，不在后续校验失败时回退用户定义。

**验证：** uv run pytest -q tests/test_mcp_config.py -k layers。
**通过条件：** 坏条目与坏整层降级不同，用户/项目各自生效，警告不虚称坏配置已禁用。
**对应需求：** AC01、AC02。

### T07：Server字段与启动目标校验

**文件：** P06,V02。
**依赖：** T06。
**步骤：**

1. 校验type、白名单字段、Server标识/长度/分隔符、argv/env/header类型与上限。
2. 校验HTTP(S)、userinfo/fragment/CRLF、保留协议头；Windows实际解析为bat/cmd也拒绝，禁止自动安装或shell拼接。

**验证：** uv run pytest -q tests/test_mcp_config.py -k fields。
**通过条件：** 合法两种配置通过；非法单项被隔离；未执行任何命令证明拦截。
**对应需求：** AC03、AC11。

### T08：变量展开与秘密集合

**文件：** P06,P34,V02,V06。
**依赖：** T07。
**步骤：**

1. 仅对最终采用的env/headers值单次展开，多个引用与空值可区分，不递归解释变量值。
2. 未定义变量跳过该Server；组合原值/展开值/认证片段与Provider秘密，配置原字节不变。

**验证：** uv run pytest -q tests/test_mcp_config.py tests/test_redaction.py -k mcp_expansion。
**通过条件：** 不展开command/args/url/名字；仅输出缺失变量名，不输出值。
**对应需求：** AC03、AC22。

### T09：配置规模与稳定裁剪

**文件：** P05,P06,V02。
**依赖：** T08。
**步骤：**

1. 覆盖256KiB文件、展开1MiB、各字段8192字符、128项与16Server限制的临界正反例。
2. 按名称稳定选择可启动Server，超限告警限流；不能以超限后的截断文件继续解析。

**验证：** uv run pytest -q tests/test_mcp_config.py -k limits。
**通过条件：** 边界值符合Plan，超限受控且不触发外部启动。
**对应需求：** AC25。

### T10：诊断管道与分片脱敏

**文件：** P15,P34,V06,V01。
**依赖：** T08。
**步骤：**

1. 为匿名stderr pipe建立持续drain、StreamingRedactor、控制符过滤和限流；不创建原始日志文件。
2. SDK日志转换为固定类别，已知秘密跨分片也不输出；超过16KiB仍drain丢弃防背压。

**验证：** uv run pytest -q tests/test_mcp_process.py tests/test_redaction.py -k diagnostics。
**通过条件：** 连续stderr、分片合成密钥、ANSI/markup、超量输出均受控，原模型流式脱敏回归保留。
**对应需求：** AC07、AC22、AC25。

### T11：固定控制进程的帧与归属

**文件：** P07,P08,P12,V01。
**依赖：** T03、T10。
**步骤：**

1. 实现ControlWorker固定操作白名单、随机请求ID、帧/队列预算，启动期间取消仍接管实际PID。
2. 控制进程不导出任意工具/shell/网络入口；Windows隐藏并接管Job，POSIX记录所有权。

**验证：** uv run pytest -q tests/test_mcp_process.py -k control_protocol。
**通过条件：** 错误type/ID/状态/超长帧拒绝，进程创建后取消无孤儿；没有连接Server。
**对应需求：** AC06、AC21。

### T12：配置加载控制入口

**文件：** P06,P07,P08,V01,V02。
**依赖：** T09、T11。
**步骤：**

1. 将load_mcp_config接到固定控制进程，传入临时root/home与受限所需环境，返回规范DTO。
2. 主进程严格验证来源、类型、预算和响应，签名密钥不作为结果返回；根不可确认则不启动MCP。

**验证：** uv run pytest -q tests/test_mcp_process.py tests/test_mcp_config.py -k control_config。
**通过条件：** 真实配置控制进程的成功/错误可观测，模型参数不能改变读取路径。
**对应需求：** AC01、AC02、AC03。

### T13：控制进程超时与清理

**文件：** P07,P08,V01。
**依赖：** T12。
**步骤：**

1. 所有固定操作共享单次5秒预算，并区分读取失败与保存提交未知。
2. 取消、超时、关闭及重复关闭均等待归属回收；临时资源仅按记录身份删除。

**验证：** uv run pytest -q -ra tests/test_mcp_process.py -k control_lifecycle。
**通过条件：** 原生挂起控制进程被终止；提交未知不假称未保存，不留后台写入。
**对应需求：** AC06、AC21。

### T14：信任规范化与认证指纹

**文件：** P09,P04,V07。
**依赖：** T03、T08。
**步骤：**

1. 实现项目真实身份、Server来源和完整有效定义的规范JSON，header名归一、map排序、args保序。
2. HMAC指纹与整条记录签名使用私有key、常量时间比较；不保存明文秘密，不接受裸SHA256或未知版本回退。

**验证：** uv run pytest -q tests/test_mcp_trust.py -k fingerprint。
**通过条件：** 更改项目/command/args/env/header/url或敏感展开值均失效；伪造项目记录不能授权。
**对应需求：** AC05、AC06。

### T15：POSIX私有密钥存取

**文件：** P09,P08,V07。
**依赖：** T13、T14。
**步骤：**

1. 实现随机32字节key独占创建，目录0700/文件0600及常规文件/无重定向核对。
2. 缺失/损坏/不安全权限视为不能复用信任；没有项目授权需求时不创建key。

**验证：** uv run pytest -q -ra tests/test_mcp_trust.py -k posix_key。
**通过条件：** 仅POSIX原生证据可记通过；Windows明确skip，不用纯替身冒充权限保护。
**对应需求：** AC05、AC06。

### T16：Windows用户密钥保护

**文件：** P09,P08,V07。
**依赖：** T13、T14。
**步骤：**

1. 实现当前用户DPAPI保护/解保护，固定用户目录和文件类型检查，不把key传Server或普通IPC结果。
2. 故障只返回固定码，坏key不覆盖后静默信任；无需求不创建文件。

**验证：** uv run pytest -q -ra tests/test_mcp_trust.py -k windows_key。
**通过条件：** Windows原生往返与合成秘密不落盘/不回显；另一平台保持未验。
**对应需求：** AC05、AC06。

### T17：信任记录读取与项目绑定

**文件：** P09,P08,V07。
**依赖：** T15、T16。
**步骤：**

1. 固定读取项目mcp-trust.local.json，校验大小/结构/签名/项目身份与每项定义指纹。
2. 缺失/坏签名/旧版本/不可确认重定向全部返回未信任，不接受仓库自带已信任标记。

**验证：** uv run pytest -q tests/test_mcp_trust.py -k trust_read。
**通过条件：** 拷贝到另一项目或只改秘密值后重问；DTO和错误无配置正文。
**对应需求：** AC05、AC06。

### T18：信任记录事务写入

**文件：** P09,P08,V07。
**依赖：** T17。
**步骤：**

1. 固定路径、父目录与临时位置复核，独占临时文件、flush/fsync、旧指纹冲突检测、原子替换。
2. 保留其他合法记录，不覆盖损坏或并发编辑文件；失败按资源身份清理。

**验证：** uv run pytest -q tests/test_mcp_trust.py -k atomic。
**通过条件：** open/write/fsync/replace故障、冲突与临时目标已存在均不损坏旧记录。
**对应需求：** AC05、AC06。

### T19：信任与密钥的Git保护

**文件：** P09,P08,V07。
**依赖：** T18。
**步骤：**

1. 只读Git探测已跟踪与忽略状态，命令不走用户shell，环境标记不能把探测导向其他仓库。
2. 仓库中未忽略/已跟踪/状态不明时不持久化；非Git目录按本地敏感文件保护，不偷偷改其他项目Git设置。

**验证：** uv run pytest -q tests/test_mcp_trust.py -k git_guard。
**通过条件：** 临时真实Git仓库中检查本地记录/临时名/key；原用户仓库和真实home不读不写。
**对应需求：** AC05。

### T20：信任保存失败与提交事实

**文件：** P07,P08,P09,V07,V01。
**依赖：** T18、T19。
**步骤：**

1. 明确未提交可将真实选择降为本次启动，显示未记住；替换后丢应答返回提交未知。
2. 保存取消/超时先停稳控制进程；提交未知不生成启动票据，不能声称回滚记录。

**验证：** uv run pytest -q tests/test_mcp_trust.py tests/test_mcp_process.py -k trust_commit。
**通过条件：** 逐阶段故障和替换后丢应答核对磁盘/进程/提示，未知时零Server启动。
**对应需求：** AC06、AC21。

### T21：信任Store固定公共入口

**文件：** P07,P08,P09,P04,V07。
**依赖：** T20。
**步骤：**

1. 实现inspect/remember/aclose，将配置快照与挑战绑定，不接受任意保存位置或签名数据。
2. 父进程校验TrustSnapshot/TrustSaveResult类型；取消与旧challenge不产生许可。

**验证：** uv run pytest -q tests/test_mcp_trust.py -k store。
**通过条件：** 真实受管Store可读写临时记录；父进程不会得到密钥，重复关闭安全。
**对应需求：** AC05、AC06。

### T22：真实启动选择与安全预览

**文件：** P10,P04,V07,V08。
**依赖：** T21。
**步骤：**

1. 实现终端1信任并记住/2跳过，默认跳过；仅启动前同步输入，非法/EOF/无TTY不信任。
2. 命令argv/url预览有界脱敏，说明启动代码/联网风险；Ctrl+C取消整个启动，不启动input后台线程。

**验证：** uv run pytest -q tests/test_mcp_trust.py tests/test_mcp_integration.py -k startup_prompt。
**通过条件：** 替身真实选择边界、无TTY、空/非法输入、取消和合成密钥覆盖，不把模型文本当选择。
**对应需求：** AC04、AC06、AC22。

### T23：启动票据与来源授权

**文件：** P10,P04,P09,V07,V08。
**依赖：** T22。
**步骤：**

1. 用户级有效定义直达票据，项目级仅有效持久信任或当前真实选择可生成generation绑定票据。
2. 所有选择完成后才允许连接；项目覆盖项不可继承用户信任，旧ID/旧定义/取消不生成票据。

**验证：** uv run pytest -q tests/test_mcp_trust.py tests/test_mcp_integration.py -k startup_authorization。
**通过条件：** 无许可时观察零进程/零HTTP请求；部分跳过不影响其他许可项。
**对应需求：** AC04、AC06。

### T24：Host启动与进程所有权

**文件：** P12,P13,P24,V01。
**依赖：** T11、T23。
**步骤：**

1. 启动固定应用Host并等待ready，发送connect前先建立WindowsJob或POSIX所有权；Job失败绝不释放connect。
2. 创建中取消接管真实子进程并回收；扩展WindowsJob可查询活动进程，不改变旧worker目的白名单。

**验证：** uv run pytest -q -ra tests/test_mcp_process.py -k host_creation。
**通过条件：** 真实Host无connect不启动Server；Job分配失败与创建取消无后续副作用。
**对应需求：** AC04、AC21。

### T25：Host IPC状态机与预算

**文件：** P12,P13,P04,V01。
**依赖：** T24。
**步骤：**

1. 实现connect/call/cancel/close输入和Plan规定输出的version/host_id/request_id/状态校验。
2. 单帧1MiB、队列32、目录分帧；重复/错ID/未知type/超限导致对应Host受控关闭。

**验证：** uv run pytest -q tests/test_mcp_process.py -k host_protocol。
**通过条件：** 错误内部消息不能调用工具、保存权限或伪造成功，外部文本不能冒充IPC。
**对应需求：** AC09、AC12、AC25。

### T26：SDK上下文单owner与关闭唤醒

**文件：** P13,V01。
**依赖：** T25。
**步骤：**

1. Host owner单任务持有并退出transport/ClientSession，输入任务只投递有界控制消息。
2. 调用任务取消不从其他Task退出AnyIO上下文；输入断开/close唤醒owner并正常收尾。

**验证：** uv run pytest -q tests/test_mcp_process.py -k owner_lifecycle。
**通过条件：** 进入/退出同owner，初始化异常及等待期间close不产生cancel-scope错配或悬挂任务。
**对应需求：** AC21。

### T27：stdio会话连接

**文件：** P13,P15,V01。
**依赖：** T26、T10。
**步骤：**

1. 接入固定版本stdio_client及参数、真实项目cwd、SDK基础环境加显式env，不继承Provider key或签名key。
2. stderr接匿名pipe持续drain；协议stdout仅由SDK读取，不写原始日志文件，不monkeypatch SDK私有函数。

**验证：** uv run pytest -q tests/test_mcp_process.py -k stdio_transport。
**通过条件：** 参数/工作根/环境实际接线可观测；无connect零外部进程。原生握手在T34验证。
**对应需求：** AC07、AC22。

### T28：HTTP专用client与来源门禁

**文件：** P14,V09。
**依赖：** T26。
**步骤：**

1. 构造显式HTTPX client、配置认证、TLS验证、trust_env=False及retries=0，通过SDK公共http_client入口接入。
2. 包装transport检查最终同源POST/DELETE、拒绝跨源/降级与不允许方法，禁止OAuth自动登录。

**验证：** uv run pytest -q tests/test_mcp_http.py -k origin。
**通过条件：** 合成认证不流向第二来源，配置受控headers生效，非法目标不发请求。
**对应需求：** AC08。

### T29：HTTP的JSON与请求SSE

**文件：** P14,P13,V09。
**依赖：** T28。
**步骤：**

1. 让SDK处理JSON响应及POST关联SSE，不将其误当独立推送全部禁止。
2. 正常同源重定向最多3跳，超限报错；通知/HTTP错误不误当请求结果。

**验证：** uv run pytest -q tests/test_mcp_http.py -k response_forms。
**通过条件：** 两种请求响应形式、初始化通知及HTTP状态正反例通过。
**对应需求：** AC08、AC09。

### T30：禁止HTTP恢复与副作用重放

**文件：** P14,V09。
**依赖：** T29。
**步骤：**

1. 独立GET/恢复请求在本地返回405，无实际GET联网；SDK恢复尝试不新建会话。
2. 非通知请求id重复POST拒绝；合法同源重定向关联同一链，不误判为工具重放。

**验证：** uv run pytest -q tests/test_mcp_http.py -k no_replay。
**通过条件：** 服务端请求计数证明GET为0、断流后调用POST未重发，无自动更换端点。
**对应需求：** AC20。

### T31：HTTP响应字节与清理预算

**文件：** P14,P05,V09。
**依赖：** T30。
**步骤：**

1. 在流解码边界逐块累计2MiB，JSON/SSE与压缩响应均计入，不只检查Content-Length。
2. 超量立即关闭响应并标记会话不可用，超时按剩余deadline而非分阶段重置。

**验证：** uv run pytest -q tests/test_mcp_http.py -k limits。
**通过条件：** 小分片、超限、异常正文、压缩内容均受控且客户端流已关闭。
**对应需求：** AC25、AC21。

### T32：最小原生stdio测试Server

**文件：** V10,V01。
**依赖：** T27。
**步骤：**

1. 新增只面向临时fixture的最小Server，可记录argv/env/cwd、分页、延迟、错误、取消及子进程状态。
2. 与SDK会话分离保存有界事件证据；程序默认不读取真实配置，不接触仓库文件或运行危险命令。

**验证：** uv run pytest -q tests/test_mcp_process.py -k fixture_stdio。
**通过条件：** fixture可独立启动/退出，记录只在tmp_path，避免仅靠stub声称真实协议通过。
**对应需求：** AC07、AC21。

### T33：最小回环HTTP测试Server

**文件：** V11,V09。
**依赖：** T31。
**步骤：**

1. 新增绑定127.0.0.1临时端口的fixture，支持初始化、分页、JSON/SSE、请求计数及合成headers核对。
2. 认证日志只保留测试用安全断言，不输出真实Token；关闭时回收服务及连接。

**验证：** uv run pytest -q tests/test_mcp_http.py -k fixture_http。
**通过条件：** fixture端口/任务正确收尾，不连接公网、不读取真实HTTP配置。
**对应需求：** AC08、AC21。

### T34：真实握手、版本与异步配对

**文件：** P13,V01,V09,V10,V11。
**依赖：** T32、T33。
**步骤：**

1. 使用官方SDK对本地两种Server完成initialize/initialized、版本检查与tools能力判断。
2. 抓取原生乱序响应/通知/未知id与额外能力请求；不启用sampling/roots/elicitation等回调。

**验证：** uv run pytest -q tests/test_mcp_process.py tests/test_mcp_http.py -k native_handshake。
**通过条件：** 合法版本成功；未知协议安全失败；响应ID正确配对，不额外调用LLM/本地工具。
**对应需求：** AC07、AC08、AC09。

### T35：分页发现与单Server总期限

**文件：** P13,P05,V01,V09。
**依赖：** T34。
**步骤：**

1. 遍历nextCursor直到结束，重复/非法/过长cursor以及64页/256工具/2MiB目录上限受控失败。
2. 从Host创建起共用30秒覆盖握手和所有页，全部成功才交目录；零工具/无工具能力与失败可区分。

**验证：** uv run pytest -q tests/test_mcp_process.py tests/test_mcp_http.py -k discovery。
**通过条件：** 实际多页与慢握手/慢末页测试，不留下失败Server半套工具。
**对应需求：** AC10、AC25。

### T36：名称与Schema适配校验

**文件：** P17,P05,V03。
**依赖：** T35。
**步骤：**

1. 生成不截断的mcp全名，校验分隔唯一/64长度/描述兜底，识别重复全名。
2. Schema按64KiB/深度16/4096节点、自包含object与Draft202012约束验证；含秘密/不支持引用则跳过，不删除约束。

**验证：** uv run pytest -q tests/test_mcp_tool.py -k definition。
**通过条件：** 不同Server同工具名隔离；坏工具不拖累合法项，required/enum/额外属性原意保持。
**对应需求：** AC11、AC25。

### T37：文本、结构化与非文本结果

**文件：** P17,P13,V03。
**依赖：** T36。
**步骤：**

1. 按顺序合并TextContent，无文本的structuredContent有界转JSON；已有文本不重复结构化数据。
2. 混合非文本标省略、纯非文本明确不支持、空结果明确无文本；isError保留远端错误优先级，不解引用资源。

**验证：** uv run pytest -q tests/test_mcp_tool.py -k result。
**通过条件：** 原调用ID与错误/截断元信息正确，不出现纯非文本空白成功或自动访问URI。
**对应需求：** AC17。

### T38：MCP Tool适配与同步保护

**文件：** P17,P21,V03。
**依赖：** T37、T04。
**步骤：**

1. 实现统一definition和纯prepare，read_only恒False、execution_kind为external，实际身份来自Manager。
2. 同步execute固定拒绝，execute_external委托Manager而非自行处理协议，不因只读提示并发。

**验证：** uv run pytest -q tests/test_mcp_tool.py -k adapter。
**通过条件：** 准备阶段零远端调用，同步入口不建loop；模拟readOnlyHint=True仍为非只读。
**对应需求：** AC12、AC16。

### T39：Manager并发启动与失败隔离

**文件：** P16,P12,P04,V12。
**依赖：** T23、T35、T38。
**步骤：**

1. 仅接受本次有效票据，并发创建最多16个Host，分别拥有启动deadline与清理结果。
2. 记录ready/零工具/skipped/failed状态，单项失败不取消其他Host；启动取消清理所有已拥有资源。

**验证：** uv run pytest -q tests/test_mcp_manager.py -k startup。
**通过条件：** 两个成功/失败/超时混合Server实际启动区间可重叠，失败项无残留半目录。
**对应需求：** AC10。

### T40：全局目录快照与来源身份

**文件：** P16,P17,P04,V12,V03。
**依赖：** T39。
**步骤：**

1. 按全名稳定排序、所有冲突项跳过、保护内置名并执行总256工具上限。
2. 生成只读McpToolIdentity目录和generation，发现完冻结，不消费tools/list变化刷新目录。

**验证：** uv run pytest -q tests/test_mcp_manager.py tests/test_mcp_tool.py -k directory。
**通过条件：** 相同输入不同响应先后得到相同快照；无伪造/覆盖/隐式动态注册。
**对应需求：** AC11、AC20。

### T41：Manager调用与连接缓存

**文件：** P16,P12,P13,V12。
**依赖：** T40。
**步骤：**

1. 通过identity/generation核对后复用对应Host，以远端原名/合法参数发送；调用期限含IPC，不每次重连。
2. 区分业务isError和传输失效，后者使Server unavailable；后续立即失败、其他Server不受影响。

**验证：** uv run pytest -q tests/test_mcp_manager.py -k call_cache。
**通过条件：** 多次调用只有一次连接/Server启动；断线后没有新connect或调用重放。
**对应需求：** AC16、AC18、AC20。

### T42：SDK取消与迟到结果隔离

**文件：** P12,P13,P16,V01,V12。
**依赖：** T41。
**步骤：**

1. 关联内部call与SDK操作，实际取消发适用通知；1秒协议收尾不能确认则关闭该Host、不重连。
2. 30秒超时失效处理；取消前已确认结果保留，迟到结果不能释放新请求，远端副作用不宣称回滚。

**验证：** uv run pytest -q tests/test_mcp_process.py tests/test_mcp_manager.py -k cancellation。
**通过条件：** 真实fixture抓取取消请求ID、原结果先后与下次调用状态，不仅断言Task.cancel。
**对应需求：** AC18、AC19、AC20。

### T43：正常关闭与共享5秒预算

**文件：** P16,P12,P13,P04,V12。
**依赖：** T42。
**步骤：**

1. 实现幂等aclose共享Future，并发通知所有Host，owner正常退出SDK/HTTP连接及诊断任务。
2. 多个Server共用5秒，零Server/零工具/启动失败/重复关闭有确定结果；HTTP适用终止尽力不保证DELETE必成功。

**验证：** uv run pytest -q tests/test_mcp_manager.py -k close_budget。
**通过条件：** 关闭不按Server数累加预算，能记录实际连接结束、close顺序和ShutdownReport。
**对应需求：** AC21。

### T44：强制回收与未确认报告

**文件：** P12,P24,P16,V01,V12。
**依赖：** T43、T24。
**步骤：**

1. 超出正常预算后并发进入额外2秒的Job/自有后代回收并复核，不只停止等待。
2. 回收失败返回clean=False及Server标识，保留已确认工具结果；不把OS/另一平台能力写成已验证。

**验证：** uv run pytest -q -ra tests/test_mcp_process.py tests/test_mcp_manager.py -k forced_close。
**通过条件：** 原生PID/Job活动进程和fixture后代实际退出；失败注入报告准确，不遗留有主后台任务。
**对应需求：** AC21。

### T45：Registry外部可信登记

**文件：** P22,V13,V03。
**依赖：** T40、T38。
**步骤：**

1. 新增register_external和只读identity查询，核对Adapter类型、generation、来源映射与同对象绑定。
2. 普通register禁止自带external绕过；definitions_for_mode只加已登记外部项，PLAN仍只有原三个读工具与提问。

**验证：** uv run pytest -q tests/test_mcp_tool.py tests/test_tool_registry.py -k external_registry。
**通过条件：** 伪造前缀/任意对象不授予执行权，原工具定义与排序/验证保持。
**对应需求：** AC11、AC12、AC15。

### T46：MCP规则语法与去重

**文件：** P25,P26,V04,V14。
**依赖：** T04。
**步骤：**

1. 增加mcp_exact/mcp_server规则kind，只支持完整名与单Server末尾星号；拒绝跨Server/任意星号/括号参数语法。
2. MCP大小写敏感、与builtin rule_key隔离；不改变原路径/命令规则转义及Windows语义。

**验证：** uv run pytest -q tests/test_mcp_permissions.py tests/test_permission_rules.py -k mcp_rules。
**通过条件：** 合法精确/组规则与非法样例全覆盖，旧规则回归通过。
**对应需求：** AC13。

### T47：MCP规则匹配与精确授权

**文件：** P26,V04。
**依赖：** T45、T46。
**步骤：**

1. 同层deny优先、会话>本地>项目>用户，精确工具身份不绑定args/path/cwd。
2. exact_rule仅生成完整名，不产生Server通配；未连接Server的规则可加载但不创造工具。

**验证：** uv run pytest -q tests/test_mcp_permissions.py -k rule_matching。
**通过条件：** 不同Server/大小写/工具参数对照命中准确；内置名不被MCP规则匹配。
**对应需求：** AC13、AC14。

### T48：外部规则持久化往返

**文件：** P28,P29,P30,P31,V04,V05,V15。
**依赖：** T47。
**步骤：**

1. 更新权限target固定序列化与严格重建，MCP规则能在SafeLoader/merge/save/reload中往返。
2. 保留原权限文件路径/目的白名单、冲突/失败/提交未知契约；信任记录不得混成权限记录。

**验证：** uv run pytest -q tests/test_mcp_permissions.py tests/test_permission_settings.py tests/test_permission_persist.py -k mcp_persist。
**通过条件：** 精确名保存后重启复用，原deny/模式/扩展数据保留，不扩权或回显参数秘密。
**对应需求：** AC14。

### T49：Engine外部身份与四档裁决

**文件：** P27,P25,V04。
**依赖：** T45、T47、T48。
**步骤：**

1. 注入只读可信身份解析器，外部EXEC路径和原内置六工具分支严格区分，未知仍拒绝。
2. PLAN硬拒；DEFAULT/ACCEPT EDITS无规则Ask；BYPASS仍遵守deny及身份/根检查，不对远端path/command假做内置围栏。

**验证：** uv run pytest -q tests/test_mcp_permissions.py -k engine_matrix。
**通过条件：** 模式×规则×只读提示矩阵、伪造工具和原内置黑名单/文件围栏全部有计数断言。
**对应需求：** AC12、AC13、AC15。

### T50：审批接纳前后的身份复核

**文件：** P27,P16,V04。
**依赖：** T49。
**步骤：**

1. accept/recheck核对项目根、目录对象、generation与取消状态；未知/旧代次不能沿用旧许可。
2. 目录保留但会话失效让Manager返回不可用，不把它误改UNKNOWN_TOOL或自动恢复连接。

**验证：** uv run pytest -q tests/test_mcp_permissions.py -k identity_recheck。
**通过条件：** 等待审批时身份变化/根变化/同tick取消零调用，合法同身份可继续。
**对应需求：** AC12、AC19、AC20。

### T51：四选工具审批范围提示

**文件：** P32,V04,V16。
**依赖：** T50。
**步骤：**

1. ApprovalBroker按external身份展示Server/工具/参数安全预览，明确本会话/永久许可覆盖后续不同参数。
2. 保持四个枚举选择、run/approval ID、断开取消与旧选择失活；不接受模型伪批准或启动信任输入。

**验证：** uv run pytest -q tests/test_mcp_permissions.py tests/test_approvals.py -k mcp_approval。
**通过条件：** 本次/会话/永久/拒绝真实执行计数和保存事实正确，提示不误称路径或参数绑定。
**对应需求：** AC14、AC22。

### T52：Executor统一门禁后的external分支

**文件：** P23,P21,V04,V17。
**依赖：** T51、T41。
**步骤：**

1. 复用原验证→PLAN→Engine→审批→recheck，仅获准后纯prepare及execute_external，不创建普通worker。
2. 最后取消检查和execution_started标记、running事件、结果先保存再await清理；同步错误不裸抛堆栈。

**验证：** uv run pytest -q tests/test_mcp_permissions.py tests/test_tool_executor.py -k external_dispatch。
**通过条件：** 审批前远端调用0，错误/拒绝后可继续；已确认结果不被取消/清理覆盖。
**对应需求：** AC12、AC18、AC19。

### T53：串行屏障与混合结果保序

**文件：** P23,V18,V08。
**依赖：** T52。
**步骤：**

1. 保持所有MCP调用read_only=False，形成串行屏障；不因readOnlyHint并行。
2. 验证前后内置读批最大4并发、混合成功/拒绝/取消的ID和原序回灌，保留原调度算法。

**验证：** uv run pytest -q tests/test_mcp_integration.py tests/test_tool_scheduler.py -k mcp_barrier。
**通过条件：** 记录真实执行区间/并发峰值；拒绝项未执行，第二审批等待取消不重复前项。
**对应需求：** AC16、AC19。

### T54：Bootstrap配置与真实选择阶段

**文件：** P18,P10,P07,V08,V19。
**依赖：** T23、T48。
**步骤：**

1. 创建受控短生命周期配置/信任阶段，只输出DTO和固定票据；不带Task/Future/连接跨loop。
2. 先完成所有真实终端选择再开始任何Server连接；无配置和用户级-only不创建多余key/菜单。

**验证：** uv run pytest -q tests/test_mcp_integration.py tests/test_cli.py -k mcp_prepare。
**通过条件：** 无TTY/拒绝/取消无目标启动；纯聊天与合法其他项仍可运行。
**对应需求：** AC01、AC04、AC06、AC24。

### T55：CLI同长期loop装配

**文件：** P18,P33,V08,V19。
**依赖：** T54、T52、T53。
**步骤：**

1. 在单长期loop中依次Manager.start、可信目录注册、Engine/Executor/Runner、app.run_async并finally关闭。
2. Provider非法仍原启动错误；注入临时home/root和fake模型，不读取真实配置，App后备保持内置-only且安全。

**验证：** uv run pytest -q tests/test_mcp_integration.py tests/test_cli.py -k mcp_bootstrap。
**通过条件：** 真实本地连接在TUI期间可调用，不跨loop关闭、不重复装配或连接。
**对应需求：** AC24。

### T56：Runner与应用关闭协作

**文件：** P18,P36,P16,V08,V20。
**依赖：** T55、T43、T44。
**步骤：**

1. 退出先冻结新任务、取消审批/Runner并补齐历史，再统一关Host与控制进程；共享关闭Future幂等。
2. CLI finally和TUI退出可重复触发，无循环等待；只调用取消不代表历史已配对。

**验证：** uv run pytest -q tests/test_mcp_integration.py tests/test_turn_runner.py -k mcp_shutdown。
**通过条件：** 审批中/运行中/最终流期间关闭后实际任务与连接结束，不泄漏待处理结果。
**对应需求：** AC19、AC21。

### T57：TUI真实MCP状态与数量

**文件：** P37,P16,P04,V16。
**依赖：** T55。
**步骤：**

1. 注入只读状态快照替换0硬编码，区分ready/零工具/不可用、总注册与当前模式可见数。
2. 保留模式/模型/轮次/用量；失效改变可用计数但不修改工具快照，状态更新队列有界。

**验证：** uv run pytest -q tests/test_mcp_tui.py -k mcp_status。
**通过条件：** 无配置、零工具、多Server与失效的实际文本准确，旧TUI状态回归保留。
**对应需求：** AC22、AC24。

### T58：TUI四选、草稿与取消

**文件：** P37,P32,V16。
**依赖：** T57、T51、T56。
**步骤：**

1. 使用Pilot对MCP真实审批按1～4/方向/Enter，确认来源与授权范围文字，等待期间不改模式。
2. Esc/Ctrl+C/退出恢复草稿与焦点，历史菜单失活；启动信任与需求答案不混用。

**验证：** uv run pytest -q tests/test_mcp_tui.py -k mcp_interaction。
**通过条件：** 真实本地工具计数/样本状态/菜单与后续聊天一致，旧ID不能批准新请求。
**对应需求：** AC14、AC19、AC22。

### T59：三协议工具请求与原生历史

**文件：** V08,V21,V22,V23。
**依赖：** T56、T58。
**步骤：**

1. 捕获Anthropic/OpenAI/Qwen离线实际请求体，含合法MCP定义、结果ID与原生assistant负载。
2. 统计发现/等待审批不发LLM请求；缓存稳定前缀受工具快照变化正常影响，原用量/提醒轮次不改算法。

**验证：** uv run pytest -q tests/test_mcp_integration.py tests/test_prompt_protocols.py tests/test_cache_usage.py tests/test_provider_events.py -k mcp_protocol。
**通过条件：** 三种协议均保留原调用负载、配对和结算，不用Provider实现diff换绿。
**对应需求：** AC23。

### T60：离线Agent闭环与权限调整

**文件：** V08,V04,V10,V11。
**依赖：** T59。
**步骤：**

1. fake模型先请求MCP被拒操作再调整，用户替身选择后调本地原生Server，结果回灌并续答。
2. 覆盖PLAN前后端硬拒、/do、显式allow/deny、BYPASS仍不越启动信任和Server失效后的其他工具继续。

**验证：** uv run pytest -q tests/test_mcp_integration.py -k mcp_loop。
**通过条件：** 检查请求数/远端副作用/历史/最终文本；普通工具失败不等于Loop基础设施停止。
**对应需求：** AC13、AC15、AC18、AC20。

### T61：端到端秘密与伪授权注入

**文件：** V08,V16,V06,P15,P34。
**依赖：** T60。
**步骤：**

1. 合成秘密置于env/header/url query、分片stderr、异常、Schema/描述、参数预览与结果，实际匹配仍用合法原值。
2. 模型/用户文本/文件/工具结果中的假信任或批准不改变记录/规则；Server instructions不入系统补充。

**验证：** uv run pytest -q tests/test_mcp_integration.py tests/test_mcp_tui.py tests/test_redaction.py -k mcp_security。
**通过条件：** 抓取事件/UI/回灌/本地记录确认无明文与控制注入，未产生额外网络/模型/文件动作。
**对应需求：** AC06、AC12、AC22。

### T62：全预算与失败隔离回归

**文件：** V02,V03,V09,V12,V08。
**依赖：** T61。
**步骤：**

1. 覆盖Plan4.2每个大小/条数/深度/节点/分页/帧/诊断限额的等于及超一边界。
2. 缩短可注入时限观察30秒总预算逻辑及审批不占执行预算，不将SDK stdio缓冲说成内存沙箱。

**验证：** uv run pytest -q tests/test_mcp_config.py tests/test_mcp_tool.py tests/test_mcp_http.py tests/test_mcp_manager.py tests/test_mcp_integration.py -k mcp_budget。
**通过条件：** 每个选择器实际收集用例；超限只影响对应范围，截断标记与最终JSON合法。
**对应需求：** AC10、AC18、AC25。

### T63：原生生命周期专项补齐

**文件：** V01,V09,V12,V08。
**依赖：** T44、T62。
**步骤：**

1. 使用实际Host/子Server/协作式孙进程覆盖正常、创建中取消、初始化失败、超时、stderr压力与强制回收。
2. 分别记录Windows Job活动进程、PID结束与POSIX后代所有权证据；不可运行平台明确skip，不用stub顶替。

**验证：** uv run pytest -q -ra tests/test_mcp_process.py tests/test_mcp_http.py tests/test_mcp_manager.py tests/test_mcp_integration.py -k native_lifecycle。
**通过条件：** 实际进程/连接/任务收尾和ShutdownReport一致；OS拒绝报告不确定而非全部成功。
**对应需求：** AC21、AC25。

### T64：离线与可选线上手动入口

**文件：** V24,V08。
**依赖：** T63。
**步骤：**

1. manual_mcp_smoke默认/--help只离线说明；--terminal仅临时项目/home、本地fixture和fake模型，支持同样本重启。
2. --live单独展示服务/模型/操作范围/请求上限与费用，需真实确认；默认不读凭据/真实MCP配置、不联网生产，模式互斥。

**验证：** uv run python tests/manual_mcp_smoke.py --help；uv run python tests/manual_mcp_smoke.py；uv run pytest -q tests/test_mcp_integration.py -k manual_mcp_guards。
**通过条件：** 默认无付费/外部服务/真实文件访问，入口不自动npm/pip安装Server。
**对应需求：** AC25。

### T65：示例、忽略规则与风险说明

**文件：** D01,D02,D03,V02,V07。
**依赖：** T64。
**步骤：**

1. 添加占位stdio/HTTP示例与${VAR}认证；本仓库忽略信任local/key相关固定临时名，不忽略共享mcp配置/示例。
2. README说明启动信任/工具许可分离、规则范围、Plan禁用、用户级自动信任、秘密变化重问、拒绝cmd入口及不隔离远端行为。

**验证：** uv run pytest -q tests/test_mcp_config.py tests/test_mcp_trust.py -k example；git check-ignore -v --no-index .weizhcode/mcp-trust.local.json .weizhcode/.mcp-trust.fake.tmp docs/mcp/mcp-servers.example.yaml。
**通过条件：** 示例用合成环境解析，local/temp命中而共享示例不命中；不创建真实信任数据。
**对应需求：** AC05、AC22、AC25。

### T66：全量回归与范围核对

**文件：** P01,P02,V01～V24,D06。
**依赖：** T65。
**步骤：**

1. 运行全套新增/旧测试，真实失败修复后重跑；记录锁/编译/空白检查，不删除原断言或默认BYPASS。
2. 核对Provider、供应商六字段、内置业务Schema、旧阶段文档与用户文件未越界；未配置lint/mypy不临时安装伪报通过。

**验证：** uv lock --check；uv run python -m compileall -q src；uv run pytest -q -ra；git diff --check。
**通过条件：** 记录实际通过/失败/skip/退出码与依赖差异，不把上阶段结果当本次证据。
**对应需求：** AC23、AC24、AC25。

### T67：真实PowerShell交互验收

**文件：** V24,D06,D07。
**依赖：** T66。
**步骤：**

1. 用户运行离线--terminal观察首次/重启信任、配置变化重问、四选工具审批、Plan、计数、窄屏长预览与滚动。
2. 分别观察Esc/Ctrl+C、拒绝后继续及退出无残留；只使用临时本地fixture，不运行危险命令。

**验证：** 用户在真实PowerShell运行 uv run python tests/manual_mcp_smoke.py --terminal。
**通过条件：** 逐场景记录操作/观察与必要截图；未开展则待验，Pilot不能替代。
**对应需求：** AC04、AC05、AC14、AC19、AC21、AC22、AC25。

### T68：可选真实模型与外部服务验收

**文件：** V24,D06,D07。
**依赖：** T66。
**步骤：**

1. 另行确认具体域名/协议/模型、工具操作、请求上限及费用；没有明确授权不启动--live。
2. 只在批准范围验证真实工具调用/审批/拒绝回灌，不自动轮换服务或重试副作用；无配置协议记未测。

**验证：** 获单独确认后运行 uv run python tests/manual_mcp_smoke.py --live。
**通过条件：** 记录脱敏真实证据；无授权则待验，不阻塞离线报告、不冒充三家实测。
**对应需求：** AC18、AC23、AC25。

### T69：验收映射与本地交付记录

**文件：** D04,D05,D06,D07。
**依赖：** T66。
**步骤：**

1. 按AC01～AC25汇总实际证据；Task/Checklist如实区分离线、原生、真实终端、真实API、平台缺口。
2. 若T67/T68已开展纳入结果，未开展保持待验；核对明确本章文件再本地提交，不自动推送或掺入用户文件。

**验证：** 核对阶段记录；git diff --check；git status --short。
**通过条件：** 仅已验证项标完成；交付不把汇总完成当整章全验收，说明剩余风险与启动方式。
**对应需求：** AC24、AC25。

## 4. 执行顺序与本地提交分组

默认逐项 T01 → T02 → … → T69。T67/T68有额外现场/授权条件，未执行不阻止T69如实汇总；T69不能把这两个待验项标完成。纯逻辑/平台分支可按依赖调整顺序，但本次不安排并行子代理，也不隐式授权额外人员操作。

| 组 | 任务范围 | 提交边界与阶段验证 |
|---|---|---|
| G1 | T01～T10 | SDK/契约/配置/脱敏；原YAML/脱敏回归保留，源文件可导入 |
| G2 | T11～T23 | 固定ControlWorker、信任key/签名/事务/启动选择；尚不启动外部Server |
| G3 | T24～T35 | Host/两种传输/原生fixture/握手/分页；已有进程归属与期限证据 |
| G4 | T36～T44 | 工具/结果、Manager启动/复用/取消/退出；单Server失败隔离可运行 |
| G5 | T45～T53 | Registry/规则/Engine/四选/Executor/串行屏障；统一门禁无绕过 |
| G6 | T54～T63 | 应用/CLI/Runner/TUI/三协议/安全/规模/原生生命周期集成 |
| G7 | T64～T69 | 手动入口、示例与说明、全回归及真实验收记录；未验保留 |

组内可按更小的逻辑单元提交；没有验证前不得为凑提交标绿。进度登记包括实际提交哈希与未推送状态，关闭不确定、平台缺口和保存未知不是可忽略日志。

## 5. 需求覆盖与验证索引

### 5.1 Spec验收覆盖

以下映射是计划覆盖，不是通过证据；每条AC有多个条件时，不能只测其中一个条件就宣称整条通过。

| Spec验收 | 对应任务 |
|---|---|
| AC01 | T06、T12、T54 |
| AC02 | T05、T06、T12 |
| AC03 | T03、T07、T08、T12 |
| AC04 | T22、T23、T24、T54、T67 |
| AC05 | T14、T15、T16、T17、T18、T19、T21、T65、T67 |
| AC06 | T11、T13、T14、T15、T16、T17、T18、T20、T21、T22、T23、T54、T61 |
| AC07 | T02、T10、T27、T32、T34 |
| AC08 | T02、T28、T29、T33、T34 |
| AC09 | T25、T29、T34 |
| AC10 | T35、T39、T62 |
| AC11 | T03、T07、T36、T40、T45 |
| AC12 | T04、T25、T38、T45、T49、T50、T52、T61 |
| AC13 | T46、T47、T49、T60 |
| AC14 | T47、T48、T51、T58、T67 |
| AC15 | T45、T49、T60 |
| AC16 | T38、T41、T53 |
| AC17 | T37 |
| AC18 | T41、T42、T52、T60、T62、T68 |
| AC19 | T42、T50、T52、T53、T56、T58、T67 |
| AC20 | T30、T40、T41、T42、T50、T60 |
| AC21 | T11、T13、T20、T24、T26、T31、T32、T33、T43、T44、T56、T63、T67 |
| AC22 | T08、T10、T22、T27、T51、T57、T58、T61、T65、T67 |
| AC23 | T59、T66、T68 |
| AC24 | T01、T02、T04、T54、T55、T57、T66、T69 |
| AC25 | T03、T05、T09、T10、T25、T31、T35、T36、T62、T63、T64、T65、T66、T67、T68、T69 |

### 5.2 已批准关键约束的执行锚点

| 约束 | 必须验证的任务 |
|---|---|
| 无凭据/真实配置开发隔离、无配置零外部启动 | T01、T12、T23、T54、T55、T64 |
| 固定SDK及握手兼容面、不照搬最新版接口 | T02、T26～T35 |
| 配置完整覆盖和同名坏定义不回退 | T05～T09、T12 |
| 私有key认证信任、秘密变化重问、Git保护 | T14～T23、T61、T65 |
| 审批前零远端调用、只读提示不放行、PLAN硬拒 | T38、T45～T52、T60 |
| HTTP正常POST SSE与禁独立GET/重放并存 | T28～T35、T41～T42 |
| 统一结果预算与原调用ID，非文本不假成功 | T36～T42、T52、T62 |
| SDK上下文同owner、创建取消与实际进程回收 | T11～T13、T24～T27、T42～T44、T56、T63 |
| 五秒正常/两秒强制是预算，不伪称OS硬保证 | T43～T44、T63、T69 |
| 全三协议离线请求、原生负载/缓存/用量保持 | T59、T66 |
| TUI自动、真实PowerShell、付费API不混记 | T57～T58、T64、T67～T69 |

### 5.3 命令与平台注意事项

- 所有任务命令从项目根执行；分号仅表示文档中多个独立验证命令，不要求连成一条脚本。
- 测试选择器是约定标签，新增函数/参数ID必须包含对应关键词，测试输出记录实际收集数。若借助有界替身缩短30秒/5秒窗口，仍保留真实进程/本地服务的退出证据。
- Git探测测试只针对临时仓库，忽略验证使用虚拟路径参数，不创建真实key/许可。对未跟踪的新文件另检查实际文本/尾随空白，不能仅因git diff未列出就声称检查过。
- 进程测试受主机限制时申请合适执行权限；无法运行的另一平台保留待验。不得删除POSIX/Windows专项或把skip计入通过。
- 默认手动入口和--terminal均不收费；--live的文档审批不等于服务/模型费用授权。只有T68单独确认后才能运行。

## 6. 进度与实际证据登记

2026-11-17开始实施；下表只标记实际范围。依赖安装与基础代码不代表启动信任/连接/工具接入完成；未运行的原生、平台和真实API项目保持待验。

| 任务 | 当前状态 | 实际证据 |
|---|---|---|
| T01 | 基线已记录，有失败 | HEAD 94a0548；原锁32包校验通过。初次全套606 passed、1 failed、3 skipped，98.86s；失败为search_content准备事件顺序，未改断言，定向3 passed/1.98s；首次受限uv缓存报权限错误，已改用正常用户缓存。 |
| T02 | 已完成 | uv sync安装mcp==1.30.0及必要依赖，锁50包；真实签名/四版本与Plan一致。test_sdk_contract通过；未启动Server。 |
| T03 | 部分完成 | 配置/身份/状态/信任基础DTO与限额已落地，隔离/敏感repr测试通过；完整发现契约、启动票据校验随接入继续，不能标全完成。 |
| T04 | 契约部分完成 | external类型/Protocol、PermissionTarget尾字段、Rule.kind默认兼容已加入并测；外部同步执行保护的实际Adapter尚待T38。 |
| T05 | 部分完成 | 通用有界SafeLoader已提取，旧权限配置回归通过；常规文件/重定向/FIFO读取保护尚待控制进程落地，不标完整通过。 |
| T06 | 纯解析完成 | test_layers覆盖整条覆盖、来源、坏项目条目遮蔽与空层；生产固定读取入口未接入。 |
| T07 | 字段解析完成 | stdio/http字段/URL/header类型及Windows脚本解析拒绝测试通过；真实Host前启动检查仍待T24～T27。 |
| T08 | 纯展开完成 | 多引用/空值/缺失/不递归/字面字段、秘密集合与原字节测试通过；统一应用redactor接线待后续。 |
| T09 | 部分验证 | 256KiB/16Server/8192字符/128参数边界通过；展开总1MiB及其他全预算组合仍待补测，不标完成。 |
| T10 | 部分完成 | 诊断收集/分片脱敏/持续drain/SDK日志固定码测试通过；尚未接匿名OS pipe或真实Server stderr，不冒充原生压力验证。 |
| T11 | 待实现/验证 | 尚未执行 |
| T12 | 待实现/验证 | 尚未执行 |
| T13 | 待实现/验证 | 尚未执行 |
| T14 | 待实现/验证 | 尚未执行 |
| T15 | 待实现/验证 | 尚未执行 |
| T16 | 待实现/验证 | 尚未执行 |
| T17 | 待实现/验证 | 尚未执行 |
| T18 | 待实现/验证 | 尚未执行 |
| T19 | 待实现/验证 | 尚未执行 |
| T20 | 待实现/验证 | 尚未执行 |
| T21 | 待实现/验证 | 尚未执行 |
| T22 | 待实现/验证 | 尚未执行 |
| T23 | 待实现/验证 | 尚未执行 |
| T24 | 待实现/验证 | 尚未执行 |
| T25 | 待实现/验证 | 尚未执行 |
| T26 | 待实现/验证 | 尚未执行 |
| T27 | 待实现/验证 | 尚未执行 |
| T28 | 待实现/验证 | 尚未执行 |
| T29 | 待实现/验证 | 尚未执行 |
| T30 | 待实现/验证 | 尚未执行 |
| T31 | 待实现/验证 | 尚未执行 |
| T32 | 待实现/验证 | 尚未执行 |
| T33 | 待实现/验证 | 尚未执行 |
| T34 | 待实现/验证 | 尚未执行 |
| T35 | 待实现/验证 | 尚未执行 |
| T36 | 待实现/验证 | 尚未执行 |
| T37 | 待实现/验证 | 尚未执行 |
| T38 | 待实现/验证 | 尚未执行 |
| T39 | 待实现/验证 | 尚未执行 |
| T40 | 待实现/验证 | 尚未执行 |
| T41 | 待实现/验证 | 尚未执行 |
| T42 | 待实现/验证 | 尚未执行 |
| T43 | 待实现/验证 | 尚未执行 |
| T44 | 待实现/验证 | 尚未执行 |
| T45 | 待实现/验证 | 尚未执行 |
| T46 | 待实现/验证 | 尚未执行 |
| T47 | 待实现/验证 | 尚未执行 |
| T48 | 待实现/验证 | 尚未执行 |
| T49 | 待实现/验证 | 尚未执行 |
| T50 | 待实现/验证 | 尚未执行 |
| T51 | 待实现/验证 | 尚未执行 |
| T52 | 待实现/验证 | 尚未执行 |
| T53 | 待实现/验证 | 尚未执行 |
| T54 | 待实现/验证 | 尚未执行 |
| T55 | 待实现/验证 | 尚未执行 |
| T56 | 待实现/验证 | 尚未执行 |
| T57 | 待实现/验证 | 尚未执行 |
| T58 | 待实现/验证 | 尚未执行 |
| T59 | 待实现/验证 | 尚未执行 |
| T60 | 待实现/验证 | 尚未执行 |
| T61 | 待实现/验证 | 尚未执行 |
| T62 | 待实现/验证 | 尚未执行 |
| T63 | 待实现/验证 | 尚未执行 |
| T64 | 待实现/验证 | 尚未执行 |
| T65 | 待实现/验证 | 尚未执行 |
| T66 | 待实现/验证 | 尚未执行 |
| T67 | 待真实终端观察 | 尚未执行 |
| T68 | 待单独授权/真实场景 | 尚未执行 |
| T69 | 待实现/验证 | 尚未执行 |

### 首批实际验证

- 定向：`uv run pytest -q -ra tests/test_mcp_process.py tests/test_mcp_config.py tests/test_mcp_tool.py tests/test_mcp_permissions.py tests/test_permission_settings.py tests/test_permission_rules.py tests/test_redaction.py` → **105 passed，4.81s**。
- `uv run python -m compileall -q src`、`uv lock --check`、`git diff --check`均退出0；锁文件由32增至50包，原其他直接依赖约束未改。
- 全量复跑 `uv run pytest -q -ra --tb=short` → **653 passed、3 skipped，112.80s，退出0**（两项原生目录链接权限跳过、一项POSIX专项）；无真实Server、生产HTTP、收费LLM或真实凭据读写。T11以后仍待实施，不因首组提交默认完成。

## 7. 审批与停止边界

Task共69项，生产/测试/文档66个明确文件条目。本次只生成本文并登记Plan批准状态，不执行文中的安装、开发、测试、Server启动、控制记录写入或Git提交命令。没有新增子代理任务。

用户批准Task后，下一步仅生成完整Checklist供单独审批。全部四份文档批准前不能进入实现。若SDK接口事实、原生进程所有权、DPAPI/权限保护、HTTP门禁或版本兼容性无法满足已批准Plan，先记录具体证据、提出差异并请求相关设计重批，不用删需求/静默换方案继续。

交付报告必须区分“实现与离线验证完成”和“整章全部验收通过”；未运行T67/T68或另一平台保留未验。历史权限系统等阶段文档不覆盖，用户数据与真实配置不纳入本章提交，未经明确请求不推送GitHub。
