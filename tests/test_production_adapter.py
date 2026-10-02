from __future__ import annotations

import anyio

from headlessdomains_mcp.client.production import ProductionHeadlessDomainsClient
from headlessdomains_mcp.config import Settings


def test_portfolio_requires_server_side_authentication() -> None:
    settings = Settings(
        data_mode="production",
        api_base_url="https://example.invalid/api/v1",
        api_token=None,
        timeout_seconds=1,
        host="127.0.0.1",
        port=8787,
    )

    async def scenario() -> None:
        client = ProductionHeadlessDomainsClient(settings)
        try:
            await client.list_my_names()
        except RuntimeError as exc:
            assert "server-side account authentication" in str(exc)
        else:
            raise AssertionError("Expected authentication to be required before any request")

    anyio.run(scenario)

