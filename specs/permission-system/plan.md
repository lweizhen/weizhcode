# weizhCode 权限系统 Plan

> 状态：用户已明确批准 Plan。本文为设计，不是实现或验收结果。
> 范围：仅本阶段权限系统；不迁移协议、不增加真实 MCP、不增加系统级命令隔离。
> 技术基线：保留 Python 3.11+、HTTPX/原始 SSE、Textual、PyYAML、现有受管工具进程；不升级依赖或重写工具业务 Schema。
> 文档依据：Context7 已核对 Python 3.11 路径 API、Textual 按键优先级及 PyYAML 安全加载/保留能力。当前锁文件中的 Textual 为 8.2.8；实现仍须在锁定环境验证，不把最新文档当作运行证据。

## 1. 架构概览与接入选择

### 1.1 当前项目的实际落点

当前不是参考材料中的单一 agent.py：

- `TurnRunner` 拥有用户任务、模式冻结、模型请求、历史提交和取消生命周期。
- `ToolScheduler` 拥有按安全性分批、最多四个只读并发、按调用序发结果。
- `ToolExecutor` 在工作进程的 prepare/execute 之前控制执行、超时、结果保存与清理。
- `ManagedWorker`/`tools.worker` 提供固定 JSON 通信和 Windows Job/POSIX 进程组收尾。
- `QuestionBroker` 已支持计划模式需求提问，TUI 为单文件 `tui.py`，对话区使用组件而非 RichLog。
- 写/改工具的 prepare 已会扫描原文件、生成快照；因此权限审批不能放在 prepare 之后。

选择“统一执行器前置门禁＋独立权限模块＋独立审批 Broker”，不把权限散落在三种 Provider，也不在 TUI 里直接执行文件操作。

### 1.2 组件职责

| 组件 | 职责 | 不承担 |
|---|---|---|
| permissions/types、modes | 四档模式、裁决、来源、授权范围和不可变值对象 | 不加载 YAML、不依赖 TUI |
| permissions/blacklist | 固定高危正则；返回命中模式标识 | 不执行命令、不解释完整 shell 语法 |
| permissions/sandbox | 同一套路径解析、项目包含判断、目标印记 | 不提供操作系统隔离 |
| permissions/rules、settings | 精确/通配规则、三级加载、同层 deny 优先 | 不读取供应商凭据 |
| permissions/engine | 前四层判定、会话规则、授权接纳 | 不读取终端、不向模型请求批准 |
| permissions/io、worker_ops | 受管的路径元数据检查与本地规则保存 | 不启动用户命令、不执行目标工具 |
| approvals.ApprovalBroker | 第五层：发布审批请求、等待真实 UI 决策、取消与连接生命周期 | 不直接修改权限配置、不把问题答案当批准 |
| ToolExecutor | 校验→硬门禁→判定→审批→复核→准备/执行 | 不改变调度并发与历史协议 |
| TurnRunner、TUI | 会话装配、模式切换、事件转发、菜单操作、取消/退出 | 不解析文本中的“已批准”为授权 |

### 1.3 执行数据流

```text
LLM 完整工具调用
  → Scheduler 建立 ToolSlot，校验/分批
  → Executor 再校验与 plan/交互硬门禁
  → Engine：黑名单 → 文件路径围栏 → 分层规则 → 模式兜底
      Deny → 结构化 denied 结果
      Allow ───────────────────────┐
      Ask → ApprovalBroker → TUI  │
               用户选择            │
               拒绝 → denied       │
               允许 → 接纳精确授权 ┘
  → 检查取消、重新验证目标/权限
  → 启动工具 worker → prepare（含准备前路径复核）
  → 核对 prepared target → execute（执行前复核）
  → 原超时与清理 → Scheduler 按序返回 → Runner 一次性提交历史
  → 下一轮 LLM，沿用原停止条件
```

检查路径只需要元数据，不读取目标文件正文。路径探测使用只允许固定内部操作的受管辅助进程，完成后关闭，再进入审批；该辅助进程不是待批准的文件工具或用户 shell。审批期间不保留已准备好的目标工具、不占用执行超时预算。

### 1.4 方案取舍

- 采用 Executor 前置门禁：覆盖直接执行和 Scheduler 调用，避免只在上层检查而漏掉准备阶段读文件。
- 不采用“工具 prepare 后再审批”：prepare 已有读取行为，违反 Spec 的执行前边界。
- 不采用“所有 I/O 丢到可遗忘线程”：取消线程等待不保证线程停止，永久规则可能在任务结束后继续写入。复用已有进程管理，明确持有辅助进程生命周期。
- 不采用参考中的 smoke 自动 BYPASS：手动脚本要显式使用受限审批或临时样本规则，不能暗中放宽生产会话。

## 2. 核心契约与依赖方向

### 2.1 模式与裁决

`permissions/types.py` 不导入 models、工具或 TUI，可安全被 models 引用。

```python
class PermissionMode(str, Enum):
    DEFAULT = "default"
    ACCEPT_EDITS = "acceptEdits"
    PLAN = "plan"
    BYPASS = "bypassPermissions"

class Decision(str, Enum):
    ALLOW = "allow"
    DENY = "deny"
    ASK = "ask"

class Category(str, Enum):
    READ = "read"
    WRITE = "write"
    EXEC = "exec"

class ApprovalChoice(str, Enum):
    ONCE = "once"
    SESSION = "session"
    PERMANENT = "permanent"
    DENY = "deny"
```

`parse_mode(value)` 仅接收四个名字，大小写不敏感，返回有效枚举或验证错误；不把未知值变成 BYPASS。`normalize_runtime_mode` 仅为原内部调用兼容，把旧 `normal` 映射为 DEFAULT，`plan` 映射为 PLAN；配置不接受 `normal` 作为新模式名。

`AgentMode` 作为兼容类型别名保留在 models，对外事件使用四档规范值。Runner 内只保存规范枚举。`RunContext.mode` 仍在任务创建时冻结，不能运行中修改。

### 2.2 前四层结果与路径印记

以下为必须实现的字段契约；均使用冻结数据对象，包含集合时转成不可变形式：

| 类型 | 字段 |
|---|---|
| RootIdentity | original_root、canonical_root、可用时的 `(st_dev, st_ino)` |
| PathStamp | canonical_target、project_relative、target_exists、nearest_existing、ancestor_identity；包含用于复核的原始路径 |
| PermissionTarget | internal_name、friendly_name、category、match_target、command 或 PathStamp |
| PermissionCheck | decision、source、reason、target、matched_layer、matched_rule；未命中项为 None |
| Rule | friendly_name、解析后的模式 token、is_exact、配置原串；结果由所在 allow/deny 列决定 |
| RuleSet | allow、deny 的有序不可变集合 |
| PermissionSettings | default_mode、RuleSet、原始安全 YAML 数据、文件版本指纹、来源状态 |
| SettingsWarning | layer、脱敏前的控制文件路径、固定错误码；不包含原文件正文 |
| SaveResult | saved、already_present、warning_code、committed；不将未知状态伪装成 saved=False |

`source` 固定取 blacklist、sandbox、rule、mode、plan、user、interaction、invalid 之一。只有规则匹配结果包含层与规则；用户展示前再脱敏，实际匹配不可使用展示文本。

### 2.3 第五层审批契约

在 `models.py` 新增冻结的 `ApprovalRequest`：

```python
@dataclass(frozen=True)
class ApprovalRequest:
    approval_id: str
    tool_name: str
    friendly_name: str
    arguments_preview: str
    target_preview: str
    reason: str
    scope_hint: str
```

不把原始 call、规则对象、Future 或含密钥的真实参数塞进 UI 事件。真正的 ToolSlot、PermissionTarget 与 Future 只由 Broker 私有 pending 持有。

`TurnEvent` 追加可选 `approval` 字段和 `approval_request` / `approval_resolved` 两类事件。`approval_resolved` 携带相同 approval_id、local_id 及 run_id，选择结果通过固定文本/固定枚举字段表达，不传原始配置。`ToolSlot.phase` 增加 `checking`、`awaiting_approval`，`execution_started` 在真正交给工具 execute 前仍为 False。

Broker 注入既有 Redactor，构造 request 时生成有界安全投影；Runner 的 `_EventChannel._safe` 再显式处理 approval 各字符串字段，不能因增加新字段而绕过安全显示。PreparedOperation 的权限印记字段追加在现有字段之后并默认 None，以保留旧位置参数构造；生产文件 worker 会拒绝缺少印记的执行指令，不能用默认 None 作为放行开关。

审批 ID、工具 local_id、运行 run_id 都使用应用生成值。协议 call_id 只用于历史配对，不单独作为授权凭据。

### 2.4 核心接口

```python
# modes.py
def parse_mode(value: str) -> PermissionMode: ...
def normalize_runtime_mode(value) -> PermissionMode: ...
def next_mode(mode: PermissionMode) -> PermissionMode: ...
def mode_fallback(mode: PermissionMode, category: Category) -> Decision: ...

# engine.py，假定 call 已通过 registry.validate；仍验证支持的内置工具身份
class PermissionEngine:
    @classmethod
    def load(cls, project_root: Path, *, user_home: Path | None = None,
             io=None) -> "PermissionEngine": ...
    async def check(self, call: ToolCall, *, mode: PermissionMode,
                    cancel: asyncio.Event) -> PermissionCheck: ...
    async def accept(self, checked: PermissionCheck, choice: ApprovalChoice,
                     *, cancel: asyncio.Event) -> SaveResult: ...
    async def aclose(self) -> None: ...

# approvals.py
class ApprovalBroker:
    def connect(self) -> str: ...
    def disconnect(self, token: str) -> None: ...
    async def request(self, slot: ToolSlot, checked: PermissionCheck, *,
                      run_id: str, cancel: asyncio.Event, emit) -> ApprovalChoice | None: ...
    def submit(self, run_id: str, approval_id: str,
               choice: ApprovalChoice) -> tuple[bool, str]: ...
    def close(self) -> None: ...

# io.py
class PermissionIO:
    async def inspect_path(self, raw_path: str, root: RootIdentity, *, cancel) -> PathStamp: ...
    async def persist_allow(self, target: PermissionTarget, settings_path: Path,
                            root: RootIdentity, *, cancel) -> SaveResult: ...
    async def aclose(self) -> None: ...
```

`load` 在启动装配时读取控制配置；交互期间的路径探测和写入由 `PermissionIO` 承担。单元测试可注入内存 I/O 与临时 home，不读取真实全局设置。生产实现不得用未注入引擎作为绕过标志。

依赖方向：types → 标准库；models → types；rules/sandbox/settings → types/标准库/PyYAML；engine → 前述模块、models、io；io → 受管进程客户端；executor → engine/Broker；runner/TUI → executor/Broker。包 `__init__.py` 只做轻量导出或惰性导出，避免重导出 engine 导致循环。

## 3. 配置、规则与模式

### 3.1 三层文件名与格式

| 层 | 文件 |
|---|---|
| 用户 | `Path.home() / ".weizhcode/settings.yaml"` |
| 项目 | `<project_root>/.weizhcode/settings.yaml` |
| 本地 | `<project_root>/.weizhcode/settings.local.yaml` |

启动只加载一次。单独新增 `.weizhcode/settings.yaml.example`；`.gitignore` 只新增本地文件和本系统命名的保存临时文件，不忽略整个 .weizhcode 目录。

```yaml
default_mode: default
permissions:
  allow:
    - 'Bash(git status)'
    - 'Write(src/**)'
  deny:
    - 'Bash(git push*)'
    - 'Read(.env)'
```

这不是 LLM 供应商配置；不改变 weizhcode.yaml 或其六字段约定。示例不得声称 Read(.env) 能自动阻止 Grep 或获准命令读取该文件。

### 3.2 加载验证与损坏文件策略

使用基于 PyYAML SafeLoader 的专用加载器；增加重复映射键检查。限制单文件 256 KiB、每文件 allow/deny 合计最多 1024 条规则、单条规则 8192 字符、嵌套深度 16；超限视为该文件无效，不做无界解析或静默截断。

空文件/null 视为空对象。顶层必须为映射；已知键 default_mode、permissions 的值严格验证；permissions 仅允许 allow、deny 两列字符串列表。非法规则、重复 YAML 键、无效模式、类型错误、未知工具名或非字符串规则使整个文件跳过，不部分采用。顶层未知键作为扩展数据保留，不赋予权限语义；只允许可安全往返的有界基本数据，拒绝复杂键、自定义对象和循环引用。

缺失无警告；不可读/非法/超限产生固定分类警告。避免输出 PyYAML 异常原文及其源码行片段。模式按有效文件本地→项目→用户选取，规则独立按会话→本地→项目→用户判定。坏文件不人为提升其他有效文件的严格程度，其他有效层 BYPASS 仍可能成为启动模式，风险照实提示。

项目根解析失败与配置损坏不同：前者不给一个“空规则＋原始未知根”的假安全引擎。保留引擎故障状态，六个执行工具返回 PERMISSION_ROOT_UNAVAILABLE；纯聊天可继续，修复后重启。计划提问不取得文件权限。

### 3.3 规则解析与精确转义

规则友好名严格为 Read/Write/Edit/Bash/Glob/Grep，映射至 read_file/write_file/edit_file/run_command/find_files/search_content。工具身份使用固定表，不凭模型给出的 read_only 或未知插件标志授予只读权限。

- 无括号为全工具规则；有括号取首个外层左括号与末尾右括号，内部括号必须成对或转义。空模式段拒绝，避免和全工具规则混淆。
- 规则外部首尾空白可去除，括号内部的空格/换行不 strip，尤其不能改写完整命令串。
- 采用独立的小型模式解析器，只把未转义 `*`/`**` 当通配；`?`、`[]` 等其他字符按字面处理，不借用 shell 展开。
- `\*`、`\(`、`\)`、`\\` 表示字面星号、括号、反斜杠。命令中的其他反斜杠按字面保留；生成器仍统一转义全部反斜杠，确保可往返。
- 命令用完整字符串匹配，区分大小写，`*` 可跨空格/换行，连续星号等价单星号。不添加“git 是只读”等语义推断。
- 文件规则使用 `/` 分段；只支持项目相对模式，不接受绝对/盘符路径、`.`/`..` 目录段或依赖 Windows 反斜杠分隔的模式。目标根目录统一为 `.`。Windows 路径按平台 normcase 比较，命令不随平台折叠大小写。
- 文件 `*` 仅段内；独立 `**` 段匹配零个或多个目录段。以分段动态匹配实现，避免简单正则回溯组合造成指数行为；文件模式不允许段中混用 `a**b` 的跨段意义。
- `exact_rule(target)` 先转义，再生成友好名包裹的字符串，解析回来的 token 全是字面值；重复保存按规范 token/目标比较去重，不凭原 YAML 排版比较。

新增精确规则失败（例如序列化后超限）只能导致“未保存，允许本次”，不得退回裸工具名或更宽 glob。

### 3.4 规则优先级和模式矩阵

每层先 deny 后 allow，层间先会话后本地、项目、用户。仅第一个命中的层有效；不扫描所有层收集 deny 后否决高层 allow。

| 兜底 | READ | WRITE | EXEC |
|---|---|---|---|
| default | Allow | Ask | Ask |
| acceptEdits | Allow | Allow | Ask |
| bypassPermissions | Allow | Allow | Allow |

plan 在执行前硬拒 WRITE/EXEC，不进入规则/兜底/审批；三个 READ 仍通过沙箱和规则，可被 deny。AskUserQuestion 保留独立 plan 交互入口，不当作第四类文件工具，不生成权限规则。

`accept` 只接受经过本次 Ask 和 Broker 真实响应的 checked 对象，不提供从模型字符串直接加入规则的入口。会话 allow 由当前 Engine 持有，跨用户任务复用，不放在单轮 RunContext，不清空于 /plan 或 /do。

命令授权按完整 command 匹配，不绑定 cwd，这是已批准 Spec 的命令范围；审批必须展示 cwd，并提示复用同命令时执行目录可能不同。目录与命令不会被拼成新规则语法来暗改需求。

## 4. 黑名单与文件围栏

### 4.1 内置黑名单

用私有固定 tuple 存储 `(pattern_id, compiled_regex)`，没有 YAML 加载/关闭入口，不把可修改列表暴露给 Engine 调用方。匹配原始 command，不匹配 TUI 截断稿、shell 的 EncodedCommand 包装或脱敏文本。

模式族至少包括：

- POSIX rm 常见 r/f 组合与分离旗标，精确识别根/主目录/整目录内容目标，避免把 `/project/build` 仅因以 `/` 开头而误当根目录。
- dd 写 /dev 磁盘设备、mkfs/常见格式化工具、重定向覆盖原始磁盘设备、已知 fork bomb。
- Windows PowerShell Remove-Item/rm/ri/del 常见递归强制删除磁盘根或主目录变体，兼顾参数顺序、引号及大小写。
- cmd rmdir/rd 对根/主目录的递归静默删除，以及 format、Clear-Disk、Format-Volume 等明确磁盘破坏命令族。

不从模型参数加载正则，不对任意脚本做解码或执行来“判断是否安全”。命中返回 pattern_id 和可读固定原因；预览命令仍走显示预算。命令正则以可控线性扫描/局部边界模式为主，避免嵌套不受限重复。加入大输入与易回溯反例测试。

### 4.2 统一路径解析

`sandbox.resolve_target(raw, root)` 是文件工具和权限探测的同一来源，不在不同地方复制 startswith 判断。

1. 根在启动时解析为实际绝对目录并保存身份；工具根与环境快照根均采用这一实际目录，不允许运行中换根。
2. 保留原路径分段顺序，把相对路径接到根后解析；不能先用 abspath/normpath 消去 `link/..` 再解析链接。`~` 仍按现有 expanduser 语义展开，展开后接受同样围栏检查。
3. 按路径组件查询存在性；已有链接/目录重定向解析到实际目标，链接循环/不支持的重定向/不可访问祖先拒绝。遇到不存在段保留后缀，遇到后续 `..` 仍按解析后的目录处理并继续验证后续已存在组件，不能跳过后缀中重新出现的链接。
4. 得到规范目标后使用按目录段的包含关系（如规范后的 Path.relative_to 或 commonpath），不用 commonprefix/裸字符串前缀。Windows 使用一致的驱动器、大小写和本地长路径前缀规范；不同盘符、UNC 边界或设备命名空间不能误通过。拒绝设备路径、NUL 和 Windows ADS 目标等不属于普通项目文件的路径形式。
5. 返回 canonical_target、相对根路径与最近存在祖先印记。目标可以不存在，但祖先必须可确定；根身份改变时拒绝，不把根换成另一个位置继续运行。

路径包含判断之后再做规则匹配。链接别名按实际目标的项目相对路径匹配，不能通过内部链接路径别名轻易绕过对同一目标的 deny。规则未承诺按硬链接内容身份匹配。

Python 3.11 的路径异常要覆盖 OSError、ValueError、RuntimeError（链接循环）；不能仅依赖新版 Path.is_junction，也不能把 is_relative_to 的词法判断误认为已经解析了链接。

### 4.3 受管路径探测与执行复核

`PermissionIO` 复用 ManagedWorker 的启动/kill/reap，但显式使用 `purpose="permission"`。新增客户端固定方法 `inspect_permission_path`、`persist_permission_allow`，分别对应 worker 的内部消息；该目的进程拒绝 prepare/execute。工具目的进程拒绝权限配置保存消息，两个目的不能中途切换。

start 消息校验固定 purpose、已确定根和请求标识；响应逐字段检查类型、请求标识与状态，内部消息不能由模型工具名路由。保存临时资源登记也按 purpose 分开验证：工具进程继续只接受当前 preview 对应的临时路径；权限进程只接受本次固定本地配置目录与随机事务 ID 对应的临时路径，不因复用传输而允许登记任意清理目标。两类资源均在清理前核对文件身份，不跟随被替换的链接删除其他文件。

路径探测不调用工具 prepare，不读取目标正文、不返回目录列表；每次检查的辅助进程在 5 秒预算内完成并清理。失败/超时返回安全拒绝；同一 READ 批的最多四次检查仍可并发。实际工具工作进程保留原默认时限，不把两者合并成审批超时。

获得 Allow/用户许可后：

- 再检查 cancel 和当前 checked 是否仍有效；元数据探测确认同一目标。变化为越界立即拒绝；变化为另一合法目标返回 PERMISSION_TARGET_CHANGED，让模型新发调用，不自动复用旧批准。
- 工具 worker prepare 前调用同一 sandbox helper，且必须与父进程批准的目标一致。父进程核对 preview.target；不一致禁止 execute。
- worker execute 前再次校验原路径、批准目标与 operation.target；写/改沿用文件快照校验，在 scan_file、verify_snapshot、创建父目录、临时文件写入及 replace 前的路径访问点执行围栏复核。
- `PreparedOperation` 通过独立字段保存文件权限印记，不能挤占业务 state 后被工具覆盖；命令不附文件印记。
- 根/路径变化错误归权限拒绝或 PREVIEW_STALE，不标记 cleanup_error 导致本可继续的 Loop 被中止。真正无法管理/清理子进程仍按原基础设施错误停止。

受管辅助进程只是使 I/O 有可终止、可等待的归属；Windows Job 仍然只负责生命周期，不提供文件隔离。上述复核减少可观察的检查/使用差异，不是原子文件描述符沙箱，也不承诺抵御所有外部竞态。

### 4.4 搜索中的内部读取

SearchWalk 新增不可省略的项目根边界，分别检查搜索根和每个候选路径。目录链接/重定向直接跳过；文件链接只在解析后的普通文件仍在项目内时可用。

实际读取前重新复核候选目标；find_files 不列出外部文件链接，search_content 不读取其正文。跳过数量以 sandbox_skipped 计入有限元数据；解析失败使用现有有限错误列表并标注检索不完整，不把失败伪装成完整无命中。

`.gitignore` 本身也是文件读取：只从项目根到搜索根收集规则，不再向项目根之外寻找祖先配置；每个 .gitignore 读取前检查实际位置，外部链接规则不能被偷偷读取。Git 仓库根不再充当比项目根更宽的授权边界。

规则引擎只检查 Glob/Grep 搜索根，不对每个候选文件另套 Read 规则，也不新增未批准的内容保密模型。围栏逐文件检查与规则按根检查是两件事。

## 5. 审批、永久保存与取消

### 5.1 ApprovalBroker 与 Runner 入口

复用 QuestionBroker 的连接/单 pending 生命周期思想，不直接复用其回答通道。Broker 只通过 `submit` 接受枚举值；不接受“yes”等文本去猜授权。

Runner 新增 `bind_approvals`、`unbind_approvals`、`submit_approval(run_id, approval_id, choice)`，先验证当前任务、关闭状态和 cancel，再交给 Broker。TUI、测试或明确绑定的其他交互消费者必须 connect；无消费者 request 返回 INTERACTION_UNAVAILABLE，不挂起、不创建许可。

Broker 在 request 前验证没有旧 pending，建立 Future 后发 approval_request；Future 只返回选择，不写 slot.result（批准不是工具执行结果）。取消 wait 与 Future 完成竞态下，以执行前 cancel 检查阻止执行；不采用 QuestionBroker“已接收答案优先”语义来认为工具已运行。

finally 清除当前 pending、取消未完成 Future、取消并 await cancel.wait 辅助任务，发对应 resolved 事件。disconnect 最后连接或 close 时置本轮 cancel，阻止正在等待的执行。submit 返回后不再接受重复/旧 ID。

### 5.2 选择后的状态变化

| 选择 | 当前调用 | 会话内存 | 本地磁盘 |
|---|---|---|---|
| ONCE | 复核后执行 | 无变化 | 无变化 |
| SESSION | 复核后执行 | 精确 allow | 无变化 |
| PERMANENT | 保存成功或明确降为本次后复核执行 | 成功时更新本地规则快照 | 精确 allow |
| DENY | 不执行，USER_DENIED | 无变化 | 无变化 |
| 取消 | 不执行尚未开始的调用 | 不生成尚未接纳的规则 | 不启动尚未开始的保存 |

在接纳 SESSION/PERMANENT 前先复核目标和 cancel；目标变化不给旧目标新增授权。授权一旦明确接纳/保存，不因用户随后取消后续执行而假装已经回滚；UI 提示已保存的事实，取消不自动撤销授权。

### 5.3 永久保存事务

固定目标 `<root>/.weizhcode/settings.local.yaml`，其父目录和文件若经重定向逃到项目外，拒绝保存；不去改用户全局文件。保存临时文件也必须在合法本地目录内，不能跟随现成临时文件链接。

内部 helper 以固定流程执行：

1. 从磁盘重新读取、严格验证当前本地文件，保存原字节指纹。文件损坏时拒绝覆盖，即便启动时该文件已被跳过。
2. 从已批准目标生成精确 allow 并去重；已有相同规范规则则不重写。保留已有 deny、default_mode 和顶层扩展数据，不用空 Settings 覆盖未知内容。
3. `safe_dump(..., allow_unicode=True, sort_keys=False)` 后重新解析，校验除本条 allow 外所有有效数据不变；不保留注释/原引号/原缩进，README 明确这一限制。只读到不能安全往返的数据时拒绝保存，而不是丢弃。
4. 同目录独占创建 `.settings.local.<随机ID>.tmp`，写入、flush/fsync，沿用已有文件权限或对新文件采用仅当前用户可写的合理本机权限；不改变目录 ACL。
5. replace 前复核目录围栏及原文件指纹；不匹配则返回冲突，不覆盖用户并发编辑。不宣称指纹检查加 replace 能消除所有外部竞态。
6. 原子替换并返回 committed=True；父进程收到成功才把新增规则纳入启动时的本地规则快照（不把磁盘其他外部变更热加载进本次会话）。与内存既有同层 deny 冲突仍按 deny 优先。
7. 失败清理本次创建且身份匹配的临时文件，保留旧文件；发 notice“仅本次允许，未保存永久授权”，不新增会话 allow 掩盖失败。

保存同样由 5 秒受管辅助进程执行。取消时停止并回收 helper，然后再结束本轮；如果替换可能已完成但成功应答丢失，不谎称没保存，返回“不确定，授权可能已保存，请检查本地配置”，本轮不继续执行。无后台保存线程在任务结束后继续改配置。

同一应用单 pending 和副作用串行已避免内部竞争；不引入跨进程全局锁，不声称可以与任意外部编辑器完全事务隔离。取消时本次允许的副作用与已提交永久许可分别报告。

### 5.4 执行超时与审批等待

审批等待不纳入工具原准备＋执行共享时限，也不设置用户必须几秒内回答的默认期限。等待可由用户取消、UI 断开、应用退出结束。元数据检查与配置保存分别有内部有限预算。

未获许可前不创建目标工具 worker。Allow 后沿用原 `asyncio.timeout` 包住 worker.start、prepare、execute，不按阶段重置；并保留 work/cancel race、shield cleanup、Windows Job/POSIX kill/reap 和部分输出处理。

## 6. Executor、调度与历史集成

### 6.1 Executor 的稳定次序

Executor 构造新增 `permissions`、`approvals` 依赖。生产 CLI 和 App 默认构造路径必须注入同一个 Engine；漏注入返回 PERMISSION_UNAVAILABLE，不隐式创建 BYPASS，不读取真实全局设置修补单测。

`execute(slot, *, mode, cancel, emit, run_id="")` 保留原关键参数，追加 run_id；Scheduler 传当前 context.run_id。会话内存属于 Engine，不属于每次工具调用。调用方直接执行器也必须经过相同门禁，run_id 缺失时只能进行不需交互的调用，Ask 返回无交互许可错误。

次序固定：

1. 关闭/取消检查；registry.validate；保存合法 call。
2. plan 写/命令硬拒；AskUserQuestion 走原 plan 专用分支，不碰权限规则。
3. 支持身份、参数分类检查；Engine.check。Deny 立即保存 denied 结果，尚无 prepare 或目标正文读取。
4. Ask 经 Broker；DENY 返回；取消返回 cancelled；允许选择按第 5 节接纳，不把 choice 本身写入工具结果。
5. 复核目标与 cancel，构造允许操作所需的印记。
6. 原 worker 执行路径，prepare 前/execute 前围栏；保存真实结果早于任何 cleanup await。
7. 原统一脱敏、序列化结果预算和 cleanup；权限正常拒绝不设置 cleanup_error。

### 6.2 错误分类

| 来源 | error_code | status | Loop |
|---|---|---|---|
| 黑名单 | DANGEROUS_COMMAND | denied | 继续 |
| 路径越界/解析无法确认 | PATH_OUTSIDE_PROJECT / PATH_UNRESOLVED | denied | 继续 |
| 根不可用/目标变化 | PERMISSION_ROOT_UNAVAILABLE / PERMISSION_TARGET_CHANGED | denied | 继续 |
| 显式 deny | PERMISSION_RULE_DENIED | denied | 继续 |
| plan 写/命令 | TOOL_NOT_ALLOWED | denied | 继续 |
| 用户拒绝 | USER_DENIED | denied | 继续 |
| 缺引擎/交互 | PERMISSION_UNAVAILABLE / INTERACTION_UNAVAILABLE | denied | 继续或按断开路径取消 |
| 用户取消 | TOOL_CANCELLED | cancelled | 原 cancelled 停止 |
| 参数/工具未知 | 保留既有 INVALID_* / UNKNOWN_TOOL | error | 原未知计数/循环规则 |
| 进程无法管理或清理 | 保留 PROCESS_CONTROL_FAILED | error | 原基础设施停止 |

`ToolResult.failure` 补齐权限类 code→denied 映射；metadata 保留 permission_source、layer、受预算约束的规则/目标说明、execution_started=False。不把 stdout/error 原始值作为权限诊断打印。最终仍由 `_safe_result` 等既有路径脱敏并与原 call_id 配对。

### 6.3 Scheduler 与 Runner

Scheduler 只追加 run_id 传递、阶段展示与兼容新模式，不自己实现第二套权限策略。连续 READ 仍按现有分组与 Semaphore(4) 并发，副作用/交互保持串行。混合拒绝与放行均发 tool_start/tool_result，结果保持原下标序。

Runner 不因权限拒绝额外 break；只沿用原取消、未知工具、迭代上限及基础设施停止条件。`_commit_exchange` 仍是唯一工具历史提交入口，不把菜单、Future、批准文本追加成伪 user/tool 消息。真正的 tool_result 才进入模型历史。

`RunContext` 和 ToolSlot 仍拥有当前任务事实；审批请求不会推进 iteration、环境采集或用量结算。`aclose` 先设置 cancel/consumer_closed，再关闭 Broker、等待 runner/worker 与权限辅助进程收尾；不能先 await 一个仍在等审批而未被唤醒的任务。

## 7. TUI 交互与模式状态

### 7.1 显示组件

新增 `approval_ui.py` 的 `ApprovalView(Static)`，挂载到当前对话区：工具行、参数/目标、原因、授权范围、四行选项和“↑↓ 选择 · 回车确认 · 1–4 直选 · Esc 取消”。使用 `markup=False` 和既有 Redactor，菜单文本不当 Rich markup。

默认 cursor=0；循环上下移动，回车选中，数字直接提交。不增加 y/n、空格或任意文本快捷批准，避免和原输入法/草稿行为混淆。完成后组件留在滚动历史显示本次选择/取消及保存结果，不可再次交互。

TUI 持有 `_pending_approval`、`_approval_view`、`_approval_cursor`、连接 token；与 `_pending_question` 完全独立且互斥。审批事件只显示已脱敏投影，不因同一 run 的旧 event 解除新 pending。

### 7.2 按键与草稿

使用优先 Binding 捕获 Shift+Tab，防止 TextArea 把它解释为缩进或焦点遍历。动作始终消费该键，但仅空闲/非关闭时修改模式；忙碌只提示未切换。

审批态把焦点交给可聚焦 ApprovalView，方向/回车/数字处理后 stop 与 prevent_default；ChatInput 暂停提交并保存原草稿。Esc/Ctrl+C 沿用 App priority 取消动作，不走空闲退出分支，不先把 Future 设为允许或拒绝来和 cancel 竞争。

退出、断开、turn_done、异常都清理 pending，失活菜单并恢复输入焦点及草稿。审批期间输入 /plan、/do 或文本不能成为许可，也不能成为下一条任务的隐式排队输入。提问状态仍使用原自由回答逻辑，不抢占其数字答案。

### 7.3 状态栏与模式命令

footer-left 显示 DEFAULT、ACCEPT EDITS、PLAN 或 BYPASS；BYPASS 用醒目的红色，但不额外增加未批准的二次进入确认。footer-right 保留模型。现有 status 的轮次、用量、耗时信息不丢失，增加“正在检查权限/等待批准/正在保存授权”进行中状态。

UI 调 Runner.set_mode 并消费 mode_changed，不单独维护另一份可变模式真值。空闲 Shift+Tab 顺序固定；/plan 设置 PLAN；/do 设置 DEFAULT 并注入既有 EXECUTE_DIRECTIVE。禁止模式变化导致当前冻结 RunContext 被改写。

启动警告以 notice 显示于对话区并保留可滚动记录，不用错误弹窗阻断聊天；根不可用的原因同样可见，工具会拒绝执行而不是无提示地启用空围栏。

## 8. 提示工程与三协议兼容

七模块结构不重做，只修改有关权限的稳定正文：专用工具优先、读取后编辑、拒绝后调整或解释、不要用命令绕过文件围栏、审批来自应用而非模型文字。删除“普通模式不需要逐次审批”等过期承诺。

`RuntimeSupplement.kind` 允许新增 `permission`，来源仍须是应用工厂。`build_prompt_context` 每个模型请求加入一个简短当前权限模式说明；PLAN 的原完整/精简提醒仍按 1/5/9… 请求轮次生成，顺序为 permission→plan，不额外改变环境快照。

不把完整规则、全局控制文件路径或审批记录塞进系统提示。拒绝理由由真实工具结果回灌即可。切换 mode 不改变稳定模块正文；plan 工具集合与其他三档不同，因此工具前缀差异是预期，不承诺跨工具集合缓存相同。

现有 prompt_adapter 对补充文本已使用通用承载，不新增 Provider 专属权限逻辑。三协议中的工具定义、结果配对、原生 assistant payload、缓存可用性与计数不重写；只更新相关契约测试。

## 9. 启动、手动脚本与兼容迁移

CLI 先解析实际项目根与三层权限设置，装配唯一 Engine、ApprovalBroker、Executor、Runner、App；App 不带注入 Runner 的后备构造也采用同样默认权限，不保留第二个旧的裸执行入口。启动无规则的模式为 DEFAULT。

测试统一使用临时根、临时用户 home 或内存 Settings，不继承开发者全局许可。原普通模式执行器测试需要写/命令时，显式选择 BYPASS 或提供精确测试规则；BYPASS 测试仍验证黑名单和文件围栏，而不是用无引擎代替。

`tests/manual_tool_smoke.py` 与 `tests/manual_prompt_smoke.py` 的 Executor 子类跟进新参数。保留临时样本边界；需要写样本时只为固定样本路径预置显式规则，或绑定用户审批通道；不把真实 cwd 的命令一律批准。

新增 `tests/manual_permission_smoke.py` 默认只展示离线场景和菜单样例，不加载凭据、不访问真实用户权限文件。真实模型阶段必须显式 --live、展示服务/模型与费用可能性并取得确认；所有文件/保存仅在临时项目与临时 home，危险命令永远不进入真实执行器，使用纯判定/禁执行替身。

README 说明配置位置、转义、四档模式、四选菜单、会话范围、配置损坏失效风险、项目配置信任、命令不受路径围栏、PyYAML 注释格式变化，以及重启加载规则。不开通付费服务、不改远端、不推送 GitHub。

## 10. 文件组织与修改清单

以下路径均相对 `D:/STUDY/weizhcode-python/`；进入 Task 时按依赖进一步拆分。

| 操作 | 文件 | 主要职责 |
|---|---|---|
| 新增 | src/weizhcode/permissions/__init__.py | 轻量门面，避免依赖环 |
| 新增 | src/weizhcode/permissions/types.py | 模式、裁决、目标、印记、规则/保存结果等契约 |
| 新增 | src/weizhcode/permissions/modes.py | 模式规范化、四档轮换、兜底 |
| 新增 | src/weizhcode/permissions/blacklist.py | 不可配置的正则与命中标识 |
| 新增 | src/weizhcode/permissions/sandbox.py | 根身份、链接解析、包含判断与复核 |
| 新增 | src/weizhcode/permissions/rules.py | 友好名、模式 token、匹配、精确转义 |
| 新增 | src/weizhcode/permissions/settings.py | 三层安全 YAML、验证、警告、启动模式 |
| 新增 | src/weizhcode/permissions/persist.py | 本地事务保存、去重、数据保留 |
| 新增 | src/weizhcode/permissions/io.py | 受管权限辅助进程客户端与取消收尾 |
| 新增 | src/weizhcode/permissions/worker_ops.py | 固定内部路径探测/保存消息实现 |
| 新增 | src/weizhcode/permissions/engine.py | 前四层、会话层、接纳授权 |
| 新增 | src/weizhcode/approvals.py | 独立审批 Broker |
| 新增 | src/weizhcode/approval_ui.py | 四项内联菜单及历史失活显示 |
| 修改 | src/weizhcode/models.py | 规范模式、审批事件、slot 阶段、operation 目标印记 |
| 修改 | src/weizhcode/tools/executor.py | 统一前置门禁、审批、复核、失败结果 |
| 修改 | src/weizhcode/tools/process.py | 固定目的及权限辅助消息，保持进程管理 |
| 修改 | src/weizhcode/tools/worker.py | 目的白名单和工具 prepare/execute 围栏 |
| 修改 | src/weizhcode/tools/base.py | 文件工具 prepare/execute 公共检查、错误映射 |
| 修改 | src/weizhcode/tools/file_utils.py | 一致的原路径解释、扫描/写入访问点复核 |
| 修改 | src/weizhcode/tools/read_file.py | 读取前目标复核 |
| 修改 | src/weizhcode/tools/write_file.py | 写入复核接线及权限说明 |
| 修改 | src/weizhcode/tools/edit_file.py | 编辑复核接线及权限说明 |
| 修改 | src/weizhcode/tools/find_files.py | 传入项目边界及跳过统计 |
| 修改 | src/weizhcode/tools/search_content.py | 候选读取围栏及不完整结果 |
| 修改 | src/weizhcode/tools/search_utils.py | 遍历/文件链接/.gitignore 围栏 |
| 修改 | src/weizhcode/tools/run_command.py | 描述一致；不增加命令路径隔离 |
| 修改 | src/weizhcode/tools/registry.py | 四档工具可见性、保留提问模式 |
| 修改 | src/weizhcode/tool_scheduler.py | run_id 传递，阶段与保序回归 |
| 修改 | src/weizhcode/turn_runner.py | 引擎/Broker 装配、模式、提交审批、关闭 |
| 修改 | src/weizhcode/tui.py | 菜单状态/按键、模式显示与启动警告 |
| 修改 | src/weizhcode/cli.py | 唯一根与三层配置装配 |
| 修改 | src/weizhcode/prompting/modules.py | 替换过期权限承诺 |
| 修改 | src/weizhcode/prompting/contracts.py | permission 补充来源契约 |
| 修改 | src/weizhcode/prompting/reminders.py | 四档输入兼容，原 plan 节奏不变 |
| 修改 | src/weizhcode/prompting/builder.py | 请求级当前权限说明 |
| 新增 | .weizhcode/settings.yaml.example | 无密钥的分层权限示例 |
| 修改 | .gitignore、README.md | 本地文件忽略与用户说明 |
| 新增 | tests/test_permission_blacklist.py | 正反例、不可覆盖、Windows 样例 |
| 新增 | tests/test_permission_sandbox.py | 根、链接、缺失段、Windows 路径、搜索边界 |
| 新增 | tests/test_permission_rules.py | 精确/通配/转义/层级 |
| 新增 | tests/test_permission_settings.py | 三层加载、坏文件、模式、真实全局隔离 |
| 新增 | tests/test_permission_persist.py | 去重/往返/失败/冲突/取消提交 |
| 新增 | tests/test_permission_engine.py | 流水线、矩阵、会话、未知安全默认 |
| 新增 | tests/test_approvals.py | 通道、ID、重复、断开、竞态 |
| 新增 | tests/test_permission_io.py | 辅助目的隔离、超时/取消/进程回收 |
| 新增 | tests/test_permission_integration.py | Loop、三协议、原生负载、用量与提示回归 |
| 新增 | tests/manual_permission_smoke.py | 默认离线、显式线上观察 |
| 修改 | tests/test_tool_executor.py、tests/test_tool_scheduler.py | 执行、准备前门禁、保序与有界并发回归 |
| 修改 | tests/test_turn_runner.py、tests/test_tui.py、tests/test_tool_tui.py | 模式、菜单、取消、状态栏、正常聊天 |
| 修改 | tests/test_user_questions.py、tests/test_search_tools.py | 提问分流、搜索外链 |
| 修改 | tests/test_prompting.py、tests/test_prompt_protocols.py | 新动态类型、前缀稳定 |
| 修改 | tests/manual_tool_smoke.py、tests/manual_prompt_smoke.py | 样本权限接线与原默认保护 |

三种 Provider、SSE 解析器和供应商配置模块原则上不改实现。没有实际存在的 smoke/main.py、agent.py、tui/stream.py 等不照搬创建。

## 11. 验证策略与证据边界

### 11.1 分层自动验证

1. 纯逻辑：模式、黑名单、规则、优先级、转义往返、非法配置整文件跳过。
2. 临时文件系统：根内外、同名前缀、缺失祖先、链接/重定向、搜索文件链接/.gitignore、目标审批后变化。
3. 保存：临时 home/root，精确去重、数据保留、文件损坏不覆盖、写失败/并发变化、取消前后提交事实。
4. 生命周期：无通道、错误/重复/旧 ID、答案与批准混淆、同 tick 取消、退出/消费者关闭、所有辅助进程与 asyncio task 回收。
5. Agent：一次拒绝后模型改合法路径、多调用保序、READ 仍并发、一次批准不是成功结果、迭代与未知上限保持。
6. TUI：run_test/Pilot 验证 TextArea 焦点下 Shift+Tab、四个数字、方向/回车、Esc/Ctrl+C、草稿恢复、滚动历史失活、提问数字不被审批抢占。
7. 三协议：使用已有传输替身捕获请求，验证被拒结果及正确 call_id、assistant 原生数据保留、审批不新增请求/统计；不因无真实模型配置跳过这些离线集成。

所有高危命令数据只交给黑名单/Engine 的禁执行替身，绝不交给可真实启动 shell 的验收路径。跨平台不可用的链接测试明示 skip，附缺失覆盖，不以 skip 冒充通过。

### 11.2 验证命令与工具现状

实现后逐步运行定向 pytest，再执行 `uv run pytest -q -ra`、`uv lock --check`、`uv run python -m compileall -q src`、`git diff --check`。这只是计划，不引用上一章测试数作为本章通过数。

当前 pyproject 没有 Ruff/mypy/pytest-timeout，不能直接承诺对应命令通过或为此未经批准升级依赖。本章不增加这些依赖；如环境已有可用工具，可记录额外结果，否则标明未配置。异步超时保护使用现有 asyncio/pytest-asyncio 能力。

当前环境此前对受限上下文中的 Windows 异步进程有执行限制；需要正常主机测试环境时单独申请运行权限。不得把主机限制误报产品缺陷，也不得因此删除原生进程清理验证。

### 11.3 手工验收

真实 PowerShell 场景包括 DEFAULT 写需批准、SESSION 同目标复用、PERMANENT 临时项目重启复用、DENY 后继续、ACCEPT EDITS、BYPASS 不越硬门禁、PLAN 提问及 /do、等待审批取消后恢复。

自动化 TUI 测试不能证明真实终端按键与布局无误；真实 API 也不默认获授权。后续 Checklist 分别记录离线、真实终端、真实模型结果及未验项，不编造缓存命中、不把危险命令交给真实终端。

## 12. Spec 覆盖映射

| Spec | Plan 落点 | 验证组 |
|---|---|---|
| F1 | 1.3、4.3、6.1 | 顺序/短路、prepare 前无正文读取、直接入口 |
| F2 | 4.1 | 黑名单多平台正反例、四档及 allow 均不可覆盖 |
| F3 | 4.2～4.4 | 路径/链接/目标变化/搜索内部读取 |
| F4 | 3.3 | 全字符串、路径分段、特殊字符精确往返 |
| F5 | 3.1～3.4、5.2 | 层级、会话跨任务、重启清空/持久 |
| F6 | 3.2 | 缺失/坏配置/警告/保留其他层 |
| F7 | 2.1、3.4、6.1 | 四档、plan 硬门禁、提问独立 |
| F8 | 7.2～7.3、9 | Shift+Tab、/plan、/do、跨轮冻结 |
| F9 | 2.3、5、7.1 | 四选、范围、永久保存、失败/取消 |
| F10 | 6.2～6.3 | 拒绝来源、配对、Loop 继续 |
| F11 | 4.3、5.1/5.4、6.3 | 有界并发、等待/取消、进程资源 |
| F12 | 2.3、3.4、5.1、6.1 | 身份、无效参数、伪批准、无消费者 |
| F13 | 6.3、8、11 | 三协议替身、提示/缓存/用量回归 |
| N1～N9 | 统一执行器、受管 I/O、安全显示、平台和证据约束 | 在 Task 与 Checklist 按 AC1～AC26 细化 |

## 13. 关键决策与风险登记

| 决策 | 选择与理由 |
|---|---|
| 审批范围 | 精确命令或工具＋真实项目内路径，不自动泛化；符合用户确认 |
| 命令 cwd | 展示但不纳入精确规则键；符合已批准语义，明确相同命令可能在不同 cwd 复用 |
| 层级 | 会话 > 本地 > 项目 > 用户，同层 deny 优先；不是全局 deny 最大 |
| 模式 | DEFAULT/ACCEPT_EDITS/PLAN/BYPASS；plan 是硬只读，不用参考的 Ask 防御兜底 |
| 坏配置 | 整文件警告跳过，接受 deny 失效风险；不擅自改为停止执行 |
| 根失效 | 拒绝工具而非假安全降级；纯聊天继续 |
| 文件围栏 | 公共解析＋探测＋准备/执行复核＋搜索内部检查；不夸大竞态保证 |
| 审批通道 | 独立 Broker，审批不是 AskUserQuestion，也不是模型历史中的新任务 |
| I/O 归属 | 受管内部辅助进程，无可遗忘的永久保存线程；取消后先收尾再 turn_done |
| 保存失败 | 清晰降为本次；不生成会话规则伪装永久成功，提交未知如实提示 |
| YAML 保留 | 保留有效数据，不承诺注释与格式；未知/损坏数据不可默默覆盖 |
| 路径沙箱边界 | 文件类，不含获准命令；黑名单不是完整 shell 安全分析 |
| 兼容 | 保留原 SSE/三协议/工具参数，旧 normal 仅运行入口兼容，不成为第五档 |
| 验证 | 默认离线、临时数据、危险样例永不执行，真实 API/终端分开举证 |

仍存在已接受的风险：项目权限文件可能放宽权限且无首次信任确认；坏配置被跳过可能丢失限制；宽泛命令 glob 可覆盖复合命令；获准 shell 可读写项目外或修改配置；应用层路径检查不等于硬链接/并发恶意进程隔离。这些不以提示词或 UI 文案假装已经解决。

## 14. 文档核对依据

以下是本次通过 Context7 获取的官方资料，作为 API 语义依据而非本项目测试通过证据：

- [Python 3.11 pathlib](https://docs.python.org/3.11/library/pathlib.html)：resolve 的链接/缺失目标语义、链接循环异常；is_relative_to 自身仅作词法包含判断。
- [Python 3.11 os.path](https://docs.python.org/3.11/library/os.path.html)：commonpath 与按字符前缀 commonprefix 的差别，跨盘符处理需要显式兜底。
- [Textual 键盘输入与优先绑定](https://textual.textualize.io/guide/input/)：priority Binding 在聚焦控件绑定前处理，适用于 Shift+Tab 及取消热键。
- [PyYAML 官方仓库](https://github.com/yaml/pyyaml)：SafeLoader 限制对象构造，但不自带重复键拒绝；safe_load/safe_dump 不保留注释和原排版，需要应用额外验证数据保留。

本章不需要新增三家模型 API 的请求参数，因而不重新研究或更改 Provider 协议。

## 15. 下一阶段边界

批准 Plan 后仅生成 Task，再经批准生成 Checklist。四份全部批准后才按 Task 实现并逐组验证、提交本地逻辑变更；不自动推送 GitHub。本章文档保留在独立 permission-system 目录，不覆盖前章。
