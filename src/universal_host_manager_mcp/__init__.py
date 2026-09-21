"""Universal Host Manager MCP Server package."""


def main() -> None:
    """Entry point for the ``universal-host-manager-mcp`` console script.

    Imports ``server`` lazily, on call, rather than at package import
    time. ``server`` raises at import time if Auth0 isn't configured
    (fail-closed by design) — importing it eagerly here would mean
    merely importing this package (e.g. to reach ``setup_wizard``,
    which has no Auth0 dependency at all) crashes before ``.env``
    even exists, breaking `uhm-setup` for a fresh install.
    """
    from .server import main as _main

    _main()


__all__ = ["main"]
