TOOL_TIMEOUT_SECONDS = 30.0
MAX_RESULT_CHARS = 20_000
MAX_READ_LINES = 200
MAX_FILE_MATCHES = 200
MAX_CONTENT_MATCHES = 100
CHUNK_SIZE = 16_384
MAX_LINE_CHARS = 65_536


def excerpt(text: str, limit: int = MAX_RESULT_CHARS) -> str:
    marker = "\n[truncated]"
    return text if len(text) <= limit else text[: max(0, limit - len(marker))] + marker
