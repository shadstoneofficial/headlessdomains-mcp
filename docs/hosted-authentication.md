# Legacy hosted MCP authentication

This applies only to `server.py`, not the separate MCP v2 ChatGPT extension.

- Public discovery and read-only tools do not require a key.
- A caller supplies its own HeadlessDomains key as `X-API-Key` on **both**
  `GET /sse` and `POST /messages/`. No credentials in query strings or defaults.
- Hosted connections never read `HEADLESSDOMAINS_API_KEY` from server environment.
  Local stdio continues to use that variable in the user's own process.
- The pinned MCP SDK binds sessions to a digest of the supplied credential.
  Another key or a missing key cannot post into a credentialed session.
- The middleware does not validate account permissions itself: it forwards only
  the connection's key to the HeadlessDomains API, which authorizes each operation.
  Invalid/revoked credentials must not be described as authenticated purchases.
- Missing hosted credentials reject write tools before any upstream request.
- Application URL access logging is off and upstream exception bodies are not
  returned. Infrastructure may still log rejected URL queries: never put keys
  there; rotate a real key if it was previously exposed in a URL.

## Smithery publication gate

Publication is paused until this repair is reviewed/deployed and gateway header
forwarding on both SSE and POST is verified. Configure an optional per-user
header mapped to `X-API-Key`, with no default. Do not merely change the old
query parameter without inspecting its generated header mapping. If Smithery
does not preserve headers or cannot connect using SSE, stop: do not fall back
to a shared key or URL credentials. Transport migration is a separate change.

Tests: `python scripts/test_hosted_auth.py` uses synthetic keys, a subprocess on
loopback and mocked upstream requests. It exercises concurrent distinct users,
anonymous rejection, no shared-key fallback and session mismatch. No real
payment, registration or bio update is permitted as a release test.
