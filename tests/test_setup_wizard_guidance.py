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
    assert (
        setup_wizard._validate_hostname("demo.ngrok-free.app", ngrok=True)
        == "demo.ngrok-free.app"
    )
    with pytest.raises(ValueError):
        setup_wizard._validate_hostname("test.example.com", ngrok=True)


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
