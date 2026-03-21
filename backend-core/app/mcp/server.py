"""Agency OS MCP server bootstrap."""

from __future__ import annotations

from contextlib import asynccontextmanager
from urllib.parse import urlparse

from mcp.server.fastmcp import FastMCP
from mcp.server.auth.handlers.metadata import ProtectedResourceMetadataHandler
from mcp.server.auth.routes import build_resource_metadata_url
from mcp.server.auth.settings import AuthSettings
from mcp.server.transport_security import TransportSecuritySettings
from mcp.shared.auth import ProtectedResourceMetadata
from starlette.requests import Request
from starlette.types import ASGIApp
from typing import Any

from ..config import settings
from .auth import SupabasePilotTokenVerifier
from .tools.wbr import register_wbr_tools


_MCP_SERVER: FastMCP | None = None
_MCP_ASGI_APP: ASGIApp | None = None
_MCP_PROXY_APP: ASGIApp | None = None


def create_mcp_server() -> FastMCP:
    mcp = FastMCP(
        name="Agency OS",
        instructions=(
            "Agency OS is Ecomlabs' internal tool server. Use its tools to "
            "retrieve canonical internal data before drafting or summarizing."
        ),
        token_verifier=SupabasePilotTokenVerifier(),
        streamable_http_path="/",
        json_response=True,
        stateless_http=True,
        auth=AuthSettings(
            issuer_url=settings.supabase_issuer,
            resource_server_url=settings.mcp_public_base_url,
            required_scopes=None,
        ),
        transport_security=TransportSecuritySettings(
            enable_dns_rebinding_protection=True,
            allowed_hosts=settings.mcp_allowed_hosts,
            allowed_origins=settings.mcp_allowed_origins,
        ),
    )
    register_wbr_tools(mcp)
    return mcp


class MCPProxyApp:
    """Stable mounted app that delegates to the current MCP runtime."""

    async def __call__(self, scope: dict[str, Any], receive: Any, send: Any) -> None:
        if _MCP_ASGI_APP is None:
            raise RuntimeError("MCP runtime is not initialized")
        await _MCP_ASGI_APP(scope, receive, send)


def initialize_mcp_runtime() -> FastMCP:
    """Create a fresh MCP runtime for one FastAPI app lifespan."""
    global _MCP_SERVER, _MCP_ASGI_APP
    server = create_mcp_server()
    _MCP_SERVER = server
    _MCP_ASGI_APP = server.streamable_http_app()
    return server


def get_mcp_protected_resource_metadata_path() -> str:
    """Return the RFC 9728 metadata path for this MCP resource."""
    metadata_url = build_resource_metadata_url(settings.mcp_public_base_url)
    return urlparse(str(metadata_url)).path


async def handle_mcp_protected_resource_metadata(request: Request):
    """Serve protected resource metadata from the parent FastAPI app."""
    metadata = ProtectedResourceMetadata(
        resource=settings.mcp_public_base_url,
        authorization_servers=[settings.supabase_issuer],
        resource_name="Agency OS MCP",
        scopes_supported=None,
    )
    handler = ProtectedResourceMetadataHandler(metadata)
    return await handler.handle(request)


def create_mcp_asgi_app() -> ASGIApp:
    """Return the stable mounted ASGI app for the Agency OS MCP pilot."""
    global _MCP_PROXY_APP
    if _MCP_PROXY_APP is None:
        _MCP_PROXY_APP = MCPProxyApp()
    return _MCP_PROXY_APP


@asynccontextmanager
async def mcp_lifespan():
    """Run the MCP session manager within the parent FastAPI lifespan."""
    server = initialize_mcp_runtime()
    try:
        async with server.session_manager.run():
            yield
    finally:
        global _MCP_SERVER, _MCP_ASGI_APP
        _MCP_SERVER = None
        _MCP_ASGI_APP = None
