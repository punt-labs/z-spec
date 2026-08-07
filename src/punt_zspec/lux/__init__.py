"""Interactive lux menu integration for the z-spec MCP server.

The FastMCP lifespan owns one :class:`ZSpecLuxSession`: a persistent applet-identity
client, the server-owned display every render path shares, and a listener task
that registers the Tutorial and Browse menu entries and routes their clicks.
"""

from __future__ import annotations

from punt_zspec.lux.session import ZSpecLuxSession

__all__ = ["ZSpecLuxSession"]
