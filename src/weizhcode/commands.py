"""仅处理空闲命令；提问与审批输入必须先由原通道处理。"""

COMMANDS = {'/exit': 'exit', '/quit': 'exit', '/plan': 'plan', '/do': 'do', '/compact': 'compact'}


def idle_command(text):
    value = text.strip()
    return COMMANDS.get(value, 'unknown' if value.startswith('/') else 'message')
