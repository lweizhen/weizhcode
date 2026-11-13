# weizhCode 工具系统 Checklist

> 状态：本文已获用户明确批准；四份文档全部获批，已进入开发，验收项仅在真实验证后更新。
> 依据：[specs/tool-system/spec.md](D:/STUDY/weizhcode-python/specs/tool-system/spec.md)、[specs/tool-system/plan.md](D:/STUDY/weizhcode-python/specs/tool-system/plan.md)、[specs/tool-system/task.md](D:/STUDY/weizhcode-python/specs/tool-system/task.md)。
> 共 82 项。每项以运行结果或实际观察为证据，聚焦行为，不以类名、文件位置或代码“看起来正确”代替验证。执行后逐项记录见下文，未全部验收通过。

## 使用规则与验收边界

- 四份文档全部批准后才开始实现和执行本清单；批准前三份不等于已经批准开发。
- 只有该项全部预期行为真实通过才勾选，并追加执行日期、平台、验证模式、命令或场景、实际输出/观察及安全的证据位置。
- 失败、未运行、缺凭证、平台不支持或环境不足均保持未勾选，分别注明原因与影响；单元测试 skip 不代表原生平台已实测通过。
- 自动模拟流、无界面 UI、真实终端、真实 API 分开记录，不互相冒充。真实 API 有独立项目，未执行不标为通过。
- 命令从 D:/STUDY/weizhcode-python 执行。测试选择器沿用 Tasks 的规划，必须实际收集目标用例；空集合/全部 deselected 不算通过。
- 写入、替换、命令和超时实验仅使用受控临时目录与无敏感样本，不改用户实际项目源码或原配置来完成验收。
- 用户已允许本阶段以 Windows PowerShell 真实终端替代 tmux，不安装额外系统组件、不修改通用仓库说明；不能把无界面测试当作这份真实终端证据。
- 生产工具执行预算仍为 30 秒；自动测试可以注入短预算，等待审批不计入，不新增用户配置。
- 进程管理不是沙箱，强制终止不是回滚；不宣称识别所有秘密或控制主动脱离受管范围的独立任务。
- 发现需要新凭证、模型更换、原配置修改、系统组件安装或超出已批准范围时，先询问用户。
- 已获开发批准并执行验证；勾选只依据下方实际证据。

## 检查分组

| 分组 | 检查编号 | 数量 |
|------|----------|------|
| 实现完整性 | C01～C19 | 19 |
| 审批与生命周期 | C20～C31 | 12 |
| 协议集成 | C32～C41 | 10 |
| 单轮闭环与历史 | C42～C51 | 10 |
| 界面与会话回归 | C52～C58 | 7 |
| 结果体量与安全 | C59～C66 | 8 |
| 编译与自动测试 | C67～C72 | 6 |
| PowerShell 端到端 | C73～C78 | 6 |
| 真实 API 单独验收 | C79～C81 | 3 |
| 交付与验收报告 | C82～C82 | 1 |

## 实现完整性

- [x] **C01：六工具与定义** 可用工具恰为已批准的六个，名称和导出顺序稳定，每项包含描述与完整参数约束。（验证：运行注册与请求体测试，观察六条定义及 read_file/write_file/edit_file/run_command/find_files/search_content 的参数。 对应：F1、AC1；任务：T3、T9、T26。）

  证据（2026-11-13，Windows）：test_tool_registry / test_provider_tools：6 个定义、稳定顺序和三协议请求体。自动验证的完整统计见下方执行记录；C81 为独立真实 API。

- [x] **C02：注册与查询失败** 重复工具名称明确报错且不覆盖原工具；未知名称不会命中其他工具。（验证：运行 test_tool_registry.py 的 registry 用例和执行器未知工具用例。 对应：F1、F13、AC1、AC10；任务：T9、T31。）

  证据（2026-11-13，Windows）：test_tool_registry / test_executor_validation_does_not_start_worker：重复、未知工具与零进程。自动验证的完整统计见下方执行记录；C81 为独立真实 API。

- [x] **C03：分段读取** 读取内容和原始行号正确；指定起始行/行数生效，超过 EOF 正常返回空片段，截断说明后续读取位置。（验证：用已知逐行编号文件验证默认读取和指定区间，对照原文件内容；运行 read_file 用例。 对应：F2、AC2；任务：T10、T11。）

  证据（2026-11-13，Windows）：test_read_file_pagination_and_eof：200 行、区间、EOF、后续位置。自动验证的完整统计见下方执行记录；C81 为独立真实 API。

- [x] **C04：读取错误** 不存在、目录、不可读、二进制和不支持编码的目标均返回明确错误，不崩溃，也不以替换字符伪装正常文本。（验证：分别构造受控样本运行 read_file/text_format 测试，断言错误分类及磁盘未改变。 对应：F2、F13、N4、AC2、AC10；任务：T10、T11。）

  证据（2026-11-13，Windows）：test_read_file_rejects_binary_and_encoding / permission_failure_structured / errors_and_large_line。自动验证的完整统计见下方执行记录；C81 为独立真实 API。

- [x] **C05：创建与覆盖** 批准后能创建、覆盖、写空内容和自动创建父目录，内容与请求一致。（验证：使用临时嵌套路径进行写入并按字节读回；结合 write_execute 和 executor_approval 测试。 对应：F3、AC3；任务：T14、T15、T33。）

  证据（2026-11-13，Windows）：test_write_execute_create_overwrite_format / approval_ui_write_and_decision_binding。自动验证的完整统计见下方执行记录；C81 为独立真实 API。

- [x] **C06：唯一替换与删除** 原文唯一匹配且获批准后，精确替换成功；新文为空可以删除唯一片段。（验证：分别执行唯一替换与空新文场景，按字节检查仅对应片段改变。 对应：F4、AC4；任务：T17、T18、T33。）

  证据（2026-11-13，Windows）：test_edit_execute_bom_and_unchanged_mixed_newlines：替换与空新文。自动验证的完整统计见下方执行记录；C81 为独立真实 API。

- [x] **C07：匹配错误可区分** 0 次、多次和空原文均不修改文件；前两者包含实际匹配数，空原文为参数错误。（验证：构造 0/1/3 处和空原文样本运行 exact_scan/edit_prepare，比较计数、错误分类及原文件字节。 对应：F4、F13、AC4、AC10；任务：T16、T17、T31。）

  证据（2026-11-13，Windows）：test_edit_prepare_reports_actual_match_count / stale_and_empty_original：0、多次、空原文。自动验证的完整统计见下方执行记录；C81 为独立真实 API。

- [x] **C08：不进行模糊编辑** 空白、大小写和原文 CRLF/LF 差异不会被静默忽略；跨读取块的原文能正确计数和定位。（验证：运行跨块、多字节、换行不一致和相似文本样本，验证精确匹配及失败无写入。 对应：F4、AC4；任务：T16、T17、T18。）

  证据（2026-11-13，Windows）：test_exact_scan_count_across_chunks / edit_prepare_precise_and_readonly。自动验证的完整统计见下方执行记录；C81 为独立真实 API。

- [ ] **C09：审批预览失效** 审批期间内容变化、目标被替换、路径转向或原本不存在的文件出现时，旧操作被拒绝，不覆盖新状态。（验证：在准备后改变临时目标再批准，观察 PREVIEW_STALE 并检查新内容保持不变。 对应：F3、F4、F12、AC3、AC4；任务：T12、T15、T18、T33。）

  状态（2026-11-13）：部分验证：内容变化及新文件出现保护通过；路径重定向/目录链接样本受本机创建链接权限限制，未完整原生验证。

- [x] **C10：编码和换行保留** 新文件为 UTF-8 无 BOM/LF；已有文件保留 BOM、原换行风格，混合换行未修改部分不被重写。（验证：对 BOM、LF、CRLF、混合换行及新增换行的样本做写/改，比较原始字节，验证主导换行及并列规则。 对应：N4、AC13；任务：T10、T13、T15、T18。）

  证据（2026-11-13，Windows）：test_text_format_snapshot / write_execute_create_overwrite_format / edit_execute_bom_and_unchanged_mixed_newlines。自动验证的完整统计见下方执行记录；C81 为独立真实 API。

- [ ] **C11：命令与目录准备** Windows 使用 PowerShell、POSIX 使用系统 shell；默认/指定目录正确，准备时不启动命令、不改变应用目录。（验证：运行 command_prepare 平台分支测试，检查所选 shell、解析目录、无效目录错误和零进程启动。 对应：F5、F12、AC5；任务：T24、T33。）

  状态（2026-11-13）：Windows shell 选择、目录与无准备副作用通过；POSIX 原生未执行。

- [x] **C12：命令输出与退出码** 标准输出、标准错误与实际退出码可区分；非零退出返回失败而非成功。（验证：执行受控 stdout/stderr/非零命令，运行 command_output/output_pressure，检查来源标签与 COMMAND_FAILED。 对应：F5、F13、AC5、AC10；任务：T25、T35。）

  证据（2026-11-13，Windows）：test_command_output_stdout_stderr_nonzero：stdout、stderr、退出码 7。自动验证的完整统计见下方执行记录；C81 为独立真实 API。

- [x] **C13：命令之间无状态继承** 上一命令中的 cd 或环境变量修改不改变下一命令的目录和变量；不要求交互输入。（验证：连续执行受控目录/环境修改和查询，确认默认目录保持启动目录，stdin 关闭，任务能结束或超时。 对应：F5、AC5；任务：T24、T25。）

  证据（2026-11-13，Windows）：test_command_output_cwd_and_environment_do_not_persist。自动验证的完整统计见下方执行记录；C81 为独立真实 API。

- [x] **C14：glob 文件查找** 模式能匹配根目录及嵌套文件，结果为文件路径，不把目录作为文件命中；分隔符和大小写按平台约定处理。（验证：用 **/*.py 等模式检索临时目录，比较根目录/子目录文件及平台样本。 对应：F6、AC6；任务：T19、T21。）

  证据（2026-11-13，Windows）：test_find_files_glob_root_and_recursive / empty_and_cap / character_budget。自动验证的完整统计见下方执行记录；C81 为独立真实 API。

- [x] **C15：普通文本与正则** 默认将点号、括号等按原文搜索并区分大小写；仅显式选择正则才解释模式，非法正则返回错误。（验证：运行 search_literal/search_limits，用同一含元字符的模式分别以文本和正则检索，对照文件/行/命中内容。 对应：F7、F13、AC6、AC10；任务：T22、T23。）

  证据（2026-11-13，Windows）：test_search_literal_not_regex_and_case / search_limits_regex_and_invalid。自动验证的完整统计见下方执行记录；C81 为独立真实 API。

- [x] **C16：忽略与隐藏规则** 默认遵循各级 .gitignore 并跳过隐藏项；祖先作用域、否定与目录排除正确，两个包含开关互不代替。（验证：运行 gitignore_scope/search_walk/find_files，在嵌套规则、从子目录搜索及四种开关组合下核对结果。 对应：F8、AC6；任务：T19、T20、T21、T23。）

  证据（2026-11-13，Windows）：test_gitignore_scope_nested_and_ancestor / flags_are_independent。自动验证的完整统计见下方执行记录；C81 为独立真实 API。

- [ ] **C17：符号链接与直接路径** 目录链接环不会造成无限遍历；显式指定目标目录可以搜索；直接读取不受搜索过滤影响，不新增路径白名单。（验证：在受控临时目录构造可用链接环及被忽略文件，验证搜索结束和直接读取；平台不支持的样本明确记 skip。 对应：F2、F8、AC2、AC6；任务：T11、T19、T21。）

  状态（2026-11-13）：直接路径/过滤行为通过；Windows 目录链接环样本因权限不足 skip，不能声明此项完整通过。

- [x] **C18：正常空结果** 完整搜索无匹配项为成功空结果，能与根目录不存在、无权限或模式非法区分。（验证：分别运行无命中、缺失根、访问失败和非法正则样本，比较结构化状态。 对应：F6、F7、F8、F13、AC6、AC10；任务：T19、T21、T23。）

  证据（2026-11-13，Windows）：test_find_files_empty_and_cap / search_walk_permission_failure_is_not_empty_success。自动验证的完整统计见下方执行记录；C81 为独立真实 API。

- [x] **C19：不完整检索说明** 二进制和非 UTF-8 文件跳过并报告数量；权限等中途失败携带原因和有限部分结果，不伪装为完整无匹配。（验证：运行编码跳过和访问中断样本，检查计数、SEARCH_INCOMPLETE、部分结果及后续会话可用。 对应：F7、F8、F13、AC6、AC10；任务：T19、T22、T23。）

  证据（2026-11-13，Windows）：test_search_limits_binary_encoding_and_long_lines / search_walk_permission_failure_is_not_empty_success。自动验证的完整统计见下方执行记录；C81 为独立真实 API。

## 审批与生命周期

- [x] **C20：读取类自动执行** 读文件、找文件、搜内容无需审批即可执行，且不会误用写入或命令权限。（验证：运行 executor_readonly，记录审批回调零次、正确工具结果和状态。 对应：F2、F6、F7、F12、AC2、AC6；任务：T32。）

  证据（2026-11-13，Windows）：test_executor_readonly_no_approval：三种只读工具的真实工作进程。自动验证的完整统计见下方执行记录；C81 为独立真实 API。

- [x] **C21：批准对象明确** 写、改、命令预览对应实际目标；命令与 cwd 完整可见，文件预览截断有提示，批准只绑定本次操作。（验证：对照受控调用参数、显示预览和实际落地目标，运行 operation_contract/approval_ui/executor_approval。 对应：F12、AC3、AC4、AC5；任务：T4、T14、T17、T24、T33、T50。）

  证据（2026-11-13，Windows）：test_operation_contract_parameters_separate_from_preview / approval_ui_write / app_shutdown_running_command_ui。自动验证的完整统计见下方执行记录；C81 为独立真实 API。

- [x] **C22：等待期间无副作用** 在批准前不创建父目录、不写文件、不启动用户命令；工具准备只读。（验证：暂停审批回调，比较临时目录树、文件字节和受控命令标记，确认全部不变。 对应：F3、F4、F5、F12、AC3、AC4、AC5；任务：T14、T17、T24、T33。）

  证据（2026-11-13，Windows）：test_write_prepare_no_side_effects / edit_prepare_precise_and_readonly / command_prepare_no_process_or_cwd_mutation。自动验证的完整统计见下方执行记录；C81 为独立真实 API。

- [x] **C23：拒绝能被解释** 拒绝或没有审批处理器时不执行，返回可区分的拒绝结果，模型据此生成一次最终文字答复，会话继续。（验证：运行 executor_approval/runner_tool_round，断言无副作用、USER_DENIED、一次最终请求及后续正常提问。 对应：F12、F13、AC3、AC10；任务：T31、T33、T46。）

  证据（2026-11-13，Windows）：test_executor_approval_missing_handler_denies / runner_tool_round / protocol_integration_boundaries(denied)。自动验证的完整统计见下方执行记录；C81 为独立真实 API。

- [x] **C24：一次决定一次执行** 允许/拒绝决定只消费一次，重复点击、错误操作标识或过期审批不能批准其他调用或重复执行。（验证：运行 worker_protocol/managed_worker/executor_approval/approval_ui，用操作计数和实际文件确认执行次数。 对应：F12、AC3、AC5、AC10；任务：T29、T30、T33、T50。）

  证据（2026-11-13，Windows）：test_managed_worker_read_and_duplicate_execute / worker_protocol_wrong_operation_id / approval_ui_write_and_decision_binding。自动验证的完整统计见下方执行记录；C81 为独立真实 API。

- [ ] **C25：默认不批准** 审批在对话区呈现，初始焦点为拒绝；没有用户明确选择就不继续，也没有长期免确认入口。（验证：通过 Pilot 和真实界面观察按钮焦点、等待状态及一次决定后两个按钮禁用。 对应：F12、AC3、AC11；任务：T50、T59。）

  状态（2026-11-13）：Pilot 观察默认拒绝、无自动批准和禁用按钮通过；真实 PowerShell 观察待用户完成。

- [x] **C26：共享 30 秒预算** 准备与执行累计最多 30 秒，不按阶段重置；等待审批不计时，批准后只使用剩余预算。（验证：以内部短预算测试准备耗时、执行耗时和更长审批等待，并核对生产常量仍为 30 秒、无新增配置。 对应：N1、AC5；任务：T6、T34。）

  证据（2026-11-13，Windows）：test_executor_timeout_approval_pauses_budget / budget_not_reset：内部短预算验证，生产仍 30 秒。自动验证的完整统计见下方执行记录；C81 为独立真实 API。

- [ ] **C27：超时真正终止进程** 超时后工作进程、命令及受管后代均结束，保留有限输出并返回超时，不只是在界面显示超时。（验证：运行 process_tree/executor_timeout，记录受控父子进程身份及结束断言；本机 Windows 验证 Job，POSIX 在对应系统验证。 对应：F5、N1、AC5、AC10；任务：T27、T28、T30、T34、T35。）

  状态（2026-11-13）：Windows Job 父子进程超时终止通过；POSIX 原生进程组未执行。

- [x] **C28：进程控制失败关闭执行** 无法建立必要进程管理时返回明确错误，待命进程被清理，用户命令未启动。（验证：注入 Job/进程组控制失败，检查 PROCESS_CONTROL_FAILED、启动标记不存在以及句柄/进程回收。 对应：F13、N1、AC5、AC10；任务：T27、T28、T30。）

  证据（2026-11-13，Windows）：test_windows_job_assignment_failure_prevents_execution：Windows Job 失败关闭分支。自动验证的完整统计见下方执行记录；C81 为独立真实 API。

- [x] **C29：所有结束路径收尾** 正常结束、拒绝、异常、超时和退出应用后，管道与受管工作进程均被回收；重复关闭无新副作用。（验证：运行 managed_worker/executor_timeout/app_shutdown，在每条路径检查进程、管道与晚到执行标记。 对应：N1、N2、AC5、AC11；任务：T30、T34、T54。）

  证据（2026-11-13，Windows）：test_managed_worker_read_and_duplicate_execute / process_tree_timeout / app_shutdown_*：Windows。自动验证的完整统计见下方执行记录；C81 为独立真实 API。

- [ ] **C30：临时文件清理归属** 失败/超时清理本轮登记的临时文件，不删除用户已有文件；不将强制终止描述为副作用回滚。（验证：注入临时写入失败/退出，检查本轮残留及旁边预置文件；核对超时结果和界面没有虚假回滚声明。 对应：F3、F4、F13、N1、AC3、AC4、AC10；任务：T13、T30、T34。）

  状态（2026-11-13）：原子写失败及预置同名临时文件不删除用例通过；强制终止写入中的资源登记清理还没有独立受控样本，保留未勾选。

- [ ] **C31：等待和执行不冻结界面** 等待审批、慢命令和耗时搜索期间仍能处理滚动、状态刷新及退出。（验证：运行非阻塞 UI 测试并在真实 PowerShell 观察慢任务；不把暂停的模型请求或阻塞工具放进按钮事件处理器。 对应：N2、AC11；任务：T32、T50、T51、T54、T61。）

  状态（2026-11-13）：无界面审批、执行状态、退出响应测试通过；真实 PowerShell 慢任务及滚动仍待手测。

## 协议集成

- [x] **C32：三后端请求定义正确** 三种协议的首次请求均携带六定义和内置使用约定，保持各自端点与格式；支持的后端禁用并行，选择工具仍为 auto。（验证：分别检查 anthropic_payload/openai_payload/qwen_payload 的模拟请求体与 prompts 用例，不只比较自然语言答复。 对应：F1、F9、F14、AC1、AC12；任务：T3、T9、T26、T37、T38、T40、T42、T44。）

  证据（2026-11-13，Windows）：test_stream_tool_fragments_and_roundtrip / prompts_match_tools：三协议定义与工具控制字段。自动验证的完整统计见下方执行记录；C81 为独立真实 API。

- [x] **C33：碎片组装不串调用** 分片到达的名称、ID 和 JSON 参数能够正确组装；交错调用独立累计，最终完整参数不被重复追加。（验证：运行三个 tool_stream 测试，覆盖中文、转义、多个 index、空增量、最终完整项，并对照预期原始参数。 对应：F10、F14、AC7、AC12；任务：T3、T5、T39、T41、T43。）

  证据（2026-11-13，Windows）：test_interleaved_tool_streams_share_no_buffers / stream_tool_fragments_and_roundtrip：三协议交错、中文及完整参数。自动验证的完整统计见下方执行记录；C81 为独立真实 API。

- [x] **C34：正文与思考区分** 正文继续实时展示，工具参数不混入正文；思考文字不展示，协议必需不透明数据与可见思考分开。（验证：输入混合正文/工具/思考模拟流，观察事件及可见文字，确认没有新增 extended thinking 展示或请求开关。 对应：F10、AC7；任务：T5、T39、T41、T43。）

  证据（2026-11-13，Windows）：test_anthropic_preserves_thinking_signature_without_display / openai_preserves_encrypted_reasoning / interleaved_tool_streams：千问思考字段不展示。自动验证的完整统计见下方执行记录；C81 为独立真实 API。

- [x] **C35：完整响应执行门槛** 即使某个工具块结束或 JSON 已完整，整个响应未成功结束前也不审批或执行工具。（验证：分别在 Claude block_stop、Responses item/arguments done、千问局部增量处暂停流，断言准备和执行均为零。 对应：F10、AC7；任务：T39、T41、T43、T45、T48。）

  证据（2026-11-13，Windows）：test_eof_never_exposes_executable_call：在局部结束后截断流也没有可执行调用事件。自动验证的完整统计见下方执行记录；C81 为独立真实 API。

- [x] **C36：异常终止不执行** 错误、截断、内容过滤、未完成响应及缺成功终止信号的 EOF 均不会放行缓冲调用。（验证：运行三协议失败终止样本及 runner_recovery，检查无成功回合、无副作用和明确请求错误。 对应：F10、F13、AC7、AC10；任务：T39、T41、T43、T48。）

  证据（2026-11-13，Windows）：test_length_limit_never_executes / eof_never_exposes_executable_call / runner_recovery_incomplete_then_retry。自动验证的完整统计见下方执行记录；C81 为独立真实 API。

- [x] **C37：参数错误无副作用** 无效 JSON、非对象、缺失字段、多余字段、错误类型、布尔伪整数、未知工具、缺失/重复 ID 均明确失败。（验证：运行注册/执行器校验和协议异常样本，记录错误类别、零工具启动及程序未崩溃。 对应：F10、F13、AC7、AC10；任务：T3、T9、T31、T39、T41、T43。）

  证据（2026-11-13，Windows）：test_tool_registry / test_protocol_integration_boundaries(diagnostic、duplicate_id、missing_id)：无效参数与零工作进程。自动验证的完整统计见下方执行记录；C81 为独立真实 API。

- [x] **C38：异常调用诊断回灌合法** 完整但无法合法编码的调用以明确诊断和结构化错误供模型续答，不伪造 ID、不发送无法配对的结果，不宣称工具执行成功。（验证：检查三后端异常请求体及 runner_recovery；确认禁用工具的续答可生成合法历史，未完成流不走诊断续答。 对应：F10、F13、F14、AC7、AC10、AC12；任务：T38、T40、T42、T48。）

  证据（2026-11-13，Windows）：test_malformed_json_preserved_for_structured_validation / protocol_integration_boundaries：三协议诊断请求体及续答。自动验证的完整统计见下方执行记录；C81 为独立真实 API。

- [x] **C39：结果逐 ID 配对** 每个正常调用恰有一个对应结果；多个全部拒绝时也回答所有可识别调用，三协议采用各自正确回灌格式。（验证：检查三后端第二次请求体、错误标记、结果顺序及 ID 集合相等，不用纯文字摘要代替工具结果。 对应：F14、F16、AC8、AC12；任务：T36、T38、T40、T42、T56。）

  证据（2026-11-13，Windows）：test_stream_tool_fragments_and_roundtrip / protocol_integration_boundaries(multiple)：结果逐 ID 配对。自动验证的完整统计见下方执行记录；C81 为独立真实 API。

- [x] **C40：Responses 回放完整** OpenAI 继续使用 Responses 与 store=False；必要输出项及不透明加密回放数据完整保留，不重复助手项、不在 UI 展示。（验证：对照 openai_payload/openai_tool_stream 的首次输出与下一请求，验证 function_call_output 配对和不透明内容保持原值。 对应：F14、F16、AC8、AC12；任务：T40、T41、T56。）

  证据（2026-11-13，Windows）：test_openai_preserves_encrypted_reasoning_and_rejects_final_mismatch：Responses、store=False、不透明项无损。自动验证的完整统计见下方执行记录；C81 为独立真实 API。

- [x] **C41：最终续答请求禁用工具** 三后端第二次请求均明确禁用工具，且本地仍有执行次数硬限制，不依赖模型仅靠提示词自觉停止。（验证：检查三协议最终请求体的工具控制字段，结合 runner_limits 验证违规调用没有执行机会。 对应：F11、F14、AC9、AC12；任务：T38、T40、T42、T46、T47。）

  证据（2026-11-13，Windows）：test_stream_tool_fragments_and_roundtrip / runner_limits_final_extra_call：三协议 none + 本地限制。自动验证的完整统计见下方执行记录；C81 为独立真实 API。

## 单轮闭环与历史

- [x] **C42：纯聊天保持一次请求** 模型不请求工具时仅一次请求，流式文字正常，无工具准备/执行且上下文保留。（验证：运行 provider_interface/runner_text 及原纯聊天测试，检查模型调用一次、工具调用零次。 对应：F9、F11、N7、AC1、AC13；任务：T37、T45。）

  证据（2026-11-13，Windows）：test_runner_text_single_request_and_single_flight：一次请求、无执行。自动验证的完整统计见下方执行记录；C81 为独立真实 API。

- [x] **C43：一个工具完整闭环** 用户提问后完成一次工具执行、结果回灌与流式最终文字答复；本轮模型最多两次请求、工具最多一次执行。（验证：运行 runner_tool_round/protocol_integration，用临时文件内容核对最终回复所依据的结果与调用计数。 对应：F11、F16、AC8；任务：T46、T56。）

  证据（2026-11-13，Windows）：test_protocol_integration_real_read：三协议 + 临时文件 + 真实工作进程；test_runner_tool_round。自动验证的完整统计见下方执行记录；C81 为独立真实 API。

- [x] **C44：失败也能续答** 拒绝、参数错误、工具失败和超时均回传可区分结果，由模型做一次最终文字解释，不自动重试。（验证：分别注入这些结果运行 runner_tool_round/runner_recovery，核对第二次请求与零次额外执行。 对应：F11、F12、F13、AC10；任务：T31、T33、T46、T48。）

  证据（2026-11-13，Windows）：test_runner_tool_round 四状态 / protocol_integration_boundaries / executor_timeout_budget_not_reset。自动验证的完整统计见下方执行记录；C81 为独立真实 API。

- [x] **C45：同批多个全部拒绝** 初次响应多个调用时，连准备阶段也不进入，不部分执行；每个可识别调用都有上限结果，再生成一次最终文字答复。（验证：用两个读工具、两个写工具及混合调用运行 runner_limits，断言准备/执行均零次、所有限制结果齐全。 对应：F11、AC9；任务：T47。）

  证据（2026-11-13，Windows）：test_runner_limits_multiple_calls_execute_none / protocol_integration_boundaries(multiple)：全部拒绝且零工作进程。自动验证的完整统计见下方执行记录；C81 为独立真实 API。

- [x] **C46：最终阶段不再执行** 最终续答再次请求工具时不执行、不发第三次请求，显示单轮提示并补记对应限制结果，使下轮历史合法。（验证：运行 runner_limits，检查模型请求数、执行数、限制提示及下一请求历史中没有孤立调用。 对应：F11、F16、AC9；任务：T47、T48。）

  证据（2026-11-13，Windows）：test_runner_limits_final_extra_call / protocol_integration_boundaries(final_limit)：不发第三请求。自动验证的完整统计见下方执行记录；C81 为独立真实 API。

- [x] **C47：初次流失败安全结束** 首个请求中断时不执行缓冲调用，不把残缺助手回复提交为完整历史；用户可继续。（验证：在不同分片位置中断并运行 runner_recovery，检查无副作用、明确错误和下一轮请求可用。 对应：F10、F13、AC7、AC10；任务：T45、T48。）

  证据（2026-11-13，Windows）：test_runner_recovery_incomplete_then_retry / eof_never_exposes_executable_call。自动验证的完整统计见下方执行记录；C81 为独立真实 API。

- [x] **C48：续答失败不重做工具** 工具已执行而最终 API 失败时，真实调用及结果保留；下一轮不偷偷重做写入/命令。（验证：先执行受控标记工具再令最终流失败，随后提问，检查标记次数不变、历史仍有原结果。 对应：F11、F13、F16、AC8、AC10；任务：T48。）

  证据（2026-11-13，Windows）：test_runner_recovery_final_failure_preserves_exchange：下一轮工具不重复执行。自动验证的完整统计见下方执行记录；C81 为独立真实 API。

- [x] **C49：后续上下文完整** 下一轮携带用户、助手调用、对应实际结果和最终回复，结果是受上限控制的内容而非界面短摘要。（验证：检查后续请求体与已保存结果，验证顺序、ID、全文预算及纯聊天历史兼容。 对应：F16、AC8；任务：T36、T46、T48、T56。）

  证据（2026-11-13，Windows）：test_runner_tool_round / protocol_integration_boundaries：完整结果及后续请求，不使用 UI 摘要。自动验证的完整统计见下方执行记录；C81 为独立真实 API。

- [x] **C50：历史不被外部副本篡改** 修改取出的嵌套调用、结果或私有回放副本，不会改变下一次取得的会话历史。（验证：运行 model_contract/tool_history 防御性副本用例，对修改前后历史做结构比较。 对应：F16、AC8；任务：T3、T36。）

  证据（2026-11-13，Windows）：test_tool_history_exchange_and_defensive_copy / model_contract 测试。自动验证的完整统计见下方执行记录；C81 为独立真实 API。

- [x] **C51：整轮防重入** 连续提交不会产生重叠请求或重复用户回合；等待审批及最终生成期间能编辑草稿，未接受的提交不清空草稿。（验证：运行 runner_text/turn_event_ui，快速连按提交并在审批/生成中编辑，核对请求数、历史和输入内容。 对应：F11、N2、AC9、AC11；任务：T45、T51。）

  证据（2026-11-13，Windows）：test_turn_event_ui_immediate_double_submit / approval_ui_write_and_decision_binding：草稿和请求计数。自动验证的完整统计见下方执行记录；C81 为独立真实 API。

## 界面与会话回归

- [ ] **C52：启动信息真实** 版本、供应商、模型和目录保持正确；状态显示 0 MCP 与实际 6 个内置工具，不虚报 MCP 接入。（验证：运行 startup_tools 并观察真实启动界面，与当前有效配置及工具定义对照。 对应：F1、F15、AC1、AC11；任务：T26、T49、T53、T58。）

  状态（2026-11-13）：无界面启动信息和真实 6 tools/0 MCP 已验证；真实启动界面待手测。

- [ ] **C53：工具状态可辨认** 对话区出现 ● 工具名(关键参数)，接收参数、准备、审批、运行、成功、失败或拒绝状态可区分。（验证：通过 tool_view/turn_event_ui 及真实工具场景观察同一工具行的更新与正确结果。 对应：F15、AC11；任务：T49、T51。）

  状态（2026-11-13）：无界面同一工具行更新及状态测试通过；真实界面状态观察未执行。

- [ ] **C54：记录顺序与回看** 前导文字、工具行、审批记录、结果摘要、最终文字依次出现且不交错，均可在对话区滚动回看。（验证：运行 UI 顺序测试并在 PowerShell 回滚查看前述完整场景，区分应用内历史与退出后的外部终端。 对应：F15、AC11；任务：T49、T51、T62。）

  状态（2026-11-13）：无界面组件顺序断言通过；真实终端滚动回看未执行。

- [x] **C55：摘要不替代真实结果** UI 结果最多 8 行/1,000 字符且提示截断，模型收到的是工具级预算内的结果，不是这份 UI 摘要。（验证：产生超过摘要但小于工具上限的结果，对比可见文本、保存结果和下一模型请求。 对应：F15、N3、AC11；任务：T6、T49、T55。）

  证据（2026-11-13，Windows）：test_tool_view_summary_safe_and_bounded / runner_tool_round：8 行/1000 字符摘要与实际结果分离。自动验证的完整统计见下方执行记录；C81 为独立真实 API。

- [ ] **C56：原输入行为无回归** Enter 提交、Shift+Enter 换行、空输入忽略和原退出入口继续有效，纯聊天仍逐步输出。（验证：运行原有及扩展 TUI 测试，在真实终端输入单行/多行和空文本观察行为；终端不支持的组合需记录实际问题。 对应：N7、AC13；任务：T51、T53、T58、T62。）

  状态（2026-11-13）：原有输入/退出测试通过；真实终端 Enter/Shift+Enter/空输入尚未手测。

- [x] **C57：错误位置与恢复** 工具失败内联显示，配置/模型请求错误使用错误面板；确认后恢复操作，失败不会伪装成成功助手回复。（验证：运行 tui_recovery/startup_tools，分别触发工具失败、缺配置和模型错误后再发送正常问题。 对应：F13、F15、AC10、AC11；任务：T52、T53。）

  证据（2026-11-13，Windows）：test_tui_recovery_* / test_startup_tools_config_failure_uses_error_app：内联失败和模型面板分层。自动验证的完整统计见下方执行记录；C81 为独立真实 API。

- [ ] **C58：退出与仅进程内历史** 空闲、审批、执行和生成阶段均能退出整个程序，待审批失效、无晚到写入；重启为新会话，不新增历史持久化或单独取消能力。（验证：运行 app_shutdown，并在真实终端退出后重启，观察进程清理、输入恢复和无旧会话自动恢复。 对应：F16、N1、N7、AC8、AC13；任务：T54、T62。）

  状态（2026-11-13）：无界面空闲、审批、执行、最终生成退出清理通过；真实终端恢复与重启观察未执行。

## 结果体量与安全

- [x] **C59：结果总预算** 每份回传模型的序列化结果不超过 20,000 字符，截断标记计入预算，状态/退出码/实际匹配数仍在。（验证：运行 result_budget/security_pipeline，对中文、转义、大正文、大诊断分别计算最终文本长度和字段。 对应：N3、AC11；任务：T6、T25、T55。）

  证据（2026-11-13，Windows）：test_result_budget / security_pipeline_* / output_pressure_real_worker：序列化 <=20000，保留退出码。自动验证的完整统计见下方执行记录；C81 为独立真实 API。

- [x] **C60：工具数量上限** 单次读取最多 200 行，找文件最多 200 条，搜内容最多 100 条；达到上限明确说明，不表示已经遍历完整目标。（验证：用超过各上限的临时样本运行 read_file/find_files/search_limits，检查数量及截断说明。 对应：F2、F6、F7、N3、AC2、AC6、AC11；任务：T6、T11、T21、T23。）

  证据（2026-11-13，Windows）：test_read_file_pagination_and_eof / find_files_empty_and_cap / search_limits_hit_count_and_output。自动验证的完整统计见下方执行记录；C81 为独立真实 API。

- [x] **C61：长输出持续排空** stdout/stderr 同时大量输出时保留体量有界、命令不因管道堵塞挂死，结束后仍得到退出码。（验证：运行 output_pressure，扩大受控输出量，对比有限保存内容、完成时间和退出状态，不仅检查最终字符串曾被截断。 对应：F5、N3、AC5、AC11；任务：T25、T35。）

  证据（2026-11-13，Windows）：test_output_pressure_real_worker / command_output_large_is_bounded：stdout/stderr 各 20 万字符仍正常结束。自动验证的完整统计见下方执行记录；C81 为独立真实 API。

- [x] **C62：超长行反馈诚实** 读取/搜索超长行不会无限缓冲；搜索无法完整检查时明确标记不完整，不返回假无匹配。（验证：运行大文件与超长行测试，观察内容上限、下一读取信息及搜索警告，界面保持响应。 对应：F2、F7、N2、N3、AC2、AC6、AC11；任务：T10、T11、T23。）

  证据（2026-11-13，Windows）：test_read_file_errors_and_large_line / search_limits_binary_encoding_and_long_lines：有限读取与不完整提示。自动验证的完整统计见下方执行记录；C81 为独立真实 API。

- [x] **C63：已知密钥不泄漏** 受控已知密钥在文件结果、stdout/stderr、工具错误、预览、模型错误及跨分片正文中都不出现在可见输出或模型工具结果中。（验证：运行 redact_batch/redact_stream/security_pipeline；检查累计可见文字和请求体，测试只用假密钥。 对应：N6、AC13；任务：T7、T8、T52、T55。）

  证据（2026-11-13，Windows）：test_redaction / security_pipeline_* / tui_recovery_split_secret_*：跨片正文、文件、命令、预览和错误。自动验证的完整统计见下方执行记录；C81 为独立真实 API。

- [x] **C64：脱敏不篡改操作** 预览和回传中被遮蔽的已知密钥不会被占位标记写入实际文件，也不会改变原始命令参数。（验证：对受控假密钥样本批准写入或命令，比较实际字节/参数与遮蔽后的显示内容。 对应：F3、F5、N6、AC3、AC5、AC13；任务：T7、T15、T25、T55。）

  证据（2026-11-13，Windows）：test_security_pipeline_actual_content_and_command_preserved / approval_ui_write_and_decision_binding：磁盘保持原始假密钥。自动验证的完整统计见下方执行记录；C81 为独立真实 API。

- [x] **C65：文本不能控制终端或界面** 模型/工具输出中的 ANSI 控制、Rich 标记及特殊文本作为安全文字处理，不执行终端控制或破坏布局，不回显堆栈和认证头。（验证：运行安全显示和 tui_recovery 测试，注入控制序列、方括号及模拟敏感错误，对照界面与安全诊断。 对应：N6、AC11、AC13；任务：T7、T49、T52、T55。）

  证据（2026-11-13，Windows）：test_tool_view_summary_safe_and_bounded / tui_recovery_split_secret_markup_and_model_failure：纯文本和控制序列过滤。自动验证的完整统计见下方执行记录；C81 为独立真实 API。

- [x] **C66：配置与默认后端兼容** 原六字段配置、默认后端选择及密钥引用继续有效，不为工具增加配置字段，也不强行解析未选后端的环境变量。（验证：运行 test_config.py/startup_tools，使用仅默认供应商密钥可用的场景启动；检查用户原配置未被改写。 对应：N7、AC13；任务：T2、T53、T57。）

  证据（2026-11-13，Windows）：test_config / test_startup_tools_cli_constructs_all_components：六字段、默认密钥与未选引用。自动验证的完整统计见下方执行记录；C81 为独立真实 API。

## 编译与自动测试

- [x] **C67：基线和全量测试** 保留原有基线证据，全量自动测试实际执行且无失败；目标筛选不是空集合，不靠静默 skip 或删断言使结果变绿。（验证：从项目根运行 uv run python -m pytest -v，记录通过/失败/跳过数量及退出码，与 T1 基线比较。 对应：N7、N8、AC13；任务：T1、T57。）

  证据（2026-11-13，Windows）：全量 uv run python -m pytest -q --tb=short：最终统计见末尾验收记录；基线 27 passed 保留。自动验证的完整统计见下方执行记录；C81 为独立真实 API。

- [x] **C68：编译检查** 实现与测试文件均可编译，无语法错误。（验证：运行 uv run python -m compileall src tests，保存退出码；不在本次编写清单时提前执行。 对应：N7、AC13；任务：T1、T57。）

  证据（2026-11-13，Windows）：uv run python -m compileall -q src tests，退出码 0。自动验证的完整统计见下方执行记录；C81 为独立真实 API。

- [x] **C69：依赖与检查范围** 仅加入已批准的 jsonschema/pathspec/wcmatch，uv.lock 与项目依赖一致；不额外引入 SDK、lint/type-check 或系统组件。（验证：在开发允许后运行 uv sync，审查 pyproject.toml/uv.lock 的实际差异并导入三依赖；Ruff/mypy 未配置则记录不适用，不声称通过。 对应：N7、AC13；任务：T2、T57。）

  证据（2026-11-13，Windows）：uv sync --locked：Resolved/Checked 32 packages；仅新增已批准的三项依赖，未新增 SDK/Ruff/mypy。自动验证的完整统计见下方执行记录；C81 为独立真实 API。

- [x] **C70：平台证据区分** 原生 Windows/其他系统测试的执行与 skip 状态分别记录；本机验证不等于所有支持系统已实测。（验证：汇总 windows_job/posix_process/process_tree 的实际运行平台、结果及跳过原因，报告不扩大结论。 对应：N1、N8、AC5、AC12；任务：T27、T28、T35、T57、T66。）

  证据（2026-11-13，Windows）：Windows Job 原生和进程树断言通过；POSIX 用例、无链接权限样本明确 skip。自动验证的完整统计见下方执行记录；C81 为独立真实 API。

- [x] **C71：三协议模拟集成齐全** Anthropic、OpenAI Responses、千问均实际执行同组模拟场景，包含正常、错误、拒绝、单轮上限和后续上下文。（验证：运行 protocol_integration 参数化测试，核对三个后端用例均被收集，检查请求体及执行次数，不依赖在线凭证。 对应：F14、N5、N8、AC12；任务：T38、T39、T40、T41、T42、T43、T56。）

  证据（2026-11-13，Windows）：test_protocol_integration_real_read 三例 + test_protocol_integration_boundaries 21 例，三后端实际收集执行。自动验证的完整统计见下方执行记录；C81 为独立真实 API。

- [x] **C72：验证结论不混用** 模拟测试、无界面 UI、真实终端与真实 API 的证据分别记录；缺凭证/环境的项目保留未执行，不勾为通过。（验证：审阅测试输出、真实终端记录及线上记录，核对每条通过结论都有对应运行/观察；后续真实 API 项单独检查。 对应：N8、AC12；任务：T57、T63、T64、T65、T66。）

  证据（2026-11-13，Windows）：本记录分别列明自动、无界面 UI、真实 API、未执行真实终端与平台限制。自动验证的完整统计见下方执行记录；C81 为独立真实 API。

## PowerShell 端到端

- [ ] **C73：启动、读文件与总结** 真实 PowerShell 启动后可输入问题，读受控文件出现工具行和流式总结；追问能参考实际文件内容及前文。（验证：运行 uv run weizhcode，在专用临时目录使用无敏感测试文件，观察完整链路、后续追问并记录实际后端及截图；不以 headless 代替。 对应：F2、F11、F15、F16、AC2、AC8、AC11；任务：T58。）

  状态（2026-11-13）：未执行：当前桌面控制规则禁止代操作终端窗口，需用户在 PowerShell 手测；未用无界面测试冒充。

- [ ] **C74：写入批准与拒绝** 真实界面能拒绝写入且磁盘不变；新一轮批准后正确创建嵌套文件，审批选择和模型解释可回看。（验证：按 T59 在临时目录操作，用另一个只读检查入口核对等待/拒绝/批准三种时刻的文件和父目录。 对应：F3、F12、AC3、AC10；任务：T59。）

  状态（2026-11-13）：未执行真实终端。对应批准/拒绝磁盘断言已在无界面 UI 通过，不能替代本项。

- [ ] **C75：精确修改与陈旧预览** 真实界面的唯一替换成功，匹配不到明确报错；审批前外部改变临时文件后旧预览失效，不能覆盖新内容。（验证：按 T60 逐轮提交、查看预览并核对文件字节，再发送正常问题确认恢复。 对应：F4、F12、N4、AC4、AC10、AC13；任务：T60。）

  状态（2026-11-13）：未执行真实终端。对应精确编辑/陈旧预览自动测试通过，不能替代本项。

- [ ] **C76：命令批准、失败与超时** 完整命令和目录可见，拒绝不执行，批准后返回输出/退出码；受控失败和超时后仍能继续对话。（验证：按 T61 使用受控命令逐轮验证，观察执行期间滚动与状态刷新；超时后进程证据与自动进程树断言对应。 对应：F5、F12、N1、N2、AC5、AC10、AC11；任务：T61。）

  状态（2026-11-13）：未执行真实终端。命令、超时、Windows 进程树及运行中退出自动测试通过，不能替代本项。

- [ ] **C77：单工具边界和错误恢复** 写文件后执行命令需分两次用户提问；每轮不连环执行，工具错误后下一次普通问题仍可提交。（验证：对前述写/改/命令场景逐轮观察；多调用强制反例由模拟流测试证明，不能因真实模型未提出多个就视为已覆盖该反例。 对应：F11、F13、AC9、AC10；任务：T47、T59、T60、T61。）

  状态（2026-11-13）：未执行真实终端；三协议多调用、最终再次调用、错误恢复自动反例通过。

- [ ] **C78：回滚查看和退出** 真实对话记录可滚动查看，顺序正确；审批/执行时退出恢复终端且无晚到操作，重启无旧历史自动恢复。（验证：按 T62 保存受控截图与进程观察，明确使用用户批准的 PowerShell 替代方案，不安装 tmux/WSL。 对应：F15、F16、N1、N2、AC11、AC13；任务：T54、T62。）

  状态（2026-11-13）：未执行真实终端；待用户观察回滚、退出恢复与新会话。

## 真实 API 单独验收

- [ ] **C79：Anthropic 线上闭环** 具备用户已提供的有效凭证时，Anthropic Messages 真实完成读取总结和受控错误恢复，行为符合单工具约束。（验证：按 T63 记录实际模型/协议/场景/结果；缺条件时本项保持未勾选并注明原因，不修改原配置、不输出密钥。 对应：F14、N5、N8、AC12；任务：T63。）

  状态（2026-11-13）：未执行：当前 anthropic-main 未具备可用凭证；不改模型、不改配置。

- [ ] **C80：OpenAI Responses 线上闭环** 具备有效凭证时，OpenAI Responses 真实完成工具回灌与最终文字；不能以 Chat Completions 连通性替代。（验证：按 T64 验证真实读取及受控错误，记录 store=False 下续答结果；缺条件保持未勾选，需模型/配置改变先询问。 对应：F14、N5、N8、AC12；任务：T64。）

  状态（2026-11-13）：未执行：当前 openai-main 未具备可用凭证；未用 Chat Completions 替代 Responses。

- [x] **C81：千问线上闭环** 具备有效凭证时，既定千问兼容端点和模型真实完成流式调用、结果配对、最终禁用工具及错误恢复。（验证：按 T65 记录实际结果，可复用前述同后端终端证据避免重复调用；不能擅自换模型，未运行仍不勾选。 对应：F14、N5、N8、AC12；任务：T65。）

  证据（2026-11-13，Windows）：uv run python tests/manual_tool_smoke.py：qwen3.7-plus（既定兼容端点），read success → missing FILE_NOT_FOUND → context 731；退出码 0，未改配置。自动验证的完整统计见下方执行记录；C81 为独立真实 API。

## 交付与验收报告

- [x] **C82：状态和证据完整** 任务与清单只在对应验证真实通过后标记；失败、未执行、平台限制及已知非沙箱/非回滚边界明确说明，交付材料无密钥。（验证：按 T66 汇总自动测试、真实终端、各 API 和剩余事项，核对每个勾选项的证据；仅本地分组提交，不自动推送 GitHub。 对应：N8、AC1、AC2、AC3、AC4、AC5、AC6、AC7、AC8、AC9、AC10、AC11、AC12、AC13；任务：T66。）

  证据（2026-11-13，Windows）：下方交付记录明确列出通过、未验和平台限制；分组本地提交，不推送远端。自动验证的完整统计见下方执行记录；C81 为独立真实 API。

## 自动验证命令索引

下面为开发完成后执行的定位索引，不是运行记录。各项行为与断言应在实现重命名、移动后继续成立；如测试文件移动，仅更新命令位置，不删除行为要求。

| 测试文件 | 执行命令 |
|----------|----------|
| [tests/test_tool_registry.py](D:/STUDY/weizhcode-python/tests/test_tool_registry.py) | `uv run python -m pytest tests/test_tool_registry.py -v` |
| [tests/test_file_tools.py](D:/STUDY/weizhcode-python/tests/test_file_tools.py) | `uv run python -m pytest tests/test_file_tools.py -v` |
| [tests/test_search_tools.py](D:/STUDY/weizhcode-python/tests/test_search_tools.py) | `uv run python -m pytest tests/test_search_tools.py -v` |
| [tests/test_command_tool.py](D:/STUDY/weizhcode-python/tests/test_command_tool.py) | `uv run python -m pytest tests/test_command_tool.py -v` |
| [tests/test_tool_executor.py](D:/STUDY/weizhcode-python/tests/test_tool_executor.py) | `uv run python -m pytest tests/test_tool_executor.py -v` |
| [tests/test_provider_events.py](D:/STUDY/weizhcode-python/tests/test_provider_events.py) | `uv run python -m pytest tests/test_provider_events.py -v` |
| [tests/test_turn_runner.py](D:/STUDY/weizhcode-python/tests/test_turn_runner.py) | `uv run python -m pytest tests/test_turn_runner.py -v` |
| [tests/test_conversation.py](D:/STUDY/weizhcode-python/tests/test_conversation.py) | `uv run python -m pytest tests/test_conversation.py -v` |
| [tests/test_tui.py](D:/STUDY/weizhcode-python/tests/test_tui.py) | `uv run python -m pytest tests/test_tui.py -v` |
| [tests/test_redaction.py](D:/STUDY/weizhcode-python/tests/test_redaction.py) | `uv run python -m pytest tests/test_redaction.py -v` |
| [tests/test_config.py](D:/STUDY/weizhcode-python/tests/test_config.py) | `uv run python -m pytest tests/test_config.py -v` |

全量命令：

- `uv run python -m pytest -v`：记录实际通过、失败、跳过数量与退出码。
- `uv run python -m compileall src tests`：记录编译退出码。
- `uv sync`：仅在开发获准后同步已批准的依赖，不视作功能测试通过。
- `uv run weizhcode`：真实 PowerShell 场景使用，必须有人或可用界面观察机制实际观察结果。

Lint / 类型检查：本阶段未配置且不新增 Ruff 或 mypy，不把未运行检查写成通过。真实 API 条件不足时不改为使用另一种协议测试代替。

## 验收标准覆盖

下表只建立覆盖关系，不表示这些项目已经通过。C82 为最终证据汇总，不用汇总项代替具体功能项。

| Spec 验收标准 | 具体检查项 |
|---------------|------------|
| AC1 | C01、C02、C32、C42、C52 |
| AC2 | C03、C04、C17、C20、C60、C62、C73 |
| AC3 | C05、C09、C21、C22、C23、C24、C25、C30、C64、C74 |
| AC4 | C06、C07、C08、C09、C21、C22、C30、C75 |
| AC5 | C11、C12、C13、C21、C22、C24、C26、C27、C28、C29、C61、C64、C70、C76 |
| AC6 | C14、C15、C16、C17、C18、C19、C20、C60、C62 |
| AC7 | C33、C34、C35、C36、C37、C38、C47 |
| AC8 | C39、C40、C43、C48、C49、C50、C58、C73 |
| AC9 | C41、C45、C46、C51、C77 |
| AC10 | C02、C04、C07、C12、C15、C18、C19、C23、C24、C27、C28、C30、C36、C37、C38、C44、C47、C48、C57、C74、C75、C76、C77 |
| AC11 | C25、C29、C31、C51、C52、C53、C54、C55、C57、C59、C60、C61、C62、C65、C73、C76、C78 |
| AC12 | C32、C33、C38、C39、C40、C41、C70、C71、C72、C79、C80、C81 |
| AC13 | C10、C42、C56、C58、C63、C64、C65、C66、C67、C68、C69、C75、C78 |

功能需求 F1～F16、非功能需求 N1～N8 及任务 T1～T66 均在对应检查项中标注；需求覆盖自检不能替代运行验证。

## 执行后记录与交付要求

执行时在对应项后记录实际证据，而不是提前填写预期结果当作实测：

- 记录验证模式：自动测试 / 无界面 UI / Windows PowerShell 真实界面 / 真实 API / 对应操作系统原生进程测试。
- 记录实际命令或用户输入、模型协议与测试目标范围；不得包含密钥、认证头或未经处理的敏感内容。
- 记录通过或失败现象、测试数量/退出码、截图或日志位置；失败与未执行说明具体原因。
- 对同一次真实终端与 API 调用可复用证据，注明关联项，避免无意义重复付费调用。
- C79～C81 分别代表三个真实 API 场景，条件不足时保持未勾选；自动跨协议模拟通过只对应 C71 等自动项目。
- 汇总时分别列出已通过、失败、未执行与平台限制；不将其他项目通过推导成整阶段全部验收通过。
- 四份文档获批后按 Tasks 分组实施与本地提交；本阶段不因验收文档产生自动 GitHub 推送。

## 当前状态

四份文档全部获批，主体实现及自动验证完成，整阶段验收尚未全部完成。已通过 62/82 项；其余 20 项包含部分已验证、真实终端待手测、缺凭证和平台限制，不等同于 20 个功能失败。

## 最终执行记录（本轮，2026-11-13）

| 验证模式 | 实际结果 |
|----------|----------|
| 全量自动测试 | uv run python -m pytest -q --tb=short：225 passed、2 skipped，33.93s，退出码 0 |
| 编译 | uv run python -m compileall -q src tests：退出码 0 |
| 锁定依赖 | uv sync --locked：Resolved/Checked 32 packages；锁文件一致 |
| 三协议模拟 + 真实工作进程 | Anthropic Messages、OpenAI Responses、千问兼容协议都收集执行；正常读取、失败、拒绝、多个全部拒绝、最终再次调用、异常诊断及下一轮上下文通过 |
| 无界面 TUI | Pilot 验证默认拒绝、批准/拒绝、预览变化保护、顺序、草稿、防重入、密钥脱敏、模型错误恢复、执行/最终生成中退出 |
| 千问真实 API | uv run python tests/manual_tool_smoke.py：既定 qwen3.7-plus，读取临时非敏感 fixture 成功；不存在文件返回 FILE_NOT_FOUND 后生成解释；继续追问得到 731；退出码 0 |
| Anthropic/OpenAI 真实 API | 未执行：未具备有效凭证；未修改配置、端点、协议或模型 |
| PowerShell 真实界面 | 未执行：当前桌面控制规则禁止代操作终端窗口；需用户手动观察，不能用 Pilot/线上无界面脚本替代 |
| 原生平台范围 | Windows Job 与受管父子进程终止已实测；POSIX 原生未跑（skip）；Windows 链接环样本因创建权限不足 skip |
| 其他未补验 | 强制终止写入中的临时资源登记清理缺独立样本；已有原子写失败和临时文件归属测试不能替代该场景 |
| Lint / 类型检查 | 未配置、不新增，不宣称 Ruff/mypy 通过 |

### 手动交接

在项目根目录的 PowerShell 运行 uv run weizhcode，按 C73～C78 使用非敏感临时文件逐轮验收。写入、修改和命令应出现“允许本次/拒绝本次”，默认拒绝；工具失败应内联显示，模型请求失败才弹错误面板。

请补充真实界面观察后再更新对应勾选；其他两家真实 API 需要有效配置/凭证时先由用户决定，不自动改模型。已完成代码按逻辑组仅本地提交，未推送 GitHub。进程管理不是沙箱，终止不保证回滚已经发生的副作用。

