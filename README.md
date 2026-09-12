# Universal Host Manager MCP
<!-- mcp-name: io.github.Abktya/universal-host-manager-mcp -->

A cross-platform [Model Context Protocol](https://modelcontextprotocol.io/) server for administering a Linux or macOS host through MCP clients such as ChatGPT and Claude.

[![Abktya/universal-host-manager-mcp MCP server](https://glama.ai/mcp/servers/Abktya/universal-host-manager-mcp/badges/score.svg)](https://glama.ai/mcp/servers/Abktya/universal-host-manager-mcp)

It uses [FastMCP](https://gofastmcp.com/) Streamable HTTP transport, Auth0 OAuth, bounded file tools, output limits and command timeouts.

> [!CAUTION]
> This project exposes arbitrary shell execution. Authentication decides who may use it; it does not make commands harmless. Read [SECURITY.md](SECURITY.md) before deploying it.

## Features

- Linux and macOS support
- Streamable HTTP endpoint
- Auth0 OAuth integration
- File reads, writes and directory listings constrained to `MCP_WORKSPACE_DIR`
- Configurable command timeouts and output truncation
- File-size limits and decoding fallback
- Fail-closed startup when authentication is not configured
- Example systemd and launchd services

## Tools

| Tool | Parameters | Purpose |
| --- | --- | --- |
| `run_command` | `command: str`, `timeout: int` | Runs an arbitrary shell command with the workspace as its working directory |
| `read_file` | `path: str` | Reads a text file inside the workspace |
| `write_file` | `path: str`, `content: str` | Writes UTF-8 text inside the workspace |
| `list_dir` | `path: str = "."` | Lists a directory inside the workspace |
| `system_metrics` | none | Reports disk, memory and top-process information |

The workspace boundary applies to the file tools. It does **not** sandbox `run_command`; commands retain all permissions of the service's OS user.

## Requirements

- Python 3.10+
- Linux or macOS
- Auth0 account for remote use
- HTTPS endpoint for remote MCP clients

## Install

```bash
git clone https://github.com/Abktya/universal-host-manager-mcp.git
cd universal-host-manager-mcp
python3 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
pip install -r requirements.txt
cp .env.example .env
```

Edit `.env` and use an explicitly restricted workspace:

```dotenv
HOST=127.0.0.1
PORT=8765
MCP_BASE_URL=https://mcp.example.com
MCP_WORKSPACE_DIR=/home/youruser/workspace

AUTH0_DOMAIN=your-tenant.eu.auth0.com
AUTH0_CLIENT_ID=replace_me
AUTH0_CLIENT_SECRET=replace_me
AUTH0_AUDIENCE=https://mcp.example.com/
```

Never commit `.env`.

## Auth0 setup

This project uses FastMCP's `Auth0Provider` fixed-client OAuth integration.

1. In Auth0, create an API.
2. Use your public MCP URL as its identifier/audience, for example `https://mcp.example.com/`.
3. Create a Regular Web Application.
4. Put its domain, client ID and client secret in `.env`.
5. Add only the callback URLs required by your MCP clients to the Auth0 application's allowed callback URLs.
6. Set the application's allowed web origins and logout URLs as required by your clients.
7. Keep RS256 signing enabled.

FastMCP also supports an Auth0 MCP-native/DCR path through `Auth0MCPProvider`. This repository currently uses the manually managed, fixed-client `Auth0Provider` path.

## Install

From PyPI (recommended):

```bash
pip install universal-host-manager-mcp
```

Or with [uv](https://docs.astral.sh/uv/) / [pipx](https://pipx.pypa.io/), without polluting a project environment:

```bash
uvx universal-host-manager-mcp
```

From source (for development):

```bash
python -m venv .venv
source .venv/bin/activate
pip install -e .
```

## Run

```bash
universal-host-manager-mcp
```

(Running from a source checkout with the `.venv` activated works the same way — the console script is installed by `pip install -e .`.)

With the default port, the Streamable HTTP endpoint is:

```text
http://127.0.0.1:8765/mcp
```

For an intentional local-only test without Auth0:

```bash
ALLOW_INSECURE_NO_AUTH=true universal-host-manager-mcp
```

Do not use insecure mode on a publicly reachable endpoint.

## Cloudflare Tunnel

Install `cloudflared`, authenticate it and create a named tunnel:

```bash
cloudflared tunnel login
cloudflared tunnel create universal-host-manager-mcp
cloudflared tunnel route dns universal-host-manager-mcp mcp.example.com
```

Create `~/.cloudflared/config.yml`:

```yaml
tunnel: YOUR_TUNNEL_ID
credentials-file: /home/youruser/.cloudflared/YOUR_TUNNEL_ID.json

ingress:
  - hostname: mcp.example.com
    service: http://127.0.0.1:8765
  - service: http_status:404
```

Validate and run it:

```bash
cloudflared tunnel ingress validate
cloudflared tunnel run universal-host-manager-mcp
```

Your remote MCP URL will be:

```text
https://mcp.example.com/mcp
```

Set `MCP_BASE_URL=https://mcp.example.com`; do not include `/mcp` in `MCP_BASE_URL`.

## ChatGPT and Claude

Add the public Streamable HTTP URL to the client's MCP/connector configuration:

```text
https://mcp.example.com/mcp
```

Complete the Auth0 sign-in when the client opens the authorization flow. The exact settings screens and supported connector options can change, so follow the current client documentation rather than using legacy SSE instructions.

Multiple clients can connect to the same running HTTP server. Each client authenticates independently; no separate server process or port is required.

## Background service

### Linux systemd

Copy and edit the included unit:

```bash
sudo cp examples/mcp-manager.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now mcp-manager
sudo systemctl status mcp-manager --no-pager
```

The example uses systemd hardening directives. Adjust `ReadWritePaths`, `ProtectHome`, the user, paths and permissions to match the resources the MCP server genuinely needs.

### macOS launchd

Edit paths in `examples/com.user.mcpmanager.plist`, then:

```bash
cp examples/com.user.mcpmanager.plist ~/Library/LaunchAgents/
launchctl bootstrap gui/$(id -u) ~/Library/LaunchAgents/com.user.mcpmanager.plist
launchctl kickstart -k gui/$(id -u)/com.user.mcpmanager
```

## Configuration

| Variable | Default | Description |
| --- | --- | --- |
| `HOST` | `127.0.0.1` | Listen address |
| `PORT` | `8765` | Listen port |
| `MCP_BASE_URL` | local URL | Public OAuth base URL, without `/mcp` |
| `MCP_WORKSPACE_DIR` | user home | Boundary for file tools and command working directory |
| `MAX_OUTPUT_CHARS` | `64000` | Maximum returned tool-output characters |
| `DEFAULT_CMD_TIMEOUT` | `300` | Default command timeout in seconds |
| `MAX_CMD_TIMEOUT` | `1800` | Maximum accepted command timeout |
| `MAX_READ_BYTES` | `5000000` | Maximum file size read by `read_file` |
| `MAX_WRITE_BYTES` | `5000000` | Maximum content size written by `write_file` |
| `LOG_LEVEL` | `INFO` | Python log level |
| `ALLOW_INSECURE_NO_AUTH` | `false` | Explicit local-development authentication bypass |

## Download

Clone with Git:

```bash
git clone https://github.com/Abktya/universal-host-manager-mcp.git
```

Or use **Code → Download ZIP** on GitHub.

## License

[MIT](LICENSE)
