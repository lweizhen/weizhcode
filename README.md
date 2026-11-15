# weizhCode

Python 3.11+ 终端 Coding Agent：HTTPX/SSE 流式多轮、工具循环、计划模式与需求澄清。

## 启动

在项目根使用现有依赖环境执行 `uv run python -m weizhcode`（或安装后的 `weizhcode` 命令）。配置使用项目根的 `weizhcode.yaml`，结构参考同目录的 `weizhcode.yaml.example`；不要提交真实密钥。

供应商仍是六字段：name、protocol、model、base_url、api_key，以及可选 thinking。protocol 的 anthropic 为 Messages，openai 为 Responses，qwen 为兼容 Chat Completions；不是所有兼容服务都支持相同缓存参数。配置修改后重新启动，不会自动更换模型或供应商。

`/plan` 切只读调查模式，允许 read_file/find_files/search_content 与 AskUserQuestion。回答需求问题不是执行授权，计划完成等待 `/do`。普通模式提供六个文件/命令/检索工具。已有工具执行机制不等于权限系统或沙箱，操作真实文件/命令须注意副作用。

## 系统提示与上下文

稳定指令由身份、系统约束、任务模式、动作执行、工具使用、语气风格、文本输出七模块组成，空行分隔；自定义指令、Skill、长期记忆本章仅预留空槽，不读取真实来源。

每个用户任务开始时采集一次工具实际工作根、平台、本地日期、Git状态数量摘要、版本与模型。Git只读查询等待最多2秒，失败/超量会降级；这是任务开始快照，不是工具执行后的实时状态。采集进程退出/取消时回收，操作系统回收不声称硬实时。

环境和应用生成的 `<system-reminder>` 不写入会话保存历史，也不拼进稳定模块。计划任务第1/5/9/13/17/21/25次模型请求使用完整提醒，其余精简；提问等待不加轮，新任务重置。标签只是提示约定，不赋予用户/文件/工具文字额外权限，不保证模型免疫提示注入。

系统与工具描述共同约定专用工具优先、编辑前先读真实原文、精确唯一替换及如实报告失败/截断。本章没有新增编辑读记录门禁或权限审批。

## 缓存策略及统计

- 官方 Anthropic `/v1` Claude请求在稳定system块结束处设置ephemeral边界，环境/历史不额外标缓存。
- 官方 Responses `/v1` 的已核对精确模型名单采用显式developer块边界；当前名单为gpt-5.6、gpt-6.1-sol、gpt-6.1-terra，不代表其他模型都不支持缓存。未知模型仍用原前缀方式，不按版本数字推断能力。
- 千问、DeepSeek、其他兼容服务默认保持稳定前缀，不发送未经确认的显式扩展。能力表不等于账号有权限，不会试探请求或自动降级重试。

缓存读/写值、字段是否提供和异常状态分开记录：真实0不等于未提供；没有证据不标不适用。累计包只更新单请求快照，每请求只结算一次。Anthropic总输入为非缓存输入+缓存读+缓存写；Responses/千问输入已含相应缓存子项，不重复相加。取消/失败保留部分统计并标不完整。统计不会增加TUI缓存状态栏。

相同前缀digest只证明应用选择的稳定部分一致，不证明服务命中。长度门槛、模型、TTL、权限和路由会影响结果；缓存写入也可能收费，不保证省钱或更快。稳定/动态分段不等于关闭服务端自动缓存或控制数据保留。

## 人工验证（默认不联网）

`uv run python tests/manual_prompt_smoke.py` 只输出内置离线演示，明确不是当前配置，不加载认证配置或发请求。

只有用户有意选择真实验证时才运行：

```powershell
uv run python tests/manual_prompt_smoke.py --live --scenario cache --prompt-variant modular
uv run python tests/manual_prompt_smoke.py --live --scenario behavior --prompt-variant modular
```

入口会说明实际服务/模型和可能费用，要求输入YES。cache仅请求两次，使用临时合成参考数据，改变动态内容并记录实际读写计数；不执行模型工具、不自动续跑或切服务。真实读取正值且无统计异常才是读取命中证据；缺字段、未命中、缺权限分别记待验。

behavior一次选择一个场景：files、edit、clarify、plan、environment、reminder或cancel。仅操作临时fixture.txt/summary.txt，命令/越界请求拒绝，AskUserQuestion支持自由回答或/cancel。plan场景输入/do后才执行；cancel场景在首个文本增量或工具启动时主动取消，用于观察恢复，真实键盘取消仍需在TUI手测。每任务最多25轮，异步阶段设90秒超时；等待终端输入时需用户完成回答或中断，不承诺强制结束阻塞输入。提醒场景未达到第5轮须如实记未观察，不能强称已验证。

改用 `--prompt-variant baseline` 可与冻结的旧提示及工具描述对比，运行时仍相同；这是人工定性观察，不是旧版本性能基准或自动评分。记录相同模型/样本/必要环境差异、工具序列、结果、用量及可选耗时，不作统计显著或固定折扣承诺。不自动批跑收费矩阵。

## 离线工程检查

```powershell
uv lock --check
uv run python -m compileall -q src
uv run pytest -v
```

不需要新增SDK、Ruff/mypy或评测依赖。Windows原生异步子进程检查需要能创建本机事件循环/进程的执行环境；平台不足与缺凭证检查分别记录。真实PowerShell界面、真实缓存命中和离线测试是不同证据。
