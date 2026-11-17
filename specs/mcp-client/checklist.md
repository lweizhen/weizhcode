# weizhCode MCP 客户端 Checklist

> 状态：MCP生产接入与离线闭环已实现；最终完整回归723 passed、4 skipped。复合条目按实际覆盖勾选，未穷尽的专项与真实场景不冒充通过。
> 日期：2026-11-17。每项通过实际输入、输出、副作用或用户操作验证；源码名称/测试文件仅作证据定位，不以“存在某方法”代替产品行为。
> 共107项，仅实际完整验证的条目勾选；其他项目保留待验。批准清单不等于任何一项已通过，也不自动授权生产连接、付费模型或GitHub推送。

## 1. 验收与证据规则

项目根为 D:/STUDY/weizhcode-python/。第16节G01～G13列出实施后的验证组，单项写明具体场景和预期行为；多项可共用一次完整运行证据，不为每项重复执行整套测试。第17节是Spec AC覆盖索引，第18节登记真实结果。

- 只有条目全部条件实际观察到才勾选。失败/未执行/平台skip/未配置/待用户确认都保持未勾，并记录原因；通过一部分不能把复合条目整体标绿。
- 开发测试只用临时项目与home、合成密钥、受管本地stdio/回环HTTP fixture及fake模型；不读取或改动 .weizhcode-test/、hello.txt、真实 weizhcode.yaml、真实用户权限/MCP/信任数据。
- 高危命令只作为纯判定数据或禁执行替身，绝不粘贴到真实shell证明拦截。不自动下载/安装Server，不连接示例/生产端点。
- 协议适配单测、真实本地传输、原生进程、Pilot、真实PowerShell和真实服务/模型各自记证据；后几类不能用前一类的通过替代。Windows实测不能外推POSIX。
- 测试必须有有限期限并记录资源归属；仅Task.cancel、停止等待或测试进程退出，不等于子Server和自有后代已回收。
- G组中测试文件/选择器在实现后才存在；必须记录实际收集数。0收集、错误选择器与skip不能算相关行为通过。旧测试失败先修后重跑，不删除安全/业务断言或默认BYPASS换绿。
- 真实终端S组采用离线fake模型和临时本地Server，不收费；L组需额外明确服务、操作和费用后授权，不因四文档批准而自动进行。
- 不把上一阶段的测试计数/截图或参考文档的历史结果复制为本章证据；上一阶段未验项也不被本章追认。
- 结果日志/截图/摘要不得包含真实秘密；不得为证明脱敏而输出密钥原文或扫描并打印真实配置。读取/检查代码只能佐证，安全条目优先记录零调用/零联网/真实副作用等行为。

## 2. 配置、覆盖与变量

- [ ] C01 两层配置都缺失/为空时，正常进入纯聊天和内置工具流程，不创建Host、key、信任记录或额外信任菜单。（验证：G01/G08：临时空home/root，拦截进程/网络/写入并检查次数为0。；对应：AC01、AC24；Task：T01、T06、T12、T54、T55）
- [x] C02 用户/项目map按Server名整条覆盖，来源保留；不从用户层补项目同名条目的缺字段。（验证：G01：构造两层同名/异名配置，检查有效字段与来源。；对应：AC01、AC02；Task：T06）
- [ ] C03 不可读、非法YAML、重复键和非法顶层跳过整层并脱敏告警；其他层仍可用，不声称坏文件实现了禁用。（验证：G01：逐类输入、固定来源告警和有效层结果对照；旧权限安全加载回归。；对应：AC02；Task：T05、T06）
- [ ] C04 单个坏Server不影响同层其他Server；项目同名条目非法或变量缺失时，不回退启动用户同名Server。（验证：G01/G08：同时放好/坏条目，检查实际启动/请求计数，而非仅检查返回列表。；对应：AC02、AC03；Task：T06、T07、T08、T12）
- [x] C05 仅接受显式stdio/http及其字段类型；缺必填、拼错/混用字段、非法header/协议头覆盖均跳过相应Server。（验证：G01：字段正反例含字符串数组/map、大小写重复header和CRLF。；对应：AC03；Task：T07）
- [ ] C06 名字/命名空间标识合法，url仅HTTP(S)，拒绝userinfo/fragment/控制字符；端点预览不泄漏query值。（验证：G01/G09：非法值零请求，检查安全预览和真实合法请求目标不被改写。；对应：AC03、AC11、AC22；Task：T07、T22、T36）
- [ ] C07 command/args以字面程序参数使用，不自动安装或套shell；Windows含PATH解析后bat/cmd入口也拒绝。（验证：G01/G03：禁止实际执行的替身记录argv与入口校验；普通可执行文件用原生fixture对照。；对应：AC03、AC07；Task：T07、T27）
- [x] C08 仅env/headers值单次展开多个${VAR}，不递归展开值中的引用，不展开command/args/url/名字；原配置字节不变。（验证：G01：合成环境、嵌入引用、变量值含引用、各字面字段前后对照。；对应：AC03；Task：T08）
- [ ] C09 未定义变量跳过对应Server并只提示变量名；已定义空值与未定义区分，其他Server可连接。（验证：G01/G08：已定义/空/缺失混合及实际连接数检查，输出无变量值。；对应：AC03、AC22；Task：T08、T09）
- [ ] C10 配置读取拒绝设备/FIFO/不明重定向及不可确认根，不能借文件链接冒充可信用户来源；不可用根仍可纯聊天。（验证：G01/G03/G08：真实临时文件类型/可用链接场景、禁止读取替身和聊天对照；原生缺口另记。；对应：AC02、AC04、AC24、AC25；Task：T05、T12）

## 3. 项目启动信任与持久化

- [ ] H01 项目来源Server首次连接前有真实启动信任选择，拒绝时实际无Server进程、无HTTP请求，其他获准项仍可运行。（验证：G02/G08：拦截与本地Server请求日志核对；不能只断言弹过菜单。；对应：AC04、AC06；Task：T22、T23、T54）
- [ ] H02 默认/空输入/非法输入/EOF/无TTY不生成信任；Ctrl+C取消整个启动，不留input后台任务或连接。（验证：G02/G08：逐种console输入与启动取消，检查票据/进程/请求数。；对应：AC04、AC06、AC21；Task：T22、T23、T54）
- [ ] H03 用户级有效定义按主动信任处理，项目同名覆盖不能继承其来源信任；所有必要选择完成后才启动连接。（验证：G02/G08：用户、项目及覆盖场景记录选择/启动时间顺序。；对应：AC04、AC06；Task：T23、T54）
- [ ] H04 同项目同有效定义重启可复用已记住的信任，但启动信任不产生工具allow规则，也不免除默认工具审批。（验证：G02/G08：同临时home/root两次重建应用，随后真实触发工具审批，检查两个存储域。；对应：AC05、AC14；Task：T17、T21、T23、T51、T55）
- [ ] H05 项目身份、command/args/url、显式env/headers或敏感展开值变化后重问；map排序/规范header大小写不制造无谓变化。（验证：G02：逐字段正反对照和原生重载；不把程序内容认证说成已实现。；对应：AC05；Task：T14、T17）
- [ ] H06 仓库伪造摘要/签名、缺key/坏key/记录版本异常、拷贝到另一项目均不能自授信任，记录不含原配置/秘密。（验证：G02：伪造项目local记录和合成秘密，核对实际零启动及持久文件内容。；对应：AC05、AC06；Task：T14、T17、T21）
- [ ] H07 Windows私有key采用当前用户保护且不进入Server环境、普通IPC结果或日志；不可确认文件类型/重定向安全拒绝。（验证：G02 Windows原生key用例：临时home往返、坏数据及输出/落盘扫描；其他平台不可勾。；对应：AC05、AC06、AC22；Task：T16、T21）
- [ ] H08 POSIX私有key/目录权限及常规文件检查生效，不安全权限/链接/坏key不复用信任，未需要授权时不创建key。（验证：G02 POSIX原生用例：0600/0700与错误权限对照；Windows上的skip不能勾。；对应：AC05、AC06；Task：T15、T17）
- [ ] H09 信任写入固定项目路径，父目录/临时位置不经重定向逃逸；独占创建、原子替换、冲突保留外部编辑，损坏旧记录不被空记录覆盖。（验证：G02/G03：真实临时路径、已有临时目标、并发指纹变化及open/write/fsync/replace故障，核对原字节。；对应：AC05、AC06；Task：T18、T20）
- [ ] H10 Git仓库中的记录/key和本系统临时文件必须未跟踪且被忽略才持久保存；状态不明/未忽略只本次，非Git可按安全本地方式保存。（验证：G02：临时真实Git仓库/非Git目录对照，不改真实项目设置，不让GIT_DIR等环境导向其他仓库。；对应：AC05；Task：T19、T65）
- [ ] H11 保存明确失败显示未记住且可仅本次启动；提交结果未知不启动该Server，取消后如已保存不谎称回滚，控制进程先停稳。（验证：G02/G03/G08：替换前故障/替换后丢应答/取消分别核对磁盘、进程、票据和提示。；对应：AC06、AC21；Task：T13、T20、T21、T23）
- [ ] H12 旧startup/approval ID、取消后的选择以及模型/文件/工具伪信任文本不能产生票据；真实选择与快照/generation绑定。（验证：G02/G08：旧ID/同tick取消/四来源注入，检查实际连接及认证记录不变。；对应：AC06；Task：T21、T22、T23、T61）

## 4. 协议传输、固定控制通道与安全诊断

- [x] P01 安装的固定SDK及握手兼容范围与Plan一致，所需接口真实可导入；不兼容时明确停止接入，不擅自换大版本或提高Python最低版本。（验证：G03 SDK契约：读取实际包元数据/签名/版本集合，再与本地握手记录对照。；对应：AC07、AC08、AC09、AC24；Task：T02、T03、T34）
- [ ] P02 真实stdio Server完成初始化、列工具与调用，收到正确argv/env/cwd；仅基础环境加显式env，Provider key/信任key不继承。（验证：G03原生stdio fixture：记录其实际收到的安全参数和环境，结果经应用回灌。；对应：AC07；Task：T27、T32、T34）
- [x] P03 真实本地HTTP Server完成握手/发现/调用，JSON和POST请求关联SSE均可用，认证头与适用会话/版本信息正确。（验证：G04回环原生HTTP fixture分别运行两种响应形式，检查服务端收到内容。；对应：AC08；Task：T28、T29、T33、T34）
- [ ] P04 JSON-RPC响应按id配对，乱序、通知、未知id、错误不会串结果或无限挂起；初始化不支持版本时清楚失败。（验证：G03/G04：原生可控Server发乱序/通知/错id，记录请求与结果ID和期限。；对应：AC09；Task：T25、T34）
- [ ] P05 不实现的Server发起采样/roots/elicitation等请求不会触发LLM、本地工具或文件访问；Server instructions不成为系统指令。（验证：G03/G04/G08：fixture发额外请求与诱导性instructions，核对回包及零额外动作。；对应：AC09、AC12、AC23；Task：T26、T34、T61）
- [ ] P06 认证不随跨来源或HTTPS降级转发；同源合法重定向可用且最多3跳，不启动OAuth或自动刷新认证。（验证：G04：双回环端点/模拟TLS边界记录真实请求，第二来源不得收到认证。；对应：AC08、AC22；Task：T28、T29）
- [ ] P07 独立GET/恢复流不联网，断流后不重新POST同一非通知请求；正常同源重定向不被误拦为调用重放。（验证：G04：实际GET/POST计数与重定向链，断流后等待到终止检查计数不增加。；对应：AC08、AC20；Task：T30、T41、T42）
- [x] P08 stdio stderr与IPC/协议stdout分离；分片秘密、控制符、超量诊断不回显原始内容，超量后继续drain不堵死Server。（验证：G03/G09：持续原生stderr/拆分合成秘密，捕获全部输出及完成状态，无原始日志落盘。；对应：AC07、AC22、AC25；Task：T10、T27、T61）
- [ ] P09 ControlWorker仅能执行固定配置/信任操作；错type/ID/状态/超长帧拒绝，不能连接Server、执行模型工具或泄漏key。（验证：G03：固定操作白名单和禁止Server/工具替身，真实控制进程正反例。；对应：AC06、AC12、AC21；Task：T11、T12、T13、T21）
- [ ] P10 Host无有效connect票据不启动Server/联网；内部消息错ID/重复结果/超量队列受控失败，Server返回文本不能冒充内部IPC。（验证：G03/G08：真实Host待命与非法控制帧，检查进程/网络/存储副作用。；对应：AC06、AC09、AC12；Task：T24、T25）
- [ ] P11 Host会话由同一owner进入/退出；创建中取消仍接管已创建进程，Job分配失败不发connect，不出现跨Task退出SDK作用域错误。（验证：G03/G06：原生启动取消、WindowsJob失败及owner任务身份/挂起检查。；对应：AC21；Task：T24、T26、T44、T63）

## 5. 发现、连接复用与失效隔离

- [ ] D01 工具分页完整读取，零工具/无工具能力与连接失败可区分；失败发现不留下半套已注册工具。（验证：G03/G04/G06：多页、空目录、无capability、末页错误的实际目录与状态。；对应：AC10；Task：T34、T35、T39）
- [ ] D02 重复/非法/过长cursor及页数/工具数/目录体量超限受控失败，不能无限翻页或部分提交目录。（验证：G03/G04/G10：重复cursor及边界值，核对请求数量和失败项注册数为0。；对应：AC10、AC25；Task：T35、T62）
- [ ] D03 获准Server并发启动，各自30秒总预算含Host创建/握手/全部分页；用户选择不计入，不能按每一步重置。（验证：G06/G10：记录两个Server实际时间区间，慢握手与慢末页缩短预算测试。；对应：AC10、AC25；Task：T35、T39、T62）
- [ ] D04 单Server连接/握手/发现失败或超时只清理它自身；成功Server和内置工具可用，启动取消才整体收尾。（验证：G06/G08：成功/不存在程序/卡住端点混合，实际调用成功项并检查失败资源。；对应：AC10、AC21、AC24；Task：T39、T55、T63）
- [ ] D05 目录在进入TUI前冻结、排序与总上限稳定；不同完成顺序和列表变更通知不改变本次工具快照。（验证：G05/G06：交换完成顺序、通知变更、超量全局候选，比较定义列表和来源。；对应：AC11、AC20；Task：T40）
- [x] D06 后续调用复用同Server会话并发送正确远端原名/参数，不每次重启；业务isError不等于连接失效。（验证：G06：真实连接/启动计数、两次调用和业务报错后正常调用对照。；对应：AC16、AC18；Task：T41）
- [ ] D07 确认失效后及时返回不可用结果，不自动重连/换端点/重放/刷新目录；其他Server与内置工具继续，可用连接数正确变化。（验证：G06/G08/G09：断开后再请求，核对网络计数、错误码、目录不变和其他工具成功。；对应：AC20、AC22；Task：T41、T42、T50、T57）

## 6. 工具目录、Schema与结果适配

- [ ] F01 远端工具具有正确命名空间、描述兜底、来源映射；非法字符/分隔符/超长全名跳过，不截断名称制造碰撞。（验证：G05：同名跨Server、合法边界与非法名组合，检查工具列表和实际原名调用。；对应：AC11；Task：T36、T38、T40）
- [ ] F02 同全名冲突项都跳过并告警，不覆盖内置或已注册工具；其他合法工具仍可发现/执行。（验证：G05/G06：重复名和内置冲突注入，不同发现顺序得到相同结果。；对应：AC11；Task：T36、T40）
- [ ] F03 Schema保留required/enum等原意，自包含object才接入；不支持引用/非法Schema不能靠删约束或静默限制额外属性换取通过。（验证：G05：正反例参数验证与导出定义对照，坏Schema不拖累合法工具。；对应：AC11、AC25；Task：T36、T45）
- [ ] F04 描述可安全显示但不提升为系统指令；Schema含已知秘密/控制注入时跳过而非替换后改语义。（验证：G05/G09：合成秘密置于描述/Schema/元信息，核对模型请求、警告和权限未变。；对应：AC11、AC12、AC22；Task：T36、T61）
- [x] F05 多个文本块按序返回，远端isError保留可用文本并标结构化错误；原call_id/tool_name正确。（验证：G05/G08：多文本/错误/原生回灌对照，错误不被省略标记覆盖。；对应：AC17、AC18；Task：T37、T41、T52）
- [ ] F06 无文本structuredContent可有界转合法JSON文本，有文本不重复；混合非文本明确省略、纯非文本明确不支持、合法空结果不混淆。（验证：G05：每种组合返回并检查模型最终序列化内容；资源URI访问次数为0。；对应：AC17、AC25；Task：T37）
- [ ] F07 同步工具执行入口不会建loop或裸调远端；prepare仅准备预览，普通注册external对象、伪造前缀/对象/generation均不能获得执行权。（验证：G05/G07：零发送替身和生产Registry正反例，原同步工具仍通过。；对应：AC12、AC24；Task：T04、T38、T45）

## 7. 权限规则、模式与四选审批

- [x] R01 完整工具名及单Server末尾星号规则合法，MCP匹配大小写敏感；跨Server/任意位置星号/括号参数语法拒绝，旧规则含Windows路径语义保持。（验证：G07：规则解析/匹配正反例和旧规则全回归。；对应：AC13；Task：T04、T46、T47）
- [ ] R02 同层deny优先、会话>本地>项目>用户首命中；高层allow可覆盖低层deny但规则不创造工具身份，也不覆盖PLAN。（验证：G07：双向冲突矩阵与未连接工具/内置名对照。；对应：AC12、AC13、AC15；Task：T47、T49）
- [ ] R03 DEFAULT/ACCEPT EDITS下未命中规则一律审批，即使readOnlyHint=True；BYPASS可跳工具审批但仍尊重deny/启动信任/参数和身份检查。（验证：G07/G08：四档×规则×只读提示，统计远端执行/审批次数和启动票据。；对应：AC12、AC13；Task：T49、T60）
- [x] R04 PLAN既不向模型提供MCP定义，也在执行端硬拒意外MCP调用；AskUserQuestion和内置读工具保留，/do恢复原默认执行语义。（验证：G07/G08：捕获Plan请求体与注入调用，检查远端0请求，再/do正常审批。；对应：AC15；Task：T45、T49、T60）
- [ ] R05 允许本次只放当前调用，下次同工具仍问；拒绝不执行、不新增deny，可在后续轮调整。（验证：G07/G08：两次同调用与拒绝后续答，检查规则快照和实际Server调用计数。；对应：AC14、AC18；Task：T51、T52、T60）
- [ ] R06 本会话只生成精确工具身份许可，不同工具/Server不复用，跨任务保留、重启清除；不宣称绑定本次参数。（验证：G07/G08：同/异工具与同工具不同参数、多任务和新Engine对照。；对应：AC14；Task：T47、T51）
- [ ] R07 永久允许保存精确完整名，重启复用；不自动保存Server通配，原deny/模式/其他合法数据不损坏，保存失败/未知行为沿用原契约。（验证：G07：临时权限文件真实事务与重载、分阶段故障/丢应答；信任文件未被当作权限文件。；对应：AC14；Task：T48、T51）
- [ ] R08 审批明确显示Server/工具及整工具授权范围，提醒后续不同参数可能复用；批准选择本身不冒充执行成功。（验证：G07/G09：检查实际菜单与最终结果，放行前Server工具执行为0。；对应：AC14、AC22；Task：T51、T58）
- [ ] R09 审批接纳/发送前重核项目根/目录对象/generation和取消；旧ID/同tick取消/身份变化不释放新请求，不新增许可后偷执行。（验证：G07/G08：等待期间变更身份、根、取消/重复选择，核对规则和副作用。；对应：AC12、AC19、AC20；Task：T50、T51、T52）
- [x] R10 内置危险命令/外部文件仍受原硬门禁；外部参数恰含path/command不被伪称已受内置围栏约束，未知工具继续拒绝。（验证：G07/G12：危险样例只判定或禁执行替身，MCP范围文字与裁决对照，旧安全测试保留。；对应：AC12、AC13、AC24；Task：T49、T52）

## 8. Agent闭环、调度、超时与取消

- [ ] A01 统一验证/模式/权限/审批/复核之后才进入外部异步执行，不经普通工具worker重建Server；审批前无远端调用。（验证：G07/G08：实际生产Executor零发送/禁worker替身，批准后原生本地工具执行。；对应：AC12、AC18、AC24；Task：T52、T55）
- [ ] A02 MCP形成串行屏障，不因只读提示并发；混合调用结果按原序与ID配对，内置只读仍最多4项有界并发。（验证：G08：记录开始/结束区间及并发峰值，含成功/拒绝/非法调用，旧调度回归。；对应：AC16、AC19；Task：T53）
- [ ] A03 离线完整闭环跑通：fake模型请求MCP→真实用户选择替身→本地Server执行→回灌→fake模型续答；拒绝/业务错误后可调整继续。（验证：G08：同时检查实际副作用、请求内容、调用次数、最终文本，不用独立函数测试代替。；对应：AC18、AC24；Task：T60）
- [ ] A04 审批等待不占调用30秒预算，调用预算含发送/IPC/SDK等待；超时结构化回灌并隔离该Server，不自动重试未知结果。（验证：G06/G08/G10：短预算+长审批等待对照，真实服务请求计数及错误/会话状态。；对应：AC18、AC20、AC25；Task：T41、T42、T52、T62）
- [ ] A05 用户取消能传达到适用SDK请求并引用正确外部request id；1秒内不能确认则关闭Host，迟到结果不串入下一调用。（验证：G03/G06：本地Server实际捕获取消通知/连接关闭与结果先后，不仅检查Task.cancel。；对应：AC19、AC20；Task：T42）
- [ ] A06 完整结果在后续清理await前保存；取消/清理失败不覆盖已确认成功，未确认发送后的提示不谎称未执行或回滚。（验证：G06/G08：结果到达与取消同tick、保存后清理失败，核对历史状态及样本副作用。；对应：AC19、AC21；Task：T42、T44、T52）
- [ ] A07 审批/执行中关闭流或退出能补齐所有调用结果，已完成副作用不重复，未开始项不执行；取消后新消息可继续。（验证：G08/G09：含两个副作用工具、第二次审批等待、消费流关闭及下一任务，检查历史配对。；对应：AC19、AC24；Task：T53、T56、T58）

## 9. 进程与连接的原生退出证据

- [ ] X01 正常退出时本地Host/stdio Server及拥有的协作式后代实际结束，HTTP本地流/会话关闭，诊断/IPC任务无悬挂。（验证：G03/G04/G06原生生命周期：实际PID/连接/任务状态；只测stub不能勾。；对应：AC21；Task：T24、T26、T27、T43、T63）
- [ ] X02 启动期间取消、Host创建中取消、初始化/发现失败与stderr压力仍执行所有权收尾，失败项不在后台继续写临时样本。（验证：G03/G06原生用例：创建/写入标记与PID结束，包含控制进程。；对应：AC21；Task：T11、T13、T24、T39、T63）
- [ ] X03 所有Server共享5秒正常关闭预算，不逐个累加；适用HTTP终止尽力执行，Server不支持DELETE时不虚报远端已停止。（验证：G04/G06：多个慢关闭Server记录区间/方法与ShutdownReport。；对应：AC21；Task：T43）
- [ ] X04 超预算进入额外2秒受控强制回收，Windows有Job活动进程/PID证据，POSIX有自有后代证据；平台分别记录。（验证：G03/G06原生forced_close：实际检查后代结束；另一平台skip不能一起勾为全平台通过。；对应：AC21、AC25；Task：T24、T44、T63）
- [ ] X05 OS拒绝/无法确认时报告clean=False及Server，不仅停止等待就说清理成功；已确认工具结果仍保留。（验证：G03/G06/G08：回收失败注入及磁盘/进程状态，用户可见诊断与事实一致。；对应：AC21、AC22；Task：T44、T56、T63）
- [ ] X06 重复关闭/CLI finally/TUI退出共享幂等收尾，先冻结与取消Loop并配齐历史，再关MCP及控制进程，无循环等待。（验证：G06/G08：同时触发关闭、未消费事件队列、审批挂起和零Server场景，检查所有owned task。；对应：AC19、AC21、AC24；Task：T43、T56）
- [ ] X07 ControlWorker检查/保存受5秒预算且可取消；提交未知先终止并等待进程，按身份清理资源，不留写入线程/进程。（验证：G02/G03原生control_lifecycle：挂起/取消/替换后丢应答与临时资源身份变化对照。；对应：AC06、AC21；Task：T13、T20、T21）

## 10. TUI自动行为与状态

- [ ] U01 连接数来自真实ready Server：零工具仍算连接、失效减少可用数；注册快照不变，总注册/当前模式可见数分清。（验证：G09：无配置/零工具/多个Server/失效/PLAN的实际状态文本与目录对照。；对应：AC22、AC24；Task：T57）
- [ ] U02 工具行、审批与结果能识别MCP来源，保留模型前文→工具行→审批→结果→续答顺序，并进入scrollback。（验证：G09：两次真实审批+脚本化文本事件，核对组件顺序和已结束菜单不可再提交。；对应：AC14、AC22；Task：T58）
- [ ] U03 1～4、方向/Enter选择与实际四种结果一致；其他文本/空格/y/n不隐式批准或发新任务，默认行为不靠焦点猜测。（验证：G09：Pilot逐键、额外反例与实际Server计数/规则变化。；对应：AC14、AC22；Task：T58）
- [ ] U04 审批时草稿保留、输入禁用，Esc/Ctrl+C只取消当轮，结束/异常后恢复焦点草稿；下一轮可继续，旧事件不清新菜单。（验证：G09：Pilot取消/异常/旧ID后再提交，对照草稿、文件和请求数。；对应：AC19、AC22；Task：T58）
- [ ] U05 需求提问、启动信任与工具审批互不混用；忙碌/等待阶段不偷换权限模式，/plan、/do与Shift+Tab旧行为保持。（验证：G08/G09和旧提问回归：问题/审批交替及忙碌按键，检查当前模式与待答对象。；对应：AC06、AC14、AC15、AC24；Task：T51、T54、T58）
- [ ] U06 窄窗/长预览仍可识别选项，控制符/markup不伪造菜单；检查/审批/执行/清理期间界面可刷新，所有可见秘密被脱敏。（验证：G09：多尺寸Pilot、慢本地Server/保存替身、拆分秘密；真实终端另由S组观察。；对应：AC22、AC25；Task：T10、T57、T58、T61）

## 11. 规模与输入输出预算

- [ ] N01 配置/信任文件各256KiB、展开后1MiB、字段8192字符、128项及16Server限制按Plan生效，排序裁剪不依赖完成先后。（验证：G01/G02/G10：等于/超一临界值，记录哪些Server未启动及限流告警。；对应：AC03、AC10、AC25；Task：T03、T09、T17、T62）
- [ ] N02 发现每Server256工具/64页/cursor4096/累计2MiB，总可注册MCP256，超限处理与稳定快照一致。（验证：G03/G04/G05/G06/G10：各限额独立临界输入与全局多Server对照。；对应：AC10、AC11、AC25；Task：T35、T40、T62）
- [ ] N03 描述8192字符、Schema64KiB/深度16/4096节点及全名64字符受控拒绝；不能静默裁剪合法性约束。（验证：G05/G10：每种等于/超一边界，不支持工具跳过并保留其他工具。；对应：AC11、AC25；Task：T36、T62）
- [ ] N04 调用参数64KiB、IPC帧1MiB、队列32有界；过长/持续坏帧不把内存队列无限堆积或触发重复请求。（验证：G03/G07/G10：原始大小和慢消费者压力，检查零发送/受控关闭与存活任务。；对应：AC12、AC25；Task：T03、T25、T52、T62）
- [ ] N05 HTTP按解码后实际流累计2MiB，JSON/SSE/小分片/压缩/缺失或虚假Content-Length均不能绕过。（验证：G04/G10：实际流式fixture测界限与响应关闭，超量后会话状态正确。；对应：AC21、AC25；Task：T31、T62）
- [ ] N06 模型最终结果含元信息共同不超20,000字符，JSON合法、ID保留、truncated标记明确；长输出不撑爆界面。（验证：G05/G08/G10：大文本/structuredContent/metadata回灌并解析完整结果。；对应：AC17、AC22、AC25；Task：T37、T52、T62）
- [x] N07 诊断单条2048字符、每Server每阶段最多16条、stderr收集16KiB有界；余量drain并计数，错误不携原始SDK堆栈。（验证：G03/G09/G10：超量持续stderr和异常正文，记录展示/收集上限及工具仍能结束。；对应：AC22、AC25；Task：T10、T61、T62）

## 12. 三协议、原能力与构建回归

- [x] B01 Anthropic/OpenAI/Qwen离线实际请求体均有合法MCP定义及配对工具结果，保留各自原生assistant负载而非重新拼坏历史。（验证：G08/G11：三协议传输替身捕获请求体，核对原ID/原生负载和MCP结果。；对应：AC23；Task：T59）
- [ ] B02 发现与等待审批不额外请求LLM或结算Token，原plan提醒/环境采集/缓存统计正确；工具集变更可能改前缀，不假称实际命中缓存。（验证：G08/G11：多任务多轮请求/用量计数，比较相同/不同快照及模式。；对应：AC23；Task：T59）
- [x] B03 依赖锁可校验且仅新增固定SDK所需依赖，Python>=3.11未提高、不安装Server或CLI extras，SDK实际兼容检查有证据。（验证：G03/G13：uv lock --check、锁差异和真实包元数据，不从Plan文字推断已安装。；对应：AC24；Task：T01、T02、T66）
- [ ] B04 源码编译、模块导入与原DTO位置参数/默认兼容通过，新增控制与外部契约不存在循环依赖或共享可变数据。（验证：G05/G07/G13：compileall与契约正反例，原工具仍可运行。；对应：AC24；Task：T03、T04、T66）
- [x] B05 新增与既有全量测试实际通过，失败修复后重跑；0收集/平台skip不计对应通过，不删断言/默认BYPASS换绿。（验证：G13：本次完整pytest输出，记录通过/失败/跳过和原因，旧测试不从上阶段复制。；对应：AC24、AC25；Task：T01、T66）
- [x] B06 差异无空白错误，未配置的Ruff/mypy/pytest-timeout如实标未配置；未跟踪新文件也实际检查，不仅凭git diff为空。（验证：G13与文档/文件差异检查：记录命令退出码和新文件检查结果。；对应：AC24；Task：T66、T69）
- [x] B07 Provider实现、供应商六字段、内置业务Schema及原Loop停止/取消/安全门禁保持；无MCP配置与App后备构造不偷启Server。（验证：G08/G13：基线差异及旧完整回归，生产后备构造零Server启动断言。；对应：AC12、AC13、AC15、AC24；Task：T04、T45、T49、T52、T55、T66）
- [x] B08 示例只有占位程序/地址和${VAR}认证，可在合成环境解析；共享配置/示例不被忽略，本地记录/key相关固定临时名被忽略且未跟踪。（验证：G01/G02/G13：示例加载、虚拟路径check-ignore及临时仓库ls-files对照，不创建真实key。；对应：AC05、AC22、AC25；Task：T65）
- [x] B09 手动入口默认和--help离线，无凭据/真实MCP配置读取、无生产网络/收费；--terminal本地fake，--live单独确认且互斥，不自动安装Server。（验证：G08及默认/--help实际退出输出：禁止加载凭据/网络替身，记录模式边界。；对应：AC24、AC25；Task：T64）

## 13. 真实PowerShell端到端场景（离线，不收费）

- [ ] S01 无MCP临时配置启动正常；内置工具和纯聊天可用，连接数0，没有信任提示、key或Host残留。（验证：用户运行--terminal的无配置场景，观察界面和入口提供的临时资源摘要。；对应：AC01、AC22、AC24、AC25；Task：T67）
- [ ] S02 首次项目stdio Server出现启动信任，跳过时不启动；信任后完成连接发现，但首次工具调用仍出现四选审批。（验证：真实终端先跳过再在同临时样本重启信任，观察本地进程/请求摘要及菜单。；对应：AC04、AC07、AC14、AC22、AC25；Task：T67）
- [ ] S03 同临时项目重启记住启动信任；修改启动配置或合成认证值重启后重新确认，未信任新定义不运行。（验证：入口受控修改临时样本并同目录restart，观察提示次数，不编辑真实home。；对应：AC05、AC06、AC25；Task：T67）
- [ ] S04 四选分别产生本次/会话/永久/拒绝效果；后续不同参数的整工具许可范围提示清楚，重启后只有永久工具许可复用。（验证：同一临时样本按步骤调用/重启，核对安全规则摘要和实际Server调用次数。；对应：AC14、AC25；Task：T67）
- [ ] S05 一好一坏Server时仍可调用好Server；本地HTTP的JSON/SSE工具可用；状态明确连接/工具/不可用数量。（验证：运行本地fixture组合场景，观察工具行、失败提示和最终续答，不连接公网。；对应：AC08、AC10、AC20、AC22、AC25；Task：T67）
- [ ] S06 PLAN无MCP工具，原需求提问正常；/do回默认后MCP需按规则审批；Shift+Tab忙碌时不偷换模式。（验证：真实输入/按键与临时调用摘要观察，禁止用外部Server声称只读绕过。；对应：AC12、AC15、AC25；Task：T67）
- [ ] S07 审批与执行时Esc/Ctrl+C只结束当前任务；草稿/焦点恢复，拒绝/取消后继续聊天，不谎称撤销已执行动作。（验证：两种按键分别手测，观察样本状态、工具结果、后续对话和历史。；对应：AC18、AC19、AC22、AC25；Task：T67）
- [ ] S08 窄窗长预览、方向/Enter与数字选择、滚动历史可用；退出后入口记录的自有Host/stdio后代结束，无继续写样本。（验证：调整真实窗口、滚动和退出，保存必要截图/文字及PID结束摘要；不是用Pilot截图替代。；对应：AC21、AC22、AC25；Task：T67）

## 14. 可选真实模型/外部服务（单独授权）

- [ ] L01 在明确服务域名、协议、模型、工具操作、请求上限和费用并获确认后，跑通真实调用→用户审批→执行→回灌→模型续答。（验证：仅获授权后--live，脱敏记录选择/实际调用/结果/请求数，不自动切换三家重复收费。；对应：AC18、AC23、AC25；Task：T68）
- [ ] L02 同次授权范围内观察真实拒绝后调整/解释及取消后继续；未配置协议或未授权外部Server记未测，不额外重连或重放。（验证：有限样本观察真实模型行为与请求计数，不为得到成功结论扩大收费/副作用范围。；对应：AC19、AC20、AC23、AC25；Task：T68）

## 15. 证据与交付核对

- [ ] Z01 每个勾选项都有本阶段真实操作/命令、结果与平台证据；Task状态同步，测试预计名称不冒充已执行。（验证：逐项核对第18节记录与Task第6节，复合条件缺一则不勾整项。；对应：AC24、AC25；Task：T69）
- [x] Z02 报告明确启动信任/调用许可不同、Server不受内置围栏、签名key不抵挡同用户代码执行、stdio Host非资源沙箱及远端副作用不回滚。（验证：README/报告与批准Spec、Plan对照，不把已接受限制写成已修复。；对应：AC12、AC13、AC19、AC21、AC25；Task：T65、T69）
- [ ] Z03 本章提交不含真实凭据/key/用户样本/无关修改，历史文档不覆盖；只记录实际本地提交，不擅自推送。（验证：检查明确文件差异/暂存清单/status，不读取用户测试目录或真实配置正文。；对应：AC22、AC24、AC25；Task：T69）
- [x] Z04 区分实现/离线验证、原生平台、真实终端、真实模型验收，S/L未运行或平台skip保持未勾，汇总完成不冒充全部验收通过。（验证：交付报告与Task/Checklist逐项交叉检查。；对应：AC24、AC25；Task：T15、T16、T63、T67、T68、T69）

## 16. 验证组与执行方式索引

下列是四文档批准后执行的命令，不是当前结果。命令均从项目根运行，组内出现的所有场景需要确实被测试覆盖；同组pytest通过不自动证明清单上没有实现的场景。按Task的 -k 可局部运行，最终记录实际收集和覆盖范围。

| 组 | 命令或方式 | 证据范围 |
|---|---|---|
| G01 | `uv run pytest -q -ra tests/test_mcp_config.py tests/test_permission_settings.py` | 临时两层配置、安全YAML、变量与字段 |
| G02 | `uv run pytest -q -ra tests/test_mcp_trust.py` | 信任、key/DPAPI、签名、Git/保存故障；平台原生结果分开 |
| G03 | `uv run pytest -q -ra tests/test_mcp_process.py` | SDK契约、固定控制/Host协议、原生stdio/进程 |
| G04 | `uv run pytest -q -ra tests/test_mcp_http.py` | 回环原生HTTP、JSON/SSE、来源/重放/流预算 |
| G05 | `uv run pytest -q tests/test_mcp_tool.py tests/test_tool_registry.py` | 工具目录/Schema/内容/可信注册 |
| G06 | `uv run pytest -q -ra tests/test_mcp_manager.py` | 并发、缓存、失效、取消、正常/强制关闭 |
| G07 | `uv run pytest -q -ra tests/test_mcp_permissions.py tests/test_permission_rules.py tests/test_permission_settings.py tests/test_permission_persist.py tests/test_approvals.py` | 旧权限语义、新身份/模式/规则/四选与事务 |
| G08 | `uv run pytest -q -ra tests/test_mcp_integration.py tests/test_cli.py` | 本地Server+fake模型完整闭环、装配、三协议、手动入口保护 |
| G09 | `uv run pytest -q tests/test_mcp_tui.py tests/test_tool_tui.py tests/test_tui.py tests/test_redaction.py` | Pilot实际按键/状态/草稿/历史/分片脱敏；非真实终端 |
| G10 | `uv run pytest -q tests/test_mcp_config.py tests/test_mcp_tool.py tests/test_mcp_http.py tests/test_mcp_manager.py tests/test_mcp_integration.py -k mcp_budget` | Plan规模临界值与可注入期限，选择器须实际收集 |
| G11 | `uv run pytest -q tests/test_mcp_integration.py tests/test_prompt_protocols.py tests/test_cache_usage.py tests/test_provider_events.py tests/test_protocol_integration.py` | 三协议请求体、原生负载、提醒、用量和缓存回归 |
| G12 | `uv run pytest -q -ra tests/test_permission_blacklist.py tests/test_permission_sandbox.py tests/test_permission_io.py tests/test_tool_executor.py tests/test_tool_scheduler.py tests/test_file_tools.py tests/test_search_tools.py tests/test_command_tool.py tests/test_user_questions.py tests/test_turn_runner.py` | 原安全/业务/生命周期/提问/Loop回归，不删原断言 |
| G13 | `uv lock --check；uv run python -m compileall -q src；uv run pytest -q -ra；git diff --check` | 各命令分别记录，完整回归、锁、编译、差异，不以一项替代另一项 |

原生生命周期专项可用Task T63的 `-k native_lifecycle`；SDK/控制协议、信任保存与取消等定向选择器按对应Task使用，不会因为只选择部分测试就声称整组通过。确需正常主机进程权限时单独申请，不能静默删除原生验证。

真实终端（T67）：用户在PowerShell运行 `uv run python tests/manual_mcp_smoke.py --terminal`，仅临时root/home与本地fixture，按S组逐项观察。入口必须支持同一临时样本重启，不能把换了项目的两次运行冒充持久信任/永久许可重载。

可选真实模型/外部服务（T68）：明确授权后才运行 `uv run python tests/manual_mcp_smoke.py --live`。记录服务域名/协议/模型、允许操作、次数/期限和费用提示，不记录认证头/key，不自动轮换多家服务。默认及--help也需要单独离线验证。

忽略规则采用虚拟路径检查：`git check-ignore -v --no-index .weizhcode/mcp-trust.local.json .weizhcode/.mcp-trust.fake.tmp docs/mcp/mcp-servers.example.yaml`，应仅local/临时路径命中，共享示例不命中。已跟踪检查、key路径保护与不安全Git环境在临时仓库验证，不创建真实项目许可文件。

## 17. Spec验收覆盖映射

映射只表明设计覆盖，不是通过凭证。一条AC对应多项/平台/场景时，相关必要条件未验证就不能宣称整条AC完成；可选L组和真实S组没运行必须单列，不能用离线G组替代。

| Spec AC | Checklist条目 |
|---|---|
| AC01 | C01、C02、S01 |
| AC02 | C02、C03、C04、C10 |
| AC03 | C04、C05、C06、C07、C08、C09、N01 |
| AC04 | C10、H01、H02、H03、S02 |
| AC05 | H04、H05、H06、H07、H08、H09、H10、B08、S03 |
| AC06 | H01、H02、H03、H06、H07、H08、H09、H11、H12、P09、P10、X07、U05、S03 |
| AC07 | C07、P01、P02、P08、S02 |
| AC08 | P01、P03、P06、P07、S05 |
| AC09 | P01、P04、P05、P10 |
| AC10 | D01、D02、D03、D04、N01、N02、S05 |
| AC11 | C06、D05、F01、F02、F03、F04、N02、N03 |
| AC12 | P05、P09、P10、F04、F07、R02、R03、R09、R10、A01、N04、B07、S06、Z02 |
| AC13 | R01、R02、R03、R10、B07、Z02 |
| AC14 | H04、R05、R06、R07、R08、U02、U03、U05、S02、S04 |
| AC15 | R02、R04、U05、B07、S06 |
| AC16 | D06、A02 |
| AC17 | F05、F06、N06 |
| AC18 | D06、F05、R05、A01、A03、A04、S07、L01 |
| AC19 | R09、A02、A05、A06、A07、X06、U04、S07、L02、Z02 |
| AC20 | P07、D05、D07、R09、A04、A05、S05、L02 |
| AC21 | H02、H11、P09、P11、D04、A06、X01、X02、X03、X04、X05、X06、X07、N05、S08、Z02 |
| AC22 | C06、C09、H07、P06、P08、D07、F04、R08、X05、U01、U02、U03、U04、U06、N06、N07、B08、S01、S02、S05、S07、S08、Z03 |
| AC23 | P05、B01、B02、L01、L02 |
| AC24 | C01、C10、P01、D04、F07、R10、A01、A03、A07、X06、U01、U05、B03、B04、B05、B06、B07、B09、S01、Z01、Z03、Z04 |
| AC25 | C10、P08、D02、D03、F03、F06、A04、X04、U06、N01、N02、N03、N04、N05、N06、N07、B05、B08、B09、S01、S02、S03、S04、S05、S06、S07、S08、L01、L02、Z01、Z02、Z03、Z04 |

Task T01～T69均有至少一个条目定位；该映射不改变批准Task的依赖和实施范围。若实际测试组织变更，只更新定位与真实记录；改变行为或技术方案须重批相关文档，不能在验收时删条件。

## 18. 实际结果登记（完整接入后）

当前：**21/107个复合条目已有完整覆盖而勾选；其余保持未勾，不等于对应功能都未实现。** 已实际接通独立配置→真实启动选择/持久信任→官方SDK Host→发现/注册→权限四选→工具调用/回灌→TUI状态→关闭。本章严格清单包含大量故障注入、跨平台和现场观察；没有把“代码存在”或一次全量通过当作107项全部验收。

### 18.1 本次真实执行

| 记录 | 实际结果 |
|---|---|
| 基础历史 | 4e02a7e阶段653 passed/3 skipped/112.80s；那时仅基础契约，不能当当前原生接入证据 |
| 首次接入全量 | 679 passed、2 failed、4 skipped/119.03s；失败为隔离测试0.8秒不足、旧EventsRunner没有executor；均修复，未删断言 |
| 定向修复 | Manager/Bootstrap/Trust/TUI/旧ToolTUI：39 passed、1 skipped/30.77s |
| 边界回归 | 工具/权限/HTTP/配置/Manager/Bootstrap/TUI：88 passed/35.19s；HTTPX同源重定向曾触发RequestNotRead，实际读取请求体后重跑通过 |
| 原生专项 | Manager/HTTP/Process/Tool/Permissions/Bootstrap/TUI：64 passed/46.39s，含Windows自有孙进程退出；非POSIX替代证据 |
| 最终完整回归 | `uv run pytest -q -ra --tb=short`：**723 passed、4 skipped，146.22s，退出0** |
| 平台跳过 | POSIX key原生权限分支、原POSIX进程专项、当前机器不能创建原生目录链接的两个旧用例；全部保持待验 |
| 锁/编译 | `uv lock --check`：50 packages/退出0；`uv run python -m compileall -q src`退出0；Python最低仍3.11 |
| 差异 | `git diff --check`退出0；明确新增MCP代码/测试/示例的尾随空白检索无命中（rg退出1）；Ruff/mypy/pytest-timeout未配置，未安装或假报通过 |
| 观察入口 | 默认及--help实际退出0，输出离线说明；manual_mcp_guards禁止凭据读取、terminal/live互斥测试通过 |
| 示例/忽略 | 合成CONTEXT7_API_KEY/DEMO_TOKEN解析得到context7、local_demo两项且零警告；local/key/temp命中Git忽略，共享示例不命中 |
| 外部访问 | 只用临时root/home、本地stdio/回环HTTP fixture、fake模型及合成秘密；没有真实配置/凭据访问、生产MCP或收费LLM调用 |
| 提交 | 仅本章明确文件作本地提交，以Git记录为准；不包含.weizhcode-test/、hello.txt或真实weizhcode.yaml，不推送 |

### 18.2 勾选证据定位

- C02/C05/C08：test_mcp_config的整条覆盖、显式字段/header/一次变量展开及非法值矩阵。
- P01：test_sdk_contract、原生stdio/HTTP握手、不支持版本隔离；mcp==1.30.0与四版本集合一致。
- P03：test_fixture_http_native_handshake_response_forms的JSON/SSE两形态，服务端实际记录认证头及请求数。
- P08/N07：test_diagnostics_drain_redaction + test_stdio_environment_and_bounded_diagnostics；真实100KB stderr、拆分合成秘密、控制符、最多16条与16KiB收集上限，Server未阻塞。
- D06：test_native_handshake_call_cache_close_budget；多次同PID调用，业务错误后成功。
- F05：test_result_projection及原生错误/Agent回灌；多文本、isError与原call_id保持，最终模型结果合法。
- R01/R10：test_external_mode_matrix_and_explicit_deny、test_external_rules_case_scope_and_deny，加原权限规则/黑名单/路径/执行器全量回归。
- R04：test_mcp_loop_plan_cancel_recovery、原plan/do/AskUserQuestion回归；外部定义不可见且执行硬拒，默认模式恢复审批。
- B01：test_mcp_protocol三协议实际请求体，原协议集成/历史负载全量回归。
- B03/B05/B06/B07：上述最终全量、锁/编译/差异记录，Provider/六字段/内置业务Schema未修改，无MCP原CLI/界面测试保留。
- B08/B09：上述示例/忽略与默认/帮助运行，test_manual_mcp_guards。
- Z02/Z04：README实际风险说明与本节分层记录；未运行S/L或POSIX绝不算通过。

### 18.3 部分已验证但保持未勾

- 信任已测试真实Control往返、DPAPI保存/重载、HMAC伪造、认证/配置变化、原子冲突、临时Git忽略与确认中项目根替换；尚未穷尽每个open/write/fsync/replace故障、提交后丢回包和所有文件重定向形式。
- Host/Manager已测试并发失败隔离、重复/坏Schema、多页/零工具、256/257工具、64/65页、cursor4096/4097、2MiB目录超限、超时/取消/不重放及孙进程回收；尚未穷尽乱序/未知ID、额外Server能力请求、1MiB/32队列恶意压力及所有OS拒绝注入。
- Schema深度/节点/大小、参数/结果体量、普通与压缩HTTP解码预算、同源重定向和跨源拒绝已测试；“每一阈值等于及超一”的全组合未穷尽，N组复合项不会因此整项勾选。
- 四选真实Agent闭环、永久精确许可重载、PLAN硬拒、取消后继续与Pilot 1/2/3/4/Esc草稿恢复已测试；MCP专属窄窗/长预览/方向键/所有同tick与多工具混合故障矩阵未穷尽，不以旧通用测试代替全部专属场景。
- 正常与强制关闭实现共享预算，Windows Job活动数/实际子孙PID结束有证据；多Server慢关闭、所有回收拒绝、POSIX原生尚未完整观察。无法确认时返回clean=False并显示Server，不虚称回滚或清理成功。

### 18.4 现场与授权边界

- S01～S08：真实PowerShell未运行；用户可执行 `uv run python tests/manual_mcp_smoke.py --terminal`，仅临时样本、fake模型和本地Server，同样本支持restart/change。
- L01/L02：未授权、未运行；真实模型费用、生产MCP域名及具体工具操作需单独确认，不为通过验收自动轮换服务。
- 已接受限制：启动信任不等于工具许可；外部Server不受内置路径围栏/命令黑名单约束；私有签名key不防同用户代码执行；Host不是资源沙箱；取消/超时不保证远端副作用回滚。

## 19. 审批边界

本Checklist获明确批准后，四份文档的设计审批才全部完成，可以按已批准Task实施并逐项收集证据。当前回复只登记Task批准并生成本文件，没有授权或执行其中的未来命令。

批准不涵盖真实危险命令、修改用户真实凭据/信任/权限文件、生产MCP连接、收费模型、自动Server安装或推送GitHub；需要这些动作时另行明确范围与授权。历史阶段文档与用户文件保持不动，未发现的SDK/平台不兼容不能默默用降级/越权方案掩盖。
