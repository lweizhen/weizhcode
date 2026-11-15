from weizhcode.prompting.modules import assemble_modules
from weizhcode.prompting.reminders import FULL_PLAN_REMINDER


SYSTEM_PROMPT = assemble_modules()
PLAN_MODE_REMINDER = FULL_PLAN_REMINDER

EXECUTE_DIRECTIVE = "请按上面的计划开始执行。"
