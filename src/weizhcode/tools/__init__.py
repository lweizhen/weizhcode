"""固定内置工具；延迟导入避免统一模型依赖具体工具。"""


def create_default_registry():
    from weizhcode.tools.registry import ToolRegistry
    from weizhcode.tools.read_file import ReadFileTool
    from weizhcode.tools.write_file import WriteFileTool
    from weizhcode.tools.edit_file import EditFileTool
    from weizhcode.tools.run_command import RunCommandTool
    from weizhcode.tools.find_files import FindFilesTool
    from weizhcode.tools.search_content import SearchContentTool
    from weizhcode.tools.ask_user_question import AskUserQuestionTool

    registry = ToolRegistry()
    for tool_type in (ReadFileTool, WriteFileTool, EditFileTool, RunCommandTool, FindFilesTool, SearchContentTool, AskUserQuestionTool):
        registry.register(tool_type())
    return registry
