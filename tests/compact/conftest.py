from __future__ import annotations

import ipaddress
import os
import socket
from copy import deepcopy
from dataclasses import dataclass
from pathlib import Path

import pytest


@dataclass
class ManualClock:
    value: float = 0.0

    def __call__(self):
        return self.value

    def advance(self, seconds):
        if seconds < 0:
            raise ValueError("测试时钟不能倒退")
        self.value += seconds


class ScriptedProvider:
    """只消费预置事件，不创建任何网络连接。"""

    def __init__(self, scripts=()):
        self.scripts = list(scripts)
        self.requests = []

    async def stream_chat(self, messages, **kwargs):
        self.requests.append((deepcopy(messages), deepcopy(kwargs)))
        if not self.scripts:
            raise AssertionError("测试模型脚本已耗尽")
        for event in self.scripts.pop(0):
            if isinstance(event, BaseException):
                raise event
            yield event


@pytest.fixture(autouse=True)
def isolated_context(tmp_path, monkeypatch):
    """仅作用于本目录；配置、家目录与网络均使用隔离样本。"""
    project, home = tmp_path / "project", tmp_path / "home"
    project.mkdir()
    home.mkdir()
    monkeypatch.chdir(project)
    for name in ("HOME", "USERPROFILE", "APPDATA", "LOCALAPPDATA", "XDG_CONFIG_HOME"):
        monkeypatch.setenv(name, str(home))
    monkeypatch.setattr(Path, "home", classmethod(lambda cls: home))
    for name in tuple(os.environ):
        if name.endswith(("_API_KEY", "_ACCESS_TOKEN")) or name.upper() in {
            "HTTP_PROXY", "HTTPS_PROXY", "ALL_PROXY"
        }:
            monkeypatch.delenv(name, raising=False)

    def local_address(address):
        if isinstance(address, (str, bytes)):
            return True  # AF_UNIX/socketpair由事件循环自行管理。
        host = address[0]
        if host == "localhost":
            return True
        try:
            return ipaddress.ip_address(host).is_loopback
        except ValueError:
            return False

    for method in ("connect", "connect_ex"):
        original = getattr(socket.socket, method)

        def guarded(sock, address, _original=original):
            if sock.family in (socket.AF_INET, socket.AF_INET6) and not local_address(address):
                raise AssertionError("上下文测试禁止外部网络")
            return _original(sock, address)

        monkeypatch.setattr(socket.socket, method, guarded)

    original_dns = socket.getaddrinfo

    def guarded_dns(host, *args, **kwargs):
        if not local_address((host, 0)):
            raise AssertionError("上下文测试禁止外部DNS")
        return original_dns(host, *args, **kwargs)

    monkeypatch.setattr(socket, "getaddrinfo", guarded_dns)
    original_open = Path.open

    def guarded_open(path, mode="r", *args, **kwargs):
        if "r" in mode and path.name in {"weizhcode.yaml", "mcp.yaml", "permissions.yaml", "trust.yaml"}:
            if not path.resolve().is_relative_to(tmp_path.resolve()):
                raise AssertionError("上下文测试禁止读取真实配置")
        return original_open(path, mode, *args, **kwargs)

    monkeypatch.setattr(Path, "open", guarded_open)
    return project, home


@pytest.fixture
def clock():
    return ManualClock()


@pytest.fixture
def fake_provider():
    return ScriptedProvider
