from __future__ import annotations

import os
from dataclasses import dataclass


@dataclass(frozen=True)
class Settings:
    data_mode: str
    api_base_url: str
    api_token: str | None
    timeout_seconds: float
    host: str
    port: int

    @classmethod
    def from_env(cls) -> "Settings":
        data_mode = os.getenv("HEADLESSDOMAINS_DATA_MODE", "fixture").strip().lower()
        if data_mode not in {"fixture", "production"}:
            raise ValueError("HEADLESSDOMAINS_DATA_MODE must be 'fixture' or 'production'.")

        token = os.getenv("HEADLESSDOMAINS_API_TOKEN", "").strip() or None
        return cls(
            data_mode=data_mode,
            api_base_url=os.getenv(
                "HEADLESSDOMAINS_API_BASE_URL",
                "https://headlessdomains.com/api/v1",
            ).rstrip("/"),
            api_token=token,
            timeout_seconds=float(os.getenv("HEADLESSDOMAINS_TIMEOUT", "20")),
            host=os.getenv("HOST", "127.0.0.1"),
            port=int(os.getenv("PORT", "8787")),
        )

