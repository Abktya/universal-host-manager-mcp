# Security policy

## Important security model

This server intentionally exposes arbitrary shell execution and file-writing
capabilities. Authentication controls who can call the tools; it does not make
shell commands safe.

`MCP_WORKSPACE_DIR` constrains the built-in file tools and sets the command
working directory. It is **not** an operating-system sandbox for `run_command`.
A command can use absolute paths or access any resource permitted to the OS user.

## Safe deployment checklist

- Run the service as a dedicated, unprivileged OS user.
- Grant that user access only to the directories and services it must manage.
- Set `MCP_WORKSPACE_DIR` explicitly.
- Keep Auth0 enabled on every remotely reachable deployment.
- Bind to `127.0.0.1` behind a TLS reverse proxy or Cloudflare Tunnel.
- Never commit `.env`, tokens, client secrets, SSH keys or tunnel credentials.
- Do not grant passwordless unrestricted `sudo`.
- Review logs and rotate credentials if an MCP client or account is compromised.
- For stronger isolation, run the service inside a locked-down container or VM.

## Logging

`run_command`'s content can include secrets — tokens or passwords passed as
command-line arguments, for example. `LOG_COMMANDS` is `false` by default: only
the timeout is logged for each call, never the command text. Set
`LOG_COMMANDS=true` only if you specifically need a command-content audit trail
and understand it may put secrets in your logs; secure and rotate log access
accordingly if you do.

## Network calls made by this server

Besides serving MCP requests, the process makes two categories of outbound
calls:

- To Auth0, for OAuth token validation (required, cannot be disabled while
  authentication is enabled).
- FastMCP itself normally checks PyPI once per 12h for a newer FastMCP
  release. This server disables that check by default (unless you've
  explicitly set `FASTMCP_CHECK_FOR_UPDATES` yourself) so startup stays
  deterministic and doesn't depend on reaching PyPI.

## Reporting a vulnerability

Please do not disclose credentials or exploitable deployment details in a public
issue. Contact the repository owner privately through GitHub.
