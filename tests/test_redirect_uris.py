"""OAuth client callback allowlist regression tests."""

from universal_host_manager_mcp import server


def test_known_mcp_clients_are_configured(monkeypatch):
    monkeypatch.delenv("UHM_ALLOWED_CLIENT_REDIRECT_URIS", raising=False)
    uris = server._allowed_client_redirect_uris()
    assert "https://chatgpt.com/connector_platform_oauth_redirect" in uris
    assert "https://app.mcptoai.com/api/mcp/oauth/callback" in uris
    assert "http://localhost:*" in uris


def test_operator_can_add_unknown_provider_callbacks(monkeypatch):
    monkeypatch.setenv(
        "UHM_ALLOWED_CLIENT_REDIRECT_URIS",
        "https://provider.example/oauth/callback, https://another.example/mcp/*\nhttps://third.example/cb",
    )
    uris = server._allowed_client_redirect_uris()
    assert "https://provider.example/oauth/callback" in uris
    assert "https://another.example/mcp/*" in uris
    assert "https://third.example/cb" in uris
