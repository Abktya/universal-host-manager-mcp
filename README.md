# Universal Host Manager MCP
<!-- mcp-name: io.github.Abktya/universal-host-manager-mcp -->

A cross-platform [Model Context Protocol](https://modelcontextprotocol.io/) server for administering a Linux or macOS host through MCP clients such as ChatGPT and Claude.

[![Abktya/universal-host-manager-mcp MCP server](https://glama.ai/mcp/servers/Abktya/universal-host-manager-mcp/badges/score.svg)](https://glama.ai/mcp/servers/Abktya/universal-host-manager-mcp)
[![tests](https://github.com/Abktya/universal-host-manager-mcp/actions/workflows/tests.yml/badge.svg)](https://github.com/Abktya/universal-host-manager-mcp/actions/workflows/tests.yml)

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

### PyPI (recommended)

```bash
pip install universal-host-manager-mcp
```

Next: run `uhm-setup` to generate your `.env` — see [Configure](#configure) below.

### uv / pipx

Without polluting a project environment:

```bash
uvx --from universal-host-manager-mcp uhm-setup
```

This installs into a throwaway environment, runs the setup wizard, and writes `.env` in the current directory. From then on, run the server itself the same way: `uvx universal-host-manager-mcp`.

### From source (for development)

```bash
git clone https://github.com/Abktya/universal-host-manager-mcp.git
cd universal-host-manager-mcp
python3 -m venv .venv
source .venv/bin/activate
pip install -e .
```

Next: run `uhm-setup` to generate your `.env` — see [Configure](#configure) below.

### Configure

The easiest way is the interactive setup wizard, installed alongside the server:

```bash
uhm-setup
```

Run it from the directory where you want to keep the configuration. The server must later be started from that same directory so it can find `.env`.

For a first test, choose **1 — Local-only test**. Press Enter to accept the port `8765`; the port prompt expects a number, not `y` or `n`. This mode:

- creates a separate `workspace` directory by default;
- listens only on `127.0.0.1`, so other computers cannot connect;
- requires no domain, tunnel, or Auth0 account;
- enables unauthenticated access only for that local test.

The wizard also offers Cloudflare Tunnel, an ngrok static domain, and an existing HTTPS URL for remote use. Remote modes require Auth0 and will not write a misleading, unusable configuration if Auth0 is skipped. It validates domains and URLs, then writes `.env` with `600` permissions—backing up an existing file to `.env.bak` first.

If a virtual environment is active, install and run both commands through that environment:

```bash
python -m pip install universal-host-manager-mcp
uhm-setup
universal-host-manager-mcp
```

To verify that the command belongs to the active environment on macOS/Linux:

```bash
command -v uhm-setup
command -v universal-host-manager-mcp
python -m pip show universal-host-manager-mcp
```

The first two paths should normally point inside `.venv/bin`. If they point to `/opt/homebrew/bin` while a virtual environment is active, reinstall with `python -m pip install universal-host-manager-mcp`.

Prefer to do it by hand? Create a `.env` file (copy `.env.example` if you installed from source) with an explicitly restricted workspace:

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

1. Open [auth0.com](https://auth0.com/), create an account, and open the Auth0 Dashboard.
2. Go to **Applications → APIs → Create API**.
3. Use your public MCP URL as its **Identifier** (audience), for example `https://mcp.example.com/`. Keep **RS256** as the signing algorithm.
4. Go to **Applications → Applications → Create Application**, enter a name, select **Regular Web Application**, and create it.
5. On Auth0's **Integrate into your application** page, click **Copy** above the `.env` block. The wizard can import `AUTH0_DOMAIN`, `AUTH0_CLIENT_ID`, and `AUTH0_CLIENT_SECRET` from your clipboard or from a pasted block. If Auth0 displays `MASKED`, reveal and copy the real Client Secret from the application's **Settings** tab; masked secrets are rejected.
6. Copy the API's **Identifier** into `AUTH0_AUDIENCE` when the wizard asks for it. It is intentionally separate because Auth0's application `.env` block does not contain the API audience.
7. In the Auth0 application's **Settings**, use the MCP server's public origin (without `/mcp`) as follows:

   | Auth0 field | Value |
   | --- | --- |
   | Application Ownership | **First-party** |
   | Application Type | **Regular Web Application** |
   | Application Login URI | Leave blank |
   | Allowed Callback URLs | `https://mcp.example.com/auth/callback` |
   | Allowed Logout URLs | `https://mcp.example.com` |
   | Allowed Web Origins | `https://mcp.example.com` |
   | Allowed Origins (CORS) | `https://mcp.example.com` |
   | Allow Cross-Origin Authentication | Off / disabled |
   | Cross-Origin Verification Fallback URL | Leave blank |
   | API Identifier / Audience | `https://mcp.example.com/` |
   | Signing Algorithm | **RS256** |
   | MCP endpoint (entered in the AI client, not Auth0) | `https://mcp.example.com/mcp` |

8. Save the Auth0 application settings, then run the wizard. Never share the Client Secret or commit `.env` to Git.

The callback above is FastMCP's fixed upstream callback. Do **not** put Claude, ChatGPT, or Grok callback URLs into Auth0: those products are downstream MCP clients and FastMCP validates their redirect URIs separately during MCP client registration. Connect each product to `https://mcp.example.com/mcp`.

Auth0's Python quickstart also shows `AUTH0_SECRET`, `APP_BASE_URL`, `PORT`, and sample Flask code. They belong to Auth0's standalone sample web application and are not used by this MCP server; the wizard safely ignores them when importing the copied block.

Client notes:

- ChatGPT supports MCP OAuth client registration with CIMD and DCR; add the public `/mcp` endpoint in ChatGPT developer mode.
- Claude custom connectors accept the public `/mcp` endpoint and start OAuth when you connect.
- Grok custom connectors accept a publicly reachable MCP server URL and complete any required authentication. Grok availability may depend on the current Grok plan and workspace controls.

FastMCP also supports an Auth0 MCP-native/DCR path through `Auth0MCPProvider`. This repository currently uses the manually managed, fixed-client `Auth0Provider` path.

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

Keep both `universal-host-manager-mcp` and `cloudflared` running. Closing either process takes the public endpoint offline. The setup wizard can optionally print Linux systemd-user or macOS LaunchAgent commands for both processes.

Your remote MCP URL will be:

```text
https://mcp.example.com/mcp
```

Set `MCP_BASE_URL=https://mcp.example.com`; do not include `/mcp` in `MCP_BASE_URL`.

## No domain? Use ngrok's free static domain

Auth0 OAuth needs a stable HTTPS URL, but you don't need to own a domain to get one. Unlike ngrok's old random URLs (which changed every restart) or Cloudflare's login-free [quick tunnels](https://developers.cloudflare.com/cloudflare-one/connections/connect-networks/do-more-with-tunnels/trycloudflare/) (same problem), ngrok's free tier includes **one static subdomain per account** that never changes, at no cost.

1. Create a free account at [ngrok.com](https://ngrok.com). On Ubuntu install the CLI with `sudo snap install ngrok`. On macOS or another platform, use ngrok's official [download instructions](https://ngrok.com/download).
2. Open the [ngrok authtoken page](https://dashboard.ngrok.com/get-started/your-authtoken), copy your token, and run:

   ```bash
   ngrok config add-authtoken YOUR_NGROK_TOKEN
   ```

   Use the **authtoken**, not the domain ID. Never share it; reset it in the dashboard if it is exposed.
3. Claim your free static domain from the ngrok dashboard (**Domains** → **New Domain**). You'll get something like `your-name.ngrok-free.dev`.
4. Start `universal-host-manager-mcp` from the directory containing `.env`.
5. In a second terminal, start the tunnel:

   ```bash
   ngrok http --url=your-name.ngrok-free.dev 8765
   ```

   **Both processes must remain running.** Closing either one takes the public endpoint offline. The wizard can optionally print Linux systemd-user or macOS LaunchAgent commands that start both automatically.
6. Set `MCP_BASE_URL=https://your-name.ngrok-free.dev` in `.env` (keep `HOST=127.0.0.1`; ngrok forwards to the local port while the server listens only on loopback).
7. In Auth0, set the application's callback URL to `https://your-name.ngrok-free.dev/auth/callback`; set web origins and logout URLs to `https://your-name.ngrok-free.dev` (see [Auth0 setup](#auth0-setup)).

Your remote MCP URL is:

```text
https://your-name.ngrok-free.dev/mcp
```

This is a good fit for personal use or a small number of clients. For production traffic at scale, ngrok's free tier applies connection/bandwidth limits — check their [pricing page](https://ngrok.com/pricing) if you outgrow it, or switch to the domain-based Cloudflare Tunnel setup above.

## AWS EC2 Deployment

These steps deploy the server on an EC2 instance and expose it safely to remote MCP clients.

### 1. Launch the instance

- AMI: Ubuntu 24.04 LTS (the commands below are for Ubuntu/`apt`; on Amazon Linux 2023 use `sudo dnf install -y python3-pip` instead)
- Instance type: `t3.micro`/`t3.small` is enough for typical management workloads
- Security group: allow inbound **SSH (22)** from your own IP only. No other inbound port is required if you use the Cloudflare Tunnel option below.

### 2. Install the server

SSH into the instance, then install from PyPI:

```bash
sudo apt update && sudo apt install -y python3-pip python3-venv
python3 -m venv ~/uhm-venv
source ~/uhm-venv/bin/activate
pip install universal-host-manager-mcp
```

### 3. Configure

```bash
mkdir -p ~/workspace
cat > ~/.env << 'EOF'
HOST=127.0.0.1
PORT=8765
MCP_BASE_URL=https://mcp.example.com
MCP_WORKSPACE_DIR=/home/ubuntu/workspace

AUTH0_DOMAIN=your-tenant.eu.auth0.com
AUTH0_CLIENT_ID=replace_me
AUTH0_CLIENT_SECRET=replace_me
AUTH0_AUDIENCE=https://mcp.example.com/
EOF
chmod 600 ~/.env
```

Keep `HOST=127.0.0.1`. The server should never listen directly on the instance's public interface — internet exposure is handled entirely by the tunnel or load balancer described below, not by opening the instance's own port.

### 4. Networking: get an HTTPS URL to the instance

Auth0 OAuth requires HTTPS. Pick one option:

**Option A — Cloudflare Tunnel (recommended, no inbound port needed)**

Run the steps from the [Cloudflare Tunnel](#cloudflare-tunnel) section above, from the EC2 instance. Because the tunnel is an outbound-only connection, you don't need to open any inbound port beyond SSH, don't need an Elastic IP, and the instance can even sit in a private subnet behind a NAT gateway.

Don't own a domain? Run the steps from [No domain? Use ngrok's free static domain](#no-domain-use-ngroks-free-static-domain) above instead — same outbound-only, no-inbound-port setup, just from the EC2 instance.

**Option B — Application Load Balancer with an ACM certificate**

- Request an ACM certificate for your domain and attach it to an ALB
- Create an HTTPS (443) listener on the ALB forwarding to the instance's `PORT`
- Security group on the instance: allow inbound `PORT` **only from the ALB's security group**, never from `0.0.0.0/0`
- Point your DNS at the ALB and set `MCP_BASE_URL` to that hostname

### 5. Run as a systemd service

Reuse the included unit (see [Background service](#background-service) below):

```bash
sudo cp examples/mcp-manager.service /etc/systemd/system/
# edit User=, WorkingDirectory=, EnvironmentFile= and ExecStart= to point at
# ~/uhm-venv/bin/universal-host-manager-mcp and ~/.env
sudo systemctl daemon-reload
sudo systemctl enable --now mcp-manager
sudo systemctl status mcp-manager --no-pager
```

### 6. Elastic IP

Not required for either networking option. The Cloudflare Tunnel connects outbound regardless of the instance's address, and an ALB registers targets by instance ID or private IP, so it doesn't need one either. Only add an Elastic IP if something else in your setup depends on a fixed public IP for this instance.

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
| `LOG_COMMANDS` | `false` | Log `run_command`'s command text (may contain secrets) instead of just its timeout |
| `FASTMCP_CHECK_FOR_UPDATES` | `off` (forced unless you set it) | FastMCP's own PyPI update-check on startup |
| `ALLOW_INSECURE_NO_AUTH` | `false` | Explicit local-development authentication bypass |

## Testing

```bash
pip install -e ".[dev]"
pytest tests/
```

CI runs the suite against fastmcp 2.13, 3.x and 4.x on every push (see the badge above), since `@mcp.tool()`'s return type changed between major versions and tests call tools through a small version-agnostic helper (`tests/conftest.py::call_tool`) to cover all three.

## Download

Clone with Git:

```bash
git clone https://github.com/Abktya/universal-host-manager-mcp.git
```

Or use **Code → Download ZIP** on GitHub.

## License

[MIT](LICENSE)
