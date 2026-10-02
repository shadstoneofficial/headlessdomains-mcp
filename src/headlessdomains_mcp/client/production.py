from __future__ import annotations

from typing import Any
from urllib.parse import quote

import httpx

from headlessdomains_mcp.client.base import AuthenticationRequired
from headlessdomains_mcp.config import Settings
from headlessdomains_mcp.models import (
    AvailabilityMatch,
    AvailabilityResult,
    CapabilitySummary,
    EndpointSummary,
    LookupResult,
    Money,
    NameRecord,
    OwnerSummary,
    PortfolioName,
    PortfolioResult,
    RecordsResult,
    ResolverSummary,
)


def _normalize_name(value: str) -> str:
    normalized = value.strip().lower().rstrip(".")
    if not normalized or len(normalized) > 255:
        raise ValueError("name must contain between 1 and 255 characters")
    return normalized


class ProductionHeadlessDomainsClient:
    """Read-only adapter for the existing headlessdomains.com API."""

    def __init__(self, settings: Settings):
        self.settings = settings

    def _headers(self, *, authenticated: bool = False) -> dict[str, str]:
        headers = {
            "Accept": "application/json",
            "User-Agent": "headlessdomains-chatgpt-plugin/0.1.0",
        }
        if authenticated:
            if not self.settings.api_token:
                raise AuthenticationRequired(
                    "The production portfolio tool needs server-side account authentication. "
                    "For local development, set HEADLESSDOMAINS_API_TOKEN; ChatGPT OAuth is not wired yet."
                )
            headers["Authorization"] = f"Bearer {self.settings.api_token}"
        return headers

    async def _get(
        self,
        path: str,
        *,
        params: dict[str, Any] | None = None,
        authenticated: bool = False,
        allow_not_found: bool = False,
    ) -> dict[str, Any] | None:
        async with httpx.AsyncClient(
            base_url=self.settings.api_base_url,
            timeout=self.settings.timeout_seconds,
            follow_redirects=True,
        ) as client:
            response = await client.get(
                path,
                params=params,
                headers=self._headers(authenticated=authenticated),
            )
        if allow_not_found and response.status_code == 404:
            return None
        response.raise_for_status()
        data = response.json()
        if not isinstance(data, dict):
            raise RuntimeError("HeadlessDomains returned a non-object JSON response.")
        return data

    async def lookup_name(self, name: str) -> LookupResult:
        normalized = _normalize_name(name)
        payload = await self._get(f"/lookup/{quote(normalized, safe='.')}", allow_not_found=True)
        if payload is None:
            availability = await self.check_availability(normalized)
            match = next((item for item in availability.matches if item.name == normalized), None)
            status = "available" if match and match.available else "unknown"
            return LookupResult(
                query=name,
                normalized_name=normalized,
                status=status,
                resolver=ResolverSummary(status="unregistered", canonical_name=normalized),
                links={"search": f"https://headlessdomains.com/search?q={quote(normalized)}"},
                warnings=availability.warnings,
            )

        domain = payload.get("domain") if isinstance(payload.get("domain"), dict) else {}
        identity = payload.get("identity") if isinstance(payload.get("identity"), dict) else {}
        profile = payload.get("profile") if isinstance(payload.get("profile"), dict) else {}
        integrations = payload.get("integrations") if isinstance(payload.get("integrations"), dict) else {}
        manifests = payload.get("manifests") if isinstance(payload.get("manifests"), dict) else {}

        capabilities = [
            CapabilitySummary(name=str(item))
            for item in identity.get("capabilities_preview", [])
            if item
        ]
        endpoints: list[EndpointSummary] = []
        for key, value in manifests.items():
            if isinstance(value, str) and value.startswith(("https://", "http://")):
                endpoints.append(EndpointSummary(kind=key, url=value, source="lookup.manifests"))
        for key, value in integrations.items():
            if isinstance(value, dict) and value.get("enabled") and isinstance(value.get("url"), str):
                endpoints.append(EndpointSummary(kind=key, url=value["url"], source="lookup.integrations"))

        owner_name = profile.get("name") or profile.get("display_name")
        return LookupResult(
            query=name,
            normalized_name=str(domain.get("name") or normalized),
            status="registered",
            resolver=ResolverSummary(
                status=str(domain.get("status") or "resolved"),
                canonical_name=str(domain.get("name") or normalized),
            ),
            owner=OwnerSummary(display_name=str(owner_name)) if owner_name else None,
            capabilities=capabilities,
            endpoints=endpoints,
            links={
                "public": f"https://headlessdomains.com/lookup?name={quote(normalized)}",
                "manage": "https://headlessdomains.com/my-domains",
            },
            warnings=[
                "The public lookup API does not currently expose a normalized owner identifier."
            ] if owner_name is None else [],
        )

    async def check_availability(
        self,
        query: str,
        namespaces: list[str] | None = None,
    ) -> AvailabilityResult:
        normalized = _normalize_name(query)
        payload = await self._get("/domains/search", params={"q": normalized})
        assert payload is not None
        allowed = {item.strip().lower().lstrip(".") for item in namespaces or []}
        matches: list[AvailabilityMatch] = []
        for raw in payload.get("results", []):
            if not isinstance(raw, dict):
                continue
            name = str(raw.get("domain") or "")
            namespace = str(raw.get("tld") or (name.rsplit(".", 1)[-1] if "." in name else ""))
            if allowed and namespace.lower() not in allowed:
                continue
            available = bool(raw.get("available"))
            price = raw.get("agent_price", raw.get("price"))
            matches.append(
                AvailabilityMatch(
                    name=name,
                    namespace=namespace,
                    available=available,
                    status="available" if available else str(raw.get("status") or "unavailable"),
                    reason=str(raw.get("reason")) if raw.get("reason") is not None else None,
                    registration_price=Money(amount=float(price)) if isinstance(price, int | float) else None,
                )
            )
        return AvailabilityResult(
            query=str(payload.get("query") or query),
            matches=matches,
            warnings=[str(item) for item in payload.get("warnings", [])],
        )

    async def list_my_names(
        self,
        query: str | None = None,
        cursor: str | None = None,
        limit: int = 25,
    ) -> PortfolioResult:
        payload = await self._get("/domains", authenticated=True)
        assert payload is not None
        rows = [item for item in payload.get("data", []) if isinstance(item, dict)]
        if query:
            needle = query.strip().lower()
            rows = [item for item in rows if needle in str(item.get("name", "")).lower()]
        offset = int(cursor or "0")
        page = rows[offset : offset + limit]
        next_cursor = str(offset + limit) if offset + limit < len(rows) else None
        return PortfolioResult(
            names=[
                PortfolioName(
                    name=str(item.get("name") or ""),
                    status=str(item.get("status") or "unknown"),
                    expires_at=str(item["expiry_date"]) if item.get("expiry_date") else None,
                    links={
                        "manage": (
                            f"https://headlessdomains.com{item['management_path']}"
                            if str(item.get("management_path", "")).startswith("/")
                            else "https://headlessdomains.com/my-domains"
                        )
                    },
                )
                for item in page
                if item.get("name")
            ],
            next_cursor=next_cursor,
        )

    async def get_records(
        self,
        name: str,
        types: list[str] | None = None,
    ) -> RecordsResult:
        normalized = _normalize_name(name)
        payload = await self._get(f"/lookup/{quote(normalized, safe='.')}", allow_not_found=True)
        if payload is None:
            return RecordsResult(name=normalized, resolver_status="unregistered", records=[])

        records: list[NameRecord] = []
        for section_name in ("profile", "integrations", "manifests"):
            section = payload.get(section_name)
            if not isinstance(section, dict):
                continue
            for key, value in section.items():
                records.append(
                    NameRecord(
                        type=f"{section_name.upper()}_{str(key).upper()}",
                        name=normalized,
                        value=value,
                        ttl=None,
                        source=f"lookup.{section_name}",
                    )
                )
        if types:
            allowed = {item.strip().upper() for item in types}
            records = [record for record in records if record.type.upper() in allowed]
        return RecordsResult(
            name=normalized,
            resolver_status="resolved",
            records=records,
            warnings=[
                "Derived from the public lookup response; HeadlessDomains does not yet expose a raw read-only DNS-record endpoint."
            ],
        )

    async def mention_names(self, query: str, limit: int = 30) -> list[str]:
        result = await self.check_availability(query)
        return [item.name for item in result.matches][:limit]

