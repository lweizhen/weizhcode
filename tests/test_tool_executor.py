from pathlib import Path

from weizhcode.models import PreparedOperation, PreparedOperationPreview, ToolCall, ToolContext, ToolResult


def test_operation_contract_failed_preparation_is_not_executable():
    call = ToolCall("id", "write_file", '{}')
    error = ToolResult.failure(call, "INVALID_ARGUMENTS", "缺少路径")
    operation = PreparedOperation(call, {}, error=error)
    preview = PreparedOperationPreview(operation.operation_id, "", "", error=error)
    assert operation.error.is_error
    assert preview.error.is_error
    assert not hasattr(preview, "state")
    assert not hasattr(ToolContext(Path.cwd()), "api_key")


def test_operation_contract_parameters_separate_from_preview():
    call = ToolCall("id", "write_file", '{}')
    operation = PreparedOperation(call, {"content": "original"}, preview="[redacted]")
    assert operation.arguments["content"] == "original"
    assert operation.operation_id
