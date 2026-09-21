"""_run()'in timeout'ta tum process group'u oldurdugunu dogrular.

subprocess.run(..., shell=True) yalnizca dogrudan 'sh' surecini oldurur;
bir pipeline'da ('sleep | cat') shell IKI cocuk fork eder, ve sadece
shell'i oldurmek bu cocuklari yetim birakir. Bu, gecmiste gercekten
yasanmis ve duzeltilmis bir bug'du (process-group kill fix) -- bu test
regresyonu yakalamak icin var.
"""

import subprocess
import time

from universal_host_manager_mcp.server import _run


def test_short_command_completes_normally():
    result = _run("echo merhaba", timeout=5)
    assert "merhaba" in result


def test_timeout_message_is_returned_promptly():
    start = time.monotonic()
    result = _run("sleep 5", timeout=1)
    elapsed = time.monotonic() - start
    assert "timed out" in result.lower()
    assert elapsed < 4, "_run, timeout suresinden cok sonra donmemeli"


def test_timeout_kills_full_process_group_not_just_the_shell():
    # Essiz bir sure kullanarak baska bir surecle karismasini onluyoruz.
    duration = "13.371"
    cmd = f"sleep {duration} | cat"

    result = _run(cmd, timeout=0.5)
    assert "timed out" in result.lower()

    # Isletim sisteminin sureci gercekten temizlemesi icin kisa bir sure.
    time.sleep(0.5)
    check = subprocess.run(
        ["pgrep", "-fl", f"sleep {duration}"],
        capture_output=True,
        text=True,
    )
    # pgrep'in kendi argv'si de sorguyu icerebilir; asil kontrol edilen,
    # gercek bir 'sleep' komutunun hayatta kalip kalmadigi.
    assert "sleep" not in check.stdout, (
        f"process group tam oldurulmedi, hala calisan surec var: {check.stdout}"
    )
