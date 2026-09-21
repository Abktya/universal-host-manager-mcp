"""run_command'in komut icerigini varsayilan olarak loglamadigini dogrular.

Komut metni, argument olarak gecirilmis token/sifre gibi hassas veri
icerebilir; bu yuzden LOG_COMMANDS acikca 'true' yapilmadikca komutun
kendisi degil, sadece timeout'u loglanir.
"""

from tests.conftest import call_tool
from universal_host_manager_mcp import server


def test_command_text_not_logged_by_default(caplog):
    with caplog.at_level("INFO", logger="universal-host-manager"):
        call_tool(server.run_command, "echo cok-gizli-deger-xyz")
    assert "cok-gizli-deger-xyz" not in caplog.text


def test_log_commands_true_includes_command_text(monkeypatch, caplog):
    monkeypatch.setattr(server, "LOG_COMMANDS", True)
    with caplog.at_level("INFO", logger="universal-host-manager"):
        call_tool(server.run_command, "echo cok-gizli-deger-xyz")
    assert "cok-gizli-deger-xyz" in caplog.text
