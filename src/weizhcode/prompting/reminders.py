from .contracts import RuntimeSupplement, _APP_ORIGIN
from weizhcode.permissions.modes import normalize_runtime_mode


FULL_PLAN_REMINDER = """当前是计划模式：使用 read_file、find_files、search_content 进行只读调查。
若需求、范围、约束或验收边界仍不明确，调用 AskUserQuestion 向用户确认，每次一题。
不要重复询问已经明确的信息，需求明确时不必提问。可提供至多四个单选项，也可让用户自由回答。
回答后继续调查和制定计划，区分已确认条件与假设；用户回答不是执行授权。
禁止写文件、改文件或执行命令（包括只读命令）。形成可执行计划后给出文本并等待用户输入 /do。"""
BRIEF_PLAN_REMINDER = "当前仍是计划模式：只读调查，必要时用 AskUserQuestion 澄清；禁止写文件、改文件或执行命令，用户回答不是执行授权，计划完成后等待 /do。"


def plan_reminder(mode: str, iteration: int) -> RuntimeSupplement | None:
    mode = normalize_runtime_mode(mode)
    if type(iteration) is not int or iteration < 1:
        raise ValueError("非法模式或请求轮次")
    if mode != "plan":
        return None
    text = FULL_PLAN_REMINDER if (iteration - 1) % 4 == 0 else BRIEF_PLAN_REMINDER
    return RuntimeSupplement("plan", text, _APP_ORIGIN)
