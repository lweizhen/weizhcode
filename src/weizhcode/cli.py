from __future__ import annotations

from weizhcode.config import load_config, resolve_default_provider
from weizhcode.conversation import Conversation
from weizhcode.errors import WeizhCodeError
from weizhcode.providers import create_provider
from weizhcode.tui import StartupErrorApp, WeizhCodeApp


def main() -> None:
    """Run the weizhCode terminal app."""
    try:
        config = load_config()
        provider_config = resolve_default_provider(config)
        provider = create_provider(provider_config)
    except WeizhCodeError as exc:
        StartupErrorApp(str(exc)).run()
        return

    WeizhCodeApp(
        provider,
        Conversation(),
        provider_name=provider_config.name,
    ).run()
