import pytest

from weizhcode.mcp.contracts import McpToolIdentity


@pytest.mark.parametrize("server,remote", [("a__b", "x"), ("a", "x__y"), ("a", ".x"), ("a", "x" * 64)])
def test_contract_identity_rejects_ambiguous_names(server, remote):
    with pytest.raises(ValueError):
        McpToolIdentity(f"mcp__{server}__{remote}", server, remote, "a" * 32)
