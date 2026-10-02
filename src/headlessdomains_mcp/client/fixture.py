from __future__ import annotations

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


class FixtureHeadlessDomainsClient:
    """Deterministic local data. It never contacts HeadlessDomains production."""

    _registered = {
        "atlas.agent": {
            "owner": "Atlas Labs",
            "capabilities": ["name resolution", "MCP discovery", "agent inbox"],
        },
        "janice.agent": {
            "owner": "Janice",
            "capabilities": ["name resolution", "portfolio management"],
        },
        "resolver.chatbot": {
            "owner": "HeadlessDomains Demo",
            "capabilities": ["Handshake resolution"],
        },
    }

    async def lookup_name(self, name: str) -> LookupResult:
        normalized = _normalize_name(name)
        item = self._registered.get(normalized)
        if item is None:
            return LookupResult(
                query=name,
                normalized_name=normalized,
                status="available",
                resolver=ResolverSummary(status="unregistered", canonical_name=normalized, source="fixture"),
                links={"search": f"https://headlessdomains.com/search?q={normalized}"},
                warnings=["Fixture data: no production request was made."],
            )

        capabilities = [CapabilitySummary(name=value) for value in item["capabilities"]]
        endpoints = [
            EndpointSummary(
                kind="agent-manifest",
                url=f"https://headlessdomains.com/manifests/{normalized}.json",
                source="fixture",
            ),
            EndpointSummary(
                kind="skill",
                url=f"https://headlessdomains.com/skills/{normalized}.md",
                source="fixture",
            ),
        ]
        return LookupResult(
            query=name,
            normalized_name=normalized,
            status="registered",
            resolver=ResolverSummary(status="resolved", canonical_name=normalized, source="fixture"),
            owner=OwnerSummary(display_name=str(item["owner"])),
            capabilities=capabilities,
            endpoints=endpoints,
            links={
                "public": f"https://headlessdomains.com/lookup?name={normalized}",
                "manage": "https://headlessdomains.com/my-domains",
            },
            warnings=["Fixture data: no production request was made."],
        )

    async def check_availability(
        self,
        query: str,
        namespaces: list[str] | None = None,
    ) -> AvailabilityResult:
        normalized = _normalize_name(query)
        if "." in normalized:
            label, namespace = normalized.rsplit(".", 1)
            candidates = [(label, namespace)]
        else:
            candidates = [(normalized, namespace) for namespace in (namespaces or ["agent", "chatbot"])]

        matches: list[AvailabilityMatch] = []
        for label, namespace in candidates:
            full_name = f"{label}.{namespace}"
            available = full_name not in self._registered
            matches.append(
                AvailabilityMatch(
                    name=full_name,
                    namespace=namespace,
                    available=available,
                    status="available" if available else "registered",
                    reason=None if available else "Already registered in the local fixture.",
                    registration_price=Money(amount=9.95 if namespace == "agent" else 12.0),
                )
            )
        return AvailabilityResult(
            query=query,
            matches=matches,
            warnings=["Fixture data: prices and availability are demonstrations only."],
        )

    async def list_my_names(
        self,
        query: str | None = None,
        cursor: str | None = None,
        limit: int = 25,
    ) -> PortfolioResult:
        names = ["janice.agent", "atlas.agent"]
        if query:
            needle = query.strip().lower()
            names = [name for name in names if needle in name]
        offset = int(cursor or "0")
        page = names[offset : offset + limit]
        next_cursor = str(offset + limit) if offset + limit < len(names) else None
        return PortfolioResult(
            names=[
                PortfolioName(
                    name=name,
                    status="active",
                    expires_at="2027-10-01T00:00:00Z",
                    links={"manage": "https://headlessdomains.com/my-domains"},
                )
                for name in page
            ],
            next_cursor=next_cursor,
            message="Fixture portfolio: no account was accessed.",
        )

    async def get_records(
        self,
        name: str,
        types: list[str] | None = None,
    ) -> RecordsResult:
        normalized = _normalize_name(name)
        if normalized not in self._registered:
            return RecordsResult(
                name=normalized,
                resolver_status="unregistered",
                records=[],
                warnings=["Fixture data: no production request was made."],
            )
        records = [
            NameRecord(
                type="TXT",
                name=normalized,
                value="agent=enabled",
                ttl=300,
                source="fixture",
            ),
            NameRecord(
                type="AGENT_JSON",
                name=normalized,
                value=f"https://headlessdomains.com/manifests/{normalized}.json",
                ttl=None,
                source="fixture",
            ),
            NameRecord(
                type="SKILL",
                name=normalized,
                value=f"https://headlessdomains.com/skills/{normalized}.md",
                ttl=None,
                source="fixture",
            ),
        ]
        if types:
            allowed = {item.strip().upper() for item in types}
            records = [record for record in records if record.type.upper() in allowed]
        return RecordsResult(
            name=normalized,
            resolver_status="resolved",
            records=records,
            warnings=["Fixture data: these are demonstration records."],
        )

    async def mention_names(self, query: str, limit: int = 30) -> list[str]:
        needle = query.strip().lower()
        return [name for name in self._registered if needle in name][:limit]

