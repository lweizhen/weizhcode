from weizhcode.compact.contracts import FileReadCapture
from weizhcode.compact.recovery import recovery_variants, with_recovery
from weizhcode.prompting.contracts import PromptContext
from weizhcode.models import ToolDefinition


def test_ctx_t45_ctx_t46_ctx_t47_recovery_is_snapshot_and_bounded():
    files = tuple(FileReadCapture(str(i), f'no-such-file-{i}', 12, 20, 'x'*17500, True, i, 'past') for i in range(5))
    tools = (ToolDefinition('read_file', 'actual reader', {'type': 'object'}),)
    variants = list(recovery_variants(files, tools, '索引入口'))
    assert 'no-such-file-0' in variants[0] and 'start_line' in variants[0]
    assert 'no-such-file' not in variants[-1]
    assert 'schema_sha256' in variants[-1] and 'actual reader' not in variants[-1]
    assert '索引入口' in variants[-1] and '重新读取' in variants[-1]
    prompt = with_recovery(PromptContext('stable'), variants[0])
    assert prompt.stable_text == 'stable' and prompt.supplements[-1].kind == 'context_recovery'
