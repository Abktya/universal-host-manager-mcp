"""Beginner-friendly setup wizard for Universal Host Manager MCP."""

from __future__ import annotations

import os
import re
import shlex
import shutil
import stat
import subprocess
import sys
import urllib.request
from dataclasses import dataclass
from pathlib import Path
from typing import Optional
from urllib.parse import urlparse

from rich.console import Console
from rich.panel import Panel
from rich.prompt import Confirm, Prompt
from rich.table import Table

console = Console()

_DANGEROUS_PATHS = {"/", "/root", "/etc", "/usr", "/bin", "/sbin", "/var", "/home"}
_HOST_LABEL = re.compile(r"^[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?$", re.IGNORECASE)


@dataclass(frozen=True)
class NetworkConfig:
    """Validated networking choices used to generate the final configuration."""

    mode: str
    base_url: str
    port: int
    remote: bool
    follow_up: tuple[str, ...] = ()


def _is_dangerous(path: Path) -> bool:
    return str(path) in _DANGEROUS_PATHS or path == Path.home()


def _validate_hostname(value: str, *, ngrok: bool = False) -> str:
    hostname = value.strip().lower().rstrip(".")
    if not hostname:
        raise ValueError("Enter a hostname, for example mcp.example.com.")
    if "://" in hostname:
        raise ValueError("Enter only the hostname, without https:// or a path.")
    if any(char in hostname for char in "/?#:@") or any(char.isspace() for char in hostname):
        raise ValueError("A hostname cannot contain a path, port, spaces, or URL parameters.")
    if "." not in hostname:
        raise ValueError("Enter a complete hostname containing a dot, not a short name such as 'test'.")
    if len(hostname) > 253 or any(not _HOST_LABEL.fullmatch(label) for label in hostname.split(".")):
        raise ValueError("That hostname is not valid. Example: mcp.example.com")
    if ngrok and not hostname.endswith(
        (".ngrok-free.dev", ".ngrok-free.app", ".ngrok.dev", ".ngrok.app")
    ):
        raise ValueError(
            "Enter the dev/static domain shown in your ngrok dashboard, such as name.ngrok-free.dev."
        )
    return hostname


def _validate_https_base_url(value: str) -> str:
    base_url = value.strip().rstrip("/")
    parsed = urlparse(base_url)
    if parsed.scheme != "https":
        raise ValueError("The public URL must start with https://.")
    if not parsed.hostname:
        raise ValueError("Enter a complete URL, for example https://mcp.example.com.")
    if parsed.username or parsed.password or parsed.query or parsed.fragment:
        raise ValueError("Do not include credentials, query parameters, or fragments in the URL.")
    if parsed.path not in ("", "/"):
        raise ValueError("Enter only the base URL; do not add /mcp or another path.")
    if "." not in parsed.hostname:
        raise ValueError("Use a complete public hostname, not a short name such as 'test'.")
    try:
        _ = parsed.port
    except ValueError as exc:
        raise ValueError("The URL contains an invalid port.") from exc
    return base_url


def _ask_port() -> int:
    console.print("The local port is a number. [bold]Press Enter[/bold] to accept 8765; do not type y/n.")
    while True:
        raw = Prompt.ask("Local port for the server", default="8765").strip()
        try:
            port = int(raw)
        except ValueError:
            console.print("[red]Please enter a number between 1 and 65535.[/red]")
            continue
        if 1 <= port <= 65535:
            return port
        console.print("[red]Port must be between 1 and 65535.[/red]")


def _ask_hostname(prompt: str, *, ngrok: bool = False) -> str:
    while True:
        try:
            return _validate_hostname(Prompt.ask(prompt), ngrok=ngrok)
        except ValueError as exc:
            console.print(f"[red]{exc}[/red]")


def _ask_https_base_url() -> str:
    while True:
        try:
            return _validate_https_base_url(Prompt.ask("Public HTTPS base URL (for example https://mcp.example.com; do not add /mcp)"))
        except ValueError as exc:
            console.print(f"[red]{exc}[/red]")


def _ask_required(prompt: str, *, password: bool = False, default: Optional[str] = None) -> str:
    """Ask until a non-empty value is entered."""
    while True:
        value = Prompt.ask(prompt, password=password, default=default).strip()
        if value:
            return value
        console.print("[red]This value cannot be empty.[/red]")


def _parse_auth0_env_block(text: str) -> dict[str, str]:
    """Extract and validate Auth0 application values from a copied .env block."""
    values: dict[str, str] = {}
    for raw_line in text.splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        if line.startswith("export "):
            line = line[7:].lstrip()
        if "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        if key not in {"AUTH0_DOMAIN", "AUTH0_CLIENT_ID", "AUTH0_CLIENT_SECRET"}:
            continue
        values[key] = value.strip().strip('"').strip("'")

    missing = [
        key for key in ("AUTH0_DOMAIN", "AUTH0_CLIENT_ID", "AUTH0_CLIENT_SECRET")
        if not values.get(key)
    ]
    if missing:
        raise ValueError("Missing required value(s): " + ", ".join(missing))

    secret = values["AUTH0_CLIENT_SECRET"]
    if "MASKED" in secret.upper() or "*" in secret:
        raise ValueError(
            "AUTH0_CLIENT_SECRET is masked. In Auth0, reveal/copy the real Client Secret "
            "from Application > Settings and try again."
        )

    values["AUTH0_DOMAIN"] = _validate_hostname(values["AUTH0_DOMAIN"])
    return values


def _read_clipboard() -> str:
    """Read text from a supported desktop clipboard without displaying secrets."""
    commands = (
        ("pbpaste",),
        ("wl-paste", "--no-newline"),
        ("xclip", "-selection", "clipboard", "-o"),
        ("xsel", "--clipboard", "--output"),
    )
    for command in commands:
        if not shutil.which(command[0]):
            continue
        result = subprocess.run(
            command,
            capture_output=True,
            text=True,
            timeout=5,
            check=False,
        )
        if result.returncode == 0 and result.stdout.strip():
            return result.stdout
    raise RuntimeError(
        "Clipboard reading is unavailable. Choose the paste or manual-entry option instead."
    )


def _ask_auth0_application_values() -> dict[str, str]:
    """Collect Auth0 application values by clipboard, block paste, or manual entry."""
    console.print("  [bold]1[/bold] Read the copied Auth0 .env block from clipboard [green](recommended)[/green]")
    console.print("  [bold]2[/bold] Paste the Auth0 .env block in the terminal")
    console.print("  [bold]3[/bold] Enter Domain, Client ID, and Client Secret separately")

    while True:
        choice = Prompt.ask("How would you like to add the Auth0 values?", choices=["1", "2", "3"], default="1")
        if choice == "3":
            domain = _ask_hostname("AUTH0_DOMAIN (for example your-tenant.eu.auth0.com)")
            return {
                "AUTH0_DOMAIN": domain,
                "AUTH0_CLIENT_ID": _ask_required("AUTH0_CLIENT_ID (Application Settings > Client ID)"),
                "AUTH0_CLIENT_SECRET": _ask_required(
                    "AUTH0_CLIENT_SECRET (Application Settings > Client Secret)",
                    password=True,
                ),
            }

        if choice == "1":
            try:
                block = _read_clipboard()
            except RuntimeError as exc:
                console.print(f"[red]{exc}[/red]")
                continue
        else:
            console.print(
                "Paste the complete block below. On a new line, type [bold]END[/bold] and press Enter."
            )
            lines: list[str] = []
            while True:
                line = console.input()
                if line.strip().upper() == "END":
                    break
                lines.append(line)
            block = "\n".join(lines)

        try:
            values = _parse_auth0_env_block(block)
        except ValueError as exc:
            console.print(f"[red]{exc}[/red]")
            console.print("Copy the block again, or choose option 3 to enter the values manually.")
            continue

        console.print("[green]✓ Auth0 Domain, Client ID, and Client Secret were imported.[/green]")
        return values


def ask_workspace_dir() -> Path:
    console.print(Panel(
        "Choose the folder the AI should work in. The built-in file tools cannot leave this folder.\n\n"
        "[yellow]Important:[/yellow] shell commands are not sandboxed; they keep the permissions of your "
        "macOS/Linux user. For a first test, use a new empty folder.", title="Workspace"))
    while True:
        path = Path(Prompt.ask("Workspace directory", default=str(Path.cwd() / "workspace"))).expanduser()
        if _is_dangerous(path):
            console.print(f"[yellow]'{path}' is a broad system or home directory.[/yellow]")
            if not Confirm.ask("Are you sure the AI should have read/write access here?", default=False):
                continue
        if not path.exists():
            if Confirm.ask(f"'{path}' doesn't exist. Create it?", default=True):
                path.mkdir(parents=True, exist_ok=True)
            else:
                continue
        elif not path.is_dir():
            console.print(f"[red]'{path}' exists and is not a directory.[/red]")
            continue
        return path.resolve()


def ask_networking() -> NetworkConfig:
    console.print(Panel(
        "Choose [bold]Local-only test[/bold] for your first installation. It needs no domain, tunnel, "
        "or Auth0 account and is reachable only from this computer.\n\n"
        "Remote options require a real HTTPS address and Auth0 authentication.",
        title="How will you use the server?"))
    console.print("  [bold]1[/bold] Local-only test [green](recommended for first-time users)[/green]")
    console.print("  [bold]2[/bold] Remote access with Cloudflare Tunnel (you own a domain)")
    console.print("  [bold]3[/bold] Remote access with an ngrok static domain")
    console.print("  [bold]4[/bold] Remote access with an HTTPS URL you already manage")
    choice = Prompt.ask("Choose", choices=["1", "2", "3", "4"], default="1")
    port = _ask_port()
    if choice == "1":
        return NetworkConfig("Local-only test", f"http://127.0.0.1:{port}", port, False)
    if choice == "2":
        hostname = _ask_hostname("Public hostname routed through Cloudflare (for example mcp.example.com)")
        return NetworkConfig("Cloudflare Tunnel", f"https://{hostname}", port, True, (
            "cloudflared tunnel login", "cloudflared tunnel create universal-host-manager-mcp",
            f"cloudflared tunnel route dns universal-host-manager-mcp {hostname}",
            "Create ~/.cloudflared/config.yml using the README example, then run:",
            "cloudflared tunnel run universal-host-manager-mcp"))
    if choice == "3":
        console.print("Claim a free static domain first at [link=https://dashboard.ngrok.com/domains]https://dashboard.ngrok.com/domains[/link]. Do not enter a made-up name.")
        hostname = _ask_hostname(
            "Your ngrok dev/static domain (for example your-name.ngrok-free.dev)", ngrok=True
        )
        return NetworkConfig("ngrok static domain", f"https://{hostname}", port, True, (
            "ngrok config add-authtoken <your-token>", f"ngrok http --url={hostname} {port}"))
    return NetworkConfig("Existing HTTPS URL", _ask_https_base_url(), port, True)


def _check_auth0_domain(domain: str) -> bool:
    try:
        with urllib.request.urlopen(f"https://{domain}/.well-known/openid-configuration", timeout=5) as response:  # noqa: S310
            return response.status == 200
    except Exception:
        return False


def _auth0_settings(public_origin: str) -> tuple[tuple[str, str], ...]:
    """Return the exact Auth0 dashboard values for this FastMCP deployment."""
    origin = public_origin.rstrip("/")
    return (
        ("Application Ownership", "First-party"),
        ("Application Type", "Regular Web Application"),
        ("Application Login URI", "Leave blank"),
        ("Allowed Callback URLs", f"{origin}/auth/callback"),
        ("Allowed Logout URLs", origin),
        ("Allowed Web Origins", origin),
        ("Allowed Origins (CORS)", origin),
        ("Allow Cross-Origin Authentication", "Off / disabled"),
        ("Cross-Origin Verification Fallback URL", "Leave blank"),
        ("API Identifier / Audience", f"{origin}/"),
        ("Signing Algorithm", "RS256"),
        ("MCP endpoint (for AI clients)", f"{origin}/mcp"),
    )


def _show_auth0_settings(public_origin: str) -> None:
    table = Table(title="Values to enter in Auth0", show_header=True, header_style="bold cyan")
    table.add_column("Auth0 field", style="bold")
    table.add_column("Value", overflow="fold")
    for field, value in _auth0_settings(public_origin):
        table.add_row(field, value)
    console.print(table)


def ask_auth0(default_audience: str) -> Optional[dict[str, str]]:
    public_origin = default_audience.rstrip("/")
    console.print(Panel(
        "1. Open [link=https://auth0.com/]https://auth0.com/[/link], create an account, and open Dashboard.\n"
        "2. Go to [bold]Applications > APIs > Create API[/bold]. Give it a name and use the suggested "
        "audience shown below as its Identifier.\n"
        "3. Go to [bold]Applications > Applications > Create Application[/bold], choose "
        "[bold]Regular Web Application[/bold].\n"
        "4. On Auth0's [bold]Integrate into your application[/bold] page, click [bold]Copy[/bold] "
        "above the .env block. The wizard can read it directly from your clipboard.\n"
        "5. If the secret says MASKED, open the application's [bold]Settings[/bold] page and copy "
        "the real Client Secret instead.\n"
        "6. In the application's [bold]Settings[/bold], enter the exact values shown below. "
        "Do not enter Claude, ChatGPT, or Grok callback URLs in Auth0; FastMCP handles those "
        "client redirects through the MCP registration flow.\n"
        "7. Click [bold]Save Changes[/bold] after entering the values.\n\n"
        "Auth0's AUTH0_SECRET, APP_BASE_URL and PORT quickstart values belong to its sample "
        "web application and are not used by this MCP server.\n\n"
        "Never publish the Client Secret or commit the generated .env file to Git.",
        title="Auth0 required for remote access"))
    _show_auth0_settings(public_origin)
    if not Confirm.ask("Do you have these Auth0 values ready?", default=False):
        return None
    application_values = _ask_auth0_application_values()
    domain = application_values["AUTH0_DOMAIN"]
    while True:
        with console.status(f"Checking {domain}..."):
            reachable = _check_auth0_domain(domain)
        if reachable:
            console.print(f"[green]✓ {domain} looks reachable.[/green]")
            break
        if Confirm.ask(f"[yellow]Couldn't verify {domain}. Use it anyway?[/yellow]", default=False):
            break
    audience = _ask_required(
        "AUTH0_AUDIENCE (API Settings > Identifier)", default=default_audience
    )
    return {**application_values, "AUTH0_AUDIENCE": audience}


def write_env(path: Path, values: dict[str, str]) -> None:
    if path.exists():
        backup = path.with_suffix(path.suffix + ".bak")
        shutil.copy2(path, backup)
        os.chmod(backup, stat.S_IRUSR | stat.S_IWUSR)
        console.print(f"[dim]Existing .env backed up to {backup}[/dim]")
    path.write_text("\n".join(f"{key}={value}" for key, value in values.items()) + "\n", encoding="utf-8")
    os.chmod(path, stat.S_IRUSR | stat.S_IWUSR)


def _server_command() -> str:
    candidate = Path(sys.executable).parent / "universal-host-manager-mcp"
    return str(candidate) if candidate.exists() else (shutil.which("universal-host-manager-mcp") or "universal-host-manager-mcp")


def _show_summary(env_path: Path, workspace: Path, network: NetworkConfig, *, auth_configured: bool) -> None:
    lines = ["[bold green]Setup complete[/bold green]", "", f"Mode: [cyan]{network.mode}[/cyan]",
             f"Configuration: [cyan]{env_path}[/cyan]", f"Workspace: [cyan]{workspace}[/cyan]",
             f"MCP endpoint: [cyan]{network.base_url}/mcp[/cyan]", "",
             "Start the server from this configuration directory:",
             f"  [cyan]cd {shlex.quote(str(env_path.parent))}[/cyan]",
             f"  [cyan]{shlex.quote(_server_command())}[/cyan]"]
    if not network.remote:
        lines += ["", "[yellow]Local test mode has no authentication, but HOST is fixed to 127.0.0.1 so other computers cannot connect.[/yellow]", "Press Ctrl+C to stop the server."]
    elif auth_configured:
        if network.follow_up:
            lines += ["", "Before connecting a remote client, complete these networking steps:"]
            lines += [f"  [cyan]{item}[/cyan]" for item in network.follow_up]
        lines += ["", "Then add the MCP endpoint above to ChatGPT, Claude, or another MCP client."]
    console.print(Panel.fit("\n".join(lines)))


def main() -> None:
    config_dir = Path.cwd().resolve()
    console.print(Panel.fit(
        "[bold]Universal Host Manager MCP — setup wizard[/bold]\n\n"
        "This wizard explains each choice and creates a protected .env file.\n"
        f"Configuration directory: [cyan]{config_dir}[/cyan]\n\n"
        "Run the server from this same directory so it can find the .env file."))
    workspace = ask_workspace_dir()
    network = ask_networking()
    auth0: Optional[dict[str, str]] = None
    if network.remote:
        auth0 = ask_auth0(network.base_url + "/")
        if auth0 is None:
            console.print("\n[yellow]Remote setup was not written because Auth0 is required.[/yellow]")
            if Confirm.ask("Configure a safe local-only test instead?", default=True):
                network = NetworkConfig("Local-only test", f"http://127.0.0.1:{network.port}", network.port, False)
            else:
                console.print("No configuration was changed. Run uhm-setup again when ready.")
                return
    values = {"HOST": "127.0.0.1", "PORT": str(network.port), "MCP_BASE_URL": network.base_url,
              "MCP_WORKSPACE_DIR": str(workspace),
              "ALLOW_INSECURE_NO_AUTH": "false" if network.remote else "true"}
    if auth0:
        values.update(auth0)
    env_path = config_dir / ".env"
    write_env(env_path, values)
    _show_summary(env_path, workspace, network, auth_configured=auth0 is not None)


if __name__ == "__main__":
    main()
