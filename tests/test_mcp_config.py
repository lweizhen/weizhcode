import json

import pytest

from weizhcode.mcp.config import parse_config_layers
from weizhcode.mcp.contracts import McpServerConfig, McpToolIdentity


def raw(servers):
    return json.dumps({"mcp_servers": servers}).encode()


def stdio(**updates):
    return {"type": "stdio", "command": "python", **updates}


def test_contract():
    args = ["hello"]
    config = McpServerConfig("demo", "user", "stdio", "python", args)
    args.clear()
    assert config.args == ("hello",)
    identity = McpToolIdentity("mcp__demo__echo", "demo", "echo", "a" * 32)
    assert identity.remote_name == "echo"
    with pytest.raises(ValueError):
        McpToolIdentity("mcp__forged__echo", "demo", "echo", "a" * 32)


@pytest.mark.parametrize("empty", [None, b"", b"null", b"{}", b"mcp_servers: null", b"mcp_servers: {}"])
def test_layers_empty(empty):
    result = parse_config_layers(empty, None, environ={})
    assert result.servers == () and not result.warnings


def test_layers_complete_override():
    user = raw({"demo": stdio(env={"TOKEN": "from-user"}), "other": stdio()})
    result = parse_config_layers(user, raw({"demo": {"type": "http", "url": "https://example.invalid/mcp"}}), environ={})
    assert [s.name for s in result.servers] == ["demo", "other"]
    assert result.servers[0].source == "project" and result.servers[0].env == {}
    assert result.servers[1].source == "user"
    assert "from-user" not in result.secret_values  # Shadowed credentials are not used.


@pytest.mark.parametrize("bad", [{}, {"type": "stdio"}, stdio(env={"TOKEN": "${MISSING}"})])
def test_layers_invalid_project_shadows_user(bad):
    result = parse_config_layers(raw({"demo": stdio(), "other": stdio()}), raw({"demo": bad}), environ={})
    assert [s.name for s in result.servers] == ["other"]
    assert result.warnings


@pytest.mark.parametrize("bad", [b"a: [", b"[]", b"mcp_servers: 7", b"mcp_servers: {}\nmcp_servers: {}",
                               b"mcp_servers: &x {cycle: *x}", b"!!python/object:builtins.object {}",
                               b"mcp_servers: {}\nunknown: 1", b"mcp_servers: {x: .nan}"])
def test_safe_load_invalid_layer(bad):
    result = parse_config_layers(raw({"demo": stdio()}), bad, environ={})
    assert [s.name for s in result.servers] == ["demo"]
    assert len(result.warnings) == 1 and result.warnings[0].source == "project"


@pytest.mark.parametrize("bad", [stdio(command=""), stdio(args="bad"), stdio(args=[1]), stdio(env={"X": 1}),
                               stdio(unknown=1), stdio(headers={}), {"type": "http"},
                               {"type": "http", "url": "file:///tmp/x"},
                               {"type": "http", "url": "https://u:secret@example.invalid"},
                               {"type": "http", "url": "https://example.invalid/#fragment"},
                               {"type": "http", "url": "https://example.invalid:bad"},
                               {"type": "http", "url": "https://example.invalid", "headers": {"Host": "evil"}},
                               {"type": "http", "url": "https://example.invalid", "headers": {"X": "a\r\nb"}},
                               {"type": "http", "url": "https://example.invalid", "headers": {"X": "a", "x": "b"}}])
def test_fields_invalid(bad):
    result = parse_config_layers(raw({"bad": bad, "good": stdio()}), None, environ={})
    assert [s.name for s in result.servers] == ["good"]
    assert result.warnings[0].code == "MCP_SERVER_INVALID"


def test_mcp_expansion():
    data = raw({"demo": stdio(command="${LITERAL}", args=["${LITERAL}"], env={"A": "pre-${X}-${EMPTY}"}),
                "remote": {"type": "http", "url": "https://example.invalid/mcp?x=${LITERAL}",
                           "headers": {"Authorization": "Bearer ${X}"}}})
    before = bytes(data)
    result = parse_config_layers(data, None, environ={"X": "${NO_RECURSION}", "EMPTY": ""})
    assert not result.warnings and data == before
    assert result.servers[0].env == {"A": "pre-${NO_RECURSION}-"}
    assert result.servers[0].command == "${LITERAL}" and result.servers[0].args == ("${LITERAL}",)
    assert result.servers[1].headers == {"authorization": "Bearer ${NO_RECURSION}"}
    assert result.servers[1].url.endswith("${LITERAL}")
    assert "${NO_RECURSION}" in result.secret_values


def test_mcp_expansion_missing():
    result = parse_config_layers(raw({"demo": stdio(env={"A": "${MISSING}-${OTHER}"}), "good": stdio()}), None, environ={})
    assert [s.name for s in result.servers] == ["good"]
    assert [w.variable for w in result.warnings] == ["MISSING", "OTHER"]
    assert all(w.code == "MCP_ENV_UNDEFINED" for w in result.warnings)


def test_limits():
    result = parse_config_layers(b" " * (256 * 1024 + 1), None, environ={})
    assert not result.servers and result.warnings[0].code == "MCP_CONFIG_LIMIT"
    result = parse_config_layers(raw({f"s{i:02}": stdio() for i in range(17)}), None, environ={})
    assert len(result.servers) == 16 and result.warnings[0].server_name == "s16"
    for updates in ({"command": "x" * 8193}, {"args": ["x"] * 129}, {"env": {f"X{i}": "x" for i in range(129)}}):
        assert not parse_config_layers(raw({"demo": stdio(**updates)}), None, environ={}).servers
    assert parse_config_layers(raw({"demo": stdio(command="x" * 8192, args=["a"] * 128)}), None, environ={}).servers


def test_fields_windows_scripts(monkeypatch):
    import weizhcode.mcp.config as module
    monkeypatch.setattr(module.shutil, "which", lambda *a, **kw: "C:/tools/program.cmd")
    if module.os.name == "nt":
        assert not parse_config_layers(raw({"demo": stdio(command="program")}), None, environ={}).servers


def test_mcp_budget_expanded_configuration():
    values = {f"V{i}": "${BIG}" for i in range(128)}
    result = parse_config_layers(raw({"a": stdio(env=values), "b": stdio(env=values)}), None, environ={"BIG": "x" * 8192})
    assert len(result.servers) <= 1
    assert result.warnings and all(w.code == "MCP_CONFIG_LIMIT" for w in result.warnings)


def test_mcp_example_parses_synthetic_environment():
    from pathlib import Path
    example = Path(__file__).parents[1] / "docs/mcp/mcp-servers.example.yaml"
    result = parse_config_layers(None, example.read_bytes(), environ={"CONTEXT7_API_KEY": "synthetic-c7", "DEMO_TOKEN": "synthetic-demo"})
    assert not result.warnings and len(result.servers) == 2
    assert result.servers[0].headers == {"authorization": "Bearer synthetic-c7"}
