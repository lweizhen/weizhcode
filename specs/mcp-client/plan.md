# weizhCode MCP 客户端 Plan

> 状态：四份文档均已批准；本设计已接入生产启动与工具流程。离线完整回归723 passed、4 skipped；本文仍非全部验收证明，证据及待验边界见Task/Checklist。
> 日期：2026-11-17。只更新本阶段文档，不安装依赖、不启动 Server、不连接生产服务。
> 基线：Python 3.11+、HTTPX、Textual、PyYAML、jsonschema，以及当前工具进程、权限 Engine、ApprovalBroker、ToolScheduler、TurnRunner。

## 1. 架构概览

### 1.1 当前落点与必要改动

当前 `Tool` 是同步 prepare/execute 接口，普通工具经临时 worker 执行；worker 自行创建六个内置工具的 registry，不能拿到主进程里的长连接。权限 Engine 只认识固定六种身份，registry 的模式筛选也只放行固定工具。因此不能只注册对象就声称完成 MCP 接入，也不能把会话复制到每次新建的工具进程。

采用“主进程统一编排 + 每个 Server 一个受管 SDK Host”的结构：

```text
CLI / ApplicationBootstrap
  ├─ 配置与信任 ControlWorker（短生命周期，固定操作）
  ├─ 终端启动信任选择（先于所有 Server 连接）
  └─ McpManager
       ├─ Server A Host ─ 官方 SDK ─ stdio Server 子进程
       └─ Server B Host ─ 官方 SDK ─ Streamable HTTP
                     ↓ 发现快照 / 调用结果
ToolRegistry（内置 worker / interactive / external）
  → ToolExecutor：统一验证、PLAN 门禁、Engine、四选审批
  → external 分支 → McpToolAdapter → McpManager.call
  → 原 ToolResult / 事件 / 历史 / Provider 请求
```

Host 是本应用的连接管理进程，不是 MCP Server 实现。SDK 负责外部 JSON-RPC 的编码、id 配对、握手和传输；本地 Host IPC 是内部控制通道，不能冒充自研外部 MCP 协议。每个 Host 只持有一个 Server 的会话；工具调用复用它。

相比直接共享 AsyncExitStack，独立 Host 可以隔离阻塞、控制本地进程树，并避免在任务 A 进入 SDK/AnyIO 上下文、任务 B 退出其 cancel scope 的跨任务收尾问题。代价是每个 Server 多一个轻量应用进程；本章 Server 总数有上限。

### 1.2 组件职责

| 组件 | 职责 | 不能做的事 |
|---|---|---|
| ConfigLoader | 两层 YAML、整条覆盖、来源、校验、变量展开、预算 | 不创建 Server、不自动回退同名坏定义 |
| TrustStore / ControlWorker | 项目身份、配置认证指纹、信任读取/事务保存 | 不接受模型工具调用、不回传签名密钥 |
| StartupTrustPrompt | 真实终端选择、脱敏预览、默认跳过 | 不复用 LLM 问题答案或四选工具授权 |
| McpManager | 并发启动、稳定快照、来源目录、调用分发、关闭 | 不绕过 Engine，不重连/重放 |
| ManagedMcpHost | 内部 IPC、启动归属、Job/进程回收、期限 | 未收到 connect 前不能启动 Server 或联网 |
| SDK Host 服务 | 单任务持有 SDK 会话，初始化、分页、调用、结果转换 | 不启用 sampling/roots/elicitation 等能力 |
| McpToolAdapter | 统一 definition、prepare、外部异步执行入口 | 不把 readOnlyHint 当作信任，不管理协议 |
| ToolRegistry / Engine / Executor | 已登记身份、模式、规则、审批、统一结果 | 不凭名称前缀给任意对象执行许可 |
| TUI | 已有工具行与审批、真实 MCP 状态 | 不显示原始认证值、Server stderr 或系统级 Server 指令 |

不改 Provider 实现、供应商六字段配置、内置工具业务 Schema、Loop 停止条件和缓存统计算法。必要时只调整注入/契约使用点及测试，不强求工具、权限、界面零 diff。

## 2. SDK、协议与运行时选择

### 2.1 固定版本与兼容面

- 实施时新增精确依赖 `mcp==1.30.0`，更新锁文件；不使用无上界 `mcp>=1.0`，不安装 CLI extras。
- 官方该版本包声明 Python >=3.10，满足项目 Python >=3.11；原其他直接依赖保持约束，传递依赖变化逐项记录，不借机升级整套项目。
- 采用该版本 `ClientSession.initialize()` 的握手流程，不采用 SDK v2 的自动 discover/新协议入口。
- 本章兼容集合固定为 SDK 1.30.0 支持且属于握手式会话的 `2024-11-05`、`2025-03-26`、`2025-06-18`、`2025-11-25`。初始化后再次检查协商版本；不在集合内则 `MCP_UNSUPPORTED_PROTOCOL` 并关闭，不自动切换成新协议。
- 外部 MCP HTTP 使用 `mcp.client.streamable_http.streamable_http_client` 和显式 `http_client=`；stdio 使用 `StdioServerParameters`、`stdio_client`。不照搬参考中的旧拼写和已弃用 headers 入口。
- 实施第一组验证包元数据、真实导入、源码签名、版本集合及本地握手；若包不可获得、版本事实不符或不兼容，停止依赖接入并报告差异，不擅自换大版本或提高 Python 最低版本。

本章并非追求“最新 MCP 协议全兼容”，而是实现已批准的三步会话。服务器只支持新式 discover 时清楚报不支持。

### 2.2 SDK 与应用的责任分界

SDK 处理 JSON-RPC 及正常传输。应用提供进程所有权、输入/输出预算、禁止跨来源认证转发、禁止网络恢复请求、错误归类、取消与强制收尾。不得把 SDK 默认行为等同于本章策略：尤其不直接透传 stderr，不默许自动 SSE 重连，也不保证每个 HTTP Server 都支持 DELETE。

## 3. 核心契约与接口

新模块内 dataclass 默认 frozen；字典/列表在边界深拷贝，内部持不可变快照或规范 JSON 字符串，不用 frozen 外壳掩盖可变嵌套。携带秘密的字段 `repr=False`，异常只携固定错误码。

```python
@dataclass(frozen=True)
class McpServerConfig:
    name: str
    source: Literal["user", "project"]
    transport: Literal["stdio", "http"]
    command: str = ""
    args: tuple[str, ...] = ()
    env_json: str = field(default="{}", repr=False)      # 展开后的显式值
    url: str = field(default="", repr=False)
    headers_json: str = field(default="{}", repr=False)

@dataclass(frozen=True)
class McpConfigSnapshot:
    servers: tuple[McpServerConfig, ...]
    warnings: tuple[McpWarning, ...]
    secret_values: tuple[str, ...] = field(repr=False)

@dataclass(frozen=True)
class McpToolIdentity:
    full_name: str
    server_name: str
    remote_name: str
    generation: str              # 本次管理器实例的随机标识

@dataclass(frozen=True)
class ServerStatus:
    name: str
    state: str                  # skipped/connecting/ready/unavailable/closed
    tool_count: int = 0
    code: str = ""

@dataclass(frozen=True)
class McpStatusSnapshot:
    servers: tuple[ServerStatus, ...]
    registered_tools: int

@dataclass(frozen=True)
class TrustRequest:
    startup_id: str
    approval_id: str
    server_name: str
    preview: str                 # 仅安全、有界显示值
    scope_hint: str

@dataclass(frozen=True)
class ShutdownReport:
    clean: bool
    unconfirmed_servers: tuple[str, ...]
    forced_servers: tuple[str, ...]
```

主要接口（参数中的 cancel 均是应用持有的取消事件）：

```python
async def load_mcp_config(root, *, user_home, cancel) -> McpConfigSnapshot: ...
async def authorize_project_servers(snapshot, *, root, store, prompt, cancel) -> AuthorizedServers: ...

class StartupTrustPrompt(Protocol):
    def choose(self, request: TrustRequest) -> Literal["trust", "skip"]: ...

class McpTrustStore:
    async def inspect(self, configs, *, root, cancel) -> TrustSnapshot: ...
    async def remember(self, config, *, root, challenge, cancel) -> TrustSaveResult: ...
    async def aclose(self) -> None: ...

class McpManager:
    async def start(self, authorized, *, cancel, report) -> McpDiscovery: ...
    def identity(self, name: str) -> McpToolIdentity | None: ...
    def snapshot(self) -> McpStatusSnapshot: ...
    async def call(self, identity, call, *, cancel, execution_started) -> ToolResult: ...
    async def aclose(self) -> ShutdownReport: ...

class McpToolAdapter:
    definition: ToolDefinition          # read_only=False, execution_kind="external"
    identity: McpToolIdentity
    def prepare(self, call, context) -> PreparedOperation: ...
    def execute(self, operation, context) -> ToolResult: ...
    async def execute_external(self, operation, *, cancel, execution_started) -> ToolResult: ...
```

同步 `execute` 必须返回 `MCP_EXTERNAL_DISPATCH_REQUIRED`，绝不暗中创建事件循环或裸发远端调用。`prepare` 只验证参数/身份和生成预览，无外部 I/O；获准后 Executor 才调用异步扩展入口。其余 Tool 仍使用原同步接口。

ToolDefinition.execution_kind 追加 `external`，不改变原字段位置、worker/interactive 含义。PermissionTarget 末尾追加可选 `external_identity`；不是把参数中的 path 当 PathStamp，也不是拿远端工具参数 command 冒充本地命令。

## 4. 配置、来源、秘密与规模

### 4.1 加载规则

读取用户级 `~/.weizhcode/mcp.yaml` 与项目级 `<root>/.weizhcode/mcp.yaml`。项目根使用权限系统固定的真实根；root 不可确认时 MCP 整体不启动，纯聊天照常。

1. 在固定用途 ControlWorker 中读取常规文件，拒绝 FIFO、设备、未知重定向和不可确定来源；文件大小先校验后有界读取。配置文件重定向导致来源范围不明确时跳过该层，不借链接把用户层当作可信配置。
2. 复用权限 YAML 的重复键/循环/复杂类型拒绝原则，但 MCP 不调用其固定权限 Schema；提取通用安全加载辅助函数，原权限校验语义不变。
3. 顶层仅允许 `mcp_servers`；缺失/null/空 map 为空。单 Server 允许其传输相关字段，未知字段或混用 HTTP/stdio 字段跳过该 Server，避免拼错认证字段仍启动。
4. 用户 map 与项目 map 按 key 合并，保留 source；先覆盖，后验证最终定义。项目同名坏条目是遮蔽项，不能被过滤后重新找用户同名值。
5. env/headers 值进行一次 `${VAR}` 替换，不递归展开环境变量值。未定义变量跳过 Server；空字符串是合法已定义值，仍可能由服务认证失败。
6. Server 名限 `[A-Za-z0-9_-]{1,32}`，禁止含 `__`，名称大小写敏感；工具原名不得含 `__`。这是为了保证命名空间分隔唯一，不用字符串分割猜来源。合成全名仍须总长 <=64。
7. url 限 HTTP/HTTPS，无 userinfo、fragment 或控制字符；query 可含 Token，因此不在预览显示 query 值。header 名大小写去重，拒绝 CR/LF 与非法名；不能覆盖 Host、Content-Length 或 MCP 受控协议头。认证头在 SDK HTTP client 上设置。
8. command 和 args 是字面程序/参数，不做 shell 拼接。Windows 的 `.bat/.cmd` 解释语义不能冒充纯 argv：本章拒绝这类入口及其 PATH 解析结果，提示使用已安装的实际可执行程序；不自动套 cmd /c。

本章不继承全部宿主环境。SDK Host 使用 SDK 默认基础环境加显式 env；父进程的模型 API key、信任签名密钥不加入 Server 环境。PATH 解析、基础环境和实际程序内容仍不是固定二进制认证。

### 4.2 固定预算

| 输入/行为 | 内置限制与超限处理 |
|---|---|
| 单层配置 / 信任记录 | 各 256 KiB；拒绝超限，不部分读成合法文件 |
| 最终 Server 数 | 最多 16，按名称稳定排序取前 16，其余逐项限流告警且不启动 |
| command / 单参数 / 单 env 或 header 值 | 各 8192 字符；args<=128，env/headers 各<=128 项；总配置受文件与展开后 1 MiB 预算约束 |
| 工具发现 | 每 Server<=256 工具、<=64 页、单 cursor<=4096 字符；重复 cursor 立即失败；累计原始目录<=2 MiB；超限视为该 Server 发现失败，不留下半套目录 |
| 总可注册 MCP 工具 | <=256；全体候选先按全名排序、去冲突，再取前 256；不以 Server 返回先后决定占位 |
| 描述 / Schema | 描述<=8192 字符，超限工具跳过；Schema<=64 KiB、深度<=16、节点<=4096，无 `$ref`/远程引用，必须是 object Schema，Draft202012Validator.check_schema 通过 |
| 原始调用参数 | <=64 KiB；超限前置拒绝，不发送 |
| Host IPC | 单帧<=1 MiB，待接收缓冲和队列均有界（32 帧）；目录分页/工具逐帧送达，不把 2 MiB 目录塞进一帧 |
| 外部 HTTP 响应 | 每个请求解码流累计<=2 MiB；HTTP transport 包装器逐块计数，超限立即中止响应并关闭该会话 |
| 工具结果 | 沿用最终序列化<=20,000 字符，正文/元信息共同计入；标记 truncated，不截坏 JSON |
| 诊断 | 单条<=2048 字符，每 Server 每阶段最多16条；stderr 每次收集最多16 KiB，其余继续 drain 丢弃并计数 |
| 时间 | ControlWorker 单操作5秒；单 Server 启动30秒；调用30秒；取消协议收尾1秒；全局正常退出5秒；强制回收额外2秒 |

原生 stdio SDK 解析器可能先缓冲远端超长行，因此不能声称仅靠应用 Schema/结果预算就防住 SDK 内存使用。独立 Host 将主 UI 与该解析器隔开；若 Host 因异常退出则失效隔离。对原始 stdio 字节的完整内存配额/沙箱不在本章，不能将这些预算描述为恶意 Server 的系统资源隔离。

### 4.3 秘密与外部元信息

对 config 原值、展开值、header 全值与认证片段建立秘密集合，与现有 Provider redactor 在构造 Runner 前统一；值不进事件对象 repr/错误正文。host 收到必要秘密通过私有 stdin IPC，而不是命令行/文件。

描述允许安全显示清理，参数 Schema 不允许通过替换秘密或删除约束改变语义：若 Schema 自身包含已知秘密/控制注入，跳过该工具并固定码告警。匹配/执行使用原始合法参数，展示与结果统一脱敏。SDK 日志不打印异常堆栈/完整消息，由固定错误类别替代。

## 5. 启动信任：防伪、持久化与真实选择

### 5.1 为什么不能只存配置 SHA256

如果只把明文配置摘要写进仓库旁的 JSON，恶意项目可同时提供配置和“已信任”摘要，首次打开就自动执行。因此记录必须由本机应用私有密钥认证，项目中自行写入的标记不能构成许可。

采用 HMAC-SHA256：

- 随机32字节签名密钥放在用户级 `~/.weizhcode/mcp-trust.key`，不放项目、不放 Server 环境或 IPC 结果；ControlWorker 内生成/使用。
- POSIX 文件0600、目录0700，拒绝不安全权限、链接/特殊文件；Windows 使用当前用户 DPAPI 保护密钥文件内容，并核对固定用户目录与文件类型。密钥保护只防误提交/离线记录伪造，不隔离已获当前用户执行权的恶意程序。
- 项目记录固定为 `<root>/.weizhcode/mcp-trust.local.json`，结构为版本、项目身份、Server 名、认证指纹、签名；不写原命令/env/header/url，更不存展开秘密。
- 指纹输入包含规范项目根和可获得的稳定文件系统身份、source、Server 名、传输、command、args、展开后的显式 env、url、headers，以及指纹格式版本；map 排序、header 名统一小写、UTF-8 规范 JSON。基础环境和程序二进制未绑定的限制明确提示。
- 对记录整体认证，验证用常量时间比较。缺 key/坏 key/坏签名/项目根变化/相关定义改变均视为未信任，不接受记录里的可选字段自称版本回退。
- 当前进程只保存本次启动的不可变授权票据，包含 generation 和配置指纹；只有这些票据可交给 Manager。没有票据不能调用 connect。

### 5.2 保存与 Git 保护

ControlWorker 执行固定 `load_config`、`inspect_trust`、`remember_trust` 三类操作，不接受任意路径/代码/工具名作为文件操作入口。用受管独立进程承担同步读取/DPAPI/Git 探测；主进程可在5秒后终止并回收，不用无限等待的 to_thread。

信任路径/父目录/临时文件禁止重定向，固定项目根围栏，写前/替换前复核。独占随机临时文件、flush/fsync、比较旧文件指纹、原子替换、按身份清理；冲突保留外部编辑，不覆盖损坏文件。

Git 仓库保存前，用不带用户 shell 的只读 Git 探测验证记录和本系统临时路径已被忽略且未被跟踪；本仓库实施时追加对应 .gitignore。对其他未配置忽略的项目不擅自改其 Git 设置：仅本次启动信任、明确提示如何加忽略后重启；非 Git 目录按本地敏感数据保护保存。Git 状态不能确定也不持久化，不宣称永久记住。密钥在用户目录位于 Git 仓库时也执行相同保护检查。

保存明确失败允许使用当前真实选择生成一次启动票据，提示“未记住”；替换提交结果未知则当前 Server 不启动并要求下次核对，绝不假称回滚。保存后取消仍可能已留记录，但本次不连接；重启信任生效的事实需如实显示。

### 5.3 启动交互

CLI 在创建任何 SDK Host 连接之前，对尚未信任的项目 Server 按名称串行展示。使用普通终端预览和两个明确选项：`1 信任并记住此配置`、`2 跳过`，默认跳过。无 TTY/EOF 返回 skip，非法输入不生成票据；Ctrl+C 取消整个启动。

此时尚无 SDK 连接或 LLM 任务，可以同步读取真实 console 输入；不在已有异步连接期间调用阻塞 input，也不靠遗留后台 input 线程收尾。测试注入 StartupTrustPrompt 替身，真实终端输入不来自模型请求。

所有选择完成、取消检查通过后才并发启动有效授权 Server。用户级配置经验证后直接得到票据；项目覆盖项不能继承用户层来源信任。取消、旧 startup_id/approval_id 或定义中途改变不会沿用票据；控制数据保存/复核完成后使用同一快照连接，本章不热加载配置。

## 6. 每 Server 的 SDK Host 与生命周期

### 6.1 受管启动与内部协议

ManagedMcpHost 启动本应用 `python -m weizhcode.mcp.host_worker`，并接管进程创建期间的取消结果；Windows 隐藏窗口。Host 初始仅导入应用、等待控制帧，不能解析项目启动命令自行执行。

Windows 在发送 connect 帧前将 Host 加入 kill-on-close Job，失败则关闭 Host、标记 PROCESS_CONTROL_FAILED，不运行 Server。POSIX Host 为独立 session/process group，记录会话身份和拥有的后代；SDK 可能给 Server 新建进程组，强制清理必须覆盖已登记的自有后代，而非只 killpg Host 后就宣称无残留。直接复用既有 WindowsJob 公共控制能力，不扩大原工具 worker 的目的白名单。

内部协议：一行 UTF-8 JSON 一帧，带 `version=1`、`host_id`、`request_id`（随机32位十六进制）与白名单 type。输入只允许 connect、call、cancel、close；输出只允许 ready、tool、discovery_done、started、result、diagnostic、closed、fatal。状态/ID/长度/重复应答校验失败立即关闭对应 Host。没有任意 eval、shell、save_permission 或 run_tool 消息。

外部 JSON-RPC id 由 SDK 维护，与 Host IPC id 区分；Host 关联内部 call id 和 SDK 操作上下文。Server 返回带 type=result 的文本不能越过 SDK 标准消息解析后冒充内部 IPC。stderr 与 IPC stdout 分开，禁止原样透传。

每个 Host 的单一 owner 协程进入/退出 SDK async context；输入接收任务只投递有界控制消息，不在另一个任务中 aclose owner 的栈。关闭通知唤醒 owner；其正常 finally 退出上下文。父进程超时可终止整个 Host，不把强制关闭作为正常工具结束手段。

### 6.2 stdio

StdioServerParameters 设 cwd=真实项目根、配置 command/args、SDK 基础环境加显式 env。SDK 实际创建程序前必须已通过 Host 的 connect 票据验证及父进程 Job/进程归属检查。

`stdio_client(..., errlog=...)` 接收专用匿名 OS pipe 写端，而不是临时日志文件或默认 sys.stderr。应用持续读取该 pipe，以 StreamingRedactor 防止分片密钥泄漏，控制字符过滤、限量并截断；即使超过展示上限仍 drain，防止 Server 被 stderr 背压卡死。SDK/logger 原始异常只保留固定错误类，不能回显完整报文。

本地子进程的 graceful 终止由 SDK 上下文先尝试，外层 Host 归属用于兜底。sdk stdio 的内部私有函数不 monkeypatch；如平台启动 API 无法让所选版本的后代被外层监督，则该平台不得宣称清理通过，先报告验证差异。

### 6.3 Streamable HTTP

Host 创建专用 httpx.AsyncClient：配置 headers、TLS 默认验证开启、trust_env=False、底层 retries=0、read/connect/pool 期限不大于当前操作剩余预算；将 client 通过 SDK 公共 http_client 参数传入。

增加应用 AsyncBaseTransport 包装：

- 只允许配置 endpoint 的同源 POST 和适用 DELETE；SDK 正常的同源路径重定向由其来源校验处理，不允许降级 HTTPS 或带认证跨源请求，包装层再次校验最终 request origin。
- 不允许独立 GET/恢复流联网。SDK 某版本可能在 initialized 后尝试 GET 或断流恢复，包装器在本地返回405，不创建网络请求；不会影响 POST 的请求关联 SSE。请求中的重试/resumption 元信息同样不启用。
- 已发出过的非通知 JSON-RPC request id 不允许重新发 POST，避免 SDK 内部恢复变成副作用重放；单次请求的同源重定向不算重放，需绑定同一重定向链而非仅按全局次数猜测。
- 对解码后响应流逐块计算2 MiB预算，JSON/SSE均适用。异常/超限关闭响应并通知会话失效。无无限重定向（最多3跳）、无自动登录/Token刷新。

SDK 不默认订阅日志或资源，不配置 sampling/roots/elicitation 回调；Server 额外请求以 SDK 的“不支持”响应处理，不能调用本地工具、文件或 LLM。初始化 instructions 和变更通知只被当作外部元信息，既不注入系统提示，也不刷新快照。

### 6.4 状态与期限

状态机：`created → connecting → ready → unavailable → closing → closed`；失败启动走 closing/closed，不存在 unavailable→connecting。无健康检查，失效仅来自真实业务 I/O、协议终止或进程退出观察。

每个30秒启动期限从创建 Host 开始，覆盖启动、connect、initialize、所有分页及目录转换；超时取消该 owner 操作并回收 Host，然后隔离失败。零工具但正常会话算 ready，注册数可为0；无工具 capability也正常显示零工具。

调用30秒期限从获准、准备完成并开始外部调用分支起算，包括 IPC 和 SDK等待，不含审批。Host 内部也用剩余期限；主进程是兜底 deadline，不依赖 Server 遵守。

## 7. 目录、适配与可信身份

发现结果先暂存在每 Server 私有候选目录；分页全部成功才交 Manager。校验工具原名/全名、Schema、描述大小和秘密后，全体候选稳定排序。任何全名发生冲突，冲突项全部跳过并告警，不让较快响应覆盖较慢响应；内置重名永远保留内置项。

Registry 增加 `register_external(adapter, identity)` 与只读身份查询。普通 register 不允许自行携 execution_kind=external；外部入口验证 Adapter 类型、Manager generation、完整来源映射及同一对象关联，再冻结目录。MCP 身份不从参数或字符串前缀反推。

Adapter.definition.read_only 恒为 False，execution_kind=external；readOnlyHint 仅可留诊断，不影响类别。`definitions_for_mode` 改为白名单分类：PLAN 仅既有三个读工具与 AskUserQuestion，其他模式为既有内置工具加已登记 external；仍拒绝任意未知扩展对象。

Schema 与现有 registry 一致禁止引用（包含本地 $ref，暂不做解引用），保留自包含 Schema 原意。若 `{}` 是输入 Schema，则不能擅自加 additionalProperties=False；仅明确可接收对象且共同 Provider 支持的 Schema可注册，不能为通过某后端而删除 required/enum 等约束。不支持的形式跳过，不影响其他合法工具。

## 8. 规则、Engine、审批与执行分支

### 8.1 规则扩展不改变旧语义

在权限 types 中为 Rule 增加末尾默认 kind=`builtin`，新增 `mcp_exact` / `mcp_server`。保留原六友好名的解析/转义/路径匹配和 Windows normcase；MCP 名称始终大小写敏感。

MCP 仅支持：

- 完整合法全名，如 `mcp__demo__echo`，精确工具身份。
- `mcp__<合法Server>__*`，只匹配该 Server 下合法工具。

拒绝裸 mcp__、跨 Server 通配、其他任意星号位置、`Mcp(...)` 参数语法及括号附加条件。MCP 规则可在 Server 缺席时合法加载，但不凭规则创造可执行身份。

`exact_rule(target)` 对 external 产生裸完整工具名；rule_key 将其与 builtin 分开、保持大小写。现有 settings/持久保存重新解析同样的扩展语法；会话/本地/项目/用户层和同层 deny 优先不变。外部工具的 match_target 是其完整名，不是 JSON 参数、cwd 或路径。

### 8.2 Engine 的外部身份分支

Engine 构造时注入 registry 的只读可信身份解析函数，而不是把所有未知工具归 EXEC：

1. 先解析参数对象，校验工具已登记身份；既有六工具仍走原分支。
2. 已登记 external 在 PLAN 立即拒绝，不进入 Ask。
3. 根身份不可确认/代次不符/已撤销目录，拒绝；目录保留但连接失效的调用由 Manager 返回 MCP_UNAVAILABLE，不伪装成 UNKNOWN_TOOL。
4. 产生带 external_identity 的 PermissionTarget，category=EXEC、command=None、path=None。黑名单和路径探测不套在远端参数上，但原内置分支不变。
5. 按旧层序查 MCP 规则，再按 EXEC 模式兜底：DEFAULT/ACCEPT EDITS Ask，BYPASS Allow，命中 deny 仍拒绝。
6. 审批接纳/执行前 recheck registry 对象、generation 和项目根身份，不为远端参数进行本地路径“验证”。取消优先；accept 保存精确 MCP 身份规则，复用原事务与保存未知处理。

审批展示来源和原参数的安全预览，scope_hint 明确：“此许可针对整个 MCP 工具身份，不绑定本次参数；后续不同参数可能复用许可。外部 Server 不受内置文件范围限制。”服务器启动信任没有权限 rule_key，不能由一次工具允许产生。

### 8.3 Executor 与 Scheduler

ToolExecutor 统一参数验证 → 模式硬门禁 → Engine → 审批 → recheck 的前半段不拆成另一个可绕过的外部 Executor。只有通过后才按注册 execution_kind 分派。

- worker：原进程准备/执行/快照/回收路径保持。
- interactive：原 PLAN AskUserQuestion 路径保持，不能拿它处理启动信任。
- external：调用同一个已注册 Adapter 的纯 prepare，再进入 execute_external；不新建普通工具 worker、不向其发送 MCP 控制消息。

发出外部请求前最后检查 cancel，标记 execution_started，并发出 running 事件。请求完成后先保存 ToolResult 再 await 清理，保留“结果已确认”和“取消发生”的先后事实；后续没有第二次隐式发送。调度器按 read_only=False 将所有 MCP 调用视为串行屏障，原内置最多4读并发、原序回灌和取消后补齐结果不改。

## 9. 结果、错误与取消

### 9.1 统一结果

SDK CallToolResult 的 content 按顺序收集 TextContent。混合非文本记录 unsupported_blocks 并追加省略标记；全非文本返回 `MCP_UNSUPPORTED_CONTENT`。空 content 且没有结构化数据是合法空结果，明确给“工具未返回文本”，不与全非文本混淆。

若有 structuredContent：无文本时将有界合法 JSON 转为文本；已有文本时不重复拼一份可能重复的数据，仅标记存在结构化数据。不读取 resource/resource_link，不解码图像。isError=True 返回 `MCP_REMOTE_ERROR` 并保留支持的文本，非文本省略信息不能覆盖原远端错误。

在 Host 内先有界转换、脱敏，主进程再次经原 Executor._result_event 和 ToolResult.to_model_text 归一化，始终恢复原 call_id/tool_name；metadata 仅安全标量，不包含 session id、Token 或 SDK异常 repr。

| 错误 | 状态及处理 |
|---|---|
| MCP_REMOTE_ERROR | error；会话仍可用，不停止 Loop |
| MCP_RPC_ERROR / MCP_AUTH_ERROR | error；固定诊断，不回显认证正文；认证使会话不可用 |
| MCP_UNAVAILABLE / MCP_TRANSPORT_ERROR | error；标记该 Server unavailable，后续立即失败 |
| MCP_UNSUPPORTED_PROTOCOL / MCP_DISCOVERY_LIMIT | 启动失败；不注册半套工具 |
| MCP_UNSUPPORTED_CONTENT / MCP_RESULT_LIMIT | error 或带截断文本；明示未支持/限额 |
| TOOL_TIMEOUT | timeout；未知远端副作用明确提示，不重试 |
| TOOL_CANCELLED | cancelled；是否已发送按 execution_started 如实说明 |
| PROCESS_CONTROL_FAILED | 原基础设施错误；保留已确认结果并按原 Loop 安全停止逻辑提示 |

### 9.2 请求取消

父进程取消先阻止未发送项，再发内部 cancel(call id)。owner 取消对应 SDK操作，让 SDK完成适用的请求取消通知；用假的 Server 实际捕获 request id 对照，不能只测 Task.cancel。取消协议收尾最多1秒；无法确认取消后本章保守关闭该 Host、标记 unavailable（不重连），避免迟到结果污染下一调用。

30秒调用超时同样使该 Server 在本次运行失效；若取消成功且协议可确认没有遗留等待者，用户主动取消可保留健康会话，否则关闭。业务 isError 不关闭。被取消请求的结果若在取消前已完整接收则保留已确认事实，不用之后的 cleanup_error 覆盖。

远端不遵守取消仍可能继续执行；本地收尾只保证本应用停止等待/发送并清理自己拥有的资源，不证明外部事务回滚。

## 10. 应用装配、界面与关闭

### 10.1 单一启动入口

新增 ApplicationBootstrap 负责创建配置、项目根、统一 redactor、MCP、registry、Engine、Executor、Runner。CLI 先同步完成真实信任输入，再 `asyncio.run` 异步启动/运行段，整个应用仅一个长期事件循环；不要用第一次 asyncio.run 连接、第二次 .run() 启动 TUI。

实际顺序为：在受控短生命周期配置阶段生成快照与信任请求 → 真实终端选择 → 固定票据 → 在同一长期 loop 内 Manager.start → 目录注册 → Engine/Runner → `await app.run_async()`。控制阶段可以拥有自己的短生命周期运行器，但不得将其 loop 上的 Task/连接/Future带入主 loop；跨边界仅不可变 DTO。

TUI 显式注入 runner 与 McpManager 状态源，不自行重复启动或读取用户 Server。App 原后备构造保留安全的内置-only行为，用于嵌入/旧测试；若调用方要 MCP，必须经过统一 bootstrap 注入，不能在 on_mount 偷启未经信任的 Server。

Manager.start 的失败单独显示启动诊断；Provider 配置本身非法仍沿用现有启动错误路径。MCP 无配置不创建 Host、密钥、信任文件或额外菜单；配置仅用户级也不需要项目签名密钥。

### 10.2 真实状态

TUI status 从 McpStatusSnapshot 计算当前 ready Server 数及成功登记工具数，移除“Connected to 0”硬编码。零工具连接算连接成功，失效后 ready 数下降但注册快照不变，显示不可用 Server 数；工具数区分总注册和当前模式可见，保留模式、模型、轮次与用量。

状态消息走有界只读队列，TUI只观察，不直接关闭SDK上下文。启动信任不进入会话历史，不消耗 LLM请求；模型看不到签名材料、敏感配置或用户 console 原始输入。

### 10.3 关闭预算与所有权

统一 shutdown 幂等：冻结新任务 → 取消 Runner/审批并等待历史配对 → 并发通知所有 Host close → SDK owner 各自退出 → 回收 IPC/诊断任务 → 关闭权限 ControlWorker。CLI finally 为兜底；TUI与Runner可多次触发，但共享同一个关闭 Future。

MCP 正常关闭共用5秒 deadline，不给每个 Server 各等5秒。deadline 到达后父进程并发强制回收，额外预算2秒；Windows关闭Job并确认Host退出与Job活动进程归零，POSIX按所有权处理Host与记录的自有后代并确认。原 WindowsJob 需增加可查询/可复核的状态方法，现有工具调用行为不改。无法确认或OS拒绝时 ShutdownReport.clean=False，明确列出 Server，不撒谎“退出干净”。

强制回收预算不是操作系统一定在7秒内成功清除恶意程序的承诺。POSIX后代主动脱离监督、远程HTTP工作继续、外部系统阻塞等不在本章沙箱保证内；正常及协作式本地fixture必须证明确实回收，不用这些限制掩盖普通子进程泄漏。

启动取消、Host 创建中取消、连接失败、日志堵塞与用户连续取消都采用同样的归属/共享关闭路径。保存信任或许可的进程，提交结果未知先停稳，再提示可能保存，不在后台留写操作。

## 11. 文件组织与变更边界

下列目录以项目根 `D:/STUDY/weizhcode-python/` 为基准；是未来实施清单，不代表现在已修改。

```text
src/weizhcode/mcp/
  __init__.py          轻量公共入口
  contracts.py         配置、来源、身份、状态、信任和关闭DTO
  limits.py            固定规模与期限
  config.py            安全两层加载、覆盖、展开、输入校验
  control.py           短生命周期固定控制进程客户端
  control_worker.py    配置/信任固定操作，不执行模型工具
  trust.py             认证指纹、私有密钥、事务记录、来源校验
  startup.py           真实终端启动信任选择与票据
  process.py           ManagedMcpHost、IPC、所有权与强制回收
  host_worker.py       单owner SDK上下文与内部控制状态机
  http.py              显式HTTP client、同源/恢复策略、流预算
  diagnostics.py       stderr匿名pipe、分片脱敏与限流
  manager.py           并发启动、目录冻结、会话缓存、调用与关闭
  tool.py              McpToolAdapter、Schema与结果适配
src/weizhcode/bootstrap.py     统一配置/信任/装配/关闭
```

必要修改：

| 文件 | 修改范围 |
|---|---|
| pyproject.toml / uv.lock | 新增固定 SDK 与必要传递依赖，保留Python最低版本 |
| models.py | external 执行类型；必要通用状态契约，不把SDK对象写入历史 |
| tools/base.py | 外部异步扩展Protocol；原同步Tool保持 |
| tools/registry.py | 外部可信登记、身份查询、模式筛选 |
| tools/executor.py | 原门禁后增加 external分支、统一结果/取消 |
| tools/process.py | WindowsJob状态查询等小范围复用；不扩大普通worker目的白名单 |
| permissions/types.py / rules.py | MCP身份与精确/Server规则类型，旧参数默认不变 |
| permissions/engine.py | 可信身份解析、外部EXEC分支、审批前后复核 |
| permissions/settings.py / persist.py / worker_ops.py / io.py | 新规则往返、外部target安全序列化，保持固定目的与路径 |
| approvals.py | MCP身份范围提示；原枚举/关联/取消语义保持 |
| cli.py | 调用bootstrap、真实启动选择、同loop运行与finally |
| tui.py / turn_runner.py | 注入状态/生命周期，显示真实计数；不重写Loop |
| redaction.py | 必要组合秘密集合接口，原流式行为不变 |
| README.md / .gitignore | 配置/信任/审批范围/风险；忽略本地记录及固定临时名 |

新增 `docs/mcp/mcp-servers.example.yaml`（非凭据示例）和离线手动观察入口 `tests/manual_mcp_smoke.py`；阶段设计文档仍只在 `specs/mcp-client/`，不新建重复设计副本。

新增测试：`tests/test_mcp_config.py`、`test_mcp_trust.py`、`test_mcp_process.py`、`test_mcp_manager.py`、`test_mcp_tool.py`、`test_mcp_http.py`、`test_mcp_permissions.py`、`test_mcp_integration.py`、`test_mcp_tui.py`，及 `tests/fixtures/mcp_stdio_server.py`、`mcp_http_server.py`。既有相应配置/工具/权限/CLI/Loop/提示与三协议测试保留。Task再拆具体逐文件步骤。

不读取/修改/暂存用户 `.weizhcode-test/`、`hello.txt`、真实 `weizhcode.yaml` 或真实用户权限/信任文件。测试注入临时home/项目，不让开发者真实配置决定测试行为。

## 12. 验证策略与需求映射

所有验证在四文档批准后才运行，当前没有本章测试结果。预计测试不代表通过。

### 12.1 分层证据

1. **SDK契约**：固定包导入、元数据、接口与支持版本；初始化/分页/取消请求实际抓包。没有源码/签名证据时不猜参数。
2. **纯逻辑**：两层遮蔽语义、变量、规则、Schema、命名冲突与预算边界、HMAC伪造/秘密变化、结果转换。
3. **固定控制/Host协议**：无票据零外部执行，错误状态/ID/超长帧/重复响应/取消竞态；控制进程不能调用Server或模型工具，Host不能持久保存信任/权限。
4. **真实本地传输**：临时stdio最小Server和回环HTTP最小Server，使用官方SDK收发；分页、JSON/SSE、认证、乱序、断线、超限、未知协议及额外能力请求。独立GET本地拒绝和调用POST不重放必须观察Server实际请求计数。
5. **真实本地进程**：Host创建中取消、Server孙进程、stderr持续输出、正常/强制退出、WindowsJob分配失败及POSIX分支分开记录。只测Windows不能宣称POSIX通过。
6. **完整离线应用**：fake模型 → MCP审批 → 真实本地Server → 回灌 → fake续答；拒绝后调整、失效隔离、Plan硬拒、取消恢复、三协议实际请求体、缓存/统计回归。
7. **TUI自动与真实PowerShell**：Pilot测按键/焦点/草稿/滚动/控制字符，用户真实终端确认启动信任、四选工具审批、重启复用、真实计数；两种证据分别记录。
8. **可选真实服务/模型**：运行前明示域名、协议、模型、操作范围、请求与费用，需另行确认，不自动连现有生产配置。默认手动入口离线、无凭据/真实配置读取。

### 12.2 覆盖表

| Spec | 架构归属 | 证据 |
|---|---|---|
| F1 / AC01～02 | ConfigLoader、来源遮蔽、ControlWorker | 临时两层文件、坏条目与坏整层对照 |
| F2 / AC03 | config、预算、环境展开 | 字段/未定义/空值/字面量与原字节 |
| F3 / AC04～06 | TrustStore、HMAC、startup、ControlWorker | 零启动/零联网、持久重启、伪造/保存故障/取消 |
| F4 / AC07～09 | 固定SDK、Host、stdio、HTTP gate | 原生本地传输与乱序/认证/版本 |
| F5 / AC10 | Manager并发、Host总期限、分页 | 时间区间、调用计数、零工具与失败隔离 |
| F6 / AC11～12 | Adapter、Registry可信目录 | 名称/Schema/冲突、假只读与未注册拒绝 |
| F7 / AC12～15 | Engine/规则/ApprovalBroker/Executor | 四档×规则×真实四选、Plan前后端硬门禁 |
| F8 / AC16～18 | Adapter、Manager.call、Scheduler | 同会话复用、串行屏障、文本/错误/不支持内容 |
| F9 / AC18～20 | SDK取消、Host失效、Runner历史 | 取消通知/迟到结果/断线/拒绝后续答 |
| F10 / AC21 | 所有权、正常/强制deadline、ShutdownReport | 实际PID/Job/连接状态、重复关闭与启动取消 |
| F11 / AC22 | 状态快照、diagnostics、redactor、TUI | 真计数、非文本/截断、分片合成秘密 |
| F12 / AC23～24 | bootstrap、统一ToolResult、原Provider/Loop | 三协议离线请求体、原全量回归 |
| N1～N8 / AC25 | 固定限额/版本/安全边界/证据分层 | 边界值、锁/编译/差异、原生与手工分开 |

实施验证包含锁文件一致性、源码编译、全套pytest和diff空白检查；当前未配置Ruff/mypy/pytest-timeout，不擅自安装并宣称通过。测试期间不会把真实危险命令交给shell，也不会靠注释掉旧断言换绿。

## 13. 主要技术决策与剩余风险

| 决策 | 选择与理由 |
|---|---|
| 协议 | 固定官方SDK 1.30.0握手式兼容面，避免新旧文档混用 |
| 连接归属 | 每Server受管Host，单owner进入/退出SDK上下文；复用连接且可回收 |
| 信任记录 | 私有key认证项目local记录，避免仓库伪造首次信任 |
| 秘密变化 | 对展开后的显式env/headers做keyed指纹，变化重问，不保存原文 |
| 规则与只读 | 仅已登记身份；MCP全为EXEC、默认Ask、PLAN硬拒；不采信只读提示 |
| HTTP恢复 | 禁止独立GET联网和请求重放，正常POST SSE仍支持 |
| 内置工具 | 原worker生命周期保留，external不是把未知工具加入worker |
| 内容 | 文本及可转文本结构化数据；非文本明确省略/不支持，不拉资源 |
| 关闭 | 5秒正常+2秒强制、结果报告；不以停止等待冒充全清理 |
| 范围 | 无OAuth/热加载/自动重连/资源/提示词/采样/审计/系统沙箱 |

必须明确的限制：信任程序可在工具调用前执行本地代码；本章不隔离同用户程序、不认证二进制和远端内容；签名key并不抵挡已经拿到用户代码执行权的攻击者。MCP永久许可针对工具名，Server更新实现后也可能继续命中，启动配置信任不是工具语义签名。内置黑名单/文件围栏不约束远端内部行为。stdio解析器仍可占用Host内存，不能宣称恶意数据资源沙箱。取消/断流不回滚远端事务；无法确认关闭时必须显示异常。

## 14. 文档依据与审批边界

已先通过 Context7 定位并查询官方 `/modelcontextprotocol/python-sdk/v1.30.0`，再核对固定tag原始源码补齐接口与元数据；不是依赖训练记忆套SDK代码。关键来源：

- [SDK 1.30.0 包元数据](https://github.com/modelcontextprotocol/python-sdk/blob/v1.30.0/pyproject.toml)：Python最低版本和SDK依赖。
- [SDK 1.30.0 客户端文档](https://github.com/modelcontextprotocol/python-sdk/blob/v1.30.0/docs/client.md)：握手、传输及HTTP client入口。
- [SDK stdio源码](https://github.com/modelcontextprotocol/python-sdk/blob/v1.30.0/src/mcp/client/stdio/__init__.py)：cwd、env、errlog、上下文收尾的依据。
- [SDK Streamable HTTP源码](https://github.com/modelcontextprotocol/python-sdk/blob/v1.30.0/src/mcp/client/streamable_http.py)：JSON/SSE、会话和恢复行为的核对依据；应用策略不能只靠默认值。
- [SDK支持版本集合](https://github.com/modelcontextprotocol/python-sdk/blob/v1.30.0/src/mcp/shared/version.py)：实施时与握手式兼容集合比对。

源码核对证明接口依据，不证明本项目已安装或通过这些行为测试；所有原生收尾、SDK取消、DPAPI、Git保护、HTTP gate和跨协议集成都必须由后续Task/Checklist落实验证，不能仅凭本文完成验收。

批准本 Plan 后只生成 Task 供单独审批；不同时生成Checklist，不开始实现。用户的Spec批准不等于自动批准本设计的技术取舍。若需要改变本Plan，只修改本阶段文档并重新审批；历史文档及用户文件保持不动。
