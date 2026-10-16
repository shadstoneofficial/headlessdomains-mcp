# Grok connection (additive Streamable HTTP)

Use `https://mcp.headlessdomains.com/mcp` after this change is deployed.
Existing `/sse` and `/messages/` clients and stdio remain supported. Discovery
continues to advertise SSE to avoid changing existing registry integrations.

```
grok mcp add --transport http headlessdomains https://mcp.headlessdomains.com/mcp
grok mcp doctor headlessdomains --json
```

Public discovery/search require no key. Authenticated operations require each
customer's own `X-API-Key` header on every request. Never use query-string keys or
a shared server credential. Use the client's secure configuration/environment
support rather than pasting real keys into shell history.

HTTP is stateless: no reusable credential-bearing HTTP session is issued.
The same tool implementations and upstream API authorization apply on both
transports. Registration, checkout, pricing and payment logic are unchanged.

This change depends on hosted credential isolation PR #3. Deploy only with that
fix included. Protocol discovery is not proof of successful purchases or Grok
Bot marketplace acceptance. Do not submit marketplace testing attestations until
the actual target host is tested. No live write tool is needed for connectivity.

## Verification — October 16, 2026

- Legacy startup/health/discovery/SSE smoke passed.
- Credential unit tests and concurrent SSE/HTTP A/B/anonymous tests passed,
  with upstream HTTP mocked. Query credentials rejected on both endpoints;
  existing SSE cross-session rejection retained.
- Grok Build 1.0.52 `mcp doctor` against local `/mcp`: healthy, handshake
  protocol 2025-11-25, four tools discovered. No business tools invoked by Grok.
- Not deployed or tested in the Grok Bot marketplace host yet.
