from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field
from pydantic.alias_generators import to_camel


class ApiModel(BaseModel):
    model_config = ConfigDict(alias_generator=to_camel, populate_by_name=True)


class Money(ApiModel):
    amount: float
    currency: str = "USD"
    term_years: int = 1


class AvailabilityMatch(ApiModel):
    name: str
    namespace: str
    available: bool
    status: str
    reason: str | None = None
    registration_price: Money | None = None


class AvailabilityResult(ApiModel):
    query: str
    matches: list[AvailabilityMatch]
    warnings: list[str] = Field(default_factory=list)


class ResolverSummary(ApiModel):
    status: str
    canonical_name: str | None = None
    source: str = "headlessdomains"


class OwnerSummary(ApiModel):
    display_name: str | None = None
    identifier: str | None = None


class CapabilitySummary(ApiModel):
    name: str
    description: str | None = None
    endpoint: str | None = None


class EndpointSummary(ApiModel):
    kind: str
    url: str
    source: str


class LookupResult(ApiModel):
    query: str
    normalized_name: str
    status: Literal["registered", "available", "reserved", "unknown"]
    resolver: ResolverSummary
    owner: OwnerSummary | None = None
    capabilities: list[CapabilitySummary] = Field(default_factory=list)
    endpoints: list[EndpointSummary] = Field(default_factory=list)
    links: dict[str, str] = Field(default_factory=dict)
    warnings: list[str] = Field(default_factory=list)


class PortfolioName(ApiModel):
    name: str
    status: str
    expires_at: str | None = None
    links: dict[str, str] = Field(default_factory=dict)


class PortfolioResult(ApiModel):
    names: list[PortfolioName]
    next_cursor: str | None = None
    auth_required: bool = False
    message: str | None = None


class NameRecord(ApiModel):
    type: str
    name: str
    value: Any
    ttl: int | None = None
    source: str


class RecordsResult(ApiModel):
    name: str
    resolver_status: str
    records: list[NameRecord]
    warnings: list[str] = Field(default_factory=list)


class AppSnapshot(ApiModel):
    view: Literal["sidebar", "thread"]
    data_mode: Literal["fixture", "production"]
    production_wiring: dict[str, str]

