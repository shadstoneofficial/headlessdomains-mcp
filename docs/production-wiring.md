# Production wiring ledger

Reviewed against the local `headlessdomains-com` source on 2026-10-02.

| Capability | Fixture mode | Production mode | Authentication | Status |
|---|---|---|---|---|
| `lookup_name` | Deterministic registered and available names | `GET /api/v1/lookup/{name}`; 404 is cross-checked through availability | Anonymous | Wired read-only |
| `check_availability` | Deterministic `.agent` and `.chatbot` results | `GET /api/v1/domains/search?q=...` | Anonymous | Wired read-only |
| `list_my_names` | Demo portfolio | `GET /api/v1/domains` | Development server-side GFAVIP bearer token | Wired for local development; ChatGPT OAuth pending |
| `get_records` | Demonstration TXT, manifest, and skill records | Derived from `profile`, `integrations`, and `manifests` in public lookup | Anonymous | Partial; raw record-read endpoint pending |
| Sidebar and thread UI | Full fixture workflow | Uses the same MCP tools | No secrets in iframe | Implemented locally |
| Composer mentions | Searches fixture names | Uses production availability search | Anonymous | Implemented locally; desktop host verification pending |

## Not implemented

- Registration or renewal.
- Payments.
- Record changes.
- A raw read-only DNS-record API.
- OAuth 2.1 account linking for ChatGPT.
- MCP Events.
- File handlers or rich forms.
- Production deployment or directory publication.

