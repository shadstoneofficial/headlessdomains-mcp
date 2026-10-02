# Connect the local HeadlessDomains plugin to ChatGPT

These steps test the isolated read-only plugin server. They do not deploy or modify `headlessdomains.com` or the existing `mcp.headlessdomains.com` service.

## 1. Install and run in fixture mode

Fixture mode is the default and makes no HeadlessDomains production requests.

```bash
python3 -m venv .venv
.venv/bin/python -m pip install -e '.[dev]'
HEADLESSDOMAINS_DATA_MODE=fixture .venv/bin/python plugin_server.py
```

The local MCP endpoint is:

```text
http://127.0.0.1:8787/mcp
```

## 2. Inspect the MCP server

```bash
npx @modelcontextprotocol/inspector@latest
```

In Inspector, choose **Streamable HTTP**, enter `http://127.0.0.1:8787/mcp`, and verify:

- `lookup_name`
- `check_availability`
- `list_my_names`
- `get_records`
- `headlessdomains.app` with a `global` entrypoint
- `headlessdomains.name_panel` with a `thread` entrypoint
- `search_mentions`
- `ui://headlessdomains/app-v1` with MIME type `text/html;profile=mcp-app`

## 3. Expose the local endpoint safely

Use OpenAI Secure MCP Tunnel when available. A temporary HTTPS forwarding tunnel may be used for development only. Point the tunnel at port `8787` and copy the resulting HTTPS URL.

Do not use a temporary tunnel for public plugin submission.

## 4. Add it in ChatGPT developer mode

1. Open ChatGPT **Settings**.
2. Select **Security and login**.
3. Turn on **Developer mode**. Availability can depend on account or workspace policy.
4. Open **ChatGPT Plugins** and select the plus button.
5. Enter a user-facing name such as `HeadlessDomains Local` and a clear fixture-mode description.
6. Enter the HTTPS tunnel URL including `/mcp`, for example `https://example-tunnel.test/mcp`.
7. Create the connection and review the discovered tools and metadata.
8. Open a new chat, enable the plugin, and test the prompts in `docs/evaluation-prompts.md`.

After changing schemas, metadata, authentication, or UI resources, restart the server, open the plugin connection, select **Refresh**, and start a new conversation.

## 5. Optional read-only production mode

Public lookup and availability calls can be tested without an account:

```bash
HEADLESSDOMAINS_DATA_MODE=production .venv/bin/python plugin_server.py
```

For the current development-only portfolio adapter, pass a GFAVIP bearer token to the server process—not to the iframe and not in ChatGPT messages:

```bash
HEADLESSDOMAINS_DATA_MODE=production \
HEADLESSDOMAINS_API_TOKEN='replace-in-your-shell-only' \
.venv/bin/python plugin_server.py
```

This token bridge is not the final ChatGPT OAuth implementation. Do not deploy or share it as public plugin authentication.

