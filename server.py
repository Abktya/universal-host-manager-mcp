"""Universal Host Manager MCP Server.

A cross-platform (Linux/macOS) FastMCP server for authenticated remote host
administration. This server exposes powerful shell and file-management tools;
read SECURITY.md and run it only as an unprivileged, dedicated OS user.
"""

from __future__ import annotations

import logging
import os
import platform
import subprocess
from functools import wraps
from pathlib import Path
from typing import Callable, ParamSpec, TypeVar

from dotenv import load_dotenv
from fastmcp import FastMCP
from fastmcp.server.auth.providers.auth0 import Auth0Provider

load_dotenv()

logging.basicConfig(
    level=os.getenv("LOG_LEVEL", "INFO").upper(),
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger("universal-host-manager")

HOST = os.getenv("HOST", "127.0.0.1")
PORT = int(os.getenv("PORT", "8765"))
BASE_URL = os.getenv("MCP_BASE_URL", f"http://localhost:{PORT}").rstrip("/")
WORKSPACE_ROOT = Path(os.getenv("MCP_WORKSPACE_DIR", Path.home())).expanduser().resolve()

MAX_OUTPUT_CHARS = int(os.getenv("MAX_OUTPUT_CHARS", "64000"))
DEFAULT_CMD_TIMEOUT = int(os.getenv("DEFAULT_CMD_TIMEOUT", "300"))
MAX_CMD_TIMEOUT = int(os.getenv("MAX_CMD_TIMEOUT", "1800"))
MAX_READ_BYTES = int(os.getenv("MAX_READ_BYTES", "5000000"))
ALLOW_INSECURE_NO_AUTH = os.getenv("ALLOW_INSECURE_NO_AUTH", "false").lower() in {
    "1", "true", "yes",
}

AUTH0_DOMAIN = os.getenv("AUTH0_DOMAIN")
AUTH0_CLIENT_ID = os.getenv("AUTH0_CLIENT_ID")
AUTH0_CLIENT_SECRET = os.getenv("AUTH0_CLIENT_SECRET")
AUTH0_AUDIENCE = os.getenv("AUTH0_AUDIENCE")

auth_values = [AUTH0_DOMAIN, AUTH0_CLIENT_ID, AUTH0_CLIENT_SECRET, AUTH0_AUDIENCE]
if all(auth_values):
    auth = Auth0Provider(
        config_url=f"https://{AUTH0_DOMAIN}/.well-known/openid-configuration",
        client_id=AUTH0_CLIENT_ID,
        client_secret=AUTH0_CLIENT_SECRET,
        audience=AUTH0_AUDIENCE,
        base_url=BASE_URL,
        allowed_client_redirect_uris=[
            "https://claude.ai/api/mcp/auth_callback",
            "https://claude.com/api/mcp/auth_callback",
            "https://chatgpt.com/connector/oauth/*",
            "https://antigravity.google/oauth-callback",
            "http://localhost:*",
            "http://127.0.0.1:*",
        ],
    )
elif any(auth_values):
    raise RuntimeError(
        "Incomplete Auth0 configuration. Set AUTH0_DOMAIN, AUTH0_CLIENT_ID, "
        "AUTH0_CLIENT_SECRET and AUTH0_AUDIENCE."
    )
elif ALLOW_INSECURE_NO_AUTH:
    auth = None
    logger.warning("Authentication is disabled by ALLOW_INSECURE_NO_AUTH=true.")
else:
    raise RuntimeError(
        "Auth0 configuration is missing. Refusing to start without authentication. "
        "For local-only development, explicitly set ALLOW_INSECURE_NO_AUTH=true."
    )

mcp = FastMCP("Universal Host Manager", auth=auth)

P = ParamSpec("P")
R = TypeVar("R")


def _truncate(text: str, limit: int = MAX_OUTPUT_CHARS) -> str:
    if len(text) <= limit:
        return text
    half = limit // 2
    omitted = len(text) - (half * 2)
    return f"{text[:half]}\n\n... [truncated {omitted} chars] ...\n\n{text[-half:]}"


def _validate_path(target_path: str) -> Path:
    candidate = Path(target_path).expanduser()
    if not candidate.is_absolute():
        candidate = WORKSPACE_ROOT / candidate
    resolved = candidate.resolve()
    if resolved != WORKSPACE_ROOT and WORKSPACE_ROOT not in resolved.parents:
        raise PermissionError(f"Path must be inside {WORKSPACE_ROOT}")
    return resolved


def _run(command: str, timeout: int = DEFAULT_CMD_TIMEOUT) -> str:
    timeout = max(1, min(timeout, MAX_CMD_TIMEOUT))
    try:
        result = subprocess.run(
            command,
            shell=True,
            capture_output=True,
            text=True,
            timeout=timeout,
            cwd=WORKSPACE_ROOT,
            errors="replace",
        )
    except subprocess.TimeoutExpired as exc:
        stdout = exc.stdout or ""
        stderr = exc.stderr or ""
        if isinstance(stdout, bytes):
            stdout = stdout.decode(errors="replace")
        if isinstance(stderr, bytes):
            stderr = stderr.decode(errors="replace")
        return _truncate(
            f"[ERROR] Command timed out after {timeout}s\n"
            f"--- partial output ---\n{(stdout + stderr).strip() or '(none)'}"
        )
    except Exception as exc:
        logger.exception("Command execution failed")
        return f"[ERROR] Execution failed: {type(exc).__name__}: {exc}"

    output = (result.stdout + result.stderr).strip() or "(no output)"
    if result.returncode:
        output = f"[exit={result.returncode}]\n{output}"
    return _truncate(output)


def safe_tool(fn: Callable[P, R]) -> Callable[P, R | str]:
    @wraps(fn)
    def wrapper(*args: P.args, **kwargs: P.kwargs) -> R | str:
        try:
            return fn(*args, **kwargs)
        except Exception as exc:
            logger.exception("Tool execution failed: %s", fn.__name__)
            return f"[ERROR] {fn.__name__} failed: {type(exc).__name__}: {exc}"

    return wrapper


@mcp.tool()
@safe_tool
def run_command(command: str, timeout: int = DEFAULT_CMD_TIMEOUT) -> str:
    """Run an arbitrary shell command with WORKSPACE_ROOT as its working directory.

    Warning: the working directory is not an OS sandbox. Absolute paths, shell
    redirection and invoked programs may access anything permitted to the server's
    OS user.
    """
    logger.info("[TOOL] run_command timeout=%ss command=%r", timeout, command[:150])
    return _run(command, timeout)


@mcp.tool()
@safe_tool
def read_file(path: str) -> str:
    """Read a text file located inside the configured workspace."""
    target = _validate_path(path)
    if not target.exists():
        return f"[ERROR] File not found: {path}"
    if not target.is_file():
        return f"[ERROR] Not a regular file: {path}"
    if target.stat().st_size > MAX_READ_BYTES:
        return f"[ERROR] File exceeds MAX_READ_BYTES ({MAX_READ_BYTES})."

    raw = target.read_bytes()
    try:
        text = raw.decode("utf-8")
    except UnicodeDecodeError:
        text = raw.decode("latin-1", errors="replace")
    return _truncate(text)


@mcp.tool()
@safe_tool
def write_file(path: str, content: str) -> str:
    """Write UTF-8 text inside the configured workspace."""
    target = _validate_path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(content, encoding="utf-8")
    return f"Wrote {len(content)} characters to {target}"


@mcp.tool()
@safe_tool
def list_dir(path: str = ".") -> str:
    """List a directory located inside the configured workspace."""
    target = _validate_path(path)
    if not target.exists():
        return f"[ERROR] Path not found: {path}"
    if not target.is_dir():
        return f"[ERROR] Not a directory: {path}"
    entries = sorted(item.name + ("/" if item.is_dir() else "") for item in target.iterdir())
    return _truncate("\n".join(entries) or "(empty directory)")


@mcp.tool()
@safe_tool
def system_metrics() -> str:
    """Return disk, memory and top-process information for Linux or macOS."""
    current_os = platform.system().lower()
    disk = _run("df -h .")
    if current_os == "darwin":
        memory = _run("vm_stat | head -10")
        processes = _run("ps -A -o %cpu,%mem,comm | sort -nr | head -n 10")
    elif current_os == "linux":
        memory = _run("free -h")
        processes = _run("ps aux --sort=-%mem | head -15")
    else:
        return f"[ERROR] Unsupported operating system: {platform.system()}"

    return (
        f"--- DISK USAGE ---\n{disk}\n\n"
        f"--- MEMORY STATUS ---\n{memory}\n\n"
        f"--- TOP PROCESSES ---\n{processes}"
    )


if __name__ == "__main__":
    logger.info(
        "Starting Universal Host Manager on %s:%s (OS=%s, workspace=%s)",
        HOST,
        PORT,
        platform.system(),
        WORKSPACE_ROOT,
    )
    mcp.run(transport="streamable-http", host=HOST, port=PORT)
