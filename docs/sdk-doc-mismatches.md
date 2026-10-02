# SDK and documentation notes

Reviewed 2026-10-02 using:

- `mcp==2.2.0`
- `mcp-types==2.2.0`
- `openai-mcp-extensions==0.1.0`

## Findings

1. The previous HeadlessDomains server used the older `mcp.server.fastmcp.FastMCP` surface and SSE. The current OpenAI extension package requires the MCP 2.x Python server surface (`mcp.server.mcpserver.MCPServer`) and exposes streamable HTTP directly.
2. The OpenAI extension SDK's Python package is server-side. This implementation uses the standards-based MCP Apps JSON-RPC bridge in a self-contained HTML resource, following the official quickstart, rather than assuming a Python browser SDK.
3. `OpenAIUiToolMetadata.preferredModelDisplayMode` is supported on tool metadata, while resource metadata uses `preferredDisplayMode` and `availableDisplayModes`. The implementation keeps those placements separate.
4. The existing `headlessdomains.com` OAuth metadata describes agent-native credentials but is not a complete ChatGPT-compatible OAuth 2.1 authorization flow. The implementation does not advertise OAuth until the required discovery, client registration, token, and challenge behavior exists.
5. The official packaging guide now prefers root `plugin.json`; older `.codex-plugin/plugin.json` layouts remain a compatibility fallback. Packaging is intentionally deferred until the MCP connection has a verified plugin ID and production endpoint.

