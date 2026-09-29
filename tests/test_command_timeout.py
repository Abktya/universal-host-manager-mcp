"""_run()'in timeout'ta tum sureci (alt surecler dahil) oldurdugunu dogrular.

subprocess.run(..., shell=True) yalnizca dogrudan shell surecini oldurur;
bir pipeline'da ('sleep | cat', POSIX) veya arka planda kalan bir islemde
(Windows) bu, ana shell'in cocuklarini yetim birakabilir. Bu, gecmiste
gercekten yasanmis ve duzeltilmis bir bug'du (process-group/process-tree
kill fix) -- bu test regresyonu yakalamak icin var.

Canlilik kontrolu icin platforma ozel surec-listeleme araclari (pgrep,
tasklist) yerine bir "marker dosyasi" teknigi kullanilir: arka plan islemi
normalde tamamlanacagi zaman bir dosyaya yazar; surec gercekten oldurulduyse
bu dosya HIC OLUSMAZ. Bu, hem POSIX hem Windows'ta ayni sekilde calisir.
"""

import os
import time

from universal_host_manager_mcp.server import _run

_IS_WINDOWS = os.name != "posix"


def _sleep_command(seconds: float) -> str:
    if _IS_WINDOWS:
        return f'powershell -NoProfile -Command "Start-Sleep -Seconds {seconds}"'
    return f"sleep {seconds}"


def test_short_command_completes_normally():
    result = _run("echo merhaba", timeout=5)
    assert "merhaba" in result


def test_timeout_message_is_returned_promptly():
    start = time.monotonic()
    result = _run(_sleep_command(5), timeout=1)
    elapsed = time.monotonic() - start
    assert "timed out" in result.lower()
    assert elapsed < 4, "_run, timeout suresinden cok sonra donmemeli"


def test_timeout_kills_full_process_tree_not_just_the_shell(tmp_path):
    marker = tmp_path / "still-alive.txt"
    if _IS_WINDOWS:
        # PowerShell'in kendisi de ayri bir cocuk surec olarak calisir;
        # sadece ust shell'i (cmd.exe) oldurmek bunu yetim birakirdi.
        cmd = (
            "powershell -NoProfile -Command "
            f"\"Start-Sleep -Seconds 2; 'done' | Out-File -FilePath '{marker}'\""
        )
    else:
        # Bir pipeline ('sleep | cat') shell'in IKI cocuk fork etmesine
        # neden olur; sadece shell'i oldurmek bunlari yetim birakirdi.
        cmd = f"sleep 2 | cat && echo done > {marker}"

    result = _run(cmd, timeout=0.5)
    assert "timed out" in result.lower()

    # Surecin normalde tamamlanacagi sureden fazla bekleyip, marker
    # dosyasinin gercekten HIC olusmadigini (surecin oldurulduaunu) dogrula.
    time.sleep(2.5)
    assert not marker.exists(), (
        "process tam oldurulmedi: arka planda calismaya devam edip marker "
        "dosyasini olusturdu"
    )
