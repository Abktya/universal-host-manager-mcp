"""read_file/write_file boyut siniri testleri."""

from tests.conftest import call_tool
from universal_host_manager_mcp import server


def test_write_file_rejects_content_over_max_write_bytes(monkeypatch):
    monkeypatch.setattr(server, "MAX_WRITE_BYTES", 10)
    result = call_tool(server.write_file, "big.txt", "x" * 100)
    assert "exceeds MAX_WRITE_BYTES" in result


def test_write_then_read_roundtrip():
    call_tool(server.write_file, "hello.txt", "merhaba dunya")
    assert call_tool(server.read_file, "hello.txt") == "merhaba dunya"


def test_read_file_rejects_file_over_max_read_bytes(monkeypatch):
    call_tool(server.write_file, "toobig.txt", "y" * 1000)
    monkeypatch.setattr(server, "MAX_READ_BYTES", 10)
    result = call_tool(server.read_file, "toobig.txt")
    assert "exceeds MAX_READ_BYTES" in result


def test_read_file_missing_file_reports_error():
    result = call_tool(server.read_file, "does-not-exist.txt")
    assert "not found" in result.lower() or "error" in result.lower()
