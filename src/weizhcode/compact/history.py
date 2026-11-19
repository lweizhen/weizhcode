from __future__ import annotations

from .contracts import HistoryEntry, HistorySnapshot


def validate_entries(entries):
    """整体替换前保守验证；诊断工具交换也必须保留完整对应关系。"""
    if entries is None:
        raise ValueError("历史候选不能为空对象")
    candidate = HistorySnapshot(0, tuple(entries)).entries
    pending = None
    last_human_seq = 0
    for entry in candidate:
        message = entry.message
        if message.role not in {"user", "assistant", "tool"}:
            raise ValueError("历史消息角色无效")
        if entry.origin == "human":
            if message.role != "user" or entry.human_seq is None or entry.human_seq <= last_human_seq:
                raise ValueError("用户原话来源或序号不合法")
            last_human_seq = entry.human_seq
        if entry.origin == "tool" and message.role != "tool":
            raise ValueError("工具来源与消息角色不一致")
        if message.tool_calls and message.role != "assistant":
            raise ValueError("工具调用必须来自助手")
        if message.tool_results and message.role != "tool":
            raise ValueError("工具结果角色错误")
        if pending is not None:
            previous, calls = pending
            if message.role != "tool":
                raise ValueError("工具调用缺少紧邻的结果")
            if previous.turn_id != entry.turn_id:
                raise ValueError("工具调用和结果不属于同一任务")
            if len(calls) != len(message.tool_results) or any(
                call.call_id != result.call_id or call.name != result.tool_name
                for call, result in zip(calls, message.tool_results)
            ):
                raise ValueError("工具调用与结果身份或数量不匹配")
            if entry.result_keys and len(entry.result_keys) != len(calls):
                raise ValueError("工具来源数量与结果不匹配")
            pending = None
        elif message.role == "tool":
            raise ValueError("存在孤立工具结果")
        if message.tool_calls:
            pending = (entry, message.tool_calls)
    if pending is not None:
        raise ValueError("工具调用缺少结果")
    return candidate


def message_groups(entries):
    groups = []
    for entry in validate_entries(entries):
        if not groups or groups[-1][-1].turn_id != entry.turn_id:
            groups.append([])
        groups[-1].append(entry)
    return tuple(tuple(group) for group in groups)


def split_recent(entries):
    """至少一万近似token且至少五条；完整任务组保留而非切断工具交换。"""
    from .estimator import chars_tokens
    from weizhcode.providers.request import canonical
    from dataclasses import asdict
    groups = message_groups(entries)
    position, tokens, messages = len(groups), 0, 0
    while position and (tokens < 10_000 or messages < 5):
        position -= 1
        for entry in groups[position]:
            tokens += chars_tokens(canonical(asdict(entry.message)))
            messages += 1
    return groups[:position], tuple(e for group in groups[position:] for e in group)
