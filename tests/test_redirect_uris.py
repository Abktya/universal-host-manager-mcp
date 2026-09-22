"""OAuth client callback allowlist regression tests."""

from universal_host_manager_mcp import server


def test_chatgpt_connector_platform_callback_is_configured():
    source = open(server.__file__, encoding="utf-8").read()
    assert "https://chatgpt.com/connector_platform_oauth_redirect" in source
