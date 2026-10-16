"""Header-only credential forwarding for legacy hosted MCP.

The upstream HeadlessDomains API validates keys and authorizes each operation.
The SDK principal here binds an SSE session to the exact supplied credential;
it is not an assertion that a key is valid or has any domain permissions.
"""
from contextvars import ContextVar
from hashlib import sha256
from urllib.parse import parse_qsl

from mcp.server.auth.middleware.bearer_auth import AuthenticatedUser
from mcp.server.auth.provider import AccessToken
from starlette.responses import JSONResponse

# None = local/non-HTTP context; empty string = hosted anonymous connection.
connection_key = ContextVar("headlessdomains_connection_key", default=None)


class HostedCredentialMiddleware:
    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            return await self.app(scope, receive, send)
        query = parse_qsl(scope.get("query_string", b"").decode("latin1"))
        if any(k.lower() in {"headlessdomains_api_key", "api_key", "x-api-key", "authorization"} for k, _ in query):
            return await JSONResponse({"error": "Credentials must not be sent in URL parameters. Use X-API-Key."}, status_code=400)(scope, receive, send)
        values = [v.decode("latin1") for k, v in scope.get("headers", []) if k.lower() == b"x-api-key"]
        if len(values) > 1 or (values and (not values[0].strip() or len(values[0]) > 512 or any(ord(c) < 33 or ord(c) > 126 for c in values[0]))):
            return await JSONResponse({"error": "Invalid X-API-Key header."}, status_code=400)(scope, receive, send)
        key = values[0] if values else ""
        scope = dict(scope)
        if key:
            # SDK 1.30 binds GET /sse and POST /messages to this principal.
            scope["user"] = AuthenticatedUser(AccessToken(
                token=key, client_id=sha256(key.encode()).hexdigest(), scopes=[],
            ))
        else:
            scope.pop("user", None)
        token = connection_key.set(key)
        try:
            await self.app(scope, receive, send)
        finally:
            connection_key.reset(token)
