# Headless Domains MCP Server

Official Model Context Protocol (MCP) server for Headless Domains. This server exposes Headless Domains API operations to MCP-compatible clients such as Claude Desktop, Cursor, and Windsurf.

## Features

- `search_domain`: check whether a domain is available
- `lookup_whois`: inspect a registered identity
- `register_domain`: register a domain with an API key
- `sync_bio`: sync agent/profile bio content with an API key
- Automatic transport selection:
  - `stdio` for local MCP clients
  - `sse` when `PORT` is present for hosted deployments

## Requirements

- Python 3.10+
- Optional: a Headless Domains API key for authenticated tools

## Local Setup

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

## Environment Variables

| Variable | Required | Default | Purpose |
| --- | --- | --- | --- |
| `HEADLESSDOMAINS_API_KEY` | No | unset | Sends `X-API-Key` for authenticated endpoints |
| `HEADLESSDOMAINS_API_BASE_URL` | No | `https://headlessdomains.com/api/v1` | Overrides the API base URL |
| `HEADLESSDOMAINS_TIMEOUT` | No | `20` | HTTP timeout in seconds |
| `HEADLESSDOMAINS_REGISTER_PATH` | No | `/domains/register` | Override register endpoint path if the API changes |
| `HEADLESSDOMAINS_SYNC_BIO_PATH` | No | `/domains/{domain}/bio` | Override sync-bio endpoint path if the API changes |
| `MCP_TRANSPORT` | No | auto | Force a transport such as `stdio` or `sse` |
| `HOST` | No | `0.0.0.0` | Bind host for SSE mode |
| `PORT` | No | unset | When present, starts the server in `sse` mode |

## Run Locally

For a local MCP client, the server uses `stdio` by default:

```bash
python server.py
```

You can also run it through the MCP CLI:

```bash
mcp run server.py
```

## Claude Desktop Configuration

Add a server entry to `claude_desktop_config.json`:

```json
{
  "mcpServers": {
    "headlessdomains": {
      "command": "mcp",
      "args": [
        "run",
        "/absolute/path/to/headlessdomains-mcp/server.py"
      ],
      "env": {
        "HEADLESSDOMAINS_API_KEY": "your-api-key-here"
      }
    }
  }
}
```

If you do not need authenticated tools yet, you can omit `HEADLESSDOMAINS_API_KEY`.

## Hosted SSE Mode

When `PORT` is present, `server.py` starts an SSE transport automatically:

```bash
PORT=8080 python server.py
```

Typical Railway-style launch:

```bash
HOST=0.0.0.0 PORT=8080 python server.py
```

## Tool Notes

### `register_domain`

- Requires `HEADLESSDOMAINS_API_KEY`
- Sends a base payload containing `domain`, `namespace`, `years`, `agreed_to_terms` (true), and `payment_method` ("gems")
- Accepts `extra_payload_json` for API fields not hard-coded into the tool

Example:

```json
{
  "domain": "myagent.agent",
  "years": 1,
  "extra_payload_json": "{\"owner_email\":\"me@example.com\"}"
}
```

### `sync_bio`

- Requires `HEADLESSDOMAINS_API_KEY`
- Syncs to the `/domains/<domain>/bio` endpoint
- Sends `domain`, `bio`, and `bio_markdown`
- Accepts `extra_payload_json` for any additional API fields (like `name`, `x`, `github`, etc.)

Example:

```json
{
  "domain": "myagent.agent",
  "bio_markdown": "# About Me",
  "extra_payload_json": "{\"name\":\"My Agent Name\", \"x\":\"twitter_handle\"}"
}
```

## Docker

Build:

```bash
docker build -t headlessdomains-mcp .
```

Run:

```bash
docker run --rm -p 8080:8080 \
  -e PORT=8080 \
  -e HEADLESSDOMAINS_API_KEY=your-api-key-here \
  headlessdomains-mcp
```

## Smoke Testing

After installing dependencies:

```bash
python -m py_compile server.py
python - <<'PY'
import server
print(server.search_domain("example.agent"))
print(server.lookup_whois("test.agent"))
PY
```

## Notes

- `/temp-specs` is ignored in `.gitignore` so local planning docs stay out of version control.
