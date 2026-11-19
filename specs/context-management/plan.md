# weizhCode 上下文管理 Plan

> 状态：四份文档均已获用户批准，进入实施；技术设计不变，完整功能尚未完成或验收通过。
> 日期：2026-11-17 创建；2026-11-18 获批。本轮仅更新审批元信息，技术设计不变。
> 目标环境：现有 Python 3.11+、HTTPX/SSE、Textual、官方 MCP SDK；不新增 tokenizer、LLM SDK、数据库或命令框架。

## 1. 设计落点与依据

### 1.1 当前代码的真实衔接点

| 当前落点 | 本章处理 |
|---|---|
| TurnRunner 已跨用户任务存在，不是每次重新创建 Agent | 会话运行状态由同一 Runner 持有；CLI 与 TUI 后备构造共用装配工厂，不照搬其他项目的 Agent 生命周期 |
| Conversation 返回深拷贝，工具交换一次追加 assistant/tool | 保留公开行为，增加有版本的内部历史快照和条件整体替换；不从深拷贝对象地址判断身份 |
| Executor、Runner、MCP 适配层多次调用最终结果序列化，单项限制 20,000 字符 | 在首次有损步骤前捕获安全文本；展示/回灌结果与归档来源分离，不能试图从已截断正文还原 |
| read_file 在读取时就受行数、长行、字符采集预算限制，并添加行号 | 在同次获准读取内记录实际返回范围的纯文本，不另开一次裸读；不放开工具本身采集上限 |
| MCP Host 在适配结果时即做最终截断 | Host 私有 IPC 增加有界文本捕获帧；不把它做成 MCP 新能力，不向 Server 传会话存储路径 |
| Provider 先造请求体，再通过公共 SSE 传输；错误大多变成字符串 | 抽出纯请求准备，保留流式接口兼容；结构化错误分类，不靠 UI 文案猜长度错误 |
| UsageAccumulator 已统一输入口径 | 估算复用归一化 TokenUsage，不再次叠加 cache_read/cache_write |
| 提问、审批、任务取消、模式切换已有通道 | 手动压缩加入同一 Runner 忙碌门禁与取消生命周期，绝不排队偷偷执行 |

本章不改变原工具 Schema、权限优先级、MCP 启动信任和目录冻结规则；新增内部数据契约不成为模型可调用工具。

### 1.2 已核对的外部协议事实

通过 Context7 核对官方类型/文档；不足部分查官方页面，不调用生产模型验证：

- Claude 的输出长度结束与上下文窗口结束是不同情况；输入已经超窗可返回明确长度校验错误，流中也可能出现窗口结束原因。见 [Claude 上下文说明](https://platform.claude.com/docs/en/build-with-claude/context-windows) 与[官方响应类型](https://github.com/anthropics/anthropic-sdk-python/blob/main/src/anthropic/types/message.py)。
- Responses 的 `truncation=disabled` 不应由应用改为自动丢开头输入；未完成响应及其原因须区别于正常完成。见 [Responses 参考](https://developers.openai.com/api/reference/resources/responses/methods/create)。本章仍使用 HTTPX，不因此安装 OpenAI SDK。
- 千问兼容端点的 `InvalidParameter` 不足以单独认定上下文过长；须结合明确的输入长度说明，不能把所有参数错误或额度错误当成压缩信号。见[百炼错误说明](https://help.aliyun.com/en/model-studio/error-code)及[输入长度示例](https://help.aliyun.com/en/model-studio/coding-plan-faq)。

文档事实不是任意兼容端点行为保证；没有得到明确长度信号就不触发紧急摘要，不根据模型名猜容量，不开启供应商自动压缩或自动换模型。

## 2. 架构概览

核心逻辑集中在 `weizhcode.compact`，依赖方向为：

```text
CLI / TUI 后备装配
    └─ Conversation + ToolExecutor + TurnRunner
                                  └─ ContextManager / SessionRuntime
                                      ├─ 捕获来源与快照（只接收获准执行所得数据）
                                      ├─ Layer1：决定 → 固定用途归档 → 稳定预览
                                      ├─ Estimator：准备后的实际请求投影 + usage 锚点
                                      ├─ SummaryDriver：无工具摘要、长度退让、解析
                                      ├─ Recovery：文件、工具快照、边界补充
                                      └─ SessionStore → 受管固定用途 IO Worker
Provider.prepare_request → PreparedRequest → 同一请求交给流式传输
```

约束：

- compact 核心不 import CLI、TUI 或 TurnRunner；只接收必要协议、快照、回调和取消信号。
- compact 的轻量契约模块不在导入期加载 Provider、MCP SDK、磁盘或进程；避免 models/permissions 间循环依赖。
- 文件、命令与 MCP 的原执行仍走原门禁；捕获只在实际执行之后，内部归档不调用模型工具。
- 资料 I/O 用固定用途受管子进程；不以可能无限阻塞的后台线程作为文件提交的最后保障。
- 生产默认启用管理；旧测试或独立嵌入可显式注入 NoopContextManager，不增加面向用户的关闭配置，也不因没有真实配置而启动 Server。

## 3. 会话状态与核心契约

### 3.1 身份、来源与版本

下面是接口设计，不是本轮写入业务代码的类型定义。

```python
@dataclass(frozen=True)
class HistoryEntry:
    entry_id: str
    turn_id: str
    origin: Literal['human', 'provider', 'tool', 'application', 'summary']
    message: ChatMessage
    human_seq: int | None = None
    created_at: str = ''
    result_keys: tuple[str, ...] = ()

@dataclass(frozen=True)
class HistorySnapshot:
    revision: int
    entries: tuple[HistoryEntry, ...]

@dataclass(frozen=True)
class ArchiveRef:
    session_id: str
    record_id: str
    kind: Literal['human', 'tool']
    source_key: str
    sha256: str
    safe_bytes: int
    raw_path: str
    view_path: str
    view_sha256: str
    complete: bool

@dataclass(frozen=True)
class ToolSource:
    execution_key: str
    text: str  # repr=False；经过统一脱敏，未经过最终模型结果截断
    collected_bytes: int
    safe_bytes: int
    truncated_at_source: bool
    capture_complete: bool

@dataclass(frozen=True)
class FileReadCapture:
    execution_key: str
    canonical_path: str
    start_line: int
    returned_lines: int
    text: str  # repr=False；去掉显示行号，保留实际换行
    truncated: bool
    accepted_sequence: int
    read_at: str
```

`execution_key` 由 Runner 的 run_id、slot 序号及本次实际执行的应用随机标识绑定，文件名另使用应用生成的 32 位十六进制 ID。它不是供应商 call_id，不接受文本解析出的伪身份。供应商 call_id/tool_name 仍完整用于原协议配对，不拿归档 ID 替换它们。

上述文本/请求字段的 `repr=False` 是实现约束，实际类型须使用 dataclass 的字段选项落实，不能只写注释。用户原文、工具原文与文件快照用 `Redactor.text` 只替换已知秘密，不用展示用控制符清理改写归档正文；UI/日志另经安全展示，JSONL视图转义控制字符。所有公开事实标签、索引说明及元信息也统一脱敏。

Conversation 增加内部 entry 来源和 revision，但不把这些应用字段发进供应商 body。现有 `messages()`、位置参数和追加公开方法保持兼容；新增：

```python
def snapshot(self) -> HistorySnapshot: ...
def replace_if_current(self, expected_revision: int, entries: tuple[HistoryEntry, ...]) -> bool: ...
```

每次追加或替换递增 revision；返回深拷贝/不可变快照。替换先在局部验证所有工具配对再一次交换，不暴露半截历史。非法输入不能以 `None` 自动清空对话。

真实用户提交使用 origin=human 并分配单调 human_seq；`/do` 产生的执行指令用 application 来源。旧摘要与提醒不被重新分配用户身份。AskUserQuestion 答案由原交互 Broker 在接纳时附带可信答案记录，在其所属任务下归档；不增加伪 user 回合，也不形成权限许可。

### 3.2 长期状态与单次操作状态

```python
class SessionRuntime:
    session_id: str
    root: RootIdentity | None
    context_window: int
    store: SessionStore
    sources: CaptureHub
    replacements: ReplacementLedger
    human_index: HumanArchiveIndex
    file_reads: RecentFileState
    anchor: UsageAnchor | None
    auto_failures: int
    latest_summary: SummaryRecord | None
    operation_generation: int

@dataclass(frozen=True)
class CompactionBudget:
    operation_id: str
    deadline: float
    max_summary_requests: int = 12

@dataclass(frozen=True)
class CompactOutcome:
    trigger: Literal['auto', 'manual', 'emergency']
    status: Literal['skipped', 'completed', 'no_reduction', 'failed', 'cancelled', 'tripped']
    before_tokens: int
    after_tokens: int | None
    offloaded_results: int
    summary_requests: int
    code: str = ''
    omitted_turn_ranges: tuple[tuple[str, str], ...] = ()
```

主线程事件循环是状态唯一 owner；工作进程只返回有界 DTO，不写父进程对象。CaptureHub 的异步接纳与 ReplacementLedger 的决定/提交各有内部锁；压缩和主任务还受 Runner 会话忙碌门禁保护，不依赖 GIL 推断跨 await 原子性。

一次重型操作持同一 operation_id、generation、快照 revision、绝对 deadline。自动/手动/紧急不能同时提交；迟到结果、旧事件、已取消 generation 不可改变当前会话。控制台输入不在后台线程继续等待。

### 3.3 ContextManager 对上层的窄接口

```python
async def before_request(frame: RequestFrame, *, cancel, emit) -> PreparedRequest: ...
async def compact_manual(frame: RequestFrame, *, cancel, emit) -> CompactOutcome: ...
async def compact_emergency(frame: RequestFrame, fault: ProviderFault, *, cancel, emit) -> CompactOutcome: ...
def settle_main_request(request_id, request_snapshot, assistant, usage, *, complete): ...
async def accept_tool_sources(slots, *, cancel): ...
async def aclose() -> CleanupReport: ...
```

`RequestFrame` 包含当前不可变历史快照、同模式工具定义快照、当前 PromptContext、当前输出预算、操作身份和 Provider。ContextManager 不持有 Registry，不擅自选择不同工具子集；每次准备、恢复及实际发送都使用这次工具快照。

### 3.4 配置与生产装配

ProviderConfig 在现有字段末尾追加 `context_window: int = 0`，不调整原位置顺序；`effective_context_window(config)` 定义在 config 层：0/缺省时 anthropic=200000、openai/qwen=128000，显式非零值须 `type(value) is int` 且大于33000。布尔不能借 int 子类关系通过，其他六字段加载语义不变。该字段只用于应用预算，不原样传入API。

`build_context_runtime(*, root_identity, context_window, redactor, store_factory=SessionStore)` 仅接收CLI已选择的配置结果；compact不反向import config。普通CLI分支、MCP分支与TUI后备构造都使用此工厂并把同一Runtime交给Executor/Runner，不创建第二份会话。

MCP分支先完成既有Bootstrap.prepare的配置/信任准备与秘密集合合并，再用最终Redactor构造Runtime；不能提前复制一份只知道模型key的旧秘密列表。Runtime在首次工具执行前接入，Host的捕获开关按每次获准调用传递，不需要为了建立Runtime重连Server。

根不可确认时SessionStore标为不可用，但仍可进行纯估算/普通聊天；需要归档的压缩安全失败，不向cwd、用户目录或临时目录改存真实资料。直接测试构造Runner可显式注入Noop；生产工厂不以“没传参数”为由悄悄关闭功能。

## 4. 工具文本捕获与既有上限

### 4.1 双通道，不把全文塞入公开元数据

- 公开通道仍是 ToolResult，保留状态、原 call_id/name、退出码等，以及最终 20,000 字符序列化上限。
- 内部通道是 ToolSource 与 FileReadCapture，仅供 CaptureHub/归档使用；不放进 ToolResult.metadata、TurnEvent 工具预览、异常字符串或供应商 provider_payload。
- 捕获文本在父进程对外使用/归档之前经过合并后的 Redactor。MCP Host 的已有脱敏继续生效，父进程再次校验；不从模型返回的 metadata 构造可信捕获对象。
- `ToolSource.text` 是“工具实际采集到的文本”，不是未执行的文件全量或命令无限输出。原始采集已截断时 `truncated_at_source=True`，所有后续版本必须保留该标记。

### 4.2 普通工具工作进程

在既有 `Tool.execute` 返回、首次最终回灌序列化前，worker 发出绑定 operation_id 的 `capture_begin / capture_chunk / capture_end` 私有帧，再返回按既有最终预算序列化的 result DTO，避免全文再次挤入一帧。ManagedWorker 验证单调序号、总量、身份、终止标记；把捕获交给 Executor 的内部 slot，不改变 `execute()` 原返回类型。原始call_id/name用于外层配对，不能拿被正文预算裁剪的副本替代其身份。

Executor 接到结果立即保存本次捕获，再走已有脱敏/最终结果预算；不能等 `_commit_exchange` 时才找已丢失原文。取消所得未完成输出仍标部分，不反推执行成功。

ReadFile 在同次获准 `_execute` 中记录实际返回片段：每段去掉由显示层添加的行号，仅保留此次确实返回的字符；记录实际范围/BOM/换行/截断。不能在工具结束后重新 `Path.read_bytes`，也不能按行号正则猜任意文件正文。仅成功结果可进入 RecentFileState；失败/取消的捕获不算成功读取。

### 4.3 MCP 通道

ExternalTool 的异步扩展末尾增加可选内部 `capture_sink=None`，旧调用仍成立。Executor 为一次获准调用生成 sink；Adapter/Manager 将 `want_capture` 传到 Host 私有调用帧。

Host 在 `adapt_result` 的最终 `to_model_text` 前提取既有文本/structuredContent 投影，逐帧送出捕获，之后发送原 bounded result。Manager 只接纳当前 Host generation/request ID/execution_key 的帧；业务 isError、非文本省略规则和串行屏障保持。MCP Server 无法选择资料文件名或注册本地文件快照。

### 4.4 内部捕获预算与降级

这些是实现内部有界性，不是新增用户配置：

| 项目 | 上限与行为 |
|---|---|
| capture_chunk | 文本至多 16 KiB UTF-8；封装后单帧至多 128 KiB，不提高原工具 IPC 读取上限 |
| 每次工具额外捕获 | 至多 2 MiB 安全文本；超过时只记录该有界采集片段并明确 capture 不完整，不声称保存全部远端输出 |
| 待处理来源缓存 | 至多 32 MiB 文本；执行前按每项最大捕获量预留，完成后按实际量返还 |
| 捕获队列 | 至多 8 帧，背压而非无限 create_task |
| 文件恢复缓存 | 最多 5 个，每个 17,500 字符；超过就标截断，旧文件记录淘汰不影响对话/归档 |

预留只在Executor完成原有验证、模式/权限/审批及目标复核后、实际启动worker或远端调用前申请；不能把捕获预算判定放在黑名单/权限之前，掩盖原应返回的拒绝。interactive提问仍走既有Broker，不为它预留2MiB工具文本缓存；已接纳答案按自己的小型可信记录处理。

来源缓存无可用预留时，不启动该项实际工具；产出 `CONTEXT_CAPTURE_LIMIT` 结构化结果，使模型在下一轮可调整，已执行结果不得被改成“未执行”。清理或压缩后才可再次获得预留，不擅自重放。测试使用 80KB/240KB 样本须在上述预算内完整捕获，不能靠提高最终模型结果限制换绿。

独立 Host 仍不是恶意 Server 的内存沙箱：SDK 可能在应用限制前缓冲 stdio 数据。本章不宣称该捕获上限等于操作系统资源配额。

## 5. 固定用途 SessionStore

### 5.1 文件布局、原文与可分页视图

资料根固定为 `D:/STUDY/weizhcode-python/.weizhcode/sessions/<session_id>/`；运行在其他项目时同样使用该项目已确认真实根，不使用此示例绝对目录跨项目写入。

```text
<project>/.weizhcode/sessions/<session_id>/
  records/<record_id>.json       # 应用身份、来源、字节数、哈希、截断事实
  objects/<record_id>.txt        # 除已知密钥脱敏外，安全原文的精确 UTF-8
  views/<record_id>.jsonl        # 供 read_file 按行分段读取
  users/page-<number>.jsonl      # 有序用户原文索引，每页最多256条
  .pending/<operation_id>/      # 本次固定用途写入的私有暂存
```

session_id 使用应用随机身份加启动时间；record_id/operation_id 只由应用分配并校验，绝不拼接外部 call_id。失败随机身份生成不退化到可覆盖其他会话的固定名字；归档不可用时保留历史并报告。

视图每行保存 part 编号与最多 1,024 个字符的 JSON text 字段，换行作为转义内容保留；记录明确说明“显示分段不是原文额外换行”。因此超长单行也能通过 start_line/line_count 获取后续部分；原 `.txt` 始终保持精确安全文本，不为阅读而改写原文。

用户单消息归档至多 8 MiB，工具记录受捕获上限约束；超限受控失败并保留原话，不能保存前缀冒称完整。索引页至多 256 KiB、记录元信息至多 64 KiB；正文不进元信息。内存摘要只携带索引路径、覆盖 seq 范围及缺口，不每轮枚举全部用户记录。

### 5.2 Store 公共接口

```python
async def save_text(kind, source_key, safe_text, *, facts, cancel, budget) -> StoreResult: ...
async def verify_refs(refs, *, cancel, budget) -> VerificationResult: ...
async def publish_user_index(records, *, cancel, budget) -> UserIndexRef: ...
def proof_for_registered_path(canonical_path) -> ArchiveReadProof | None: ...
async def aclose() -> CleanupReport: ...
```

StoreResult 区分 `saved / known_failed / uncertain / conflict`。不确定不是已回滚；本次不冻结预览、不提交重型历史。相同 source_key 的已登记引用仅在身份/内容哈希相同时复用，不能仅因文件存在就当成功。

### 5.3 进程、白名单与事务

SessionStore 固定启动自己的 archive_worker；复用当前 OwnedProcess 的进程所有权/Windows Job/POSIX 回收原语，不调用 MCP Manager，不传 Provider 凭据或信任 key，不把任意模块名暴露给模型。

worker 只接受 `save_record / verify_records / publish_index / inspect_commit`；参数为固定会话、应用 ID、数据块和期望摘要，不接受任意读写路径、shell、工具名或网络地址。私有帧带 version、worker ID、request ID、operation ID，限 128 KiB，流式传输有界数据。

复用的OwnedProcess接收白名单须显式追加归档响应及捕获帧类型；每个调用方仍按自身用途/状态验证，不能仅凭通用白名单接受消息。归档worker不会因此拥有MCP connect/call能力，MCP目录阶段也不得接纳工具捕获帧。

单个 IO 操作预算 5 秒；调用方绝对期限更短时取更短值。父进程取消时终止和回收，额外清理预算最多 2 秒且纳入上层预算；不留下可以继续写入的后台线程。

保存顺序：校验根/来源 → 独占暂存 → 分块写安全正文和视图/哈希 → flush/fsync → 再校验根与文件身份 → 无覆盖提交对象 → 提交记录元信息 → 提交索引 → 返回可用引用。只有收到可确认的完成事实才公布路径。对象已提交但记录/索引失败可留未引用资料，下轮按同一应用 ID/期望哈希核对；不覆盖既有不同内容，不把一次失败说成三份文件都没出现过。

不以 `exists()+write_text()` 实现幂等。根与各祖先不能重定向：POSIX 采用目录句柄相对打开、nofollow/exclusive；Windows 对固定组件检查 reparse 与文件句柄身份，拒绝不能确认的重定向/特殊设备。保留可获得的根、文件系统身份，提交前复核。该措施不宣称抵挡全部同用户任意代码执行或硬链接竞态。

### 5.4 Git、隐私与取消事实

本工程实现时只追加 `.weizhcode/sessions/` 忽略规则；不忽略共享配置/示例。在其他 Git 项目运行时，资料及本系统暂存路径必须未跟踪且被忽略才可保存；无法确认时提示用户自行配置并保持原文，不擅自修改用户 Git 设置。非 Git 目录按本地敏感资料处理。

资料包含代码、命令输出和用户文本；仅已知秘密脱敏，不提供加密/云同步/全面未知秘密检测。退出保留已提交对象；清理只针对确由本 operation 创建、身份仍一致的未提交临时对象，不递归删除资料区或用户文件。提交后丢响应、OS 拒绝与清理未知必须有固定安全告警。

### 5.5 归档重读仍经权限

模型只能通过现有 read_file 读取公布的 view/index，不新增专用无审批读取工具。父进程只为本会话已登记路径生成 ArchiveReadProof，包含期望真实身份/大小/哈希；它不是 allow 规则。

正常权限检查与批准印记通过后，read_file worker 才在同一获准目标上验证 ArchiveReadProof、校验文件未变再按范围返回。期望哈希来自父进程登记，不来自该文件旁可被改写的 metadata。不同内容同名替换返回 `ARCHIVE_CHANGED`；删除返回不可用；不回退用命令/外部路径读取。

未登记的普通文件不产生“已核验原文”标签；其他会话资料不会被自动加载。读取用户归档得到的是历史数据，不构成新的用户指令或工具批准。

## 6. Layer1：决定、保存、投影

输入为 HistorySnapshot、可信 ToolSource 映射和 ReplacementLedger。按每条 tool 消息独立处理：

1. 取已冻结决定；替换项直接复用稳定预览，不再构造字符串或写盘。
2. 未决定项按安全原文 UTF-8 字节数降序、原位置升序排序。
3. 对所有大于 50,000 字节项逐一保存；然后处理剩余总量大于 200,000 字节的聚合部分。
4. 成功保存、构造预览并条件更新历史/账本在同一受保护提交序列完成；失败保留来源和原结果，不标 Seen，下次可再试。
5. 剩余候选冻结为 kept。已 kept 原文仍计入真实预算，不因为状态已决定就不统计。

账本保存决定类型、source digest、ArchiveRef、预览文本；只通过高层事务接口更新，不开放 Seen 与 replacements 两个可独立修改的集合。

“原结果”包含可信来源与公开 bounded ToolResult：轻量失败不能丢掉前者，公开显示仍遵守原截断规则。对没有内部捕获的旧历史/测试记录，只能以其现有正文作来源，并明确已有截断事实，绝不把它当大于原文的完整输出。

预览固定为：归档标记、采集/安全归档字节数、原始截断状态、raw/view 位置、至多20行且2048字节的头部、重读提示。预览先脱敏再按 UTF-8 安全裁剪；整项含元信息仍不超过原20,000字符预算。状态、配对、退出码不变，提供 stable projection 给所有 Provider 的原生序列化。

重型流程淘汰较早工具交换时，为仍可获取的安全来源补存历史资料；这不改变 kept 的轻量决定，不在仍保留的消息上翻转 kept 为 replaced。若只能得到旧截断正文，归档明确 partial，不补采或重执行工具。

## 7. 请求准备、估算与输出预留

### 7.1 估算与发送只使用一份准备结果

Provider 增加纯准备与发送接口，旧 stream_chat 保留为便捷包装：

```python
@dataclass(frozen=True)
class RequestOptions:
    purpose: Literal['chat', 'summary'] = 'chat'
    allow_tools: bool = True
    max_output_tokens: int = 4096

@dataclass(frozen=True)
class PreparedRequest:
    request_id: str
    purpose: str
    protocol: str
    body_json: str  # repr=False；深拷贝后规范JSON，不暴露可变dict
    message_projections: tuple[str, ...]  # repr=False；实际协议投影
    fixed_projection: str  # repr=False；系统/动态补充/工具定义等
    fixed_digest: str
    tools_digest: str
    output_reserve: int

def prepare_request(messages, *, tools, prompt_context, options, redactor=None) -> PreparedRequest: ...
async def stream_prepared(request: PreparedRequest) -> AsyncIterator[ProviderEvent]: ...
```

PreparedRequest 不含可打印认证头；认证仍由 Provider 内部构造。生产准备路径传入Runtime最终合并的Redactor，先对出站副本应用统一秘密脱敏，不能只使用Provider自身模型key的小集合；不因此改写Conversation中尚未归档的用户原话。Body 不允许发送前再追加环境、提醒、工具或更换 max_tokens。Collector 使用同一个 PreparedRequest，不为发送重新计算一份消息列表。

原有 stream_func 注入和 HTTPX/SSE 路径保留，便于抓真实 body 离线测试；旧 FakeProvider 可通过 Noop 管理路径或测试适配器保持原接口，新上下文集成测试使用具备纯准备接口的替身/真实 Provider 加假传输。

### 7.2 实际投影与锚点

估算投影覆盖真正出站字段：正文、工具参数/结果 JSON、工具定义、稳定指令、环境、提醒、恢复信息、以及必须重放的原生签名/加密块。只取 body 中模型输入相关字段，不把认证头、内部 capture、日志或输出 Token 数字当正文。

没有有效锚点时：`ceil(input_projection_chars / 3.5)`，不以 UTF-8 字节替代字符。结构化分隔也计入投影，以确定性紧凑 JSON 表达；估算仍是近似，不虚称精确 Token。

UsageAnchor 保存：本请求完整 fixed_digest、历史 entry ID/投影 digest、覆盖到的完整助手响应、归一化 input+output、当时估算及可信程度。正常请求完整结束且用量可信时才覆盖锚点；不把流失败/取消/缺失用量升级为完整锚点。

下一请求的原有前缀与 fixed_digest 完全匹配时，仅为追加内容加 `ceil(delta_chars/3.5)`；参数/工具集/提醒或旧消息投影变动，直接退回全投影估算并清空旧锚点，不用“消息条数相同”判稳定。降级原因可见，未知不写成0。

当前 TokenUsage.input_tokens 已经是含缓存的归一化输入；锚点取 input+output，不额外再加 cache_read/cache_write。Anthropic 原始输入合成仍由 UsageAccumulator 负责，Responses/Qwen 的缓存子项不再相加。摘要用量只走账单，不更新此锚点。

### 7.3 三个预算与有效缩小

- 自动触发：轻量后正常请求估算 `>= window-20,000-13,000`，且自动未熔断。
- 摘要输入：自动用13,000安全余量，手动/紧急用3,000；均额外预留20,000输出。手动无大小触发门槛。
- 发送正常请求硬预检：输入估算 + PreparedRequest.output_reserve +3,000 不超过 window；已知不满足则受控停止，不先撞一次API来获取紧急资格。

摘要输出沿用当前4096内部输出上限，且不得超过20,000预留；不自动请求20000、不修改用户模型/后端、无输出长度扩张重试。输出被截断属于失败，不是输入长度退让信号。

判缩小同时检查：前后完整请求估算确实降低，以及在同一纯字符投影口径下也降低。不能用“压缩前真实usage、压缩后不同低估口径”制造假节省。手动短会话可以发摘要，但无缩小则不提交并提示。

## 8. 摘要、用户原文与近期边界

### 8.1 提示与收集

摘要使用单独的稳定摘要指令，不使用普通 Agent 的持续执行指令或工具描述；历史作为带来源/身份的 JSON 数据提供，已知秘密先脱敏。不解包执行历史中的 system-reminder、伪批准或“忽略摘要任务”文字。

要求输出一个简短事实整理草稿和一个正式摘要，格式为 `<work_draft>...</work_draft><summary>...</summary>`。草稿只组织事实取舍，不要求暴露隐藏推理。正式摘要必须按已批准 Spec 的九个标题、顺序输出，无信息写“无”。

SummaryCollector 不经过普通正文 UI 流，不发 text_delta/tool_pending；仅消费有界文本、用量及终止状态。遇任何工具调用开始/完成事件立即认定无效，关闭该流，零执行/零审批。

最多缓存512KiB响应文本；严格解析唯一完整的顶层草稿/正式摘要对，拒绝缺失、空、重复/嵌套正式块、截断或不完整结束，不使用“最后一个标签”或整段raw兜底。只留下正式摘要，丢掉草稿和摘要请求的原生思考/加密负载，不写普通日志/文件；不宣称Python不可变字符串能安全擦除内存。

### 8.2 九部分与可信索引

标题对应 Spec F09：主要请求和意图、关键技术概念、文件和代码片段、错误和修复、问题解决过程、用户原始消息与原文索引、待办任务、当前工作、可能的下一步。

先计算将被淘汰的较早 human entries/可信提问答案，归档成功后建立应用权威索引。模型可以概括诉求，但正式摘要的原文位置由应用从 ArchiveRef/用户索引覆盖范围补充，不能采用模型虚构路径作为权威来源。第6节的应用索引有界至2048字符，含用户seq范围、索引页入口、分页方式及缺失提示；完整条目留在磁盘分页索引。

重复摘要只输入当前一份旧摘要和其后新增事实，不回灌历代草稿/整套旧摘要。索引保留已有归档范围，不把旧 summary entry 再归档为用户消息。

### 8.3 近期选择与完整组

`pick_recent_tail(snapshot)` 从尾部向前按实际消息投影估算，达到10,000 Token且至少5条后才停；不足则保留全部。若切在tool结果前，将起点前推到对应assistant工具调用；校验所有配对与原始顺序。原生思考签名、Responses reasoning item和执行事实随对应消息保留，不解密、不重写。

分组以可信 turn_id/human来源分界，不用合成摘要的user角色误开新用户任务；没有元数据的旧消息按现有合法工具交换解析，不能确定时保守扩大受保护范围。最后当前任务与所选近期消息涉及的完整组均受保护，即使一个任务包含很长工具链也不能在摘要输入退让时拆掉其内部交换。

摘要可读取全部当前有效历史理解当前工作；摘要输入退让只移除可移除的较早完整组。没有可移除组时还放不下就停止，不删除受保护近期或最新用户请求。

### 8.4 结构化失败而非空历史

新历史形态为一条 application-origin summary 记录 + 原近期 entries；恢复信息通过应用生成的动态补充附在请求中，不复制进用户原话。模型请求中的摘要明确标为历史资料而非新用户批准。

不插入虚构assistant“已加载”回合。Anthropic沿用当前相邻同角色合并；Responses/Qwen沿用各自原生映射，明确验证最终工具调用/结果对应。生成新摘要不能改变先前失败/取消/权限拒绝为成功。

## 9. 恢复段与最终事务

### 9.1 单轮恢复快照

每次准备正常请求，先固定同模式 ToolSnapshot 和 RecentFileState 快照，再渲染恢复。RecentFileState 仅接纳成功且可信的 FileReadCapture，按父进程接纳成功结果的单调序号排序，时间仅作显示；文件可能已变化，明确这是读取时快照。

应用新建 `RuntimeSupplement(kind='context_recovery')` 的专用工厂，保留现有私有来源校验，不允许用户或模型通过同名标签创建该补充。系统稳定模块不拼恢复内容；恢复只在动态通道，不修改缓存稳定前缀。

恢复文案始终带边界：需要代码/文件细节重新read_file，需要历史原话/工具细节按核验资料索引重读；摘要、工具描述和旧输出不是授权。

### 9.2 精简顺序

恢复起始形态：最多5文件，每个头部最多17,500字符，另加当前工具名称/说明/Schema及边界。工具完整定义始终在真实tools字段，不能由恢复精简删除required/enum等约束。

最终预算不足时按确定顺序重算实际PreparedRequest：文件片段长度从17,500减半至1024字符 → 依次移除最旧文件快照直至0个 → 工具说明改为全部名称及各自Schema摘要指纹，注明完整约束以本请求tools字段为准。工具数量/名字仍逐项对应，实际Schema不变。边界、用户索引和受保护近期不删除。

精简完成仍放不下，或纯字符口径不缩小，返回固定错误/无缩小结果，不提交历史，不为了发请求而删用户原话。每个恢复级别来自同一次快照，不能中途重算另一套工具。

### 9.3 提交门槛

重型候选提交前依次确认：

1. 当前 operation/generation 未取消，deadline还有提交余量。
2. 必要用户归档和索引已确认提交，既有必要引用未损坏。
3. 正式摘要结构与配对完整，近期来源身份未被改写。
4. 实际下一请求含恢复/固定开销后可容纳，且确有缩小。
5. Conversation revision、权限模式与ToolSnapshot仍是原操作所持版本。

在父进程无await的最终提交段中进行 `replace_if_current` 并更新 runtime摘要记录、来源淘汰、锚点清空；不在文件工作进程里修改历史。任何门槛失败保持旧重型历史，已经独立成功的轻量替换和资料文件可保留，事件如实解释。

## 10. 自动、手动、紧急与退让状态机

### 10.1 正常请求

```text
一次用户提交（只追加一次）
  → 固定当前任务/工具/提示快照
  → Layer1（每次普通请求前，首次有损截断前已保有来源）
  → PreparedRequest + 估算
  → 达自动阈值且未熔断？
      否：硬预检 → 正常请求
      是：compact_started(auto)
           → 归档较早用户原话/必要资料 → 摘要 → 恢复/预算 → 条件提交
           → compact_finished / failed
           → 可容纳才正常请求；否则本轮受控停止
  → 正常流完整成功后更新主锚点；工具仍按原门禁执行
```

不能在轻量前按旧估算发“正在摘要”假事件。一次before_request最多一轮自动重型操作；不因估算仍高在同一请求前反复压缩。

### 10.2 手动入口

Runner 增加 `force_compact() -> AsyncIterator[TurnEvent]`，同步认领busy并创建本操作Context/事件通道；不调用run，不追加用户消息，不拿“等主任务结束”的队列替代拒绝忙碌。空历史直接no-op提示。

非空则跳过额外Layer1、自动阈值、熔断判断；保留已有预览，必要用户归档仍执行。统一phase事件、取消、用量和资源收尾，完成后释放busy、恢复草稿/焦点。无缩小保持旧历史，不说“压缩成功”。

### 10.3 长度错误与一次紧急重试

当前普通请求明确失败且 fault.kind=context_length 时，在同一Agent迭代设置 `emergency_retried`：

- 如尚未重试，发紧急开始事件，同一120秒操作预算内先确保Layer1再强制摘要，不看自动熔断。
- 成功重建后重新prepare实际请求并硬预检，再用新request_id重试原请求一次。此重试不新增用户entry、不重新执行已完成工具、不增加普通迭代计数。
- 已重试仍失败、强制摘要失败或硬预检不通过，按本轮错误结束；没有第二次紧急压缩。
- 失败流已显示的部分正文/工具待定行标为未完成，不提交其不完整assistant或执行其工具；真正已确认的上一轮工具交换完整保留。

### 10.4 摘要输入退让

一次操作维护 attempts、reduction_step、绝对deadline与 omitted_turn_ranges。先预检包含摘要指令/JSON包装/索引的实际摘要请求；超过预算先缩候选，不白发。

每步只移走可移除较早完整组：前3步各1组，之后每步ceil(剩余可移除组数×0.2)，至少1组。预检退让与服务器长度错误共用该递减序列，不能各自重置计数。每个实际摘要尝试计入12次总上限，所有I/O/请求/收尾受同一120秒期限约束，预留最后2秒清理。

普通错误、无效结构、输出截断不走此长度重试；无可移除组、达到总次数/时限或取消即结束。临时移走的范围在正式摘要/应用边界中标为未纳入本次摘要，并给原资料索引，不假称覆盖。

### 10.5 熔断与结果分类

只在一次完整自动重型操作最终结束时更新：完成且已提交→清零；失败/无缩小/内部长度重试耗尽→加1；取消→不改。达到3次后跨后续用户任务停止自动重型操作，Layer1仍可运行。

手动/紧急路径不读写自动计数；成功不暗中复位已熔断状态。自动失败后若正常硬预检仍通过可继续任务；否则受控停止，不能为凑3次失败发送已知超大的请求。

## 11. Provider错误、结束状态与用量

### 11.1 结构化分类

ProviderEvent 在末尾追加可选 fault/finish_reason 字段，保持原位置参数兼容；StreamState 保留分类而不是把所有异常丢成一段文案。ProviderFault 只含 protocol、safe_code、http_status、kind、param、固定安全说明，不保存可打印原认证头/响应全文。

SSE HTTP失败先有界读取至64KiB错误正文，再解析结构化error；超量/非法正文为普通错误，不输出完整正文。分类优先级先排除401/403/429/5xx和传输故障，再看明确长度信号。

| 后端 | 长度信号 | 不算输入过长 |
|---|---|---|
| Anthropic | HTTP400/流结构化invalid_request_error且明确匹配已知prompt-too-long说明；或明确model_context_window_exceeded结束原因 | 泛invalid_request_error、max_tokens输出截断、refusal、pause_turn、错误参数或认证/额度 |
| OpenAI Responses | 明确context_length_exceeded代码；适用HTTP400或已识别流error来源，不能从任意正文片段触发 | incomplete_details.max_output_tokens、content_filter、泛invalid_prompt、网络/权限/额度/限流 |
| Qwen兼容Chat | 明确context_length_exceeded；或HTTP400的受认可参数错误类型与严格输入长度格式共同命中 | 所有InvalidParameter直接放行、max_tokens参数范围、finish_reason=length、额度/激活/内容类型错误 |

未知兼容错误保留unknown，不使用模糊“包含long/length”正则。测试必须覆盖400非长度、输出上限、401/403/429/500、恶意正文带关键字，以及HTTP与流内两种路径。OpenAI不切换到Agents API或其他接口来获取错误分类。

### 11.2 请求与完整性

summary目的使用空tools且allow_tools=False；Responses显式禁自动输入截断，保持store=False；其余协议不增加未经确认的供应商压缩扩展或自动续写参数。兼容端点拒绝标准字段时正常报错，不删除安全字段后悄悄重试。

Claude须完整合法结束且摘要无工具；Responses只接受completed，incomplete/failed与理由保留；Qwen必须完整终止且finish_reason正常。输出截断/安全拒绝不能作为正式摘要成功，也不能触发输入长度退让。普通任务extended thinking及必须原样重放的签名/加密块不改写；摘要本身的新原生负载不写进Conversation。

### 11.3 用量统一结算

所有正常/摘要/紧急重试请求有不同request_id与purpose；沿用原usage累计快照合并，按请求只settle一次。摘要开始/失败/取消均可收集已报告的部分usage，不为取用量重开API请求。

会话总量含摘要成本，事件另带purpose和触发原因；只有完整可信主对话请求可更新主估算锚点。未报告保持missing/不完整，不捏造零，也不重加缓存子项。

## 12. TUI、提示工厂与关闭

统一空闲命令注册 `/exit`、`/quit`、`/plan`、`/do`、`/compact`。退出别名仍存在；未知斜杠命令不进入模型。处理顺序先原退出/取消生命周期、再审批/提问通道、再忙碌门禁、最后空闲命令与普通文本，不抢走需求答案。

`/do` 可生成旧应用执行指令，但原始命令不作为human原话重复归档。Shift+Tab及模式切换在compact忙碌期间拒绝，与普通任务一致。

TurnEvent 末尾追加可选 CompactionNotice，不把Exception对象放入事件；开始、完成、失败/取消按operation_id匹配，旧事件不能清理新菜单或草稿。文案明确auto/manual/emergency，估算字段缺失显示未知，不打印假“降到0”。层一仅有磁盘整理时可显示轻量状态，不冒称正在调用摘要。

UI不销毁旧消息/工具scrollback，不展示摘要草稿；模型历史已被替换时可追加边界提示。压缩失败保留草稿，结束恢复输入焦点；成功可能增加模型费用的说明放在README/启动使用说明，不暗示免费。

Runner.aclose先冻结新任务、取消当前普通/手动上下文、补齐原工具配对与结算，再关ContextManager/SessionStore，最后继续既有Executor/MCP/权限收尾；都使用共享幂等关闭Future，不互相等待自身任务。120秒是操作预算，不把OS拒绝或无法确认的清理说成硬实时成功；未知对象/提交如实报告且禁迟到历史更新。

## 13. 文件组织与改动范围

以下为未来实现文件清单，不代表本轮已创建。所有路径在本项目根内；测试只用tmp目录，不读 `.weizhcode-test/`、`hello.txt`、真实模型/MCP配置及真实用户权限/信任文件。

### 13.1 新增核心模块

| 完整路径 | 职责 |
|---|---|
| D:/STUDY/weizhcode-python/src/weizhcode/compact/__init__.py | 轻量公共导出，不做I/O |
| D:/STUDY/weizhcode-python/src/weizhcode/compact/contracts.py | 身份、来源、引用、结果、请求帧等只读契约 |
| D:/STUDY/weizhcode-python/src/weizhcode/compact/limits.py | Spec常量与内部处理预算 |
| D:/STUDY/weizhcode-python/src/weizhcode/compact/state.py | SessionRuntime、账本、快照与自动计数 |
| D:/STUDY/weizhcode-python/src/weizhcode/compact/capture.py | 可信内部CaptureSink/Hub与worker捕获上下文 |
| D:/STUDY/weizhcode-python/src/weizhcode/compact/archive.py | SessionStore、固定进程、提交状态及引用登记 |
| D:/STUDY/weizhcode-python/src/weizhcode/compact/archive_worker.py | 固定归档白名单与有界IPC，不执行模型工具 |
| D:/STUDY/weizhcode-python/src/weizhcode/compact/archive_fs.py | 根/重定向/身份校验、独占保存、核验及索引事务 |
| D:/STUDY/weizhcode-python/src/weizhcode/compact/history.py | 原子历史候选、用户/工具分组、近期边界 |
| D:/STUDY/weizhcode-python/src/weizhcode/compact/estimator.py | 实际协议投影、usage锚点与失效规则 |
| D:/STUDY/weizhcode-python/src/weizhcode/compact/layer1.py | 单项/聚合归档和稳定预览 |
| D:/STUDY/weizhcode-python/src/weizhcode/compact/summary.py | 独立摘要收集、解析、有界长度退让 |
| D:/STUDY/weizhcode-python/src/weizhcode/compact/prompts.py | 摘要九部分与固定边界文本 |
| D:/STUDY/weizhcode-python/src/weizhcode/compact/recovery.py | 单轮文件/工具/边界恢复及预算精简 |
| D:/STUDY/weizhcode-python/src/weizhcode/compact/manager.py | 正常/手动/紧急编排、预算、CAS提交 |
| D:/STUDY/weizhcode-python/src/weizhcode/compact/factory.py | 生产Runtime装配，接收已选窗口/真实根 |
| D:/STUDY/weizhcode-python/src/weizhcode/providers/request.py | RequestOptions/PreparedRequest纯准备通用契约 |
| D:/STUDY/weizhcode-python/src/weizhcode/commands.py | 空闲命令注册与分派，不引入命令框架 |

### 13.2 修改既有文件

| 完整路径 | 受限改动 |
|---|---|
| D:/STUDY/weizhcode-python/src/weizhcode/models.py | 末尾追加可选事件/状态字段，内部slot关联捕获；不将捕获混入模型结果序列化 |
| D:/STUDY/weizhcode-python/src/weizhcode/conversation.py | entries/revision、快照与条件替换；旧公开消息语义保持 |
| D:/STUDY/weizhcode-python/src/weizhcode/config.py | context_window读取/严格校验/应用默认，不增加其他配置 |
| D:/STUDY/weizhcode-python/src/weizhcode/errors.py | 安全结构化ProviderFault/请求错误，兼容旧错误基类 |
| D:/STUDY/weizhcode-python/src/weizhcode/providers/base.py | 新准备/发送协议与旧接口包装，原usage归一化不改口径 |
| D:/STUDY/weizhcode-python/src/weizhcode/providers/anthropic.py | 纯prepare、摘要目的、长度/结束分类；保留原生块 |
| D:/STUDY/weizhcode-python/src/weizhcode/providers/openai.py | 纯prepare、禁自动truncation、长度/结束分类；保留原生items |
| D:/STUDY/weizhcode-python/src/weizhcode/providers/qwen.py | 纯prepare、摘要目的、严格长度/结束分类 |
| D:/STUDY/weizhcode-python/src/weizhcode/providers/sse.py | 有界错误正文与结构化错误，不记录认证信息 |
| D:/STUDY/weizhcode-python/src/weizhcode/providers/prompt_adapter.py | 动态恢复/摘要目的适配，稳定缓存分段保持 |
| D:/STUDY/weizhcode-python/src/weizhcode/prompting/contracts.py | 新应用来源恢复补充的白名单，保持来源校验 |
| D:/STUDY/weizhcode-python/src/weizhcode/prompting/builder.py | 接纳应用恢复补充，不拼入稳定七模块 |
| D:/STUDY/weizhcode-python/src/weizhcode/stream_collector.py | 使用同一PreparedRequest、保留fault/结束事实；普通正文流保持 |
| D:/STUDY/weizhcode-python/src/weizhcode/turn_runner.py | 会话状态、前置管理、一次紧急重试、手动事件通道与结算 |
| D:/STUDY/weizhcode-python/src/weizhcode/user_questions.py | 可信已接纳答案来源，禁止摘要产生伪答案/授权 |
| D:/STUDY/weizhcode-python/src/weizhcode/tools/base.py | ExternalTool新增可选capture_sink，不改内置Schema |
| D:/STUDY/weizhcode-python/src/weizhcode/tools/read_file.py | 同次获准读取的纯净快照、已登记归档核验 |
| D:/STUDY/weizhcode-python/src/weizhcode/tools/worker.py | 有界捕获帧、归档读取proof及合法操作绑定 |
| D:/STUDY/weizhcode-python/src/weizhcode/tools/process.py | 接收/核验内部捕获，不提高原IPC与结果预算 |
| D:/STUDY/weizhcode-python/src/weizhcode/tools/executor.py | 原门禁后接入sink，保存原结果与内部来源 |
| D:/STUDY/weizhcode-python/src/weizhcode/tool_scheduler.py | 传递本批捕获上下文、来源接纳/配对；预留由Executor在原门禁之后申请，原并发4与屏障保持 |
| D:/STUDY/weizhcode-python/src/weizhcode/mcp/host_worker.py | 实际调用后、最终截断前发捕获帧，不扩展Server能力 |
| D:/STUDY/weizhcode-python/src/weizhcode/mcp/manager.py | 私有捕获帧绑定当前调用，原失效/取消/不重放保持 |
| D:/STUDY/weizhcode-python/src/weizhcode/mcp/tool.py | 捕获原投影后保持旧结果上限与文本/非文本语义 |
| D:/STUDY/weizhcode-python/src/weizhcode/mcp/process.py | 仅扩充受管进程的私有帧白名单，保持所有权/有限关闭；各用途独立校验 |
| D:/STUDY/weizhcode-python/src/weizhcode/cli.py | 普通/MCP两装配分支统一注入生产Runtime |
| D:/STUDY/weizhcode-python/src/weizhcode/tui.py | 手动命令、phase显示、草稿/焦点/取消及后备构造 |
| D:/STUDY/weizhcode-python/weizhcode.yaml.example | 可选context_window示例；不改真实weizhcode.yaml |
| D:/STUDY/weizhcode-python/.gitignore | 仅追加本系统sessions资料路径 |
| D:/STUDY/weizhcode-python/README.md | 新命令、费用、窗口默认、归档隐私与实际边界 |

若实现中发现需要上述范围外的生产改动，先说明具体文件和原因；不借上下文管理重构整个Provider/权限/MCP系统。

## 14. 技术决策摘要

| 决策 | 选择与理由 |
|---|---|
| 长状态归属 | 沿用常驻Runner拥有Runtime，避免跨任务丢账本/锚点/熔断 |
| 身份 | 应用entry/执行/记录身份分层，不把远端call_id变成本地路径 |
| 结果保真 | 私有捕获与有界公开结果双通道，不拆掉旧安全预算 |
| 原话 | 精确安全正文+分页视图+有界索引，不把所有旧原话塞回每次请求 |
| 文件恢复 | 已批准同次读取的纯文本，不再读取或猜行号正文 |
| 估算 | 实际PreparedRequest投影，归一化usage只计一次，旧锚点不匹配即降级 |
| 摘要权限 | 独立目的/空工具/硬拒意外调用，不能触发原工具执行入口 |
| 近期边界 | 双下界且配对完整，过大受控失败而非静默丢用户内容 |
| 资料I/O | 固定用途受管进程，提交事实与超时分离，不无限等待线程 |
| 恢复 | 动态应用补充，工具/文件同轮快照，稳定提示不污染 |
| 事务 | 本地文件可分步提交，但公开引用与历史用CAS统一确认，取消不虚称回滚 |
| 错误与重试 | 明确长度信号才紧急；普通请求一次、摘要12次/120秒，共用递减状态 |
| 依赖 | 不加tokenizer/LLM SDK/数据库，继续使用现有HTTPX与MCP SDK |

## 15. 验证设计与需求覆盖

本节是后续Task/Checklist的依据，不是已执行证据。所有自动测试默认禁止生产网络/真实配置读取。

| 验证组 | 明确测试文件（项目根 D:/STUDY/weizhcode-python/） | 主要覆盖 |
|---|---|---|
| V01 契约/状态 | tests/compact/test_state.py、tests/test_conversation.py | F01/F02/F05/F18，来源隔离、CAS、旧位置参数、跨任务保持 |
| V02 捕获 | tests/compact/test_capture.py、tests/test_tool_executor.py、tests/test_mcp_tool.py | F03/F04/F11，真实首次截断前捕获、不同通道、伪帧、部分结果 |
| V03 归档 | tests/compact/test_archive.py、tests/compact/test_archive_process.py | F01/F02/F05/F21，精确正文/分页、链接/冲突、Git、坏资料、取消及未知提交 |
| V04 轻量 | tests/compact/test_layer1.py | F03/F04/F05，UTF-8边界、单项/聚合、原文/预览冻结、失败重试 |
| V05 估算 | tests/compact/test_estimator.py、tests/test_cache_usage.py | F06，实际body、三协议缓存归一化、增量不重计、锚点失效 |
| V06 摘要/近期 | tests/compact/test_summary.py、tests/compact/test_history.py | F08/F09/F10/F17，九部分、拒草稿兜底、配对/签名、保护范围、递减上限 |
| V07 恢复/事务 | tests/compact/test_recovery.py、tests/compact/test_manager.py | F07/F11/F12/F13/F18，快照/模式、无缩小、原文缺失、原子提交与熔断 |
| V08 三协议 | tests/test_context_protocols.py、tests/test_provider_events.py、tests/test_protocol_integration.py | F06/F08/F16/F19，抓实际请求体、空tools、fault、完成/截断、用量 |
| V09 Runner闭环 | tests/test_context_integration.py、tests/test_turn_runner.py、tests/test_tool_scheduler.py | F07/F14/F16/F17/F18/F19，真实本地工具/MCP+fake模型、只重试请求、不重放工具 |
| V10 UI/命令 | tests/test_context_tui.py、tests/test_tui.py、tests/test_user_questions.py | F14/F15/F19，busy、草稿、旧菜单、数字/取消、无草稿泄漏、scrollback |
| V11 配置/装配 | tests/test_config.py、tests/test_cli.py、tests/test_mcp_bootstrap.py | F20，三默认、严格非法值、两装配路径与后备构造、不读生产配置 |
| V12 原生/完整回归 | 上述文件 + 原tests全套 | N1～N8；Windows/POSIX分别记录，故障不是删断言或默认BYPASS换绿 |

测试文件名是将要创建/扩展的准确位置；Task会给每组具体用例与命令，不能用不存在的-k选择器或0收集作为通过。当前无Ruff/mypy配置，不在实现时临时安装来伪报已有工程检查。

必须覆盖的边界包括：50,000等于/超1、200,000等于/超1、20行/2048字节的中文边界、六条40KB聚合、三条80KB单项、2MiB捕获、32MiB预算、8MiB用户归档、长单行分段、九标题/标签注入、120秒与12次先到、33,000配置边界、模糊错误反例、原生协议原始配对及退让不删除近期。

### 15.1 逐条验收映射

| Spec标准 | Plan归属 | 验证组 |
|---|---|---|
| AC01 | 3、5：身份、跨任务状态、懒创建 | V01/V03 |
| AC02 | 5、8：原话/有界索引、多次摘要来源 | V01/V03/V06 |
| AC03 | 5、9：保存失败/坏记录禁止移除原话 | V03/V07 |
| AC04 | 4、6：首次截断前捕获及真实出站投影 | V02/V04/V08 |
| AC05 | 6：单项与聚合独立触发 | V04 |
| AC06 | 3、5、6：幂等、冲突、冻结与重试 | V01/V03/V04 |
| AC07 | 5、6：UTF-8预览及安全路径 | V03/V04 |
| AC08 | 7、11：usage归一化与覆盖锚点 | V05/V08 |
| AC09 | 7：轻量后估算、锚点失效/降级 | V05/V07 |
| AC10 | 7、10：自动阈值与真实进行中状态 | V07/V09 |
| AC11 | 8、11：摘要零工具与草稿隔离 | V06/V08/V10 |
| AC12 | 8、9：九部分/无效输出禁止提交 | V06/V07 |
| AC13 | 8：近期双下界及原生配对 | V06/V08 |
| AC14 | 4、9：同次成功读取与有界快照 | V02/V07 |
| AC15 | 7、9：同轮工具快照与模式边界 | V07/V08 |
| AC16 | 7、9：重建总预算与无缩小 | V07 |
| AC17 | 10、12：手动绕阈值、空会话/无缩小 | V09/V10 |
| AC18 | 10、12：命令、busy、原交互兼容 | V09/V10/V11 |
| AC19 | 10、11：紧急一次请求重试、不重放工具 | V08/V09 |
| AC20 | 10、11：长度分类反例及不可恢复停止 | V08/V09 |
| AC21 | 8、10：完整组退让及保护近期 | V06/V09 |
| AC22 | 5、10、12：总次数/时限/取消 | V03/V06/V09 |
| AC23 | 3、10：自动熔断与强制路径隔离 | V01/V07/V09 |
| AC24 | 11、12：状态、usage分账与迭代不混计 | V08/V09/V10 |
| AC25 | 3.4、13：窗口配置、默认与示例 | V11 |
| AC26 | 5：原门禁、核验原文及可分页视图 | V03/V09 |
| AC27 | 3、5、9：有界处理、互斥与条件提交 | V01/V03/V07/V12 |
| AC28 | 5、11、12：隐私、取消与清理事实 | V03/V08/V10/V12 |
| AC29 | 11、13、15：现有能力/完整离线回归 | V08/V09/V10/V11/V12 |
| AC30 | 7、10、15.2：长任务与超大近期受控停止 | V09/V12及单独现场观察 |

### 15.2 手动入口与真实验证分层

新增未来入口 `D:/STUDY/weizhcode-python/tests/manual_context_smoke.py`：

- 默认/--help仅离线说明，不读真实凭据/配置、不造真实会话资料、不调用API。
- --terminal使用临时root/home、fake模型、本地工具/回环MCP，支持长结果、用户原话归档、三种压缩、取消与重读，终端退出保留/清理由入口说明且只针对拥有的临时样本。
- --live与terminal互斥，先说明实际域名/协议/模型、只允许的临时操作、摘要及重试上限和可能费用，再要求真实确认；未授权不运行。真实终端观察不被Pilot替代，真实模型不被fake计数替代。

开发阶段不做真实收费调用；后续Checklist必须分别列实现、离线、原生平台、真实终端、真实模型、未验专项，不能把全量通过数当所有组合已验。

## 16. 审批与实施边界

本 Plan 已整份批准；当前只生成 Task，再单独生成 Checklist，四份均批准后才改业务代码。

本轮不创建资料目录、不加载真实weizhcode.yaml/MCP配置、不启动IO/工具/Server进程、不调用收费模型、不处理用户既有会话文件、不安装依赖、不提交或推送Git。未执行上一阶段仍待验项目，不把它们追认为本章通过。
