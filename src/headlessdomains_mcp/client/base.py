from __future__ import annotations

from typing import Protocol

from headlessdomains_mcp.models import (
    AvailabilityResult,
    LookupResult,
    PortfolioResult,
    RecordsResult,
)


class AuthenticationRequired(RuntimeError):
    """Raised when an account-scoped read has no server-side credential."""


class HeadlessDomainsClient(Protocol):
    async def lookup_name(self, name: str) -> LookupResult: ...

    async def check_availability(
        self,
        query: str,
        namespaces: list[str] | None = None,
    ) -> AvailabilityResult: ...

    async def list_my_names(
        self,
        query: str | None = None,
        cursor: str | None = None,
        limit: int = 25,
    ) -> PortfolioResult: ...

    async def get_records(
        self,
        name: str,
        types: list[str] | None = None,
    ) -> RecordsResult: ...

    async def mention_names(self, query: str, limit: int = 30) -> list[str]: ...

