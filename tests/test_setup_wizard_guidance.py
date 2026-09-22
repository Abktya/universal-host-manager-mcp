"""Beginner setup flow validation and regression tests."""

import os
import subprocess
import sys

import pytest

from universal_host_manager_mcp import setup_wizard


def test_hostname_validation_rejects_short_or_url_values():
    assert setup_wizard._validate_hostname("MCP.Example.com.") == "mcp.example.com"
    for value in ("test", "https://mcp.example.com", "mcp.example.com/path"):
        with pytest.raises(ValueError):
            setup_wizard._validate_hostname(value)


def test_ngrok_requires_a_real_static_domain_suffix():
    accepted = (
        "demo.ngrok-free.dev",
        "demo.ngrok-free.app",
        "demo.ngrok.dev",
        "demo.ngrok.app",
    )
    for hostname in accepted:
        assert setup_wizard._validate_hostname(hostname, ngrok=True) == hostname

    with pytest.raises(ValueError):
        setup_wizard._validate_hostname("test.example.com", ngrok=True)


def test_ngrok_follow_up_explains_installation_and_token_setup():
    steps = setup_wizard._ngrok_follow_up("demo.ngrok-free.dev", 8700)
    guidance = "\n".join(steps)

    assert "brew install ngrok/ngrok/ngrok" in guidance
    assert "sudo snap install ngrok" in guidance
    assert "dashboard.ngrok.com/get-started/your-authtoken" in guidance
    assert "ngrok config add-authtoken YOUR_NGROK_TOKEN" in guidance
    assert "domain ID" in guidance
    assert "ngrok http --url=demo.ngrok-free.dev 8700" in guidance


def test_linux_autostart_configures_both_ngrok_services(tmp_path):
    script = "\n".join(setup_wizard._remote_autostart_steps(
        "demo.ngrok-free.dev", 8700, "linux", tmp_path,
        "/venv/bin/universal-host-manager-mcp",
    ))
    assert "universal-host-manager-mcp.service" in script
    assert "universal-host-manager-ngrok.service" in script
    assert f"WorkingDirectory={tmp_path}" in script
    assert "ExecStart=/venv/bin/universal-host-manager-mcp" in script
    assert "ngrok-free.dev 8700" in script
    assert "enable-linger" in script
    assert script.startswith("#!/bin/sh")
    assert "<<EOF" in script


def test_macos_autostart_configures_both_ngrok_agents(tmp_path):
    script = "\n".join(setup_wizard._remote_autostart_steps(
        "demo.ngrok-free.dev", 8700, "macos", tmp_path,
        "/venv/bin/universal-host-manager-mcp",
    ))
    assert "io.bkty.universal-host-manager-mcp.plist" in script
    assert "io.bkty.universal-host-manager-ngrok.plist" in script
    assert "--url=demo.ngrok-free.dev" in script
    assert "launchctl bootstrap" in script


def test_cloudflare_guidance_and_linux_autostart(tmp_path):
    guidance = "\n".join(setup_wizard._cloudflare_follow_up("mcp.example.com", 8765))
    assert "connections/connect-networks/downloads" in guidance
    assert "brew install cloudflared" in guidance
    assert "cloudflared tunnel login" in guidance
    assert "cloudflared tunnel route dns universal-host-manager-mcp mcp.example.com" in guidance

    script = "\n".join(setup_wizard._cloudflare_autostart_steps(
        "linux", tmp_path, "/venv/bin/universal-host-manager-mcp",
    ))
    assert "universal-host-manager-mcp.service" in script
    assert "universal-host-manager-cloudflared.service" in script
    assert "cloudflared" in script
    assert "tunnel run universal-host-manager-mcp" in script
    assert "enable-linger" in script


def test_cloudflare_macos_autostart_configures_both_agents(tmp_path):
    script = "\n".join(setup_wizard._cloudflare_autostart_steps(
        "macos", tmp_path, "/venv/bin/universal-host-manager-mcp",
    ))
    assert "io.bkty.universal-host-manager-mcp.plist" in script
    assert "io.bkty.universal-host-manager-cloudflared.plist" in script
    assert "launchctl bootstrap" in script


def test_public_url_must_be_https_origin_without_mcp_path():
    assert setup_wizard._validate_https_base_url("https://mcp.example.com/") == "https://mcp.example.com"
    for value in ("http://mcp.example.com", "https://test", "https://mcp.example.com/mcp"):
        with pytest.raises(ValueError):
            setup_wizard._validate_https_base_url(value)


def test_port_prompt_recovers_from_yes_and_out_of_range(monkeypatch):
    answers = iter(("y", "70000", "8765"))
    monkeypatch.setattr(setup_wizard.Prompt, "ask", lambda *args, **kwargs: next(answers))
    assert setup_wizard._ask_port() == 8765


def test_required_prompt_rejects_empty_value(monkeypatch):
    answers = iter(("", "client-id"))
    monkeypatch.setattr(setup_wizard.Prompt, "ask", lambda *args, **kwargs: next(answers))
    assert setup_wizard._ask_required("Client ID") == "client-id"


def test_auth0_settings_are_derived_from_public_origin():
    settings = dict(setup_wizard._auth0_settings("https://mcp.example.com/"))

    assert settings["Application Ownership"] == "First-party"
    assert settings["Application Type"] == "Regular Web Application"
    assert settings["Application Login URI"] == "Leave blank"
    assert settings["Allowed Callback URLs"] == "https://mcp.example.com/auth/callback"
    assert settings["Allowed Logout URLs"] == "https://mcp.example.com"
    assert settings["Allowed Web Origins"] == "https://mcp.example.com"
    assert settings["Allowed Origins (CORS)"] == "https://mcp.example.com"
    assert settings["API Identifier / Audience"] == "https://mcp.example.com/"
    assert settings["MCP endpoint (for AI clients)"] == "https://mcp.example.com/mcp"
    assert "User-delegated Access" in settings["Application > API Access"]


def test_auth0_guidance_shows_fastmcp_callback(monkeypatch, capsys):
    monkeypatch.setattr(setup_wizard.Confirm, "ask", lambda *args, **kwargs: False)

    assert setup_wizard.ask_auth0("https://mcp.example.com/") is None

    output = capsys.readouterr().out
    assert "Allowed Callback URLs" in output
    assert "Allowed Web Origins" in output
    assert "AUTH0_SECRET" in output
    assert "Claude, ChatGPT, or Grok callback URLs" in output



def test_auth0_env_block_imports_required_application_values():
    block = """
    # copied from Auth0
    AUTH0_DOMAIN=dev-example.eu.auth0.com
    AUTH0_CLIENT_ID=client123
    AUTH0_CLIENT_SECRET="real-secret-value"
    AUTH0_SECRET=not-used
    APP_BASE_URL=https://mcp.example.com
    PORT=443
    """

    assert setup_wizard._parse_auth0_env_block(block) == {
        "AUTH0_DOMAIN": "dev-example.eu.auth0.com",
        "AUTH0_CLIENT_ID": "client123",
        "AUTH0_CLIENT_SECRET": "real-secret-value",
    }


@pytest.mark.parametrize(
    "secret",
    ("******MASKED********", "********", "prefix*MIDDLE"),
)
def test_auth0_env_block_rejects_masked_secret(secret):
    block = (
        "AUTH0_DOMAIN=dev-example.eu.auth0.com\n"
        "AUTH0_CLIENT_ID=client123\n"
        f"AUTH0_CLIENT_SECRET={secret}\n"
    )
    with pytest.raises(ValueError, match="masked"):
        setup_wizard._parse_auth0_env_block(block)


def test_auth0_env_block_reports_missing_values():
    with pytest.raises(ValueError, match="AUTH0_CLIENT_SECRET"):
        setup_wizard._parse_auth0_env_block(
            "AUTH0_DOMAIN=dev-example.eu.auth0.com\nAUTH0_CLIENT_ID=client123\n"
        )


def test_clipboard_import_parses_auth0_block(monkeypatch):
    monkeypatch.setattr(
        setup_wizard,
        "_read_clipboard",
        lambda: (
            "AUTH0_DOMAIN=dev-example.eu.auth0.com\n"
            "AUTH0_CLIENT_ID=client123\n"
            "AUTH0_CLIENT_SECRET=real-secret\n"
        ),
    )
    monkeypatch.setattr(setup_wizard.Prompt, "ask", lambda *args, **kwargs: "1")

    values = setup_wizard._ask_auth0_application_values()

    assert values["AUTH0_CLIENT_SECRET"] == "real-secret"


def test_local_setup_writes_runnable_loopback_configuration(tmp_path, monkeypatch):
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(setup_wizard, "ask_workspace_dir", lambda: workspace)
    monkeypatch.setattr(
        setup_wizard,
        "ask_networking",
        lambda: setup_wizard.NetworkConfig("Local-only test", "http://127.0.0.1:8765", 8765, False),
    )
    monkeypatch.setattr(setup_wizard, "_show_summary", lambda *args, **kwargs: None)

    setup_wizard.main()

    contents = (tmp_path / ".env").read_text()
    assert "HOST=127.0.0.1" in contents
    assert "MCP_BASE_URL=http://127.0.0.1:8765" in contents
    assert "ALLOW_INSECURE_NO_AUTH=true" in contents


def test_skipped_remote_auth_can_switch_to_safe_local_mode(tmp_path, monkeypatch):
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(setup_wizard, "ask_workspace_dir", lambda: workspace)
    monkeypatch.setattr(
        setup_wizard,
        "ask_networking",
        lambda: setup_wizard.NetworkConfig("ngrok", "https://demo.ngrok-free.app", 8765, True),
    )
    monkeypatch.setattr(setup_wizard, "ask_auth0", lambda audience: None)
    monkeypatch.setattr(setup_wizard.Confirm, "ask", lambda *args, **kwargs: True)
    monkeypatch.setattr(setup_wizard, "_show_summary", lambda *args, **kwargs: None)

    setup_wizard.main()

    contents = (tmp_path / ".env").read_text()
    assert "MCP_BASE_URL=http://127.0.0.1:8765" in contents
    assert "ALLOW_INSECURE_NO_AUTH=true" in contents


def test_skipped_remote_auth_can_exit_without_changing_existing_env(tmp_path, monkeypatch):
    env_path = tmp_path / ".env"
    env_path.write_text("KEEP=1\n")
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(setup_wizard, "ask_workspace_dir", lambda: workspace)
    monkeypatch.setattr(
        setup_wizard,
        "ask_networking",
        lambda: setup_wizard.NetworkConfig("remote", "https://mcp.example.com", 8765, True),
    )
    monkeypatch.setattr(setup_wizard, "ask_auth0", lambda audience: None)
    monkeypatch.setattr(setup_wizard.Confirm, "ask", lambda *args, **kwargs: False)

    setup_wizard.main()

    assert env_path.read_text() == "KEEP=1\n"


def test_server_command_prefers_active_python_environment(tmp_path, monkeypatch):
    executable = tmp_path / "bin" / "python"
    command = executable.parent / "universal-host-manager-mcp"
    command.parent.mkdir()
    command.touch()
    monkeypatch.setattr(setup_wizard.sys, "executable", str(executable))

    assert setup_wizard._server_command() == str(command)


def test_server_loads_env_from_launch_directory(tmp_path):
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    (tmp_path / ".env").write_text(
        "HOST=127.0.0.1\n"
        "PORT=9876\n"
        f"MCP_WORKSPACE_DIR={workspace}\n"
        "ALLOW_INSECURE_NO_AUTH=true\n"
    )
    env = os.environ.copy()
    for key in (
        "HOST",
        "PORT",
        "MCP_WORKSPACE_DIR",
        "ALLOW_INSECURE_NO_AUTH",
        "AUTH0_DOMAIN",
        "AUTH0_CLIENT_ID",
        "AUTH0_CLIENT_SECRET",
        "AUTH0_AUDIENCE",
    ):
        env.pop(key, None)
    result = subprocess.run(
        [sys.executable, "-c", "from universal_host_manager_mcp import server; print(server.PORT)"],
        cwd=tmp_path,
        env=env,
        capture_output=True,
        text=True,
        timeout=20,
        check=False,
    )
    assert result.returncode == 0, result.stderr
    assert result.stdout.strip() == "9876"


def test_autostart_script_is_executable_and_summary_uses_one_command(tmp_path, monkeypatch):
    monkeypatch.setattr(setup_wizard, "_server_command", lambda: "/venv/bin/universal-host-manager-mcp")
    network = setup_wizard.NetworkConfig(
        "ngrok static domain", "https://demo.ngrok-free.dev", 8700, True,
        autostart_target="linux",
    )
    path = setup_wizard._write_autostart_script(tmp_path / ".env", network, "demo.ngrok-free.dev")
    assert path.name == "uhm-enable-autostart.sh"
    assert path.stat().st_mode & 0o100
    contents = path.read_text()
    assert contents.startswith("#!/bin/sh")
    assert "universal-host-manager-ngrok.service" in contents


def test_macos_permission_steps_reference_exact_path_and_full_disk_access():
    steps = setup_wizard._macos_permission_steps("/opt/venv/bin/universal-host-manager-mcp")
    guidance = "\n".join(steps)

    assert "/opt/venv/bin/universal-host-manager-mcp" in guidance
    assert "Full Disk Access" in guidance
    assert "Automation" in guidance
    assert "new path to macOS" in guidance


def test_macos_privacy_settings_prompt_declined_does_not_call_open(monkeypatch):
    monkeypatch.setattr(setup_wizard.Confirm, "ask", lambda *a, **k: False)
    calls = []
    monkeypatch.setattr(setup_wizard.subprocess, "run", lambda *a, **k: calls.append(a))
    setup_wizard._offer_to_open_macos_privacy_settings()
    assert calls == []


def test_macos_privacy_settings_prompt_accepted_opens_full_disk_access_pane(monkeypatch):
    monkeypatch.setattr(setup_wizard.Confirm, "ask", lambda *a, **k: True)
    calls = []
    monkeypatch.setattr(setup_wizard.subprocess, "run", lambda *a, **k: calls.append(a[0]))
    setup_wizard._offer_to_open_macos_privacy_settings()
    assert len(calls) == 1
    assert calls[0] == [
        "open",
        "x-apple.systempreferences:com.apple.preference.security?Privacy_AllFiles",
    ]


def test_workspace_readiness_probe_reads_writes_and_cleans_up(tmp_path):
    passed, details = setup_wizard._test_workspace_access(tmp_path)

    assert passed is True
    assert "Read, write, and delete" in details
    assert list(tmp_path.iterdir()) == []


def test_macos_readiness_declined_stops_before_capability_questions(
    tmp_path, monkeypatch
):
    monkeypatch.setattr(setup_wizard.Confirm, "ask", lambda *a, **k: False)
    called = []
    monkeypatch.setattr(
        setup_wizard,
        "_ask_macos_readiness_capabilities",
        lambda: called.append(True),
    )

    assert setup_wizard._run_macos_readiness_test(
        tmp_path, "/venv/bin/universal-host-manager-mcp"
    ) is None
    assert called == []


def test_macos_capabilities_are_asked_separately(monkeypatch):
    answers = iter((True, True, False, True, False))
    prompts = []

    def answer(prompt, **kwargs):
        prompts.append(prompt)
        return next(answers)

    monkeypatch.setattr(setup_wizard.Confirm, "ask", answer)

    selected = setup_wizard._ask_macos_readiness_capabilities()

    assert selected == {
        "workspace": True,
        "full_disk_access": True,
        "chrome_automation": False,
        "accessibility": True,
        "screen_recording": False,
    }
    assert len(prompts) == 5


def test_open_macos_privacy_pane_uses_requested_panel(monkeypatch):
    calls = []

    def fake_run(args, **kwargs):
        calls.append(args)
        return subprocess.CompletedProcess(args, 0)

    monkeypatch.setattr(setup_wizard.subprocess, "run", fake_run)

    assert setup_wizard._open_macos_privacy_pane("accessibility") is True
    assert calls[0][-1].endswith("Privacy_Accessibility")


def test_chrome_automation_uses_read_only_apple_event(monkeypatch):
    calls = []

    def fake_run(args, **kwargs):
        calls.append(args)
        return subprocess.CompletedProcess(args, 0, stdout="Google", stderr="")

    monkeypatch.setattr(setup_wizard.subprocess, "run", fake_run)

    passed, details = setup_wizard._test_chrome_automation(
        "/venv/bin/universal-host-manager-mcp"
    )

    assert passed is True
    assert "read-only" in details
    assert calls[0] == ["open", "-Ra", "Google Chrome"]
    assert calls[1][0:2] == ["osascript", "-e"]


def test_readiness_runs_only_selected_capabilities(tmp_path, monkeypatch):
    monkeypatch.setattr(setup_wizard.Confirm, "ask", lambda *a, **k: True)
    monkeypatch.setattr(
        setup_wizard,
        "_ask_macos_readiness_capabilities",
        lambda: {
            "workspace": True,
            "full_disk_access": False,
            "chrome_automation": False,
            "accessibility": False,
            "screen_recording": False,
        },
    )
    monkeypatch.setattr(
        setup_wizard,
        "_test_workspace_access",
        lambda workspace: (True, "ok"),
    )
    captured = []
    monkeypatch.setattr(
        setup_wizard,
        "_show_macos_readiness_report",
        lambda results: captured.extend(results) or True,
    )

    assert setup_wizard._run_macos_readiness_test(
        tmp_path, "/venv/bin/universal-host-manager-mcp"
    ) is True
    assert captured == [("Workspace files", True, "ok")]
