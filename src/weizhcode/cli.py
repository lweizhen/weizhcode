from __future__ import annotations

from pathlib import Path

from weizhcode import __version__
from weizhcode.config import load_config, resolve_default_provider, ENV_REF_RE
from weizhcode.conversation import Conversation
from weizhcode.errors import WeizhCodeError
from weizhcode.providers import create_provider
from weizhcode.tui import StartupErrorApp, WeizhCodeApp
from weizhcode.models import ToolContext
from weizhcode.redaction import Redactor
from weizhcode.tools import create_default_registry
from weizhcode.tools.executor import ToolExecutor
from weizhcode.turn_runner import TurnRunner


def main() -> None:
    """Run the weizhCode terminal app."""
    try:
        config = load_config()
        provider_config = resolve_default_provider(config)
        provider = create_provider(provider_config)
    except WeizhCodeError as exc:
        StartupErrorApp(str(exc)).run()
        return

    redactor = Redactor(p.api_key for p in config.providers if not ENV_REF_RE.fullmatch(p.api_key))
    conversation = Conversation()
    registry = create_default_registry()
    executor = ToolExecutor(registry, ToolContext(Path.cwd()), redactor)
    runner = TurnRunner(provider, conversation, registry, executor, redactor)
    WeizhCodeApp(
        provider,
        conversation,
        runner=runner,
        redactor=redactor,
        provider_name=provider_config.name,
        model=provider_config.model,
        project_path=str(Path.cwd()),
        version=__version__,
    ).run()
