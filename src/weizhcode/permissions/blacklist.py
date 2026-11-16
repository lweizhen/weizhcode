"""Fixed heuristic rules, not a complete shell-security parser or OS isolation."""
import re


_ROOT = r'''(?<!\S)(?:["']?(?:/(?:\*)?|~(?:/\*)?|\$HOME(?:/\*)?|\$\{HOME\}(?:/\*)?)["']?)(?=\s|[;&|]|$)'''
_WIN_ROOT = r'''(?<!\S)(?:["']?(?:[a-z]:[\\/](?:\*)?|%userprofile%(?:[\\/]\*)?|\$env:userprofile(?:[\\/]\*)?|~(?:[\\/]\*)?)["']?)(?=\s|[;&|]|$)'''
_PATTERNS = (
    ("posix_root_delete", r"\brm\s+(?=[^;|\n]*(?:-[a-zA-Z]*r|--recursive))(?=[^;|\n]*(?:-[a-zA-Z]*f|--force))[^;|\n]*?" + _ROOT),
    ("device_write", r"\bdd\b[^;|\n]*\bof\s*=\s*[\"']?/dev/"),
    ("filesystem_format", r"\bmkfs(?:\.[a-z0-9]+)?\b"),
    ("raw_redirect", r">\s*[\"']?/dev/(?:sd|hd|nvme|disk)"),
    ("fork_bomb", r":\s*\(\s*\)\s*\{[^}\n]*\|[^}\n]*&[^}\n]*\}"),
    ("windows_root_delete", r"\b(?:remove-item|rm|ri|del)\s+(?=[^;|\n]*(?:-recurse\b|-r\b|-rf\b|-fr\b))[^;|\n]*?" + _WIN_ROOT),
    ("cmd_root_delete", r"\b(?:rd|rmdir)\s+(?=[^;|\n]*/s\b)[^;|\n]*?" + _WIN_ROOT),
    ("windows_disk_format", r"(?:^|[;&|\n]\s*|\s)(?:format(?:\.com)?\s+[a-z]:|clear-disk\b|format-volume\b)"),
)
_BLACKLIST = tuple((name, re.compile(pattern, re.IGNORECASE)) for name, pattern in _PATTERNS)


def hits_blacklist(command: str) -> str | None:
    for name, pattern in _BLACKLIST:
        if pattern.search(command):
            return name
    return None
