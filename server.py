import json
import os
from typing import Any, Dict

import requests
from mcp.server.fastmcp import FastMCP

# Initialize the MCP Server
mcp = FastMCP("HeadlessDomains")

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
    Check if a .agent or .chatbot domain is available for registration.

    Args:
        query: The domain name to search (e.g. "myagent", "foo.agent").
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
        domain: The full domain name (e.g. "myagent.agent").
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
        domain: The full domain to register.
        years: Number of years to register the domain for.
        extra_payload_json: Optional JSON object merged into the request body.
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
        domain: The full domain to update.
        bio_markdown: The bio or profile markdown/text to sync.
        extra_payload_json: Optional JSON object merged into the request body.
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
        mcp.settings.host = os.getenv("HOST", DEFAULT_SSE_HOST)
        mcp.settings.port = int(port)
        
        # Disable DNS rebinding protection to allow Railway and custom domains
        if hasattr(mcp.settings, "transport_security"):
            mcp.settings.transport_security.enable_dns_rebinding_protection = False
            mcp.settings.transport_security.allowed_hosts = ["*"]
            mcp.settings.transport_security.allowed_origins = ["*"]
            
        mcp.run(transport=transport or "sse")
        return

    mcp.run(transport=transport or "stdio")


if __name__ == "__main__":
    main()
