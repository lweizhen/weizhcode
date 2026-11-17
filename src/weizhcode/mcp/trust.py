"""Fixed-path trust operations. Only executed by the application ControlWorker."""
from __future__ import annotations

from dataclasses import asdict
import hashlib
import hmac
import json
import os
from pathlib import Path
import stat
import subprocess
from uuid import uuid4

from .limits import MAX_CONFIG_BYTES


def encode(value):
    return json.dumps(value, sort_keys=True, ensure_ascii=False, allow_nan=False, separators=(",", ":")).encode()


def checked_path(base, relative):
    base = Path(base)
    if not base.is_absolute() or base.resolve(strict=True) != base:
        raise ValueError("MCP_CONTROL_ROOT")
    cursor = base
    for part in Path(relative).parts:
        if part in {"..", "."}:
            raise ValueError("MCP_CONTROL_PATH")
        cursor = cursor / part
        try:
            info = cursor.lstat()
        except FileNotFoundError:
            continue
        if stat.S_ISLNK(info.st_mode) or getattr(info, "st_file_attributes", 0) & 0x400:
            raise ValueError("MCP_CONTROL_REDIRECTED")
    return cursor


def read_bytes(base, relative):
    path = checked_path(base, relative)
    try:
        before = path.lstat()
    except FileNotFoundError:
        return None
    if not stat.S_ISREG(before.st_mode) or before.st_size > MAX_CONFIG_BYTES:
        raise ValueError("MCP_CONTROL_FILE")
    fd = os.open(path, os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0) | getattr(os, "O_NONBLOCK", 0))
    with os.fdopen(fd, "rb") as stream:
        now = os.fstat(stream.fileno())
        if (before.st_dev, before.st_ino) != (now.st_dev, now.st_ino) or not stat.S_ISREG(now.st_mode):
            raise ValueError("MCP_CONTROL_CHANGED")
        raw = stream.read(MAX_CONFIG_BYTES + 1)
    checked_path(base, relative)
    if len(raw) > MAX_CONFIG_BYTES:
        raise ValueError("MCP_CONTROL_LIMIT")
    return raw


def git_safe(path):
    # Git config/environment must not redirect these read-only probes to another repository.
    env = {k: v for k, v in os.environ.items() if not k.upper().startswith("GIT_")}
    options = {"capture_output": True, "env": env, "timeout": 2}
    if os.name == "nt":
        options["creationflags"] = subprocess.CREATE_NO_WINDOW
    directory = path.parent
    while not directory.exists():
        directory = directory.parent
    probe = subprocess.run(["git", "-C", str(directory), "rev-parse", "--show-toplevel"], **options)
    if probe.returncode:
        return not any((p / ".git").exists() for p in (directory, *directory.parents))
    root = Path(probe.stdout.decode().strip())
    relative = str(path.relative_to(root))
    tracked = subprocess.run(["git", "-C", str(root), "ls-files", "--error-unmatch", "--", relative], **options)
    ignored = subprocess.run(["git", "-C", str(root), "check-ignore", "--no-index", "-q", "--", relative], **options)
    return tracked.returncode == 1 and ignored.returncode == 0


def atomic(base, relative, data, expected=None):
    path = checked_path(base, relative)
    path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    checked_path(base, relative)
    temp = path.with_name(f".mcp-trust.{uuid4().hex}.tmp")
    identity = None
    try:
        fd = os.open(temp, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        with os.fdopen(fd, "wb") as stream:
            info = os.fstat(stream.fileno())
            identity = (info.st_dev, info.st_ino)
            stream.write(data)
            stream.flush()
            os.fsync(stream.fileno())
        if read_bytes(base, relative) != expected:
            raise ValueError("MCP_TRUST_CONFLICT")
        checked_path(base, relative)
        os.replace(temp, path)
    finally:
        if identity and temp.exists():
            info = temp.lstat()
            if (info.st_dev, info.st_ino) == identity and stat.S_ISREG(info.st_mode):
                temp.unlink()


def get_key(home, *, create=False):
    relative = ".weizhcode/mcp-trust.key"
    path = checked_path(home, relative)
    raw = read_bytes(home, relative)
    if raw is None:
        if not create:
            return None
        if not git_safe(path) or not git_safe(path.with_name(".mcp-trust.fake.tmp")):
            raise ValueError("MCP_TRUST_NOT_IGNORED")
        key = os.urandom(32)
        if os.name == "nt":
            import win32crypt
            raw = win32crypt.CryptProtectData(key, None, None, None, None, 0)
        else:
            raw = key
        atomic(home, relative, raw)
    if os.name == "nt":
        import win32crypt
        key = win32crypt.CryptUnprotectData(raw, None, None, None, 0)[1]
    else:
        if path.stat().st_mode & 0o077 or path.parent.stat().st_mode & 0o077:
            raise ValueError("MCP_TRUST_KEY_PERMISSIONS")
        key = raw
    if len(key) != 32:
        raise ValueError("MCP_TRUST_KEY_INVALID")
    return key


def fingerprint(config, root, key):
    root = Path(root)
    info = root.stat()
    payload = {"version": 1, "root": str(root), "identity": [info.st_dev, info.st_ino], "server": asdict(config)}
    return hmac.new(key, encode(payload), hashlib.sha256).hexdigest()


def inspect_trust(root, home, configs):
    key = get_key(home)
    if key is None:
        return []
    raw = read_bytes(root, ".weizhcode/mcp-trust.local.json")
    if raw is None:
        return []
    value = json.loads(raw)
    body = value["body"]
    signature = hmac.new(key, encode(body), hashlib.sha256).hexdigest()
    if body.get("version") != 1 or not hmac.compare_digest(signature, value["signature"]):
        raise ValueError("MCP_TRUST_INVALID")
    entries = body["entries"]
    return [c.name for c in configs if entries.get(c.name) == fingerprint(c, root, key)]


def remember(root, home, config):
    relative = ".weizhcode/mcp-trust.local.json"
    path = checked_path(root, relative)
    if not git_safe(path) or not git_safe(path.with_name(".mcp-trust.fake.tmp")):
        raise ValueError("MCP_TRUST_NOT_IGNORED")
    key = get_key(home, create=True)
    previous = read_bytes(root, relative)
    entries = {}
    if previous:
        value = json.loads(previous)
        body = value["body"]
        if body.get("version") != 1 or not hmac.compare_digest(
                value["signature"], hmac.new(key, encode(body), hashlib.sha256).hexdigest()):
            raise ValueError("MCP_TRUST_INVALID")
        entries = dict(body["entries"])
    entries[config.name] = fingerprint(config, root, key)
    body = {"version": 1, "entries": entries}
    data = encode({"body": body, "signature": hmac.new(key, encode(body), hashlib.sha256).hexdigest()})
    if len(data) > MAX_CONFIG_BYTES:
        raise ValueError("MCP_TRUST_LIMIT")
    atomic(root, relative, data, previous)
