from __future__ import annotations

import os
from pathlib import Path
from typing import Annotated
from urllib.parse import quote

import uvicorn
from mcp.server.apps import APP_MIME_TYPE, Apps
from mcp.server.mcpserver import MCPServer
from mcp.server.mcpserver.resources import TextResource
from mcp_types import Icon, ToolAnnotations
from openai_mcp_extensions import (
    OpenAIExtensions,
    OpenAIGlobalEntrypoint,
    OpenAIMentionResource,
    OpenAIMentionSearchParams,
    OpenAIMentionSearchResult,
    OpenAIThreadEntrypoint,
    OpenAIUiResourceMetadata,
    OpenAIUiToolMetadata,
)
from pydantic import Field
from starlette.requests import Request
from starlette.responses import JSONResponse

from headlessdomains_mcp.client import (
    AuthenticationRequired,
    FixtureHeadlessDomainsClient,
    HeadlessDomainsClient,
    ProductionHeadlessDomainsClient,
)
from headlessdomains_mcp.config import Settings
from headlessdomains_mcp.models import (
    AppSnapshot,
    AvailabilityResult,
    LookupResult,
    PortfolioResult,
    RecordsResult,
)

UI_URI = "ui://headlessdomains/app-v1"
ICON_SVG = """<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 20 20" fill="none"><circle cx="10" cy="10" r="7.5" stroke="currentColor" stroke-width="1.33"/><path d="M6 6v8M14 6v8M6 10h8" stroke="currentColor" stroke-width="1.33" stroke-linecap="round"/></svg>"""
APP_ICON = Icon(
    src="data:image/svg+xml," + quote(ICON_SVG),
    mime_type="image/svg+xml",
    sizes=["any"],
)
READ_ONLY = ToolAnnotations(
    read_only_hint=True,
    destructive_hint=False,
    open_world_hint=False,
)


def _client_for(settings: Settings) -> HeadlessDomainsClient:
    if settings.data_mode == "production":
        return ProductionHeadlessDomainsClient(settings)
    return FixtureHeadlessDomainsClient()


def _dump_meta(model: object) -> dict:
    return model.model_dump(by_alias=True, exclude_none=True, mode="json")  # type: ignore[attr-defined]


def create_server(
    settings: Settings | None = None,
    client: HeadlessDomainsClient | None = None,
) -> MCPServer:
    settings = settings or Settings.from_env()
    client = client or _client_for(settings)

    app_html = Path(__file__).with_name("app.html").read_text(encoding="utf-8")
    apps = Apps()
    extensions = OpenAIExtensions()
    apps.add_resource(
        TextResource(
            uri=UI_URI,
            name="headlessdomains-app",
            title="HeadlessDomains",
            description="Search, resolve, and inspect HeadlessDomains names.",
            mime_type=APP_MIME_TYPE,
            text=app_html,
            meta={
                "ui": {"prefersBorder": False},
                "openai/ui": _dump_meta(
                    OpenAIUiResourceMetadata(
                        available_display_modes=["fullscreen"],
                        preferred_display_mode="fullscreen",
                    )
                ),
            },
        )
    )

    def snapshot(view: str) -> AppSnapshot:
        return AppSnapshot(
            view=view,
            data_mode=settings.data_mode,
            production_wiring={
                "lookup_name": "production" if settings.data_mode == "production" else "fixture",
                "check_availability": "production" if settings.data_mode == "production" else "fixture",
                "list_my_names": (
                    "production-server-token"
                    if settings.data_mode == "production" and settings.api_token
                    else "fixture" if settings.data_mode == "fixture" else "authentication-pending"
                ),
                "get_records": "derived-lookup" if settings.data_mode == "production" else "fixture",
            },
        )

    @apps.tool(
        resource_uri=UI_URI,
        name="headlessdomains.app",
        title="HeadlessDomains",
        description="Open HeadlessDomains name search and the connected account portfolio.",
        annotations=READ_ONLY,
        icons=[APP_ICON],
        structured_output=True,
        meta={
            "openai/iconStyle": "monochrome",
            "openai/ui": _dump_meta(
                OpenAIUiToolMetadata(
                    entrypoints=[OpenAIGlobalEntrypoint()],
                    preferred_model_display_mode="fullscreen",
                )
            )
        },
    )
    async def open_sidebar() -> AppSnapshot:
        return snapshot("sidebar")

    @apps.tool(
        resource_uri=UI_URI,
        name="headlessdomains.name_panel",
        title="HeadlessDomains name inspector",
        description="Open a HeadlessDomains name inspector beside this conversation.",
        annotations=READ_ONLY,
        icons=[APP_ICON],
        structured_output=True,
        meta={
            "openai/iconStyle": "monochrome",
            "openai/ui": _dump_meta(
                OpenAIUiToolMetadata(
                    entrypoints=[OpenAIThreadEntrypoint()],
                    preferred_model_display_mode="fullscreen",
                )
            )
        },
    )
    async def open_thread_panel() -> AppSnapshot:
        return snapshot("thread")

    @extensions.mentions.search
    async def search_mentions(
        params: OpenAIMentionSearchParams,
        _context,
    ) -> OpenAIMentionSearchResult:
        names = await client.mention_names(params.query, limit=30)
        return OpenAIMentionSearchResult(
            items=[
                OpenAIMentionResource(
                    resource_uri=f"headlessdomains://names/{name}",
                    title=name,
                    subtitle="HeadlessDomains name",
                )
                for name in names
            ]
        )

    server = MCPServer(
        name="headlessdomains-chatgpt-plugin",
        title="HeadlessDomains",
        description="Read-only name resolution, availability, records, and portfolio tools.",
        instructions=(
            "Use these read-only tools to resolve and inspect HeadlessDomains names. "
            "Do not claim that registration, renewal, payment, or record mutation is supported."
        ),
        website_url="https://headlessdomains.com",
        version="0.1.0",
        extensions=[apps, extensions],
    )

    @server.tool(
        name="lookup_name",
        title="Look up a HeadlessDomains name",
        description="Resolve one exact name and return its owner summary, endpoints, and capabilities.",
        annotations=READ_ONLY,
        structured_output=True,
    )
    async def lookup_name(
        name: Annotated[str, Field(min_length=1, max_length=255)],
    ) -> LookupResult:
        return await client.lookup_name(name)

    @server.tool(
        name="check_availability",
        title="Check name availability",
        description="Check authoritative availability without starting checkout or changing account state.",
        annotations=READ_ONLY,
        structured_output=True,
    )
    async def check_availability(
        query: Annotated[str, Field(min_length=1, max_length=255)],
        namespaces: Annotated[list[str] | None, Field(max_length=25)] = None,
    ) -> AvailabilityResult:
        return await client.check_availability(query, namespaces)

    @server.tool(
        name="list_my_names",
        title="List my HeadlessDomains names",
        description=(
            "List the connected account's names. Fixture mode returns demo data; production mode "
            "requires server-side authentication and never accepts an account ID from the model."
        ),
        annotations=READ_ONLY,
        structured_output=True,
    )
    async def list_my_names(
        query: Annotated[str | None, Field(max_length=255)] = None,
        cursor: str | None = None,
        limit: Annotated[int, Field(ge=1, le=100)] = 25,
    ) -> PortfolioResult:
        try:
            return await client.list_my_names(query=query, cursor=cursor, limit=limit)
        except AuthenticationRequired as exc:
            return PortfolioResult(
                names=[],
                auth_required=True,
                message=str(exc),
            )

    @server.tool(
        name="get_records",
        title="Get name records",
        description=(
            "Return source-labelled records for one name. Production currently derives records "
            "from the public lookup response and reports that limitation."
        ),
        annotations=READ_ONLY,
        structured_output=True,
    )
    async def get_records(
        name: Annotated[str, Field(min_length=1, max_length=255)],
        types: Annotated[list[str] | None, Field(max_length=50)] = None,
    ) -> RecordsResult:
        return await client.get_records(name, types)

    @server.custom_route("/healthz", methods=["GET"], include_in_schema=False)
    async def health(_request: Request) -> JSONResponse:
        return JSONResponse(
            {
                "status": "ok",
                "service": "headlessdomains-chatgpt-plugin",
                "dataMode": settings.data_mode,
            }
        )

    return server


def main() -> None:
    settings = Settings.from_env()
    server = create_server(settings=settings)
    transport = os.getenv("MCP_TRANSPORT", "streamable-http").strip().lower()
    if transport == "stdio":
        server.run(transport="stdio")
        return
    if transport != "streamable-http":
        raise ValueError("MCP_TRANSPORT must be 'streamable-http' or 'stdio'.")

    app = server.streamable_http_app(
        streamable_http_path="/mcp",
        stateless_http=True,
        host=settings.host,
    )
    uvicorn.run(app, host=settings.host, port=settings.port)


if __name__ == "__main__":
    main()
