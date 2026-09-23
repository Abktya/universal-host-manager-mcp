"""uhm-setup'in yazdigi .env dosyasinin izinlerini ve yedekleme davranisini dogrular."""

import stat

from universal_host_manager_mcp.setup_wizard import write_env


def test_write_env_sets_owner_only_permissions(tmp_path):
    env_path = tmp_path / ".env"
    write_env(env_path, {"FOO": "bar"})
    mode = stat.S_IMODE(env_path.stat().st_mode)
    assert mode == 0o600


def test_write_env_backs_up_existing_file(tmp_path):
    env_path = tmp_path / ".env"
    env_path.write_text("OLD=1\n")

    write_env(env_path, {"NEW": "2"})

    backup = tmp_path / ".env.bak"
    assert backup.exists()
    assert "OLD=1" in backup.read_text()
    assert "NEW=2" in env_path.read_text()
    backup_mode = stat.S_IMODE(backup.stat().st_mode)
    assert backup_mode == 0o600, "yedeklenen dosya da (sir icerebilecegi icin) 600 olmali"


def test_write_env_rejects_values_containing_newline(tmp_path):
    import pytest
    from universal_host_manager_mcp.setup_wizard import write_env

    env_path = tmp_path / ".env"
    with pytest.raises(ValueError, match="newline"):
        write_env(env_path, {"AUTH0_CLIENT_SECRET": "line1\nEVIL_KEY=injected"})
    assert not env_path.exists()
