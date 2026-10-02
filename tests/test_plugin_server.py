from __future__ import annotations

import anyio
from mcp.client import Client

from headlessdomains_mcp.config import Settings
from headlessdomains_mcp.server import UI_URI, create_server


def fixture_settings() -> Settings:
    return Settings(
        data_mode="fixture",
        api_base_url="https://headlessdomains.com/api/v1",
        api_token=None,
        timeout_seconds=1,
        host="127.0.0.1",
        port=8787,
    )


def test_tools_resources_and_entrypoints_are_advertised() -> None:
    async def scenario() -> None:
        async with Client(create_server(settings=fixture_settings())) as client:
            listed = await client.list_tools()
            tools = {tool.name: tool for tool in listed.tools}

            assert {
                "headlessdomains.app",
                "headlessdomains.name_panel",
                "search_mentions",
                "lookup_name",
                "check_availability",
                "list_my_names",
                "get_records",
            } == set(tools)

            assert tools["headlessdomains.app"].meta == {
                "openai/iconStyle": "monochrome",
                "openai/ui": {
                    "entrypoints": [{"type": "global"}],
                    "preferredModelDisplayMode": "fullscreen",
                },
                "ui": {"resourceUri": UI_URI},
            }
            assert tools["headlessdomains.name_panel"].meta == {
                "openai/iconStyle": "monochrome",
                "openai/ui": {
                    "entrypoints": [{"type": "thread"}],
                    "preferredModelDisplayMode": "fullscreen",
                },
                "ui": {"resourceUri": UI_URI},
            }
            assert tools["headlessdomains.app"].icons is not None
            assert tools["headlessdomains.app"].icons[0].mime_type == "image/svg+xml"
            assert tools["search_mentions"].meta == {
                "openai/extensions": {"mentions/search": {}},
                "ui": {"visibility": ["app"]},
            }

            for name in ("lookup_name", "check_availability", "list_my_names", "get_records"):
                assert tools[name].annotations is not None
                assert tools[name].annotations.read_only_hint is True
                assert tools[name].annotations.destructive_hint is False
                assert tools[name].output_schema is not None

            resources = await client.list_resources()
            assert len(resources.resources) == 1
            resource = resources.resources[0]
            assert str(resource.uri) == UI_URI
            assert resource.mime_type == "text/html;profile=mcp-app"
            assert resource.meta == {
                "ui": {"prefersBorder": False},
                "openai/ui": {
                    "availableDisplayModes": ["fullscreen"],
                    "preferredDisplayMode": "fullscreen",
                },
            }

            rendered = await client.read_resource(UI_URI)
            assert rendered.contents[0].mime_type == "text/html;profile=mcp-app"
            assert "ui/initialize" in (rendered.contents[0].text or "")
            assert "tools/call" in (rendered.contents[0].text or "")

    anyio.run(scenario)


def test_fixture_tools_return_structured_results() -> None:
    async def scenario() -> None:
        async with Client(create_server(settings=fixture_settings())) as client:
            availability = await client.call_tool("check_availability", {"query": "atlas"})
            assert availability.structured_content is not None
            assert availability.structured_content["matches"][0]["name"] == "atlas.agent"
            assert availability.structured_content["matches"][0]["available"] is False

            lookup = await client.call_tool("lookup_name", {"name": "atlas.agent"})
            assert lookup.structured_content is not None
            assert lookup.structured_content["status"] == "registered"
            assert lookup.structured_content["owner"]["displayName"] == "Atlas Labs"

            portfolio = await client.call_tool("list_my_names", {"limit": 1})
            assert portfolio.structured_content is not None
            assert len(portfolio.structured_content["names"]) == 1
            assert portfolio.structured_content["nextCursor"] == "1"

            records = await client.call_tool("get_records", {"name": "atlas.agent"})
            assert records.structured_content is not None
            assert {item["type"] for item in records.structured_content["records"]} == {
                "TXT",
                "AGENT_JSON",
                "SKILL",
            }

    anyio.run(scenario)


def test_mentions_return_resource_items() -> None:
    async def scenario() -> None:
        async with Client(create_server(settings=fixture_settings())) as client:
            result = await client.call_tool("search_mentions", {"query": "atlas"})
            assert result.structured_content == {
                "items": [
                    {
                        "type": "resource",
                        "resourceUri": "headlessdomains://names/atlas.agent",
                        "title": "atlas.agent",
                        "subtitle": "HeadlessDomains name",
                    }
                ]
            }

    anyio.run(scenario)


def test_invalid_tool_input_is_rejected() -> None:
    async def scenario() -> None:
        async with Client(create_server(settings=fixture_settings())) as client:
            result = await client.call_tool("check_availability", {"query": ""})
            assert result.is_error is True

    anyio.run(scenario)
