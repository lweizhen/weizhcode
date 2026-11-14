# 计划模式需求澄清 Tasks

> 状态：四份文档已统一批准；实施与验收状态见末尾。依赖按编号顺序，无并行代理或新依赖。

根目录：D:/STUDY/weizhcode-python。先跑验证再标记完成；原有文件/进程/安全断言不能删除或静默跳过。

| 任务 | 文件与聚焦改动 | 验证与对应标准 |
|---|---|---|
| T1 | models.py、tools/ask_user_question.py、tools/__init__.py：请求模型、interactive 元信息、Schema 与第七工具 | tests/test_user_questions.py -k ask_question_schema：合法/缺字段/重复选项/边界；AC1、AC3 |
| T2 | tools/registry.py、prompts.py：模式过滤和必要澄清提示，不强制每任务提问 | tests/test_user_questions.py -k ask_question_modes；检查提示词；AC1、AC2 |
| T3 | user_questions.py：单问题问答、索引映射、自由回答、服务端校验 | tests/test_user_questions.py -k answer：边界、空白、索引、重复；AC3、AC5 |
| T4 | user_questions.py：消费者连接、无交互快速失败、取消/退出与等待任务清理 | tests/test_user_questions.py -k lifecycle：无消费者、断开、同拍、过期与复用；AC4、AC7、AC9 |
| T5 | tools/executor.py：分流到 broker，plan 门禁与人类等待排除超时 | tests/test_user_questions.py -k lifecycle_unavailable：零 worker、normal 拒绝、短预算不影响回答；AC1、AC4 |
| T6 | tool_scheduler.py：交互独立串行屏障，不跨问答重排 | tests/test_user_questions.py -k interactive_barrier：读/问/读与连续问题；AC6 |
| T7 | turn_runner.py、models.py：共享 broker、消费者绑定、带 run_id 的回答接口和安全事件副本 | tests/test_user_questions.py -k runner_history：同任务续跑、历史、迭代不额外增加、归属校验；AC5、AC7 |
| T8 | tool_ui.py、tui.py：内联问题、序号/文本输入、等待状态，命令与草稿保护 | tests/test_tool_tui.py -k ask_question：选择、自由答、非法答、忙时命令、取消和旧事件；AC2～AC8 |
| T9 | test_protocol_integration.py、test_user_questions.py、test_cli.py：三协议回灌、密钥/控制字符、同构接线 | 前两文件 -k ask_question 实际收集通过，test_cli.py 完整回归；AC9、AC10 |
| T10 | 扩展必要的模式/工具数量断言，回归全部现有功能 | uv sync --locked；uv run python -m pytest -q -rs；uv run python -m compileall src tests；AC10 |
| T11 | 本目录 checklist.md：记录自动与条件具备的真实 API 证据，用户真实终端手测 | 问→答→继续计划→等待 /do；等待取消后再提问；缺条件保留待验；AC2、AC5、AC7、AC10 |
| T12 | 本目录 task.md/checklist.md：据实汇总，本地逻辑提交 | 检查差异和提交路径；不含用户配置/.weizhcode-test，不自动推送；全部 AC |

测试命令统一前缀 uv run python -m pytest，对表内测试路径使用项目根下绝对路径；每项选择器必须实际收集用例，零用例不算通过。T1～T9 相关模块同时编译；UI/接口接线作为一致工作组完成回归后提交，不交付半套签名。

## 进度

T1～T10 已完成；T11 的默认服务真实 API 已完成、真实终端待用户实测；T12 已记录本轮证据并准备本地提交，不宣称全部终端验收完成。实现遇到与批准行为不同的取舍时先说明，不默默扩展到权限系统或普通模式交互。

## 本轮证据（2026-11-14）

- 新增专项：tests/test_user_questions.py、tests/test_tool_tui.py、tests/test_protocol_integration.py -k ask_question：19 passed；随后新增待答时 /exit 清理专项：1 passed。相关协议/循环/界面完整局部回归106 passed。
- 初次全量发现旧安装数量及提示词断言未迁移，更新为安装七工具、normal 六工具、plan 四工具；原有安全断言保留，不增加 skip。修正后全量370 passed、2 skipped，70.30秒；最后加入退出专项再次全量验证，实际结果补记下文。
- uv sync --locked 成功，compileall src tests 通过。没有新增依赖、配置、权限组件；没有修改用户配置或 .weizhcode-test。
- 实际测试集中在新增 test_user_questions.py 以便复用受控问答场景，覆盖 Schema、Broker、Executor、Scheduler、Runner 和安全出口；表中验证入口已与实际位置对齐。
- 默认 DeepSeek 真实 API：anthropic 协议、deepseek-flash；只允许 AskUserQuestion，其他工具被测试范围门禁拒绝，不读写项目文件。实际 questions=1、stop_reason=completed、mode=plan、answer_in_history=true，最终计划非空并等待 /do，退出码0。回答样本为“仅做本地命令行，不做网页；用本地样本验收。”；这是无界面交互消费者证据，不是用户真实终端观察。
- C16/C17 保留待验：需用户在真实 PowerShell 观察问题、草稿、按键、取消与退出。其他服务本轮未单独线上验证，不以默认服务通过代替。
- 最终交付复验：371 passed、2 skipped，72.15秒，compileall退出码0；跳过项仍为目录链接权限与POSIX原生平台。待答退出专项1 passed，全部专项累计20个用例。阶段证据已记录，仅本地提交，不推送；用户配置与 .weizhcode-test 不纳入提交。
