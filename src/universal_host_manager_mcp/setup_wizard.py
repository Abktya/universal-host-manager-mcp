"""Interactive setup wizard for Universal Host Manager MCP.

Walks through workspace selection, network exposure method, and Auth0
credentials, then writes a ready-to-use .env file. Run with:

    uhm-setup
"""

from __future__ import annotations

import os
import shutil
import stat
import urllib.error
import urllib.request
from pathlib import Path
from typing import Optional

from rich.console import Console
from rich.panel import Panel
from rich.prompt import Confirm, IntPrompt, Prompt

console = Console()

_DANGEROUS_PATHS = {"/", "/root", "/etc", "/usr", "/bin", "/sbin", "/var", "/home"}


def _is_dangerous(path: Path) -> bool:
    return str(path) in _DANGEROUS_PATHS or path == Path.home()


def ask_workspace_dir() -> Path:
    """Prompt for MCP_WORKSPACE_DIR, offering to create it and refusing
    broad system/home paths without an explicit confirmation."""
    while True:
        raw = Prompt.ask(
            "[bold]Workspace directory[/bold] "
            "(read_file/write_file/list_dir will be restricted to this)",
            default=str(Path.home() / "workspace"),
        )
        path = Path(raw).expanduser()

        if _is_dangerous(path):
            console.print(
                f"[yellow]'{path}' is a broad system or home directory.[/yellow]"
            )
            if not Confirm.ask(
                "Are you sure you want the AI to have read/write access here?",
                default=False,
            ):
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


def ask_networking() -> tuple[str, int]:
    """Ask how the server will be reached over HTTPS and return
    (base_url, port). Prints the exact follow-up command to run for
    the chosen method."""
    console.print(Panel("How will MCP clients reach this server over HTTPS?", title="Networking"))
    console.print("  [bold]1[/bold] Cloudflare Tunnel (you own a domain)")
    console.print("  [bold]2[/bold] ngrok free static domain (no domain needed)")
    console.print("  [bold]3[/bold] I'll set this up myself / already have a URL")

    choice = Prompt.ask("Choose", choices=["1", "2", "3"], default="3")
    port = IntPrompt.ask("Local port for the server to listen on", default=8765)

    if choice == "1":
        hostname = Prompt.ask("The hostname you'll route the tunnel to, e.g. mcp.example.com").strip()
        console.print(
            "\nAfter this wizard finishes, run:\n"
            "  [cyan]cloudflared tunnel login[/cyan]\n"
            "  [cyan]cloudflared tunnel create universal-host-manager-mcp[/cyan]\n"
            f"  [cyan]cloudflared tunnel route dns universal-host-manager-mcp {hostname}[/cyan]\n"
            f"then create ~/.cloudflared/config.yml pointing at http://127.0.0.1:{port}\n"
            "(see the README's Cloudflare Tunnel section for the full config).\n"
        )
        base_url = f"https://{hostname}"

    elif choice == "2":
        subdomain = Prompt.ask("Your ngrok static domain, e.g. your-name.ngrok-free.app").strip()
        console.print(
            "\nClaim the static domain first at https://dashboard.ngrok.com/domains if you haven't.\n"
            "After this wizard finishes, run:\n"
            "  [cyan]ngrok config add-authtoken <your-token>[/cyan]  (from your ngrok dashboard)\n"
            f"  [cyan]ngrok http --url={subdomain} {port}[/cyan]\n"
        )
        base_url = f"https://{subdomain}"

    else:
        base_url = Prompt.ask("Public HTTPS base URL clients will use (no trailing slash, no /mcp)").strip()

    base_url = base_url.rstrip("/")
    if not base_url.startswith("https://"):
        if not Confirm.ask(
            f"[yellow]'{base_url}' doesn't start with https:// — Auth0 requires HTTPS. "
            "Continue anyway?[/yellow]",
            default=False,
        ):
            return ask_networking()

    return base_url, port


def _check_auth0_domain(domain: str) -> bool:
    url = f"https://{domain}/.well-known/openid-configuration"
    try:
        with urllib.request.urlopen(url, timeout=5) as resp:  # noqa: S310
            return resp.status == 200
    except Exception:
        return False


def ask_auth0(default_audience: str) -> Optional[dict]:
    """Prompt for Auth0 credentials, verifying the tenant domain is
    reachable. Returns None if the user opts to skip Auth0 for now."""
    console.print(
        Panel(
            "Create an API + a Regular Web Application in Auth0 first if you haven't "
            "(see the README's Auth0 setup section). You'll need the tenant domain, "
            "client ID and client secret from there.",
            title="Auth0",
        )
    )

    if not Confirm.ask("Do you have an Auth0 application ready?", default=True):
        console.print(
            "[yellow]Skipping Auth0 for now.[/yellow] Run this wizard again once you have it, "
            "or set ALLOW_INSECURE_NO_AUTH=true for local-only testing "
            "(never on a publicly reachable endpoint)."
        )
        return None

    while True:
        domain = Prompt.ask("AUTH0_DOMAIN (e.g. your-tenant.eu.auth0.com)").strip()
        with console.status(f"Checking {domain}..."):
            ok = _check_auth0_domain(domain)
        if ok:
            console.print(f"[green]\u2713 {domain} looks reachable.[/green]")
            break
        if Confirm.ask(f"[yellow]Couldn't reach {domain} \u2014 use it anyway?[/yellow]", default=False):
            break

    client_id = Prompt.ask("AUTH0_CLIENT_ID").strip()
    client_secret = Prompt.ask("AUTH0_CLIENT_SECRET", password=True).strip()
    audience = Prompt.ask("AUTH0_AUDIENCE", default=default_audience).strip()

    return {
        "AUTH0_DOMAIN": domain,
        "AUTH0_CLIENT_ID": client_id,
        "AUTH0_CLIENT_SECRET": client_secret,
        "AUTH0_AUDIENCE": audience,
    }


def write_env(path: Path, values: dict) -> None:
    """Write values as a .env file, backing up any existing one and
    restricting permissions to the owner only."""
    if path.exists():
        backup = path.with_suffix(path.suffix + ".bak")
        shutil.copy2(path, backup)
        console.print(f"[dim]Existing .env backed up to {backup}[/dim]")

    lines = [f"{key}={value}" for key, value in values.items()]
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    os.chmod(path, stat.S_IRUSR | stat.S_IWUSR)  # 600, owner read/write only


def main() -> None:
    console.print(
        Panel.fit(
            "[bold]Universal Host Manager MCP \u2014 setup wizard[/bold]\n"
            "This will generate a .env file in the current directory.",
        )
    )

    workspace = ask_workspace_dir()
    base_url, port = ask_networking()
    default_audience = base_url + "/"
    auth0 = ask_auth0(default_audience)

    values = {
        "HOST": "127.0.0.1",
        "PORT": str(port),
        "MCP_BASE_URL": base_url,
        "MCP_WORKSPACE_DIR": str(workspace),
    }
    if auth0:
        values.update(auth0)
    else:
        values["ALLOW_INSECURE_NO_AUTH"] = "false"

    env_path = Path.cwd() / ".env"
    write_env(env_path, values)

    console.print(
        Panel.fit(
            f"[bold green]Done![/bold green] Wrote {env_path}\n\n"
            "Next steps:\n"
            "  1. Start the tunnel command shown above, if applicable.\n"
            "  2. Run: [cyan]universal-host-manager-mcp[/cyan]\n"
            f"  3. Your MCP endpoint will be: [cyan]{base_url}/mcp[/cyan]",
        )
    )


if __name__ == "__main__":
    main()
