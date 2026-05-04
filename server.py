import json
import os
from typing import Any, Dict

import requests
from mcp.server.fastmcp import FastMCP
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, JSONResponse
import uvicorn

# Initialize the MCP Server
mcp = FastMCP(
    "HeadlessDomains",
    instructions="Use this server to search for available .agent domains, look up WHOIS records for existing agent domains, and register new domains via MPP."
)

@mcp.resource("ui://search")
def search_ui() -> str:
    """Return the interactive UI for the domain search."""
    return """
    <!DOCTYPE html>
    <html>
    <head>
        <title>Headless Domains Search</title>
        <style>
            body { font-family: system-ui, sans-serif; padding: 20px; text-align: center; }
            .success { color: green; font-weight: bold; }
            .error { color: red; font-weight: bold; }
        </style>
    </head>
    <body>
        <h2>Domain Search Results</h2>
        <div id="results">Waiting for tool result...</div>
        <script>
            window.addEventListener("message", (event) => {
                if (event.data?.method === "ui/notifications/tool-result") {
                    const result = event.data.params.content[0].text;
                    const div = document.getElementById("results");
                    if (result.includes("AVAILABLE")) {
                        div.innerHTML = `<span class="success">${result}</span>`;
                    } else {
                        div.innerHTML = `<span class="error">${result}</span>`;
                    }
                }
            });
        </script>
    </body>
    </html>
    """

@mcp.resource("ui://whois")
def whois_ui() -> str:
    """Return the interactive UI for the WHOIS lookup."""
    return """
    <!DOCTYPE html>
    <html>
    <head>
        <title>Agent WHOIS Profile</title>
        <style>
            body { font-family: system-ui, sans-serif; padding: 20px; }
            .card { background: #f9f9f9; border: 1px solid #ddd; border-radius: 8px; padding: 20px; box-shadow: 0 2px 4px rgba(0,0,0,0.1); }
            h2 { margin-top: 0; color: #333; }
            pre { background: #eee; padding: 10px; border-radius: 4px; overflow-x: auto; }
        </style>
    </head>
    <body>
        <div class="card">
            <h2>🤖 Agent Identity Profile</h2>
            <div id="results">Waiting for WHOIS data...</div>
        </div>
        <script>
            window.addEventListener("message", (event) => {
                if (event.data?.method === "ui/notifications/tool-result") {
                    const result = event.data.params.content[0].text;
                    document.getElementById("results").innerHTML = `<pre>${result}</pre>`;
                }
            });
        </script>
    </body>
    </html>
    """

DEFAULT_API_BASE_URL = "https://headlessdomains.com/api/v1"
DEFAULT_TIMEOUT_SECONDS = 20
DEFAULT_SSE_HOST = "0.0.0.0"
DEFAULT_REGISTER_PATH = "/domains/register"
DEFAULT_SYNC_BIO_PATH = "/domains/sync-bio"
SEARCH_PAGE_URL = "https://headlessdomains.com/search"


def _api_base_url() -> str:
    return os.getenv("HEADLESSDOMAINS_API_BASE_URL", DEFAULT_API_BASE_URL).rstrip("/")


def _request_timeout() -> int:
    raw_timeout = os.getenv("HEADLESSDOMAINS_TIMEOUT", str(DEFAULT_TIMEOUT_SECONDS))
    try:
        return int(raw_timeout)
    except ValueError:
        return DEFAULT_TIMEOUT_SECONDS


def _api_key() -> str:
    return os.getenv("HEADLESSDOMAINS_API_KEY", "").strip()


def _headers(require_api_key: bool = False) -> Dict[str, str]:
    headers = {
        "Accept": "application/json",
        "User-Agent": "headlessdomains-mcp/1.0",
    }
    api_key = _api_key()
    if api_key:
        headers["X-API-Key"] = api_key
    elif require_api_key:
        raise ValueError(
            "HEADLESSDOMAINS_API_KEY is not set. Add it to your environment or Claude Desktop config."
        )
    return headers


def _parse_json_object(raw_json: str, field_name: str) -> Dict[str, Any]:
    if not raw_json.strip():
        return {}

    try:
        parsed = json.loads(raw_json)
    except json.JSONDecodeError as exc:
        raise ValueError(f"{field_name} must be valid JSON.") from exc

    if not isinstance(parsed, dict):
        raise ValueError(f"{field_name} must decode to a JSON object.")

    return parsed


def _request(
    method: str,
    path: str,
    *,
    params: Dict[str, Any] = None,
    json_body: Dict[str, Any] = None,
    require_api_key: bool = False,
) -> Any:
    response = requests.request(
        method=method,
        url=f"{_api_base_url()}{path}",
        params=params,
        json=json_body,
        headers=_headers(require_api_key=require_api_key),
        timeout=_request_timeout(),
    )

    try:
        response.raise_for_status()
    except requests.HTTPError as exc:
        try:
            details = response.json()
        except ValueError:
            details = {"message": response.text[:500]}
        raise RuntimeError(
            f"Headless Domains API request failed with status {response.status_code}: {details}"
        ) from exc

    try:
        return response.json()
    except ValueError:
        return {"status": "ok", "text": response.text}


@mcp.tool()
def search_domain(query: str) -> str:
    """
    Search for available decentralized .agent or .chatbot domains across the Headless Domains ecosystem.

    Args:
        query: The domain name or keyword to search for (e.g. 'janice' or 'janice.agent').
    """
    try:
        data = _request("GET", "/domains/search", params={"q": query})
        results = data.get("results", [])
        
        if not results:
            return f"No results found for '{query}'."

        # Find an exact match if possible, otherwise use the first result
        target = next((r for r in results if r.get("domain") == query), results[0])
        domain = target.get("domain", query)

        warnings = data.get("warnings", [])
        warning_text = f" (Warnings: {', '.join(warnings)})" if warnings else ""

        # Using FastMCP's context object to return UI metadata is not strictly supported by the simple decorator,
        # but we can return the exact JSON structure the client needs. However, since FastMCP wraps returns in a TextContent block,
        # the ora.run scanner is actually checking the server-card.json or the raw `tools/list` response for `_meta.ui`.
        
        if target.get("available"):
            price = target.get("agent_price", target.get("price", "unknown"))
            return f"✅ Domain '{domain}' is AVAILABLE for ${price} USD.{warning_text}"
        else:
            reason = target.get("reason", "Already registered or reserved.")
            return f"❌ Domain '{domain}' is NOT available. Reason: {reason}{warning_text}"
    except (requests.RequestException, RuntimeError, ValueError) as exc:
        return f"Error searching Headless Domains API: {exc}"


@mcp.tool()
def lookup_whois(domain: str) -> dict:
    """
    Perform a WHOIS lookup to get the public profile, SKILL.md, and capabilities of an agent identity.

    Args:
        domain: The full domain name to lookup (e.g. 'myagent.agent').
    """
    try:
        return _request("GET", f"/lookup/{domain}")
    except (requests.RequestException, RuntimeError, ValueError) as exc:
        return {"error": f"Failed to lookup domain: {exc}"}


@mcp.tool()
def register_domain(
    domain: str,
    years: int = 1,
    extra_payload_json: str = "",
) -> dict:
    """
    Register a Headless Domains name using an API key from the environment.

    Args:
        domain: The full domain name to register (e.g. 'myagent.agent').
        years: Number of years to register the domain for.
        extra_payload_json: Optional JSON string merged into the request body.
    """
    try:
        namespace = domain.split(".")[-1] if "." in domain else "agent"
        payload = {
            "domain": domain,
            "namespace": namespace,
            "years": years,
            "agreed_to_terms": True,
            "payment_method": "gems"
        }
        payload.update(_parse_json_object(extra_payload_json, "extra_payload_json"))
        register_path = os.getenv("HEADLESSDOMAINS_REGISTER_PATH", DEFAULT_REGISTER_PATH)
        return _request(
            "POST",
            register_path,
            json_body=payload,
            require_api_key=True,
        )
    except (requests.RequestException, RuntimeError, ValueError) as exc:
        return {"error": f"Failed to register domain: {exc}"}


@mcp.tool()
def sync_bio(
    domain: str,
    bio_markdown: str,
    extra_payload_json: str = "",
) -> dict:
    """
    Sync an agent bio or profile document using an API key from the environment.

    Args:
        domain: The full domain name to update (e.g. 'myagent.agent').
        bio_markdown: The bio or profile markdown/text to sync to the domain.
        extra_payload_json: Optional JSON string merged into the request body.
    """
    try:
        payload = {
            "domain": domain,
            "bio": bio_markdown,
            "bio_markdown": bio_markdown,
        }
        payload.update(_parse_json_object(extra_payload_json, "extra_payload_json"))
        # As per docs, use /domains/<domain>/bio
        sync_bio_path = os.getenv("HEADLESSDOMAINS_SYNC_BIO_PATH", f"/domains/{domain}/bio")
        return _request(
            "POST",
            sync_bio_path,
            json_body=payload,
            require_api_key=True,
        )
    except (requests.RequestException, RuntimeError, ValueError) as exc:
        return {"error": f"Failed to sync bio: {exc}"}


def main() -> None:
    port = os.getenv("PORT")
    transport = os.getenv("MCP_TRANSPORT")

    if port:
        # When running on Railway (or any hosted environment with a PORT),
        # we wrap the FastMCP app in a FastAPI app so we can serve a custom HTML root page.
        app = FastAPI(title="Headless Domains MCP")

        # Allow CORS for Smithery and other MCP registries
        app.add_middleware(
            CORSMiddleware,
            allow_origins=["*"],
            allow_credentials=True,
            allow_methods=["*"],
            allow_headers=["*"],
        )

        @app.get("/", response_class=HTMLResponse)
        async def root():
            return """
            <!DOCTYPE html>
            <html>
            <head>
                <title>Headless Domains MCP</title>
                <style>
                    body { font-family: system-ui, -apple-system, sans-serif; line-height: 1.6; max-width: 800px; margin: 0 auto; padding: 2rem; color: #333; }
                    h1 { color: #1a1a1a; }
                    .card { background: #f8f9fa; border-radius: 8px; padding: 1.5rem; margin-top: 2rem; border: 1px solid #e9ecef; }
                    a { color: #0066cc; text-decoration: none; }
                    a:hover { text-decoration: underline; }
                    code { background: #e9ecef; padding: 0.2rem 0.4rem; border-radius: 4px; font-size: 0.9em; }
                </style>
            </head>
            <body>
                <h1>🌐 Headless Domains MCP Server</h1>
                <p>This is the official <a href="https://modelcontextprotocol.io/" target="_blank">Model Context Protocol (MCP)</a> server for <strong>Headless Domains</strong>.</p>
                <p>It allows AI agents (like Claude, Cursor, and custom agentic frameworks) to natively search for and register decentralized agent identities.</p>
                
                <div class="card">
                    <h2>🔌 How Agents Connect to This Server</h2>
                    <p>The Model Context Protocol (MCP) provides two main ways for an AI agent to connect to this server:</p>
                    
                    <h3>1. Hosted Server (SSE) - 🌟 Recommended</h3>
                    <p>This is the cloud-hosted web server you are currently looking at! It is the best method for widespread adoption because modern agents (like Cursor, Windsurf, or web-based AI tools) can connect directly over the internet without users needing to download or install any Python code.</p>
                    <p><strong>Endpoint URL:</strong> <code>https://mcp.headlessdomains.com/sse</code></p>
                    <p><em>Note: If the user wishes to register domains or sync bios, they must pass their <code>HEADLESSDOMAINS_API_KEY</code> as an environment variable or header when connecting their agent.</em></p>

                    <h3>2. Local Process (stdio)</h3>
                    <p>The AI agent literally runs Python on the user's laptop to start the server locally in the background. This is currently required for <strong>Claude Desktop</strong>. It is secure, but requires the user to install Python and clone the GitHub repository.</p>
                    <p><strong>Command:</strong> <code>mcp run server.py</code></p>
                </div>

                <div class="card">
                    <h2>🔗 Links & Resources</h2>
                    <ul>
                        <li><a href="https://headlessdomains.com" target="_blank">Headless Domains Official Website</a></li>
                        <li><a href="https://github.com/shadstoneofficial/headlessdomains-mcp" target="_blank">GitHub Repository & Documentation</a></li>
                    </ul>
                </div>
                
                <!-- WebMCP Support Hooks -->
                <form action="/mcp/tools/search_domain" data-webmcp="tool" style="display: none;"></form>
                <form action="/mcp/tools/lookup_whois" data-webmcp="tool" style="display: none;"></form>
                <form action="/mcp/tools/register_domain" data-webmcp="tool" style="display: none;"></form>
                <form action="/mcp/tools/sync_bio" data-webmcp="tool" style="display: none;"></form>
            </body>
            </html>
            """

        @app.get("/.well-known/mcp/server-card.json", response_class=JSONResponse)
        async def server_card():
            return {
                "name": "Headless Domains MCP",
                "displayName": "Headless Domains MCP",
                "version": "1.0.0",
                "description": "Official Model Context Protocol server for Headless Domains",
                "icon": "https://headlessdomains.com/favicon.ico",
                "serverUrl": "https://mcp.headlessdomains.com/sse",
                "serverInfo": {
                    "name": "Headless Domains MCP",
                    "displayName": "Headless Domains MCP",
                    "version": "1.0.0"
                },
                "tools": [
                    {
                        "name": "search_domain",
                        "description": "Search for available decentralized .agent or .chatbot domains across the Headless Domains ecosystem.",
                        "_meta": {
                            "ui": {
                                "resourceUri": "ui://search"
                            }
                        },
                        "inputSchema": {
                            "type": "object",
                            "properties": {
                                "query": {"type": "string", "description": "The domain name or keyword to search for (e.g. 'janice' or 'janice.agent')."}
                            },
                            "required": ["query"]
                        }
                    },
                    {
                        "name": "lookup_whois",
                        "description": "Perform a WHOIS lookup to get the public profile, SKILL.md, and capabilities of an agent identity.",
                        "_meta": {
                            "ui": {
                                "resourceUri": "ui://whois"
                            }
                        },
                        "inputSchema": {
                            "type": "object",
                            "properties": {
                                "domain": {"type": "string", "description": "The full domain name to lookup (e.g. 'myagent.agent')."}
                            },
                            "required": ["domain"]
                        }
                    },
                    {
                        "name": "register_domain",
                        "description": "Register a Headless Domains name using an API key from the environment.",
                        "inputSchema": {
                            "type": "object",
                            "properties": {
                                "domain": {"type": "string", "description": "The full domain name to register (e.g. 'myagent.agent')."},
                                "years": {"type": "integer", "description": "Number of years to register the domain for.", "default": 1},
                                "extra_payload_json": {"type": "string", "description": "Optional JSON string merged into the request body.", "default": ""}
                            },
                            "required": ["domain"]
                        }
                    },
                    {
                        "name": "sync_bio",
                        "description": "Sync an agent bio or profile document using an API key from the environment.",
                        "inputSchema": {
                            "type": "object",
                            "properties": {
                                "domain": {"type": "string", "description": "The full domain name to update (e.g. 'myagent.agent')."},
                                "bio_markdown": {"type": "string", "description": "The bio or profile markdown/text to sync to the domain."},
                                "extra_payload_json": {"type": "string", "description": "Optional JSON string merged into the request body.", "default": ""}
                            },
                            "required": ["domain", "bio_markdown"]
                        }
                    }
                ]
            }

        @app.get("/mcp.json", response_class=JSONResponse)
        async def mcp_json():
            return {
                "name": "Headless Domains MCP",
                "description": "Official Model Context Protocol server for Headless Domains",
                "icon": "https://headlessdomains.com/favicon.ico",
                "mcpServers": {
                    "headlessdomains": {
                        "command": "python",
                        "args": ["server.py"]
                    }
                }
            }

        @app.get("/.well-known/ai-plugin.json", response_class=JSONResponse)
        async def ai_plugin():
            return {
                "schema_version": "v1",
                "name_for_human": "Headless Domains MCP",
                "name_for_model": "headless_domains_mcp",
                "description_for_human": "Official Model Context Protocol server for Headless Domains",
                "description_for_model": "Allows AI agents to natively search for and register decentralized agent identities.",
                "auth": {"type": "none"},
                "api": {"type": "openapi", "url": "https://mcp.headlessdomains.com/openapi.json"},
                "logo_url": "https://headlessdomains.com/favicon.ico",
                "contact_email": "support@headlessdomains.com",
                "legal_info_url": "https://headlessdomains.com/terms"
            }

        @app.get("/.well-known/mcp", response_class=JSONResponse)
        async def well_known_mcp():
            return {
                "mcpVersion": "2024-11-05",
                "serverUrl": "https://mcp.headlessdomains.com/sse",
                "name": "Headless Domains MCP",
                "displayName": "Headless Domains MCP",
                "version": "1.0.0",
                "description": "Official Model Context Protocol server for Headless Domains",
                "icon": "https://headlessdomains.com/favicon.ico",
                "transport": "sse"
            }

        # Mount the FastMCP ASGI app onto the FastAPI app
        # This automatically exposes the /sse and /messages endpoints required by MCP clients
        
        # Disable DNS rebinding protection so custom domains (mcp.headlessdomains.com) don't get 421 Invalid Host header
        if hasattr(mcp.settings, "transport_security"):
            mcp.settings.transport_security.enable_dns_rebinding_protection = False
            mcp.settings.transport_security.allowed_hosts = ["*"]
            mcp.settings.transport_security.allowed_origins = ["*"]

        mcp_app = mcp.sse_app()
        app.mount("/", mcp_app)

        # Run the combined app
        uvicorn.run(app, host="0.0.0.0", port=int(port))
        return

    # Fallback for local CLI usage (stdio)
    mcp.run(transport=transport or "stdio")


if __name__ == "__main__":
    main()
