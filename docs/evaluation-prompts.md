# Local evaluation prompts

Run these in a new ChatGPT conversation after each metadata refresh.

## Expected tool calls

- “Is atlas.agent registered?” → `lookup_name`
- “Check atlas across the available namespaces.” → `check_availability`
- “Show the names in my connected account.” → `list_my_names`
- “Show the raw published records for atlas.agent.” → `get_records`
- Open **HeadlessDomains** from the sidebar → `headlessdomains.app`
- Open the **HeadlessDomains name inspector** beside a conversation → `headlessdomains.name_panel`

## Follow-ups

- “Now inspect its endpoints and capabilities.” after a lookup.
- “Only show TXT records.” after a record request.
- Select a name from the portfolio and verify that the inspector opens it without exposing credentials.

## Edge and negative cases

- Empty query should be rejected by schema validation.
- A name longer than 255 characters should be rejected.
- An unknown fixture name should return `available`, not fabricate an owner.
- “Register atlas.agent for me” should be declined as unsupported by this read-only plugin.
- “Renew all my names” should not select any write tool.
- Production portfolio without server authentication should return a clear account-connection requirement.

