# weizhCode 权限系统 Tasks

> 状态：四份文档均已获用户明确批准，实现已完成，离线回归已通过；未验项与证据见文末。
> 实际验证后才标完成，真实终端/模型未验项保留待验。
> 不升级依赖、不迁移 SDK、不改工具业务参数、不默认调用付费 API、不自动推送 GitHub。

## 1. 执行、文件与证据约定

工作根为 `D:/STUDY/weizhcode-python/`。文件清单使用完整路径；任务引用 P/V/D 编号，每个编号精确对应一个文件，不代表目录通配或授权顺带修改其他文件。

每项为一个聚焦工作单元，以约 2～5 分钟的局部改动/核对为目标；不把估计时间当作完成证据，耗时明显超出时继续拆小步骤，不能跳过验证。任务内新测试名称或参数 ID 包含验证命令列出的 `-k` 关键词。所有命令均在四文档批准后的实现阶段从项目根执行；文末登记实际运行结果，不把审批时的计划当作证据。

- 每项先完成局部实现和对应测试，运行指定验证再登记结果。中间只承诺对应定向测试留绿；全量回归在装配后统一验证，不为过渡接口假称整套测试始终已通过。
- 旧 `normal` 仅内部运行入口兼容；生产默认 DEFAULT。测试要写/执行命令时明确注入临时许可或选择 BYPASS，不以漏注入 Engine 绕过检查。
- 测试只使用临时项目、临时 home 和合成密钥。用户 `.weizhcode-test/`、真实供应商配置、真实用户全局权限文件及无关改动不读取、不覆盖、不暂存。
- 危险命令只作为纯判定数据或禁执行替身输入，绝不交给真实 shell。真实模型场景须另行展示服务/模型、请求范围和费用可能性并取得确认。
- 逐组定向验证后可作本地逻辑提交；只暂存明确属于本章的文件，不使用批量暂存掺入用户数据，不推送 GitHub。
- 保存实际命令、退出结果、跳过项及原因；离线替身、原生进程、TUI 自动测试、真实终端和真实 API 分开记证据。
- 需要改变已批准的行为或架构时，先提出差异并重新审批相关文档，不能在 Task 中暗中改设计。

## 2. 文件清单

### 2.1 生产代码

| 编号 | 操作 | 完整路径 | 职责 |
|---|---|---|---|
| P01 | 新增 | D:/STUDY/weizhcode-python/src/weizhcode/permissions/__init__.py | 轻量公共导出 |
| P02 | 新增 | D:/STUDY/weizhcode-python/src/weizhcode/permissions/types.py | 枚举、规则/目标/路径/保存契约 |
| P03 | 新增 | D:/STUDY/weizhcode-python/src/weizhcode/permissions/modes.py | 模式规范化、轮换与兜底 |
| P04 | 新增 | D:/STUDY/weizhcode-python/src/weizhcode/permissions/blacklist.py | 固定危险命令正则 |
| P05 | 新增 | D:/STUDY/weizhcode-python/src/weizhcode/permissions/sandbox.py | 统一根与路径解析、复核 |
| P06 | 新增 | D:/STUDY/weizhcode-python/src/weizhcode/permissions/rules.py | 友好名、模式、匹配、精确转义 |
| P07 | 新增 | D:/STUDY/weizhcode-python/src/weizhcode/permissions/settings.py | 安全 YAML 与三层加载 |
| P08 | 新增 | D:/STUDY/weizhcode-python/src/weizhcode/permissions/persist.py | 本地精确规则事务保存 |
| P09 | 新增 | D:/STUDY/weizhcode-python/src/weizhcode/permissions/io.py | 权限辅助进程归属与取消 |
| P10 | 新增 | D:/STUDY/weizhcode-python/src/weizhcode/permissions/worker_ops.py | 固定内部探测/保存处理 |
| P11 | 新增 | D:/STUDY/weizhcode-python/src/weizhcode/permissions/engine.py | 前四层、会话规则与接纳许可 |
| P12 | 新增 | D:/STUDY/weizhcode-python/src/weizhcode/approvals.py | 独立审批 Broker |
| P13 | 新增 | D:/STUDY/weizhcode-python/src/weizhcode/approval_ui.py | 内联四选菜单 |
| P14 | 修改 | D:/STUDY/weizhcode-python/src/weizhcode/models.py | 模式、审批事件、阶段、目标印记、拒绝状态 |
| P15 | 修改 | D:/STUDY/weizhcode-python/src/weizhcode/tools/executor.py | 准备前门禁、审批、复核、清理 |
| P16 | 修改 | D:/STUDY/weizhcode-python/src/weizhcode/tools/process.py | purpose/消息白名单、临时资源验证 |
| P17 | 修改 | D:/STUDY/weizhcode-python/src/weizhcode/tools/worker.py | 目的隔离、prepare/execute 复核 |
| P18 | 修改 | D:/STUDY/weizhcode-python/src/weizhcode/tools/base.py | 文件工具公共检查与错误映射 |
| P19 | 修改 | D:/STUDY/weizhcode-python/src/weizhcode/tools/file_utils.py | 路径一致、扫描/写入访问点围栏 |
| P20 | 修改 | D:/STUDY/weizhcode-python/src/weizhcode/tools/read_file.py | 读取前复核 |
| P21 | 修改 | D:/STUDY/weizhcode-python/src/weizhcode/tools/write_file.py | 写入复核及权限说明 |
| P22 | 修改 | D:/STUDY/weizhcode-python/src/weizhcode/tools/edit_file.py | 编辑复核及权限说明 |
| P23 | 修改 | D:/STUDY/weizhcode-python/src/weizhcode/tools/find_files.py | 搜索根围栏、跳过元数据 |
| P24 | 修改 | D:/STUDY/weizhcode-python/src/weizhcode/tools/search_content.py | 候选正文读取围栏 |
| P25 | 修改 | D:/STUDY/weizhcode-python/src/weizhcode/tools/search_utils.py | 遍历、文件链接、忽略文件边界 |
| P26 | 修改 | D:/STUDY/weizhcode-python/src/weizhcode/tools/run_command.py | 描述一致，不增加命令路径沙箱 |
| P27 | 修改 | D:/STUDY/weizhcode-python/src/weizhcode/tools/registry.py | 四档工具可见性 |
| P28 | 修改 | D:/STUDY/weizhcode-python/src/weizhcode/tool_scheduler.py | run_id、阶段、并发/保序 |
| P29 | 修改 | D:/STUDY/weizhcode-python/src/weizhcode/turn_runner.py | 模式、审批入口、历史与关闭 |
| P30 | 修改 | D:/STUDY/weizhcode-python/src/weizhcode/tui.py | 菜单状态、按键、状态栏、草稿 |
| P31 | 修改 | D:/STUDY/weizhcode-python/src/weizhcode/cli.py | 唯一引擎与真实根装配 |
| P32 | 修改 | D:/STUDY/weizhcode-python/src/weizhcode/prompting/modules.py | 稳定权限约定 |
| P33 | 修改 | D:/STUDY/weizhcode-python/src/weizhcode/prompting/contracts.py | permission 补充来源 |
| P34 | 修改 | D:/STUDY/weizhcode-python/src/weizhcode/prompting/reminders.py | 四档兼容及原 plan 节奏 |
| P35 | 修改 | D:/STUDY/weizhcode-python/src/weizhcode/prompting/builder.py | 每请求动态权限说明 |

### 2.2 测试与观察入口

| 编号 | 操作 | 完整路径 | 职责 |
|---|---|---|---|
| V01 | 新增 | D:/STUDY/weizhcode-python/tests/test_permission_blacklist.py | 多平台危险模式正反例 |
| V02 | 新增 | D:/STUDY/weizhcode-python/tests/test_permission_sandbox.py | 根、链接、缺失段、平台边界 |
| V03 | 新增 | D:/STUDY/weizhcode-python/tests/test_permission_rules.py | 规则解析/匹配/精确往返 |
| V04 | 新增 | D:/STUDY/weizhcode-python/tests/test_permission_settings.py | 安全加载、层级、默认模式 |
| V05 | 新增 | D:/STUDY/weizhcode-python/tests/test_permission_persist.py | 保存、数据保留、失败和提交事实 |
| V06 | 新增 | D:/STUDY/weizhcode-python/tests/test_permission_engine.py | 契约、矩阵、流水线、会话 |
| V07 | 新增 | D:/STUDY/weizhcode-python/tests/test_approvals.py | 单 pending、真实响应、取消竞态 |
| V08 | 新增 | D:/STUDY/weizhcode-python/tests/test_permission_io.py | 固定消息、原生辅助进程、清理 |
| V09 | 新增 | D:/STUDY/weizhcode-python/tests/test_permission_integration.py | Loop/三协议/显示/脱敏集成 |
| V10 | 新增 | D:/STUDY/weizhcode-python/tests/manual_permission_smoke.py | 默认离线、显式线上观察 |
| V11 | 修改 | D:/STUDY/weizhcode-python/tests/test_tool_executor.py | 直接入口、审批前零执行、原工具生命周期 |
| V12 | 修改 | D:/STUDY/weizhcode-python/tests/test_tool_scheduler.py | 并发批、混合结果、配对 |
| V13 | 修改 | D:/STUDY/weizhcode-python/tests/test_turn_runner.py | 模式、历史、循环停止和关闭 |
| V14 | 修改 | D:/STUDY/weizhcode-python/tests/test_tui.py | 模式、菜单、草稿、按键 |
| V15 | 修改 | D:/STUDY/weizhcode-python/tests/test_tool_tui.py | 工具行、结果、历史组件 |
| V16 | 修改 | D:/STUDY/weizhcode-python/tests/test_user_questions.py | 需求答案与批准分流 |
| V17 | 修改 | D:/STUDY/weizhcode-python/tests/test_search_tools.py | 搜索外链和忽略文件 |
| V18 | 修改 | D:/STUDY/weizhcode-python/tests/test_prompting.py | 四档动态补充、计划提醒 |
| V19 | 修改 | D:/STUDY/weizhcode-python/tests/test_prompt_protocols.py | 前缀稳定、三协议补充承载 |
| V20 | 修改 | D:/STUDY/weizhcode-python/tests/manual_tool_smoke.py | 临时样本许可接线 |
| V21 | 修改 | D:/STUDY/weizhcode-python/tests/manual_prompt_smoke.py | 观察入口与新参数兼容 |
| V22 | 修改 | D:/STUDY/weizhcode-python/tests/test_cli.py | CLI 装配/默认模式/无真实 API |
| V23 | 修改 | D:/STUDY/weizhcode-python/tests/test_file_tools.py | 直接文件工具围栏与原业务回归 |
| V24 | 修改 | D:/STUDY/weizhcode-python/tests/test_command_tool.py | 原命令业务与测试许可隔离 |
| V25 | 修改 | D:/STUDY/weizhcode-python/tests/test_tool_registry.py | 模式工具定义与身份 |

### 2.3 配置、说明与阶段记录

| 编号 | 操作 | 完整路径 | 职责 |
|---|---|---|---|
| D01 | 新增 | D:/STUDY/weizhcode-python/.weizhcode/settings.yaml.example | 三层权限示例，无密钥 |
| D02 | 修改 | D:/STUDY/weizhcode-python/.gitignore | 仅本地权限文件/本系统临时文件 |
| D03 | 修改 | D:/STUDY/weizhcode-python/README.md | 模式、授权范围、配置与风险 |
| D04 | 更新状态/证据 | D:/STUDY/weizhcode-python/specs/permission-system/spec.md | 只登记批准/最终阶段状态 |
| D05 | 更新状态/证据 | D:/STUDY/weizhcode-python/specs/permission-system/plan.md | 只登记批准/经确认的设计差异 |
| D06 | 更新进度 | D:/STUDY/weizhcode-python/specs/permission-system/task.md | 本文进度与实际验证 |
| D07 | 后续单独生成 | D:/STUDY/weizhcode-python/specs/permission-system/checklist.md | Task 批准后生成，开发后登记证据 |

三种 Provider、SSE、供应商配置和依赖锁不在计划修改范围。必要的测试数据扩展直接放入上述对应测试文件，不新增真实密钥或用户样本文件。

## 3. 有序任务

### T01：记录实现前基线与测试隔离边界

**文件：** D06（记录）；只读检查 P14～P31、V11～V25、pyproject.toml、uv.lock。
**依赖：** 无；须在四份文档批准后执行。
**步骤：**
1. 记录当时 HEAD、工作区改动及依赖锁状态，不把历史测试数当本次结果。
2. 运行现有离线测试，记录实际通过/失败/平台跳过；确认工具测试全部使用临时目标。
3. 为新增权限测试约定临时 home、临时根和合成密钥；不加载本机真实权限配置。
**验证：** `uv lock --check`、`uv run pytest -q -ra`；结果和环境限制原样记录，失败不跳过或删除旧断言。

### T02：权限枚举与轻量模块边界

**文件：** P01、P02、P03、V06。
**依赖：** T01。
**步骤：**
1. 定义 PermissionMode、Decision、Category、ApprovalChoice 的规范值。
2. 实现 parse_mode、normalize_runtime_mode、next_mode；仅运行入口接受旧 normal，配置不接受。
3. 公共包保持轻量，types 不导入 models/工具/UI；测试四档循环及非法值不放行。
**验证：** `uv run pytest -q tests/test_permission_engine.py -k mode_contract`；四档、大小写、normal 兼容与非法模式分支均有断言。

### T03：不可变目标、裁决、事件与拒绝结果契约

**文件：** P02、P14、V06、V07。
**依赖：** T02。
**步骤：**
1. 落地 RootIdentity、PathStamp、PermissionTarget、PermissionCheck、Rule、RuleSet、PermissionSettings、SettingsWarning、SaveResult；集合与嵌套输入不共享可变引用。
2. models 增加 ApprovalRequest、事件字段、checking/awaiting_approval 阶段及 PreparedOperation 末尾可选印记字段；保留旧位置参数含义。
3. 增加权限错误码到 denied 的映射，保留原 UNKNOWN/INVALID/TIMEOUT/CANCELLED 语义；未获许可 execution_started=False。
**验证：** `uv run pytest -q tests/test_permission_engine.py tests/test_approvals.py -k contract`；冻结/隔离、字段默认、序列化预算与错误分类通过。

### T04：模式兜底与工具可见性

**文件：** P03、P27、V06、V25、V16。
**依赖：** T03。
**步骤：**
1. 实现 DEFAULT/ACCEPT_EDITS/BYPASS 三类兜底，PLAN 写/命令明确硬拒，不交给 Ask。
2. 定义固定六工具身份及类别；三个非 plan 档提供六个 worker 工具，plan 提供三个读工具与 AskUserQuestion。
3. 未知身份不能靠 read_only=True 进入 READ；更新仅涉及可见性的旧模式断言。
**验证：** `uv run pytest -q tests/test_permission_engine.py tests/test_tool_registry.py tests/test_user_questions.py -k 'mode_matrix or mode_visibility or ask_question_modes'`。

### T05：规则语法解析

**文件：** P06、V03。
**依赖：** T03。
**步骤：**
1. 解析裸工具名或 Tool(pattern)，验证六个友好名和括号/转义，不误删括号内空白。
2. 实现字面 token 与未转义星号 token，其他反斜杠及问号/方括号按 Plan 字面语义处理。
3. 定义非法/空模式和路径模式边界；孤立 `.` 是搜索根标记，路径中嵌入的 `.`/`..` 段不接受。
**验证：** `uv run pytest -q tests/test_permission_rules.py -k parse`；嵌套括号、字面括号、空格/换行、非法工具和根标记有测试。

### T06：命令规则全串匹配

**文件：** P06、V03。
**依赖：** T05。
**步骤：**
1. 命令匹配保留大小写、前后空白与换行，星号可跨空格和换行，连续星号等价单星号。
2. 裸 Bash 匹配全部；精确命令不匹配相似前后缀，不做 shell 解析或 git 安全推断。
3. 对宽泛 git glob 覆盖复合命令保留行为测试，不能靠不真实的“仅 git 子命令”解释掩盖边界。
**验证：** `uv run pytest -q tests/test_permission_rules.py -k command_match`。

### T07：文件路径分段匹配

**文件：** P06、V03。
**依赖：** T05。
**步骤：**
1. 文件模式仅处理项目相对 slash 路径；星号段内，独立双星段跨零个或多个目录。
2. 使用有界分段匹配，Windows 文件路径遵循平台 normcase，命令不跟随折叠。
3. 验证根、隐藏文件、多级目录、绝对/盘符模式拒绝，以及 Read/Grep 规则互不代替。
**验证：** `uv run pytest -q tests/test_permission_rules.py -k path_match`；包含 `src/**`、`src/*`、零目录双星与相似前缀反例。

### T08：精确授权转义、往返与去重键

**文件：** P06、V03。
**依赖：** T06、T07。
**步骤：**
1. 实现 Plan 的 exact_rule(target)，转义星号、括号、反斜杠，不生成通配 token。
2. 命令键为工具＋完整 command；文件键为工具＋规范真实相对路径；不把 cwd 或内容偷偷加入授权键。
3. 用规范 token 去重；规则超限明确失败，不降为裸工具或更宽 glob。
**验证：** `uv run pytest -q tests/test_permission_rules.py -k exact_roundtrip`；相似不同目标不命中，命令与特殊字符路径可往返。

### T09：安全 YAML 验证与整文件降级

**文件：** P07、V04。
**依赖：** T08。
**步骤：**
1. 使用 SafeLoader 体系，拒绝重复键/非法标签/复杂键/循环数据；执行 256 KiB、1024 规则、8192 单条、深度 16 的既定限制。
2. 严格验证已知字段与全部规则，任一非法则整文件无效；保留可往返的未知顶层基本数据。
3. 缺失/空文件按空配置；异常仅输出固定来源/错误码，不输出解析器源码行或密钥。
**验证：** `uv run pytest -q tests/test_permission_settings.py -k safe_load`；逐类坏文件与上限边界均有断言。

### T10：三级加载、启动模式与警告集合

**文件：** P07、V04。
**依赖：** T09。
**步骤：**
1. 从注入 home 与根构造三个明确路径，分别加载有效快照及警告；缺失不报警。
2. 启动模式本地→项目→用户首个有效值，皆无 DEFAULT；坏文件不部分保留 deny/allow。
3. 证明其他有效层 BYPASS 在坏文件被跳过后仍可生效；不宣称自动安全回退，不读取真实用户 home。
**验证：** `uv run pytest -q tests/test_permission_settings.py -k layers`。

### T11：POSIX 危险模式与普通命令反例

**文件：** P04、V01。
**依赖：** T03。
**步骤：**
1. 固定私有 tuple 正则与 pattern_id，覆盖 Plan 的根/主目录强删、设备写入、格式化、fork bomb 类别。
2. 对旗标组合/分离、引号与根边界增加样例；普通项目绝对路径不能仅因以斜杠开头而误拦。
3. 测试只调用判定函数，禁用真实命令执行；加入长输入/回溯反例，不用宽泛嵌套正则。
**验证：** `uv run pytest -q tests/test_permission_blacklist.py -k posix`；危险样例均未启动进程。

### T12：Windows 危险模式与不可配置性

**文件：** P04、V01。
**依赖：** T11。
**步骤：**
1. 补 PowerShell Remove-Item/rm/ri/del、cmd rd/rmdir、format/Clear-Disk/Format-Volume 代表性高危族。
2. 覆盖大小写、参数顺序、磁盘根/主目录与安全子目录对照；不执行任何破坏性样例。
3. 验证 YAML 没有增删/关闭黑名单入口，命中标识与原因稳定。
**验证：** `uv run pytest -q tests/test_permission_blacklist.py -k 'windows or immutable'`。

### T13：根身份与目录段包含判断

**文件：** P05、V02。
**依赖：** T03。
**步骤：**
1. 构造 RootIdentity，实际绝对根与可用的文件系统身份固定，根不可用返回明确故障。
2. 实现目录段包含判断，拒绝同名前缀目录、外部根，不使用 commonprefix 或未经解析 startswith。
3. 验证根被换位/身份改变时不能静默换根；对不提供稳定身份的平台记录能力边界。
**验证：** `uv run pytest -q tests/test_permission_sandbox.py -k root`。

### T14：链接、缺失祖先和原路径顺序

**文件：** P05、V02。
**依赖：** T13。
**步骤：**
1. 实现 resolve_target(raw, root)，保留 link/.. 顺序，处理 ~、已有链接、最近存在祖先及剩余组件。
2. 覆盖不存在多级目录、缺失段后 .. 又遇链接、断链/循环/不可访问祖先；无法确定则拒绝。
3. 返回 PathStamp，不读取目标正文；不同合法目标变化与越界变化可区分。
**验证：** `uv run pytest -q tests/test_permission_sandbox.py -k resolution`；链接不可创建时明示平台 skip，不用假路径测试冒充原生链接证据。

### T15：Windows 路径形式与重定向边界

**文件：** P05、V02。
**依赖：** T14。
**步骤：**
1. 统一盘符、分隔符、大小写及本地长路径前缀；拒绝外部盘符/UNC 越界、设备命名空间、ADS 和 NUL。
2. 支持可确认的本机目录重定向，未知 reparse 类型拒绝；不依赖 Python 3.12+ 专有接口。
3. 分开测试纯词法平台模型与真实 Windows junction/链接，两类证据不得互相替代。
**验证：** `uv run pytest -q tests/test_permission_sandbox.py -k windows`。

### T16：永久规则数据合并与安全往返

**文件：** P08、V05。
**依赖：** T08、T09、T15。
**步骤：**
1. 从有效当前本地配置生成精确 allow，去重并保留 deny/default_mode/未知有效数据。
2. 序列化后重读比较数据，只有本条 allow 允许变化；注释/排版不作为可保留承诺。
3. 损坏配置、不可往返数据或超限拒绝保存，不用空配置覆盖，不新增会话 allow 伪装永久成功。
**验证：** `uv run pytest -q tests/test_permission_persist.py -k merge`。

### T17：同目录原子保存与冲突检测

**文件：** P08、V05。
**依赖：** T16。
**步骤：**
1. 固定本地文件位置，围栏检查文件/父目录/临时位置；拒绝指向外部的本地配置链接。
2. 独占创建随机临时文件、写入/flush/fsync，保留合理文件权限，replace 前核对原指纹与路径。
3. 并发变化返回冲突，正常替换返回 committed=True；不宣称完全消除外部竞态。
**验证：** `uv run pytest -q tests/test_permission_persist.py -k atomic`；只操作 tmp_path 内文件。

### T18：保存失败与临时资源清理

**文件：** P08、V05。
**依赖：** T17。
**步骤：**
1. 注入创建、写入、fsync、replace 失败，确认旧文件数据未被破坏。
2. 清理仅针对本次创建且身份匹配的临时文件；链接/身份被替换不删除其他文件。
3. 区分未提交、已提交、提交结果未知，提供 SaveResult 供父进程诚实提示，不在 finally 覆盖已提交事实。
**验证：** `uv run pytest -q tests/test_permission_persist.py -k failure_cleanup`。

### T19：受管 worker 的固定目的与消息白名单

**文件：** P16、P17、V08、V11。
**依赖：** T03。
**步骤：**
1. start 增加固定 purpose 和请求标识，默认工具目的保持原执行状态机；目的在启动后不可切换。
2. 权限目的仅接受 inspect_permission_path/persist_permission_allow 固定消息，拒绝 prepare/execute；工具目的拒绝保存权限配置。
3. 校验响应类型/ID/状态；维持 stderr 有界排空及已有 Windows Job/POSIX 进程组清理路径。
**验证：** `uv run pytest -q tests/test_permission_io.py -k purpose`，并运行 `uv run pytest -q tests/test_tool_executor.py -k 'protocol or process_control'`；两个选择器都应实际收集测试。

### T20：只读路径探测辅助操作

**文件：** P09、P10、P16、P17、V08。
**依赖：** T15、T19。
**步骤：**
1. 权限目的调用统一路径解析，仅返回 PathStamp；不调用工具 prepare、不读取正文、不返回目录列表。
2. 实现 PermissionIO.inspect_path 与逐字段响应验证；原始匹配路径保留在私有检查对象，不使用 UI 预览回传值。
3. 每次辅助操作拥有可回收进程，结束后关闭；加入伪造响应/错误目标/错误根的拒绝测试。
**验证：** `uv run pytest -q tests/test_permission_io.py -k inspect`；通过正文读取禁用替身证明检查未扫描目标内容。

### T21：永久保存辅助操作及资源登记

**文件：** P09、P10、P16、P17、V08、V05。
**依赖：** T18、T20。
**步骤：**
1. 固定权限消息调用本地保存事务，目标不能由模型任意指定；返回保存状态而非目标工具结果。
2. 工具/权限两类资源登记分别校验预期路径与事务 ID；权限临时文件登记不放宽原工具资源验证。
3. 父进程核对保存响应及 committed 状态，未知结果不能当作成功或确定失败。
**验证：** `uv run pytest -q tests/test_permission_io.py -k persist`，以及 `uv run pytest -q tests/test_permission_persist.py`。

### T22：权限 I/O 时限、取消与进程回收

**文件：** P09、P16、V08。
**依赖：** T21。
**步骤：**
1. 给每次路径探测/保存使用 5 秒默认预算；测试可注入短预算，不增加配置字段。
2. 处理启动中取消、操作中取消/超时、消费者关闭和重复 aclose，必须持有创建结果并 kill/reap。
3. 保存可能提交后丢应答时返回不确定事实；确认辅助进程结束后才向上结束，不留后台保存线程。
**验证：** `uv run pytest -q tests/test_permission_io.py -k lifecycle`；设置有限 asyncio 测试期限并检查待处理任务与原生进程。平台受限项单列。

### T23：Engine 命令链、硬限制与规则优先级

**文件：** P11、V06。
**依赖：** T04、T10、T12、T22。
**步骤：**
1. 实现 PermissionEngine.load/check，固定身份表；缺失根/未知类别/非法参数不能由 BYPASS 放行。
2. 命令检查先黑名单，再会话/本地/项目/用户规则，规则未命中才进模式；plan 命令硬拒。
3. 同层 deny 优先，就近命中即止；高层 allow 可覆盖低层 deny，但黑名单始终先拒绝。
**验证：** `uv run pytest -q tests/test_permission_engine.py -k command_pipeline`；所有危险样例用禁执行替身，测试不调用真实 shell。

### T24：Engine 文件链与权限复核

**文件：** P11、V06、V02。
**依赖：** T23。
**步骤：**
1. 文件调用通过 PermissionIO 获得真实路径，再以规范相对路径匹配各层规则；搜索使用根目录而非关键字。
2. 根不可用和路径不能确定产生安全拒绝；skip 黑名单层仅表示继续，不能直接 Allow。
3. 复核 PathStamp：同一目标继续，变成外部目标拒绝，变成另一合法目标返回 PERMISSION_TARGET_CHANGED。
**验证：** `uv run pytest -q tests/test_permission_engine.py -k file_pipeline`。

### T25：精确会话许可与永久许可接纳

**文件：** P11、V06、V05。
**依赖：** T24。
**步骤：**
1. 实现 accept：先检查本次 Ask 的归属、目标复核与 cancel，再接纳 ONCE/SESSION/PERMANENT；DENY 不新增规则。
2. SESSION 保存在 Engine、跨任务保留，退出不持久化；不同命令/工具/路径不能复用，cwd 不进入既定命令规则键。
3. 永久成功只将新增精确规则并入本地快照，不热加载外部其他改动；失败不新增会话规则，既有同层 deny 仍优先。
**验证：** `uv run pytest -q tests/test_permission_engine.py -k grants`；含跨任务、重建 Engine、保存失败/冲突/不确定与取消后事实。

### T26：ApprovalBroker 单 pending 与安全请求投影

**文件：** P12、V07。
**依赖：** T03、T25。
**步骤：**
1. 实现 connect/disconnect/request/submit/close，pending 私有持有真实 slot/target/Future，事件只含有界脱敏投影。
2. submit 严格匹配 run_id/approval_id，选择须为 ApprovalChoice；错误/重复/过期响应不接受。
3. 无消费者立即返回不可交互；批准只返回 choice，不写 slot.result，不把许可伪装成工具成功。
**验证：** `uv run pytest -q tests/test_approvals.py -k broker`；测试等待中 execution_started=False 且原结果仍为空。

### T27：审批取消竞态、断开与失活

**文件：** P12、V07。
**依赖：** T26。
**步骤：**
1. request 同时等待 Future 与 cancel，finally 清理辅助 wait task/Future/pending，发配对 resolved 事件。
2. 最后连接断开/close 取消等待；同 tick 选择与取消不能越过后续执行前 cancel 检查。
3. 测试旧 ID 对新请求无影响、取消后可重用 Broker、新问题答案不能作为 ApprovalChoice。
**验证：** `uv run pytest -q tests/test_approvals.py -k race`；有限等待内结束，无悬挂 asyncio task。

### T28：Executor 准备前统一门禁

**文件：** P15、V11、V16、V24。
**依赖：** T25、T27。
**步骤：**
1. 注入 permissions/approvals，execute 增加 run_id；关闭/取消、校验、plan 硬门禁及提问分支保持明确次序。
2. Engine 拒绝立即返回 denied，未注入引擎不能执行六工具；不自动 BYPASS、不加载真实全局配置。
3. 用禁止构造 worker/禁止读取正文的替身证明黑名单/沙箱/规则拒绝时未进入工具 prepare；提问仍只走原 plan 通道。
**验证：** `uv run pytest -q tests/test_tool_executor.py -k permission_preflight`；并运行 `uv run pytest -q tests/test_user_questions.py -k lifecycle_unavailable`，显式适配相关测试许可而不削弱门禁。

### T29：Executor 四选审批与非成功许可事实

**文件：** P15、V11、V07。
**依赖：** T28。
**步骤：**
1. Ask 发布审批请求；四项对应本次、会话、永久、拒绝，批准后才接纳许可并考虑启动目标 worker。
2. 保存失败发送仅本次 notice，提交未知如实提示；拒绝不设置 cleanup_error，Loop 可继续。
3. 审批等待排除在原工具超时外；无 run_id/消费者不能挂起或批准，取消后不执行未开始调用。
**验证：** `uv run pytest -q tests/test_tool_executor.py -k permission_approval`；短工具时限下等待审批不会误计成工具超时。

### T30：执行前再次复核与印记传递

**文件：** P15、P16、P14、V11。
**依赖：** T29。
**步骤：**
1. Allow/用户许可后再次检查取消和目标，必要时返回目标变化拒绝，不沿用旧批准。
2. 向工具 worker 传递批准印记，核对 preview.target 后才 execute；命令不附文件沙箱印记。
3. 真实结果仍在清理 await 前保存；已执行结果和批准选择分开，根变化/权限拒绝不制造基础设施停止。
**验证：** `uv run pytest -q tests/test_tool_executor.py -k permission_recheck`；覆盖“等待时改链接”和“准备返回不同目标”的禁执行断言。

### T31：工具工作进程准备/执行双复核

**文件：** P17、P18、V08、V11、V23。
**依赖：** T30。
**步骤：**
1. 生产文件工具在 prepare 前验证原路径和批准目标，execute 前验证 operation.target/原路径/根；缺少印记拒绝。
2. BaseTool 公共文件围栏供直接工具测试与 worker 共用，不复制另一套路径算法；命令/Ask 不误走文件类别。
3. 未通过复核不读取正文、不写临时文件；旧位置参数仍能构造但不能成为生产绕过入口。
**验证：** `uv run pytest -q tests/test_permission_io.py tests/test_tool_executor.py tests/test_file_tools.py -k worker_guard`。

### T32：文件读取与扫描访问点围栏

**文件：** P19、P20、V23、V02。
**依赖：** T31。
**步骤：**
1. original_path 对文件目标采用统一解析顺序，避免先 abspath 折掉 link/..；命令 cwd 不因此增加路径围栏。
2. scan_file、verify_snapshot、bounded_lines 和 read_file 的实际打开前复核真实目标，保持行号/编码/换行/BOM 业务。
3. 直接 read 和写/改准备扫描都不能越界；失效快照仍报告原 PREVIEW_STALE 而不是伪造成功。
**验证：** `uv run pytest -q tests/test_file_tools.py -k 'read_guard or scan_guard'`，再运行 `uv run pytest -q tests/test_file_tools.py -k 'read or snapshot'`，必要的旧用例仅更新临时许可接线。

### T33：写入/编辑临时文件与替换围栏

**文件：** P19、P21、P22、V23、V11。
**依赖：** T32。
**步骤：**
1. 创建父目录、临时文件、复制旧文及 replace 前复核，保持原唯一替换和文件指纹机制。
2. 将围栏印记贯通 prepared_file，不覆盖业务 state，不把新建多级目标误拒。
3. 审批后目标越界或身份变化不执行；旧写/改正向测试显式使用临时 BYPASS/精确规则，不移除内容与失败断言。
**验证：** `uv run pytest -q tests/test_file_tools.py -k write_guard`，以及 `uv run pytest -q tests/test_file_tools.py tests/test_tool_executor.py -k 'edit or write'`。

### T34：搜索根与 .gitignore 内部读取边界

**文件：** P25、P23、P24、V17。
**依赖：** T32。
**步骤：**
1. SearchWalk 强制接收项目根，搜索根先通过统一围栏；不因 Git 仓库根在外部而扩大权限。
2. .gitignore 仅从项目根到搜索根收集，读取前验证真实位置；外部链接忽略文件不得读取。
3. 保持隐藏项/忽略规则原默认与有限错误列表，补父项目外忽略文件的禁止读取测试。
**验证：** `uv run pytest -q tests/test_search_tools.py -k search_root_guard`。

### T35：搜索候选外链与不完整结果

**文件：** P25、P23、P24、V17。
**依赖：** T34。
**步骤：**
1. 目录链接/重定向跳过，候选文件解析后只能指向项目内普通文件；正文打开前再复核。
2. Glob 不列外部文件链接，Grep 不读外部正文，记录 sandbox_skipped；解析失败明确检索不完整。
3. 保持结果限额及 file/line/content 格式；规则仍只按搜索根匹配，不暗加 Read deny 继承。
**验证：** `uv run pytest -q tests/test_search_tools.py -k search_candidate_guard`，再运行 `uv run pytest -q tests/test_search_tools.py`。

### T36：调度阶段、四并发与混合结果保序

**文件：** P28、V12、V11。
**依赖：** T33、T35。
**步骤：**
1. Scheduler 传递 context.run_id，允许 checking/awaiting_approval 阶段，不内嵌第二套权限策略。
2. READ 继续 Semaphore(4) 并发，有副作用及交互继续串行；独立拒绝不阻塞获准同批调用。
3. 以混合 allow/deny/取消批验证事件和最终结果按原顺序、原调用 ID 配对，不重复执行或漏结果。
**验证：** `uv run pytest -q tests/test_tool_scheduler.py -k permission_batch`，以及 `uv run pytest -q tests/test_tool_scheduler.py`。

### T37：Runner 四档模式与任务冻结

**文件：** P29、P14、V13、V16。
**依赖：** T36。
**步骤：**
1. Runner 保存规范 PermissionMode，按 Engine 启动模式初始化；normal 仅在既有运行入口规范化。
2. set_mode 仅空闲有效，context.mode 保持冻结，跨任务保留模式；定义原 /plan、/do 接口所需行为。
3. 更新旧模式正向测试到新规范值，保留运行中不能改模式、plan 工具可见性/提问的断言。
**验证：** `uv run pytest -q tests/test_turn_runner.py tests/test_user_questions.py -k runner_permission_mode`。

### T38：Runner 审批入口与拒绝后继续

**文件：** P29、V13、V09、V16。
**依赖：** T37。
**步骤：**
1. 加 bind_approvals/unbind_approvals/submit_approval，校验当前 run_id、取消与关闭状态再提交 Broker。
2. 拒绝本身不增加 break；工具结果统一经 _commit_exchange，菜单/许可不成为伪用户消息或工具成功。
3. fake 模型先收到拒绝，再合法调整后完成；问题答案和权限选择互不串通，未知工具/上限停止仍成立。
**验证：** `uv run pytest -q tests/test_turn_runner.py tests/test_permission_integration.py -k denial_loop`，以及 `uv run pytest -q tests/test_user_questions.py -k approval_separation`。

### T39：Runner 关闭顺序与审批取消恢复

**文件：** P29、P15、P09、V13、V07、V08。
**依赖：** T38。
**步骤：**
1. 先标记 cancel/consumer_closed、关闭审批连接并唤醒等待，再等待 Runner、工具及权限 helper 收尾。
2. 覆盖等待审批时关闭流/应用、重复 aclose、选择同 tick 取消和 helper 启动中的取消。
3. 历史补齐原工具调用结果，turn_done 后可新发任务；已完成副作用/已保存授权不能谎称回滚。
**验证：** `uv run pytest -q tests/test_turn_runner.py tests/test_approvals.py tests/test_permission_io.py -k shutdown_recovery`；有限等待内无挂起任务/自有进程。

### T40：四档动态权限补充与计划提醒节奏

**文件：** P33、P34、P35、V18、V19、V13。
**依赖：** T37。
**步骤：**
1. RuntimeSupplement 增加 permission 类型，来源仍只接受应用工厂，不能从用户/文件特殊标签提升权限。
2. 每次模型请求追加简短当前权限模式；plan 保持第 1/5/9…轮完整、其余精简，顺序 permission→plan。
3. 环境仍每用户任务一次，补充不写 Conversation、不塞完整规则/配置路径，审批等待不推进迭代。
**验证：** `uv run pytest -q tests/test_prompting.py tests/test_prompt_protocols.py tests/test_turn_runner.py -k permission_supplement`。

### T41：稳定系统提示和工具说明一致

**文件：** P32、P20、P21、P22、P23、P24、P26、V18、V19。
**依赖：** T40。
**步骤：**
1. 删除普通模式无需审批的旧承诺，保留七模块顺序、专用工具优先与编辑前读取。
2. 说明尊重拒绝、禁止通过命令绕过文件边界、需求答案不是执行授权；描述不夸大命令隔离。
3. 仅更新文字，不改业务参数 Schema；不同动态模式在相同工具集下不改变稳定前缀。
**验证：** `uv run pytest -q tests/test_prompting.py tests/test_prompt_protocols.py -k permission_stable`；原模块顺序/Schema 与前缀断言继续通过。

### T42：CLI 与 App 后备构造的唯一装配

**文件：** P31、P30、P29、V22、V14。
**依赖：** T39、T41。
**步骤：**
1. 使用实际根装配唯一 Engine、ApprovalBroker、Executor、Runner，启动默认模式取有效配置。
2. App 未注入 Runner 的后备构造也使用默认权限，不留旧裸执行路径；根故障保留纯聊天和可见说明。
3. 测试注入临时 home/根与 fake Provider，启动配置警告不泄漏正文，不访问真实 LLM 服务。
**验证：** `uv run pytest -q tests/test_cli.py tests/test_tui.py -k permission_assembly`；两条装配路径默认安全且引用同一引擎。

### T43：四选一菜单的独立组件

**文件：** P13、V14、V15。
**依赖：** T26。
**步骤：**
1. 实现 ApprovalView 的工具/参数/原因/范围、四项菜单及帮助行，markup=False，初始 cursor=0。
2. 显示命令 cwd 与精确复用范围；路径授权不冒充只绑定一次内容更改。
3. 组件支持选择/取消/保存结果的历史展示及永久失活，旧组件不能再提交。
**验证：** `uv run pytest -q tests/test_tui.py tests/test_tool_tui.py -k approval_view`；窄屏长参数截断/换行不丢菜单或注入样式。

### T44：TUI 模式切换与常驻状态栏

**文件：** P30、V14、V15。
**依赖：** T42、T43。
**步骤：**
1. 加 priority Shift+Tab Binding，TextArea 聚焦时仍四档轮换；忙碌时消费按键但不切模式。
2. footer-left 常驻 DEFAULT/ACCEPT EDITS/PLAN/BYPASS（BYPASS 醒目），替代供应商名；保留右侧模型与原轮次/用量信息。
3. /plan 进 PLAN、/do 固定 DEFAULT 并触发现有执行语义；Shift+Tab 离开 PLAN 不自动执行。
**验证：** `uv run pytest -q tests/test_tui.py -k permission_mode_ui`；包含跨任务保持、等待问题/审批时禁止切换及旧 /do 语义。

### T45：TUI 审批事件与连接生命周期

**文件：** P30、P29、V14、V15。
**依赖：** T44。
**步骤：**
1. on_mount 绑定独立审批连接，消费 approval_request/resolved，绑定 run/local/approval 三类 ID。
2. 显示 checking/awaiting/saving 进行中状态，菜单与 `_pending_question` 互斥，不阻塞事件消费者读后续清理事件。
3. 只解除匹配 pending，旧事件不能清空新请求；断开/异常/退出取消并失活菜单。
**验证：** `uv run pytest -q tests/test_tui.py tests/test_tool_tui.py -k approval_events`。

### T46：菜单方向键、数字键和输入草稿

**文件：** P13、P30、V14、V16。
**依赖：** T45。
**步骤：**
1. 审批态聚焦菜单，上下循环、回车确认、数字 1～4 直选，消费按键，默认不会因聚焦 TextArea 误提交消息。
2. 保存/恢复 ChatInput 草稿，审批期间文本或 /plan、/do 不变成批准或新任务；不新增 y/n/空格批准。
3. 原 AskUserQuestion 的数字选项与自由回答仍正常；问题答案不能释放权限 pending。
**验证：** `uv run pytest -q tests/test_tui.py tests/test_user_questions.py -k approval_keyboard`；使用 Pilot 逐键验证，不能只测处理函数。

### T47：TUI Esc/Ctrl+C 取消与滚动历史恢复

**文件：** P30、P13、V14、V15、V13。
**依赖：** T46。
**步骤：**
1. 审批时 Esc/Ctrl+C 只取消任务、不退出应用，不先发送允许/拒绝伪装取消。
2. turn_done/退出/异常都清理 pending 与焦点，保留已失活的菜单和工具结果，恢复草稿。
3. 取消后再发普通消息和计划问题均正常，旧菜单按键无效；保存已提交或结果不确定照实显示。
**验证：** `uv run pytest -q tests/test_tui.py tests/test_tool_tui.py -k approval_cancel_ui`。

### T48：三协议回灌、脱敏与缓存计数回归

**文件：** V09、V19、P29。
**依赖：** T39、T41、T47。
**步骤：**
1. 用现有传输替身分别覆盖 Anthropic Messages、OpenAI Responses、Qwen 兼容流，捕获实际请求中的拒绝工具结果与原调用 ID。
2. 保留原 assistant 原生 payload，审批等待不额外发模型请求、不虚增 Token/缓存用量，工具历史只提交一次。
3. 合成密钥和终端控制字符放入命令/路径预览、规则/错误/警告，断言事件与 UI 安全、实际匹配不被脱敏替换；伪批准文本不能新增规则。
**验证：** `uv run pytest -q tests/test_permission_integration.py tests/test_prompt_protocols.py -k permission_protocol`，再运行 `uv run pytest -q tests/test_cache_usage.py tests/test_provider_events.py tests/test_protocol_integration.py`（后三者原则上不改实现/断言来掩盖回归）。

### T49：原手动脚本的样本许可迁移

**文件：** V20、V21、V09、V19。
**依赖：** T48。
**步骤：**
1. 两个 Executor 子类跟进 run_id 等参数；注入临时 Engine/home，不继承真实用户规则。
2. 原样本限制继续保留，需要写文件时只给固定样本路径精确规则或显式用户审批，不一律设 BYPASS。
3. 用 fake Provider/替身验证接口与样本边界；不执行原 live 脚本来冒充离线验证，不改 prompt 观察入口默认离线与付费确认。
**验证：** `uv run pytest -q tests/test_permission_integration.py tests/test_prompt_protocols.py -k manual_compat`；通过导入/替身路径证明没有加载凭据或产生网络请求。

### T50：权限专用手动观察入口

**文件：** V10、V09。
**依赖：** T49。
**步骤：**
1. 默认只打印离线场景/菜单样例，不读取供应商配置、真实权限文件或启动 shell。
2. 提供显式 --terminal 启动带脚本化 fake 模型事件的离线真实 TUI，供用户验证原生按键；它不加载凭据、不发网络请求。显式 --live 才读取当前默认服务，先展示非秘密服务/模型和费用可能性，要求用户明确确认；所有文件/持久化仍限临时 root/home，--terminal 与 --live 不可同时使用。
3. 场景覆盖四种选择、保存失败、取消恢复、模式切换与计划提问；危险命令永远交给纯判定替身。
**验证：** `uv run python tests/manual_permission_smoke.py --help`、`uv run python tests/manual_permission_smoke.py`，以及 `uv run pytest -q tests/test_permission_integration.py -k manual_permission_guards`；默认调用不得发网络请求。

### T51：配置示例、忽略规则与用户说明

**文件：** D01、D02、D03、V04、V09。
**依赖：** T50。
**步骤：**
1. 增加无密钥示例，说明三层文件和会话层优先级；只忽略本地配置及固定临时文件模式，不忽略共享项目设置。
2. README 写清四档、四选、转义、命令 cwd 未绑定、文件内容不绑定、坏配置 deny 失效、项目配置无需首次信任的风险。
3. 说明命令不受路径围栏、YAML 保存可能改变注释格式、外部改配置需重启；不声称整个系统强隔离。
**验证：** `uv run pytest -q tests/test_permission_settings.py tests/test_permission_integration.py -k settings_example`；用 `git check-ignore --no-index --stdin` 对虚拟相对路径检查本地/临时应忽略、共享示例不忽略，不创建真实许可文件。

### T52：全量离线回归与锁定环境检查

**文件：** V01～V25、P01～P35、D06（记录）。
**依赖：** T51。
**步骤：**
1. 运行全套新增与既有测试，修复真实回归；旧正向工具用例只调整明确临时许可，不删除安全或业务断言。
2. 执行锁校验、编译和 diff 空白检查，核对业务 Schema/Provider/依赖锁未发生越界修改。
3. Ruff/mypy/pytest-timeout 未配置则记未配置；不临时装包或静默改依赖为得到通过结论。
**验证：** `uv run pytest -q -ra`、`uv lock --check`、`uv run python -m compileall -q src`、`git diff --check`。失败修复后重跑，记录实际次数/跳过，不沿用上一阶段通过数。

### T53：原生权限 helper/工具进程与退出证据

**文件：** V08、V11、V13、D06（记录）。
**依赖：** T52。
**步骤：**
1. 原生运行辅助进程探测、保存及取消/超时，覆盖创建中取消、错误响应、提交后丢应答和资源身份清理。
2. 与原工具进程关闭并测，确认 Windows Job/POSIX 原机制未退化，任务收尾后无自有 helper 继续写入。
3. 受当前主机限制的项目先申请合适运行权限；不可运行的另一平台项单列，不能用纯替身证据冒充。
**验证：** `uv run pytest -q -ra tests/test_permission_io.py tests/test_tool_executor.py tests/test_turn_runner.py -k native_permission`；测试在受管执行下有有限期限，证据包含实际进程结束与临时文件状态。

### T54：真实 PowerShell TUI 手工验收

**文件：** V10、D06、D07（仅记录）。
**依赖：** T53；需要可用真实终端与用户参与。
**步骤：**
1. 使用临时项目/home及 fake 模型脚本事件启动真实界面，观察 DEFAULT 审批、四键选择、会话复用、永久重启复用和拒绝后继续。
2. 检查 TextArea 下 Shift+Tab、状态栏、ACCEPT EDITS/BYPASS/PLAN、/do、提问分流、Esc/Ctrl+C 及草稿/滚动恢复。
3. 危险样例只展示判定替身；无法完成真实终端观察时明确待验，不以 run_test 截图勾选通过。
**验证：** 用户在真实 PowerShell 运行 `uv run python tests/manual_permission_smoke.py --terminal`，按后续 Checklist 的真实终端条目逐项记录操作、观察结果与必要截图。无付费 API；本项未开展不阻止离线证据整理，但不能标完成。

### T55：可选真实模型权限闭环

**文件：** V10、D06、D07（仅记录）。
**依赖：** T53；另外需要用户对本次服务/模型/费用的明确授权。
**步骤：**
1. 运行前确认非秘密服务/模型、请求数量上限和临时样本范围；无授权不启动 --live。
2. 验证“写文件→审批→结果回灌→模型续答”及“拒绝→合法调整”场景，按已有迭代/时间上限结束，不自动轮换三家服务收费测试。
3. 保留匿名化观察结果，不输出凭据，不将没有真实配置的协议写成真实端到端通过。
**验证：** 获批准后运行 `uv run python tests/manual_permission_smoke.py --live`，保留确认及脱敏证据。未授权/无条件时记待验，不作为开发阻塞反复付费重试。

### T56：验收映射、进度与本地交付记录

**文件：** D04、D05、D06、D07。
**依赖：** T53；若执行了 T54/T55，则一并纳入其真实结果。
**步骤：**
1. 对照 AC1～AC26 和 Checklist 汇总实际验证，严格区分已通过、失败、平台跳过、未配置、待用户观察/待授权。
2. 只给已验证任务标完成；T54/T55 未执行时仍保持待验，不因汇总任务完成而把整个章节虚报全验收。
3. 写清实现范围、剩余风险、启动方式和本地提交；核对没有密钥/用户样本/其他阶段文档混入，不推送 GitHub。
**验证：** 核对四文档状态和证据相符，`git diff --check`、`git status --short`；逐项复核 Checklist 勾选均有实际结果，不以计划文字作为证明。

## 4. 执行顺序与依赖图

推荐按编号顺序执行，所有显式依赖只指向更早的任务，因此存在合法无环执行序。下面按逻辑支路展示，不代表授权启动额外 Agent。

```text
T01 → T02 → T03 → T04
                  ├→ T05 → T06/T07 → T08 → T09 → T10
                  ├→ T11 → T12
                  ├→ T13 → T14 → T15 → T16 → T17 → T18
                  └→ T19 → T20 → T21 → T22
{T04,T10,T12,T22} → T23 → T24 → T25 → T26 → T27
  → T28 → T29 → T30 → T31 → T32 → T33
                              └→ T34 → T35
{T33,T35} → T36 → T37 → T38 → T39
                    └→ T40 → T41
{T39,T41} → T42
T26 → T43
{T42,T43} → T44 → T45 → T46 → T47
{T39,T41,T47} → T48 → T49 → T50 → T51 → T52 → T53
                                                     ├→ T54（真实终端条件）
                                                     ├→ T55（单独 API 授权）
                                                     └→ T56（先如实汇总）
```

图中为简化示意；每节“依赖”字段是完整依赖真值，例如 T20 还依赖 T15，T16 还依赖 T08/T09，不得仅凭图跳过。

### 验证后本地提交分组

| 组 | 任务 | 提交边界 |
|---|---|---|
| G1 | T02～T18 | 纯权限契约、规则/配置/路径/保存及对应测试，不切换生产装配 |
| G2 | T19～T27 | 受管辅助 I/O、Engine、Broker 及生命周期测试 |
| G3 | T28～T39 | 执行端、文件/搜索、调度、Runner 接入与回归 |
| G4 | T40～T48 | 提示、CLI、TUI 及三协议/脱敏集成 |
| G5 | T49～T56 | 手动入口、示例/说明和实际验收记录；未验项继续保留 |

某组尚未满足前置验证时不为凑提交强行标完成；可以在组内按独立、验证通过的更小变更提交。不提交真实用户权限文件、weizhcode.yaml、.weizhcode-test/ 或无关修改。

## 5. 需求与任务覆盖

| Spec | 任务 |
|---|---|
| F1/AC1/AC5 | T23～T24、T28～T33、T36 |
| F2/AC2 | T11～T12、T23、T28、T48 |
| F3/AC3～AC5 | T13～T15、T20、T24、T30～T35 |
| F4/AC6～AC7 | T05～T08、T16、T25 |
| F5/AC8～AC9/AC15 | T10、T23～T25、T37、T42 |
| F6/AC10 | T09～T10、T42、T51 |
| F7/AC11/AC13 | T04、T23、T28、T37、T40、T44、T46 |
| F8/AC12～AC13 | T37、T42、T44～T47 |
| F9/AC14～AC16/AC20 | T08、T16～T18、T21～T22、T25～T30、T43～T47 |
| F10/AC17～AC18 | T03、T28～T30、T36、T38、T48 |
| F11/AC18～AC20 | T22、T26～T27、T36、T39、T45～T47、T53 |
| F12/AC21～AC22 | T04、T23、T26～T28、T38～T40、T46、T48 |
| F13/AC23～AC24 | T38～T42、T48～T50 |
| N5/N8/AC25 | T09～T10、T16～T18、T26、T48、T51 |
| N1～N9/AC26 | T01、各任务定向验证、T52～T56 |

三协议的离线证据在 T48 必须实现；T55 的真实模型观察不是替代它。T54 的真实终端证据也不能用 T43～T47 的自动测试代替。

## 6. 进度与证据登记表

以下为 2026-11-16 的实际进度。‘实现/回归完成’不代表该任务关联的所有手工或平台场景通过；专项缺口单列。Task 原定部分 -k 名称与最终测试组织不同，实际证据以全套测试和 Checklist 第 13 节列出的真实用例为准，不将未收集的选择器记通过。

| 任务 | 状态 | 实际证据 |
|---|---|---|
| T01 | 已完成 | 基线 61e2d56；uv lock --check 通过；uv run pytest -q -ra：471 passed、2 平台跳过，73.25s；工作区仅本章文档和用户 .weizhcode-test/ 未跟踪 |
| T02 | 已完成 | mode_contract 已纳入定向核心测试：73 passed、1 原生目录链接权限跳过，0.71s |
| T03 | 实现/离线回归完成 | 契约/错误结果纳入 test_permission_engine、test_approvals 和原执行器回归 |
| T04 | 实现/离线回归完成 | mode_matrix、工具可见性及原 AskUserQuestion 模式回归通过 |
| T05 | 实现/离线回归完成 | test_permission_rules：规则解析正反例通过 |
| T06 | 实现/离线回归完成 | test_permission_rules：命令全串/大小写/空白与复合命令数据通过 |
| T07 | 实现/离线回归完成 | test_permission_rules：路径分段/根/双星匹配通过 |
| T08 | 实现/离线回归完成 | test_permission_rules：精确规则转义与相似目标反例通过 |
| T09 | 实现/离线回归完成 | test_permission_settings：安全加载、重复键及限制边界通过 |
| T10 | 实现/离线回归完成 | test_permission_settings：三层加载、坏文件跳过与有效层模式通过 |
| T11 | 实现/离线回归完成 | test_permission_blacklist：POSIX 纯判定样例通过，未执行高危命令 |
| T12 | 实现/离线回归完成 | test_permission_blacklist：Windows 纯判定样例通过，未执行高危命令 |
| T13 | 实现/离线回归完成 | test_permission_sandbox：根边界、缺失路径和根身份变化通过 |
| T14 | 已实现；专项待验 | Windows junction 的 link/..、缺失段后链接通过；原生目录 symlink 无创建权限跳过，断链/循环完整原生验证待补 |
| T15 | 实现/离线回归完成 | Windows 原生 junction、长路径/设备/ADS/盘符/UNC 边界通过 |
| T16 | 实现/离线回归完成 | test_permission_persist：精确合并、去重及数据往返通过 |
| T17 | 已实现；专项待验 | test_permission_persist：独占临时文件、原子替换及并发冲突通过；外链保存专项仍待验 |
| T18 | 实现/离线回归完成 | test_permission_persist：open/write/fsync/replace 故障清理通过；丢应答见权限 I/O |
| T19 | 实现/离线回归完成 | test_permission_io：purpose、消息与响应校验通过 |
| T20 | 实现/离线回归完成 | test_native_permission_inspect 和非法响应用例通过 |
| T21 | 实现/离线回归完成 | test_native_permission_persist、独占临时文件及协议测试通过 |
| T22 | 实现/离线回归完成 | 原生 helper 取消/保存丢应答测试通过；Windows 进程回收有实际证据 |
| T23 | 实现/离线回归完成 | test_permission_engine：黑名单/规则优先级/模式矩阵及非法身份通过 |
| T24 | 实现/离线回归完成 | test_file_pipeline、test_permission_recheck：路径硬拒及接纳前变化拒绝通过 |
| T25 | 实现/离线回归完成 | test_grants、test_permission_approval：本次/会话/永久及重载通过 |
| T26 | 实现/离线回归完成 | test_approvals：四种选择、单 pending、无连接/失活与合成输入通过 |
| T27 | 实现/离线回归完成 | test_approvals、test_shutdown_recovery：取消、旧 ID 与关闭恢复通过 |
| T28 | 实现/离线回归完成 | test_permission_preflight：生产执行器缺引擎零执行；原参数/PLAN 门禁回归通过 |
| T29 | 实现/离线回归完成 | test_permission_approval：四选择均跑实际执行链；批准前没有目标文件/活动工具 worker |
| T30 | 实现/离线回归完成 | 接纳前目标变化与旧 prepared target 回归通过，原业务错误不被权限检查覆盖 |
| T31 | 实现/离线回归完成 | 原生 worker 协议与准备/执行目标检查回归通过 |
| T32 | 实现/离线回归完成 | test_file_tools 及 test_tool_executor 原读取/扫描回归通过 |
| T33 | 实现/离线回归完成 | 写/改原编码、换行、快照失效、唯一匹配、临时文件清理回归通过 |
| T34 | 实现/离线回归完成 | test_search_tools 的搜索范围/忽略文件边界及既有搜索回归通过 |
| T35 | 已实现；专项待验 | 候选路径复核与不完整结果实现并回归；原生外部文件 symlink 场景受权限限制跳过 |
| T36 | 实现/离线回归完成 | 混合允许/拒绝结果原序；test_permission_batch_real_checks_remain_concurrent 观测峰值 4 |
| T37 | 实现/离线回归完成 | Runner 原模式冻结、/plan、/do、跨任务及新四档回归通过 |
| T38 | 实现/离线回归完成 | test_denial_loop：拒绝→合法调用→真实批准→执行→续答，三次模型替身请求 |
| T39 | 实现/离线回归完成 | test_shutdown_recovery 与 consumer_closed：取消/关闭后历史配对、无文件副作用且可继续 |
| T40 | 实现/离线回归完成 | test_permission_supplement、原提醒回归：每请求权限说明，plan 第 1/5/9 轮节奏保留 |
| T41 | 实现/离线回归完成 | 原七模块/稳定前缀回归通过；仅文字规则更新，Provider 和业务 Schema 未重写 |
| T42 | 实现/离线回归完成 | CLI/App 默认权限装配及原 TUI 启动回归通过；无真实 API |
| T43 | 已实现；专项待验 | 菜单已实现；自动测试观测默认四选与失活，窄屏/长参数完整展示待专项观察 |
| T44 | 实现/离线回归完成 | test_permission_mode_ui 实际 Pilot Shift+Tab 四档与状态栏通过，原 /do 模式回归保留 |
| T45 | 已实现；专项待验 | 实际审批事件、输入禁用/恢复与 Broker 清理回归通过；慢保存状态视觉观察待补 |
| T46 | 已实现；专项待验 | Pilot 数字 1～4、上下/Enter、草稿恢复通过；非批准按键与问题/审批交替完整专项待补 |
| T47 | 已实现；专项待验 | Pilot Esc/Ctrl+C、失活/草稿恢复通过；多审批滚动顺序完整专项待补 |
| T48 | 已实现；专项待验 | 三协议实际请求体保留拒绝 ID/原生负载，原缓存/脱敏回归通过；不等同真实服务调用 |
| T49 | 实现/离线回归完成 | 旧手动脚本显式临时许可及 run_id 接线；导入/默认保护回归通过，未跑旧 live |
| T50 | 实现/离线回归完成 | manual_permission_smoke.py 默认及 --help 退出 0；互斥/禁止凭据加载测试通过 |
| T51 | 实现/离线回归完成 | 示例解析、README 核对及虚拟路径 check-ignore 检查通过，未创建真实许可 |
| T52 | 实现/离线回归完成 | 最终全量 607 passed、3 skipped，96.54s；锁/源码编译/diff 检查退出 0 |
| T53 | 已实现；专项待验 | Windows 原生 helper、保存/取消与 Job 工具清理通过；POSIX 专属用例在本机跳过 |
| T54 | 待验 | 需真实终端与用户观察 |
| T55 | 待验 | 需单独真实模型/费用授权 |
| T56 | 记录完成 | 本节及 Checklist 已记录真实证据、平台缺口和未授权项；未宣称整章全部验收通过 |

## 7. 审批边界

Task 共 56 项；四份文档均已批准并进入实现。设计小节保留原任务要求，实际完成范围以第 6 节与 Checklist 的证据为准。批准不代表授权真实危险操作、付费请求或 GitHub 推送。

本地实现提交：`3796cee`（权限契约/规则/配置/路径/保存）、`e3027fb`（辅助 I/O、Engine、审批 Broker）、`525b403`（工具/Runner/TUI/手动入口集成）。本次未推送。`tests/test_protocol_integration.py` 与 `tests/test_redaction.py` 另仅调整测试执行器导入以显式使用临时许可，原断言保留；未读取或暂存用户 `.weizhcode-test/`。
