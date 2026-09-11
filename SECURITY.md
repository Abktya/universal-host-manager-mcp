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

## Reporting a vulnerability

Please do not disclose credentials or exploitable deployment details in a public
issue. Contact the repository owner privately through GitHub.
