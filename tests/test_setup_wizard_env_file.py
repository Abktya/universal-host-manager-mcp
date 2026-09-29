"""uhm-setup'in yazdigi .env dosyasinin izinlerini ve yedekleme davranisini dogrular.

0o600 (sahip-disinda kimse okuyamaz/yazamaz) POSIX'e ozgu bir kavramdir.
Windows'ta os.chmod ACL tabanli farkli bir modele denk dusurulur ve tam bu
degeri uretmez (os.stat her zaman 0o666/0o444 gibi bir seyi bildirir) --
bu bir bug degil, iki isletim sisteminin izin modelinin temelden farkli
olmasi. Bu yuzden tam-izin kontrolleri yalnizca POSIX'te calisir.
"""

import os
import stat

from universal_host_manager_mcp.setup_wizard import write_env

_IS_WINDOWS = os.name != "posix"


def test_write_env_sets_owner_only_permissions(tmp_path):
    env_path = tmp_path / ".env"
    write_env(env_path, {"FOO": "bar"})
    if _IS_WINDOWS:
        return
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
    if _IS_WINDOWS:
        return
    backup_mode = stat.S_IMODE(backup.stat().st_mode)
    assert backup_mode == 0o600, "yedeklenen dosya da (sir icerebilecegi icin) 600 olmali"


def test_write_env_rejects_values_containing_newline(tmp_path):
    import pytest
    from universal_host_manager_mcp.setup_wizard import write_env

    env_path = tmp_path / ".env"
    with pytest.raises(ValueError, match="newline"):
        write_env(env_path, {"AUTH0_CLIENT_SECRET": "line1\nEVIL_KEY=injected"})
    assert not env_path.exists()
