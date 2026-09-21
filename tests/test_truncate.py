"""_truncate() cikti kisaltma davranisinin testleri."""

from universal_host_manager_mcp import server


def test_short_text_is_returned_unchanged():
    assert server._truncate("merhaba") == "merhaba"


def test_long_text_is_shortened_and_marked():
    text = "x" * 1000
    out = server._truncate(text, limit=100)
    assert len(out) < len(text)
    assert "truncated" in out
    assert out.startswith("x" * 50)
    assert out.endswith("x" * 50)


def test_truncate_respects_custom_limit():
    text = "a" * 500
    out = server._truncate(text, limit=40)
    half = 40 // 2
    assert out.startswith("a" * half)
    assert out.endswith("a" * half)
